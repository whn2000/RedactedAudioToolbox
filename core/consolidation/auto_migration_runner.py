import json
import logging
import shutil
from pathlib import Path
from ..paths import app_paths

logger = logging.getLogger("AutoMigrationRunner")

class AutoMigrationRunner:
    """
    自动迁移遗留数据至新架构。
    原则：
    1. 幂等：多次执行不会重复污染新数据。
    2. 安全：绝不直接删除原文件，只将其重命名或加标记。
    3. 备份：在任何变更前，对旧文件进行备份。
    """
    def __init__(self, gateway):
        self.gateway = gateway
        self.root_dir = Path(app_paths.root_dir)
        self.backup_dir = app_paths.backups_dir

    def run_all(self):
        logger.info("Starting legacy data migration...")
        self.migrate_config_json()
        self.migrate_cookies_txt()
        self.migrate_pipeline_cache()
        logger.info("Legacy data migration completed.")

    def _mark_as_migrated(self, file_path: Path):
        if file_path.exists():
            marker_path = file_path.with_name(f"{file_path.name}.migrated")
            # 采用 copy 方式，保留原文件但不破坏业务的潜在只读依赖
            # 如果要求封锁，可以配合 write_guard
            if not marker_path.exists():
                with open(marker_path, "w") as f:
                    f.write("MIGRATED")

    def _create_backup(self, file_path: Path):
        if file_path.exists():
            backup_path = self.backup_dir / f"{file_path.name}.bak"
            if not backup_path.exists():
                shutil.copy2(file_path, backup_path)
                logger.debug(f"Backed up {file_path.name} to {backup_path}")

    def migrate_config_json(self):
        config_path = self.root_dir / "config.json"
        marker = self.root_dir / "config.json.migrated"
        
        if config_path.exists() and not marker.exists():
            logger.info("Migrating config.json to YAML ConfigManager...")
            self._create_backup(config_path)
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 扁平结构递归写入 ConfigManager
                def _write_dict(d, prefix=""):
                    for k, v in d.items():
                        key_path = f"{prefix}.{k}" if prefix else k
                        if isinstance(v, dict):
                            _write_dict(v, key_path)
                        else:
                            # 如果目标中不存在或不同，则覆盖
                            existing = self.gateway.get_config(key_path)
                            if existing is None or existing != v:
                                self.gateway.set_config(key_path, v)
                
                _write_dict(data)
                self._mark_as_migrated(config_path)
                logger.info("Successfully migrated config.json")
            except Exception as e:
                logger.error(f"Failed to migrate config.json: {e}")

    def migrate_cookies_txt(self):
        cookies_path = self.root_dir / "cookies.txt"
        marker = self.root_dir / "cookies.txt.migrated"
        
        if cookies_path.exists() and not marker.exists():
            logger.info("Migrating cookies.txt to SecretsManager...")
            self._create_backup(cookies_path)
            try:
                with open(cookies_path, "r", encoding="utf-8") as f:
                    cookies_content = f.read()
                
                existing = self.gateway.get_secret("netscape_cookies")
                if existing != cookies_content:
                    self.gateway.set_secret("netscape_cookies", cookies_content)
                
                self._mark_as_migrated(cookies_path)
                logger.info("Successfully migrated cookies.txt")
            except Exception as e:
                logger.error(f"Failed to migrate cookies.txt: {e}")

    def migrate_pipeline_cache(self):
        cache_path = self.root_dir / "pipeline_cache.json"
        marker = self.root_dir / "pipeline_cache.json.migrated"
        
        if cache_path.exists() and not marker.exists():
            logger.info("Migrating pipeline_cache.json to SQLite CacheManager...")
            self._create_backup(cache_path)
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                for k, v in data.items():
                    # value 转 string，这是 cache 的常见要求
                    val_str = json.dumps(v) if not isinstance(v, str) else v
                    self.gateway.write_cache("pipeline", k, val_str)
                    
                self._mark_as_migrated(cache_path)
                logger.info("Successfully migrated pipeline_cache.json")
            except Exception as e:
                logger.error(f"Failed to migrate pipeline_cache.json: {e}")
