import numpy as np
import librosa
from typing import Optional, Tuple
from aafs.core.evidence import Evidence

def detect_brickwall(S_db: np.ndarray, freqs: np.ndarray, nyquist_check: float = 22050, threshold_db_per_hz: float = -0.1) -> Optional[Evidence]:
    """
    检测指定频率附近的 Brickwall (断崖式频谱切断)。
    这通常意味着音频是从较低采样率 (如 44.1kHz) 强行 Upsample 的。
    
    参数:
    - S_db: STFT 频谱对数幅度 (dB)
    - freqs: 对应的频率轴
    - nyquist_check: 疑似原采样率的 Nyquist 频率 (默认 22050 对应 44.1kHz CD音质)
    - threshold_db_per_hz: 陡峭度阈值 (dB/Hz)。默认 -0.1 (即 100Hz 内下跌 10dB)
    """
    # 缩小检测区域，通常是目标截止频率附近 (例如 20k - 25k)
    mask = (freqs > (nyquist_check - 2000)) & (freqs < (nyquist_check + 3000))
    S_region = S_db[mask, :]
    freqs_region = freqs[mask]
    
    if len(freqs_region) < 2:
        return None
        
    # 为了避免静音帧的干扰，只聚合能量最高的 10% 的帧
    # 真实录音在高潮时，高频能量也会延展
    max_energy_frames = np.percentile(S_region, 90, axis=1)
    
    # 计算频域导数 (斜率)
    grad = np.diff(max_energy_frames) / np.diff(freqs_region)
    max_slope = np.min(grad) # 负值最大代表下跌最快 (最陡)
    
    steepest_idx = np.argmin(grad)
    steepest_freq = freqs_region[steepest_idx]
    
    # 判断是否为明显的砖墙，并且发生在关键频率附近
    is_brickwall = max_slope < threshold_db_per_hz
    near_nyquist = abs(steepest_freq - nyquist_check) < 500
    
    confidence = 0.0
    if is_brickwall and near_nyquist:
        # 斜率越陡，置信度越高
        confidence = min(1.0, abs(max_slope) / (abs(threshold_db_per_hz) * 3))
    
    if confidence > 0:
        return Evidence(
            name=f"brickwall_near_{int(nyquist_check)}",
            value=float(max_slope),
            confidence=float(confidence),
            category="upsample_trace",
            provenance_sensitive=True, # 模拟设备/母带机可能自带极其陡峭的 LPF
            description=f"Detected abrupt spectral cutoff at {int(steepest_freq)}Hz with slope {max_slope:.2f} dB/Hz."
        )
    return None
