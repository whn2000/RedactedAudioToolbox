from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseTorrentClient(ABC):
    """
    统一的做种客户端抽象基类。
    所有具体的客户端实现（如 qBittorrent, Transmission 等）必须继承此类并实现其抽象方法。
    """
    @abstractmethod
    def add_torrent(self, torrent_path: str, save_path: str, category: str = None) -> bool:
        """
        向客户端添加一个种子文件进行做种。

        :param torrent_path: 本地 .torrent 文件路径
        :param save_path: 客户端挂载的下载保存路径
        :param category: 种子分类（主要用于 qBittorrent）
        :return: 是否成功添加
        """
        pass

    @abstractmethod
    def get_torrents(self, category: str = None) -> List[Dict[str, Any]]:
        """
        获取客户端当前的所有种子，以列表形式返回。
        为了兼容性，返回的字典格式必须包含如下键：
        - "name": 种子名称
        - "hash": 种子的 infohash
        - "save_path": 种子的保存路径
        - "tracker": 种子的 tracker announce URL 字符串（如果是多个用逗号隔开）
        - "progress": 种子进度 (0.0 - 1.0)
        - "state": 种子状态字符串
        - "size": 种子总大小字节数

        :param category: 筛选的分类名称（若支持）
        :return: 包含种子信息的字典列表
        """
        pass

    @abstractmethod
    def set_category(self, hashes: str, category: str) -> bool:
        """
        设置一个或多个种子的分类。

        :param hashes: 单个 infohash 字符串或多个用逗号/列表表示的 hash
        :param category: 目标分类名称
        :return: 是否成功设置
        """
        pass
