from .base import BaseTorrentClient
from .qbittorrent import QbittorrentClient
from .transmission import TransmissionClient

def create_client(client_type: str, host: str, port: str, username: str, password: str) -> BaseTorrentClient:
    """
    做种客户端简单工厂函数。
    
    :param client_type: 'qBittorrent' 或 'Transmission' (不区分大小写)
    :param host: 客户端连接地址
    :param port: 客户端连接端口
    :param username: 用户名
    :param password: 密码
    :return: 对应的 BaseTorrentClient 实现实例
    """
    normalized_type = client_type.lower().strip()
    if normalized_type == "transmission":
        return TransmissionClient(host, port, username, password)
    elif normalized_type == "qbittorrent":
        return QbittorrentClient(host, port, username, password)
    else:
        raise ValueError(f"不支持的做种客户端类型: {client_type}")
