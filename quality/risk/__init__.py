"""
Risk scoring engine.

Provides the plugin-based risk assessment system including the base rule
class, auto-discovery registry, scoring engine, and all built-in rules.
"""

from quality.risk.engine import RiskEngine

__all__ = ["RiskEngine"]
