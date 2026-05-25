"""
Channel analysis for stereo audio files.

Computes the similarity between left and right channels to detect
mono-mastered content falsely presented as stereo, or unusual
channel configurations that may indicate processing artifacts.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
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


def compute_channel_similarity(file_path: Path) -> float | None:
    """Compute the similarity between left and right channels.

    Uses SoX to extract per-channel spectrograms and compares their
    pixel-level content. A similarity of 1.0 means channels are
    identical (suspicious for music).

    Args:
        file_path: Path to a stereo audio file.

    Returns:
        Similarity ratio from 0.0 (completely different) to 1.0 (identical),
        or None if the file is not stereo or analysis fails.
    """
    try:
        # Check if file is stereo
        result = subprocess.run(
            ["sox", "--info", "-c", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **_SUBPROCESS_KWARGS,
        )
        channels = int(result.stdout.strip())
        if channels < 2:
            logger.debug("File %s has %d channels, skipping similarity", file_path, channels)
            return None

        tmp_dir = Path(tempfile.mkdtemp())
        left_img = tmp_dir / "left.png"
        right_img = tmp_dir / "right.png"

        # Generate spectrogram for left channel
        subprocess.run(
            [
                "sox", str(file_path), "-n",
                "remix", "1",
                "spectrogram", "-r", "-Y", "256", "-o", str(left_img),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_SUBPROCESS_KWARGS,
        )

        # Generate spectrogram for right channel
        subprocess.run(
            [
                "sox", str(file_path), "-n",
                "remix", "2",
                "spectrogram", "-r", "-Y", "256", "-o", str(right_img),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_SUBPROCESS_KWARGS,
        )

        if not left_img.exists() or not right_img.exists():
            logger.debug("Failed to generate channel spectrograms for %s", file_path)
            return None

        similarity = _compare_images(left_img, right_img)

        # Cleanup
        for f in [left_img, right_img]:
            try:
                f.unlink()
            except OSError:
                pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

        return similarity

    except FileNotFoundError:
        logger.warning("sox not found — cannot compute channel similarity")
        return None
    except Exception as exc:
        logger.debug("Channel similarity computation failed for %s: %s", file_path, exc)
        return None


def _compare_images(img_a: Path, img_b: Path) -> float:
    """Compare two grayscale images pixel-by-pixel.

    Args:
        img_a: Path to first image.
        img_b: Path to second image.

    Returns:
        Similarity ratio from 0.0 to 1.0.
    """
    from PIL import Image

    a = Image.open(img_a).convert("L")
    b = Image.open(img_b).convert("L")

    # Resize to same dimensions if needed
    if a.size != b.size:
        b = b.resize(a.size)

    width, height = a.size
    total_pixels = width * height

    if total_pixels == 0:
        return 1.0

    matching = 0
    for y in range(height):
        for x in range(width):
            pa = a.getpixel((x, y))
            pb = b.getpixel((x, y))
            # Pixels within tolerance of 10 are considered matching
            if abs(pa - pb) <= 10:
                matching += 1

    return round(matching / total_pixels, 4)
