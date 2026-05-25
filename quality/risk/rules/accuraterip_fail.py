"""
Rule: AccurateRip verification failure.

Checks the log analysis flags to determine if AccurateRip verification
failed. A failed AccurateRip check means the extracted audio cannot be
verified against the AccurateRip database, increasing the risk of
bit-imperfect rips.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class AccurateRipFailRule(BaseRule):
    """Detect failed AccurateRip verification in ripping logs."""

    name = "accuraterip_fail"
    description = "Flags releases where AccurateRip verification failed"

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Check if AccurateRip verification failed.

        Relies on structured flags from the log parser. Only triggers
        when a log is present and has been analyzed.
        """
        if not ctx.has_log or ctx.log_analysis is None:
            return None

        flags = ctx.log_analysis.flags

        # If AccurateRip status is not in flags, we can't determine
        ar_ok = flags.get("accuraterip_ok")
        if ar_ok is None:
            return None

        metadata = {
            "accuraterip_ok": ar_ok,
            "log_type": ctx.log_analysis.log_type,
            "log_score": ctx.log_analysis.score,
        }

        if ar_ok:
            # AccurateRip passed — this is a positive signal
            return None

        # AccurateRip failed
        log_score = ctx.log_analysis.score

        if log_score < 80:
            return RuleResult(
                rule_name=self.name,
                score_delta=30,
                reason="AccurateRip verification failed and log score is low — rip quality is questionable",
                severity=Severity.CRITICAL.value,
                metadata=metadata,
            )
        else:
            return RuleResult(
                rule_name=self.name,
                score_delta=15,
                reason="AccurateRip verification failed — rip integrity not verified against database",
                severity=Severity.WARNING.value,
                metadata=metadata,
            )
