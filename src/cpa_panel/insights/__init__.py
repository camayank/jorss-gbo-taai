"""
CPA Insights Module

Provides CPA-specific insights and recommendations:
- Review checklists
- Risk indicators
- Compliance alerts
- Optimization opportunities
"""

from .cpa_insights import (
    CPAInsightsEngine,
    CPAInsight,
    InsightCategory,
    InsightPriority,
)

__all__ = [
    "CPAInsightsEngine",
    "CPAInsight",
    "InsightCategory",
    "InsightPriority",
]
