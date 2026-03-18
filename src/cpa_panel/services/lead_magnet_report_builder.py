"""
Lead Magnet → Advisory Report Schema Bridge (F0-A)

Converts the lead magnet's TaxProfile (quick-question format with income ranges
and boolean flags) into a TaxProfileInput (precise dollar amounts) so that lead
magnet sessions can optionally generate full advisory reports.

Usage:
    from cpa_panel.services.lead_magnet_report_builder import build_tax_profile_input
    tax_profile_input = build_tax_profile_input(lead_magnet_tax_profile)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Income range midpoints used when converting range strings to dollar amounts.
INCOME_RANGE_MIDPOINTS: Dict[str, float] = {
    "0-25k": 12_500,
    "25k-50k": 37_500,
    "50k-75k": 62_500,
    "75k-100k": 87_500,
    "100k-150k": 125_000,
    "150k-200k": 175_000,
    "200k-300k": 250_000,
    "300k-500k": 400_000,
    "500k+": 600_000,
    "1m+": 1_200_000,
}


def build_tax_profile_input(
    tax_profile,  # lead_magnet_service.TaxProfile dataclass
    *,
    override_income: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Convert a lead-magnet TaxProfile into a dict suitable for constructing
    a ``TaxProfileInput`` (web.advisor.models).

    Args:
        tax_profile: A ``TaxProfile`` dataclass from ``lead_magnet_service``.
        override_income: If provided, use this exact income instead of the
            midpoint derived from ``income_range``.

    Returns:
        A dict whose keys match ``TaxProfileInput`` fields.  Callers can
        pass it directly: ``TaxProfileInput(**result)``.
    """
    profile_dict = tax_profile.to_dict() if hasattr(tax_profile, "to_dict") else dict(tax_profile)

    # --- Filing status ---
    filing_status = profile_dict.get("filing_status", "single")

    # --- Income estimation ---
    income_range = profile_dict.get("income_range", "50k-75k")
    total_income = override_income or INCOME_RANGE_MIDPOINTS.get(income_range, 62_500)

    # Distribute income across sources based on flags
    income_sources = profile_dict.get("income_sources", [])
    has_business = profile_dict.get("has_business", False)
    occupation_type = profile_dict.get("occupation_type", "w2")

    w2_income: Optional[float] = None
    business_income: Optional[float] = None
    investment_income: Optional[float] = None

    if occupation_type == "w2" and not has_business:
        w2_income = total_income
    elif has_business or occupation_type in ("self_employed", "1099"):
        # Split 70/30 as a reasonable default for mixed-income filers
        w2_income = round(total_income * 0.3) if "w2" in income_sources else None
        business_income = round(total_income * 0.7) if w2_income else total_income
    else:
        w2_income = total_income

    if "investments" in income_sources or "investment" in income_sources:
        # Assign ~10% as investment income, deducted from w2
        investment_income = round(total_income * 0.10)
        if w2_income:
            w2_income = max(0, w2_income - investment_income)

    # --- State ---
    state_code = profile_dict.get("state_code", "")
    state = state_code if len(state_code) == 2 and state_code != "US" else None

    # --- Dependents ---
    dependents = profile_dict.get("dependents_count", 0)

    # --- Deductions (inferred from booleans) ---
    is_homeowner = profile_dict.get("is_homeowner", False)
    mortgage_interest = 12_000.0 if is_homeowner else None
    property_taxes = 5_000.0 if is_homeowner else None

    has_student_loans = profile_dict.get("has_student_loans", False)

    # --- Retirement ---
    retirement_savings = profile_dict.get("retirement_savings", "none")
    retirement_401k: Optional[float] = None
    if retirement_savings == "maxed":
        retirement_401k = 23_000.0  # 2025 max
    elif retirement_savings == "some":
        retirement_401k = 8_000.0  # Moderate estimate

    # --- HSA ---
    healthcare_type = profile_dict.get("healthcare_type", "employer")
    hsa_contributions: Optional[float] = None
    if healthcare_type == "hdhp_hsa":
        hsa_contributions = 4_150.0  # 2025 individual max

    # --- Self-employment ---
    is_self_employed = has_business or occupation_type in ("self_employed", "1099")
    health_insurance_premiums: Optional[float] = None
    if is_self_employed and healthcare_type in ("marketplace", "individual"):
        health_insurance_premiums = 7_200.0  # Rough annual average

    result = {
        "filing_status": filing_status,
        "total_income": total_income,
        "w2_income": w2_income,
        "business_income": business_income,
        "investment_income": investment_income,
        "dependents": dependents,
        "state": state,
        "mortgage_interest": mortgage_interest,
        "property_taxes": property_taxes,
        "retirement_401k": retirement_401k,
        "hsa_contributions": hsa_contributions,
        "is_self_employed": is_self_employed,
        "health_insurance_premiums": health_insurance_premiums,
    }

    # Strip None values so TaxProfileInput uses its own defaults
    return {k: v for k, v in result.items() if v is not None}
