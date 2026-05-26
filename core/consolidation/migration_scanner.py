import logging
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from ..paths import app_paths

logger = logging.getLogger("MigrationScanner")

class HealthLevel(Enum):
    CLEAN = "clean"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class MigrationHealthStatus:
    level: HealthLevel
    unmigrated_files: list[str]
    legacy_code_references: int

class MigrationScanner:
    """
    运行时迁移健康度扫描器。
    用于在系统启动时评估：是否还存在未迁移的旧数据文件？
    如果存在，则提醒开发者或触发自动迁移。
    """
    def __init__(self):
        self.legacy_files_to_check = [
            "config.json",
            "cookies.txt",
            "pipeline_cache.json"
        ]
        
    def scan(self) -> MigrationHealthStatus:
        unmigrated = []
        root_dir = Path(app_paths.root_dir)
        
        # 1. 检查遗留文件是否仍在磁盘上 (并且没有被标记为已迁移)
        for filename in self.legacy_files_to_check:
            file_path = root_dir / filename
            migrated_marker = root_dir / f"{filename}.migrated"
            
            if file_path.exists() and not migrated_marker.exists():
                unmigrated.append(filename)

        # 2. (可选) 可以调用 legacy_audit 获取静态引用的数量
        # 这里为了启动速度，可能只做最基本的文件扫描。如果需要，可按需启动 Auditor。
        legacy_code_refs = 0
        
        level = HealthLevel.CLEAN
        if unmigrated:
            level = HealthLevel.WARNING
            # 如果核心配置文件未迁移，认为是 critical
            if "config.json" in unmigrated:
                level = HealthLevel.CRITICAL
                
        status = MigrationHealthStatus(
            level=level,
            unmigrated_files=unmigrated,
            legacy_code_references=legacy_code_refs
        )
        return status

    def print_status(self, status: MigrationHealthStatus):
        if status.level == HealthLevel.CLEAN:
            logger.info("[Migration Health] CLEAN - No legacy data files detected.")
        else:
            logger.warning(f"[Migration Health] {status.level.name} - Found unmigrated legacy files: {', '.join(status.unmigrated_files)}")
            logger.warning("Please ensure auto_migration_runner is executed or use StorageGateway.")
