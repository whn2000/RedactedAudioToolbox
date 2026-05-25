"""
Rule: Spectrogram gap/shelf detection.

Detects visible gaps or shelves in the spectrogram, which are strong
indicators of lossy encoding artifacts. These gaps appear as horizontal
bands with significantly reduced energy, unlike natural frequency
content which is continuous.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class SpectrogramGapRule(BaseRule):
    """Detect spectrogram gaps indicating lossy artifacts."""

    name = "spectrogram_gap"
    description = "Detects visible gaps or shelves in the spectrogram"

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Check if the spectrogram contains gaps.

        Uses the pre-computed gap detection result from AudioFeatures.
        A detected gap is a strong indicator of lossy transcoding.
        """
        if not ctx.features.spectrogram_gap_detected:
            return None

        metadata = {
            "spectrogram_gap_detected": True,
            "cutoff_freq": ctx.features.cutoff_freq,
        }

        # If we also have a low cutoff, this is very concerning
        cutoff = ctx.features.cutoff_freq
        if cutoff is not None and cutoff < 20000:
            return RuleResult(
                rule_name=self.name,
                score_delta=35,
                reason=f"Spectrogram shows lossy artifacts (gap detected) with low cutoff at {cutoff:.0f}Hz",
                severity=Severity.CRITICAL.value,
                metadata=metadata,
            )

        return RuleResult(
            rule_name=self.name,
            score_delta=20,
            reason="Spectrogram shows a visible gap or shelf — possible lossy encoding artifact",
            severity=Severity.WARNING.value,
            metadata=metadata,
        )
