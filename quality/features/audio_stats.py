"""
Audio metadata and statistics extraction.

Extracts bitrate, bit depth, sample rate, and other audio metadata using
ffprobe. Complements the spectrogram module which focuses on frequency
domain analysis.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SUBPROCESS_KWARGS: dict[str, Any] = {}
try:
    import os
    if os.name == "nt":
        _SUBPROCESS_KWARGS["creationflags"] = 0x08000000
except Exception:
    pass


def get_audio_metadata(file_path: Path) -> dict[str, Any]:
    """Extract audio metadata using ffprobe.

    Args:
        file_path: Path to the audio file.

    Returns:
        Dictionary with keys: bit_depth, sample_rate, codec, channels,
        duration_seconds, avg_bitrate_kbps.
    """
    result: dict[str, Any] = {
        "bit_depth": None,
        "sample_rate": None,
        "codec": None,
        "channels": None,
        "duration_seconds": None,
        "avg_bitrate_kbps": None,
    }

    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", "-select_streams", "a:0",
            str(file_path),
        ]
        output = subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            **_SUBPROCESS_KWARGS,
        )
        data = json.loads(output.stdout)

        # Extract from stream
        if "streams" in data and len(data["streams"]) > 0:
            stream = data["streams"][0]
            bps = stream.get("bits_per_raw_sample") or stream.get("bits_per_sample")
            if bps and str(bps).isdigit():
                result["bit_depth"] = int(bps)

            sr = stream.get("sample_rate")
            if sr and str(sr).isdigit():
                result["sample_rate"] = int(sr)

            result["codec"] = stream.get("codec_name")
            ch = stream.get("channels")
            if ch and str(ch).isdigit():
                result["channels"] = int(ch)

            duration = stream.get("duration")
            if duration:
                try:
                    result["duration_seconds"] = float(duration)
                except ValueError:
                    pass

        # Extract from format
        if "format" in data:
            fmt = data["format"]
            bit_rate = fmt.get("bit_rate")
            if bit_rate and str(bit_rate).isdigit():
                result["avg_bitrate_kbps"] = round(int(bit_rate) / 1000, 1)

            if result["duration_seconds"] is None:
                duration = fmt.get("duration")
                if duration:
                    try:
                        result["duration_seconds"] = float(duration)
                    except ValueError:
                        pass

    except FileNotFoundError:
        logger.warning("ffprobe not found — cannot extract audio metadata")
    except subprocess.CalledProcessError as exc:
        logger.warning("ffprobe failed for %s: %s", file_path, exc)
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Failed to parse ffprobe output for %s: %s", file_path, exc)

    return result


def compute_fake_hires_score(
    bit_depth: int | None,
    sample_rate: int | None,
    cutoff_freq: float | None,
) -> float | None:
    """Compute a fake Hi-Res likelihood score.

    Compares the declared sample rate against the actual frequency
    content as determined by spectrogram cutoff analysis.

    Args:
        bit_depth: Declared bit depth.
        sample_rate: Declared sample rate in Hz.
        cutoff_freq: Measured cutoff frequency in Hz.

    Returns:
        Score from 0.0 (genuine) to 1.0 (definitely fake), or None
        if insufficient data.
    """
    if sample_rate is None or cutoff_freq is None:
        return None

    # Only relevant for Hi-Res content (sample_rate > 48kHz)
    if sample_rate <= 48000:
        nyquist = sample_rate / 2.0
        # If cutoff is below 80% of nyquist, suspicious
        ratio = cutoff_freq / nyquist
        if ratio >= 0.9:
            return 0.0
        elif ratio >= 0.8:
            return 0.2
        elif ratio >= 0.7:
            return 0.5
        else:
            return 0.8

    # Hi-Res: sample_rate > 48kHz
    nyquist = sample_rate / 2.0
    # True Hi-Res should have content well above 22kHz
    if cutoff_freq >= 30000:
        return 0.0  # Genuine Hi-Res
    elif cutoff_freq >= 24000:
        return 0.3  # Borderline
    elif cutoff_freq >= 22000:
        return 0.6  # Likely upsampled from 44.1/48kHz
    else:
        return 0.9  # Almost certainly fake Hi-Res


def compute_mp3_signature_score(
    cutoff_freq: float | None,
    hf_rolloff_smoothness: float | None,
    avg_bitrate_kbps: float | None,
) -> float | None:
    """Compute a score indicating MP3 transcode artifacts.

    MP3 encoding produces characteristic patterns:
    - Hard cutoff at specific frequencies (16kHz, 19kHz, 20kHz)
    - Very smooth/sharp rolloff (unlike natural analog rolloff)
    - Certain bitrate ranges correspond to known MP3 presets

    Args:
        cutoff_freq: Measured cutoff frequency in Hz.
        hf_rolloff_smoothness: Measured rolloff smoothness (0-1).
        avg_bitrate_kbps: Average bitrate in kbps.

    Returns:
        Score from 0.0 (no MP3 signs) to 1.0 (definite MP3 source).
    """
    if cutoff_freq is None:
        return None

    score = 0.0
    evidence_count = 0

    # Check for known MP3 cutoff frequencies
    mp3_cutoffs = [
        (15500, 16500, 0.9),   # 128kbps MP3
        (17500, 18500, 0.7),   # 160kbps MP3
        (18500, 19500, 0.6),   # 192kbps MP3
        (19500, 20500, 0.5),   # 256kbps MP3
        (20000, 21000, 0.4),   # 320kbps MP3
    ]

    for low, high, weight in mp3_cutoffs:
        if low <= cutoff_freq <= high:
            score += weight
            evidence_count += 1
            break

    # Sharp rolloff is characteristic of MP3
    if hf_rolloff_smoothness is not None and hf_rolloff_smoothness > 0.7:
        score += 0.3
        evidence_count += 1

    if evidence_count == 0:
        return 0.0

    return min(1.0, round(score / max(evidence_count, 1), 4))
