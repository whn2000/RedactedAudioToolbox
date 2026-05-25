"""
Tests for the risk scoring engine.

Tests rule discovery, score normalization, level classification,
configuration overrides, and JSON serialization.
"""

from __future__ import annotations

import json

import pytest

from quality.config import QualityConfig
from quality.models import AudioContext, AudioFeatures, LogAnalysis, RiskReport
from quality.risk.engine import RiskEngine


class TestRiskEngineDiscovery:
    """Test that the engine discovers rules correctly."""

    def test_discovers_all_builtin_rules(self) -> None:
        """Engine should discover all 10 built-in rules."""
        engine = RiskEngine()
        assert len(engine.rules) == 10

    def test_all_rules_have_names(self) -> None:
        """Every discovered rule must have a non-empty name."""
        engine = RiskEngine()
        for rule in engine.rules:
            assert rule.name, f"Rule {rule.__class__.__name__} has no name"

    def test_all_rules_have_descriptions(self) -> None:
        """Every discovered rule must have a description."""
        engine = RiskEngine()
        for rule in engine.rules:
            assert rule.description, f"Rule '{rule.name}' has no description"

    def test_rules_sorted_by_name(self) -> None:
        """Rules should be sorted alphabetically by name."""
        engine = RiskEngine()
        names = [r.name for r in engine.rules]
        assert names == sorted(names)

    def test_expected_rule_names(self) -> None:
        """Check that all expected rules are present."""
        engine = RiskEngine()
        names = {r.name for r in engine.rules}
        expected = {
            "cutoff_22khz", "highfreq_smooth", "no_log",
            "accuraterip_fail", "web_source_trusted", "spectrogram_gap",
            "fake_hires", "mp3_transcode", "bitrate_anomaly",
            "channel_similarity",
        }
        assert names == expected


class TestRiskEngineScoring:
    """Test score normalization and level classification."""

    def test_clean_release_is_safe(self, clean_context: AudioContext) -> None:
        """A clean release should score SAFE."""
        engine = RiskEngine()
        report = engine.evaluate(clean_context)
        assert report.level == "SAFE"
        assert report.score <= 15

    def test_transcode_scores_high(self, transcode_context: AudioContext) -> None:
        """A transcode should score HIGH_RISK or LIKELY_TRANSCODE."""
        engine = RiskEngine()
        report = engine.evaluate(transcode_context)
        assert report.level in ("HIGH_RISK", "LIKELY_TRANSCODE")
        assert report.score >= 56

    def test_score_clamped_0_100(self) -> None:
        """Score should always be between 0 and 100."""
        engine = RiskEngine()
        # Even with extreme features, score should be clamped
        ctx = AudioContext(
            format="FLAC",
            source="CD",
            has_log=False,
            features=AudioFeatures(
                cutoff_freq=5000.0,
                spectrogram_gap_detected=True,
                mp3_signature_score=1.0,
                hf_rolloff_smoothness=1.0,
                channel_similarity=0.99,
                avg_bitrate_kbps=100.0,
            ),
        )
        report = engine.evaluate(ctx)
        assert 0 <= report.score <= 100

    def test_web_source_reduces_score(self, web_context: AudioContext) -> None:
        """WEB source should apply negative delta (reducing risk)."""
        engine = RiskEngine()
        report = engine.evaluate(web_context)
        web_results = [r for r in report.rule_results if r.rule_name == "web_source_trusted"]
        assert len(web_results) == 1
        assert web_results[0].score_delta < 0

    def test_no_log_cd_increases_risk(self, no_log_cd_context: AudioContext) -> None:
        """CD without log should trigger no_log rule."""
        engine = RiskEngine()
        report = engine.evaluate(no_log_cd_context)
        no_log_results = [r for r in report.rule_results if r.rule_name == "no_log"]
        assert len(no_log_results) == 1
        assert no_log_results[0].score_delta > 0


class TestRiskEngineConfig:
    """Test configuration overrides."""

    def test_disable_rule(self, clean_context: AudioContext) -> None:
        """Disabled rules should not evaluate."""
        config = QualityConfig(risk_disabled_rules=["web_source_trusted"])
        engine = RiskEngine(config)
        report = engine.evaluate(clean_context)
        names = {r.rule_name for r in report.rule_results}
        assert "web_source_trusted" not in names

    def test_weight_override(self, transcode_context: AudioContext) -> None:
        """Weight overrides should affect scoring."""
        # With 0 weight, rules still trigger but contribute 0 score
        config = QualityConfig(risk_rule_weights={
            "cutoff_22khz": 0.0,
            "mp3_transcode": 0.0,
            "highfreq_smooth": 0.0,
            "spectrogram_gap": 0.0,
            "no_log": 0.0,
            "bitrate_anomaly": 0.0,
        })
        engine = RiskEngine(config)
        report = engine.evaluate(transcode_context)
        # Score should be much lower when heavy rules are zeroed
        assert report.score < 50

    def test_custom_thresholds(self) -> None:
        """Custom thresholds should affect level classification."""
        config = QualityConfig(risk_thresholds={
            "SAFE": 50,
            "LOW_RISK": 70,
            "SUSPICIOUS": 85,
            "HIGH_RISK": 95,
        })
        engine = RiskEngine(config)
        ctx = AudioContext(
            format="FLAC", source="CD", has_log=False,
            features=AudioFeatures(cutoff_freq=19000.0),
        )
        report = engine.evaluate(ctx)
        # With higher thresholds, more things are SAFE
        assert report.level in ("SAFE", "LOW_RISK")


class TestRiskEngineOutput:
    """Test output formatting."""

    def test_report_to_dict(self, clean_context: AudioContext) -> None:
        """Report should serialize to a dictionary."""
        engine = RiskEngine()
        report = engine.evaluate(clean_context)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "score" in d
        assert "level" in d
        assert "reasons" in d
        assert "suggestions" in d
        assert "rule_results" in d

    def test_report_to_json(self, clean_context: AudioContext) -> None:
        """Report should serialize to valid JSON."""
        engine = RiskEngine()
        report = engine.evaluate(clean_context)
        j = report.to_json()
        parsed = json.loads(j)
        assert isinstance(parsed, dict)
        assert parsed["level"] == report.level

    def test_suggestions_present(self, transcode_context: AudioContext) -> None:
        """High-risk reports should include suggestions."""
        engine = RiskEngine()
        report = engine.evaluate(transcode_context)
        assert len(report.suggestions) > 0

    def test_reasons_match_triggered_rules(self, transcode_context: AudioContext) -> None:
        """Reasons should correspond to triggered rules."""
        engine = RiskEngine()
        report = engine.evaluate(transcode_context)
        # Every positive-delta rule should contribute a reason
        positive_rules = [r for r in report.rule_results if r.score_delta > 0]
        assert len(report.reasons) == len(positive_rules)
