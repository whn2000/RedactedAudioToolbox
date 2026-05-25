"""
Log type auto-detection and dispatch.

Reads a log file with encoding auto-detection, normalizes line endings,
and dispatches to the appropriate parser (EAC or XLD).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from quality.log_parser.base import BaseLogParser
from quality.log_parser.eac_parser import EACParser
from quality.log_parser.xld_parser import XLDParser
from quality.models import LogAnalysis, LogType

logger = logging.getLogger(__name__)

# Default parsers, ordered by detection priority
_DEFAULT_PARSERS: list[type[BaseLogParser]] = [EACParser, XLDParser]

# Default encoding fallback chain
_DEFAULT_ENCODINGS: Sequence[str] = (
    "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1",
)


def read_log_file(
    path: Path,
    encodings: Sequence[str] | None = None,
) -> str:
    """Read a log file with automatic encoding detection.

    Tries each encoding in order until one succeeds. Normalizes
    line endings to LF (\\n).

    Args:
        path: Path to the log file.
        encodings: Ordered list of encodings to try.

    Returns:
        Normalized log content as a string.

    Raises:
        ValueError: If the file cannot be decoded with any encoding.
    """
    if encodings is None:
        encodings = _DEFAULT_ENCODINGS

    for enc in encodings:
        try:
            raw = path.read_text(encoding=enc)
            # Normalize CRLF → LF
            normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
            return normalized
        except (UnicodeDecodeError, UnicodeError):
            continue

    raise ValueError(
        f"Cannot decode log file '{path}' with any of: {', '.join(encodings)}"
    )


def detect_log_type(content: str) -> str:
    """Detect the log type from content.

    Args:
        content: Normalized log text.

    Returns:
        Log type string ("EAC", "XLD", or "UNKNOWN").
    """
    for parser_cls in _DEFAULT_PARSERS:
        parser = parser_cls()
        if parser.can_parse(content):
            return parser.parser_name

    return LogType.UNKNOWN.value


def detect_and_parse(
    content: str | None = None,
    path: Path | None = None,
    encodings: Sequence[str] | None = None,
) -> LogAnalysis:
    """Auto-detect log type and parse.

    Provide either ``content`` (already read) or ``path`` (will be read
    with encoding auto-detection). If both are provided, ``content``
    takes precedence.

    Args:
        content: Pre-read log text (normalized).
        path: Path to a log file.
        encodings: Encoding fallback chain for file reading.

    Returns:
        LogAnalysis with score, flags, issues, and metadata.
    """
    if content is None and path is None:
        return LogAnalysis(
            log_type=LogType.UNKNOWN.value,
            score=0,
            confidence="LOW",
            issues=["No log content or path provided"],
        )

    if content is None and path is not None:
        try:
            content = read_log_file(path, encodings)
        except ValueError as exc:
            return LogAnalysis(
                log_type=LogType.UNKNOWN.value,
                score=0,
                confidence="LOW",
                issues=[str(exc)],
            )

    assert content is not None

    for parser_cls in _DEFAULT_PARSERS:
        parser = parser_cls()
        if parser.can_parse(content):
            logger.info("Detected log type: %s", parser.parser_name)
            try:
                analysis = parser.parse(content)
                return analysis
            except Exception as exc:
                logger.error("Parser %s failed: %s", parser.parser_name, exc)
                return LogAnalysis(
                    log_type=parser.parser_name,
                    score=0,
                    confidence="LOW",
                    issues=[f"Parser error: {exc}"],
                )

    logger.warning("Unknown log format — no parser matched")
    return LogAnalysis(
        log_type=LogType.UNKNOWN.value,
        score=0,
        confidence="LOW",
        issues=["Unknown log format — could not identify as EAC or XLD"],
    )
