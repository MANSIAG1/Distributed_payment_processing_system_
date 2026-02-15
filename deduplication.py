# server/replication/deduplication.py
class Deduplicator:
    """
    Very simple in-memory deduplication by tx_id (not persistent).
    For production, dedup info must be persisted.
    """
    def __init__(self):
        self.seen = set()

    def is_duplicate(self, tx_id):
        if tx_id in self.seen:
            return True
        self.seen.add(tx_id)
        return False
