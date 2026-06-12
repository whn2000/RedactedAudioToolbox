import os
from pathlib import Path
from typing import Callable, Optional, Any
from core.clients.base import BaseTorrentClient
from core.rclone_helper import rclone_copy_with_progress

class SeedingManager:
    """
    中央做种管理器。
    实现高内聚，封装所有的传输过程（rclone）与挂种交互，向外暴露极简的业务 API。
    """
    def __init__(self, gateway: Optional[Any] = None):
        """
        初始化做种管理器。
        :param gateway: 统一存储网关。如果不传则使用全局 app_context 的 gateway。
        """
        self.gateway = gateway
        if not self.gateway:
            import core.globals
            if core.globals.app_context:
                self.gateway = core.globals.app_context.gateway

    def _get_cfg(self, key_path: str, default: Any = None) -> Any:
        if self.gateway:
            return self.gateway.get_config(key_path, default)
        return default

    def get_client(self, is_remote: bool = False) -> BaseTorrentClient:
        """
        根据配置动态创建客户端实例。
        
        :param is_remote: True 获取做种/远程客户端，False 获取本地下载/监控客户端
        """
        if not is_remote:
            # 本地下载/监控客户端 (用于 Pipeline 监控)
            client_type = "qBittorrent"
            host = self._get_cfg("global.qb_host", "http://127.0.0.1")
            port = self._get_cfg("global.qb_port", "8080")
            user = self._get_cfg("global.qb_user", "admin")
            password = self._get_cfg("global.qb_pass", "adminadmin")
        else:
            # 做种/远程客户端 (用于远程做种和转种)
            client_type = self._get_cfg("seeding.client_type", "qBittorrent")
            # 优先读取独立的 seeding 连接配置，如果没有则回退到全局 qb 配置（兼容旧版本配置升级）
            host = self._get_cfg("seeding.host", self._get_cfg("global.qb_host", "http://127.0.0.1"))
            port = self._get_cfg("seeding.port", self._get_cfg("global.qb_port", "8080"))
            user = self._get_cfg("seeding.user", self._get_cfg("global.qb_user", "admin"))
            password = self._get_cfg("seeding.pass", self._get_cfg("global.qb_pass", "adminadmin"))

        from core.clients.factory import create_client
        return create_client(client_type, host, port, user, password)

    def seed_torrent(
        self,
        local_path: str,
        torrent_path: str,
        use_remote: bool = False,
        remote_save_path: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        完整的做种流程封装。如果启用远程做种，会自动调用 rclone 上传，成功后再添加到对应的挂种客户端。
        
        :param local_path: 本地待上传/做种的音轨数据路径
        :param torrent_path: 本地 .torrent 文件路径
        :param use_remote: 是否使用远程做种 (即使用远程 Seedbox 与 rclone 上传)
        :param remote_save_path: 远程挂载客户端中的下载保存路径（当使用远程做种时必须填写）
        :param on_progress: 传输进度状态回调
        :return: 整个流程是否成功
        """
        def _log(msg: str):
            if on_progress:
                on_progress(msg)
            else:
                print(msg)

        if use_remote:
            rclone_remote = self._get_cfg("seeding.rclone_remote", "").strip()
            rclone_config = self._get_cfg("seeding.rclone_config", "").strip()
            
            if rclone_remote:
                _log(f"📦 [SeedingManager] 开始上传数据到远程做种服务器...")
                success = rclone_copy_with_progress(
                    local_path,
                    rclone_remote,
                    rclone_config if rclone_config else None,
                    progress_callback=_log
                )
                if not success:
                    _log("❌ [SeedingManager] 远程上传同步失败，已中止挂种流程。")
                    return False
                _log("✅ [SeedingManager] 远程上传成功，接下来添加种子。")
            else:
                _log("⚠️ [SeedingManager] 未配置 rclone_remote，将跳过上传步骤直接添加种子。")

            # 连接远程做种客户端并挂载种子
            _log("🔄 [SeedingManager] 正在连接远程做种客户端...")
            try:
                client = self.get_client(is_remote=True)
                save_dir = remote_save_path or self._get_cfg("seeding.manual_remote_save_path", "")
                if not save_dir:
                    _log("❌ [SeedingManager] 未指定远程保存路径，无法添加种子。")
                    return False
                    
                _log(f"📥 [SeedingManager] 正在向客户端推送种子，远程路径: {save_dir}")
                # 统一推送为 red_seeding 分类以示区分
                success = client.add_torrent(torrent_path, save_path=save_dir, category="red_seeding")
                if success:
                    _log("🎉 [SeedingManager] 成功推送到远程客户端挂种！")
                    return True
                else:
                    _log("❌ [SeedingManager] 推送到远程客户端失败，请检查远程客户端配置。")
                    return False
            except Exception as e:
                _log(f"❌ [SeedingManager] 连接或操作远程做种客户端时异常: {e}")
                return False
        else:
            # 本地做种流程
            _log("🔄 [SeedingManager] 正在连接本地做种客户端...")
            try:
                client = self.get_client(is_remote=False)
                from core.paths import app_paths
                save_dir = app_paths.reverse_translate_path(str(Path(local_path).parent))
                _log(f"📥 [SeedingManager] 正在向本地客户端推送种子，路径: {save_dir}")
                success = client.add_torrent(torrent_path, save_path=save_dir, category="red_seeding")
                if success:
                    _log("🎉 [SeedingManager] 成功推送到本地客户端挂种！")
                    return True
                else:
                    _log("❌ [SeedingManager] 推送到本地客户端失败。")
                    return False
            except Exception as e:
                _log(f"❌ [SeedingManager] 连接或操作本地客户端异常: {e}")
                return False
