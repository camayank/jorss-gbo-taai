"""
International tax recommendation generators.

Extracted from recommendation_helper.py — foreign tax credit,
FBAR, and international reporting.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import TAX_YEAR

logger = logging.getLogger(__name__)


def get_foreign_tax_credit_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate foreign tax credit recommendations."""
    recs = []

    foreign_income = safe_float(profile.get("foreign_income", 0))
    foreign_taxes_paid = safe_float(profile.get("foreign_taxes_paid", 0))
    foreign_accounts = safe_float(profile.get("foreign_account_balance", 0))

    if foreign_income <= 0 and foreign_taxes_paid <= 0 and foreign_accounts <= 0:
        return recs

    # Foreign Tax Credit
    if foreign_taxes_paid > 0:
        recs.append(create_recommendation(
            title="Foreign Tax Credit (Form 1116)",
            description=f"Claim a credit of ${foreign_taxes_paid:,.0f} for foreign taxes paid, reducing your US tax dollar-for-dollar.",
            potential_savings=foreign_taxes_paid,
            category="credits",
            priority="high",
            action_items=[
                "File Form 1116 to claim the credit",
                "Compare credit vs deduction — credit is usually better",
                "If foreign taxes are under $300 ($600 MFJ), you may elect direct credit without Form 1116",
            ],
        ))

    # FBAR filing requirement
    if foreign_accounts > 10000:
        recs.append(create_recommendation(
            title="FBAR Filing Requirement (FinCEN 114)",
            description="You must file FBAR if aggregate foreign account balances exceed $10,000 at any time during the year.",
            potential_savings=0,
            category="compliance",
            priority="critical",
            action_items=[
                "File FinCEN Form 114 electronically by April 15",
                "Automatic extension to October 15 if needed",
                "Report ALL foreign financial accounts",
            ],
            warnings=[
                "Penalties for non-filing can be $10,000+ per account",
                "Willful violations can result in criminal penalties",
            ],
        ))

    # FATCA Form 8938
    if foreign_accounts > 50000:
        recs.append(create_recommendation(
            title="FATCA Reporting (Form 8938)",
            description="File Form 8938 with your tax return for foreign financial assets exceeding $50,000.",
            potential_savings=0,
            category="compliance",
            priority="high",
            action_items=[
                "File Form 8938 with your Form 1040",
                "This is separate from FBAR — you may need both",
                "Include foreign bank accounts, securities, and financial instruments",
            ],
        ))

    return recs
