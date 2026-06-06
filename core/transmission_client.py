import os
from typing import List, Any
from transmission_rpc import Client

class TransmissionClient:
    def __init__(self, host: str = '127.0.0.1', port: Any = 9091, username: str = None, password: str = None):
        self.host = host
        self.port = int(port) if port else 9091
        self.username = username
        self.password = password
        self.client = None
        self._connect()

    def _connect(self):
        try:
            # Connect to Transmission RPC
            self.client = Client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password
            )
        except Exception as e:
            self.client = None
            raise ConnectionError(f"Failed to connect to Transmission RPC at {self.host}:{self.port}: {e}")

    def add_torrent(self, torrent_path: str, save_path: str) -> bool:
        """
        Add a .torrent file to Transmission for seeding.
        """
        if not self.client:
            try:
                self._connect()
            except Exception:
                return False

        if not self.client:
            return False

        try:
            if not os.path.exists(torrent_path):
                print(f"[Transmission] Torrent file not found: {torrent_path}")
                return False
                
            with open(torrent_path, 'rb') as f:
                torrent_data = f.read()
                
            # Add torrent by passing the raw torrent file bytes
            self.client.add_torrent(torrent_data, download_dir=save_path)
            return True
        except Exception as e:
            print(f"[Transmission] Error adding torrent: {e}")
            return False

    def get_torrents(self) -> List[Any]:
        """
        Get all active torrents (for cross-seed matching).
        """
        if not self.client:
            try:
                self._connect()
            except Exception:
                return []

        if not self.client:
            return []

        try:
            torrents = self.client.get_torrents()
            # Map Transmission torrent objects to dictionaries matching the structure of qB torrents for compatibility
            results = []
            for t in torrents:
                results.append({
                    "name": t.name,
                    "hash": t.hashString,
                    "save_path": t.download_dir,
                    # We can join trackers into a string
                    "tracker": ",".join([tr.announce for tr in t.trackers]) if t.trackers else ""
                })
            return results
        except Exception as e:
            print(f"[Transmission] Error fetching torrents: {e}")
            return []
