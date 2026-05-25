"""
Spectrogram-based feature extraction.

Wraps the existing lossless_checker functions to extract spectrogram
features (cutoff frequency, high-frequency energy, gap detection, etc.)
without duplicating analysis logic.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Windows: hide subprocess console windows
_SUBPROCESS_KWARGS: dict[str, Any] = {}
try:
    import os
    if os.name == "nt":
        _SUBPROCESS_KWARGS["creationflags"] = 0x08000000
except Exception:
    pass


def get_audio_nyquist(file_path: Path) -> float:
    """Get the Nyquist frequency of an audio file via soxi.

    Args:
        file_path: Path to the audio file.

    Returns:
        Nyquist frequency in Hz. Defaults to 22050.0 on error.
    """
    try:
        result = subprocess.run(
            ["sox", "--info", "-r", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **_SUBPROCESS_KWARGS,
        )
        sample_rate = int(result.stdout.strip())
        return sample_rate / 2.0
    except Exception as exc:
        logger.debug("Failed to get Nyquist for %s: %s", file_path, exc)
        return 22050.0


def get_audio_specs(file_path: Path) -> tuple[int, int]:
    """Get bit depth and sample rate of an audio file via soxi.

    Args:
        file_path: Path to the audio file.

    Returns:
        Tuple of (bit_depth, sample_rate). Defaults to (16, 44100) on error.
    """
    try:
        res_sr = subprocess.run(
            ["sox", "--info", "-r", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **_SUBPROCESS_KWARGS,
        )
        sample_rate = int(res_sr.stdout.strip())
        res_b = subprocess.run(
            ["sox", "--info", "-b", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **_SUBPROCESS_KWARGS,
        )
        bit_depth = int(res_b.stdout.strip())
        return bit_depth, sample_rate
    except Exception as exc:
        logger.debug("Failed to get audio specs for %s: %s", file_path, exc)
        return 16, 44100


def generate_raw_spectrogram(file_path: Path, output_path: Path) -> bool:
    """Generate a raw (no axes) spectrogram image using SoX.

    Args:
        file_path: Path to the audio file.
        output_path: Path where the PNG image will be saved.

    Returns:
        True if the spectrogram was generated successfully.
    """
    try:
        subprocess.run(
            [
                "sox", str(file_path), "-n", "spectrogram",
                "-r", "-Y", "512", "-o", str(output_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_SUBPROCESS_KWARGS,
        )
        return output_path.exists()
    except Exception as exc:
        logger.warning("Failed to generate spectrogram for %s: %s", file_path, exc)
        return False


def analyze_spectrogram_cutoff(
    spectrogram_path: Path,
    nyquist_freq: float,
) -> float | None:
    """Analyze a raw spectrogram image to determine frequency cutoff.

    Scans from the top (highest frequency) downward, looking for rows
    with significant signal energy.

    Args:
        spectrogram_path: Path to a raw spectrogram PNG (no axes).
        nyquist_freq: Nyquist frequency of the source audio.

    Returns:
        Cutoff frequency in Hz, or None if analysis fails.
    """
    try:
        from PIL import Image

        img = Image.open(spectrogram_path).convert("L")
        width, height = img.size

        cutoff_row = 0
        for y in range(height):
            row_pixels = [img.getpixel((x, y)) for x in range(width)]
            bright_pixels = sum(1 for p in row_pixels if p > 30)
            if bright_pixels > width * 0.01 or max(row_pixels) > 80:
                cutoff_row = y
                break

        cutoff_freq = nyquist_freq * (1 - (cutoff_row / height))
        return round(cutoff_freq, 2)
    except Exception as exc:
        logger.warning("Spectrogram analysis failed for %s: %s", spectrogram_path, exc)
        return None


def detect_spectrogram_gap(
    spectrogram_path: Path,
    nyquist_freq: float,
) -> bool:
    """Detect visible gaps or shelves in a spectrogram.

    A gap is identified when there is a sudden drop in energy across
    a horizontal band, indicating a lossy encoding artifact.

    Args:
        spectrogram_path: Path to a raw spectrogram PNG.
        nyquist_freq: Nyquist frequency of the source audio.

    Returns:
        True if a gap is detected, False otherwise.
    """
    try:
        from PIL import Image

        img = Image.open(spectrogram_path).convert("L")
        width, height = img.size

        # Compute average brightness per row
        row_avgs: list[float] = []
        for y in range(height):
            row_pixels = [img.getpixel((x, y)) for x in range(width)]
            row_avgs.append(sum(row_pixels) / width)

        # Look for sudden drops (gap = a row much darker than neighbors)
        # Only check the lower 80% of the image (audible range)
        start_row = int(height * 0.2)
        for y in range(start_row + 2, height - 2):
            above_avg = (row_avgs[y - 1] + row_avgs[y - 2]) / 2
            current_avg = row_avgs[y]
            below_avg = (row_avgs[y + 1] + row_avgs[y + 2]) / 2

            if above_avg > 5 and current_avg < above_avg * 0.3 and below_avg > above_avg * 0.5:
                logger.debug(
                    "Spectrogram gap detected at row %d (avg=%.1f, above=%.1f, below=%.1f)",
                    y, current_avg, above_avg, below_avg,
                )
                return True

        return False
    except Exception as exc:
        logger.debug("Gap detection failed for %s: %s", spectrogram_path, exc)
        return False


def compute_hf_energy_ratio(
    spectrogram_path: Path,
    nyquist_freq: float,
    threshold_hz: float = 16000.0,
) -> float | None:
    """Compute the ratio of high-frequency energy to total energy.

    Args:
        spectrogram_path: Path to a raw spectrogram PNG.
        nyquist_freq: Nyquist frequency of the source audio.
        threshold_hz: Frequency threshold separating LF from HF.

    Returns:
        Ratio from 0.0 to 1.0, or None on failure.
    """
    try:
        from PIL import Image

        img = Image.open(spectrogram_path).convert("L")
        width, height = img.size

        # Row 0 = highest frequency (nyquist), row height-1 = 0 Hz
        threshold_row = int(height * (1 - threshold_hz / nyquist_freq))
        threshold_row = max(0, min(threshold_row, height - 1))

        total_energy = 0.0
        hf_energy = 0.0

        for y in range(height):
            row_sum = sum(img.getpixel((x, y)) for x in range(width))
            total_energy += row_sum
            if y <= threshold_row:
                hf_energy += row_sum

        if total_energy == 0:
            return 0.0

        return round(hf_energy / total_energy, 4)
    except Exception as exc:
        logger.debug("HF energy ratio computation failed: %s", exc)
        return None


def compute_hf_rolloff_smoothness(
    spectrogram_path: Path,
    nyquist_freq: float,
) -> float | None:
    """Measure the smoothness of the high-frequency rolloff.

    A natural rolloff is gradual (smoothness close to 0.0), while a
    hard cutoff from lossy encoding produces an abrupt transition
    (smoothness close to 1.0).

    Args:
        spectrogram_path: Path to a raw spectrogram PNG.
        nyquist_freq: Nyquist frequency of the source audio.

    Returns:
        Smoothness score (0.0=gradual, 1.0=sharp cutoff), or None on failure.
    """
    try:
        from PIL import Image

        img = Image.open(spectrogram_path).convert("L")
        width, height = img.size

        # Compute row averages for the upper 40% (high frequencies)
        start = 0
        end = int(height * 0.4)
        row_avgs: list[float] = []
        for y in range(start, end):
            row_sum = sum(img.getpixel((x, y)) for x in range(width))
            row_avgs.append(row_sum / width)

        if len(row_avgs) < 3:
            return None

        # Compute derivatives (differences between consecutive rows)
        derivatives = [
            abs(row_avgs[i + 1] - row_avgs[i]) for i in range(len(row_avgs) - 1)
        ]

        if not derivatives:
            return None

        max_derivative = max(derivatives)
        avg_derivative = sum(derivatives) / len(derivatives)

        if avg_derivative == 0:
            return 0.0

        # High ratio of max to average indicates sharp cutoff
        sharpness = min(1.0, max_derivative / (avg_derivative * 10))
        return round(sharpness, 4)
    except Exception as exc:
        logger.debug("Rolloff smoothness computation failed: %s", exc)
        return None


def extract_spectrogram_features(
    file_path: Path,
    work_dir: Path | None = None,
) -> dict[str, Any]:
    """Extract all spectrogram-based features for a single audio file.

    Generates a temporary raw spectrogram and analyzes it for cutoff
    frequency, HF energy ratio, gap detection, and rolloff smoothness.

    Args:
        file_path: Path to an audio file.
        work_dir: Working directory for temp files. Uses system temp if None.

    Returns:
        Dictionary with keys: cutoff_freq, hf_energy_ratio,
        spectrogram_gap_detected, hf_rolloff_smoothness.
    """
    result: dict[str, Any] = {
        "cutoff_freq": None,
        "hf_energy_ratio": None,
        "spectrogram_gap_detected": False,
        "hf_rolloff_smoothness": None,
    }

    nyquist = get_audio_nyquist(file_path)

    if work_dir is None:
        tmp = Path(tempfile.mkdtemp())
    else:
        tmp = work_dir
        tmp.mkdir(parents=True, exist_ok=True)

    raw_img = tmp / f"_spec_raw_{file_path.stem}.png"

    try:
        if generate_raw_spectrogram(file_path, raw_img):
            result["cutoff_freq"] = analyze_spectrogram_cutoff(raw_img, nyquist)
            result["hf_energy_ratio"] = compute_hf_energy_ratio(raw_img, nyquist)
            result["spectrogram_gap_detected"] = detect_spectrogram_gap(raw_img, nyquist)
            result["hf_rolloff_smoothness"] = compute_hf_rolloff_smoothness(raw_img, nyquist)
    finally:
        if raw_img.exists():
            try:
                raw_img.unlink()
            except OSError:
                pass

    return result
