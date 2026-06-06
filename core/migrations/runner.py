import shutil
import time
from pathlib import Path
from ..paths import app_paths
from ..logger import get_logger

logger = get_logger(__name__)

# 定义当前代码库预期的结构版本
EXPECTED_YAML_VERSION = 1
EXPECTED_DB_SCHEMA_VERSION = 3

class MigrationRunner:
    """
    全自动的基建无损升级器。
    统一协调 YAML 字段升级与 SQLite Schema 变迁，防范旧数据被破坏。
    在进行任何写入前强制落盘备份（轮转制）。
    """
    def __init__(self, db_manager, config_manager):
        self.db = db_manager
        self.config = config_manager
        self.backups_dir = app_paths.backups_dir

    def run_migrations(self):
        """启动期的总指挥入口"""
        logger.info("正在验证数据结构的完整性与版本...")
        
        # 探测当前系统所处的版本
        current_yaml_ver = self.config.get("version", 1)
        
        row = self.db.fetch_one("SELECT value FROM meta WHERE key = 'schema_version'")
        current_db_ver = int(row["value"]) if row else 1

        if current_yaml_ver < EXPECTED_YAML_VERSION or current_db_ver < EXPECTED_DB_SCHEMA_VERSION:
            logger.warning(f"检测到版本落后 (YAML: {current_yaml_ver}->{EXPECTED_YAML_VERSION}, DB: {current_db_ver}->{EXPECTED_DB_SCHEMA_VERSION})。即将开启自动化迁移。")
            self._create_backup()
            
            # 分阶段执行，利用事务保护
            try:
                self._migrate_db(current_db_ver, EXPECTED_DB_SCHEMA_VERSION)
                self._migrate_yaml(current_yaml_ver, EXPECTED_YAML_VERSION)
                logger.info("全部迁移任务圆满成功。")
            except Exception as e:
                logger.error(f"自动化迁移在执行中崩溃: {e}。当前系统启动已被终止，保护数据不受损。")
                raise
        else:
            logger.debug("结构验证通过，无需迁移。")

    def _create_backup(self, max_backups=5):
        """生产级的防灾准备：轮转备份 DB 与 YAML"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        db_source = app_paths.database_dir / "app.db"
        yaml_source = app_paths.config_dir / "settings.yaml"
        
        db_backup = self.backups_dir / f"app_v{EXPECTED_DB_SCHEMA_VERSION}_{timestamp}.db.bak"
        yaml_backup = self.backups_dir / f"settings_v{EXPECTED_YAML_VERSION}_{timestamp}.yaml.bak"

        try:
            if db_source.exists():
                shutil.copy2(db_source, db_backup)
            if yaml_source.exists():
                shutil.copy2(yaml_source, yaml_backup)
            logger.info(f"已创建防灾备份：{timestamp}")
            
            # 轮转清理旧备份
            backups = sorted([f for f in self.backups_dir.iterdir() if f.suffix == ".bak"], key=lambda x: x.stat().st_mtime)
            while len(backups) > max_backups * 2: # yaml 和 db 各一份，乘以 2
                oldest = backups.pop(0)
                oldest.unlink(missing_ok=True)
                logger.debug(f"触发轮转，清理了超期的旧备份：{oldest.name}")
        except Exception as e:
            logger.error(f"严重警告：在创建迁移备份时发生错误 ({e})！")
            raise

    def _migrate_db(self, current, target):
        """DB 结构变迁，严格包裹在 Transaction 中。当前版本为空跑框架。"""
        if current >= target:
            return
            
        with self.db.transaction() as cursor:
            if current == 1: 
                # 从 V1 到 V2：更新 watch_artists，增加 discovery_results
                try:
                    cursor.execute("ALTER TABLE watch_artists ADD COLUMN target_sites TEXT DEFAULT '[\"RED\"]'")
                    cursor.execute("ALTER TABLE watch_artists ADD COLUMN enabled INTEGER DEFAULT 1")
                    cursor.execute("ALTER TABLE watch_artists ADD COLUMN check_interval INTEGER DEFAULT 43200")
                except Exception as e:
                    logger.warning(f"ALTER TABLE 可能部分已存在 (这在开发调试期间可能发生): {e}")

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS discovery_results (
                    id TEXT PRIMARY KEY,
                    artist TEXT NOT NULL,
                    album TEXT NOT NULL,
                    year INTEGER,
                    platform TEXT NOT NULL,
                    platform_id TEXT NOT NULL,
                    red_exists INTEGER DEFAULT 0,
                    ops_exists INTEGER DEFAULT 0,
                    red_group_id INTEGER,
                    ops_group_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                current = 2

            if current == 2:
                try:
                    cursor.execute("ALTER TABLE discovery_results ADD COLUMN jps_exists INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE discovery_results ADD COLUMN dic_exists INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE discovery_results ADD COLUMN jps_group_id INTEGER")
                    cursor.execute("ALTER TABLE discovery_results ADD COLUMN dic_group_id INTEGER")
                except Exception as e:
                    logger.warning(f"ALTER TABLE 可能部分已存在: {e}")
                current = 3
            
            # 最后必须更新版本号
            cursor.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (str(target),))
            logger.info(f"SQLite Schema 已成功跃升至 V{target}。")

    def _migrate_yaml(self, current, target):
        """YAML 配置变迁，利用 ConfigManager 自带的线程安全更新。"""
        if current >= target:
            return
            
        # TODO: 未来在此处添加配置默认值补全逻辑
        
        self.config.set("version", target)
        logger.info(f"YAML 配置已成功跃升至 V{target}。")
