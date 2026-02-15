class LamportClock:
    """
    Lamport Logical Clock for ordering events in a distributed system.
    """

    def __init__(self, node_id):
        self.node_id = node_id
        self.time = 0

    def tick(self):
        """Increment on internal event."""
        self.time += 1
        return self.time

    def update(self, received_time):
        """Update clock based on a message received."""
        self.time = max(self.time, received_time) + 1
        return self.time

    def get_time(self):
        return self.time

    def __str__(self):
        return f"LamportClock(node={self.node_id}, time={self.time})"
