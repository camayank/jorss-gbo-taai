"""Predefined edge case scenarios for tax calculation testing."""

LIFE_EVENT_SCENARIOS = {
    "death_mid_year": {
        "description": "Taxpayer died June 15",
        "filing_status": "single",
        "total_income": 75000,
        "is_final_return": True,
        "expected_tax_range": (7000, 12000),
    },
    "mid_year_marriage": {
        "description": "Married October 15, filing MFJ",
        "filing_status": "married_filing_jointly",
        "spouse1_income": 80000,
        "spouse2_income": 60000,
        "expected_tax_range": (18000, 25000),
    },
    "mid_year_divorce": {
        "description": "Divorced March 1, filing single",
        "filing_status": "single",
        "total_income": 95000,
        "expected_tax_range": (14000, 18000),
    },
}

INCOME_BOUNDARY_SCENARIOS = {
    "zero_income": {
        "description": "Zero income return",
        "filing_status": "single",
        "total_income": 0,
        "expected_tax": 0,
    },
    "at_standard_deduction": {
        "description": "Income equals standard deduction",
        "filing_status": "single",
        "total_income": 15000,
        "expected_tax": 0,
    },
    "maximum_income": {
        "description": "Very high income ($10M)",
        "filing_status": "single",
        "total_income": 10000000,
        "expected_effective_rate_min": 0.30,
    },
    "negative_agi": {
        "description": "Business losses exceed income",
        "filing_status": "single",
        "total_income": 50000,
        "business_loss": -100000,
        "expected_tax": 0,
    },
}

PHASEOUT_SCENARIOS = {
    "ctc_at_phaseout_start": {
        "description": "CTC at $200,000 phaseout start (single)",
        "filing_status": "single",
        "total_income": 200000,
        "num_children": 2,
        "expected_ctc": 4000,
    },
    "eitc_maximum": {
        "description": "EITC at maximum credit income",
        "filing_status": "single",
        "earned_income": 17500,
        "num_children": 3,
        "expected_eitc_min": 7000,
    },
    "education_credit_phaseout": {
        "description": "AOTC at phaseout",
        "filing_status": "single",
        "total_income": 85000,
        "education_expenses": 4000,
        "expected_credit_range": (1000, 2500),
    },
}

AMT_SCENARIOS = {
    "amt_high_salt": {
        "description": "AMT triggered by high SALT",
        "filing_status": "married_filing_jointly",
        "total_income": 500000,
        "salt_deduction": 50000,
        "expected_amt_min": 5000,
    },
    "amt_iso_exercise": {
        "description": "AMT triggered by ISO exercise",
        "filing_status": "single",
        "total_income": 200000,
        "iso_bargain_element": 300000,
        "expected_amt_min": 20000,
    },
}

# 2025 Tax Constants for reference
TAX_CONSTANTS_2025 = {
    "standard_deduction_single": 15000,
    "standard_deduction_mfj": 30000,
    "standard_deduction_hoh": 22500,
    "ctc_per_child": 2000,
    "ctc_phaseout_single": 200000,
    "ctc_phaseout_mfj": 400000,
    "salt_cap": 10000,
    "amt_exemption_single": 85700,
    "amt_exemption_mfj": 133300,
    "top_bracket_rate": 0.37,
    "top_bracket_start_single": 609350,
}
