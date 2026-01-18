"""
Practice Intelligence Dashboard

Lightweight analytics for CPA firm portfolio insights.

SCOPE BOUNDARIES (ENFORCED - DO NOT EXPAND):

ALLOWED (3 METRICS ONLY):
1. Advisory vs Compliance Mix - Distribution of engagement types
2. Complexity Tier Distribution - Count of returns by complexity
3. YoY Value Surface - Year-over-year comparison metrics

FORBIDDEN (DO NOT ADD - USE EXTERNAL PMS):
- Time tracking
- Staff productivity
- Revenue per staff
- Utilization metrics
- Billable hours
- Realization rates
- WIP tracking
- Staff performance metrics
- Capacity planning

This module provides READ-ONLY portfolio analytics.
For practice management features, integrate with Karbon, Canopy, or Jetpack.
"""

from .intelligence_service import (
    PracticeIntelligenceService,
    PortfolioMetrics,
    get_intelligence_service,
)

__all__ = [
    "PracticeIntelligenceService",
    "PortfolioMetrics",
    "get_intelligence_service",
]
