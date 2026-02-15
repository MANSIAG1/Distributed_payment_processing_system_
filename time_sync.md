Lamport Clock (lamport_clock.py)

Ensures events are ordered across distributed nodes even if clocks are not synchronized.

Doesn’t care about real-world time, only about the sequence of events.

Key concepts:

Each node has a counter called a logical clock.

Local events: increment your counter (tick()).

Receiving a message: set your counter to max(local, received) + 1.

Events can now be compared across nodes using this counter.

Vector Clock (vector_clock.py)

Captures causal relationships between events in multiple nodes.

More precise than Lamport clocks.

Key concepts:

Each node maintains a vector of counters for all nodes in the system.

Local event: increment your node’s counter.

Receiving a message: merge received vector with local vector (max(local, received)) and increment your counter.

Can detect concurrent events (events that don’t depend on each other).

NTP Sync (ntp_sync.py)

Purpose:

Synchronizes the real-world clocks of nodes.

Ensures logs have accurate timestamps for human reading, debugging, or auditing.

Key concepts:

Uses the Network Time Protocol (NTP) to query an accurate time server.

Can compute clock offset between the local node and real time.

Provides real timestamps alongside logical clocks for better logging.

Why do we need three time synchronization strategie for this project?

laport clocks gives a simple way to order events logically, vector clocks have the capability to detect conflicts and concurrent transactions while ntp synchronization is needed for auditing, debugging and reporting. Hence it is more convenient and efficient to use these three time synchronization strategis.