# server/consensus/leader_election.py
# This file is a simple helper wrapper to start Raft election; most logic is in raft.py.
from server.consensus.raft import RaftNode

def create_raft_node():
    raft = RaftNode()
    return raft
