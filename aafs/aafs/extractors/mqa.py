import os
import numpy as np
import soundfile as sf
from typing import Optional
from aafs.core.evidence import Evidence

# MQA magic syncword: 0xbe0498c88 (36 bits)
_MAGIC_HEX = 0xBE0498C88
_MAGIC_BITS = 36
MAGIC = np.array(
    [(_MAGIC_HEX >> (_MAGIC_BITS - 1 - i)) & 1 for i in range(_MAGIC_BITS)],
    dtype=np.uint8,
)

def _check_mqa_syncword(left: np.ndarray, right: np.ndarray) -> bool:
    """
    Check for MQA syncword in the XOR of left and right channels.
    Searches bits 16-23 of (left ^ right) for the MQA magic bit pattern.
    """
    xor = left ^ right
    magic_len = len(MAGIC)

    for bit_pos in range(16, 24):
        # Extract single bit at bit_pos from each sample
        bits = ((xor >> bit_pos) & 1).astype(np.uint8)
        if len(bits) < magic_len:
            continue
        # Sliding window search: convert 0/1 to -1/+1, correlate
        signal = bits.astype(np.int8) * 2 - 1
        pattern = MAGIC.astype(np.int8) * 2 - 1
        corr = np.correlate(signal, pattern, mode="valid")
        if np.any(corr == magic_len):
            return True

    return False

def detect_mqa_file(filepath: str) -> Optional[Evidence]:
    """
    Scan a FLAC file's first few seconds for MQA encoding markers.
    """
    if not os.path.exists(filepath):
        return None

    try:
        # Read the first 2 seconds of the audio file as int32 PCM to preserve LSB precision
        # 2 seconds at 44.1kHz is 88,200 frames. We read 100,000 to be safe.
        data, samplerate = sf.read(filepath, frames=100000, dtype='int32')
        
        # Verify it is a stereo audio file
        if len(data.shape) != 2 or data.shape[1] != 2:
            return None
            
        left = data[:, 0]
        right = data[:, 1]
        
        if _check_mqa_syncword(left, right):
            return Evidence(
                name="mqa_detected",
                value=1.0,
                confidence=1.0,
                category="lossy_trace",
                provenance_sensitive=False,
                description="MQA encoding syncword detected in audio channels. MQA is a lossy/proprietary format."
            )
            
    except Exception as e:
        # Silently ignore read exceptions
        pass

    return None
