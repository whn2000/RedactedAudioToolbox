"""
Rule: 22kHz hard cutoff detection.

Detects a hard frequency cutoff near 22kHz (or below the expected
Nyquist frequency), which is a strong indicator of lossy source
material that has been transcoded to a lossless format.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class CutoffRule(BaseRule):
    """Detect hard frequency cutoff indicating lossy source."""

    name = "cutoff_22khz"
    description = "Detects hard high-frequency cutoff near or below 22kHz"

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Check if the cutoff frequency is suspiciously low.

        Scoring scales with how far below the expected Nyquist the
        cutoff falls. A cutoff at 16kHz is much worse than 20kHz.
        """
        cutoff = ctx.features.cutoff_freq
        if cutoff is None:
            return None

        sample_rate = ctx.sample_rate or 44100
        nyquist = sample_rate / 2.0

        # Calculate expected minimum cutoff (90% of Nyquist)
        expected_min = nyquist * 0.90

        if cutoff >= expected_min:
            return None  # Normal — no issue

        # Calculate severity based on how far below expected
        ratio = cutoff / nyquist if nyquist > 0 else 0
        metadata = {
            "detected_cutoff_hz": cutoff,
            "expected_min_hz": round(expected_min, 1),
            "nyquist_hz": nyquist,
            "ratio": round(ratio, 4),
        }

        if ratio < 0.70:
            # Extremely low — strong transcode indicator
            return RuleResult(
                rule_name=self.name,
                score_delta=40,
                reason=f"Hard frequency cutoff at {cutoff:.0f}Hz (expected ≥{expected_min:.0f}Hz) — strong transcode indicator",
                severity=Severity.CRITICAL.value,
                metadata=metadata,
            )
        elif ratio < 0.80:
            return RuleResult(
                rule_name=self.name,
                score_delta=30,
                reason=f"Hard frequency cutoff at {cutoff:.0f}Hz (expected ≥{expected_min:.0f}Hz) — likely lossy source",
                severity=Severity.CRITICAL.value,
                metadata=metadata,
            )
        elif ratio < 0.88:
            return RuleResult(
                rule_name=self.name,
                score_delta=20,
                reason=f"Frequency cutoff at {cutoff:.0f}Hz is below expected minimum of {expected_min:.0f}Hz",
                severity=Severity.WARNING.value,
                metadata=metadata,
            )
        else:
            return RuleResult(
                rule_name=self.name,
                score_delta=10,
                reason=f"Frequency cutoff at {cutoff:.0f}Hz is slightly below expected {expected_min:.0f}Hz — may be natural rolloff",
                severity=Severity.INFO.value,
                metadata=metadata,
            )
