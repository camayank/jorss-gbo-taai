"""
Credit recommendation generators.

Extracted from recommendation_helper.py — credit optimization,
education savings, and related generators.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_int, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import (
    TAX_YEAR, STANDARD_DEDUCTIONS, CREDIT_LIMITS, RETIREMENT_LIMITS,
)

logger = logging.getLogger(__name__)


def get_education_savings_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate education savings recommendations."""
    recs = []

    has_children = safe_int(profile.get("num_dependents", 0)) > 0
    has_education = safe_float(profile.get("education_expenses", 0)) > 0
    agi = safe_float(profile.get("agi", 0))

    if not has_children and not has_education:
        return recs

    # American Opportunity Tax Credit
    if has_education and agi < 180000:
        credit_amount = min(safe_float(profile.get("education_expenses", 0)), 4000)
        aotc = min(credit_amount * 0.25 + min(credit_amount, 2000), 2500)
        if aotc > 0:
            recs.append(create_recommendation(
                title="American Opportunity Tax Credit (AOTC)",
                description=f"You may qualify for up to ${aotc:,.0f} in education credits per student.",
                potential_savings=aotc,
                category="credits",
                priority="high" if aotc > 1000 else "medium",
                action_items=[
                    "Ensure you have Form 1098-T from eligible institution",
                    "Track qualified education expenses (tuition, fees, books)",
                    "Note: Available for first 4 years of postsecondary education",
                ],
            ))

    # 529 Plan
    if has_children:
        recs.append(create_recommendation(
            title="529 Education Savings Plan",
            description="Tax-advantaged savings for education. Earnings grow tax-free when used for qualified expenses.",
            potential_savings=500,
            category="credits",
            priority="medium",
            complexity="simple",
            action_items=[
                "Open a 529 plan in your state for possible state tax deduction",
                "Contribute regularly — no federal tax deduction but tax-free growth",
                "Can be used for K-12 tuition (up to $10,000/year) and college expenses",
            ],
        ))

    return recs
