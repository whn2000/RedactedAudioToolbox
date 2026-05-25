"""
RedactedAudioToolbox Quality Audit System.

A modular, plugin-based audio quality audit framework for Private Tracker
music releases. Provides risk scoring, log analysis, duplicate detection,
and upload description generation.

Modules:
    risk        - Plugin-based risk scoring engine
    log_parser  - EAC / XLD ripping log analysis
    dedup       - Duplicate and trump detection
    description - BBCode description generator
    features    - Audio feature extraction layer
    cache       - Feature caching system
"""

from quality.models import (
    AudioContext,
    AudioFeatures,
    DuplicateCheckResult,
    LogAnalysis,
    RiskReport,
    RuleResult,
    TorrentInfo,
)

__version__ = "1.0.0"
__all__ = [
    "AudioContext",
    "AudioFeatures",
    "DuplicateCheckResult",
    "LogAnalysis",
    "RiskReport",
    "RuleResult",
    "TorrentInfo",
]
