"""
Base class for all risk assessment rules.

Every rule must inherit from BaseRule and implement the evaluate() method.
Rules are auto-discovered by the registry and must NOT be registered manually.

Design principles:
- Rules are pure evaluators: they read AudioContext, they never modify it.
- Heavy computation (FFT, spectrogram analysis) belongs in features/.
- Rules consume pre-computed AudioFeatures via ctx.features.
- Each rule lives in its own file under risk/rules/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from quality.models import AudioContext, RuleResult


class BaseRule(ABC):
    """Abstract base class for risk assessment rules.

    Subclasses must define class-level ``name`` and ``description`` attributes,
    and implement the ``evaluate()`` method.

    Attributes:
        name: Machine-readable identifier (e.g., 'cutoff_22khz').
        description: Human-readable explanation of what the rule checks.
        enabled: Whether the rule is active. Can be toggled via config.
        weight: Multiplier for score_delta (default 1.0).
    """

    name: str = ""
    description: str = ""
    enabled: bool = True
    weight: float = 1.0

    @abstractmethod
    def evaluate(self, ctx: AudioContext) -> RuleResult | None:
        """Evaluate this rule against the given audio context.

        Args:
            ctx: Complete audio context including pre-computed features,
                log analysis, and metadata.

        Returns:
            A RuleResult if the rule triggers (positive or negative score),
            or None if the rule does not apply to this context.
        """

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<{self.__class__.__name__} '{self.name}' ({status}, weight={self.weight})>"
