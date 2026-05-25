"""
Central data models for the quality audit system.

All dataclasses used across the quality package are defined here to avoid
circular imports and provide a single source of truth for data structures.
Every model supports JSON serialization via to_dict() / to_json().
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RiskLevel(str, Enum):
    """Risk classification levels, from safest to most dangerous."""

    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH_RISK = "HIGH_RISK"
    LIKELY_TRANSCODE = "LIKELY_TRANSCODE"


class Severity(str, Enum):
    """Rule result severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Confidence(str, Enum):
    """Log analysis confidence levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LogType(str, Enum):
    """Supported ripping log types."""

    EAC = "EAC"
    XLD = "XLD"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Audio Feature Extraction Results
# ---------------------------------------------------------------------------


@dataclass
class AudioFeatures:
    """Extracted audio features for risk analysis.

    Computed once by FeatureExtractor and shared across all rules.
    Rules must NOT perform their own heavy analysis — they consume
    pre-computed features from this structure only.
    """

    cutoff_freq: float | None = None
    """Detected high-frequency cutoff in Hz (e.g., 16000.0 for MP3 source)."""

    hf_energy_ratio: float | None = None
    """Ratio of energy above 16kHz to total energy (0.0–1.0)."""

    spectrogram_gap_detected: bool = False
    """Whether a visible gap or shelf was detected in the spectrogram."""

    channel_similarity: float | None = None
    """Cosine similarity between L/R channels (0.0–1.0, 1.0 = identical)."""

    fake_hires_score: float | None = None
    """Composite score indicating likelihood of fake Hi-Res (0.0–1.0)."""

    mp3_signature_score: float | None = None
    """Composite score indicating MP3 transcode artifacts (0.0–1.0)."""

    hf_rolloff_smoothness: float | None = None
    """Smoothness of high-frequency rolloff (0.0–1.0, 1.0 = perfectly smooth)."""

    avg_bitrate_kbps: float | None = None
    """Average bitrate in kbps."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Log Analysis
# ---------------------------------------------------------------------------


@dataclass
class LogAnalysis:
    """Result of parsing a ripping log (EAC or XLD).

    Attributes:
        log_type: Detected log type ("EAC", "XLD", "UNKNOWN").
        score: Numeric score from 0–100, where 100 is perfect.
        confidence: Assessment confidence ("LOW", "MEDIUM", "HIGH").
        issues: Human-readable list of problems found.
        flags: Structured boolean flags for programmatic access.
        metadata: Additional extracted metadata (drive, software version, etc.).
    """

    log_type: str = "UNKNOWN"
    score: int = 0
    confidence: str = "LOW"
    issues: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Risk Assessment
# ---------------------------------------------------------------------------


@dataclass
class RuleResult:
    """Result from a single risk rule evaluation.

    Attributes:
        rule_name: Machine-readable rule identifier (e.g., 'cutoff_22khz').
        score_delta: Points added to the raw risk score (positive = riskier).
        reason: Human-readable explanation of why this rule triggered.
        severity: One of 'info', 'warning', 'critical'.
        metadata: Rule-specific diagnostic data for debugging.
    """

    rule_name: str
    score_delta: int
    reason: str
    severity: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)


@dataclass
class RiskReport:
    """Aggregated risk assessment report.

    The final output of the risk scoring engine after evaluating all
    enabled rules against an AudioContext.
    """

    score: int = 0
    """Normalized risk score (0–100)."""

    level: str = "SAFE"
    """Risk level classification."""

    reasons: list[str] = field(default_factory=list)
    """Aggregated human-readable reasons."""

    suggestions: list[str] = field(default_factory=list)
    """Recommended actions based on risk level."""

    rule_results: list[RuleResult] = field(default_factory=list)
    """Detailed per-rule results for inspection."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "score": self.score,
            "level": self.level,
            "reasons": self.reasons,
            "suggestions": self.suggestions,
            "rule_results": [r.to_dict() for r in self.rule_results],
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Audio Context (input to rules)
# ---------------------------------------------------------------------------


def _path_serializer(obj: Any) -> Any:
    """JSON serialization helper for Path objects."""
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@dataclass
class AudioContext:
    """All available information about a release, passed to risk rules.

    This is the single source of truth for rule evaluation. It is built
    from multiple sources (file system, log parsing, spectrogram analysis)
    before being fed into the risk engine.
    """

    album_dir: Path | None = None
    format: str | None = None
    source: str | None = None
    bitrate: str | None = None
    bit_depth: int | None = None
    sample_rate: int | None = None
    has_log: bool = False
    has_cue: bool = False
    log_content: str | None = None
    log_analysis: LogAnalysis | None = None
    spectrogram_path: Path | None = None
    features: AudioFeatures = field(default_factory=AudioFeatures)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary with Path objects converted to strings."""
        result: dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Path):
                result[k] = str(v)
            elif isinstance(v, (AudioFeatures, LogAnalysis)):
                result[k] = v.to_dict()
            else:
                result[k] = v
        return result

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Torrent / Dedup
# ---------------------------------------------------------------------------


@dataclass
class TorrentInfo:
    """Information about an existing torrent for dedup comparison.

    Mirrors the data available from RED/OPS API search results.
    """

    artist: str = ""
    album: str = ""
    year: int = 0
    format: str = ""
    bitrate: str = ""
    source: str = ""
    has_log: bool = False
    log_score: int | None = None
    bit_depth: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class DuplicateCheckResult:
    """Result of duplicate and trump detection.

    Used to determine if a release should be uploaded or if a better
    version already exists on the tracker.
    """

    exists: bool = False
    better_version_exists: bool = False
    possible_trump_reason: list[str] = field(default_factory=list)
    matched_torrents: list[TorrentInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "exists": self.exists,
            "better_version_exists": self.better_version_exists,
            "possible_trump_reason": self.possible_trump_reason,
            "matched_torrents": [t.to_dict() for t in self.matched_torrents],
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
