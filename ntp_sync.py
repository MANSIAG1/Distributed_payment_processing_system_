import ntplib
from time import ctime

class NTPSync:
    """
    Simple NTP-based synchronization for distributed nodes.
    """

    def __init__(self, server="pool.ntp.org"):
        self.server = server
        self.client = ntplib.NTPClient()

    def get_time(self):
        """Fetch synchronized time from NTP server."""
        try:
            response = self.client.request(self.server, version=3)
            return ctime(response.tx_time)
        except Exception as e:
            print(f"[NTP ERROR] {e}")
            return None

# Example usage
if __name__ == "__main__":
    ntp = NTPSync()
    print("Synchronized Time:", ntp.get_time())
