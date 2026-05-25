"""
Duplicate checking engine.

Orchestrates providers and comparators to determine if a release
already exists on the tracker and whether it could be trumped.
"""

from __future__ import annotations

import logging
from typing import Sequence

from quality.dedup.comparators import DEFAULT_COMPARATORS, BaseComparator
from quality.dedup.providers import BaseProvider, MockProvider
from quality.models import DuplicateCheckResult, TorrentInfo

logger = logging.getLogger(__name__)


class DuplicateChecker:
    """Checks for duplicate releases and potential trumps.

    Uses a data provider to search for existing releases and a set
    of comparators to evaluate whether the existing releases are
    better than the candidate.

    Args:
        provider: Data provider for searching existing releases.
        comparators: List of comparators for quality evaluation.
            Defaults to all built-in comparators.

    Usage::

        checker = DuplicateChecker(MockProvider())
        candidate = TorrentInfo(artist="Radiohead", album="OK Computer", ...)
        result = checker.check(candidate)
        print(result.to_json())
    """

    def __init__(
        self,
        provider: BaseProvider | None = None,
        comparators: Sequence[BaseComparator] | None = None,
    ) -> None:
        self._provider = provider or MockProvider()
        self._comparators = list(comparators or DEFAULT_COMPARATORS)

    @property
    def provider(self) -> BaseProvider:
        """Return the current data provider."""
        return self._provider

    def check(self, candidate: TorrentInfo) -> DuplicateCheckResult:
        """Check if a candidate release is a duplicate or could be trumped.

        Args:
            candidate: The release being considered for upload.

        Returns:
            DuplicateCheckResult with exists, better_version_exists,
            trump reasons, and matched torrents.
        """
        existing = self._provider.search(candidate.artist, candidate.album)

        if not existing:
            logger.info(
                "No existing releases found for '%s - %s'",
                candidate.artist, candidate.album,
            )
            return DuplicateCheckResult(
                exists=False,
                better_version_exists=False,
            )

        logger.info(
            "Found %d existing releases for '%s - %s'",
            len(existing), candidate.artist, candidate.album,
        )

        # Check for exact format/source match (true duplicate)
        exact_match = self._find_exact_match(candidate, existing)

        # Check for better versions
        trump_reasons: list[str] = []
        for ex in existing:
            for comp in self._comparators:
                reason = comp.compare(candidate, ex)
                if reason and reason not in trump_reasons:
                    trump_reasons.append(reason)

        better_exists = len(trump_reasons) > 0

        return DuplicateCheckResult(
            exists=exact_match is not None or len(existing) > 0,
            better_version_exists=better_exists,
            possible_trump_reason=trump_reasons,
            matched_torrents=existing,
        )

    @staticmethod
    def _find_exact_match(
        candidate: TorrentInfo,
        existing: list[TorrentInfo],
    ) -> TorrentInfo | None:
        """Find an exact format/source match.

        Args:
            candidate: Candidate release.
            existing: List of existing releases.

        Returns:
            First matching TorrentInfo, or None.
        """
        for ex in existing:
            if (
                ex.format.upper() == candidate.format.upper()
                and ex.source.upper() == candidate.source.upper()
                and ex.bitrate.upper() == candidate.bitrate.upper()
            ):
                return ex
        return None
