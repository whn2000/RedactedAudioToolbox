import os
import re
import math
import subprocess
from typing import Optional
from aafs.core.evidence import Evidence

if os.name == 'nt':
    SUBPROCESS_KWARGS = {'creationflags': 0x08000000}
else:
    SUBPROCESS_KWARGS = {}

def detect_wasted_bits(filepath: str, declared_bit_depth: int) -> Optional[Evidence]:
    """
    Analyze a FLAC file's wasted bits using the official 'flac -ac' analysis.
    If wasted_bits >= 8, it indicates the file was padded from a lower bit depth (e.g. 16-bit -> 24-bit).
    """
    if declared_bit_depth <= 16:
        return None

    if not os.path.exists(filepath):
        return None

    try:
        # Execute flac analysis command
        res = subprocess.run(["flac", "-ac", filepath], capture_output=True, text=True, **SUBPROCESS_KWARGS)
        if res.returncode != 0:
            return None

        wasted_bits_list = []
        for line in res.stdout.splitlines():
            m = re.search(r"wasted_bits=(\d+)", line)
            if m:
                wasted_bits_list.append(int(m.group(1)))

        if not wasted_bits_list:
            return None

        # Calculate average wasted bits
        wasted_bits = math.ceil(sum(wasted_bits_list) / len(wasted_bits_list))

        if wasted_bits >= 8:
            # Scale confidence: 8 wasted bits = 0.66 confidence, 12+ = 1.0 confidence
            confidence = min(1.0, wasted_bits / 12.0)
            return Evidence(
                name="wasted_bits_upconvert",
                value=float(wasted_bits),
                confidence=float(confidence),
                category="bit_padding",
                provenance_sensitive=False,
                description=f"FLAC analysis shows {wasted_bits} wasted bits out of {declared_bit_depth} bits, indicating the file only contains {declared_bit_depth - wasted_bits} bits of actual resolution."
            )

    except Exception:
        # Ignore exceptions (e.g. flac command not found)
        pass

    return None
