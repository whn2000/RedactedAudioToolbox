import json
import time
from pathlib import Path
from qbittorrent_client import QbittorrentClient

def push_existing_torrents():
    config_file = Path("config.json")
    if not config_file.exists():
        print("未找到 config.json，请先在主程序中保存配置。")
        return

    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    save_path = Path(config.get("save_path", "."))
    qb_host = config.get("qb_host", "http://127.0.0.1")
    qb_port = config.get("qb_port", "8080")
    qb_user = config.get("qb_user", "admin")
    qb_pass = config.get("qb_pass", "adminadmin")

    print(f"尝试连接 qBittorrent: {qb_host}:{qb_port}")
    qb = QbittorrentClient(qb_host, qb_port, qb_user, qb_pass)
    
    if not qb.login():
        print("❌ qBittorrent 登录失败！请检查账号密码和端口。")
        return

    print(f"正在扫描目录: {save_path}")
    count = 0
    for torrent_file in save_path.glob("*.torrent"):
        json_file = torrent_file.with_suffix(".json")
        if json_file.exists():
            print(f"发现已下载的种子: {torrent_file.name}")
            # 推送到 qBittorrent，保存路径与 torrent 所在路径一致（或者指定为其父目录）
            # 在 elitetmhelper2.py 中，save_path 传的是 save_path.parent
            # 这里对应的是 save_path
            success = qb.add_torrent(str(torrent_file), save_path=str(save_path), category="red_auto")
            if success:
                print("  ✅ 成功推送到 qBittorrent 并打上 'red_auto' 标签！")
                count += 1
            else:
                print("  ❌ 推送失败。")
        else:
            print(f"跳过: {torrent_file.name} (缺少对应的 .json 元数据文件)")

    if count > 0:
        print(f"\n🎉 成功推送 {count} 个种子！请在 qBittorrent 中查看。等待其下载完成后，主程序的流水线(如果您保持开启)将会接管后续操作。")
    else:
        print("\n没有找到需要推送的种子。")

if __name__ == "__main__":
    push_existing_torrents()
    time.sleep(5)
