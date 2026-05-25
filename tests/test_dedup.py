"""
Tests for the duplicate checking system.

Tests provider search, comparator logic, trump detection,
and edge cases.
"""

from __future__ import annotations

import json

import pytest

from quality.dedup.comparators import (
    BitDepthComparator,
    BitrateComparator,
    FormatComparator,
    LogComparator,
    SourceComparator,
)
from quality.dedup.engine import DuplicateChecker
from quality.dedup.providers import MockProvider, RedAPIProvider
from quality.models import TorrentInfo


class TestMockProvider:
    """Test the mock data provider."""

    def test_find_radiohead(self) -> None:
        """Should find Radiohead releases."""
        provider = MockProvider()
        results = provider.search("Radiohead", "OK Computer")
        assert len(results) >= 2

    def test_find_pink_floyd(self) -> None:
        """Should find Pink Floyd releases."""
        provider = MockProvider()
        results = provider.search("Pink Floyd", "The Dark Side of the Moon")
        assert len(results) >= 1

    def test_case_insensitive(self) -> None:
        """Search should be case-insensitive."""
        provider = MockProvider()
        r1 = provider.search("radiohead", "ok computer")
        r2 = provider.search("RADIOHEAD", "OK COMPUTER")
        assert len(r1) == len(r2)

    def test_not_found(self) -> None:
        """Non-existent releases should return empty list."""
        provider = MockProvider()
        results = provider.search("Nonexistent Artist", "Nonexistent Album")
        assert len(results) == 0

    def test_add_torrent(self) -> None:
        """Should be able to add custom torrents."""
        provider = MockProvider()
        custom = TorrentInfo(
            artist="Test", album="Album", year=2024,
            format="FLAC", bitrate="Lossless", source="WEB",
            has_log=False,
        )
        provider.add_torrent(custom)
        results = provider.search("Test", "Album")
        assert len(results) == 1

    def test_provider_name(self) -> None:
        assert MockProvider().provider_name == "mock"


class TestRedAPIProvider:
    """Test the RED API provider stub."""

    def test_returns_empty(self) -> None:
        """Stub should return empty results."""
        provider = RedAPIProvider()
        results = provider.search("Any", "Any")
        assert len(results) == 0

    def test_provider_name(self) -> None:
        assert RedAPIProvider().provider_name == "red_api"


class TestComparators:
    """Test individual comparators."""

    def test_format_better_existing(self) -> None:
        """FLAC existing should trump MP3 candidate."""
        comp = FormatComparator()
        candidate = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="MP3", bitrate="320", source="CD", has_log=True,
        )
        existing = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="Lossless", source="CD", has_log=True,
        )
        reason = comp.compare(candidate, existing)
        assert reason is not None
        assert "FLAC" in reason

    def test_format_equal(self) -> None:
        """Same format should not trump."""
        comp = FormatComparator()
        t = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="Lossless", source="CD", has_log=True,
        )
        assert comp.compare(t, t) is None

    def test_bitrate_24bit_trumps_16bit(self) -> None:
        """24-bit lossless should trump 16-bit lossless."""
        comp = BitrateComparator()
        candidate = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="Lossless", source="WEB", has_log=False,
        )
        existing = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="24bit Lossless", source="WEB", has_log=False,
        )
        reason = comp.compare(candidate, existing)
        assert reason is not None
        assert "24-bit" in reason

    def test_source_cd_trumps_cassette(self) -> None:
        """CD should trump Cassette."""
        comp = SourceComparator()
        candidate = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="Lossless", source="CASSETTE", has_log=False,
        )
        existing = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="Lossless", source="CD", has_log=True,
        )
        reason = comp.compare(candidate, existing)
        assert reason is not None

    def test_log_presence_trumps(self) -> None:
        """Existing with log trumps candidate without."""
        comp = LogComparator()
        candidate = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="Lossless", source="CD", has_log=False,
        )
        existing = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="Lossless", source="CD",
            has_log=True, log_score=100,
        )
        reason = comp.compare(candidate, existing)
        assert reason is not None
        assert "log" in reason.lower()

    def test_bit_depth_comparison(self) -> None:
        """Higher bit depth existing should trump."""
        comp = BitDepthComparator()
        candidate = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="Lossless", source="WEB",
            has_log=False, bit_depth=16,
        )
        existing = TorrentInfo(
            artist="X", album="Y", year=2020,
            format="FLAC", bitrate="24bit Lossless", source="WEB",
            has_log=False, bit_depth=24,
        )
        reason = comp.compare(candidate, existing)
        assert reason is not None
        assert "24bit" in reason


class TestDuplicateChecker:
    """Test the duplicate checker engine."""

    def test_existing_found(self) -> None:
        """Should detect existing releases."""
        checker = DuplicateChecker(MockProvider())
        candidate = TorrentInfo(
            artist="Radiohead", album="OK Computer", year=1997,
            format="MP3", bitrate="320", source="CD", has_log=True,
        )
        result = checker.check(candidate)
        assert result.exists is True
        assert len(result.matched_torrents) > 0

    def test_better_version_exists(self) -> None:
        """Should detect better versions (FLAC > MP3)."""
        checker = DuplicateChecker(MockProvider())
        candidate = TorrentInfo(
            artist="Radiohead", album="OK Computer", year=1997,
            format="MP3", bitrate="V0", source="CD", has_log=True,
        )
        result = checker.check(candidate)
        assert result.better_version_exists is True
        assert len(result.possible_trump_reason) > 0

    def test_not_found(self) -> None:
        """Non-existent releases should not be found."""
        checker = DuplicateChecker(MockProvider())
        candidate = TorrentInfo(
            artist="Unknown", album="Unknown", year=2024,
            format="FLAC", bitrate="Lossless", source="WEB", has_log=False,
        )
        result = checker.check(candidate)
        assert result.exists is False
        assert result.better_version_exists is False

    def test_json_output(self) -> None:
        """Result should serialize to valid JSON."""
        checker = DuplicateChecker(MockProvider())
        candidate = TorrentInfo(
            artist="Radiohead", album="OK Computer", year=1997,
            format="FLAC", bitrate="Lossless", source="CD", has_log=True,
        )
        result = checker.check(candidate)
        parsed = json.loads(result.to_json())
        assert "exists" in parsed
        assert "possible_trump_reason" in parsed
