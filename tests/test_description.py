"""
Tests for the description generator.

Tests section rendering, template composition, conditional sections,
and BBCode output validity.
"""

from __future__ import annotations

import pytest

from quality.description.generator import DescriptionGenerator
from quality.description.sections import (
    render_dynamic_range_section,
    render_footer,
    render_format_section,
    render_header,
    render_log_section,
    render_risk_section,
    render_spectrogram_section,
    render_tools_section,
)
from quality.models import LogAnalysis, RiskReport, RuleResult


class TestSectionRenderers:
    """Test individual section renderers."""

    def test_header(self) -> None:
        """Header should contain title text."""
        header = render_header()
        assert "Release Information" in header
        assert "[b]" in header

    def test_format_section(self) -> None:
        """Format section should include format, bitrate, source."""
        section = render_format_section(
            format="FLAC", bitrate="Lossless", source="CD",
        )
        assert "FLAC" in section
        assert "Lossless" in section
        assert "CD" in section

    def test_format_section_with_depth(self) -> None:
        """Format section should include bit depth when provided."""
        section = render_format_section(
            format="FLAC", bitrate="Lossless", source="WEB",
            bit_depth=24, sample_rate=96000,
        )
        assert "24" in section
        assert "96000" in section

    def test_format_section_defaults(self) -> None:
        """Format section should show 'Unknown' for missing values."""
        section = render_format_section()
        assert "Unknown" in section

    def test_tools_section(self) -> None:
        """Tools section should list tools."""
        section = render_tools_section(["Tool1", "Tool2"])
        assert "Tool1" in section
        assert "Tool2" in section

    def test_tools_section_defaults(self) -> None:
        """Tools section should provide defaults when no tools given."""
        section = render_tools_section()
        assert "RedactedAudioToolbox" in section

    def test_log_section_with_issues(self) -> None:
        """Log section should show issues."""
        log = LogAnalysis(
            log_type="EAC", score=85, confidence="MEDIUM",
            issues=["CRC mismatch found"],
        )
        section = render_log_section(log)
        assert "EAC" in section
        assert "85" in section
        assert "CRC mismatch" in section

    def test_log_section_no_issues(self) -> None:
        """Log section should show 'no issues' when clean."""
        log = LogAnalysis(
            log_type="XLD", score=100, confidence="HIGH",
            issues=[],
        )
        section = render_log_section(log)
        assert "No issues" in section

    def test_log_section_none(self) -> None:
        """No log should return empty string."""
        assert render_log_section(None) == ""

    def test_spectrogram_section(self) -> None:
        """Spectrogram section should embed image URL."""
        section = render_spectrogram_section("https://example.com/spec.png")
        assert "[img]" in section
        assert "https://example.com/spec.png" in section

    def test_spectrogram_section_none(self) -> None:
        """No URL should return empty string."""
        assert render_spectrogram_section(None) == ""

    def test_dr_section(self) -> None:
        """DR section should show value."""
        section = render_dynamic_range_section(12)
        assert "12" in section

    def test_dr_section_none(self) -> None:
        """No DR value should return empty string."""
        assert render_dynamic_range_section(None) == ""

    def test_risk_section_safe(self) -> None:
        """SAFE level should use green styling."""
        report = RiskReport(score=5, level="SAFE")
        section = render_risk_section(report)
        assert "green" in section
        assert "SAFE" in section

    def test_risk_section_warning(self) -> None:
        """SUSPICIOUS level should use orange styling."""
        report = RiskReport(score=45, level="SUSPICIOUS")
        section = render_risk_section(report)
        assert "orange" in section

    def test_risk_section_danger(self) -> None:
        """HIGH_RISK should use red styling."""
        report = RiskReport(
            score=75, level="HIGH_RISK",
            reasons=["Hard cutoff detected"],
            suggestions=["Manual review required"],
        )
        section = render_risk_section(report)
        assert "red" in section
        assert "Hard cutoff" in section
        assert "Manual review" in section

    def test_risk_section_disabled(self) -> None:
        """Disabled risk section should return empty."""
        report = RiskReport(score=50, level="SUSPICIOUS")
        assert render_risk_section(report, include=False) == ""

    def test_footer(self) -> None:
        """Footer should contain generator attribution."""
        footer = render_footer()
        assert "RedactedAudioToolbox" in footer


class TestDescriptionGenerator:
    """Test the description generator composition."""

    def test_minimal_description(self) -> None:
        """Should generate a description with minimal input."""
        gen = DescriptionGenerator()
        bbcode = gen.generate(format="FLAC")
        assert "FLAC" in bbcode
        assert "Release Information" in bbcode

    def test_full_description(self) -> None:
        """Should generate a complete description with all inputs."""
        gen = DescriptionGenerator()
        log = LogAnalysis(
            log_type="EAC", score=100, confidence="HIGH", issues=[],
        )
        risk = RiskReport(score=5, level="SAFE")
        bbcode = gen.generate(
            format="FLAC",
            bitrate="Lossless",
            source="CD",
            bit_depth=16,
            sample_rate=44100,
            log_analysis=log,
            risk_report=risk,
            spectrogram_url="https://example.com/spec.png",
            dr_value=14,
        )
        assert "FLAC" in bbcode
        assert "Lossless" in bbcode
        assert "CD" in bbcode
        assert "EAC" in bbcode
        assert "SAFE" in bbcode
        assert "spec.png" in bbcode
        assert "14" in bbcode

    def test_no_risk_section(self) -> None:
        """include_risk_notice=False should omit risk section."""
        gen = DescriptionGenerator(include_risk_notice=False)
        risk = RiskReport(score=50, level="SUSPICIOUS")
        bbcode = gen.generate(format="FLAC", risk_report=risk)
        assert "SUSPICIOUS" not in bbcode

    def test_no_spectrogram(self) -> None:
        """include_spectrogram=False should omit spectrogram."""
        gen = DescriptionGenerator(include_spectrogram=False)
        bbcode = gen.generate(
            format="FLAC",
            spectrogram_url="https://example.com/spec.png",
        )
        assert "[img]" not in bbcode

    def test_generate_from_dict(self) -> None:
        """Should work with dict input."""
        gen = DescriptionGenerator()
        bbcode = gen.generate_from_dict({
            "format": "FLAC",
            "bitrate": "24bit Lossless",
            "source": "WEB",
        })
        assert "FLAC" in bbcode
        assert "24bit Lossless" in bbcode

    def test_bbcode_structure(self) -> None:
        """Generated BBCode should have balanced tags."""
        gen = DescriptionGenerator()
        bbcode = gen.generate(format="FLAC", source="CD")
        # Check balanced [b] tags
        assert bbcode.count("[b]") == bbcode.count("[/b]")
        # Check balanced [size] tags
        assert bbcode.count("[size=") == bbcode.count("[/size]")
