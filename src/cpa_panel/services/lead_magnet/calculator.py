"""
Lead magnet tax calculation and scoring logic.

Extracted from LeadMagnetService:
- _detect_complexity()
- _parse_income_range()
- _estimate_marginal_rate()
- _calculate_lead_score()
- _build_tax_health_score()
- _generate_insights()
"""

import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, date, timezone

logger = logging.getLogger(__name__)

# These are imported by the main service; we re-export for convenience
from cpa_panel.services.lead_magnet_service import (
    TaxProfile,
    TaxComplexity,
    TaxInsight,
    FilingStatus,
    IncomeSource,
    LifeEvent,
    LeadTemperature,
    STATE_DISPLAY_NAMES,
    HIGH_TAX_STATES,
    PROPERTY_TAX_HEAVY_STATES,
)

try:
    from cpa_panel.config.lead_magnet_score_config import SCORE_BENCHMARKS, get_score_weights
except ImportError:
    SCORE_BENCHMARKS = {}
    def get_score_weights():
        return {}


def detect_complexity(profile: TaxProfile) -> TaxComplexity:
    """
    Detect tax complexity from profile.

    Rules:
    - SIMPLE: W-2 only + standard deduction signals
    - MODERATE: Multiple W-2s OR investments OR homeowner
    - COMPLEX: Self-employment OR rental OR multi-state
    - PROFESSIONAL: Business owner + high income (>$200k) OR complex + high income
    """
    sources = set(profile.income_sources)
    income = parse_income_range(profile.income_range)

    has_self_employed = IncomeSource.SELF_EMPLOYED in sources
    has_rental = IncomeSource.RENTAL in sources
    has_investments = IncomeSource.INVESTMENTS in sources
    has_business = profile.has_business or has_self_employed
    high_income = income >= 200000
    very_high_income = income >= 500000

    if very_high_income and (has_business or has_rental or has_investments):
        return TaxComplexity.PROFESSIONAL
    if high_income and has_business:
        return TaxComplexity.PROFESSIONAL
    if has_business and has_rental and has_investments:
        return TaxComplexity.PROFESSIONAL
    if has_self_employed or has_rental or has_business:
        return TaxComplexity.COMPLEX
    if LifeEvent.BUSINESS_START in profile.life_events:
        return TaxComplexity.COMPLEX
    multiple_sources = len(sources) > 1
    if multiple_sources or has_investments or profile.is_homeowner:
        return TaxComplexity.MODERATE
    return TaxComplexity.SIMPLE


def parse_income_range(range_str: str) -> int:
    """Parse income range string to a representative integer."""
    if not range_str:
        return 50000

    range_str = range_str.strip().lower()

    # Direct numeric
    try:
        clean = range_str.replace("$", "").replace(",", "").replace("k", "000")
        return int(float(clean))
    except (ValueError, TypeError):
        pass

    # Named ranges
    range_map = {
        "under_25k": 20000,
        "25k_50k": 37500,
        "50k_75k": 62500,
        "75k_100k": 87500,
        "100k_150k": 125000,
        "150k_200k": 175000,
        "200k_500k": 350000,
        "500k_plus": 750000,
        "over_500k": 750000,
        "1m_plus": 1500000,
        "over_1m": 1500000,
    }

    for key, val in range_map.items():
        if key in range_str:
            return val

    return 50000


def estimate_marginal_rate(income: int, filing_status: FilingStatus) -> float:
    """Estimate marginal tax rate (2025 brackets)."""
    if filing_status == FilingStatus.MARRIED_JOINTLY:
        if income < 23850:
            return 0.10
        elif income < 96950:
            return 0.12
        elif income < 206700:
            return 0.22
        elif income < 394600:
            return 0.24
        else:
            return 0.32
    else:
        if income < 11925:
            return 0.10
        elif income < 48475:
            return 0.12
        elif income < 103350:
            return 0.22
        elif income < 197300:
            return 0.24
        else:
            return 0.32


