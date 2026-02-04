"""
Deduction recommendation generators.

Extracted from recommendation_helper.py — standard vs itemized,
SALT, QBI, and smart deduction detection.
"""

import logging
from typing import Dict, Any, List

from ..models import UnifiedRecommendation
from ..utils import safe_float, safe_int, safe_str, create_recommendation, estimate_marginal_rate
from ..constants import (
    TAX_YEAR, STANDARD_DEDUCTIONS, DEDUCTION_LIMITS, BUSINESS_LIMITS,
)

logger = logging.getLogger(__name__)


def get_qbi_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Generate Section 199A QBI deduction recommendations."""
    recs = []

    self_employment_income = safe_float(profile.get("self_employment_income", 0))
    business_income = safe_float(profile.get("business_income", 0))
    total_business = self_employment_income + business_income

    if total_business <= 0:
        return recs

    filing_status = safe_str(profile.get("filing_status", "single")).lower()
    agi = safe_float(profile.get("agi", 0))

    qbi_threshold = BUSINESS_LIMITS.get("qbi_threshold_mfj", 383900) if "married" in filing_status and "joint" in filing_status else BUSINESS_LIMITS.get("qbi_threshold_single", 191950)

    potential_deduction = total_business * 0.20

    if agi < qbi_threshold:
        recs.append(create_recommendation(
            title="Section 199A QBI Deduction",
            description=f"Your business income of ${total_business:,.0f} may qualify for a 20% QBI deduction of up to ${potential_deduction:,.0f}.",
            potential_savings=potential_deduction * estimate_marginal_rate(profile),
            category="deductions",
            priority="high",
            action_items=[
                "Ensure your business is a qualified trade or business",
                "Document all business income and expenses",
                "Consider W-2 wage and UBIA limitations if near threshold",
            ],
        ))
    elif agi < qbi_threshold + 100000:
        recs.append(create_recommendation(
            title="QBI Deduction Phase-out Planning",
            description=f"Your income is near the QBI threshold. Consider strategies to stay below ${qbi_threshold:,.0f}.",
            potential_savings=potential_deduction * estimate_marginal_rate(profile) * 0.5,
            category="deductions",
            priority="high",
            action_items=[
                "Maximize retirement contributions to reduce AGI",
                "Consider timing of income and deductions",
                "Consult with CPA about W-2 wage safe harbor",
            ],
        ))

    return recs


def get_smart_deduction_detector_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """Detect commonly missed deductions."""
    recs = []

    agi = safe_float(profile.get("agi", 0))
    filing_status = safe_str(profile.get("filing_status", "single")).lower()

    # Student loan interest
    student_loan_interest = safe_float(profile.get("student_loan_interest", 0))
    if student_loan_interest > 0 and agi < 95000:
        deduction = min(student_loan_interest, 2500)
        recs.append(create_recommendation(
            title="Student Loan Interest Deduction",
            description=f"Deduct up to ${deduction:,.0f} in student loan interest, even if you don't itemize.",
            potential_savings=deduction * estimate_marginal_rate(profile),
            category="deductions",
            priority="medium",
            complexity="simple",
            action_items=["Ensure you received Form 1098-E from your loan servicer"],
        ))

    # Educator expenses
    is_educator = profile.get("is_educator", False)
    if is_educator:
        recs.append(create_recommendation(
            title="Educator Expense Deduction",
            description="Teachers can deduct up to $300 for classroom supplies, even without itemizing.",
            potential_savings=300 * estimate_marginal_rate(profile),
            category="deductions",
            priority="low",
            complexity="simple",
            action_items=["Keep receipts for classroom supplies, books, and materials"],
        ))

    # HSA above-the-line deduction
    hsa_contribution = safe_float(profile.get("hsa_contribution", 0))
    if hsa_contribution > 0:
        recs.append(create_recommendation(
            title="HSA Tax Triple Benefit",
            description=f"Your HSA contribution of ${hsa_contribution:,.0f} is tax-deductible, grows tax-free, and withdrawals for medical are tax-free.",
            potential_savings=hsa_contribution * estimate_marginal_rate(profile),
            category="deductions",
            priority="medium",
            action_items=["Maximize HSA contributions if you have a high-deductible health plan"],
        ))

    return recs
