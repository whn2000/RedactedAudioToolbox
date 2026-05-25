"""
Data providers for duplicate checking.

Defines the BaseProvider interface and implementations:
- MockProvider: In-memory test data for development and testing.
- RedAPIProvider: Stub for future RED API integration.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from quality.models import TorrentInfo

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """Abstract base class for torrent data providers.

    Providers search a data source (mock, API, database) for existing
    releases matching the given artist/album criteria.
    """

    @abstractmethod
    def search(self, artist: str, album: str) -> list[TorrentInfo]:
        """Search for existing releases by artist and album.

        Args:
            artist: Artist name (case-insensitive matching).
            album: Album title (case-insensitive matching).

        Returns:
            List of matching TorrentInfo objects.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier."""


class MockProvider(BaseProvider):
    """In-memory mock provider for testing and development.

    Pre-populated with a realistic set of releases to test duplicate
    detection and trump logic.
    """

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "mock"

    def __init__(self) -> None:
        self._data: list[TorrentInfo] = self._build_mock_data()

    def search(self, artist: str, album: str) -> list[TorrentInfo]:
        """Search mock data by artist and album.

        Uses case-insensitive substring matching.
        """
        artist_lower = artist.lower().strip()
        album_lower = album.lower().strip()

        results = [
            t for t in self._data
            if artist_lower in t.artist.lower()
            and album_lower in t.album.lower()
        ]

        logger.debug(
            "MockProvider: searched '%s - %s', found %d results",
            artist, album, len(results),
        )
        return results

    def add_torrent(self, torrent: TorrentInfo) -> None:
        """Add a torrent to the mock dataset.

        Args:
            torrent: TorrentInfo to add.
        """
        self._data.append(torrent)

    @staticmethod
    def _build_mock_data() -> list[TorrentInfo]:
        """Build the default mock dataset."""
        return [
            TorrentInfo(
                artist="Radiohead",
                album="OK Computer",
                year=1997,
                format="FLAC",
                bitrate="Lossless",
                source="CD",
                has_log=True,
                log_score=100,
                bit_depth=16,
            ),
            TorrentInfo(
                artist="Radiohead",
                album="OK Computer",
                year=1997,
                format="FLAC",
                bitrate="24bit Lossless",
                source="WEB",
                has_log=False,
                log_score=None,
                bit_depth=24,
            ),
            TorrentInfo(
                artist="Radiohead",
                album="OK Computer",
                year=1997,
                format="MP3",
                bitrate="320",
                source="CD",
                has_log=True,
                log_score=95,
                bit_depth=None,
            ),
            TorrentInfo(
                artist="Pink Floyd",
                album="The Dark Side of the Moon",
                year=1973,
                format="FLAC",
                bitrate="Lossless",
                source="CD",
                has_log=True,
                log_score=100,
                bit_depth=16,
            ),
            TorrentInfo(
                artist="Pink Floyd",
                album="The Dark Side of the Moon",
                year=2011,
                format="FLAC",
                bitrate="24bit Lossless",
                source="WEB",
                has_log=False,
                log_score=None,
                bit_depth=24,
            ),
            TorrentInfo(
                artist="Daft Punk",
                album="Random Access Memories",
                year=2013,
                format="FLAC",
                bitrate="Lossless",
                source="WEB",
                has_log=False,
                log_score=None,
                bit_depth=16,
            ),
            TorrentInfo(
                artist="Daft Punk",
                album="Random Access Memories",
                year=2013,
                format="FLAC",
                bitrate="24bit Lossless",
                source="WEB",
                has_log=False,
                log_score=None,
                bit_depth=24,
            ),
        ]


class RedAPIProvider(BaseProvider):
    """Stub provider for RED API integration.

    This provider is designed to be connected to the real RED/OPS
    API in the future. Currently returns empty results with a log
    warning.

    Args:
        api_key: RED API key.
        base_url: API base URL.
    """

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "red_api"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://redacted.sh/ajax.php",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url

    def search(self, artist: str, album: str) -> list[TorrentInfo]:
        """Search RED API for existing releases.

        Currently a stub — returns empty results. Will be implemented
        when API integration is added.
        """
        logger.warning(
            "RedAPIProvider is a stub — returning empty results for '%s - %s'. "
            "Implement API integration to enable real searches.",
            artist, album,
        )
        return []
