import numpy as np
import librosa
from typing import Optional
from aafs.core.evidence import Evidence

def detect_spectral_holes(S_mag: np.ndarray, freqs: np.ndarray, start_freq: float = 16000.0, percentile: int = 90) -> Optional[Evidence]:
    """
    检测频谱空洞 (Spectral Holes)。
    有损编码 (MP3/AAC) 会将心理声学掩蔽阈值以下的频带直接清零（或变为极低的量化噪声）。
    
    参数:
    - S_mag: STFT 幅度谱 (线性值，非 dB)
    - freqs: 对应的频率轴
    - start_freq: 开始检测的高频起点 (默认 16kHz)
    - percentile: 用于统计的百分位数 (默认取全曲 90% 的最严重帧)
    """
    hf_idx = np.where(freqs > start_freq)[0]
    if len(hf_idx) == 0:
        return None
        
    S_hf = S_mag[hf_idx, :]
    
    # 动态计算该音频高频区域的相对底噪
    # 不使用绝对 0，以防止轻微的 dither 或重采样引入极其微弱的底噪
    max_val = np.max(S_mag)
    zero_threshold = 1e-5 * max_val 
    
    # 计算每一帧的高频空洞比例
    holes_ratio_per_frame = np.sum(S_hf < zero_threshold, axis=0) / len(hf_idx)
    
    # 能量门限：只考察整首曲子能量最高的 25% 帧，排除静音帧的干扰
    frame_energy = np.sum(S_mag**2, axis=0)
    energy_thresh = np.percentile(frame_energy, 75)
    active_frames = frame_energy > energy_thresh
    
    if not np.any(active_frames):
        return None
        
    active_holes = holes_ratio_per_frame[active_frames]
    
    # 取最严重的 percentile
    p_holes = np.percentile(active_holes, percentile)
    
    confidence = 0.0
    # 通常 >30% 空洞就非常可疑，>60% 实锤
    if p_holes > 0.3:
        confidence = min(1.0, (p_holes - 0.3) / 0.5)
        
    if confidence > 0:
        return Evidence(
            name="high_density_spectral_holes",
            value=float(p_holes),
            confidence=float(confidence),
            category="lossy_trace",
            provenance_sensitive=False, # 模拟老录音即使没有高频，也会被平滑的磁带底噪填满，绝不会出现坑洞
            description=f"{p_holes*100:.1f}% of high-frequency bins (> {start_freq/1000:.1f}kHz) are quantization dead zones in high-energy frames."
        )
    return None
