"""Tax Recommendation Engine.

This module provides intelligent analysis and recommendations for:
- Filing status optimization
- Deduction strategy (standard vs itemized)
- Credit eligibility and optimization
- Tax-saving strategies
- State-specific benefits
- Real-time tax estimates from minimal data
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
from .ai_enhancer import (
    AIRecommendationEnhancer,
    AIEnhancedRecommendation,
    AIRecommendationSummary,
    get_ai_enhancer,
)
from .realtime_estimator import (
    RealTimeEstimator,
    TaxEstimate,
    EstimateConfidence,
    quick_estimate_from_w2,
    get_refund_range,
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
    # AI enhancement
    "AIRecommendationEnhancer",
    "AIEnhancedRecommendation",
    "AIRecommendationSummary",
    "get_ai_enhancer",
    # Real-time estimation
    "RealTimeEstimator",
    "TaxEstimate",
    "EstimateConfidence",
    "quick_estimate_from_w2",
    "get_refund_range",
]
