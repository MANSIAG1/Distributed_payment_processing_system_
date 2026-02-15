class VectorClock:
    """
    Vector Clock for capturing causality in distributed systems.
    """

    def __init__(self, node_id, nodes):
        self.node_id = node_id
        self.nodes = nodes  # list of all node IDs
        self.clock = {n: 0 for n in nodes}

    def tick(self):
        """Increment local node’s time."""
        self.clock[self.node_id] += 1
        return self.clock.copy()

    def update(self, received_clock):
        """Merge local clock with received clock."""
        for node, ts in received_clock.items():
            self.clock[node] = max(self.clock[node], ts)
        self.clock[self.node_id] += 1
        return self.clock.copy()

    def get_clock(self):
        return self.clock.copy()

    def __str__(self):
        return f"VectorClock(node={self.node_id}, clock={self.clock})"
