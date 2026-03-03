"""
Backward-compatibility shim for recommendation_helper.

All implementation has moved to the modular ``web.recommendation`` package.
Import from there for new code::

    from web.recommendation import get_recommendations, get_recommendations_sync
"""

from web.recommendation import (  # noqa: F401
    get_recommendations,
    get_recommendations_sync,
    enrich_calculation_with_recommendations,
    UnifiedRecommendation,
    RecommendationResult,
)
