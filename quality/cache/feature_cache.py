import json
import hashlib
from pathlib import Path
from typing import Optional

from quality.models import AudioFeatures

class FeatureCache:
    """极速音频特征缓存，通过文件修改时间与大小计算摘要，避免重复进行频谱和通道分析。"""
    
    def __init__(self, cache_dir: str | Path = ".cache/features") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _generate_key(self, file_path: Path) -> str:
        """根据文件的绝对路径、修改时间和文件大小生成极速 Cache Key。"""
        stat = file_path.stat()
        key_string = f"{file_path.absolute()}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
        
    def get_cached_features(self, file_path: Path) -> Optional[AudioFeatures]:
        """尝试获取命中缓存的特征。"""
        try:
            key = self._generate_key(file_path)
            cache_file = self.cache_dir / f"{key}.json"
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return AudioFeatures(**data)
        except Exception:
            pass  # 任何异常情况都安全退回无缓存状态
        return None
        
    def save_cached_features(self, file_path: Path, features: AudioFeatures) -> None:
        """将提取完毕的特征存入本地缓存目录。"""
        try:
            key = self._generate_key(file_path)
            cache_file = self.cache_dir / f"{key}.json"
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(features.to_json())
        except Exception:
            pass
