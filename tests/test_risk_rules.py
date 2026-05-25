"""
Tests for individual risk rules.

Each rule is tested in isolation with controlled AudioContext inputs
to verify correct triggering, scoring, severity, and metadata.
"""

from __future__ import annotations

import pytest

from quality.models import AudioContext, AudioFeatures, LogAnalysis, Severity
from quality.risk.rules.accuraterip_fail import AccurateRipFailRule
from quality.risk.rules.bitrate_anomaly import BitrateAnomalyRule
from quality.risk.rules.channel_similarity import ChannelSimilarityRule
from quality.risk.rules.cutoff_22khz import CutoffRule
from quality.risk.rules.fake_hires import FakeHiresRule
from quality.risk.rules.highfreq_smooth import HighFreqSmoothRule
from quality.risk.rules.mp3_transcode import Mp3TranscodeRule
from quality.risk.rules.no_log import NoLogRule
from quality.risk.rules.spectrogram_gap import SpectrogramGapRule
from quality.risk.rules.web_source_trusted import WebSourceTrustedRule


class TestCutoffRule:
    """Tests for the 22kHz cutoff rule."""

    def test_normal_cutoff_no_trigger(self) -> None:
        """Normal cutoff should not trigger."""
        rule = CutoffRule()
        ctx = AudioContext(
            sample_rate=44100,
            features=AudioFeatures(cutoff_freq=21500.0),
        )
        assert rule.evaluate(ctx) is None

    def test_low_cutoff_triggers(self) -> None:
        """Low cutoff should trigger with high delta."""
        rule = CutoffRule()
        ctx = AudioContext(
            sample_rate=44100,
            features=AudioFeatures(cutoff_freq=16000.0),
        )
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta >= 30
        assert result.severity == Severity.CRITICAL.value

    def test_borderline_cutoff(self) -> None:
        """Borderline cutoff should trigger with moderate delta."""
        rule = CutoffRule()
        ctx = AudioContext(
            sample_rate=44100,
            features=AudioFeatures(cutoff_freq=19000.0),
        )
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta > 0

    def test_no_cutoff_data(self) -> None:
        """Missing cutoff data should not trigger."""
        rule = CutoffRule()
        ctx = AudioContext(features=AudioFeatures(cutoff_freq=None))
        assert rule.evaluate(ctx) is None

    def test_metadata_contains_cutoff(self) -> None:
        """Result metadata should include detected cutoff."""
        rule = CutoffRule()
        ctx = AudioContext(
            sample_rate=44100,
            features=AudioFeatures(cutoff_freq=15000.0),
        )
        result = rule.evaluate(ctx)
        assert result is not None
        assert "detected_cutoff_hz" in result.metadata


class TestHighFreqSmoothRule:
    """Tests for the HF smoothness rule."""

    def test_normal_rolloff_no_trigger(self) -> None:
        rule = HighFreqSmoothRule()
        ctx = AudioContext(features=AudioFeatures(hf_rolloff_smoothness=0.2))
        assert rule.evaluate(ctx) is None

    def test_high_smoothness_triggers(self) -> None:
        rule = HighFreqSmoothRule()
        ctx = AudioContext(features=AudioFeatures(hf_rolloff_smoothness=0.9))
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta >= 20
        assert result.severity == Severity.CRITICAL.value

    def test_none_smoothness(self) -> None:
        rule = HighFreqSmoothRule()
        ctx = AudioContext(features=AudioFeatures(hf_rolloff_smoothness=None))
        assert rule.evaluate(ctx) is None


class TestNoLogRule:
    """Tests for the no-log rule."""

    def test_cd_with_log_no_trigger(self) -> None:
        rule = NoLogRule()
        ctx = AudioContext(source="CD", has_log=True)
        assert rule.evaluate(ctx) is None

    def test_cd_without_log_triggers(self) -> None:
        rule = NoLogRule()
        ctx = AudioContext(source="CD", has_log=False)
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta >= 15

    def test_web_source_no_trigger(self) -> None:
        """WEB sources should not be flagged for missing log."""
        rule = NoLogRule()
        ctx = AudioContext(source="WEB", has_log=False)
        assert rule.evaluate(ctx) is None

    def test_unknown_source_without_log(self) -> None:
        rule = NoLogRule()
        ctx = AudioContext(source="", has_log=False)
        result = rule.evaluate(ctx)
        assert result is not None


class TestAccurateRipFailRule:
    """Tests for the AccurateRip failure rule."""

    def test_ar_ok_no_trigger(self) -> None:
        rule = AccurateRipFailRule()
        ctx = AudioContext(
            has_log=True,
            log_analysis=LogAnalysis(
                log_type="EAC", score=100, confidence="HIGH",
                flags={"accuraterip_ok": True},
            ),
        )
        assert rule.evaluate(ctx) is None

    def test_ar_failed_triggers(self) -> None:
        rule = AccurateRipFailRule()
        ctx = AudioContext(
            has_log=True,
            log_analysis=LogAnalysis(
                log_type="EAC", score=80, confidence="MEDIUM",
                flags={"accuraterip_ok": False},
            ),
        )
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta >= 15

    def test_no_log_no_trigger(self) -> None:
        rule = AccurateRipFailRule()
        ctx = AudioContext(has_log=False)
        assert rule.evaluate(ctx) is None

    def test_ar_not_in_flags(self) -> None:
        """Missing AR flag should not trigger."""
        rule = AccurateRipFailRule()
        ctx = AudioContext(
            has_log=True,
            log_analysis=LogAnalysis(log_type="EAC", score=90, confidence="HIGH", flags={}),
        )
        assert rule.evaluate(ctx) is None


