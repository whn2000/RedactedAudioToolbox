import os
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, IO, Optional

logger = logging.getLogger("WriteGuard")

class WriteGuardMode(Enum):
    STRICT = "strict"       # Block legacy writes completely
    MIGRATION = "migration" # Sync to new system and old system (or redirect)
    AUDIT = "audit"         # Allow write but log a warning

class WriteGuard:
    """
    拦截危险写入行为的控制层 (Write Guard Layer)。
    用于在迁移期间收敛对旧配置文件的无序写入。
    """
    def __init__(self, mode: WriteGuardMode = WriteGuardMode.AUDIT):
        self.mode = mode
        # 遗留文件列表
        self.legacy_files = {"config.json", "cookies.txt", "pipeline_cache.json"}
        
        # 为了能够在 migration 模式下重定向写入，我们可能需要 StorageGateway
        # 由于网关是在启动后组装的，我们可以延迟注入或通过全局访问获取
        self.gateway = None

    def set_gateway(self, gateway):
        """注入统一存储网关"""
        self.gateway = gateway

    def _is_legacy_target(self, file_path: str | Path) -> bool:
        path_str = str(file_path)
        return any(path_str.endswith(lf) for lf in self.legacy_files)

    def _handle_violation(self, file_path: str, action_desc: str):
        if self.mode == WriteGuardMode.STRICT:
            logger.error(f"[STRICT] Blocked legacy write to {file_path}: {action_desc}")
            raise PermissionError(f"Direct write to legacy file '{file_path}' is strictly forbidden. Use StorageGateway.")
        elif self.mode == WriteGuardMode.AUDIT:
            logger.warning(f"[AUDIT] Legacy write detected to {file_path}: {action_desc}")
        elif self.mode == WriteGuardMode.MIGRATION:
            logger.warning(f"[MIGRATION] Intercepted write to {file_path}. Data should be synced to new StorageGateway.")
            # 注意：实际重定向写入需要在 safe_write_json 这种高层接口中完成，
            # 这里的 handle 只是记录。

    def safe_open(self, file_path: str | Path, mode: str = "r", encoding: Optional[str] = None, **kwargs) -> IO:
        """
        安全的 open 包装器。
        如果你需要修改遗留文件，请不要使用内置的 open，而是使用此函数。
        """
        if "w" in mode or "a" in mode or "+" in mode:
            if self._is_legacy_target(file_path):
                self._handle_violation(str(file_path), f"safe_open(mode='{mode}')")
                
                if self.mode == WriteGuardMode.MIGRATION:
                    # 在迁移模式下，如果无法完全接管 open 的上下文管理器行为
                    # 最安全的做法是抛出异常，强制调用方改用 safe_write_json 或 gateway
                    logger.error("Cannot seamlessly migrate raw file handles in MIGRATION mode.")
                    raise NotImplementedError("Use safe_write_json or StorageGateway instead of raw safe_open for writes.")
        
        return open(file_path, mode=mode, encoding=encoding, **kwargs)

    def safe_write_json(self, file_path: str | Path, data: dict, **kwargs):
        """
        安全的 json 写入包装器。
        如果处于迁移模式，将尝试双写或重定向到新的网关。
        """
        path_str = str(file_path)
        is_legacy = self._is_legacy_target(path_str)

        if is_legacy:
            self._handle_violation(path_str, "safe_write_json")
            
            if self.mode == WriteGuardMode.MIGRATION and self.gateway:
                # 尝试自动将旧的 config.json 写入重定向到网关
                if path_str.endswith("config.json"):
                    logger.info("Redirecting config.json write to StorageGateway...")
                    # 假设 config.json 根节点都是配置项
                    for k, v in data.items():
                        self.gateway.set_config(k, v)
                    return # 拦截旧文件的真实写入（或者可以选择双写）
                    
                elif path_str.endswith("pipeline_cache.json"):
                    logger.info("Redirecting pipeline_cache.json to CacheManager via StorageGateway...")
                    # 这里可能需要根据结构适配
                    for k, v in data.items():
                        self.gateway.write_cache("pipeline", k, v)
                    return
        
        # 默认回退行为：如果是 audit 或者普通文件，继续正常的写入
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, **kwargs)


# 提供一个全局默认实例，方便不方便依赖注入的老代码调用
default_guard = WriteGuard(mode=WriteGuardMode.AUDIT)

def safe_open(*args, **kwargs):
    return default_guard.safe_open(*args, **kwargs)

def safe_write_json(*args, **kwargs):
    return default_guard.safe_write_json(*args, **kwargs)
