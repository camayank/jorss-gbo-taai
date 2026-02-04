"""
Penalty and AMT recommendation generators.

Extracted from recommendation_helper.py — AMT risk assessment
and estimated tax penalty avoidance.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_int, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import TAX_YEAR, AMT_LIMITS

logger = logging.getLogger(__name__)


def get_amt_risk_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate AMT risk assessment recommendations."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    filing_status = safe_str(profile.get("filing_status", "single")).lower()
    state_local_taxes = safe_float(profile.get("state_local_taxes", 0))
    iso_exercises = safe_float(profile.get("iso_exercises", 0))

    exemption = AMT_LIMITS.get("exemption_mfj", 137000) if "married" in filing_status and "joint" in filing_status else AMT_LIMITS.get("exemption_single", 88100)

    # High SALT + high income = AMT risk
    if state_local_taxes > 10000 and agi > 200000:
        recs.append(create_recommendation(
            title="Alternative Minimum Tax (AMT) Risk",
            description="Your high state/local taxes and income level may trigger AMT. Plan accordingly.",
            potential_savings=2000,
            category="amt",
            priority="high",
            action_items=[
                "Run AMT calculation with your CPA",
                "Consider timing of deductions that are AMT preference items",
                "SALT deduction is limited to $10,000 under both regular and AMT",
            ],
            warnings=["AMT can increase your tax liability significantly"],
        ))

    # ISO exercise AMT impact
    if iso_exercises > 0:
        amt_impact = iso_exercises * 0.26
        recs.append(create_recommendation(
            title="ISO Exercise AMT Impact",
            description=f"Your ISO exercises of ${iso_exercises:,.0f} could trigger ${amt_impact:,.0f} in AMT.",
            potential_savings=amt_impact * 0.3,
            category="amt",
            priority="critical",
            action_items=[
                "Calculate AMT impact before exercising more ISOs",
                "Consider spreading exercises across tax years",
                "Track AMT credit carryforward for future years",
                "Consider disqualifying disposition if AMT impact is too high",
            ],
        ))

    return recs


def get_estimated_tax_penalty_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate estimated tax penalty avoidance recommendations."""
    recs = []

    self_employment_income = safe_float(profile.get("self_employment_income", 0))
    investment_income = safe_float(profile.get("investment_income", 0))
    tax_withheld = safe_float(profile.get("federal_withholding", 0))
    estimated_payments = safe_float(profile.get("estimated_tax_payments", 0))
    prior_year_tax = safe_float(profile.get("prior_year_tax", 0))
    agi = safe_float(profile.get("agi", 0))

    # Check if estimated payments are needed
    non_withheld_income = self_employment_income + investment_income
    if non_withheld_income < 1000:
        return recs

    total_payments = tax_withheld + estimated_payments
    estimated_liability = agi * estimate_marginal_rate(profile)

    safe_harbor = max(prior_year_tax, estimated_liability * 0.90) if prior_year_tax > 0 else estimated_liability * 0.90
    if agi > 150000 and prior_year_tax > 0:
        safe_harbor = max(prior_year_tax * 1.10, estimated_liability * 0.90)

    if total_payments < safe_harbor * 0.80:
        shortfall = safe_harbor - total_payments
        recs.append(create_recommendation(
            title="Estimated Tax Payment Shortfall",
            description=f"You may owe an underpayment penalty. Consider making estimated payments of ${shortfall:,.0f} to reach safe harbor.",
            potential_savings=shortfall * 0.08,
            category="penalty",
            priority="critical",
            action_items=[
                "Make estimated payment by next quarterly deadline",
                f"Safe harbor amount: ${safe_harbor:,.0f}",
                "Consider increasing W-2 withholding if employed",
                "Use IRS Form 2210 to calculate exact penalty",
            ],
            warnings=["Underpayment penalty rate is currently ~8%"],
        ))

    return recs
