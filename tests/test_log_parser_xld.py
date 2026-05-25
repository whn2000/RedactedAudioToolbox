"""
Tests for the XLD log parser.

Tests detection, parsing, scoring, flag extraction, and edge cases
for X Lossless Decoder ripping logs.
"""

from __future__ import annotations

import json

import pytest

from quality.log_parser.detector import detect_and_parse, detect_log_type
from quality.log_parser.xld_parser import XLDParser


class TestXLDDetection:
    """Test XLD log type detection."""

    def test_detects_xld_log(self, xld_log_content: str) -> None:
        """Should correctly identify XLD log content."""
        assert detect_log_type(xld_log_content) == "XLD"

    def test_parser_can_parse(self, xld_log_content: str) -> None:
        """XLDParser.can_parse() should return True for XLD logs."""
        parser = XLDParser()
        assert parser.can_parse(xld_log_content) is True

    def test_parser_rejects_non_xld(self) -> None:
        """XLDParser.can_parse() should return False for non-XLD content."""
        parser = XLDParser()
        assert parser.can_parse("This is not an XLD log") is False

    def test_parser_name(self) -> None:
        parser = XLDParser()
        assert parser.parser_name == "XLD"


class TestXLDParsing:
    """Test XLD log parsing results."""

    def test_parse_produces_analysis(self, xld_log_content: str) -> None:
        """Parsing should produce a LogAnalysis object."""
        parser = XLDParser()
        result = parser.parse(xld_log_content)
        assert result.log_type == "XLD"
        assert 0 <= result.score <= 100

    def test_perfect_log_high_score(self, xld_log_content: str) -> None:
        """A perfect XLD log should score ≥90."""
        parser = XLDParser()
        result = parser.parse(xld_log_content)
        assert result.score >= 90
        assert result.confidence == "HIGH"

    def test_extracts_version(self, xld_log_content: str) -> None:
        """Should extract XLD version."""
        parser = XLDParser()
        result = parser.parse(xld_log_content)
        version = result.metadata.get("xld_version", "")
        assert version != "unknown"

    def test_secure_mode_flag(self, xld_log_content: str) -> None:
        """Should detect XLD Secure Ripper mode."""
        parser = XLDParser()
        result = parser.parse(xld_log_content)
        assert result.flags.get("secure_mode") is True

    def test_cache_defeat_flag(self, xld_log_content: str) -> None:
        """Should detect cache defeat setting."""
        parser = XLDParser()
        result = parser.parse(xld_log_content)
        assert result.flags.get("cache_defeat") is True

    def test_accuraterip_flag(self, xld_log_content: str) -> None:
        """Should detect AccurateRip status."""
        parser = XLDParser()
        result = parser.parse(xld_log_content)
        assert result.flags.get("accuraterip_ok") is True

    def test_test_copy_crc_match(self, xld_log_content: str) -> None:
        """Should detect matching CRCs."""
        parser = XLDParser()
        result = parser.parse(xld_log_content)
        assert result.flags.get("test_copy_crc_match") is True


class TestXLDEdgeCases:
    """Test XLD edge cases and error handling."""

    def test_non_secure_mode(self) -> None:
        """Non-secure mode should lower score."""
        log = """X Lossless Decoder version 20210101 (153.1)

Used drive : TEST DRIVE
Ripper mode             : CDParanoia III 10.2
Disable audio cache     : OK
"""
        parser = XLDParser()
        result = parser.parse(log)
        assert result.flags.get("secure_mode") is False
        assert result.score < 100

    def test_no_cache_defeat(self) -> None:
        """Missing cache defeat should lower score."""
        log = """X Lossless Decoder version 20210101 (153.1)

Used drive : TEST DRIVE
Ripper mode             : XLD Secure Ripper
"""
        parser = XLDParser()
        result = parser.parse(log)
        assert result.flags.get("cache_defeat") is False

    def test_json_serialization(self, xld_log_content: str) -> None:
        """LogAnalysis should serialize to valid JSON."""
        parser = XLDParser()
        result = parser.parse(xld_log_content)
        parsed = json.loads(result.to_json())
        assert parsed["log_type"] == "XLD"
        assert "flags" in parsed
        assert isinstance(parsed["flags"], dict)


class TestLogDetector:
    """Test the auto-detection dispatcher."""

    def test_auto_detect_eac(self, eac_log_content: str) -> None:
        """Should auto-detect and parse EAC logs."""
        result = detect_and_parse(content=eac_log_content)
        assert result.log_type == "EAC"

    def test_auto_detect_xld(self, xld_log_content: str) -> None:
        """Should auto-detect and parse XLD logs."""
        result = detect_and_parse(content=xld_log_content)
        assert result.log_type == "XLD"

    def test_unknown_log(self) -> None:
        """Unknown log format should return UNKNOWN type."""
        result = detect_and_parse(content="This is random text, not a log file.")
        assert result.log_type == "UNKNOWN"
        assert result.score == 0

    def test_none_input(self) -> None:
        """No input should return UNKNOWN type."""
        result = detect_and_parse()
        assert result.log_type == "UNKNOWN"
        assert len(result.issues) > 0
