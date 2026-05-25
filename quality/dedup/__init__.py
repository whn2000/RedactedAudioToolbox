"""
Duplicate detection and trump checking.

Provides comparison engines and data providers for checking if a
release already exists on the tracker or could be trumped.
"""

from quality.dedup.engine import DuplicateChecker

__all__ = ["DuplicateChecker"]
