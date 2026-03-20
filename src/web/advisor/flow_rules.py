"""Eligibility predicate functions for the adaptive flow engine.

Each function takes a profile dict and returns bool.
Used by FlowQuestion.eligibility to decide if a question applies.
"""

from __future__ import annotations

# ─── Constants ────────────────────────────────────────────────────────────────

NO_INCOME_TAX_STATES = frozenset({
    "TX", "FL", "WA", "NV", "WY", "SD", "AK", "NH", "TN",
})

HIGH_TAX_STATES = frozenset({
    "CA", "NY", "NJ", "OR", "HI", "MN", "CT", "VT",
})

# ─── Income Type Predicates ──────────────────────────────────────────────────

def is_w2_employee(p: dict) -> bool:
    """Any W-2 variant (single job, multiple, W-2+side, military)."""
    return p.get("income_type") in (
        "w2_employee", "multiple_w2", "w2_plus_side", "military",
    )


def is_w2_only(p: dict) -> bool:
    """Pure single-job W-2 employee."""
    return p.get("income_type") == "w2_employee"


def is_multiple_w2(p: dict) -> bool:
    return p.get("income_type") == "multiple_w2"


def is_w2_plus_side(p: dict) -> bool:
    return p.get("income_type") == "w2_plus_side"


def is_business_or_se(p: dict) -> bool:
    """Self-employed, business owner, or W-2+side (for SE-specific questions)."""
    return p.get("income_type") in (
        "self_employed", "business_owner", "w2_plus_side",
    ) or p.get("is_self_employed")


def is_self_employed_only(p: dict) -> bool:
    """Pure self-employed / business owner (not W-2+side)."""
    return p.get("income_type") in ("self_employed", "business_owner")


def is_scorp(p: dict) -> bool:
    return p.get("entity_type") == "s_corp"


def is_ccorp(p: dict) -> bool:
    return p.get("entity_type") == "c_corp"


def is_partnership(p: dict) -> bool:
    return p.get("entity_type") == "partnership"


def is_retired(p: dict) -> bool:
    return p.get("income_type") == "retired"


def is_military(p: dict) -> bool:
    return p.get("income_type") == "military"


def is_investor(p: dict) -> bool:
    return p.get("income_type") == "investor"


# ─── Filing Status Predicates ────────────────────────────────────────────────

def is_married(p: dict) -> bool:
    return p.get("filing_status") in ("married_joint", "married_separate")


def is_mfj(p: dict) -> bool:
    return p.get("filing_status") == "married_joint"


def is_mfs(p: dict) -> bool:
    return p.get("filing_status") == "married_separate"


def is_hoh(p: dict) -> bool:
    return p.get("filing_status") == "head_of_household"


def is_qss(p: dict) -> bool:
    return p.get("filing_status") == "qualifying_widow"


def is_single_or_hoh(p: dict) -> bool:
    return p.get("filing_status") in ("single", "head_of_household")


# ─── Dependents ───────────────────────────────────────────────────────────────

def has_dependents(p: dict) -> bool:
    return (p.get("dependents") or 0) > 0


def has_young_dependents(p: dict) -> bool:
    """Has dependents under 17 (after age-split is known)."""
    deps = p.get("dependents") or 0
    under_17 = p.get("dependents_under_17")
    if deps == 0:
        return False
    if under_17 is None:
        return False  # Wait for age-split answer
    return under_17 > 0


def has_no_dependents(p: dict) -> bool:
    return (p.get("dependents") or 0) == 0


# ─── State Predicates ────────────────────────────────────────────────────────

def is_no_income_tax_state(p: dict) -> bool:
    return p.get("state") in NO_INCOME_TAX_STATES


def is_high_tax_state(p: dict) -> bool:
    return p.get("state") in HIGH_TAX_STATES


# ─── Income Level Predicates ─────────────────────────────────────────────────

def _income(p: dict) -> float:
    return float(p.get("total_income", 0) or 0)


def is_very_low_income(p: dict) -> bool:
    return _income(p) < 25000


def is_low_income(p: dict) -> bool:
    return _income(p) < 50000


def is_mid_income(p: dict) -> bool:
    i = _income(p)
    return 50000 <= i < 100000


def is_high_income(p: dict) -> bool:
    i = _income(p)
    return 100000 <= i < 200000


def is_very_high_income(p: dict) -> bool:
    return _income(p) >= 200000


def is_low_income_w2_only(p: dict) -> bool:
    """Low-income W-2 only — skip complex questions like K-1."""
    return (
        p.get("income_type") == "w2_employee"
        and _income(p) < 75000
        and not p.get("_has_investments")
        and not p.get("_has_rental")
    )


def income_above(threshold: float):
    """Factory: returns predicate checking income > threshold."""
    def _check(p: dict) -> bool:
        return _income(p) > threshold
    return _check


def income_below(threshold: float):
    """Factory: returns predicate checking income < threshold."""
    def _check(p: dict) -> bool:
        return _income(p) < threshold
    return _check


# ─── Age Predicates ───────────────────────────────────────────────────────────

def is_young(p: dict) -> bool:
    return p.get("age") in ("age_under_26", "age_26_49", None)


def is_near_retirement(p: dict) -> bool:
    return p.get("age") == "age_50_64"


def is_senior(p: dict) -> bool:
    return p.get("age") == "age_65_plus"


# ─── Situation Flags ──────────────────────────────────────────────────────────

def has_investments(p: dict) -> bool:
    v = p.get("_has_investments")
    return bool(v) and v not in ("no_investments",)


def has_rental(p: dict) -> bool:
    v = p.get("_has_rental")
    return bool(v) and v not in ("no_rental",)


def has_k1(p: dict) -> bool:
    v = p.get("_has_k1")
    return bool(v) and v not in ("no_k1_income",)


def has_business_income(p: dict) -> bool:
    bi = p.get("business_income")
    if bi is None:
        return False
    return float(bi) > 0
