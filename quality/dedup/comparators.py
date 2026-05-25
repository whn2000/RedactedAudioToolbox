"""
Comparison strategies for duplicate and trump detection.

Provides pluggable comparators that evaluate different dimensions of
release quality (format, bitrate, source, log, bit depth). Each
comparator returns a trump reason if the existing release is better.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from quality.models import TorrentInfo

logger = logging.getLogger(__name__)


class BaseComparator(ABC):
    """Abstract base class for release comparators.

    Each comparator checks one dimension of quality and returns
    a trump reason if the existing release is superior.
    """

    @abstractmethod
    def compare(
        self, candidate: TorrentInfo, existing: TorrentInfo
    ) -> str | None:
        """Compare a candidate release against an existing one.

        Args:
            candidate: The release being considered for upload.
            existing: An existing release on the tracker.

        Returns:
            A trump reason string if the existing release is better,
            or None if the candidate is equal or better.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the comparator name."""


# Format quality priority (higher = better)
_FORMAT_PRIORITY: dict[str, int] = {
    "FLAC": 100,
    "ALAC": 95,
    "WAV": 90,
    "APE": 85,
    "WV": 80,
    "MP3": 50,
    "AAC": 45,
    "OGG": 40,
    "OPUS": 40,
}

# Source quality priority (higher = better)
_SOURCE_PRIORITY: dict[str, int] = {
    "CD": 100,
    "WEB": 90,
    "VINYL": 85,
    "SACD": 80,
    "DVD": 75,
    "BLU-RAY": 75,
    "SOUNDBOARD": 60,
    "DAT": 55,
    "CASSETTE": 40,
}


class FormatComparator(BaseComparator):
    """Compare releases by audio format quality."""

    @property
    def name(self) -> str:
        return "format"

    def compare(
        self, candidate: TorrentInfo, existing: TorrentInfo
    ) -> str | None:
        """Check if existing release has a better format."""
        cand_priority = _FORMAT_PRIORITY.get(candidate.format.upper(), 0)
        exist_priority = _FORMAT_PRIORITY.get(existing.format.upper(), 0)

        if exist_priority > cand_priority:
            return (
                f"Existing release has better format: "
                f"{existing.format} > {candidate.format}"
            )
        return None


class BitrateComparator(BaseComparator):
    """Compare releases by bitrate."""

    @property
    def name(self) -> str:
        return "bitrate"

    def compare(
        self, candidate: TorrentInfo, existing: TorrentInfo
    ) -> str | None:
        """Check if existing release has better bitrate.

        For lossless formats, '24bit Lossless' > 'Lossless'.
        For lossy formats, higher numeric bitrate is better.
        """
        cand_br = candidate.bitrate.upper()
        exist_br = existing.bitrate.upper()

        # Same format family check
        if candidate.format.upper() != existing.format.upper():
            return None

        # Lossless comparison
        if "24BIT" in exist_br and "24BIT" not in cand_br:
            return "Existing release is 24-bit lossless (higher resolution)"

        # Numeric bitrate comparison for lossy
        cand_num = self._extract_bitrate_num(cand_br)
        exist_num = self._extract_bitrate_num(exist_br)

        if cand_num is not None and exist_num is not None:
            if exist_num > cand_num:
                return f"Existing release has higher bitrate: {existing.bitrate} > {candidate.bitrate}"

        return None

    @staticmethod
    def _extract_bitrate_num(bitrate: str) -> int | None:
        """Extract numeric bitrate value."""
        import re
        match = re.search(r"(\d+)", bitrate)
        return int(match.group(1)) if match else None


class SourceComparator(BaseComparator):
    """Compare releases by source quality."""

    @property
    def name(self) -> str:
        return "source"

    def compare(
        self, candidate: TorrentInfo, existing: TorrentInfo
    ) -> str | None:
        """Check if existing release has a better source."""
        cand_priority = _SOURCE_PRIORITY.get(candidate.source.upper(), 0)
        exist_priority = _SOURCE_PRIORITY.get(existing.source.upper(), 0)

        if exist_priority > cand_priority:
            return (
                f"Existing release has better source: "
                f"{existing.source} > {candidate.source}"
            )
        return None


class LogComparator(BaseComparator):
    """Compare releases by log presence and score."""

    @property
    def name(self) -> str:
        return "log"

    def compare(
        self, candidate: TorrentInfo, existing: TorrentInfo
    ) -> str | None:
        """Check if existing release has a better log."""
        if not candidate.has_log and existing.has_log:
            score_info = ""
            if existing.log_score is not None:
                score_info = f" (score: {existing.log_score})"
            return f"Existing release includes AccurateRip verified log{score_info}"

        if (
            candidate.has_log
            and existing.has_log
            and candidate.log_score is not None
            and existing.log_score is not None
        ):
            if existing.log_score > candidate.log_score:
                return (
                    f"Existing release has higher log score: "
                    f"{existing.log_score} > {candidate.log_score}"
                )

        return None


class BitDepthComparator(BaseComparator):
    """Compare releases by bit depth."""

    @property
    def name(self) -> str:
        return "bit_depth"

    def compare(
        self, candidate: TorrentInfo, existing: TorrentInfo
    ) -> str | None:
        """Check if existing release has better bit depth."""
        if candidate.bit_depth is None or existing.bit_depth is None:
            return None

        if existing.bit_depth > candidate.bit_depth:
            return f"Existing release is true {existing.bit_depth}bit source"

        return None


# Default comparator list
DEFAULT_COMPARATORS: list[BaseComparator] = [
    FormatComparator(),
    BitrateComparator(),
    SourceComparator(),
    LogComparator(),
    BitDepthComparator(),
]
