"""
Tax-Specific Skip Rules for Questionnaire

Provides pre-configured skip conditions based on IRS rules and thresholds
for Tax Year 2025. These rules help users avoid irrelevant questions.

Usage:
    from onboarding.tax_skip_rules import SkipRules, get_skip_condition

    # In question definition
    question = Question(
        id="eitc_children",
        text="How many qualifying children do you have?",
        show_if=SkipRules.EITC_ELIGIBLE,
        ...
    )

    # Or use the helper
    show_if = get_skip_condition("eitc_eligible")
"""

from typing import Dict, Any, Optional
from decimal import Decimal


# =============================================================================
# TAX YEAR 2025 THRESHOLDS
# These should be updated annually when IRS releases new limits
# =============================================================================

# EITC (Earned Income Tax Credit) Thresholds - TY2025
EITC_LIMITS = {
    "single": {
        0: Decimal("18950"),   # No children
        1: Decimal("50162"),   # 1 child
        2: Decimal("55768"),   # 2 children
        3: Decimal("59899"),   # 3+ children
    },
    "mfj": {  # Married Filing Jointly
        0: Decimal("25511"),
        1: Decimal("56723"),
        2: Decimal("62318"),
        3: Decimal("66460"),
    },
}
EITC_INVESTMENT_INCOME_LIMIT = Decimal("11600")

# Child Tax Credit Thresholds
CTC_PHASEOUT_SINGLE = Decimal("200000")
CTC_PHASEOUT_MFJ = Decimal("400000")
CTC_MAX_AGE = 17  # Child must be under 17

# Education Credits Thresholds
AOTC_MAGI_PHASEOUT_SINGLE = Decimal("90000")
AOTC_MAGI_PHASEOUT_MFJ = Decimal("180000")
LLC_MAGI_PHASEOUT_SINGLE = Decimal("80000")
LLC_MAGI_PHASEOUT_MFJ = Decimal("160000")

# Retirement Savings Credit (Saver's Credit)
SAVERS_CREDIT_LIMIT_SINGLE = Decimal("38250")
SAVERS_CREDIT_LIMIT_HOH = Decimal("57375")
SAVERS_CREDIT_LIMIT_MFJ = Decimal("76500")

# Standard Deduction (TY2025)
STANDARD_DEDUCTION = {
    "single": Decimal("15000"),
    "mfj": Decimal("30000"),
    "mfs": Decimal("15000"),
    "hoh": Decimal("22500"),
    "qw": Decimal("30000"),
}

# AMT Exemption Phaseout
AMT_EXEMPTION_SINGLE = Decimal("88100")
AMT_EXEMPTION_MFJ = Decimal("137000")
AMT_PHASEOUT_SINGLE = Decimal("626350")
AMT_PHASEOUT_MFJ = Decimal("1252700")

# Net Investment Income Tax (NIIT)
NIIT_THRESHOLD_SINGLE = Decimal("200000")
NIIT_THRESHOLD_MFJ = Decimal("250000")


# =============================================================================
# SKIP RULE CONDITIONS
# =============================================================================

