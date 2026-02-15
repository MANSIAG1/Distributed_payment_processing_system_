# server/consensus/state_machine.py
"""
State machine applies committed log entries from Raft to the node's ledger.
For simplicity the PaymentService directly writes committed entries to ledger.
This module can be extended to decouple log -> apply operations.
"""
def apply_entry(entry, payment_service):
    """
    entry: dict containing transaction fields
    payment_service: instance of PaymentService to append to ledger
    """
    # The PaymentService provides _append_local_ledger
    try:
        payment_service._append_local_ledger(entry)
        return True
    except Exception:
        return False
