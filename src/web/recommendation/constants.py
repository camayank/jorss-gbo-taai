"""
Recommendation Constants - Tax Year Limits and Thresholds

SPEC-006: Centralized tax constants for 2025 tax year.
"""

from typing import Dict, Any

# =============================================================================
# TAX YEAR 2025 CONSTANTS
# =============================================================================

TAX_YEAR = 2025

# Standard Deductions (2025)
STANDARD_DEDUCTIONS = {
    "single": 15750,
    "married_filing_jointly": 31500,
    "married_filing_separately": 15750,
    "head_of_household": 23850,
    "qualifying_widow": 31500,
}

# Additional Standard Deduction (Age 65+ or Blind)
ADDITIONAL_STANDARD_DEDUCTION = {
    "single": 1950,
    "married": 1550,
}

# Tax Brackets (2025) - Marginal Rates
TAX_BRACKETS = {
    "single": [
        (11600, 0.10),
        (47150, 0.12),
        (100525, 0.22),
        (191950, 0.24),
        (243725, 0.32),
        (609350, 0.35),
        (float("inf"), 0.37),
    ],
    "married_filing_jointly": [
        (23200, 0.10),
        (94300, 0.12),
        (201050, 0.22),
        (383900, 0.24),
        (487450, 0.32),
        (731200, 0.35),
        (float("inf"), 0.37),
    ],
    "married_filing_separately": [
        (11600, 0.10),
        (47150, 0.12),
        (100525, 0.22),
        (191950, 0.24),
        (243725, 0.32),
        (365600, 0.35),
        (float("inf"), 0.37),
    ],
    "head_of_household": [
        (16550, 0.10),
        (63100, 0.12),
        (100500, 0.22),
        (191950, 0.24),
        (243700, 0.32),
        (609350, 0.35),
        (float("inf"), 0.37),
    ],
}

# =============================================================================
# RETIREMENT CONTRIBUTION LIMITS (2025)
# =============================================================================

RETIREMENT_LIMITS = {
    "401k_limit": 23500,
    "401k_catch_up_50plus": 7500,
    "401k_catch_up_60_63": 11250,  # New super catch-up
    "ira_limit": 7000,
    "ira_catch_up_50plus": 1000,
    "sep_ira_limit": 69000,
    "simple_ira_limit": 16500,
    "simple_ira_catch_up": 3500,
    "hsa_single": 4300,
    "hsa_family": 8550,
    "hsa_catch_up_55plus": 1000,
}

# Roth IRA Income Phase-out (2025)
ROTH_IRA_PHASEOUT = {
    "single": {"start": 150000, "end": 165000},
    "married_filing_jointly": {"start": 236000, "end": 246000},
    "married_filing_separately": {"start": 0, "end": 10000},
}

# Traditional IRA Deduction Phase-out (with employer plan)
TRAD_IRA_PHASEOUT = {
    "single": {"start": 79000, "end": 89000},
    "married_filing_jointly": {"start": 126000, "end": 146000},
    "married_filing_separately": {"start": 0, "end": 10000},
}

# =============================================================================
# CREDIT LIMITS AND PHASE-OUTS (2025)
# =============================================================================

CREDIT_LIMITS = {
    # Child Tax Credit
    "child_tax_credit": 2000,
    "child_tax_credit_refundable": 1700,
    "ctc_phaseout_single": 200000,
    "ctc_phaseout_mfj": 400000,

    # Earned Income Tax Credit (3+ children)
    "eitc_max_3plus": 7830,
    "eitc_phaseout_single": 59899,
    "eitc_phaseout_mfj": 66819,

    # Child and Dependent Care Credit
    "cdcc_max_one_child": 3000,
    "cdcc_max_two_plus": 6000,

    # Education Credits
    "aotc_max": 2500,
    "aotc_phaseout_single": {"start": 80000, "end": 90000},
    "aotc_phaseout_mfj": {"start": 160000, "end": 180000},
    "llc_max": 2000,

    # Saver's Credit
    "savers_credit_max": 1000,
    "savers_credit_phaseout_single": 38250,
    "savers_credit_phaseout_mfj": 76500,

    # Electric Vehicle Credit
    "ev_credit_max": 7500,
    "ev_credit_income_single": 150000,
    "ev_credit_income_mfj": 300000,
}

# =============================================================================
# DEDUCTION LIMITS (2025)
# =============================================================================

DEDUCTION_LIMITS = {
    # SALT Cap
    "salt_cap": 10000,

    # Mortgage Interest
    "mortgage_debt_limit": 750000,
    "mortgage_debt_limit_grandfathered": 1000000,

    # Charitable
    "charitable_cash_agi_limit": 0.60,
    "charitable_property_agi_limit": 0.30,

    # Medical
    "medical_agi_threshold": 0.075,

    # Student Loan Interest
    "student_loan_interest_max": 2500,
    "student_loan_phaseout_single": {"start": 80000, "end": 95000},
    "student_loan_phaseout_mfj": {"start": 165000, "end": 195000},

    # Educator Expense
    "educator_expense_max": 300,
}

