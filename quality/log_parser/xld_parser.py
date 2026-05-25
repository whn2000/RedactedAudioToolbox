"""
X Lossless Decoder (XLD) log parser.

Parses XLD ripping logs using regex patterns to extract quality metrics,
verify AccurateRip results, check extraction mode, detect errors,
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


class XLDParser(BaseLogParser):
    """Parser for X Lossless Decoder ripping logs."""

    @property
    def parser_name(self) -> str:
        """Return parser identifier."""
        return LogType.XLD.value

    def can_parse(self, content: str) -> bool:
        """Check if the content is an XLD log.

        XLD logs contain 'X Lossless Decoder' or 'XLD extraction logfile'
        in the header. We avoid matching bare 'xld' to prevent false positives.
        """
        header = content[:500].lower()
        return (
            "x lossless decoder" in header
            or "xld extraction logfile" in header
        )

    def parse(self, content: str) -> LogAnalysis:
        """Parse an XLD log and produce a scored analysis.

        Analyzes: AccurateRip, read mode, cache defeat, pregap handling,
        Test/Copy CRC match.
        """
        score = 100
        issues: list[str] = []
        flags: dict[str, bool] = {}
        metadata: dict[str, Any] = {}

        # --- Extract metadata ---
        metadata["xld_version"] = self._extract_version(content)
        metadata["drive"] = self._extract_drive(content)

        # --- Read Mode (XLD Secure Ripper) ---
        read_mode = self._extract_read_mode(content)
        metadata["read_mode"] = read_mode
        secure = "xld secure ripper" in read_mode.lower()
        flags["secure_mode"] = secure
        if not secure:
            score -= 15
            issues.append("XLD Secure Ripper mode not used")

        # --- Cache Defeat ---
        cache_defeat = self._check_cache_defeat(content)
        flags["cache_defeat"] = cache_defeat
        if not cache_defeat:
            score -= 5
            issues.append("Drive cache defeat not enabled — may produce inaccurate rips")

        # --- Pregap Handling ---
        pregap = self._extract_pregap_handling(content)
        metadata["pregap_handling"] = pregap
        flags["pregap_analyzed"] = "analyz" in pregap.lower() if pregap else False

        # --- AccurateRip ---
        ar_result = self._check_accuraterip(content)
        flags["accuraterip_ok"] = ar_result["all_ok"]
        flags["accuraterip_present"] = ar_result["present"]
        metadata["accuraterip_tracks_ok"] = ar_result["tracks_ok"]
        metadata["accuraterip_tracks_total"] = ar_result["tracks_total"]

        if not ar_result["present"]:
            score -= 5
            issues.append("AccurateRip results not found in XLD log")
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
            # XLD doesn't always have test CRC — less severe than EAC
            score -= 5
            issues.append("No Test CRC data found in log")
        elif not crc_result["all_match"]:
            mismatched = crc_result["total"] - crc_result["matched"]
            score -= min(30, mismatched * 10)
            issues.append(
                f"CRC mismatch: {mismatched} track(s) have inconsistent checksums"
            )

        # --- Read Errors ---
        read_errors = self._count_read_errors(content)
        flags["read_errors"] = read_errors > 0
        metadata["read_error_count"] = read_errors
        if read_errors > 0:
            score -= min(30, read_errors * 10)
            issues.append(f"{read_errors} read error(s) detected")

        # --- Track Quality Summary ---
        track_quality = self._extract_track_quality(content)
        metadata["track_quality_summary"] = track_quality

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
        """Extract XLD version string."""
        match = re.search(
            r"X Lossless Decoder\s+version\s+([\d.]+(?:\s*\([^)]+\))?)",
            content, re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        match = re.search(r"XLD\s+(\d+\.\d+)", content, re.IGNORECASE)
        return match.group(1).strip() if match else "unknown"

    @staticmethod
    def _extract_drive(content: str) -> str:
        """Extract drive model from XLD log."""
        match = re.search(
            r"Used drive\s*:\s*(.+?)(?:\n|$)", content, re.IGNORECASE
        )
        return match.group(1).strip() if match else "unknown"

    @staticmethod
    def _extract_read_mode(content: str) -> str:
        """Extract read mode."""
        match = re.search(
            r"(?:Ripper mode|Read mode)\s*:\s*(.+?)(?:\n|$)",
            content, re.IGNORECASE,
        )
        return match.group(1).strip() if match else "unknown"

    @staticmethod
    def _check_cache_defeat(content: str) -> bool:
        """Check if drive cache defeat was enabled."""
        match = re.search(
            r"(?:Disable|Defeat)\s*(?:audio)?\s*cache\s*:\s*(OK|Yes|True|Enabled)",
            content, re.IGNORECASE,
        )
        return match is not None

    @staticmethod
    def _extract_pregap_handling(content: str) -> str:
        """Extract pregap detection/handling mode."""
        match = re.search(
            r"(?:Gap|Pregap)\s*(?:status|handling|detection)\s*:\s*(.+?)(?:\n|$)",
            content, re.IGNORECASE,
        )
        return match.group(1).strip() if match else "unknown"

    @staticmethod
    def _check_accuraterip(content: str) -> dict[str, Any]:
        """Analyze AccurateRip verification results."""
        result = {"present": False, "all_ok": False, "tracks_ok": 0, "tracks_total": 0}

        # XLD format: "Track XX : OK (confidence XXX)"
        ar_ok_matches = re.findall(
            r"AccurateRip.*?(?:OK|Match|confidence\s+\d+)",
            content, re.IGNORECASE,
        )

        ar_all_matches = re.findall(
            r"AccurateRip",
            content, re.IGNORECASE,
        )

        # Check for per-track results
        track_ok = re.findall(
            r"Track\s+\d+\s*:?\s*OK",
            content, re.IGNORECASE,
        )

        track_all = re.findall(
            r"Track\s+\d+",
            content, re.IGNORECASE,
        )

        if ar_all_matches or ar_ok_matches:
            result["present"] = True

        if track_all:
            result["tracks_total"] = len(set(track_all))

        if ar_ok_matches:
            result["tracks_ok"] = len(ar_ok_matches)
        elif track_ok:
            result["tracks_ok"] = len(track_ok)

        if result["tracks_total"] > 0:
            result["all_ok"] = result["tracks_ok"] >= result["tracks_total"]

        # Check for summary line
        if re.search(r"All tracks accurately ripped", content, re.IGNORECASE):
            result["present"] = True
            result["all_ok"] = True

        return result

    @staticmethod
    def _check_test_copy_crc(content: str) -> dict[str, Any]:
        """Check Test & Copy CRC consistency."""
        result = {"all_match": True, "matched": 0, "total": 0}

        # XLD format: "CRC32 hash (test run)  : XXXXXXXX"
        #             "CRC32 hash             : XXXXXXXX"
        test_crcs = re.findall(
            r"CRC32 hash\s*\(test\s*run\)\s*:\s*([0-9A-Fa-f]+)",
            content, re.IGNORECASE,
        )
        copy_crcs = re.findall(
            r"CRC32 hash\s*(?:\(skip zero\))?\s*:\s*([0-9A-Fa-f]+)",
            content, re.IGNORECASE,
        )

        # Remove test CRCs from copy CRCs to avoid double counting
        # since copy CRC pattern may also match test CRC lines
        if test_crcs and copy_crcs:
            # Filter out test-run matches from copy list
            non_test_crcs = []
            test_lines = set()
            for tc in test_crcs:
                test_lines.add(tc.upper())

            for cc in copy_crcs:
                if cc.upper() not in test_lines or len(non_test_crcs) < len(test_crcs):
                    non_test_crcs.append(cc)

            copy_crcs = non_test_crcs

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
    def _count_read_errors(content: str) -> int:
        """Count read errors in the log."""
        matches = re.findall(
            r"(?:Read error|I/O error)", content, re.IGNORECASE
        )
        return len(matches)

    @staticmethod
    def _extract_track_quality(content: str) -> list[dict[str, str]]:
        """Extract per-track quality summary."""
        tracks: list[dict[str, str]] = []
        # XLD format: "Track XX" followed by quality line
        track_blocks = re.findall(
            r"Track\s+(\d+)\s*.*?(?:Quality|Result)\s*:\s*(.+?)(?:\n|$)",
            content, re.IGNORECASE,
        )
        for num, quality in track_blocks:
            tracks.append({"track": num, "quality": quality.strip()})
        return tracks
