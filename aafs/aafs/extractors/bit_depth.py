import numpy as np
from scipy import signal
from typing import Optional
from aafs.core.evidence import Evidence

def detect_fake_bit_depth_via_lsb(audio_array: np.ndarray, declared_bit_depth: int = 24) -> Optional[Evidence]:
    """
    通过 LSB 残差自相关区分 TPDF Dither (造假) 与真实声学底噪。
    如果标称 24bit，但低 8 位实际上是白噪声 dither 或者全 0，说明它是从 16bit 甚至更低假冒的。
    
    参数:
    - audio_array: 浮点音频数组 (通常是 -1.0 到 1.0 之间)
    - declared_bit_depth: 标称位深 (例如 24)
    """
    if declared_bit_depth <= 16:
        return None
        
    # 将 -1~1 转为对应 bit深度的整数范围
    scale = 2**(declared_bit_depth - 1)
    # 取音频的一段代表性窗口，避免计算量过大。例如取 5 秒 (5 * 48000)
    sample_len = min(len(audio_array), 240000)
    
    # 找寻能量较大的一段（避开开头绝对静音）
    rms = librosa.feature.rms(y=audio_array, frame_length=2048, hop_length=512)[0]
    if len(rms) > 0:
        max_rms_idx = np.argmax(rms)
        start_sample = max_rms_idx * 512
        end_sample = min(len(audio_array), start_sample + sample_len)
        audio_window = audio_array[start_sample:end_sample]
    else:
        audio_window = audio_array[:sample_len]
        
    int_audio = audio_window * scale
    
    # 提取量化残差 (由于是从 16bit 转来的，残差相当于 16bit 以下的数值)
    # 对于 24-bit 来说，就是最低 8 位的浮点余数
    # 这里我们通过量化到 16bit 精度来提取差异
    quantized_16 = np.round(audio_window * (2**15)) / (2**15)
    residual = (audio_window - quantized_16) * scale
    
    if np.max(np.abs(residual)) < 1e-9:
        # 完全没有残差，说明是 Naive 补 0 (GCD=256)
        return Evidence(
            name="zero_padded_lsb",
            value=0.0,
            confidence=1.0, # 100% 肯定
            category="bit_padding",
            provenance_sensitive=False,
            description="The lower 8 bits of the 24-bit container are completely zero. This is a 16-bit file."
        )
        
    # 计算自相关
    autocorr = signal.correlate(residual, residual, mode='full')
    autocorr = autocorr[len(autocorr)//2:]
    
    # 归一化自相关
    if autocorr[0] < 1e-10:
        return None
        
    autocorr_norm = autocorr / autocorr[0]
    
    # 测量 lag 1 到 5 的相关性能量
    temporal_correlation_energy = np.sum(np.abs(autocorr_norm[1:6]))
    
    # 如果 temporal_correlation_energy 极低 (< 0.05)，高度怀疑是人工强加的 Dither (白噪声)
    confidence = 0.0
    if temporal_correlation_energy < 0.08:
        # 能量越低，越确信是 dither
        confidence = min(1.0, (0.08 - temporal_correlation_energy) / 0.08)
        
    if confidence > 0.5:
        return Evidence(
            name="dithered_lsb",
            value=float(temporal_correlation_energy),
            confidence=float(confidence),
            category="bit_padding",
            provenance_sensitive=True,
            description=f"LSB autocorrelation energy is {temporal_correlation_energy:.3f}, indicating synthetic TPDF dither rather than acoustic noise floor. Effective bit-depth is ~16."
        )
        
    return None

import librosa # 放在函数内部或文件头部
