"""
Lead magnet insight and payload generation.

Extracted from LeadMagnetService:
- _generate_insights()
- _build_personalization_payload()
- _build_deadline_payload()
- _build_comparison_chart_payload()
- _build_strategy_waterfall_payload()
- _build_tax_calendar_payload()
- _build_share_payload()
- Various display helpers
"""

import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timezone

logger = logging.getLogger(__name__)

from cpa_panel.services.lead_magnet_service import (
    TaxProfile,
    TaxComplexity,
    TaxInsight,
    FilingStatus,
    IncomeSource,
    LifeEvent,
    STATE_DISPLAY_NAMES,
    HIGH_TAX_STATES,
)

from cpa_panel.services.lead_magnet.calculator import (
    parse_income_range,
    estimate_marginal_rate,
)


def normalize_state_code(state_code: Optional[str]) -> str:
    """Normalize a state code and return US for unknown values."""
    normalized = (state_code or "US").strip().upper()
    if normalized in STATE_DISPLAY_NAMES:
        return normalized
    return "US"


def filing_status_display(filing_status: FilingStatus) -> str:
    """Human-readable display name for filing status."""
    mapping = {
        FilingStatus.SINGLE: "single filers",
        FilingStatus.MARRIED_JOINTLY: "married filers",
        FilingStatus.MARRIED_SEPARATELY: "married-separate filers",
        FilingStatus.HEAD_OF_HOUSEHOLD: "head-of-household filers",
        FilingStatus.QUALIFYING_WIDOW: "qualifying surviving spouse filers",
    }
    return mapping.get(filing_status, "filers")


def income_range_display(income_range: str) -> str:
    """Human-readable income range display."""
    display_map = {
        "under_25k": "Under $25,000",
        "25k_50k": "$25,000 - $50,000",
        "50k_75k": "$50,000 - $75,000",
        "75k_100k": "$75,000 - $100,000",
        "100k_150k": "$100,000 - $150,000",
        "150k_200k": "$150,000 - $200,000",
        "200k_500k": "$200,000 - $500,000",
        "500k_plus": "Over $500,000",
        "1m_plus": "Over $1,000,000",
    }
    return display_map.get(income_range, income_range)


def build_personalization_payload(
    profile: Optional[TaxProfile],
    complexity: TaxComplexity,
    savings_low: float,
    savings_high: float,
) -> Dict[str, Any]:
    """Build personalization context for report templates."""
    if not profile:
        return {
            "greeting": "Valued Client",
            "filing_status_label": "filers",
            "income_label": "your income range",
            "state_label": "your state",
            "complexity_label": "standard",
        }

    income = parse_income_range(profile.income_range)
    state = normalize_state_code(profile.state_code)
    state_name = STATE_DISPLAY_NAMES.get(state, state)
    high_tax = state in HIGH_TAX_STATES

    return {
        "greeting": "there",
        "filing_status_label": filing_status_display(profile.filing_status),
        "income_label": income_range_display(profile.income_range),
        "state_label": state_name,
        "state_code": state,
        "is_high_tax_state": high_tax,
        "complexity_label": complexity.value,
        "savings_range_text": f"${savings_low:,.0f} - ${savings_high:,.0f}",
        "income_numeric": income,
    }


def build_deadline_payload() -> Dict[str, Any]:
    """Build tax deadline context."""
    now = datetime.now(timezone.utc)
    tax_year = now.year - 1 if now.month <= 4 else now.year

    # Standard filing deadline: April 15
    deadline = datetime(tax_year + 1, 4, 15, tzinfo=timezone.utc)
    days_until = (deadline - now).days

    if days_until < 0:
        # Past deadline - extension deadline
        extension_deadline = datetime(tax_year + 1, 10, 15, tzinfo=timezone.utc)
        days_until_ext = (extension_deadline - now).days
        return {
            "tax_year": tax_year,
            "deadline": extension_deadline.strftime("%B %d, %Y"),
            "days_until": max(0, days_until_ext),
            "is_past_regular": True,
            "urgency": "high" if days_until_ext < 30 else "medium",
            "message": f"Extension deadline: {extension_deadline.strftime('%B %d, %Y')}",
        }

    urgency = "low"
    if days_until < 14:
        urgency = "critical"
    elif days_until < 30:
        urgency = "high"
    elif days_until < 60:
        urgency = "medium"

    return {
        "tax_year": tax_year,
        "deadline": deadline.strftime("%B %d, %Y"),
        "days_until": days_until,
        "is_past_regular": False,
        "urgency": urgency,
        "message": f"{days_until} days until the filing deadline",
    }


def build_comparison_chart_payload(
    savings_low: float,
    savings_high: float,
    score_overall: int,
) -> Dict[str, Any]:
    """Build comparison chart data for the report."""
    # Simulated benchmark data for comparison
    without_optimization = savings_high * 0.1
    with_optimization = savings_high

    return {
        "without_optimization": int(without_optimization),
        "with_optimization": int(with_optimization),
        "score_vs_average": score_overall - 50,
        "improvement_potential": int(savings_high - savings_low),
    }


