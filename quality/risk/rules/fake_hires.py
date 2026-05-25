"""
Rule: Fake Hi-Res detection.

Detects releases that claim to be Hi-Res (>48kHz sample rate or >16-bit
depth) but lack genuine high-frequency content. This typically indicates
upsampling from a lower-resolution source.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class FakeHiresRule(BaseRule):
    """Detect fake Hi-Res audio (upsampled from lower resolution)."""

    name = "fake_hires"
    description = "Detects Hi-Res files that lack genuine high-frequency content"

    # Thresholds for fake_hires_score from audio_stats
    _CRITICAL_THRESHOLD = 0.7
    _WARNING_THRESHOLD = 0.4
    _INFO_THRESHOLD = 0.2

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Check for fake Hi-Res characteristics.

        Only applies to files claiming Hi-Res specifications (>48kHz
        sample rate or >16-bit depth).
        """
        sample_rate = ctx.sample_rate
        bit_depth = ctx.bit_depth

        # Only check if the file claims to be Hi-Res
        is_hires = False
        if sample_rate is not None and sample_rate > 48000:
            is_hires = True
        if bit_depth is not None and bit_depth > 16 and sample_rate is not None and sample_rate > 44100:
            is_hires = True

        if not is_hires:
            return None

        fake_score = ctx.features.fake_hires_score
        if fake_score is None:
            return None

        metadata = {
            "fake_hires_score": fake_score,
            "declared_bit_depth": bit_depth,
            "declared_sample_rate": sample_rate,
            "cutoff_freq": ctx.features.cutoff_freq,
        }

        if fake_score >= self._CRITICAL_THRESHOLD:
            return RuleResult(
                rule_name=self.name,
                score_delta=40,
                reason=f"Fake Hi-Res detected (score={fake_score:.2f}) — "
                       f"declared {bit_depth}bit/{sample_rate}Hz but lacks genuine high-frequency content",
                severity=Severity.CRITICAL.value,
                metadata=metadata,
            )
        elif fake_score >= self._WARNING_THRESHOLD:
            return RuleResult(
                rule_name=self.name,
                score_delta=25,
                reason=f"Suspicious Hi-Res quality (score={fake_score:.2f}) — "
                       f"high-frequency content does not match declared {sample_rate}Hz",
                severity=Severity.WARNING.value,
                metadata=metadata,
            )
        elif fake_score >= self._INFO_THRESHOLD:
            return RuleResult(
                rule_name=self.name,
                score_delta=10,
                reason=f"Hi-Res content quality is borderline (score={fake_score:.2f})",
                severity=Severity.INFO.value,
                metadata=metadata,
            )

        return None
