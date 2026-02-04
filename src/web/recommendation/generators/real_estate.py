"""
Real estate recommendation generators.

Extracted from recommendation_helper.py — home sale exclusion,
1031 exchanges, installment sales, passive activity losses, rental depreciation.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_int, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import TAX_YEAR

logger = logging.getLogger(__name__)


def get_home_sale_exclusion_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate home sale exclusion recommendations."""
    recs = []

    home_sale_gain = safe_float(profile.get("home_sale_gain", 0))
    filing_status = safe_str(profile.get("filing_status", "single")).lower()

    if home_sale_gain <= 0:
        return recs

    exclusion = 500000 if "married" in filing_status and "joint" in filing_status else 250000

    if home_sale_gain <= exclusion:
        recs.append(create_recommendation(
            title="Home Sale Exclusion (Section 121)",
            description=f"Your home sale gain of ${home_sale_gain:,.0f} is fully excludable (limit: ${exclusion:,.0f}).",
            potential_savings=home_sale_gain * 0.15,
            category="real_estate",
            priority="high",
            action_items=[
                "Verify you owned and lived in the home for 2 of the last 5 years",
                "Ensure you haven't used the exclusion in the last 2 years",
            ],
        ))
    else:
        taxable = home_sale_gain - exclusion
        recs.append(create_recommendation(
            title="Partial Home Sale Exclusion",
            description=f"Exclude ${exclusion:,.0f} of your ${home_sale_gain:,.0f} gain. ${taxable:,.0f} will be taxable.",
            potential_savings=exclusion * 0.15,
            category="real_estate",
            priority="high",
            action_items=[
                "Consider installment sale to spread gain over multiple years",
                "Offset with capital losses if available",
            ],
        ))

    return recs


def get_1031_exchange_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate 1031 like-kind exchange recommendations."""
    recs = []

    rental_properties = safe_int(profile.get("rental_properties", 0))
    rental_income = safe_float(profile.get("rental_income", 0))
    planning_to_sell = profile.get("planning_to_sell_property", False)

    if rental_properties <= 0 and not planning_to_sell:
        return recs

    if planning_to_sell or rental_properties > 1:
        estimated_gain = safe_float(profile.get("property_gain_estimate", 100000))
        savings = estimated_gain * 0.20
        recs.append(create_recommendation(
            title="1031 Like-Kind Exchange",
            description="Defer capital gains tax by exchanging investment property for similar property.",
            potential_savings=savings,
            category="real_estate",
            priority="high",
            complexity="complex",
            action_items=[
                "Identify replacement property within 45 days of sale",
                "Complete exchange within 180 days",
                "Use a qualified intermediary — cannot touch proceeds",
                "Both properties must be held for investment or business use",
            ],
            warnings=["Strict timeline requirements", "Personal residences do not qualify"],
        ))

    return recs


def get_installment_sale_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate installment sale recommendations."""
    recs = []

    large_asset_sale = safe_float(profile.get("large_asset_sale", 0))
    if large_asset_sale <= 50000:
        return recs

    marginal_rate = estimate_marginal_rate(profile)
    savings = large_asset_sale * marginal_rate * 0.15

    recs.append(create_recommendation(
        title="Installment Sale Strategy",
        description=f"Spread the ${large_asset_sale:,.0f} gain over multiple years to stay in lower tax brackets.",
        potential_savings=savings,
        category="real_estate",
        priority="medium",
        complexity="complex",
        action_items=[
            "Structure sale with payments over 2+ tax years",
            "Calculate optimal payment schedule with CPA",
            "Consider interest rate implications",
        ],
    ))

    return recs


def get_passive_activity_loss_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate passive activity loss recommendations."""
    recs = []

    rental_losses = safe_float(profile.get("rental_losses", 0))
    agi = safe_float(profile.get("agi", 0))

    if rental_losses <= 0:
        return recs

    if agi <= 100000:
        deductible = min(rental_losses, 25000)
        recs.append(create_recommendation(
            title="Rental Loss Deduction (Active Participation)",
            description=f"Deduct up to ${deductible:,.0f} in rental losses against ordinary income.",
            potential_savings=deductible * estimate_marginal_rate(profile),
            category="real_estate",
            priority="high",
            action_items=[
                "Document active participation in rental management",
                "Keep records of time spent on rental activities",
            ],
        ))
    elif agi <= 150000:
        phase_out_pct = (agi - 100000) / 50000
        deductible = min(rental_losses, 25000) * (1 - phase_out_pct)
        if deductible > 0:
            recs.append(create_recommendation(
                title="Partial Rental Loss Deduction",
                description=f"Deduct approximately ${deductible:,.0f} (phase-out applies at your income level).",
                potential_savings=deductible * estimate_marginal_rate(profile),
                category="real_estate",
                priority="medium",
                action_items=["Consider Real Estate Professional status for full deduction"],
            ))

    return recs


def get_rental_depreciation_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate rental depreciation recommendations."""
    recs = []

    rental_properties = safe_int(profile.get("rental_properties", 0))
    rental_income = safe_float(profile.get("rental_income", 0))

    if rental_properties <= 0:
        return recs

    estimated_property_value = safe_float(profile.get("rental_property_value", 300000))
    land_pct = 0.20
    building_value = estimated_property_value * (1 - land_pct)
    annual_depreciation = building_value / 27.5

    recs.append(create_recommendation(
        title="Rental Property Depreciation",
        description=f"Claim approximately ${annual_depreciation:,.0f}/year in depreciation on your rental property.",
        potential_savings=annual_depreciation * estimate_marginal_rate(profile),
        category="real_estate",
        priority="high",
        action_items=[
            "Ensure depreciation is being claimed (27.5-year straight line for residential)",
            "Consider cost segregation study for accelerated depreciation",
            "Track improvements separately — they start a new depreciation schedule",
        ],
    ))

    return recs
