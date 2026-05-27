from typing import List
from aafs.core.evidence import Evidence

def apply_provenance_suppression(evidences: List[Evidence]) -> List[Evidence]:
    """
    溯源感知降权系统 (MVP版)。
    扫描所有证据。如果发现了模拟来源证据 (如 tape hiss)，
    则对那些极易被老录音误导的特征 (如 brickwall, lossy_trace) 强制降低置信度。
    """
    # 1. 查找是否存在 Analog Provenance 证据
    is_analog_sourced = False
    analog_confidence = 0.0
    
    for ev in evidences:
        if ev.category == "provenance" and ev.name == "analog_tape_hiss":
            if ev.confidence > 0.6:
                is_analog_sourced = True
                analog_confidence = ev.confidence
                break
                
    # 2. 如果是模拟源，降低相关敏感证据的置信度
    if is_analog_sourced:
        for ev in evidences:
            if ev.provenance_sensitive:
                # 动态降权：模拟源置信度越高，敏感证据被降权越多
                suppression_factor = 1.0 - (0.8 * analog_confidence) # 最多降低 80% 的权重
                
                original_conf = ev.confidence
                ev.confidence *= suppression_factor
                
                ev.description += f" [Suppressed {original_conf:.2f}->{ev.confidence:.2f} due to Analog Provenance]"
                
    return evidences
