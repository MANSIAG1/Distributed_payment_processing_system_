# server/consensus/raft.py
import threading
import time
import random
import json
import os
from common import utils
from config import config
from server.time_sync.vector_clock import VectorClock

from proto import consensus_pb2
from proto import consensus_pb2_grpc
import grpc
import time as pytime

class RaftNode(consensus_pb2_grpc.ConsensusServiceServicer):
    """
    Minimal Raft-like node:
    - Maintains currentTerm, votedFor, log (list of entries)
    - Supports RequestVote and AppendEntries RPCs
    - Has a background election timer to become leader in absence of heartbeats
    This is simplified for educational/demo use.
    """

    def __init__(self):
        self.node_id = config.NODE_ID
        self.current_term = 0
        self.voted_for = None
        self.log = []  # list of entries (dicts)
        self.commit_index = -1
        self.lock = threading.Lock()
        self.leader_id = None
        self.peers = dict(config.PEER_NODES)
        self.election_timeout = config.ELECTION_TIMEOUT
        self.heartbeat_interval = config.HEARTBEAT_INTERVAL
        self.running = True
        
  
        
        # Initialize vector clock with all nodes
        all_nodes = [self.node_id] + list(self.peers.keys())
        self.vector_clock = VectorClock(self.node_id, all_nodes)
        utils.log_event(f"[RAFT:{self.node_id}] Initialized vector clock with nodes: {all_nodes}")

        # background election thread
        self.election_thread = threading.Thread(target=self._run_election_timer, daemon=True)
        self.election_thread.start()
        # background heartbeat sender if leader
        self.heartbeat_thread = threading.Thread(target=self._maybe_send_heartbeats, daemon=True)
        self.heartbeat_thread.start()

        # map index->event (simple waiters)
        self.commit_waiters = {}  # index -> threading.Event
        self.last_heartbeat_time = pytime.time()

    # --- RPC implementations ---
    def RequestVote(self, request, context):
        with self.lock:
            rv = False
            if request.term < self.current_term:
                rv = False
            else:
                # grant vote if not voted this term
                if self.voted_for is None or self.voted_for == request.candidate_id:
                    self.voted_for = request.candidate_id
                    self.current_term = request.term
                    rv = True
            utils.log_event(f"[RAFT:{self.node_id}] RequestVote from {request.candidate_id} term={request.term} granted={rv}")
            return consensus_pb2.VoteResponse(vote_granted=rv, term=self.current_term)

    def AppendEntries(self, request, context):
        with self.lock:
            # treat as heartbeat if entries empty
            self.current_term = max(self.current_term, request.term)
            self.leader_id = request.leader_id
            self.last_heartbeat_time = pytime.time()
            
            # Update vector clock on receiving entries
            if hasattr(request, 'vector_clock') and request.vector_clock:
                leader_clock = {k: v for k, v in request.vector_clock.clock.items()}
                self.vector_clock.update(leader_clock)
                utils.log_event(f"[RAFT:{self.node_id}] Updated vector clock: {self.vector_clock}")
            
            if len(request.entries) > 0:
                for e in request.entries:
                    # Convert entry vector clock to dict
                    entry_vclock = {k: v for k, v in e.vector_time.clock.items()} if e.vector_time else self.vector_clock.get_clock()
                    
                    # convert LogEntry proto -> dict and include vector timestamp
                    entry = {
                        "user_id": e.user_id,
                        "amount": e.amount,
                        "status": e.status,
                        "timestamp": e.timestamp,
                        "vector_time": entry_vclock
                    }
                    self.log.append(entry)
                    utils.log_event(f"[RAFT:{self.node_id}] Appended entry from leader {request.leader_id}")
                # mark latest as committed by leader_commit index
                self.commit_index = max(self.commit_index, request.leader_commit)
                
                # Tick vector clock after processing entries
                self.vector_clock.tick()
            
            # Create response vector clock
            response_vclock = consensus_pb2.VectorClockMap()
            for node, time in self.vector_clock.get_clock().items():
                response_vclock.clock[node] = time
                
            return consensus_pb2.AppendEntriesResponse(
                term=self.current_term,
                success=True,
                vector_clock=response_vclock
            )

    # --- client api for local node to propose entries ---
    def propose(self, entry):
        """
        Called by PaymentService to propose an entry to the cluster.
        If this node is leader, append to local log and send AppendEntries to followers.
        If not leader, attempt to forward to leader (handled by node code).
        Returns the log index of the appended entry.
        """
        with self.lock:
            # Update vector clock for new entry
            self.vector_clock.tick()
            entry["vector_time"] = self.vector_clock.get_clock()
            
            entry_index = len(self.log)
            self.log.append(entry)
            utils.log_event(f"[RAFT:{self.node_id}] Proposed entry at index {entry_index} with vector time {entry['vector_time']}")
            # create a waiter that will be set when commit_index >= entry_index
            evt = threading.Event()
            self.commit_waiters[entry_index] = evt

        # If leader, send AppendEntries immediately
        if self.get_leader() == self.node_id:
            self._broadcast_append([entry])
            # simulate commit when majority ack (we simplify as immediate)
            self._mark_committed(entry_index)
        else:
            # not leader; return index but commit will be handled when forwarded/proposed by leader
            pass

        return entry_index

    def wait_for_commit(self, index, timeout=5):
        """
        Wait for a log index to be committed. Returns True if committed.
        """
        evt = None
        with self.lock:
            evt = self.commit_waiters.get(index)
            if evt is None:
                # if already committed
                return index <= self.commit_index
        finished = evt.wait(timeout=timeout)
        with self.lock:
            return index <= self.commit_index

    # --- internal helpers ---
    def get_leader(self):
        with self.lock:
            return self.leader_id

    def _mark_committed(self, index):
        with self.lock:
            if index > self.commit_index:
                self.commit_index = index
                # trigger waiter events up to commit_index
                to_remove = []
                for i, evt in list(self.commit_waiters.items()):
                    if i <= self.commit_index:
                        evt.set()
                        to_remove.append(i)
                for i in to_remove:
                    del self.commit_waiters[i]
                utils.log_event(f"[RAFT:{self.node_id}] Commit index advanced to {self.commit_index}")

    def _broadcast_append(self, entries):
        """
        Send AppendEntries RPC to all peers (best-effort).
        """
        # Increment vector clock before broadcast
        self.vector_clock.tick()
        
        for pid, addr in self.peers.items():
            try:
                with grpc.insecure_channel(addr) as channel:
                    stub = consensus_pb2_grpc.ConsensusServiceStub(channel)
                    # construct LogEntry protos
                    le_proto_list = []
                    for e in entries:
                        # Create vector clock map for the entry
                        entry_vclock = consensus_pb2.VectorClockMap()
                        for node, time in e.get("vector_time", self.vector_clock.get_clock()).items():
                            entry_vclock.clock[node] = time
                            
                        le = consensus_pb2.LogEntry(
                            user_id=e["user_id"],
                            amount=e["amount"],
                            status=e.get("status",""),
                            timestamp=e.get("timestamp",""),
                            vector_time=entry_vclock
                        )
                        le_proto_list.append(le)
                        
                    # Create vector clock map for the request
                    vclock = consensus_pb2.VectorClockMap()
                    for node, time in self.vector_clock.get_clock().items():
                        vclock.clock[node] = time
                        
                    req = consensus_pb2.AppendEntriesRequest(
                        term=self.current_term,
                        leader_id=self.node_id,
                        prev_log_index=len(self.log)-len(entries)-1,
                        prev_log_term=self.current_term,
                        entries=le_proto_list,
                        leader_commit=self.commit_index,
                        vector_clock=vclock
                    )
                    response = stub.AppendEntries(req, timeout=config.RPC_TIMEOUT)
                    
                    # Update vector clock with follower's response
                    if hasattr(response, 'vector_clock') and response.vector_clock:
                        follower_clock = {k: v for k, v in response.vector_clock.clock.items()}
                        self.vector_clock.update(follower_clock)
                        utils.log_event(f"[RAFT:{self.node_id}] Updated vector clock from {pid}: {self.vector_clock}")
            except Exception as ex:
                utils.log_event(f"[RAFT:{self.node_id}] Error broadcasting to {pid}: {ex}")

    def _run_election_timer(self):
        """
        Basic election timer: if no leader for a randomized timeout, try to become leader by requesting votes.
        """
        while self.running:
            # randomized timeout
            timeout = self.election_timeout + random.uniform(0, self.election_timeout)
            time.sleep(timeout)
            # check if leader known/recent
            with self.lock:
                leader = self.leader_id
                time_since_heartbeat = pytime.time() - self.last_heartbeat_time
            if leader is None or time_since_heartbeat > self.election_timeout:
                # start election
                with self.lock:
                    self.leader_id = None
                self._start_election()

    def _start_election(self):
        with self.lock:
            self.current_term += 1
            self.voted_for = self.node_id
            self_votes = 1
            target_term = self.current_term
        utils.log_event(f"[RAFT:{self.node_id}] Starting election term={target_term}")
        failed_votes = 0
        for pid, addr in self.peers.items():
            try:
                with grpc.insecure_channel(addr) as channel:
                    stub = consensus_pb2_grpc.ConsensusServiceStub(channel)
                    req = consensus_pb2.VoteRequest(term=target_term, candidate_id=self.node_id,
                                                    last_log_index=len(self.log)-1, last_log_term=self.current_term)
                    resp = stub.RequestVote(req, timeout=config.RPC_TIMEOUT)
                    if resp.vote_granted:
                        self_votes += 1
            except Exception as e:
                failed_votes += 1
                utils.log_event(f"[RAFT:{self.node_id}] Vote request to {pid} failed: {e}")

        majority = (len(self.peers) + 1) // 2 + 1
        if failed_votes == len(self.peers):
            utils.log_event(f"[RAFT:{self.node_id}] WARNING: All vote requests failed. Check network and peer configuration.")
        if self_votes >= majority and failed_votes < len(self.peers):
            with self.lock:
                self.leader_id = self.node_id
            utils.log_event(f"[RAFT:{self.node_id}] Became LEADER with {self_votes} votes (term {self.current_term})")
        else:
            utils.log_event(f"[RAFT:{self.node_id}] Election failed ({self_votes} votes)")

    def _maybe_send_heartbeats(self):
        """
        If leader, periodically send empty AppendEntries as heartbeat.
        """
        while self.running:
            if self.get_leader() == self.node_id:
                # send heartbeat
                try:
                    self._broadcast_append([])
                except Exception as e:
                    utils.log_event(f"[RAFT:{self.node_id}] Heartbeat error: {e}")
            time.sleep(self.heartbeat_interval)


    def stop(self):
        self.running = False