# =============================================================================
# BUSINESS TAX LIMITS (2025)
# =============================================================================

BUSINESS_LIMITS = {
    # Section 199A QBI Deduction
    "qbi_deduction_rate": 0.20,
    "qbi_threshold_single": 191950,
    "qbi_threshold_mfj": 383900,
    "qbi_phaseout_range": 50000,
    "qbi_phaseout_range_mfj": 100000,

    # Section 179 Expensing
    "section_179_limit": 1220000,
    "section_179_phaseout_start": 3050000,

    # Bonus Depreciation (2025 - 40%)
    "bonus_depreciation_rate": 0.40,

    # Self-Employment Tax
    "se_tax_rate": 0.153,
    "se_tax_wage_base": 176100,
    "se_medicare_additional_threshold": 200000,
    "se_medicare_additional_rate": 0.009,

    # Home Office
    "home_office_simplified_rate": 5,
    "home_office_simplified_max_sqft": 300,
}

# =============================================================================
# AMT THRESHOLDS (2025)
# =============================================================================

AMT_LIMITS = {
    "exemption_single": 88100,
    "exemption_mfj": 137000,
    "exemption_mfs": 68500,
    "phaseout_single": 626350,
    "phaseout_mfj": 1252700,
    "rate_26_threshold": 232600,
    "rate_28_threshold": 232600,
}

# =============================================================================
# ESTATE AND GIFT TAX (2025)
# =============================================================================

ESTATE_GIFT_LIMITS = {
    "estate_exemption": 13610000,
    "annual_gift_exclusion": 18000,
    "gift_tax_rate": 0.40,
}

# =============================================================================
# MEDICARE IRMAA THRESHOLDS (2025)
# =============================================================================

MEDICARE_IRMAA = {
    "single": [
        (106000, 0),       # No surcharge
        (133000, 70.00),   # Tier 1
        (167000, 175.00),  # Tier 2
        (200000, 280.00),  # Tier 3
        (500000, 385.00),  # Tier 4
        (float("inf"), 419.90),  # Tier 5
    ],
    "married_filing_jointly": [
        (212000, 0),
        (266000, 70.00),
        (334000, 175.00),
        (400000, 280.00),
        (750000, 385.00),
        (float("inf"), 419.90),
    ],
}

# =============================================================================
# SOCIAL SECURITY (2025)
# =============================================================================

SOCIAL_SECURITY_LIMITS = {
    "wage_base": 176100,
    "tax_rate_employee": 0.062,
    "tax_rate_self_employed": 0.124,
    "full_retirement_age": 67,
    "early_retirement_reduction": 0.30,
    "delayed_credit_per_year": 0.08,
    "earnings_test_under_fra": 22320,
    "earnings_test_year_of_fra": 59520,
}

# =============================================================================
# KEY DATES AND DEADLINES
# =============================================================================

TAX_DEADLINES = {
    "filing_deadline": "April 15, 2026",
    "extension_deadline": "October 15, 2026",
    "q1_estimated": "April 15, 2025",
    "q2_estimated": "June 16, 2025",
    "q3_estimated": "September 15, 2025",
    "q4_estimated": "January 15, 2026",
    "roth_contribution_deadline": "April 15, 2026",
    "hsa_contribution_deadline": "April 15, 2026",
}

# =============================================================================
# FILING STATUS MAPPING
# =============================================================================

FILING_STATUS_MAP = {
    "single": "single",
    "s": "single",
    "married": "married_filing_jointly",
    "married_filing_jointly": "married_filing_jointly",
    "mfj": "married_filing_jointly",
    "married_filing_separately": "married_filing_separately",
    "mfs": "married_filing_separately",
    "head_of_household": "head_of_household",
    "hoh": "head_of_household",
    "qualifying_widow": "qualifying_widow",
    "qw": "qualifying_widow",
    "qualifying_surviving_spouse": "qualifying_widow",
}

def get_standard_deduction(filing_status: str) -> float:
    """Get standard deduction for filing status."""
    status = FILING_STATUS_MAP.get(filing_status.lower(), "single")
    return STANDARD_DEDUCTIONS.get(status, STANDARD_DEDUCTIONS["single"])

def get_retirement_limit(limit_name: str) -> float:
    """Get retirement contribution limit."""
    return RETIREMENT_LIMITS.get(limit_name, 0)

def get_credit_limit(limit_name: str) -> float:
    """Get credit limit or threshold."""
    return CREDIT_LIMITS.get(limit_name, 0)
