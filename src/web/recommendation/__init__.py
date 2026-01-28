"""
Tax Recommendation Engine

SPEC-006: Modular recommendation system for tax optimization.

This package provides comprehensive tax recommendations based on user profiles.

Usage:
    from web.recommendation import get_recommendations, get_recommendations_sync

    # Async
    result = await get_recommendations(profile)

    # Sync
    result = get_recommendations_sync(profile)

Structure:
- models.py: Data classes (UnifiedRecommendation, RecommendationResult)
- constants.py: Tax year limits and thresholds
- utils.py: Helper functions (safe_float, validate_profile, etc.)
- generators/: Recommendation generators by domain
- orchestrator.py: Main entry point and deduplication
"""

# Re-export main interfaces
from .models import UnifiedRecommendation, RecommendationResult
from .orchestrator import get_recommendations, get_recommendations_sync
from .utils import (
    safe_float,
    safe_int,
    safe_str,
    safe_decimal,
    validate_profile,
    create_recommendation,
    estimate_marginal_rate,
    get_urgency_info,
    get_lead_score,
)
from .constants import (
    TAX_YEAR,
    STANDARD_DEDUCTIONS,
    TAX_BRACKETS,
    RETIREMENT_LIMITS,
    CREDIT_LIMITS,
    DEDUCTION_LIMITS,
    get_standard_deduction,
)

__all__ = [
    # Main interfaces
    "get_recommendations",
    "get_recommendations_sync",
    # Models
    "UnifiedRecommendation",
    "RecommendationResult",
    # Utilities
    "safe_float",
    "safe_int",
    "safe_str",
    "safe_decimal",
    "validate_profile",
    "create_recommendation",
    "estimate_marginal_rate",
    "get_urgency_info",
    "get_lead_score",
    # Constants
    "TAX_YEAR",
    "STANDARD_DEDUCTIONS",
    "TAX_BRACKETS",
    "RETIREMENT_LIMITS",
    "CREDIT_LIMITS",
    "DEDUCTION_LIMITS",
    "get_standard_deduction",
]
