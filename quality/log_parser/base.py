"""
Base class for ripping log parsers.

Defines the pluggable parser interface. Each parser must implement
can_parse() for type detection and parse() for analysis.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from quality.models import LogAnalysis


class BaseLogParser(ABC):
    """Abstract base class for ripping log parsers.

    Implementations must handle:
    - Detection: can this parser handle the given log content?
    - Parsing: extract score, flags, issues, and metadata.

    Parsers should be tolerant of encoding variations (UTF-8, UTF-16,
    CRLF/LF) — the detector normalizes content before passing it.
    """

    @abstractmethod
    def can_parse(self, content: str) -> bool:
        """Determine if this parser can handle the given log content.

        Args:
            content: Normalized (UTF-8, LF) log text.

        Returns:
            True if this parser recognizes the log format.
        """

    @abstractmethod
    def parse(self, content: str) -> LogAnalysis:
        """Parse the log content and produce an analysis.

        Args:
            content: Normalized log text.

        Returns:
            Fully populated LogAnalysis with score, flags, issues,
            and metadata.
        """

    @property
    @abstractmethod
    def parser_name(self) -> str:
        """Return the parser name (e.g., 'EAC', 'XLD')."""
