"""CPA firm specialty context — filters and badges strategies by firm focus area."""

from __future__ import annotations
from typing import List


# Map specialty → strategy keywords to match against strategy id/category/title
STRATEGY_SPECIALTY_MAP: dict[str, list[str]] = {
    "real_estate": [
        "cost_segregation", "1031", "rental", "real_estate", "depreciation", "passive"
    ],
    "small_business": [
        "entity", "qbi", "section_179", "aug", "business", "schedule_c", "se_tax", "wotc"
    ],
    "high_income": [
        "backdoor", "roth", "amt", "niit", "charitable", "trust", "qsbs", "defined_benefit"
    ],
    "self_employed": [
        "sep", "solo_401k", "home_office", "vehicle", "health_insurance", "se_deduction",
        "defined_benefit", "augusta"
    ],
    "startups": [
        "rd_tax", "r_and_d", "qsbs", "stock_option", "startup", "section_1202"
    ],
    "retirement_planning": [
        "ira", "roth", "401k", "defined_benefit", "pension", "sep", "solo"
    ],
    "crypto": [
        "crypto", "digital_asset", "nft", "harvest"
    ],
}

# Default specialties for firms without explicit profile (covers common strategies)
_DEFAULT_SPECIALTIES: list[str] = ["small_business", "self_employed"]


def get_cpa_specialties(
    firm_id: str | None,
    firm_profile: dict | None = None,
) -> list[str]:
    """Return specialty list for a firm.

    Resolution order:
    1. ``firm_profile["specialties"]`` — set during onboarding (preferred)
    2. ``firm_profile["specializations"]`` — branding-model field name alias
    3. Fallback to defaults when no profile data is available.
    """
    if firm_profile:
        raw = firm_profile.get("specialties") or firm_profile.get("specializations")
        if raw and isinstance(raw, list):
            known = set(STRATEGY_SPECIALTY_MAP.keys())
            filtered = [s for s in raw if isinstance(s, str) and s in known]
            if filtered:
                return filtered
    if not firm_id:
        return _DEFAULT_SPECIALTIES
    # Production: query DB for firm specialties
    # For now return defaults — CPA dashboard setup will populate these
    return _DEFAULT_SPECIALTIES


def apply_cpa_specialty_badges(
    strategies: list,
    firm_id: str | None,
    firm_profile: dict | None = None,
) -> None:
    """Mutate strategy objects in-place, setting cpa_recommended and cpa_badge."""
    specialties = get_cpa_specialties(firm_id, firm_profile=firm_profile)
    for strategy in strategies:
        strategy_text = " ".join([
            getattr(strategy, "id", "") or "",
            getattr(strategy, "category", "") or "",
            getattr(strategy, "title", "") or "",
        ]).lower()
        for specialty in specialties:
            keywords = STRATEGY_SPECIALTY_MAP.get(specialty, [])
            if any(kw in strategy_text for kw in keywords):
                try:
                    strategy.cpa_recommended = True
                    strategy.cpa_badge = f"Specialty: {specialty.replace('_', ' ').title()}"
                except AttributeError:
                    # Dict-based strategy
                    strategy["cpa_recommended"] = True
                    strategy["cpa_badge"] = f"Specialty: {specialty.replace('_', ' ').title()}"
                break