def calculate_lead_score(
    profile: TaxProfile,
    complexity: TaxComplexity,
    insights: List[TaxInsight],
    time_spent_seconds: int = 0,
) -> Tuple[int, LeadTemperature, float]:
    """
    Calculate lead score for CPA engagement prioritization.

    Returns (score 0-100, temperature, estimated_engagement_value).
    """
    score = 0
    weights = get_score_weights()

    # Complexity weight (higher complexity = higher value to CPA)
    complexity_weights = {
        TaxComplexity.SIMPLE: 10,
        TaxComplexity.MODERATE: 25,
        TaxComplexity.COMPLEX: 45,
        TaxComplexity.PROFESSIONAL: 60,
    }
    score += complexity_weights.get(complexity, 10)

    # Income weight
    income = parse_income_range(profile.income_range)
    if income >= 500000:
        score += 20
    elif income >= 200000:
        score += 15
    elif income >= 100000:
        score += 10
    elif income >= 50000:
        score += 5

    # Savings potential weight
    total_savings = sum(i.savings_high for i in insights)
    if total_savings >= 10000:
        score += 15
    elif total_savings >= 5000:
        score += 10
    elif total_savings >= 1000:
        score += 5

    # Engagement signals
    if time_spent_seconds > 300:  # > 5 minutes
        score += 5
    elif time_spent_seconds > 120:  # > 2 minutes
        score += 3

    # Cap at 100
    score = min(score, 100)

    # Temperature
    if score >= 70:
        temperature = LeadTemperature.HOT
    elif score >= 40:
        temperature = LeadTemperature.WARM
    else:
        temperature = LeadTemperature.COLD

    # Engagement value estimate (based on complexity)
    engagement_values = {
        TaxComplexity.SIMPLE: 250,
        TaxComplexity.MODERATE: 500,
        TaxComplexity.COMPLEX: 1000,
        TaxComplexity.PROFESSIONAL: 2500,
    }
    engagement_value = float(engagement_values.get(complexity, 250))

    return score, temperature, engagement_value


def build_tax_health_score(
    profile: Optional[TaxProfile],
    complexity: TaxComplexity,
    insights: List[TaxInsight],
    savings_low: float,
    savings_high: float,
) -> Dict[str, Any]:
    """
    Build a tax health score payload for the report.

    Returns a dict with overall score, band, and breakdown.
    """
    if not profile:
        return {
            "overall": 50,
            "band": "average",
            "breakdown": {},
            "message": "Complete your profile for a personalized score.",
        }

    # Score components (0-100 each)
    income = parse_income_range(profile.income_range)

    # Retirement readiness
    retirement_score = 30  # baseline
    if profile.retirement_savings == "maxed":
        retirement_score = 95
    elif profile.retirement_savings == "some":
        retirement_score = 60
    elif profile.retirement_savings == "employer_match":
        retirement_score = 50

    # Deduction optimization
    deduction_score = 50  # baseline
    if profile.is_homeowner:
        deduction_score += 15
    if IncomeSource.SELF_EMPLOYED in profile.income_sources:
        deduction_score += 10

    # Credit utilization
    credit_score = 50
    if profile.children_under_17:
        credit_score += 20
    if profile.healthcare_type == "hdhp_hsa":
        credit_score += 15

    # Complexity handling
    complexity_penalty = {
        TaxComplexity.SIMPLE: 0,
        TaxComplexity.MODERATE: 5,
        TaxComplexity.COMPLEX: 10,
        TaxComplexity.PROFESSIONAL: 15,
    }
    penalty = complexity_penalty.get(complexity, 0)

    # Overall weighted score
    overall = int(
        retirement_score * 0.30
        + deduction_score * 0.25
        + credit_score * 0.25
        + (100 - penalty) * 0.20
    )
    overall = max(10, min(100, overall))

    # Band
    if overall >= 80:
        band = "excellent"
        message = "Your tax strategy is well-optimized!"
    elif overall >= 60:
        band = "good"
        message = "Good foundation with room for improvement."
    elif overall >= 40:
        band = "average"
        message = "Several optimization opportunities available."
    else:
        band = "needs_attention"
        message = "Significant tax savings opportunities identified."

    # State tax efficiency score
    state_code = getattr(profile, "state_code", None) or ""
    state_tax_efficiency = 40 if state_code in HIGH_TAX_STATES else 65

    avg_taxpayer = SCORE_BENCHMARKS.get("average_taxpayer", SCORE_BENCHMARKS.get("average_score", 52))
    cpa_optimized = SCORE_BENCHMARKS.get("cpa_optimized_target", SCORE_BENCHMARKS.get("cpa_planned_average", 78))
    cpa_planned = SCORE_BENCHMARKS.get("cpa_planned_average", cpa_optimized)

    return {
        "overall": overall,
        "band": band,
        "message": message,
        "missed_savings_range": f"${int(savings_low):,} - ${int(savings_high):,}",
        "breakdown": {
            "retirement_readiness": retirement_score,
            "deduction_optimization": min(100, deduction_score),
            "credit_utilization": min(100, credit_score),
        },
        "savings_range": {
            "low": int(savings_low),
            "high": int(savings_high),
        },
        "benchmark": {
            "average_taxpayer": avg_taxpayer,
            "average_score": avg_taxpayer,
            "cpa_planned_average": cpa_planned,
            "cpa_optimized_target": cpa_optimized,
        },
        "subscores": {
            "retirement_readiness": retirement_score,
            "deduction_optimization": min(100, deduction_score),
            "credit_utilization": min(100, credit_score),
            "complexity_handling": max(0, 100 - penalty),
            "state_tax_efficiency": state_tax_efficiency,
        },
    }
