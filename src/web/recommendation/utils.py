"""
Recommendation Utilities - Helper Functions

SPEC-006: Shared utility functions for recommendation generators.
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal
import logging

from .models import UnifiedRecommendation
from .constants import FILING_STATUS_MAP

logger = logging.getLogger(__name__)


def safe_float(
    value: Any,
    default: float = 0.0,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> float:
    """
    Safely convert value to float with optional bounds.

    Args:
        value: Value to convert
        default: Default if conversion fails
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Converted float value
    """
    if value is None:
        return default

    try:
        result = float(value)

        if min_val is not None and result < min_val:
            return min_val
        if max_val is not None and result > max_val:
            return max_val

        return result
    except (ValueError, TypeError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None
) -> int:
    """Safely convert value to int with optional bounds."""
    if value is None:
        return default

    try:
        result = int(float(value))

        if min_val is not None and result < min_val:
            return min_val
        if max_val is not None and result > max_val:
            return max_val

        return result
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Safely convert value to string."""
    if value is None:
        return default
    return str(value).strip()


def safe_decimal(value: Any, default: float = 0.0) -> Decimal:
    """Safely convert value to Decimal."""
    try:
        if value is None:
            return Decimal(str(default))
        return Decimal(str(value))
    except:
        return Decimal(str(default))


def normalize_filing_status(status: Any) -> str:
    """
    Normalize filing status to standard format.

    Args:
        status: Raw filing status value

    Returns:
        Normalized filing status string
    """
    if not status:
        return "single"

    status_str = str(status).lower().strip().replace(" ", "_").replace("-", "_")

    return FILING_STATUS_MAP.get(status_str, "single")


