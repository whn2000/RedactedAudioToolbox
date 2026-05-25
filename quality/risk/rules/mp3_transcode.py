"""
Rule: MP3 transcode detection.

Detects audio files that were transcoded from MP3 (or other lossy
formats) to a lossless format based on characteristic cutoff frequencies.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class Mp3TranscodeRule(BaseRule):
    """Detect MP3-to-lossless transcode artifacts using cutoff."""

    name = "mp3_transcode"
    description = "Detects files transcoded from MP3 to lossless format"
    enabled = True
    weight = 1.0

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Check for MP3 transcode signature based on hard frequency cutoffs."""
        
        if not ctx.features or ctx.features.cutoff_freq is None:
            return None

        cutoff = ctx.features.cutoff_freq
        fmt = (ctx.format or "FLAC").upper()

        # 仅针对标称为无损的格式进行检测
        if fmt in ("FLAC", "WAV", "ALAC", "APE"):
            
            # 1. 检测高码率假无损 (320kbps MP3 / 256k AAC 典型截断在 19.5kHz - 21.5kHz)
            if 19500 <= cutoff <= 21500:
                return RuleResult(
                    rule_name=self.name,
                    score_delta=45,
                    reason=f"Suspicious frequency cutoff at {cutoff:.0f}Hz — highly typical of 320kbps MP3 or AAC transcode",
                    severity=Severity.CRITICAL.value,
                    metadata={"cutoff_freq": cutoff, "declared_format": fmt}
                )
            
            # 2. 检测低码率假无损 (128k/192k MP3 典型截断 < 19.5kHz)
            elif cutoff < 19500:
                return RuleResult(
                    rule_name=self.name,
                    score_delta=60,
                    reason=f"Severe frequency cutoff at {cutoff:.0f}Hz — strong indicator of low-bitrate transcode",
                    severity=Severity.CRITICAL.value,
                    metadata={"cutoff_freq": cutoff, "declared_format": fmt}
                )

        return None