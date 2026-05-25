"""
Tests for the EAC log parser.

Tests detection, parsing, scoring, flag extraction, and edge cases
for Exact Audio Copy ripping logs.
"""

from __future__ import annotations

import pytest

from quality.log_parser.detector import detect_and_parse, detect_log_type
from quality.log_parser.eac_parser import EACParser


class TestEACDetection:
    """Test EAC log type detection."""

    def test_detects_eac_log(self, eac_log_content: str) -> None:
        """Should correctly identify EAC log content."""
        assert detect_log_type(eac_log_content) == "EAC"

    def test_parser_can_parse(self, eac_log_content: str) -> None:
        """EACParser.can_parse() should return True for EAC logs."""
        parser = EACParser()
        assert parser.can_parse(eac_log_content) is True

    def test_parser_rejects_non_eac(self) -> None:
        """EACParser.can_parse() should return False for non-EAC content."""
        parser = EACParser()
        assert parser.can_parse("This is not a log file") is False

    def test_parser_name(self) -> None:
        parser = EACParser()
        assert parser.parser_name == "EAC"


class TestEACParsing:
    """Test EAC log parsing results."""

    def test_parse_produces_analysis(self, eac_log_content: str) -> None:
        """Parsing should produce a LogAnalysis object."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        assert result.log_type == "EAC"
        assert 0 <= result.score <= 100

    def test_perfect_log_high_score(self, eac_log_content: str) -> None:
        """A perfect EAC log should score ≥90."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        assert result.score >= 90
        assert result.confidence == "HIGH"

    def test_extracts_version(self, eac_log_content: str) -> None:
        """Should extract EAC version."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        assert result.metadata.get("eac_version") == "1.6"

    def test_extracts_drive(self, eac_log_content: str) -> None:
        """Should extract drive model."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        assert "PLEXTOR" in result.metadata.get("drive", "")

    def test_secure_mode_flag(self, eac_log_content: str) -> None:
        """Should detect secure mode."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        assert result.flags.get("secure_mode") is True

    def test_accuraterip_flag(self, eac_log_content: str) -> None:
        """Should detect AccurateRip status."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        assert result.flags.get("accuraterip_ok") is True

    def test_test_copy_crc_match(self, eac_log_content: str) -> None:
        """Should detect matching Test/Copy CRCs."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        assert result.flags.get("test_copy_crc_match") is True

    def test_no_timing_problems(self, eac_log_content: str) -> None:
        """Should report no timing problems."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        assert result.flags.get("timing_problem") is False

    def test_no_read_errors(self, eac_log_content: str) -> None:
        """Should report no read errors."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        assert result.flags.get("read_errors") is False


class TestEACEdgeCases:
    """Test edge cases and error handling."""

    def test_burst_mode_log(self) -> None:
        """Burst mode should lower the score."""
        log = """Exact Audio Copy V1.6 from 23. October 2020

Used drive  : ASUS DRW-24B1ST
Read mode                 : Burst

Track  1
     Test CRC AABBCCDD
     Copy CRC AABBCCDD
"""
        parser = EACParser()
        result = parser.parse(log)
        assert result.flags.get("secure_mode") is False
        assert result.score < 100

    def test_crc_mismatch(self) -> None:
        """CRC mismatch should lower the score."""
        log = """Exact Audio Copy V1.6 from 23. October 2020

Used drive  : TEST DRIVE
Read mode                 : Secure

Track  1
     Test CRC AABBCCDD
     Copy CRC 11223344
"""
        parser = EACParser()
        result = parser.parse(log)
        assert result.flags.get("test_copy_crc_match") is False
        assert result.score < 100

    def test_empty_log(self) -> None:
        """Empty/minimal EAC log should produce low score."""
        log = "Exact Audio Copy V1.6\n"
        parser = EACParser()
        result = parser.parse(log)
        assert result.score < 80

    def test_json_serialization(self, eac_log_content: str) -> None:
        """LogAnalysis should serialize to valid JSON."""
        parser = EACParser()
        result = parser.parse(eac_log_content)
        import json
        parsed = json.loads(result.to_json())
        assert parsed["log_type"] == "EAC"
        assert "flags" in parsed
