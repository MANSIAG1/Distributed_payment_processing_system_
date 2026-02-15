# server/replication/replicator.py
import grpc
import threading
import time
from common import utils
from config import config
from proto import replication_pb2
from proto import replication_pb2_grpc
from proto import payment_pb2

class Replicator:
    """
    Replicator sends transaction entries to peers using ReplicationService.
    """

    def __init__(self, peers=None):
        self.peers = peers if peers is not None else dict(config.PEER_NODES)
        self.lock = threading.Lock()

    def push_transaction(self, entry):
        """
        Push a single transaction (dictionary) to all peers (best-effort).
        """
        tx = payment_pb2.Transaction(
            user_id=entry["user_id"],
            amount=entry["amount"],
            status=entry["status"],
            timestamp=entry["timestamp"]
        )
        req = replication_pb2.ReplicationRequest(transactions=[tx], source_node=config.NODE_ID)
        errors = []
        for pid, addr in self.peers.items():
            # don't send to self
            if pid == config.NODE_ID:
                continue
            try:
                with grpc.insecure_channel(addr) as channel:
                    stub = replication_pb2_grpc.ReplicationServiceStub(channel)
                    resp = stub.ReplicateLedger(req, timeout=config.RPC_TIMEOUT)
                    utils.log_event(f"[REPLICATOR] Sent tx {entry['tx_id']} to {pid}: {resp.status}")
            except Exception as e:
                errors.append((pid, str(e)))
                utils.log_event(f"[REPLICATOR] Error sending to {pid}: {e}")

        if errors:
            utils.log_event(f"[REPLICATOR] push_transaction had errors: {errors}")
