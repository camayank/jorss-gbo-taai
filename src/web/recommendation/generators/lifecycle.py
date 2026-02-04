"""
Lifecycle recommendation generators.

Extracted from recommendation_helper.py — filing status optimization,
timing strategies, and charitable strategies.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_int, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import TAX_YEAR, STANDARD_DEDUCTIONS

logger = logging.getLogger(__name__)


def get_filing_status_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate filing status optimization recommendations."""
    recs = []

    filing_status = safe_str(profile.get("filing_status", "single")).lower()
    has_dependents = safe_int(profile.get("num_dependents", 0)) > 0
    is_married = "married" in filing_status

    # HOH check for single with dependents
    if filing_status == "single" and has_dependents:
        single_std = STANDARD_DEDUCTIONS.get("single", 15750)
        hoh_std = STANDARD_DEDUCTIONS.get("head_of_household", 23850)
        savings = (hoh_std - single_std) * estimate_marginal_rate(profile)

        recs.append(create_recommendation(
            title="Consider Head of Household Filing Status",
            description=f"As a single filer with dependents, you may qualify for HOH status — saving approximately ${savings:,.0f} through a higher standard deduction.",
            potential_savings=savings,
            category="filing_status",
            priority="high",
            action_items=[
                "Verify you paid more than half the cost of maintaining your home",
                "Confirm qualifying person lived with you for more than half the year",
                "HOH gets higher standard deduction and wider tax brackets",
            ],
        ))

    # MFS to MFJ check
    if filing_status in ("married_separate", "married_filing_separately"):
        recs.append(create_recommendation(
            title="Compare Married Filing Jointly vs Separately",
            description="Filing jointly often results in lower taxes due to wider brackets and more credits.",
            potential_savings=2000,
            category="filing_status",
            priority="high",
            action_items=[
                "Calculate tax both ways to compare",
                "MFJ allows EITC, education credits, and student loan deduction",
                "MFS may be better if spouse has high medical expenses or student loans",
            ],
        ))

    return recs


def get_timing_strategy_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate income/deduction timing strategy recommendations."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    marginal_rate = estimate_marginal_rate(profile)
    self_employment_income = safe_float(profile.get("self_employment_income", 0))

    # Income deferral for high earners
    if agi > 200000 and self_employment_income > 0:
        recs.append(create_recommendation(
            title="Income Deferral Strategy",
            description="Consider deferring self-employment income to next year if you expect lower income.",
            potential_savings=self_employment_income * 0.05 * marginal_rate,
            category="timing",
            priority="medium",
            complexity="moderate",
            action_items=[
                "Delay billing or invoicing until next tax year",
                "Consider prepaying deductible expenses this year",
                "Evaluate whether next year's rate will be lower",
            ],
        ))

    # Bunching deductions
    itemized_total = safe_float(profile.get("total_itemized_deductions", 0))
    filing_status = safe_str(profile.get("filing_status", "single")).lower()
    std_ded = STANDARD_DEDUCTIONS.get(filing_status, STANDARD_DEDUCTIONS.get("single", 15750))

    if 0 < itemized_total < std_ded * 1.5:
        recs.append(create_recommendation(
            title="Deduction Bunching Strategy",
            description="Concentrate deductions into alternating years to exceed the standard deduction threshold.",
            potential_savings=(itemized_total - std_ded) * marginal_rate if itemized_total > std_ded else 500,
            category="timing",
            priority="medium",
            action_items=[
                "Prepay property taxes (within SALT cap)",
                "Make two years of charitable donations in one year",
                "Use donor-advised fund for charitable bunching",
                "Alternate between standard and itemized deductions",
            ],
        ))

    return recs


def get_charitable_strategy_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate charitable giving strategy recommendations."""
    recs = []

    charitable_donations = safe_float(profile.get("charitable_donations", 0))
    agi = safe_float(profile.get("agi", 0))
    age = safe_int(profile.get("age", 0))

    if charitable_donations <= 0 and agi < 100000:
        return recs

    marginal_rate = estimate_marginal_rate(profile)

    # Donor-advised fund
    if charitable_donations > 5000:
        recs.append(create_recommendation(
            title="Donor-Advised Fund (DAF)",
            description="Contribute to a DAF for an immediate tax deduction, then distribute to charities over time.",
            potential_savings=charitable_donations * marginal_rate * 0.3,
            category="charitable",
            priority="medium",
            action_items=[
                "Open a DAF at Fidelity Charitable, Schwab Charitable, or Vanguard",
                "Contribute appreciated stock to avoid capital gains",
                "Bunch multiple years of giving into one year",
            ],
        ))

    # Qualified Charitable Distribution (QCD) for 70.5+
    if age >= 70:
        recs.append(create_recommendation(
            title="Qualified Charitable Distribution (QCD)",
            description="Donate up to $105,000 directly from your IRA to charity. Counts toward RMD and is excluded from income.",
            potential_savings=min(charitable_donations, 105000) * marginal_rate,
            category="charitable",
            priority="high",
            action_items=[
                "Must be 70½ or older",
                "Transfer directly from IRA to qualifying charity",
                "Satisfies RMD requirement without increasing AGI",
            ],
        ))

    # Appreciated stock donation
    if agi > 100000 and charitable_donations > 1000:
        recs.append(create_recommendation(
            title="Donate Appreciated Securities",
            description="Donating appreciated stock avoids capital gains tax and provides a full fair-market-value deduction.",
            potential_savings=charitable_donations * 0.15,
            category="charitable",
            priority="medium",
            action_items=[
                "Identify long-term holdings with significant appreciation",
                "Donate directly to charity — do not sell first",
                "Deduction limited to 30% of AGI for appreciated property",
            ],
        ))

    return recs
