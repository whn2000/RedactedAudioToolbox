import pytest
from unittest.mock import MagicMock, patch
from core.clients.qbittorrent import QbittorrentClient
from core.clients.transmission import TransmissionClient

@patch('core.clients.qbittorrent.requests.Session')
def test_qbittorrent_get_torrents(mock_session_class):
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    
    # Mock login
    mock_login_resp = MagicMock()
    mock_login_resp.text = "Ok."
    mock_login_resp.status_code = 200
    mock_session.post.return_value = mock_login_resp
    
    # Mock get_torrents response
    mock_torrents_resp = MagicMock()
    mock_torrents_resp.status_code = 200
    mock_torrents_resp.json.return_value = [
        {
            "name": "Test Album",
            "hash": "abcdef123456",
            "save_path": "/downloads",
            "tracker": "http://tracker/announce",
            "progress": 1.0,
            "state": "seeding",
            "size": 500000000
        }
    ]
    mock_session.get.return_value = mock_torrents_resp
    
    client = QbittorrentClient(host="http://localhost", port=8080, username="admin", password="password")
    torrents = client.get_torrents(category="red_auto")
    
    assert len(torrents) == 1
    t = torrents[0]
    assert t["name"] == "Test Album"
    assert t["hash"] == "abcdef123456"
    assert t["save_path"] == "/downloads"
    assert t["tracker"] == "http://tracker/announce"
    assert t["progress"] == 1.0
    assert t["state"] == "seeding"
    assert t["size"] == 500000000


@patch('core.clients.transmission.Client')
def test_transmission_get_torrents(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Mock return list of torrents from transmission-rpc
    mock_torrent = MagicMock()
    mock_torrent.name = "Test Album"
    mock_torrent.hashString = "abcdef123456"
    mock_torrent.download_dir = "/downloads"
    
    mock_tracker = MagicMock()
    mock_tracker.announce = "http://tracker/announce"
    mock_torrent.trackers = [mock_tracker]
    
    mock_torrent.percent_done = 1.0
    mock_torrent.status = "seeding"
    mock_torrent.total_size = 500000000
    mock_torrent.labels = ["red_auto"]
    
    mock_client.get_torrents.return_value = [mock_torrent]
    
    client = TransmissionClient(host="127.0.0.1", port=9091)
    torrents = client.get_torrents(category="red_auto")
    
    assert len(torrents) == 1
    t = torrents[0]
    assert t["name"] == "Test Album"
    assert t["hash"] == "abcdef123456"
    assert t["save_path"] == "/downloads"
    assert t["tracker"] == "http://tracker/announce"
    assert t["progress"] == 1.0
    assert t["state"] == "seeding"
    assert t["size"] == 500000000
