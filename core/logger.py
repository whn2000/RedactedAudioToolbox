import logging
import sys
from logging.handlers import RotatingFileHandler
from .paths import app_paths

# 确保在使用日志系统前目录已经存在
app_paths.init_paths()

LOG_FORMAT = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class LevelFilter(logging.Filter):
    """用于精确控制文件输出的等级范围"""
    def __init__(self, low, high):
        super().__init__()
        self.low = low
        self.high = high

    def filter(self, record):
        return self.low <= record.levelno <= self.high

def _setup_root_logger():
    """初始化全局 Root Logger"""
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        return # 防止重复添加 handler
        
    root_logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # 1. 控制台输出 (INFO及以上，便于 Docker logs 和 CLI)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 2. 常规运行日志 (app.log: DEBUG 到 INFO)
    app_log_path = app_paths.logs_dir / "app.log"
    app_handler = RotatingFileHandler(
        app_log_path, maxBytes=10 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(formatter)
    app_handler.addFilter(LevelFilter(logging.DEBUG, logging.INFO))

    # 3. 错误日志 (error.log: WARNING 及以上)
    error_log_path = app_paths.logs_dir / "error.log"
    error_handler = RotatingFileHandler(
        error_log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)

def get_logger(name: str) -> logging.Logger:
    """
    统一的日志获取入口。
    示例: logger = get_logger(__name__)
    """
    _setup_root_logger()
    return logging.getLogger(name)
