"""
Unified Rules Engine Module.

This module provides a flexible, configuration-driven rule engine for:
- Tax calculation rules
- Validation rules
- Recommendation rules
- Eligibility rules

Rules can be defined in YAML configuration or dynamically via AI assistance.
"""

from .rule_engine import (
    Rule,
    RuleResult,
    RuleContext,
    RuleEngine,
    get_rule_engine,
)
from .rule_types import (
    RuleCategory,
    RuleSeverity,
    RuleType,
)

__all__ = [
    'Rule',
    'RuleResult',
    'RuleContext',
    'RuleEngine',
    'get_rule_engine',
    'RuleCategory',
    'RuleSeverity',
    'RuleType',
]
