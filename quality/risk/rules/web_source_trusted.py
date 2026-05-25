"""
Rule: WEB source trust bonus.

WEB sources (Bandcamp, Qobuz, Tidal, etc.) are generally more reliable
than CD rips because they come directly from the label/distributor's
digital master. This rule applies a negative score delta (risk reduction)
to WEB-sourced releases.
"""

from __future__ import annotations

from quality.models import AudioContext, RuleResult, Severity
from quality.risk.base import BaseRule


class WebSourceTrustedRule(BaseRule):
    """Apply risk reduction for trusted WEB sources."""

    name = "web_source_trusted"
    description = "Reduces risk score for WEB-sourced releases (Bandcamp, Qobuz, etc.)"

    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Apply a negative score delta for WEB sources.

        WEB releases don't suffer from ripping errors, drive offsets,
        or other physical media issues. The main risk is re-encoding
        (MP3→FLAC), which is caught by other rules.
        """
        source = (ctx.source or "").upper()
        if source != "WEB":
            return None

        metadata = {"source": ctx.source}

        return RuleResult(
            rule_name=self.name,
            score_delta=-10,
            reason="WEB source — generally more reliable than physical media rips",
            severity=Severity.INFO.value,
            metadata=metadata,
        )
