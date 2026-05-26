import os
import shutil
from pathlib import Path
from .paths import app_paths
from .logger import get_logger

logger = get_logger(__name__)

class CacheManager:
    """
    统一缓存生命周期管理器。
    用于接管文件系统中的临时文件 (temp) 与大体积频图 (spectrograms) 的淘汰策略，
    并能够调用 DBManager 执行数据库内的 API 缓存过期清理。
    """
    def __init__(self, db_manager):
        self.db = db_manager
        self.temp_dir = app_paths.temp_dir
        self.spec_dir = app_paths.spectrograms_dir

    def init_cleanup(self):
        """应用启动时挂载的常规体检与清理程序"""
        logger.info("开始执行启动期的缓存体检任务...")
        self.cleanup_temp()
        self.cleanup_expired()
        # 默认限制频图目录为 1024 MB (1GB)，超出则按最后修改时间淘汰
        self.cleanup_by_size(self.spec_dir, max_size_mb=1024)

    def cleanup_temp(self):
        """
        强力清空临时目录 (每次冷启动必须执行)。
        跳过无法删除的锁定文件。
        """
        if not self.temp_dir.exists():
            return
            
        try:
            for item in self.temp_dir.iterdir():
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as e:
                    logger.debug(f"忽略临时文件清理失败 (可能正被占用): {item.name} - {e}")
            logger.info("临时数据清空完毕。")
        except Exception as e:
            logger.error(f"清理临时目录时发生严重错误: {e}")

    def cleanup_expired(self):
        """向 SQLite 下达指令，清理超期的 API 返回值缓存"""
        if not self.db:
            return
            
        try:
            # 配合第一阶段定义的 search_cache 表
            deleted_count = self.db.execute("DELETE FROM search_cache WHERE expires_at < CURRENT_TIMESTAMP")
            if deleted_count > 0:
                logger.info(f"已清理数据库中 {deleted_count} 条超时的 API 缓存记录。")
        except Exception as e:
            logger.error(f"清理 SQLite 过期缓存失败: {e}")

    def cleanup_by_size(self, target_dir: Path, max_size_mb: int):
        """
        核心的容量控制算法。
        按照文件的 Last Modified 时间，从旧到新依次删除，直到总体积跌回水位线。
        暂不依赖外部数据库，直接操作文件系统 stats。
        """
        if not target_dir.exists():
            return
            
        try:
            files_meta = []
            total_size = 0
            
            # 第一趟扫描：聚合体积与时间戳
            for item in target_dir.iterdir():
                if item.is_file():
                    stat = item.stat()
                    total_size += stat.st_size
                    files_meta.append((item, stat.st_size, stat.st_mtime))
            
            max_bytes = max_size_mb * 1024 * 1024
            if total_size <= max_bytes:
                return
                
            logger.warning(f"目录 {target_dir.name} 容量告警 ({total_size/1024/1024:.2f} MB > {max_size_mb} MB)，触发淘汰机制。")
            
            # 按照修改时间升序（最旧的文件排在最前面）
            files_meta.sort(key=lambda x: x[2])
            
            freed_bytes = 0
            # 第二趟扫描：拔除老旧文件
            for file_path, fsize, fmtime in files_meta:
                try:
                    file_path.unlink()
                    freed_bytes += fsize
                    total_size -= fsize
                    if total_size <= max_bytes:
                        break # 水位恢复正常，停火
                except Exception as e:
                    logger.debug(f"无法删除旧缓存: {file_path.name} - {e}")
                    
            logger.info(f"容量淘汰执行完毕，本次回收空间: {freed_bytes/1024/1024:.2f} MB。")
            
        except Exception as e:
            logger.error(f"在清理目录 {target_dir} 的空间限制时发生错误: {e}")
