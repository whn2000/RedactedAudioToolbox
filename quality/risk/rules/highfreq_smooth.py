"""
Rule: High-frequency abnormal smoothness detection.

Detects unnaturally smooth high-frequency rolloff, which is characteristic
of lossy codecs (MP3, AAC) that use a sharp low-pass filter. Natural
analog recordings have gradual, irregular rolloff patterns.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class HighFreqSmoothRule(BaseRule):
    """Detect abnormally smooth high-frequency rolloff."""

    name = "highfreq_smooth"
    description = "Detects unnaturally smooth HF rolloff indicating lossy encoding"

    # Smoothness thresholds
    _CRITICAL_THRESHOLD = 0.85
    _WARNING_THRESHOLD = 0.65
    _INFO_THRESHOLD = 0.50

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Check if the high-frequency rolloff is suspiciously smooth.

        Natural recordings have irregular, gradual rolloff. Lossy codecs
        produce characteristic sharp, smooth cutoffs.
        """
        smoothness = ctx.features.hf_rolloff_smoothness
        if smoothness is None:
            return None

        metadata = {"hf_rolloff_smoothness": smoothness}

        if smoothness >= self._CRITICAL_THRESHOLD:
            return RuleResult(
                rule_name=self.name,
                score_delta=25,
                reason=f"Abnormally smooth HF rolloff (smoothness={smoothness:.2f}) — characteristic of lossy encoding",
                severity=Severity.CRITICAL.value,
                metadata=metadata,
            )
        elif smoothness >= self._WARNING_THRESHOLD:
            return RuleResult(
                rule_name=self.name,
                score_delta=15,
                reason=f"Suspiciously smooth HF rolloff (smoothness={smoothness:.2f})",
                severity=Severity.WARNING.value,
                metadata=metadata,
            )
        elif smoothness >= self._INFO_THRESHOLD:
            return RuleResult(
                rule_name=self.name,
                score_delta=8,
                reason=f"Slightly unusual HF rolloff smoothness ({smoothness:.2f}) — may be natural",
                severity=Severity.INFO.value,
                metadata=metadata,
            )

        return None