class SkipRules:
    """
    Pre-defined skip conditions for tax questions.

    These are condition dictionaries that can be used with the
    QuestionnaireEngine's show_if/hide_if parameters.
    """

    # ------------------------------------
    # EITC (Earned Income Tax Credit)
    # ------------------------------------

    EITC_ELIGIBLE = {
        "and": [
            {"field": "filing_status", "op": "in", "value": ["single", "mfj", "hoh", "qw"]},
            {"field": "has_earned_income", "op": "equals", "value": True},
            # Investment income check
            {"field": "investment_income", "op": "lte", "value": 11600},
            # AGI check based on filing status and children - simplified
            {"or": [
                {"and": [
                    {"field": "filing_status", "op": "equals", "value": "mfj"},
                    {"field": "agi", "op": "lte", "value": 66460},
                ]},
                {"and": [
                    {"field": "filing_status", "op": "in", "value": ["single", "hoh", "qw"]},
                    {"field": "agi", "op": "lte", "value": 59899},
                ]},
            ]},
        ]
    }

    # Skip EITC if clearly ineligible (high income or MFS)
    SKIP_EITC = {
        "or": [
            {"field": "filing_status", "op": "equals", "value": "mfs"},
            {"field": "agi", "op": "gt", "value": 66460},
            {"field": "investment_income", "op": "gt", "value": 11600},
        ]
    }

    # ------------------------------------
    # Child Tax Credit
    # ------------------------------------

    CTC_ELIGIBLE = {
        "and": [
            {"field": "has_dependent_children", "op": "equals", "value": True},
            {"field": "youngest_child_age", "op": "lt", "value": 17},
        ]
    }

    SKIP_CTC = {
        "or": [
            {"field": "has_dependent_children", "op": "equals", "value": False},
            {"field": "youngest_child_age", "op": "gte", "value": 17},
        ]
    }

    # ------------------------------------
    # Education Credits
    # ------------------------------------

    EDUCATION_CREDITS_ELIGIBLE = {
        "and": [
            {"field": "has_education_expenses", "op": "equals", "value": True},
            {"or": [
                {"and": [
                    {"field": "filing_status", "op": "equals", "value": "mfj"},
                    {"field": "magi", "op": "lte", "value": 180000},
                ]},
                {"and": [
                    {"field": "filing_status", "op": "in", "value": ["single", "hoh", "qw"]},
                    {"field": "magi", "op": "lte", "value": 90000},
                ]},
            ]},
        ]
    }

    # AOTC requires student in first 4 years of college
    AOTC_ELIGIBLE = {
        "and": [
            EDUCATION_CREDITS_ELIGIBLE,
            {"field": "student_has_degree", "op": "equals", "value": False},
            {"field": "years_aotc_claimed", "op": "lt", "value": 4},
        ]
    }

    SKIP_EDUCATION_CREDITS = {
        "or": [
            {"field": "has_education_expenses", "op": "equals", "value": False},
            {"field": "filing_status", "op": "equals", "value": "mfs"},
            {"and": [
                {"field": "filing_status", "op": "equals", "value": "mfj"},
                {"field": "magi", "op": "gt", "value": 180000},
            ]},
            {"and": [
                {"field": "filing_status", "op": "in", "value": ["single", "hoh"]},
                {"field": "magi", "op": "gt", "value": 90000},
            ]},
        ]
    }

    # ------------------------------------
    # Rental Income
    # ------------------------------------

    RENTAL_SECTION_REQUIRED = {
        "or": [
            {"field": "has_rental_property", "op": "equals", "value": True},
            {"field": "rental_income", "op": "gt", "value": 0},
        ]
    }

    SKIP_RENTAL_SECTION = {
        "and": [
            {"field": "has_rental_property", "op": "equals", "value": False},
            {"field": "rental_income", "op": "in", "value": [None, 0]},
        ]
    }

    # ------------------------------------
    # Self-Employment
    # ------------------------------------

    SELF_EMPLOYMENT_SECTION_REQUIRED = {
        "or": [
            {"field": "is_self_employed", "op": "equals", "value": True},
            {"field": "has_1099_income", "op": "equals", "value": True},
            {"field": "self_employment_income", "op": "gt", "value": 0},
        ]
    }

    SKIP_SELF_EMPLOYMENT = {
        "and": [
            {"field": "is_self_employed", "op": "equals", "value": False},
            {"field": "has_1099_income", "op": "equals", "value": False},
            {"field": "self_employment_income", "op": "in", "value": [None, 0]},
        ]
    }

    # ------------------------------------
    # Itemized Deductions
    # ------------------------------------

    # Show itemized deductions section if total likely exceeds standard deduction
    ITEMIZED_DEDUCTIONS_LIKELY = {
        "or": [
            {"field": "mortgage_interest", "op": "gt", "value": 10000},
            {"field": "property_taxes", "op": "gt", "value": 5000},
            {"field": "charitable_contributions", "op": "gt", "value": 3000},
            {"and": [
                {"field": "filing_status", "op": "equals", "value": "single"},
                {"field": "estimated_itemized", "op": "gt", "value": 15000},
            ]},
            {"and": [
                {"field": "filing_status", "op": "equals", "value": "mfj"},
                {"field": "estimated_itemized", "op": "gt", "value": 30000},
            ]},
        ]
    }

    SKIP_ITEMIZED_DETAILS = {
        "and": [
            {"field": "will_itemize", "op": "equals", "value": False},
            {"field": "mortgage_interest", "op": "in", "value": [None, 0]},
            {"field": "charitable_contributions", "op": "lte", "value": 300},
        ]
    }

    # ------------------------------------
    # AMT (Alternative Minimum Tax)
    # ------------------------------------

    AMT_CHECK_REQUIRED = {
        "or": [
            {"field": "agi", "op": "gt", "value": 200000},
            {"field": "has_iso_exercise", "op": "equals", "value": True},
            {"field": "has_large_itemized", "op": "equals", "value": True},
        ]
    }

    SKIP_AMT = {
        "and": [
            {"field": "agi", "op": "lte", "value": 200000},
            {"field": "has_iso_exercise", "op": "equals", "value": False},
            {"field": "estimated_itemized", "op": "lte", "value": 50000},
        ]
    }

    # ------------------------------------
    # NIIT (Net Investment Income Tax)
    # ------------------------------------

    NIIT_APPLICABLE = {
        "and": [
            {"field": "has_investment_income", "op": "equals", "value": True},
            {"or": [
                {"and": [
                    {"field": "filing_status", "op": "equals", "value": "mfj"},
                    {"field": "magi", "op": "gt", "value": 250000},
                ]},
                {"and": [
                    {"field": "filing_status", "op": "in", "value": ["single", "hoh"]},
                    {"field": "magi", "op": "gt", "value": 200000},
                ]},
            ]},
        ]
    }

    SKIP_NIIT = {
        "or": [
            {"field": "has_investment_income", "op": "equals", "value": False},
            {"and": [
                {"field": "filing_status", "op": "equals", "value": "mfj"},
                {"field": "magi", "op": "lte", "value": 250000},
            ]},
            {"and": [
                {"field": "filing_status", "op": "in", "value": ["single", "hoh"]},
                {"field": "magi", "op": "lte", "value": 200000},
            ]},
        ]
    }

    # ------------------------------------
    # Retirement Savings Credit (Saver's Credit)
    # ------------------------------------

    SAVERS_CREDIT_ELIGIBLE = {
        "and": [
            {"field": "age", "op": "gte", "value": 18},
            {"field": "is_full_time_student", "op": "equals", "value": False},
            {"field": "retirement_contributions", "op": "gt", "value": 0},
            {"or": [
                {"and": [
                    {"field": "filing_status", "op": "equals", "value": "mfj"},
                    {"field": "agi", "op": "lte", "value": 76500},
                ]},
                {"and": [
                    {"field": "filing_status", "op": "equals", "value": "hoh"},
                    {"field": "agi", "op": "lte", "value": 57375},
                ]},
                {"and": [
                    {"field": "filing_status", "op": "in", "value": ["single", "mfs"]},
                    {"field": "agi", "op": "lte", "value": 38250},
                ]},
            ]},
        ]
    }

    # ------------------------------------
    # Foreign Income
    # ------------------------------------

    FOREIGN_INCOME_SECTION_REQUIRED = {
        "or": [
            {"field": "has_foreign_income", "op": "equals", "value": True},
            {"field": "foreign_earned_income", "op": "gt", "value": 0},
            {"field": "has_foreign_accounts", "op": "equals", "value": True},
        ]
    }

    SKIP_FOREIGN_INCOME = {
        "and": [
            {"field": "has_foreign_income", "op": "equals", "value": False},
            {"field": "foreign_earned_income", "op": "in", "value": [None, 0]},
            {"field": "has_foreign_accounts", "op": "equals", "value": False},
        ]
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Map of rule names to conditions
_SKIP_RULES_MAP = {
    # EITC
    "eitc_eligible": SkipRules.EITC_ELIGIBLE,
    "skip_eitc": SkipRules.SKIP_EITC,

    # Child Tax Credit
    "ctc_eligible": SkipRules.CTC_ELIGIBLE,
    "skip_ctc": SkipRules.SKIP_CTC,

    # Education
    "education_credits_eligible": SkipRules.EDUCATION_CREDITS_ELIGIBLE,
    "aotc_eligible": SkipRules.AOTC_ELIGIBLE,
    "skip_education_credits": SkipRules.SKIP_EDUCATION_CREDITS,

    # Rental
    "rental_section_required": SkipRules.RENTAL_SECTION_REQUIRED,
    "skip_rental": SkipRules.SKIP_RENTAL_SECTION,

    # Self-Employment
    "self_employment_required": SkipRules.SELF_EMPLOYMENT_SECTION_REQUIRED,
    "skip_self_employment": SkipRules.SKIP_SELF_EMPLOYMENT,

    # Itemized Deductions
    "itemized_likely": SkipRules.ITEMIZED_DEDUCTIONS_LIKELY,
    "skip_itemized": SkipRules.SKIP_ITEMIZED_DETAILS,

    # AMT
    "amt_check_required": SkipRules.AMT_CHECK_REQUIRED,
    "skip_amt": SkipRules.SKIP_AMT,

    # NIIT
    "niit_applicable": SkipRules.NIIT_APPLICABLE,
    "skip_niit": SkipRules.SKIP_NIIT,

    # Retirement
    "savers_credit_eligible": SkipRules.SAVERS_CREDIT_ELIGIBLE,

    # Foreign
    "foreign_income_required": SkipRules.FOREIGN_INCOME_SECTION_REQUIRED,
    "skip_foreign": SkipRules.SKIP_FOREIGN_INCOME,
}


def get_skip_condition(rule_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a skip condition by name.

    Args:
        rule_name: Name of the rule (e.g., "eitc_eligible", "skip_rental")

    Returns:
        Condition dictionary or None if not found
    """
    return _SKIP_RULES_MAP.get(rule_name.lower())


def get_available_rules() -> list:
    """Get list of available rule names."""
    return list(_SKIP_RULES_MAP.keys())


def create_income_threshold_condition(
    field: str,
    single_threshold: Decimal,
    mfj_threshold: Decimal,
    comparison: str = "lte",
    hoh_threshold: Optional[Decimal] = None,
) -> Dict[str, Any]:
    """
    Create an income threshold condition that varies by filing status.

    Args:
        field: The income field to check (e.g., "agi", "magi")
        single_threshold: Threshold for single filers
        mfj_threshold: Threshold for MFJ filers
        comparison: Comparison operator ("lte", "lt", "gte", "gt")
        hoh_threshold: Optional threshold for HOH (defaults to midpoint)

    Returns:
        Condition dictionary
    """
    if hoh_threshold is None:
        hoh_threshold = (single_threshold + mfj_threshold) / 2

    return {
        "or": [
            {"and": [
                {"field": "filing_status", "op": "equals", "value": "mfj"},
                {"field": field, "op": comparison, "value": float(mfj_threshold)},
            ]},
            {"and": [
                {"field": "filing_status", "op": "equals", "value": "hoh"},
                {"field": field, "op": comparison, "value": float(hoh_threshold)},
            ]},
            {"and": [
                {"field": "filing_status", "op": "in", "value": ["single", "mfs", "qw"]},
                {"field": field, "op": comparison, "value": float(single_threshold)},
            ]},
        ]
    }
