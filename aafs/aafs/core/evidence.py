from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Evidence:
    """
    证据对象，用于连接物理特征提取层与判定层。
    确保系统具备法医级可解释性。
    """
    name: str                   # 证据名称，如 "brickwall_at_22050"
    value: float                # 原始物理值，如 -120.5 (dB/kHz)
    confidence: float           # 探测器的置信度 (0.0~1.0)
    category: str               # 分类: 'lossy_trace', 'upsample_trace', 'bit_padding', 'provenance'
    provenance_sensitive: bool  # 遇到老录音时，此证据是否该被忽略/降权
    description: str            # 可解释的自然语言描述
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 4) if isinstance(self.value, float) else self.value,
            "confidence": round(self.confidence, 4),
            "category": self.category,
            "provenance_sensitive": self.provenance_sensitive,
            "description": self.description
        }
