"""
Tax planning helper functions extracted from intelligent_advisor_api.py.

Contains:
- Profile-to-return conversion functions (convert_profile_to_tax_return, build_tax_return_from_profile)
- Safety check runner (_run_safety_checks)
- Strategy tier classification (_classify_strategy_tier)
- Helper profile converters
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from decimal import Decimal

from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)


def convert_profile_to_tax_return(profile: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
    """
    Convert advisor chat profile dict to a complete tax return dictionary.

    This is the central conversion function used by report generation,
    full analysis, and PDF export.
    """
    filing_status = profile.get("filing_status", "single")
    total_income = float(profile.get("total_income", 0) or 0)
    w2_income = float(profile.get("w2_income", 0) or 0)
    business_income = float(profile.get("business_income", 0) or 0)
    self_employment_income = float(profile.get("self_employment_income", 0) or 0)

    # Income components
    wages = w2_income or total_income
    if not wages and not business_income and not self_employment_income:
        wages = total_income

    # Deductions
    mortgage = float(profile.get("mortgage_interest", 0) or 0)
    property_taxes = float(profile.get("property_taxes", 0) or 0)
    state_tax = float(profile.get("state_income_tax", 0) or 0)
    charitable = float(profile.get("charitable_donations", 0) or 0)
    medical = float(profile.get("medical_expenses", 0) or 0)

    # Standard deduction amounts (2025)
    standard_deduction_amounts = {
        "single": 15000,
        "married_joint": 30000,
        "married_separate": 15000,
        "head_of_household": 22500,
        "qualifying_widow": 30000,
    }
    standard_deduction = standard_deduction_amounts.get(filing_status, 15000)

    itemized_total = mortgage + min(property_taxes + state_tax, 10000) + charitable
    if medical > total_income * 0.075:
        itemized_total += medical - total_income * 0.075

    use_itemized = itemized_total > standard_deduction
    deduction_amount = itemized_total if use_itemized else standard_deduction

    # Retirement contributions
    retirement_401k = float(profile.get("retirement_401k", 0) or profile.get("retirement_contributions", 0) or 0)
    ira = float(profile.get("retirement_ira", 0) or profile.get("traditional_ira", 0) or 0)
    hsa = float(profile.get("hsa_contributions", 0) or profile.get("hsa_contribution", 0) or 0)

    # Credits
    dependents = int(profile.get("dependents", 0) or 0)
    child_tax_credit = dependents * 2000

    return {
        "session_id": session_id,
        "filing_status": filing_status,
        "taxpayer": {
            "first_name": profile.get("first_name", ""),
            "last_name": profile.get("last_name", ""),
            "age": profile.get("age"),
            "state": profile.get("state", "CA"),
        },
        "income": {
            "wages": float(money(wages)),
            "business_income": float(money(business_income)),
            "self_employment_income": float(money(self_employment_income)),
            "investment_income": float(money(float(profile.get("investment_income", 0) or 0))),
            "rental_income": float(money(float(profile.get("rental_income", 0) or 0))),
            "total_income": float(money(total_income)),
        },
        "deductions": {
            "type": "itemized" if use_itemized else "standard",
            "amount": float(money(deduction_amount)),
            "mortgage_interest": float(money(mortgage)),
            "property_taxes": float(money(property_taxes)),
            "state_income_tax": float(money(state_tax)),
            "charitable": float(money(charitable)),
            "medical": float(money(medical)),
        },
        "adjustments": {
            "retirement_401k": float(money(retirement_401k)),
            "ira": float(money(ira)),
            "hsa": float(money(hsa)),
        },
        "credits": {
            "child_tax_credit": child_tax_credit,
            "dependents": dependents,
        },
    }


def _summarize_profile(profile: dict) -> str:
    """Create a human-readable summary of the current profile."""
    parts = []

    if profile.get("filing_status"):
        status_names = {
            "single": "Single",
            "married_joint": "Married Filing Jointly",
            "married_separate": "Married Filing Separately",
            "head_of_household": "Head of Household",
            "qualifying_widow": "Qualifying Surviving Spouse"
        }
        parts.append(status_names.get(profile["filing_status"], profile["filing_status"]))

    if profile.get("total_income"):
        parts.append(f"${profile['total_income']:,.0f} income")

    if profile.get("state"):
        parts.append(f"in {profile['state']}")

    if profile.get("dependents"):
        parts.append(f"{profile['dependents']} dependent(s)")

    if profile.get("business_income"):
        parts.append(f"${profile['business_income']:,.0f} business income")

    return ", ".join(parts) if parts else "No profile data"


def _profile_to_return_data(profile: Dict, session_id: str = "") -> Dict[str, Any]:
    """Convert a profile dict to return_data format for safety checks / anomaly detection."""
    total_income = float(profile.get("total_income", 0) or 0)
    filing_status = profile.get("filing_status", "single")

    return {
        "session_id": session_id,
        "filing_status": filing_status,
        "total_income": total_income,
        "wages": float(profile.get("w2_income", 0) or 0),
        "business_income": float(profile.get("business_income", 0) or 0),
        "self_employment_income": float(profile.get("self_employment_income", 0) or 0),
        "investment_income": float(profile.get("investment_income", 0) or 0),
        "rental_income": float(profile.get("rental_income", 0) or 0),
        "mortgage_interest": float(profile.get("mortgage_interest", 0) or 0),
        "property_taxes": float(profile.get("property_taxes", 0) or 0),
        "state_income_tax": float(profile.get("state_income_tax", 0) or 0),
        "charitable_donations": float(profile.get("charitable_donations", 0) or 0),
        "medical_expenses": float(profile.get("medical_expenses", 0) or 0),
        "dependents": int(profile.get("dependents", 0) or 0),
        "state": profile.get("state", "CA"),
        "age": int(profile.get("age", 30) or 30),
    }


async def classify_strategy_tier(
    strategy: dict,
    profile: dict,
    ai_enabled: bool = True,
) -> dict:
    """
    Classify a strategy recommendation into free/premium tiers.

    Strategies with savings > $5,000 or complex implementation are premium.
    """
    savings = strategy.get("estimated_savings", 0)
    complexity = strategy.get("complexity", "medium")

    if savings > 5000 or complexity == "high":
        tier = "premium"
    elif savings > 1000:
        tier = "standard"
    else:
        tier = "free"

    return {
        **strategy,
        "tier": tier,
        "locked": tier == "premium",
    }


def build_safety_summary(safety_checks: Optional[dict]) -> Optional[dict]:
    """Build a human-readable safety summary from safety check results."""
    if not safety_checks:
        return None

    flags = safety_checks.get("flags", [])
    warnings = safety_checks.get("warnings", [])
    score = safety_checks.get("confidence_score", 100)

    if not flags and not warnings:
        return {
            "status": "pass",
            "message": "No safety concerns detected.",
            "confidence_score": score,
        }

    return {
        "status": "review_recommended" if flags else "caution",
        "message": f"{len(flags)} item(s) flagged for review, {len(warnings)} warning(s).",
        "flags": flags,
        "warnings": warnings,
        "confidence_score": score,
    }
