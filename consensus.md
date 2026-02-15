raft.py

Purpose:
Implements the Raft consensus algorithm, which ensures all nodes agree on the same ledger state even if some nodes fail.

Things to include:
Raft roles: Leader, Follower, Candidate.

Log replication:
Leader sends new transactions to followers.
Followers acknowledge the transaction.
Commit entry once a majority confirms.

Persistence: store log entries so that nodes can recover after crash.

Integration: Works with node_server.py and state_machine.py to ensure transactions are applied consistently.


leader_election.py

Purpose:
Handles automatic selection of a leader node for coordinating transactions.

Things to include:

Election triggers:
Leader fails or heartbeat missing.
Election timeout occurs.

Election process:
Nodes vote for a candidate.
Candidate becomes leader if it gets majority votes.

Term management:
Track current term and reject stale votes or requests.

Integration:

raft.py uses this module to determine which node should act as leader for log replication.


state_machine.py

Purpose:
Apply committed transactions from Raft log to the actual ledger (the state machine).

Things to include:

State Machine class:
Methods to apply_transaction(transaction) and update ledger.
Methods to get_state() or query ledger.

Integration with Raft:
Only committed entries from Raft leader are applied.
Ensures that all nodes have identical ledger state.