class TestWebSourceTrustedRule:
    """Tests for the WEB source trust rule."""

    def test_web_source_reduces_risk(self) -> None:
        rule = WebSourceTrustedRule()
        ctx = AudioContext(source="WEB")
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta < 0  # Negative = reduces risk

    def test_cd_source_no_trigger(self) -> None:
        rule = WebSourceTrustedRule()
        ctx = AudioContext(source="CD")
        assert rule.evaluate(ctx) is None


class TestSpectrogramGapRule:
    """Tests for the spectrogram gap rule."""

    def test_no_gap_no_trigger(self) -> None:
        rule = SpectrogramGapRule()
        ctx = AudioContext(features=AudioFeatures(spectrogram_gap_detected=False))
        assert rule.evaluate(ctx) is None

    def test_gap_detected_triggers(self) -> None:
        rule = SpectrogramGapRule()
        ctx = AudioContext(features=AudioFeatures(spectrogram_gap_detected=True))
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta >= 20

    def test_gap_with_low_cutoff_critical(self) -> None:
        rule = SpectrogramGapRule()
        ctx = AudioContext(features=AudioFeatures(
            spectrogram_gap_detected=True, cutoff_freq=18000.0,
        ))
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.severity == Severity.CRITICAL.value


class TestFakeHiresRule:
    """Tests for the fake Hi-Res rule."""

    def test_genuine_hires_no_trigger(self) -> None:
        rule = FakeHiresRule()
        ctx = AudioContext(
            bit_depth=24, sample_rate=96000,
            features=AudioFeatures(fake_hires_score=0.0),
        )
        assert rule.evaluate(ctx) is None

    def test_fake_hires_triggers(self) -> None:
        rule = FakeHiresRule()
        ctx = AudioContext(
            bit_depth=24, sample_rate=96000,
            features=AudioFeatures(fake_hires_score=0.8),
        )
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta >= 25

    def test_16bit_no_trigger(self) -> None:
        """Standard 16-bit should not trigger Hi-Res rule."""
        rule = FakeHiresRule()
        ctx = AudioContext(
            bit_depth=16, sample_rate=44100,
            features=AudioFeatures(fake_hires_score=0.5),
        )
        assert rule.evaluate(ctx) is None


class TestMp3TranscodeRule:
    """Tests for the MP3 transcode rule."""

    def test_no_mp3_signature(self) -> None:
        rule = Mp3TranscodeRule()
        ctx = AudioContext(
            format="FLAC",
            features=AudioFeatures(mp3_signature_score=0.1),
        )
        assert rule.evaluate(ctx) is None

    def test_strong_mp3_signature(self) -> None:
        rule = Mp3TranscodeRule()
        ctx = AudioContext(
            format="FLAC",
            features=AudioFeatures(mp3_signature_score=0.8),
        )
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta >= 40
        assert result.severity == Severity.CRITICAL.value

    def test_mp3_format_skipped(self) -> None:
        """Declared MP3 should not trigger transcode rule."""
        rule = Mp3TranscodeRule()
        ctx = AudioContext(
            format="MP3",
            features=AudioFeatures(mp3_signature_score=0.9),
        )
        assert rule.evaluate(ctx) is None


class TestBitrateAnomalyRule:
    """Tests for the bitrate anomaly rule."""

    def test_normal_flac_bitrate(self) -> None:
        rule = BitrateAnomalyRule()
        ctx = AudioContext(
            format="FLAC",
            features=AudioFeatures(avg_bitrate_kbps=900.0),
        )
        assert rule.evaluate(ctx) is None

    def test_low_flac_bitrate(self) -> None:
        rule = BitrateAnomalyRule()
        ctx = AudioContext(
            format="FLAC",
            features=AudioFeatures(avg_bitrate_kbps=200.0),
        )
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta >= 15


class TestChannelSimilarityRule:
    """Tests for the channel similarity rule."""

    def test_normal_similarity(self) -> None:
        rule = ChannelSimilarityRule()
        ctx = AudioContext(features=AudioFeatures(channel_similarity=0.5))
        assert rule.evaluate(ctx) is None

    def test_high_similarity_triggers(self) -> None:
        rule = ChannelSimilarityRule()
        ctx = AudioContext(features=AudioFeatures(channel_similarity=0.99))
        result = rule.evaluate(ctx)
        assert result is not None
        assert result.score_delta >= 15

    def test_none_similarity(self) -> None:
        rule = ChannelSimilarityRule()
        ctx = AudioContext(features=AudioFeatures(channel_similarity=None))
        assert rule.evaluate(ctx) is None
