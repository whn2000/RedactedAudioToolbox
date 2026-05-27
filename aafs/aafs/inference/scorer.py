from typing import List, Dict, Any
from aafs.core.evidence import Evidence
from aafs.inference.suppressor import apply_provenance_suppression

class SimpleScorer:
    """
    MVP 版本的简易打分器。
    代替复杂的 XGBoost 保证我们系统能跑起来。
    """
    def __init__(self):
        pass
        
    def evaluate(self, evidences: List[Evidence]) -> Dict[str, Any]:
        # 先经过溯源降权
        evidences = apply_provenance_suppression(evidences)
        
        fake_hi_res_score = 0.0
        fake_lossless_score = 0.0
        
        reasons = []
        
        for ev in evidences:
            if ev.confidence > 0.3: # 只考虑显著的证据
                if ev.category == "upsample_trace":
                    fake_hi_res_score = max(fake_hi_res_score, ev.confidence)
                    reasons.append(ev.description)
                elif ev.category == "lossy_trace":
                    fake_lossless_score = max(fake_lossless_score, ev.confidence)
                    reasons.append(ev.description)
                elif ev.category == "bit_padding":
                    fake_hi_res_score = max(fake_hi_res_score, ev.confidence)
                    reasons.append(ev.description)
                    
        # 最终决定
        is_fake_hi_res = fake_hi_res_score > 0.6
        is_fake_lossless = fake_lossless_score > 0.6
        
        classification = "genuine"
        if is_fake_lossless:
            classification = "fake_lossless (transcoded)"
        elif is_fake_hi_res:
            classification = "fake_hi_res (upsampled / padded)"
            
        return {
            "classification": classification,
            "fake_hi_res_probability": float(fake_hi_res_score),
            "fake_lossless_probability": float(fake_lossless_score),
            "evidences": [ev.to_dict() for ev in evidences],
            "summary_reasons": reasons
        }
