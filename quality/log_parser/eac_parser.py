"""
Exact Audio Copy (EAC) log parser.

Parses EAC ripping logs using regex patterns to extract quality metrics,
verify AccurateRip results, check secure mode usage, detect errors,
and produce a scored LogAnalysis.

Scoring starts at 100 and deducts points for each issue found.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from quality.log_parser.base import BaseLogParser
from quality.models import Confidence, LogAnalysis, LogType

logger = logging.getLogger(__name__)


class EACParser(BaseLogParser):
    """Parser for Exact Audio Copy ripping logs."""

    @property
    def parser_name(self) -> str:
        """Return parser identifier."""
        return LogType.EAC.value

    def can_parse(self, content: str) -> bool:
        """Check if the content is an EAC log.

        EAC logs typically start with 'Exact Audio Copy' in the header.
        """
        # Check first 500 chars for EAC signature
        header = content[:500].lower()
        return "exact audio copy" in header

    def parse(self, content: str) -> LogAnalysis:
        """Parse an EAC log and produce a scored analysis.

        Analyzes: AccurateRip, drive offset, secure mode, timing problems,
        suspicious positions, Test/Copy CRC match, null samples, read errors.
        """
        score = 100
        issues: list[str] = []
        flags: dict[str, bool] = {}
        metadata: dict[str, Any] = {}

        # --- Extract metadata ---
        metadata["eac_version"] = self._extract_version(content)
        metadata["drive"] = self._extract_drive(content)
        metadata["read_mode"] = self._extract_read_mode(content)

        # --- Secure Mode ---
        secure = self._check_secure_mode(content)
        flags["secure_mode"] = secure
        if not secure:
            score -= 15
            issues.append("Secure mode not used — rip integrity not guaranteed")

        # --- Drive Offset ---
        offset_ok = self._check_drive_offset(content)
        flags["drive_offset_configured"] = offset_ok
        if not offset_ok:
            score -= 5
            issues.append("Drive read offset may not be correctly configured")

        # --- AccurateRip ---
        ar_result = self._check_accuraterip(content)
        flags["accuraterip_ok"] = ar_result["all_ok"]
        flags["accuraterip_present"] = ar_result["present"]
        metadata["accuraterip_tracks_ok"] = ar_result["tracks_ok"]
        metadata["accuraterip_tracks_total"] = ar_result["tracks_total"]

        if not ar_result["present"]:
            score -= 5
            issues.append("AccurateRip results not found in log")
        elif not ar_result["all_ok"]:
            failed = ar_result["tracks_total"] - ar_result["tracks_ok"]
            score -= min(30, failed * 5)
            issues.append(
                f"AccurateRip: {ar_result['tracks_ok']}/{ar_result['tracks_total']} "
                f"tracks verified ({failed} failed)"
            )

        # --- Test & Copy CRC ---
        crc_result = self._check_test_copy_crc(content)
        flags["test_copy_crc_match"] = crc_result["all_match"]
        metadata["crc_tracks_matched"] = crc_result["matched"]
        metadata["crc_tracks_total"] = crc_result["total"]

        if crc_result["total"] == 0:
            score -= 10
            issues.append("No Test & Copy CRC data found — test run may not have been performed")
            flags["test_copy_crc_match"] = False
        elif not crc_result["all_match"]:
            mismatched = crc_result["total"] - crc_result["matched"]
            score -= min(30, mismatched * 10)
            issues.append(
                f"Test & Copy CRC mismatch: {mismatched} track(s) have inconsistent checksums"
            )

        # --- Timing Problems ---
        timing = self._check_timing_problems(content)
        flags["timing_problem"] = timing
        if timing:
            score -= 5
            issues.append("Timing problems detected during extraction")

        # --- Suspicious Positions ---
        suspicious = self._check_suspicious_positions(content)
        flags["suspicious_positions"] = suspicious
        if suspicious:
            score -= 10
            issues.append("Suspicious position(s) detected — may indicate disc damage")

        # --- Read Errors ---
        read_errors = self._count_read_errors(content)
        flags["read_errors"] = read_errors > 0
        metadata["read_error_count"] = read_errors
        if read_errors > 0:
            score -= min(30, read_errors * 10)
            issues.append(f"{read_errors} read error(s) detected")

        # --- Null Samples ---
        null_samples = self._check_null_samples(content)
        flags["null_samples_issue"] = null_samples
        if null_samples:
            score -= 5
            issues.append("Null samples issue detected in one or more tracks")

        # --- Gap Handling ---
        gap_mode = self._extract_gap_handling(content)
        metadata["gap_handling"] = gap_mode

        # Clamp score
        score = max(0, min(100, score))

        # Determine confidence
        if score >= 90 and flags.get("accuraterip_ok", False):
            confidence = Confidence.HIGH.value
        elif score >= 70:
            confidence = Confidence.MEDIUM.value
        else:
            confidence = Confidence.LOW.value

        return LogAnalysis(
            log_type=self.parser_name,
            score=score,
            confidence=confidence,
            issues=issues,
            flags=flags,
            metadata=metadata,
        )

    # --- Private extraction methods ---

    @staticmethod
    def _extract_version(content: str) -> str:
        """Extract EAC version string."""
        match = re.search(
            r"Exact Audio Copy\s+V(\d+\.\d+(?:\.\d+)?(?:\s+beta\s*\d*)?)",
            content, re.IGNORECASE,
        )
        return match.group(1).strip() if match else "unknown"

    @staticmethod
    def _extract_drive(content: str) -> str:
        """Extract drive model from EAC log."""
        match = re.search(
            r"Used drive\s*:\s*(.+?)(?:\n|$)",
            content, re.IGNORECASE,
        )
        return match.group(1).strip() if match else "unknown"

    @staticmethod
    def _extract_read_mode(content: str) -> str:
        """Extract read mode (Secure, Burst, etc.)."""
        match = re.search(
            r"Read mode\s*:\s*(.+?)(?:\n|$)",
            content, re.IGNORECASE,
        )
        return match.group(1).strip() if match else "unknown"

    @staticmethod
    def _check_secure_mode(content: str) -> bool:
        """Check if secure mode was used."""
        match = re.search(
            r"Read mode\s*:\s*Secure",
            content, re.IGNORECASE,
        )
        return match is not None

    @staticmethod
    def _check_drive_offset(content: str) -> bool:
        """Check if drive offset is configured (non-zero)."""
        match = re.search(
            r"Read offset correction\s*:\s*(\d+)",
            content, re.IGNORECASE,
        )
        if match:
            offset = int(match.group(1))
            return offset != 0
        return False

    @staticmethod
    def _check_accuraterip(content: str) -> dict[str, Any]:
        """Analyze AccurateRip verification results."""
        result = {"present": False, "all_ok": False, "tracks_ok": 0, "tracks_total": 0}

        # Look for AccurateRip summary or per-track results
        ar_matches = re.findall(
            r"(?:accurately ripped|AccurateRip.*?(?:OK|Match|confidence))",
            content, re.IGNORECASE,
        )
        if not ar_matches:
            # Try alternative patterns
            ar_matches = re.findall(
                r"Track\s+\d+.*(?:accurately ripped|AR\s*(?:OK|Match|v[12]))",
                content, re.IGNORECASE,
            )

        if ar_matches:
            result["present"] = True
            result["tracks_total"] = len(ar_matches)

        # Count successful verifications
        ok_matches = re.findall(
            r"(?:accurately ripped\s*\(confidence\s+\d+\))",
            content, re.IGNORECASE,
        )
        if not ok_matches:
            ok_matches = re.findall(
                r"AccurateRip.*?OK",
                content, re.IGNORECASE,
            )

        result["tracks_ok"] = len(ok_matches)
        result["all_ok"] = (
            result["present"]
            and result["tracks_ok"] > 0
            and result["tracks_ok"] >= result["tracks_total"]
        )

        # Check for "All tracks accurately ripped" summary
        if re.search(r"All tracks accurately ripped", content, re.IGNORECASE):
            result["present"] = True
            result["all_ok"] = True

        return result

    @staticmethod
    def _check_test_copy_crc(content: str) -> dict[str, Any]:
        """Check Test & Copy CRC consistency."""
        result = {"all_match": True, "matched": 0, "total": 0}

        # Pattern: "Test CRC XXXXXXXX" and "Copy CRC XXXXXXXX" per track
        test_crcs = re.findall(
            r"Test CRC\s+([0-9A-Fa-f]+)", content, re.IGNORECASE
        )
        copy_crcs = re.findall(
            r"Copy CRC\s+([0-9A-Fa-f]+)", content, re.IGNORECASE
        )

        pairs = min(len(test_crcs), len(copy_crcs))
        result["total"] = pairs

        for i in range(pairs):
            if test_crcs[i].upper() == copy_crcs[i].upper():
                result["matched"] += 1
            else:
                result["all_match"] = False

        if pairs == 0:
            result["all_match"] = False

        return result

    @staticmethod
    def _check_timing_problems(content: str) -> bool:
        """Check for timing problems."""
        return bool(re.search(
            r"Timing problem", content, re.IGNORECASE
        ))

    @staticmethod
    def _check_suspicious_positions(content: str) -> bool:
        """Check for suspicious positions."""
        return bool(re.search(
            r"Suspicious position", content, re.IGNORECASE
        ))

    @staticmethod
    def _count_read_errors(content: str) -> int:
        """Count read errors in the log."""
        matches = re.findall(
            r"Read error", content, re.IGNORECASE
        )
        return len(matches)

    @staticmethod
    def _check_null_samples(content: str) -> bool:
        """Check for null samples issues."""
        # EAC reports null samples in CRC section
        return bool(re.search(
            r"(?:Null samples|missing samples)",
            content, re.IGNORECASE
        ))

    @staticmethod
    def _extract_gap_handling(content: str) -> str:
        """Extract gap handling mode."""
        match = re.search(
            r"Gap handling\s*:\s*(.+?)(?:\n|$)",
            content, re.IGNORECASE,
        )
        return match.group(1).strip() if match else "unknown"
