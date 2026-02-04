"""
Investment recommendation generators.

Extracted from recommendation_helper.py — tax-loss harvesting,
NIIT, qualified dividends, and opportunity detection.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_int, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import TAX_YEAR, STANDARD_DEDUCTIONS

logger = logging.getLogger(__name__)


def get_opportunity_detector_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Detect tax optimization opportunities based on profile data."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    filing_status = safe_str(profile.get("filing_status", "single")).lower()
    capital_gains = safe_float(profile.get("capital_gains", 0))
    capital_losses = safe_float(profile.get("capital_losses", 0))
    investment_income = safe_float(profile.get("investment_income", 0))

    # Tax-loss harvesting opportunity
    if capital_gains > 5000 and capital_losses < capital_gains:
        potential = min(capital_gains - capital_losses, capital_gains * 0.3) * estimate_marginal_rate(profile)
        recs.append(create_recommendation(
            title="Tax-Loss Harvesting Opportunity",
            description=f"With ${capital_gains:,.0f} in gains, consider harvesting losses to offset. Potential tax savings: ${potential:,.0f}.",
            potential_savings=potential,
            category="investment",
            priority="high",
            action_items=[
                "Review portfolio for positions with unrealized losses",
                "Sell losing positions before year-end to offset gains",
                "Be aware of wash sale rule (30 days before/after)",
                "Consider tax-lot selection for partial sales",
            ],
        ))

    # NIIT alert
    niit_threshold = 250000 if "married" in filing_status and "joint" in filing_status else 200000
    if agi > niit_threshold and investment_income > 0:
        niit_amount = min(investment_income, agi - niit_threshold) * 0.038
        recs.append(create_recommendation(
            title="Net Investment Income Tax (NIIT) Planning",
            description=f"You may owe ${niit_amount:,.0f} in NIIT (3.8% surtax). Consider strategies to reduce investment income or AGI.",
            potential_savings=niit_amount * 0.5,
            category="investment",
            priority="medium",
            action_items=[
                "Consider tax-exempt municipal bonds",
                "Maximize retirement contributions to reduce AGI",
                "Review timing of investment income recognition",
            ],
        ))

    # Capital loss carryforward
    net_loss = capital_losses - capital_gains
    if net_loss > 3000:
        recs.append(create_recommendation(
            title="Capital Loss Deduction & Carryforward",
            description=f"Deduct $3,000 against ordinary income this year. Carry forward ${net_loss - 3000:,.0f} to future years.",
            potential_savings=3000 * estimate_marginal_rate(profile),
            category="investment",
            priority="medium",
            complexity="simple",
            action_items=["Track carryforward amount for next year's return"],
        ))

    return recs
