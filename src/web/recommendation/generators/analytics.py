"""
Analytics recommendation generators.

Extracted from recommendation_helper.py — tax drivers, complexity routing,
rules-based recommendations, real-time estimation, CPA knowledge, and adaptive questions.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_int, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import TAX_YEAR, STANDARD_DEDUCTIONS

logger = logging.getLogger(__name__)


def get_tax_drivers_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Analyze and report on the primary tax drivers for this profile."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    if agi <= 0:
        return recs

    drivers = []
    w2_wages = safe_float(profile.get("w2_wages", 0))
    se_income = safe_float(profile.get("self_employment_income", 0))
    investment_income = safe_float(profile.get("investment_income", 0))
    rental_income = safe_float(profile.get("rental_income", 0))

    if w2_wages > 0:
        drivers.append(("W-2 Wages", w2_wages, w2_wages / agi))
    if se_income > 0:
        drivers.append(("Self-Employment", se_income, se_income / agi))
    if investment_income > 0:
        drivers.append(("Investments", investment_income, investment_income / agi))
    if rental_income > 0:
        drivers.append(("Rental Income", rental_income, rental_income / agi))

    drivers.sort(key=lambda x: x[1], reverse=True)

    if drivers:
        top = drivers[0]
        recs.append(create_recommendation(
            title=f"Primary Tax Driver: {top[0]}",
            description=f"{top[0]} at ${top[1]:,.0f} represents {top[2]:.0%} of your AGI. Focus optimization efforts here.",
            potential_savings=top[1] * 0.02,
            category="planning",
            priority="medium",
            action_items=[
                f"Explore deductions and credits related to {top[0].lower()}",
                "Consider income shifting or deferral strategies",
            ],
        ))

    return recs


def get_complexity_router_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Route to appropriate complexity level of recommendations."""
    recs = []

    # Assess complexity
    complexity_factors = 0
    if safe_float(profile.get("self_employment_income", 0)) > 0:
        complexity_factors += 1
    if safe_int(profile.get("rental_properties", 0)) > 0:
        complexity_factors += 1
    if safe_float(profile.get("foreign_income", 0)) > 0:
        complexity_factors += 2
    if safe_float(profile.get("investment_income", 0)) > 50000:
        complexity_factors += 1
    if safe_int(profile.get("num_dependents", 0)) > 3:
        complexity_factors += 1
    if safe_float(profile.get("agi", 0)) > 500000:
        complexity_factors += 1

    if complexity_factors >= 4:
        recs.append(create_recommendation(
            title="Complex Tax Situation Detected",
            description="Your tax profile has multiple complexity factors. Professional assistance is strongly recommended.",
            potential_savings=safe_float(profile.get("agi", 0)) * 0.03,
            category="compliance",
            priority="high",
            action_items=[
                "Schedule appointment with a CPA or Enrolled Agent",
                "Consider year-round tax planning engagement",
                "Prepare comprehensive document package",
            ],
        ))

    return recs


def get_rules_based_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate rule-based recommendations from tax rules engine."""
    recs = []

    # This is a pass-through to the tax rules engine
    # In production, it integrates with the validation/tax_rules_engine.py
    try:
        from validation.tax_rules_engine import TaxRulesEngine
        # Rules engine integration would go here
    except ImportError:
        pass

    return recs


def get_realtime_estimator_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate real-time tax estimation recommendations."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    filing_status = safe_str(profile.get("filing_status", "single")).lower()

    if agi <= 0:
        return recs

    std_deduction = STANDARD_DEDUCTIONS.get(filing_status, STANDARD_DEDUCTIONS.get("single", 15750))
    taxable_income = max(0, agi - std_deduction)

    # Quick estimate
    estimated_tax = taxable_income * estimate_marginal_rate(profile) * 0.7  # Rough effective rate

    recs.append(create_recommendation(
        title="Quick Tax Estimate",
        description=f"Estimated federal tax: ${estimated_tax:,.0f} on taxable income of ${taxable_income:,.0f}.",
        potential_savings=0,
        category="planning",
        priority="low",
        metadata={"estimated_tax": estimated_tax, "taxable_income": taxable_income},
    ))

    return recs


def get_cpa_knowledge_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate CPA knowledge-based recommendations."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    filing_status = safe_str(profile.get("filing_status", "single")).lower()

    # Common missed opportunities
    has_w2 = safe_float(profile.get("w2_wages", 0)) > 0
    has_hsa = profile.get("has_hdhp", False)

    if has_w2 and has_hsa and safe_float(profile.get("hsa_contribution", 0)) == 0:
        max_hsa = 4300 if "married" not in filing_status else 8550
        recs.append(create_recommendation(
            title="Unused HSA Contribution Opportunity",
            description=f"You have an HDHP but haven't contributed to your HSA. Max contribution: ${max_hsa:,.0f}.",
            potential_savings=max_hsa * estimate_marginal_rate(profile),
            category="deductions",
            priority="high",
            action_items=[
                f"Contribute up to ${max_hsa:,.0f} to your HSA",
                "Contributions are above-the-line (reduce AGI)",
                "You have until April 15 to contribute for the prior year",
            ],
        ))

    return recs


def get_adaptive_question_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate adaptive follow-up question recommendations based on profile gaps."""
    recs = []

    # Identify missing profile data that could unlock recommendations
    gaps = []
    if not profile.get("filing_status"):
        gaps.append("filing status")
    if not profile.get("agi") and not profile.get("w2_wages"):
        gaps.append("income information")
    if profile.get("num_dependents") is None:
        gaps.append("dependent information")

    if gaps:
        recs.append(create_recommendation(
            title="Complete Your Profile for Better Recommendations",
            description=f"We need more information to provide targeted advice: {', '.join(gaps)}.",
            potential_savings=0,
            category="planning",
            priority="low",
            metadata={"missing_fields": gaps},
        ))

    return recs
