# server/node/heartbeat.py
import socket
import threading
import time
from config import config
from common import utils

class HeartbeatMonitor(threading.Thread):
    """
    Simple heartbeat monitor that checks whether peer TCP ports are open.
    Not an RPC heartbeat — uses socket connect (lightweight).
    """

    def __init__(self, interval=None):
        super().__init__(daemon=True)
        self.interval = interval if interval is not None else config.HEARTBEAT_INTERVAL
        self.peers = dict(config.PEER_NODES)  # copy
        self.running = True
        self.status = {pid: False for pid in self.peers.keys()}
        self.lock = threading.Lock()
        self._last_heartbeat = time.time()

    def check_peer(self, hostport):
        host, port = hostport.split(":")
        try:
            port = int(port)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect((host, port))
            s.close()
            return True
        except Exception:
            return False

    def run_once(self):
        for pid, hostport in self.peers.items():
            alive = self.check_peer(hostport)
            with self.lock:
                prev = self.status.get(pid, False)
                self.status[pid] = alive
            if alive and not prev:
                utils.log_event(f"[HEARTBEAT] peer {pid} became ALIVE")
            if not alive and prev:
                utils.log_event(f"[HEARTBEAT] peer {pid} became DOWN")

    def run(self):
        utils.log_event("[HEARTBEAT] Starting heartbeat monitor")
        while self.running:
            try:
                self.run_once()
            except Exception as e:
                utils.log_event(f"[HEARTBEAT] Error: {e}")
            time.sleep(self.interval)

    def stop(self):
        self.running = False

    def get_live_peers(self):
        with self.lock:
            return [pid for pid, alive in self.status.items() if alive]
