"""
Rule: Missing ripping log detection.

CD-sourced releases should include a ripping log (EAC or XLD) as proof
of extraction quality. Absence of a log for CD sources is a red flag
that the source may be unreliable.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class NoLogRule(BaseRule):
    """Detect CD-sourced releases without a ripping log."""

    name = "no_log"
    description = "Flags CD-sourced releases missing a ripping log"

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Check if a CD source is missing its ripping log.

        Only applies when the source is CD/Vinyl. WEB sources do not
        require ripping logs and are not flagged.
        """
        # Only relevant for CD/Vinyl sources
        source = (ctx.source or "").upper()
        if source not in ("CD", "VINYL", ""):
            return None

        # If source is explicitly WEB or similar, skip
        if source in ("WEB", "SACD", "SOUNDBOARD", "DAT", "CASSETTE"):
            return None

        if ctx.has_log:
            return None

        # No log present for a CD source
        metadata = {"source": ctx.source or "unknown", "has_log": False}

        if source == "CD":
            return RuleResult(
                rule_name=self.name,
                score_delta=20,
                reason="CD source without ripping log — extraction quality is unverifiable",
                severity=Severity.WARNING.value,
                metadata=metadata,
            )
        elif source == "VINYL":
            return RuleResult(
                rule_name=self.name,
                score_delta=10,
                reason="Vinyl source without log — minor concern",
                severity=Severity.INFO.value,
                metadata=metadata,
            )

        # Unknown source without log — moderate concern
        return RuleResult(
            rule_name=self.name,
            score_delta=15,
            reason="Unknown source without ripping log",
            severity=Severity.WARNING.value,
            metadata=metadata,
        )
