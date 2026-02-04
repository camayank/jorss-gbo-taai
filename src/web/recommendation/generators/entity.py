"""
Entity structure recommendation generators.

Extracted from recommendation_helper.py — S-Corp optimization,
entity structuring, and CPA referral opportunities.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_int, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import TAX_YEAR, BUSINESS_LIMITS

logger = logging.getLogger(__name__)


def get_entity_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate entity structure optimization recommendations."""
    recs = []

    self_employment_income = safe_float(profile.get("self_employment_income", 0))
    business_income = safe_float(profile.get("business_income", 0))
    total_business = self_employment_income + business_income

    if total_business < 50000:
        return recs

    se_tax = total_business * 0.9235 * BUSINESS_LIMITS.get("se_tax_rate", 0.153)

    # S-Corp election analysis
    if total_business > 80000:
        reasonable_salary = total_business * 0.60
        salary_se_equivalent = reasonable_salary * 0.0765 * 2
        distribution = total_business - reasonable_salary
        potential_savings = se_tax - salary_se_equivalent

        if potential_savings > 2000:
            recs.append(create_recommendation(
                title="S-Corporation Election",
                description=f"Converting to S-Corp could save ${potential_savings:,.0f}/year in self-employment taxes.",
                potential_savings=potential_savings,
                category="business",
                priority="high",
                complexity="complex",
                action_items=[
                    f"Set reasonable salary at ~${reasonable_salary:,.0f}",
                    f"Take ${distribution:,.0f} as distributions (no SE tax)",
                    "File Form 2553 for S-Corp election",
                    "Must run payroll and file payroll taxes",
                    "Consult CPA for reasonable compensation analysis",
                ],
                warnings=[
                    "Additional payroll administration costs (~$1,000-3,000/year)",
                    "IRS scrutinizes unreasonably low salaries",
                ],
            ))

    return recs


def get_cpa_opportunities(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Identify situations where CPA consultation is highly valuable."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    self_employment_income = safe_float(profile.get("self_employment_income", 0))
    rental_properties = safe_int(profile.get("rental_properties", 0))
    foreign_income = safe_float(profile.get("foreign_income", 0))
    num_dependents = safe_int(profile.get("num_dependents", 0))

    complexity_score = 0
    if agi > 200000:
        complexity_score += 2
    if self_employment_income > 50000:
        complexity_score += 2
    if rental_properties > 0:
        complexity_score += 2
    if foreign_income > 0:
        complexity_score += 3
    if num_dependents > 2:
        complexity_score += 1

    if complexity_score >= 4:
        recs.append(create_recommendation(
            title="Professional Tax Preparation Recommended",
            description="Your tax situation has sufficient complexity that professional preparation is likely cost-effective.",
            potential_savings=agi * 0.02,
            category="compliance",
            priority="high",
            complexity="simple",
            action_items=[
                "Schedule consultation with enrolled agent or CPA",
                "Gather all tax documents before meeting",
                "Ask about tax planning strategies for next year",
            ],
        ))

    return recs
