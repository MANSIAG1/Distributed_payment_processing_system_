# server/replication/sync_manager.py
import threading
import json
import os
import grpc
from common import utils
from config import config

from proto import replication_pb2
from proto import replication_pb2_grpc
from proto import payment_pb2

LEDGER_FILE = config.LEDGER_FILE

class ReplicationService(replication_pb2_grpc.ReplicationServiceServicer):
    """
    Receives replication requests from peers and applies transactions to local ledger.
    Can also actively push new transactions to other peers.
    """

    def __init__(self, deduplicator=None):
        self.ledger_lock = threading.Lock()
        if not os.path.exists(LEDGER_FILE):
            with open(LEDGER_FILE, "w") as f:
                json.dump([], f)
        self.dedup = deduplicator

    def _append_if_not_exists(self, tx):
        """
        Append transaction to local ledger if not already present.
        deduplication is based on (timestamp, user_id, amount).
        """
        with self.ledger_lock:
            with open(LEDGER_FILE, "r+") as f:
                try:
                    ledger = json.load(f)
                except Exception:
                    ledger = []
                # dedup by timestamp, user_id, amount
                exists = any(
                    entry.get("timestamp") == tx.timestamp and
                    entry.get("user_id") == tx.user_id and
                    entry.get("amount") == tx.amount
                    for entry in ledger
                )
                if not exists:
                    new_entry = {
                        "tx_id": f"rep-{tx.timestamp}-{tx.user_id}",
                        "user_id": tx.user_id,
                        "amount": tx.amount,
                        "status": tx.status,
                        "timestamp": tx.timestamp,
                        "source": "replication"
                    }
                    ledger.append(new_entry)
                    f.seek(0)
                    json.dump(ledger, f, indent=2)
                    f.truncate()
                    utils.log_event(f"[REPLICATION] Appended replicated tx for {tx.user_id} at {tx.timestamp}")
                    return True
                else:
                    utils.log_event(f"[REPLICATION] Duplicate detected for {tx.user_id} @ {tx.timestamp}")
                    return False

    def ReplicateLedger(self, request, context):
        """
        gRPC endpoint: called by peers to replicate a batch of transactions.
        """
        try:
            for tx in request.transactions:
                self._append_if_not_exists(tx)
            return replication_pb2.ReplicationResponse(status="OK", message="Applied")
        except Exception as e:
            utils.log_event(f"[REPLICATION] Error: {e}")
            return replication_pb2.ReplicationResponse(status="FAILED", message=str(e))

    def push_transaction(self, tx):
        """
        Called by PaymentService to replicate a new transaction.
        tx: dict with keys ["tx_id", "user_id", "amount", "status", "timestamp"]
        """
        class DummyTx:
            # helper to mimic proto object
            def __init__(self, tx):
                self.user_id = tx["user_id"]
                self.amount = tx["amount"]
                self.status = tx.get("status", "")
                self.timestamp = tx["timestamp"]

        dummy_tx = DummyTx(tx)
        # Append locally
        self._append_if_not_exists(dummy_tx)

        # Broadcast to all peers
        for peer_id, addr in config.PEER_NODES.items():
            try:
                with grpc.insecure_channel(addr) as channel:
                    stub = replication_pb2_grpc.ReplicationServiceStub(channel)
                    tx_proto = payment_pb2.Transaction(
                        user_id=dummy_tx.user_id,
                        amount=dummy_tx.amount,
                        status=dummy_tx.status,
                        timestamp=dummy_tx.timestamp
                    )
                    req = replication_pb2.ReplicationRequest(transactions=[tx_proto])
                    stub.ReplicateLedger(req, timeout=config.RPC_TIMEOUT)
                    utils.log_event(f"[REPLICATION] Broadcasted tx {tx['tx_id']} to {peer_id}")
            except Exception as e:
                utils.log_event(f"[REPLICATION] Failed to replicate tx {tx['tx_id']} to {peer_id}: {e}")