def validate_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize a tax profile.

    Extracts key values from various possible locations in the profile
    and normalizes them for consistent processing.

    Args:
        profile: Raw profile dictionary

    Returns:
        Normalized profile dictionary
    """
    if not profile:
        return {}

    # Try to extract from nested structures
    taxpayer = profile.get("taxpayer", {})
    income = profile.get("income", {})
    deductions = profile.get("deductions", {})
    credits = profile.get("credits", {})

    # Build normalized profile
    normalized = {
        # Basic info
        "filing_status": normalize_filing_status(
            profile.get("filing_status") or
            taxpayer.get("filing_status") or
            "single"
        ),
        "tax_year": safe_int(profile.get("tax_year", 2025)),
        "age": safe_int(profile.get("age") or taxpayer.get("age"), default=35),
        "spouse_age": safe_int(profile.get("spouse_age") or taxpayer.get("spouse_age"), default=0),

        # Income
        "wages": safe_float(
            profile.get("wages") or
            profile.get("w2_income") or
            income.get("wages") or
            income.get("total_wages") or
            0
        ),
        "gross_income": safe_float(
            profile.get("gross_income") or
            profile.get("total_income") or
            income.get("total_income") or
            0
        ),
        "agi": safe_float(
            profile.get("agi") or
            profile.get("adjusted_gross_income") or
            income.get("agi") or
            0
        ),
        "self_employment_income": safe_float(
            profile.get("self_employment_income") or
            income.get("self_employment") or
            0
        ),
        "business_income": safe_float(
            profile.get("business_income") or
            income.get("business_income") or
            0
        ),
        "rental_income": safe_float(
            profile.get("rental_income") or
            income.get("rental_income") or
            0
        ),
        "investment_income": safe_float(
            profile.get("investment_income") or
            income.get("investment_income") or
            income.get("interest_income", 0) + income.get("dividend_income", 0) or
            0
        ),
        "capital_gains": safe_float(
            profile.get("capital_gains") or
            income.get("capital_gains") or
            0
        ),

        # Deductions
        "itemized_deductions": safe_float(
            profile.get("itemized_deductions") or
            deductions.get("total") or
            0
        ),
        "mortgage_interest": safe_float(
            profile.get("mortgage_interest") or
            deductions.get("mortgage_interest") or
            0
        ),
        "state_local_taxes": safe_float(
            profile.get("state_local_taxes") or
            deductions.get("state_local_taxes") or
            0
        ),
        "charitable_contributions": safe_float(
            profile.get("charitable_contributions") or
            deductions.get("charitable") or
            0
        ),

        # Retirement
        "retirement_contributions": safe_float(
            profile.get("retirement_contributions") or
            profile.get("401k_contributions") or
            0
        ),
        "ira_contributions": safe_float(
            profile.get("ira_contributions") or
            0
        ),
        "has_employer_retirement": profile.get("has_employer_retirement", False),

        # Family
        "num_dependents": safe_int(
            profile.get("num_dependents") or
            len(profile.get("dependents", []))
        ),
        "num_children_under_17": safe_int(profile.get("num_children_under_17", 0)),
        "has_dependents": bool(
            profile.get("has_dependents") or
            profile.get("num_dependents", 0) > 0 or
            len(profile.get("dependents", [])) > 0
        ),

        # Other
        "state_of_residence": safe_str(
            profile.get("state_of_residence") or
            profile.get("state") or
            taxpayer.get("state") or
            ""
        ),
        "is_self_employed": profile.get("is_self_employed", False),
        "has_rental_property": profile.get("has_rental_property", False),
        "has_investments": profile.get("has_investments", False),

        # Pass through original for access to nested data
        "_original": profile,
    }

    # Calculate derived values
    if not normalized["gross_income"] and normalized["wages"]:
        normalized["gross_income"] = normalized["wages"]

    if not normalized["agi"] and normalized["gross_income"]:
        normalized["agi"] = normalized["gross_income"]

    return normalized


def create_recommendation(
    title: str,
    description: str,
    potential_savings: float,
    priority: str = "medium",
    category: str = "general",
    confidence: float = 0.8,
    complexity: str = "moderate",
    action_items: Optional[List[str]] = None,
    requirements: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    source: str = "unified_advisor",
    metadata: Optional[Dict[str, Any]] = None,
) -> UnifiedRecommendation:
    """
    Factory function to create a recommendation.

    Args:
        title: Short title
        description: Detailed description
        potential_savings: Estimated tax savings
        priority: critical, high, medium, low
        category: Recommendation category
        confidence: Confidence score (0-1)
        complexity: simple, moderate, complex
        action_items: List of action steps
        requirements: Prerequisites
        warnings: Important caveats
        source: Generator source
        metadata: Additional metadata

    Returns:
        UnifiedRecommendation instance
    """
    return UnifiedRecommendation(
        title=title,
        description=description,
        potential_savings=max(0, potential_savings),
        priority=priority,
        category=category,
        confidence=confidence,
        complexity=complexity,
        action_items=action_items or [],
        requirements=requirements or [],
        warnings=warnings or [],
        source=source,
        metadata=metadata or {},
    )


def estimate_marginal_rate(agi: float, filing_status: str) -> float:
    """
    Estimate marginal tax rate based on AGI and filing status.

    Args:
        agi: Adjusted gross income
        filing_status: Filing status

    Returns:
        Estimated marginal tax rate (0-0.37)
    """
    from .constants import TAX_BRACKETS

    status = normalize_filing_status(filing_status)
    brackets = TAX_BRACKETS.get(status, TAX_BRACKETS["single"])

    for threshold, rate in brackets:
        if agi <= threshold:
            return rate

    return 0.37  # Top rate


def calculate_tax_savings(deduction_amount: float, marginal_rate: float) -> float:
    """
    Calculate tax savings from a deduction.

    Args:
        deduction_amount: Amount of deduction
        marginal_rate: Marginal tax rate

    Returns:
        Estimated tax savings
    """
    return deduction_amount * marginal_rate


def format_currency(amount: float) -> str:
    """Format amount as currency string."""
    return f"${amount:,.0f}"


def format_percentage(rate: float) -> str:
    """Format rate as percentage string."""
    return f"{rate * 100:.1f}%"


def get_urgency_info() -> tuple:
    """
    Get current urgency level based on date.

    Returns:
        Tuple of (urgency_level, deadline_info)
    """
    from datetime import datetime

    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day

    # Tax filing deadline is April 15
    if month < 4 or (month == 4 and day <= 15):
        if month == 4:
            return ("high", f"Tax deadline is April 15, {year}")
        elif month == 3:
            return ("medium", f"Tax deadline approaching: April 15, {year}")
        else:
            return ("normal", None)

    # After April 15
    if month == 4 and day > 15:
        return ("normal", "2025 filing deadline passed. Consider extension if needed.")

    # Q2-Q4 - focus on estimated taxes and planning
    if month in (6, 9):
        return ("medium", "Estimated tax payment due this month")

    return ("normal", None)


def get_lead_score(profile: Dict[str, Any]) -> int:
    """
    Calculate lead score based on profile complexity.

    Higher scores indicate more complex situations that benefit from professional help.

    Args:
        profile: Validated profile dictionary

    Returns:
        Lead score (0-100)
    """
    score = 0

    # Income complexity
    agi = profile.get("agi", 0)
    if agi > 500000:
        score += 25
    elif agi > 200000:
        score += 15
    elif agi > 100000:
        score += 10

    # Self-employment
    if profile.get("is_self_employed") or profile.get("self_employment_income", 0) > 0:
        score += 20

    # Business income
    if profile.get("business_income", 0) > 0:
        score += 15

    # Rental property
    if profile.get("has_rental_property") or profile.get("rental_income", 0) > 0:
        score += 15

    # Investments
    if profile.get("investment_income", 0) > 50000:
        score += 10
    if profile.get("capital_gains", 0) > 50000:
        score += 10

    # Multiple income sources
    income_sources = sum([
        1 if profile.get("wages", 0) > 0 else 0,
        1 if profile.get("self_employment_income", 0) > 0 else 0,
        1 if profile.get("business_income", 0) > 0 else 0,
        1 if profile.get("rental_income", 0) > 0 else 0,
        1 if profile.get("investment_income", 0) > 0 else 0,
    ])
    if income_sources >= 3:
        score += 15

    return min(100, score)
