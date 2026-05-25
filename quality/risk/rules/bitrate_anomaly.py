"""
Rule: Bitrate anomaly detection.

Detects unusual bitrate values that don't match the declared format.
For example, a FLAC file with an abnormally low bitrate may indicate
encoding issues, or a file claiming to be 320kbps MP3 but having
a much lower actual bitrate.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class BitrateAnomalyRule(BaseRule):
    """Detect abnormal bitrate values for the declared format."""

    name = "bitrate_anomaly"
    description = "Flags files with unusual bitrate for their declared format"

    # Expected minimum bitrates by format (kbps)
    _MIN_BITRATE: dict[str, float] = {
        "FLAC": 300.0,
        "WAV": 1000.0,
        "ALAC": 300.0,
        "APE": 250.0,
    }

    # Expected maximum bitrate for lossy formats
    _MAX_BITRATE_LOSSY: dict[str, float] = {
        "MP3": 330.0,
        "AAC": 350.0,
        "OGG": 500.0,
        "OPUS": 512.0,
    }

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Check if the bitrate is anomalous for the declared format.

        For lossless formats: flags unusually low bitrates that may
        indicate very simple content or encoding errors.
        """
        avg_bitrate = ctx.features.avg_bitrate_kbps
        if avg_bitrate is None:
            return None

        fmt = (ctx.format or "").upper()
        if not fmt:
            return None

        metadata = {
            "avg_bitrate_kbps": avg_bitrate,
            "format": ctx.format,
        }

        # Check lossless format minimum bitrate
        min_br = self._MIN_BITRATE.get(fmt)
        if min_br is not None and avg_bitrate < min_br:
            severity = Severity.WARNING.value
            delta = 15

            if avg_bitrate < min_br * 0.5:
                severity = Severity.CRITICAL.value
                delta = 20

            metadata["expected_min_kbps"] = min_br
            return RuleResult(
                rule_name=self.name,
                score_delta=delta,
                reason=f"Bitrate {avg_bitrate:.0f}kbps is unusually low for {fmt} "
                       f"(expected ≥{min_br:.0f}kbps)",
                severity=severity,
                metadata=metadata,
            )

        # Check if a declared lossless format has a suspiciously
        # low bitrate indicating possible empty/silent content
        if fmt in self._MIN_BITRATE and avg_bitrate < 100:
            return RuleResult(
                rule_name=self.name,
                score_delta=20,
                reason=f"Extremely low bitrate ({avg_bitrate:.0f}kbps) for {fmt} — "
                       "file may be corrupted or mostly silent",
                severity=Severity.CRITICAL.value,
                metadata=metadata,
            )

        return None
