replicator.py

Purpose:
Responsible for sending and receiving replicated payment transactions between nodes.
Ensures all nodes have the same data in their ledgers.

Things to include:

Replication class or functions:
send_transaction(transaction, target_node) → send a payment to another node.
receive_transaction(transaction) → receive a transaction from another node.

Integration with consensus:
Only commit replicated transactions after Raft consensus or quorum acknowledgment.

Retries & error handling:
Retry sending if a node is down temporarily.

Logging replication events: record when a transaction is sent or applied.

sync_manager.py

Purpose:
Manages synchronization of data between nodes, especially during recovery or startup.

Things to include:

Node synchronization logic:
When a node joins or rejoins, fetch missing transactions from other nodes.
Compare ledger states and bring the node up-to-date.

Conflict resolution:
Use timestamps (Lamport, vector clocks) or consensus to decide which transactions to keep.

Periodic sync (optional):
Nodes periodically check each other to ensure no transactions are missed.

Integration:
Works with replicator.py to fetch and apply transactions.
Works with deduplication.py to avoid duplicates.

deduplication.py

Purpose:
Prevent duplicate transactions caused by retries, failovers, or multiple replication paths.

Things to include:

Deduplication logic:
Maintain a record of transaction IDs that have been applied.
Before adding a transaction to the ledger, check if it already exists.

Integration:
Called by replicator.py and sync_manager.py before committing a transaction.
