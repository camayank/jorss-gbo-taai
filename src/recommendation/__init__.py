"""Tax Recommendation Engine.

This module provides intelligent analysis and recommendations for:
- Filing status optimization
- Deduction strategy (standard vs itemized)
- Credit eligibility and optimization
- Tax-saving strategies
- State-specific benefits
"""

from .recommendation_engine import TaxRecommendationEngine
from .filing_status_optimizer import FilingStatusOptimizer
from .deduction_analyzer import DeductionAnalyzer
from .credit_optimizer import CreditOptimizer
from .tax_strategy_advisor import TaxStrategyAdvisor
from .tax_rules_engine import TaxRulesEngine, TaxRule, RuleCategory, RuleSeverity
from .entity_optimizer import (
    EntityStructureOptimizer,
    EntityType,
    EntityAnalysis,
    EntityComparisonResult,
    ReasonableSalaryAnalysis,
)

__all__ = [
    "TaxRecommendationEngine",
    "FilingStatusOptimizer",
    "DeductionAnalyzer",
    "CreditOptimizer",
    "TaxStrategyAdvisor",
    "TaxRulesEngine",
    "TaxRule",
    "RuleCategory",
    "RuleSeverity",
    # Entity structure optimization
    "EntityStructureOptimizer",
    "EntityType",
    "EntityAnalysis",
    "EntityComparisonResult",
    "ReasonableSalaryAnalysis",
]
