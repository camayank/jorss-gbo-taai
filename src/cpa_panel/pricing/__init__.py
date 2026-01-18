"""
CPA Engagement Pricing Module

Provides complexity-based pricing guidance for CPA engagements.

IMPORTANT: This is NOT an e-filing platform. This module provides
pricing guidance for CPA advisory services, not tax filing services.
"""

from .complexity_pricing import (
    ComplexityTier,
    PricingGuidance,
    EngagementPricingEngine,
)

__all__ = [
    "ComplexityTier",
    "PricingGuidance",
    "EngagementPricingEngine",
]
