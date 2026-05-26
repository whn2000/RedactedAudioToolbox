from typing import Any, Optional
import logging

logger = logging.getLogger("StorageGateway")

class StorageGateway:
    """
    统一存储网关 (Single Source of Truth).
    所有对配置、凭据、缓存和数据的访问，都必须通过此网关。
    不允许业务代码直接实例化或访问底层的 yaml/json/sqlite 文件。
    """
    def __init__(self, config_manager, secrets_manager, cache_manager, db_manager):
        self.config = config_manager
        self.secrets = secrets_manager
        self.cache = cache_manager
        self.db = db_manager

    # ==========================
    # 配置 (Config) 接口
    # ==========================
    def get_config(self, key_path: str, default: Any = None) -> Any:
        return self.config.get(key_path, default)

    def set_config(self, key_path: str, value: Any):
        logger.debug(f"Gateway routed config set: {key_path}")
        self.config.set(key_path, value)

    # ==========================
    # 凭据 (Secrets) 接口
    # ==========================
    def get_secret(self, key: str, default: Any = None) -> Any:
        return self.secrets.get_secret(key) or default

    def set_secret(self, key: str, value: str):
        logger.debug(f"Gateway routed secret set: {key}")
        self.secrets.set_secret(key, value)

    # ==========================
    # 缓存 (Cache) 接口
    # ==========================
    def read_cache(self, prefix: str, key: str, default: Any = None) -> Any:
        # CacheManager 目前可能没有直接提供 read，这里做个简单封装
        # 假设我们通过 DB 直接读取或者通过 cache_manager 提供的方法
        row = self.db.fetch_one(
            "SELECT result_data FROM search_cache WHERE query_hash = ?", 
            (f"{prefix}:{key}",)
        )
        return row["result_data"] if row else default

    def write_cache(self, prefix: str, key: str, value: str, expire_seconds: Optional[int] = None):
        logger.debug(f"Gateway routed cache write: {prefix}:{key}")
        # 如果底层 cache_manager 支持更细致的方法，可以直接调用。这里以写 DB 为例：
        # 实际情况中，CacheManager 可能有 set_cache 方法
        if hasattr(self.cache, 'set'):
            self.cache.set(f"{prefix}:{key}", value, expire_seconds=expire_seconds)
        else:
            # Fallback to direct DB logic if cache manager doesn't have a high level set
            # timestamp is required for expires_at, give a default
            expire_at = '2099-12-31 23:59:59' 
            self.db.execute(
                "INSERT OR REPLACE INTO search_cache (query_hash, result_data, expires_at) VALUES (?, ?, ?)",
                (f"{prefix}:{key}", value, expire_at)
            )

    # ==========================
    # 业务数据 (Database) 接口
    # ==========================
    def execute_db(self, query: str, params: tuple = ()):
        return self.db.execute(query, params)
        
    def fetch_one(self, query: str, params: tuple = ()):
        return self.db.fetch_one(query, params)
        
    def fetch_all(self, query: str, params: tuple = ()):
        return self.db.fetch_all(query, params)

