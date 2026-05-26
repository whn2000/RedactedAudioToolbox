import os
import sys
from pathlib import Path
import platformdirs

class Paths:
    """
    统一路径管理类，负责解析、初始化并提供全局数据路径。
    优先级策略:
    1. REDTOOLBOX_DATA_DIR 环境变量 (适配 Docker/CI/CD/NAS)
    2. 程序目录下的 portable.flag 便携模式标志 (适配便携版)
    3. platformdirs 提供的用户标准数据目录 (适配常规桌面安装)
    """
    def __init__(self):
        # 假设 core/ 位于 redtoolbox/ 目录下
        self.app_dir = Path(__file__).resolve().parent.parent

        # 1. 检查环境变量优先
        env_dir = os.environ.get("REDTOOLBOX_DATA_DIR")
        if env_dir:
            self.data_dir = Path(env_dir).resolve()
        # 2. 检查便携模式
        elif (self.app_dir / "portable.flag").exists():
            self.data_dir = self.app_dir / "data"
        # 3. 使用系统标准用户目录
        else:
            self.data_dir = Path(platformdirs.user_data_dir("RedactedAudioToolbox", "RedactedAudioToolbox"))

        # 核心子目录划分
        self.config_dir = self.data_dir / "config"
        self.database_dir = self.data_dir / "database"
        self.cache_dir = self.data_dir / "cache"
        self.logs_dir = self.data_dir / "logs"
        self.temp_dir = self.cache_dir / "temp"
        self.spectrograms_dir = self.cache_dir / "spectrograms"
        self.backups_dir = self.database_dir / "backups"
        self.output_dir = self.data_dir / "output"

    def init_paths(self):
        """
        自动创建所有必需的目录结构。
        程序入口处应当首个调用此方法。
        """
        directories = [
            self.data_dir,
            self.config_dir,
            self.database_dir,
            self.cache_dir,
            self.logs_dir,
            self.temp_dir,
            self.spectrograms_dir,
            self.backups_dir,
            self.output_dir
        ]
        for d in directories:
            d.mkdir(parents=True, exist_ok=True)
            
    def clear_temp(self):
        """清理临时文件夹中的内容（建议在程序启动或关闭时调用）"""
        if self.temp_dir.exists():
            for item in self.temp_dir.iterdir():
                if item.is_file():
                    try:
                        item.unlink()
                    except Exception:
                        pass # 忽略正在使用或无权限的文件

# 全局路径实例
app_paths = Paths()
