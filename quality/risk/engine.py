"""
Risk scoring engine.

Orchestrates rule evaluation, score normalization, and level classification.
The engine loads rules from the registry, applies configuration (enable/disable,
weights), evaluates all active rules against an AudioContext, and produces
a normalized RiskReport.

Score normalization:
    raw_score = sum(rule.score_delta * rule.weight for each triggered rule)
    normalized = clamp(raw_score * 100 / max_raw_score, 0, 100)

Level thresholds (configurable):
    0–15   → SAFE
    16–35  → LOW_RISK
    36–55  → SUSPICIOUS
    56–80  → HIGH_RISK
    81–100 → LIKELY_TRANSCODE
"""

from __future__ import annotations

import logging
from typing import Any

from quality.config import QualityConfig
from quality.models import AudioContext, RiskLevel, RiskReport, RuleResult
from quality.risk.base import BaseRule
from quality.risk.registry import discover_rules

logger = logging.getLogger(__name__)

# Default level thresholds (upper bound for each level)
_DEFAULT_THRESHOLDS: dict[str, int] = {
    "SAFE": 15,
    "LOW_RISK": 35,
    "SUSPICIOUS": 55,
    "HIGH_RISK": 80,
}

# Suggestions mapped to risk levels
_LEVEL_SUGGESTIONS: dict[str, list[str]] = {
    RiskLevel.SAFE.value: [
        "Release appears clean — safe to upload.",
    ],
    RiskLevel.LOW_RISK.value: [
        "Minor concerns detected — review before uploading.",
    ],
    RiskLevel.SUSPICIOUS.value: [
        "Multiple quality concerns — manual review recommended.",
        "Check spectrogram and log carefully before uploading.",
    ],
    RiskLevel.HIGH_RISK.value: [
        "Significant quality issues detected — manual review required.",
        "Do not auto-upload without human verification.",
    ],
    RiskLevel.LIKELY_TRANSCODE.value: [
        "Strong evidence of lossy source or transcode — do NOT upload.",
        "This release will likely be reported and removed.",
    ],
}


class RiskEngine:
    """Plugin-based risk scoring engine.

    Discovers rules from the registry, applies configuration overrides,
    and evaluates all enabled rules against a given AudioContext.

    Args:
        config: Optional QualityConfig for threshold and rule overrides.

    Usage::

        engine = RiskEngine()
        report = engine.evaluate(audio_context)
        print(report.to_json())
    """

    def __init__(self, config: QualityConfig | None = None) -> None:
        self._config = config or QualityConfig()
        self._rules: list[BaseRule] = []
        self._load_rules()

    @property
    def rules(self) -> list[BaseRule]:
        """Return the list of loaded rules (read-only)."""
        return list(self._rules)

    def _load_rules(self) -> None:
        """Discover rules and apply configuration overrides."""
        self._rules = discover_rules()

        disabled = set(self._config.risk_disabled_rules)
        weights = self._config.risk_rule_weights

        for rule in self._rules:
            if rule.name in disabled:
                rule.enabled = False
                logger.debug("Rule '%s' disabled by config", rule.name)

            if rule.name in weights:
                rule.weight = weights[rule.name]
                logger.debug("Rule '%s' weight set to %.2f", rule.name, rule.weight)

        active = sum(1 for r in self._rules if r.enabled)
        logger.info(
            "Risk engine loaded: %d rules (%d active, %d disabled)",
            len(self._rules), active, len(self._rules) - active,
        )

    def evaluate(self, ctx: AudioContext) -> RiskReport:
        """Evaluate all enabled rules against the given context.

        Args:
            ctx: Complete audio context with pre-computed features.

        Returns:
            A RiskReport with normalized score, level, reasons,
            suggestions, and detailed per-rule results.
        """
        results: list[RuleResult] = []
        raw_score = 0.0

        for rule in self._rules:
            if not rule.enabled:
                continue

            try:
                result = rule.evaluate(ctx)
                if result is not None:
                    weighted_delta = result.score_delta * rule.weight
                    raw_score += weighted_delta
                    results.append(result)
                    logger.debug(
                        "Rule '%s' triggered: delta=%d (weighted=%.1f), severity=%s",
                        rule.name, result.score_delta, weighted_delta, result.severity,
                    )
            except Exception as exc:
                logger.error("Rule '%s' raised an exception: %s", rule.name, exc)

        # Normalize score to 0–100
        max_raw = self._config.risk_max_raw_score
        if max_raw <= 0:
            max_raw = 200

        normalized = int(round(raw_score * 100 / max_raw))
        normalized = max(0, min(100, normalized))

        # Classify level
        level = self._classify_level(normalized)

        # Aggregate reasons
        reasons = [r.reason for r in results if r.score_delta > 0]

        # Get suggestions for this level
        suggestions = list(_LEVEL_SUGGESTIONS.get(level, []))

        report = RiskReport(
            score=normalized,
            level=level,
            reasons=reasons,
            suggestions=suggestions,
            rule_results=results,
        )

        logger.info(
            "Risk assessment: score=%d, level=%s, %d rules triggered",
            report.score, report.level, len(results),
        )
        return report

    def _classify_level(self, score: int) -> str:
        """Map a normalized score to a risk level.

        Args:
            score: Normalized score (0–100).

        Returns:
            Risk level string.
        """
        thresholds = self._config.risk_thresholds or _DEFAULT_THRESHOLDS

        if score <= thresholds.get("SAFE", 15):
            return RiskLevel.SAFE.value
        elif score <= thresholds.get("LOW_RISK", 35):
            return RiskLevel.LOW_RISK.value
        elif score <= thresholds.get("SUSPICIOUS", 55):
            return RiskLevel.SUSPICIOUS.value
        elif score <= thresholds.get("HIGH_RISK", 80):
            return RiskLevel.HIGH_RISK.value
        else:
            return RiskLevel.LIKELY_TRANSCODE.value
