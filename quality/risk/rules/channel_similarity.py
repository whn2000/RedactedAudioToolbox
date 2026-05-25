"""
Rule: L/R channel similarity detection.

Detects abnormally identical left and right channels in stereo files.
While some music (especially older recordings) has similar channels,
extremely high similarity across all frequencies is suspicious and
may indicate mono content padded to stereo, or processing artifacts.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class ChannelSimilarityRule(BaseRule):
    """Detect abnormally identical L/R channels."""

    name = "channel_similarity"
    description = "Flags stereo files with abnormally identical L/R channels"

    _CRITICAL_THRESHOLD = 0.98
    _WARNING_THRESHOLD = 0.95
    _INFO_THRESHOLD = 0.90

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Check if L/R channels are suspiciously identical.

        Very high similarity (>0.95) across all frequencies is unusual
        for properly mastered stereo music and may indicate processing
        problems or mono-to-stereo padding.
        """
        similarity = ctx.features.channel_similarity
        if similarity is None:
            return None

        metadata = {"channel_similarity": similarity}

        if similarity >= self._CRITICAL_THRESHOLD:
            return RuleResult(
                rule_name=self.name,
                score_delta=25,
                reason=f"L/R channels are nearly identical (similarity={similarity:.4f}) — "
                       "may be mono content or processing artifact",
                severity=Severity.WARNING.value,
                metadata=metadata,
            )
        elif similarity >= self._WARNING_THRESHOLD:
            return RuleResult(
                rule_name=self.name,
                score_delta=15,
                reason=f"L/R channels have very high similarity ({similarity:.4f})",
                severity=Severity.WARNING.value,
                metadata=metadata,
            )
        elif similarity >= self._INFO_THRESHOLD:
            return RuleResult(
                rule_name=self.name,
                score_delta=5,
                reason=f"L/R channels show moderate similarity ({similarity:.4f}) — may be normal for this genre",
                severity=Severity.INFO.value,
                metadata=metadata,
            )

        return None
