import os
from typing import List, Dict, Any
from transmission_rpc import Client
from .base import BaseTorrentClient

class TransmissionClient(BaseTorrentClient):
    def __init__(self, host: str = '127.0.0.1', port: Any = 9091, username: str = None, password: str = None):
        self.host = host
        self.port = int(port) if port else 9091
        self.username = username
        self.password = password
        self.client = None
        self._connect()

    def _connect(self):
        try:
            self.client = Client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password
            )
        except Exception as e:
            self.client = None
            # 我们不在这里抛出崩溃，而是记录日志并在操作时重试
            print(f"[Transmission] 无法连接到 Transmission RPC ({self.host}:{self.port}): {e}")

    def add_torrent(self, torrent_path: str, save_path: str, category: str = None) -> bool:
        if not self.client:
            try:
                self._connect()
            except Exception:
                return False

        if not self.client:
            return False

        try:
            if not os.path.exists(torrent_path):
                print(f"[Transmission] 种子文件不存在: {torrent_path}")
                return False
                
            with open(torrent_path, 'rb') as f:
                torrent_data = f.read()
                
            # 添加种子
            torrent = self.client.add_torrent(torrent_data, download_dir=save_path)
            
            # 如果提供了 category 且客户端支持 labels，尝试给种子打上标签
            if category and torrent:
                try:
                    # Transmission 3.0+ supports labels
                    self.client.change_torrent(torrent.id, labels=[category])
                except Exception:
                    pass
            return True
        except Exception as e:
            print(f"[Transmission] 添加种子出错: {e}")
            return False

    def get_torrents(self, category: str = None) -> List[Dict[str, Any]]:
        if not self.client:
            try:
                self._connect()
            except Exception:
                return []

        if not self.client:
            return []

        try:
            torrents = self.client.get_torrents()
            results = []
            for t in torrents:
                # 过滤分类：如果指定了 category，并且当前种子的 labels 中不包含该标签，则跳过
                if category:
                    labels = getattr(t, 'labels', [])
                    if category not in labels:
                        continue
                        
                results.append({
                    "name": t.name,
                    "hash": t.hashString,
                    "save_path": t.download_dir,
                    "tracker": ",".join([tr.announce for tr in t.trackers]) if t.trackers else "",
                    "progress": getattr(t, "percent_done", 0.0),
                    "state": getattr(t, "status", ""),
                    "size": getattr(t, "total_size", 0)
                })
            return results
        except Exception as e:
            print(f"[Transmission] 获取种子列表出错: {e}")
            return []

    def set_category(self, hashes: str, category: str) -> bool:
        if not self.client:
            try:
                self._connect()
            except Exception:
                return False

        if not self.client:
            return False

        try:
            # Transmission labels are set via change_torrent using hashString or IDs
            self.client.change_torrent(hashes, labels=[category])
            return True
        except Exception as e:
            print(f"[Transmission] 修改标签出错: {e}")
            return False
