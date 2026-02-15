# server/node/node_server.py
import threading
import json
import os
import time
from datetime import datetime
import uuid
import grpc

from common import utils
from config import config

# gRPC generated modules
from proto import payment_pb2
from proto import payment_pb2_grpc
from proto import replication_pb2
from proto import replication_pb2_grpc
from proto import consensus_pb2
from proto import consensus_pb2_grpc

# Import local modules (replication + consensus instances will be created at runtime)
from server.replication.replicator import Replicator
from server.consensus.raft import RaftNode

LEDGER_FILE = config.LEDGER_FILE

class PaymentService(payment_pb2_grpc.PaymentServiceServicer):
    """
    Implements ProcessPayment and GetHistory.
    Each node can accept payments; leader will replicate entries via Replicator.
    """

    def __init__(self, raft_node=None, replicator=None):
        self.raft = raft_node  # RaftNode instance
        self.replicator = replicator  # Replicator instance
        self.ledger_lock = threading.Lock()
        # ensure ledger file exists
        if not os.path.exists(LEDGER_FILE):
            with open(LEDGER_FILE, "w") as f:
                json.dump([], f)

    def _append_local_ledger(self, entry):
        with self.ledger_lock:
            with open(LEDGER_FILE, "r+") as f:
                try:
                    ledger = json.load(f)
                except Exception:
                    ledger = []
                ledger.append(entry)
                f.seek(0)
                json.dump(ledger, f, indent=2)
                f.truncate()
        utils.log_event(f"[LEDGER] Appended entry {entry['tx_id']} locally")

    def ProcessPayment(self, request, context):
        """
        Process a payment.
        If this node is leader, append to local log, replicate via replicator and commit.
        If not leader, redirect or forward to leader address.
        """
        tx_id = str(uuid.uuid4())
        entry = {
            "tx_id": tx_id,
            "user_id": request.user_id,
            "amount": request.amount,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "PENDING",
            "origin_node": config.NODE_ID
        }

        # Strictly: only leader should propose; for simplicity we accept and forward.
        leader = self.raft.get_leader()
        if leader and leader != config.NODE_ID:
            # forward to leader using gRPC
            leader_addr = config.PEER_NODES.get(leader)
            if leader_addr:
                try:
                    channel = grpc.insecure_channel(leader_addr)
                    stub = payment_pb2_grpc.PaymentServiceStub(channel)
                    # Build new request with same fields but keep original tx_id via metadata? We'll re-create
                    leader_req = payment_pb2.PaymentRequest(user_id=request.user_id, amount=request.amount)
                    resp = stub.ProcessPayment(leader_req, timeout=config.RPC_TIMEOUT)
                    return resp
                except Exception as e:
                    utils.log_event(f"[FORWARD] Failed to forward to leader {leader}: {e}")
                    # fallthrough and attempt local handling

        # This node will propose the entry
        # apply lamport/clock or raft log append via raft
        index = self.raft.propose(entry)
        # Wait until committed (timeout small)
        committed = self.raft.wait_for_commit(index, timeout=5)
        if committed:
            entry["status"] = "COMMITTED"
            # append to local ledger
            self._append_local_ledger(entry)
            # replicate to followers directly (best-effort)
            try:
                if self.replicator:
                    self.replicator.push_transaction(entry)
            except Exception as e:
                utils.log_event(f"[REPLICATOR] replicate error: {e}")

            return payment_pb2.PaymentResponse(status="SUCCESS", message="Payment committed", timestamp=entry["timestamp"])
        else:
            # fallback: write as PENDING locally
            entry["status"] = "PENDING"
            self._append_local_ledger(entry)
            return payment_pb2.PaymentResponse(status="PENDING", message="Payment not committed yet", timestamp=entry["timestamp"])

    def GetHistory(self, request, context):
        """
        Return all transactions for a user.
        """
        utils.log_event(f"[HISTORY] Getting history for user_id={request.user_id}")
        with self.ledger_lock:
            try:
                with open(LEDGER_FILE, "r") as f:
                    ledger = json.load(f)
                    utils.log_event(f"[HISTORY] Loaded {len(ledger)} entries from ledger")
            except Exception as e:
                utils.log_event(f"[HISTORY] Error loading ledger: {e}")
                ledger = []

        transactions = []
        for e in ledger:
            if request.user_id == "" or e.get("user_id") == request.user_id:
                utils.log_event(f"[HISTORY] Found matching transaction: user={e.get('user_id', '')}, status={e.get('status', '')}")
                transactions.append(payment_pb2.Transaction(
                    user_id=e.get("user_id", ""),
                    amount=e.get("amount", 0.0),
                    status=e.get("status", ""),
                    timestamp=e.get("timestamp", "")
                ))
        return payment_pb2.HistoryResponse(transactions=transactions)
