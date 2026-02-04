"""
Strategy recommendation generators.

Extracted from recommendation_helper.py — withholding optimization,
tax impact analysis, refund estimation, planning insights.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_int, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import TAX_YEAR, STANDARD_DEDUCTIONS

logger = logging.getLogger(__name__)


def get_withholding_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate withholding optimization recommendations."""
    recs = []

    federal_withholding = safe_float(profile.get("federal_withholding", 0))
    estimated_liability = safe_float(profile.get("estimated_tax_liability", 0))
    agi = safe_float(profile.get("agi", 0))

    if federal_withholding <= 0 or estimated_liability <= 0:
        return recs

    difference = federal_withholding - estimated_liability

    if difference > 2000:
        monthly_extra = difference / 12
        recs.append(create_recommendation(
            title="Reduce Withholding — You're Overpaying",
            description=f"You're over-withholding by ~${difference:,.0f}/year. Adjust W-4 to get ~${monthly_extra:,.0f}/month more in each paycheck.",
            potential_savings=difference * 0.05,
            category="withholding",
            priority="medium",
            complexity="simple",
            action_items=[
                "Submit updated W-4 to employer",
                "Use IRS Tax Withholding Estimator at irs.gov",
                "Consider investing the extra monthly cash flow",
            ],
        ))
    elif difference < -1000:
        recs.append(create_recommendation(
            title="Increase Withholding to Avoid Penalty",
            description=f"You may owe ${abs(difference):,.0f} at tax time. Increase withholding or make estimated payments.",
            potential_savings=abs(difference) * 0.08,
            category="withholding",
            priority="high",
            action_items=[
                "Submit updated W-4 with additional withholding",
                "Or make quarterly estimated tax payments",
                "Aim for safe harbor: 100% of prior year tax (110% if AGI > $150K)",
            ],
        ))

    return recs


def get_tax_impact_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate tax impact analysis recommendations."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    filing_status = safe_str(profile.get("filing_status", "single")).lower()
    marginal_rate = estimate_marginal_rate(profile)

    # Effective rate analysis
    total_tax = safe_float(profile.get("total_tax", 0))
    if agi > 0 and total_tax > 0:
        effective_rate = total_tax / agi
        if effective_rate > 0.30:
            recs.append(create_recommendation(
                title="High Effective Tax Rate",
                description=f"Your effective rate is {effective_rate:.1%} — consider strategies to reduce your tax burden.",
                potential_savings=agi * 0.02,
                category="planning",
                priority="high",
                action_items=[
                    "Maximize tax-advantaged retirement contributions",
                    "Review all available deductions and credits",
                    "Consider tax-efficient investment strategies",
                    "Consult with a CPA about advanced planning",
                ],
            ))

    return recs


def get_refund_estimator_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate refund estimation and optimization recommendations."""
    recs = []

    refund = safe_float(profile.get("estimated_refund", 0))
    balance_due = safe_float(profile.get("balance_due", 0))

    if refund > 3000:
        recs.append(create_recommendation(
            title="Large Refund — Consider Adjusting Withholding",
            description=f"Your estimated refund of ${refund:,.0f} means you've been giving the IRS an interest-free loan.",
            potential_savings=refund * 0.05,
            category="withholding",
            priority="medium",
            action_items=[
                "Adjust W-4 to reduce withholding",
                "Invest the extra cash flow throughout the year",
                "Target a small refund of $200-500",
            ],
        ))

    if balance_due > 5000:
        recs.append(create_recommendation(
            title="Payment Options for Balance Due",
            description=f"You may owe ${balance_due:,.0f}. Consider payment options to avoid penalties.",
            potential_savings=balance_due * 0.08,
            category="compliance",
            priority="critical",
            action_items=[
                "Pay by April 15 to avoid failure-to-pay penalty",
                "Apply for installment agreement if you can't pay in full",
                "Consider short-term payment plan (120 days) for smaller balances",
            ],
        ))

    return recs


def get_tax_strategy_advisor_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate comprehensive tax strategy advisor recommendations."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    age = safe_int(profile.get("age", 0))
    filing_status = safe_str(profile.get("filing_status", "single")).lower()

    # RMD planning
    if age >= 72:
        recs.append(create_recommendation(
            title="Required Minimum Distribution (RMD) Planning",
            description="You must take RMDs from traditional retirement accounts. Plan to minimize tax impact.",
            potential_savings=1000,
            category="retirement",
            priority="critical",
            action_items=[
                "Calculate RMD amount using IRS Uniform Lifetime Table",
                "Take RMD by December 31 (April 1 for first year only)",
                "Consider QCD to satisfy RMD while reducing AGI",
                "Evaluate Roth conversions to reduce future RMDs",
            ],
            warnings=["50% penalty on missed RMDs"],
        ))

    # Year-end planning
    recs.append(create_recommendation(
        title="Year-End Tax Planning Checklist",
        description="Review these strategies before December 31 to optimize your tax position.",
        potential_savings=500,
        category="planning",
        priority="medium",
        action_items=[
            "Maximize retirement contributions",
            "Harvest tax losses in investment portfolio",
            "Make charitable donations (consider bunching)",
            "Prepay deductible expenses if itemizing",
            "Review estimated tax payments for safe harbor",
        ],
    ))

    return recs


def get_planning_insights_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate forward-looking planning insight recommendations."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    marginal_rate = estimate_marginal_rate(profile)

    # Roth conversion planning
    if agi < 100000:
        recs.append(create_recommendation(
            title="Roth Conversion Opportunity",
            description=f"Your relatively low income ({marginal_rate:.0%} bracket) makes this a good year for Roth conversions.",
            potential_savings=1000,
            category="retirement",
            priority="medium",
            action_items=[
                "Convert traditional IRA to Roth while in a lower bracket",
                "Pay tax now at lower rate; enjoy tax-free growth forever",
                "Consider partial conversions to stay within current bracket",
            ],
        ))

    return recs
