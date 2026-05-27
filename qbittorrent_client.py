import requests
from pathlib import Path
import time

class QbittorrentClient:
    def __init__(self, host, port, username, password):
        self.host = host.rstrip('/')
        if not self.host.startswith('http'):
            self.host = 'http://' + self.host
        self.port = port
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = f"{self.host}:{self.port}"
        self.is_logged_in = False

    def login(self):
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

    def add_torrent(self, torrent_path, save_path=None, category="red_auto"):
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
            return resp.status_code == 200
        except Exception as e:
            print(f"添加种子到 qBittorrent 失败: {e}")
            return False

    def get_torrents(self, category="red_auto"):
        if not self.is_logged_in and not self.login():
            return []
            
        url = f"{self.base_url}/api/v2/torrents/info"
        try:
            resp = self.session.get(url, params={'category': category})
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception:
            return []

    def set_category(self, hashes, category):
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
