import threading
import yaml
from .paths import app_paths
from .logger import get_logger

logger = get_logger(__name__)

# 初始版本的默认配置（版本号用于后续的 Migration 检测）
DEFAULT_CONFIG = {
    "version": 1,
    "download": {
        "auto_download": True
    },
    "audio": {
        "max_spectrogram_freq": 22000
    },
    "risk": {
        "enabled": True
    }
}

class ConfigManager:
    """
    YAML 配置中心。
    支持点分嵌套键 (dot-notation) 存取，并保证多线程读写安全。
    """
    def __init__(self):
        self.config_path = app_paths.config_dir / "settings.yaml"
        self.config_data = {}
        # RLock 允许同一线程内多次获取锁
        self.data_lock = threading.RLock()
        self.load()

    def load(self):
        """从文件加载配置，若不存在则创建默认配置"""
        with self.data_lock:
            if not self.config_path.exists():
                logger.info(f"配置文件不存在，即将生成默认配置: {self.config_path}")
                self.config_data = DEFAULT_CONFIG.copy()
                self.save()
            else:
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        self.config_data = data if data else DEFAULT_CONFIG.copy()
                except Exception as e:
                    logger.error(f"读取配置文件失败: {e}，将临时使用默认配置防崩溃。")
                    self.config_data = DEFAULT_CONFIG.copy()

    def save(self):
        """安全的保存策略：先写临时文件，然后利用 replace 原子覆盖防损坏"""
        temp_path = self.config_path.with_suffix('.yaml.tmp')
        with self.data_lock:
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(self.config_data, f, default_flow_style=False, allow_unicode=True)
                
                # 跨平台的原子替换操作
                temp_path.replace(self.config_path)
            except Exception as e:
                logger.error(f"保存配置文件失败: {e}")
                if temp_path.exists():
                    temp_path.unlink() # 清理遗留临时文件

    def get(self, key_path: str, default=None):
        """
        获取嵌套配置，例如: get("audio.max_spectrogram_freq")
        """
        with self.data_lock:
            keys = key_path.split(".")
            val = self.config_data
            for key in keys:
                if isinstance(val, dict) and key in val:
                    val = val[key]
                else:
                    return default
            return val

    def set(self, key_path: str, value):
        """
        设置嵌套配置并自动持久化。
        如果路径中的中间节点不存在，将自动创建字典。
        """
        with self.data_lock:
            keys = key_path.split(".")
            d = self.config_data
            for key in keys[:-1]:
                if key not in d or not isinstance(d[key], dict):
                    d[key] = {}
                d = d[key]
            d[keys[-1]] = value
            self.save()
