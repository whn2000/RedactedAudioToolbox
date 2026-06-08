import requests
from pathlib import Path
from typing import List, Dict, Any
from .base import BaseTorrentClient

class QbittorrentClient(BaseTorrentClient):
    def __init__(self, host: str, port: Any, username: str, password: str):
        self.host = host.rstrip('/')
        if not self.host.startswith('http'):
            self.host = 'http://' + self.host
        self.port = port
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = f"{self.host}:{self.port}"
        self.is_logged_in = False

    def login(self) -> bool:
        url = f"{self.base_url}/api/v2/auth/login"
        try:
            resp = self.session.post(url, data={
                'username': self.username,
                'password': self.password
            }, timeout=10)
            if resp.text.strip() == "Ok.":
                self.is_logged_in = True
                return True
            return False
        except Exception as e:
            print(f"qBittorrent 登录失败: {e}")
            return False

    def add_torrent(self, torrent_path: str, save_path: str, category: str = "red_auto") -> bool:
        if not self.is_logged_in and not self.login():
            return False
            
        url = f"{self.base_url}/api/v2/torrents/add"
        path = Path(torrent_path)
        if not path.exists():
            return False
            
        files = {'torrents': (path.name, path.open('rb'), 'application/x-bittorrent')}
        data = {
            'category': category,
            'tags': 'red_toolbox',
            'paused': 'false'
        }
        if save_path:
            data['savepath'] = save_path
            
        try:
            resp = self.session.post(url, files=files, data=data)
            if resp.status_code == 403: # Session expired
                if self.login():
                    path = Path(torrent_path)
                    files = {'torrents': (path.name, path.open('rb'), 'application/x-bittorrent')}
                    resp = self.session.post(url, files=files, data=data)
            return resp.status_code == 200
        except Exception as e:
            print(f"添加种子到 qBittorrent 失败: {e}")
            return False

    def get_torrents(self, category: str = None) -> List[Dict[str, Any]]:
        if not self.is_logged_in and not self.login():
            return []
            
        url = f"{self.base_url}/api/v2/torrents/info"
        params = {}
        if category:
            params['category'] = category
            
        try:
            resp = self.session.get(url, params=params)
            if resp.status_code == 403: # Session expired
                if self.login():
                    resp = self.session.get(url, params=params)
            
            if resp.status_code == 200:
                results = []
                for t in resp.json():
                    # 确保返回格式标准化，统一包含 name, hash, save_path, tracker 键
                    results.append({
                        "name": t.get("name", ""),
                        "hash": t.get("hash", ""),
                        "save_path": t.get("save_path", t.get("savepath", "")),
                        "tracker": t.get("tracker", "")
                    })
                return results
            return []
        except Exception as e:
            print(f"获取 qBittorrent 种子列表失败: {e}")
            return []

    def set_category(self, hashes: str, category: str) -> bool:
        if not self.is_logged_in and not self.login():
            return False
            
        # 尝试先创建分类
        create_url = f"{self.base_url}/api/v2/torrentCategories/create"
        try:
            self.session.post(create_url, data={'category': category})
        except:
            pass
            
        url = f"{self.base_url}/api/v2/torrents/setCategory"
        try:
            resp = self.session.post(url, data={'hashes': hashes, 'category': category})
            if resp.status_code == 403:  # Session expired
                if self.login():
                    resp = self.session.post(url, data={'hashes': hashes, 'category': category})
            return resp.status_code == 200
        except Exception:
            return False
