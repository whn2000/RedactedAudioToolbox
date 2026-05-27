import numpy as np
from typing import Optional
from aafs.core.evidence import Evidence

def detect_tape_hiss_or_analog_noise(S_mag: np.ndarray, freqs: np.ndarray) -> Optional[Evidence]:
    """
    检测模拟母带/磁带特有的高频连续宽带底噪 (Tape Hiss)。
    如果被检测到，说明这是一个老式模拟录音。
    """
    # 关注 10kHz 到 20kHz 的高频区
    mask = (freqs > 10000) & (freqs < 20000)
    S_hf = S_mag[mask, :]
    
    if S_hf.size == 0:
        return None
        
    # 分析高频段的熵。模拟磁带底噪非常接近高频白噪声/粉红噪声，频谱非常平坦且密集
    # 计算每一帧的高频熵
    S_hf_norm = S_hf / (np.sum(S_hf, axis=0) + 1e-10)
    entropy = -np.sum(S_hf_norm * np.log2(S_hf_norm + 1e-10), axis=0)
    
    max_entropy = np.log2(len(freqs[mask]))
    normalized_entropy = entropy / max_entropy
    
    # 获取整首歌的平稳度。模拟底噪应该是整首歌一直存在的，哪怕在静音段
    median_entropy = np.median(normalized_entropy)
    
    # 计算静音段的高频能量 (如果不带静音段，取能量最低的10%帧)
    frame_energy = np.sum(S_mag**2, axis=0)
    quiet_frames = frame_energy < np.percentile(frame_energy, 10)
    
    if not np.any(quiet_frames):
        return None
        
    quiet_hf_energy = np.mean(S_hf[:, quiet_frames])
    
    confidence = 0.0
    # 极高的高频谱熵 (>0.85) 且静音段有显著高频底噪
    if median_entropy > 0.85 and quiet_hf_energy > 1e-4:
        confidence = min(1.0, (median_entropy - 0.8) / 0.15)
        
    if confidence > 0.5:
        return Evidence(
            name="analog_tape_hiss",
            value=float(median_entropy),
            confidence=float(confidence),
            category="provenance",
            provenance_sensitive=False,
            description=f"Detected high continuous analog noise floor (entropy: {median_entropy:.2f}). Highly likely an analog-sourced recording."
        )
        
    return None
