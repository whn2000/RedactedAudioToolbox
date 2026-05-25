"""
Configuration management for the quality audit system.

Provides a typed QualityConfig dataclass that can be loaded from a JSON file,
constructed from a dictionary, or instantiated with sensible defaults.
All subsystems read their configuration from this central object.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QualityConfig:
    """Central configuration for all quality audit subsystems.

    Configuration is organized by subsystem with flat attribute names
    using a ``subsystem_setting`` naming convention for simplicity.
    Use ``from_file()`` or ``from_dict()`` to load from external sources.
    """

    # -- Risk Engine ----------------------------------------------------------
    risk_max_raw_score: int = 200
    """Maximum possible raw score before normalization to 0–100."""

    risk_thresholds: dict[str, int] = field(default_factory=lambda: {
        "SAFE": 15,
        "LOW_RISK": 35,
        "SUSPICIOUS": 55,
        "HIGH_RISK": 80,
    })
    """Upper bounds for each risk level (score <= threshold → level)."""

    risk_disabled_rules: list[str] = field(default_factory=list)
    """List of rule names to disable (e.g., ['web_source_trusted'])."""

    risk_rule_weights: dict[str, float] = field(default_factory=dict)
    """Per-rule weight overrides (rule_name → weight, default 1.0)."""

    # -- Log Parser -----------------------------------------------------------
    log_parser_default_score: int = 100
    """Starting score for log analysis (deductions are subtracted)."""

    log_parser_encodings: list[str] = field(default_factory=lambda: [
        "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1",
    ])
    """Ordered list of encodings to try when reading log files."""

    # -- Dedup ----------------------------------------------------------------
    dedup_provider: str = "mock"
    """Data provider for duplicate checking ('mock' or 'red_api')."""

    # -- Description ----------------------------------------------------------
    description_template: str = "default"
    """Template name for BBCode description generation."""

    description_include_risk_notice: bool = True
    """Whether to include risk warnings in generated descriptions."""

    description_include_spectrogram: bool = True
    """Whether to include spectrogram references in descriptions."""

    # -- Cache ----------------------------------------------------------------
    cache_enabled: bool = True
    """Whether feature caching is enabled."""

    cache_directory: str = ".quality_cache"
    """Directory for cached feature data (relative to album dir)."""

    cache_ttl_seconds: int = 86400
    """Cache time-to-live in seconds (default: 24 hours)."""

    # -- Factory Methods ------------------------------------------------------

    @classmethod
    def from_file(cls, path: Path) -> QualityConfig:
        """Load configuration from a JSON file.

        Args:
            path: Path to a JSON configuration file.

        Returns:
            A QualityConfig instance. Falls back to defaults on any error.
        """
        if not path.exists():
            logger.info("Config file not found at %s, using defaults", path)
            return cls()

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning(
                "Failed to parse config file %s: %s — using defaults", path, exc
            )
            return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityConfig:
        """Create a QualityConfig from a nested dictionary.

        The expected top-level keys are: ``risk``, ``log_parser``, ``dedup``,
        ``description``, ``cache``. Missing keys fall back to defaults.

        Args:
            data: Nested configuration dictionary.

        Returns:
            A QualityConfig instance.
        """
        risk = data.get("risk", {})
        log_p = data.get("log_parser", {})
        dedup = data.get("dedup", {})
        desc = data.get("description", {})
        cache = data.get("cache", {})

        defaults = cls()

        return cls(
            risk_max_raw_score=risk.get("max_raw_score", defaults.risk_max_raw_score),
            risk_thresholds=risk.get("thresholds", defaults.risk_thresholds),
            risk_disabled_rules=risk.get("disabled_rules", defaults.risk_disabled_rules),
            risk_rule_weights=risk.get("rule_weights", defaults.risk_rule_weights),
            log_parser_default_score=log_p.get(
                "default_score", defaults.log_parser_default_score
            ),
            log_parser_encodings=log_p.get(
                "supported_encodings", defaults.log_parser_encodings
            ),
            dedup_provider=dedup.get("provider", defaults.dedup_provider),
            description_template=desc.get("template", defaults.description_template),
            description_include_risk_notice=desc.get(
                "include_risk_notice", defaults.description_include_risk_notice
            ),
            description_include_spectrogram=desc.get(
                "include_spectrogram", defaults.description_include_spectrogram
            ),
            cache_enabled=cache.get("enabled", defaults.cache_enabled),
            cache_directory=cache.get("directory", defaults.cache_directory),
            cache_ttl_seconds=cache.get("ttl_seconds", defaults.cache_ttl_seconds),
        )

    # -- Serialization --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a nested dictionary matching the expected JSON layout."""
        return {
            "risk": {
                "max_raw_score": self.risk_max_raw_score,
                "thresholds": self.risk_thresholds,
                "disabled_rules": self.risk_disabled_rules,
                "rule_weights": self.risk_rule_weights,
            },
            "log_parser": {
                "default_score": self.log_parser_default_score,
                "supported_encodings": self.log_parser_encodings,
            },
            "dedup": {
                "provider": self.dedup_provider,
            },
            "description": {
                "template": self.description_template,
                "include_risk_notice": self.description_include_risk_notice,
                "include_spectrogram": self.description_include_spectrogram,
            },
            "cache": {
                "enabled": self.cache_enabled,
                "directory": self.cache_directory,
                "ttl_seconds": self.cache_ttl_seconds,
            },
        }

    def to_json(self) -> str:
        """Serialize to a formatted JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def save(self, path: Path) -> None:
        """Save configuration to a JSON file.

        Args:
            path: Destination file path. Parent directories are created.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        logger.info("Configuration saved to %s", path)