def build_strategy_waterfall_payload(
    insights: List[TaxInsight],
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Build strategy waterfall chart data showing cumulative savings."""
    waterfall = []
    cumulative = 0

    for insight in insights[:limit]:
        midpoint = (insight.savings_low + insight.savings_high) / 2
        cumulative += midpoint
        waterfall.append({
            "title": insight.title,
            "savings_low": int(insight.savings_low),
            "savings_high": int(insight.savings_high),
            "savings_midpoint": int(midpoint),
            "cumulative": int(cumulative),
            "category": insight.category,
            "priority": insight.priority,
        })

    return waterfall


def build_tax_calendar_payload(max_items: int = 5) -> List[Dict[str, Any]]:
    """Build a tax calendar with key dates."""
    now = datetime.now(timezone.utc)
    tax_year = now.year - 1 if now.month <= 4 else now.year

    calendar = [
        {
            "date": f"January 31, {tax_year + 1}",
            "title": "W-2 / 1099 Deadline",
            "description": "Employers must issue W-2s; payers must issue 1099s.",
            "category": "document",
        },
        {
            "date": f"April 15, {tax_year + 1}",
            "title": "Tax Filing Deadline",
            "description": f"File {tax_year} tax return or extension.",
            "category": "deadline",
        },
        {
            "date": f"April 15, {tax_year + 1}",
            "title": "IRA Contribution Deadline",
            "description": f"Last day for {tax_year} IRA contributions.",
            "category": "planning",
        },
        {
            "date": f"June 15, {tax_year + 1}",
            "title": "Q2 Estimated Taxes Due",
            "description": "Second quarterly estimated tax payment.",
            "category": "payment",
        },
        {
            "date": f"October 15, {tax_year + 1}",
            "title": "Extension Deadline",
            "description": "File extended tax return.",
            "category": "deadline",
        },
    ]

    return calendar[:max_items]


def build_share_payload(
    session_id: str,
    score_overall: int,
    score_band: str,
    state_code: str,
    cpa_slug: Optional[str],
    estimated_savings: int,
) -> Dict[str, Any]:
    """Build social sharing payload."""
    share_text = f"I scored {score_overall}/100 on my tax health check! Potential savings: ${estimated_savings:,}."

    return {
        "text": share_text,
        "score": score_overall,
        "band": score_band,
        "state": state_code,
        "savings": estimated_savings,
    }


def generate_insights(
    profile: TaxProfile,
    complexity: TaxComplexity,
) -> List[TaxInsight]:
    """Generate tax insights based on profile."""
    insights = []
    income = parse_income_range(profile.income_range)

    # Child Tax Credit
    if profile.children_under_17:
        savings = 2000 * profile.dependents_count
        insights.append(TaxInsight(
            insight_id=f"ctc-{uuid.uuid4().hex[:8]}",
            title="Child Tax Credit Optimization",
            category="credits",
            description_teaser="You may be eligible for significant child tax credits.",
            description_full=(
                f"With {profile.dependents_count} qualifying child(ren) under 17, you may be "
                f"eligible for the Child Tax Credit worth up to $2,000 per child. The credit "
                f"is partially refundable up to $1,600 per child."
            ),
            savings_low=savings * 0.5,
            savings_high=savings,
            action_items=[
                "Verify children's SSNs are valid for work",
                "Confirm residency requirements (lived with you > 6 months)",
                "Check income phase-out thresholds",
            ],
            irs_reference="IRS Publication 972",
            priority="high",
        ))

    # Retirement savings opportunity
    if profile.retirement_savings != "maxed" and income > 30000:
        max_401k = 23500  # 2025 limit (IRS Rev. Proc. 2024-40)
        marginal_rate = estimate_marginal_rate(income, profile.filing_status)
        savings = max_401k * marginal_rate

        insights.append(TaxInsight(
            insight_id=f"ret-{uuid.uuid4().hex[:8]}",
            title="Retirement Contribution Opportunity",
            category="retirement",
            description_teaser="Maximize tax-advantaged retirement savings.",
            description_full=(
                f"Based on your income, increasing your 401(k) or IRA contributions could "
                f"significantly reduce your taxable income. The 2025 401(k) limit is $23,500 "
                f"($31,000 if over 50). Each dollar contributed saves approximately "
                f"{marginal_rate * 100:.0f}% in taxes."
            ),
            savings_low=savings * 0.3,
            savings_high=savings,
            action_items=[
                "Review current 401(k) contribution percentage",
                "Check if employer offers matching",
                "Consider catch-up contributions if over 50",
                "Evaluate Roth vs Traditional based on tax bracket",
            ],
            irs_reference="IRS Publication 590-A",
            priority="high",
        ))

    # HSA opportunity
    if profile.healthcare_type == "hdhp_hsa":
        hsa_limit = 8550 if profile.filing_status == FilingStatus.MARRIED_JOINTLY else 4300  # 2025 limits
        marginal_rate = estimate_marginal_rate(income, profile.filing_status)
        savings = hsa_limit * marginal_rate

        insights.append(TaxInsight(
            insight_id=f"hsa-{uuid.uuid4().hex[:8]}",
            title="HSA Triple Tax Advantage",
            category="healthcare",
            description_teaser="Maximize your Health Savings Account benefits.",
            description_full=(
                f"Your HDHP eligibility allows HSA contributions up to ${hsa_limit:,}. "
                f"HSAs offer triple tax benefits: deductible contributions, tax-free growth, "
                f"and tax-free withdrawals for medical expenses."
            ),
            savings_low=savings * 0.5,
            savings_high=savings,
            action_items=[
                "Verify HDHP eligibility requirements",
                f"Contribute maximum ${hsa_limit:,} for the year",
                "Consider investing HSA funds for long-term growth",
            ],
            irs_reference="IRS Publication 969",
            priority="high",
        ))

    # Homeowner deductions
    if profile.is_homeowner:
        estimated_property_tax = income * 0.015
        estimated_mortgage_interest = income * 0.02

        insights.append(TaxInsight(
            insight_id=f"home-{uuid.uuid4().hex[:8]}",
            title="Homeowner Tax Benefits",
            category="deductions",
            description_teaser="Review mortgage interest and property tax deductions.",
            description_full=(
                "As a homeowner, you may benefit from itemizing deductions including "
                "mortgage interest and property taxes. The SALT deduction cap is $10,000, "
                "which includes state income taxes and property taxes combined."
            ),
            savings_low=2000,
            savings_high=min(10000, estimated_property_tax + estimated_mortgage_interest) * 0.22,
            action_items=[
                "Gather Form 1098 for mortgage interest",
                "Compile property tax statements",
                "Compare itemized vs standard deduction",
            ],
            irs_reference="IRS Schedule A",
            priority="medium",
        ))

    # Self-employment deductions
    if IncomeSource.SELF_EMPLOYED in profile.income_sources:
        insights.append(TaxInsight(
            insight_id=f"se-{uuid.uuid4().hex[:8]}",
            title="Self-Employment Tax Strategies",
            category="business",
            description_teaser="Multiple deductions available for self-employed individuals.",
            description_full=(
                "Self-employment opens numerous tax planning opportunities including "
                "the QBI deduction (up to 20% of qualified income), home office deduction, "
                "health insurance premiums, retirement plans (SEP-IRA, Solo 401k), and "
                "business expense deductions."
            ),
            savings_low=income * 0.05,
            savings_high=income * 0.15,
            action_items=[
                "Track all business expenses",
                "Calculate home office deduction",
                "Review QBI deduction eligibility",
                "Consider SEP-IRA or Solo 401(k)",
            ],
            irs_reference="IRS Schedule C, Form 8829",
            priority="high",
        ))

    # Life events
    if LifeEvent.BABY in profile.life_events:
        insights.append(TaxInsight(
            insight_id=f"baby-{uuid.uuid4().hex[:8]}",
            title="New Baby Tax Benefits",
            category="credits",
            description_teaser="Several tax benefits are available for new parents.",
            description_full=(
                "Congratulations on your new addition! This triggers several tax benefits "
                "including the Child Tax Credit, potential dependent care FSA, and if "
                "applicable, the Earned Income Tax Credit."
            ),
            savings_low=1500,
            savings_high=3600,
            action_items=[
                "Get SSN for newborn ASAP",
                "Update W-4 withholding",
                "Sign up for dependent care FSA if available",
            ],
            priority="high",
        ))

    if LifeEvent.HOME_PURCHASE in profile.life_events:
        insights.append(TaxInsight(
            insight_id=f"newh-{uuid.uuid4().hex[:8]}",
            title="New Home Tax Considerations",
            category="deductions",
            description_teaser="First-year homeowner tax planning opportunities.",
            description_full=(
                "Your home purchase may result in significant deductible expenses "
                "including mortgage points, PMI (if income qualifies), and prorated "
                "property taxes. Keep all closing documents for tax preparation."
            ),
            savings_low=1000,
            savings_high=5000,
            action_items=[
                "Keep HUD-1 settlement statement",
                "Note any points paid on mortgage",
                "Track property tax payments",
            ],
            priority="high",
        ))

    # Ensure minimum insights
    if len(insights) < 3:
        insights.append(TaxInsight(
            insight_id=f"gen-{uuid.uuid4().hex[:8]}",
            title="Tax Filing Optimization",
            category="planning",
            description_teaser="Review your overall tax strategy with a professional.",
            description_full=(
                "A professional tax review can identify additional savings opportunities "
                "based on your complete financial picture. This includes timing strategies, "
                "charitable giving optimization, and education credits if applicable."
            ),
            savings_low=200,
            savings_high=1500,
            action_items=["Schedule consultation with tax professional"],
            priority="medium",
        ))

    return insights
