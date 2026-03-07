"""Shared Hypothesis strategies for property-based testing."""

import sys
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from hypothesis import strategies as st, settings

from models.taxpayer import TaxpayerInfo, FilingStatus, Dependent
from models.tax_return import TaxReturn
from models.deductions import Deductions, ItemizedDeductions
from models.credits import TaxCredits
from models.income_legacy import Income


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

# All 50 US states + DC
US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
]


@st.composite
def dependent_strategy(draw):
    """Generate a random valid Dependent."""
    # Use only ASCII letters (Dependent model validates name characters)
    name = draw(st.text(
        min_size=1, max_size=30,
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
    )).strip()
    if not name:
        name = "Child"
    return Dependent(
        name=name,
        age=draw(st.integers(min_value=0, max_value=90)),
        relationship=draw(st.sampled_from([
            "son", "daughter", "stepson", "stepdaughter",
            "brother", "sister", "parent", "grandchild",
        ])),
    )


@st.composite
def income_strategy(draw):
    """Generate a random valid Income object."""
    wages = draw(st.lists(st.builds(
        lambda: {"employer": "Test Corp", "wages": draw(st.floats(min_value=0, max_value=500000, allow_nan=False, allow_infinity=False, allow_subnormal=False))},
    ), min_size=0, max_size=2))

    return Income(
        w2s=[],  # W2Info objects are complex; test with direct fields
        self_employment_income=draw(st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        self_employment_expenses=draw(st.floats(min_value=0, max_value=500_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        interest_income=draw(st.floats(min_value=0, max_value=100_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        dividend_income=draw(st.floats(min_value=0, max_value=200_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        qualified_dividends=draw(st.floats(min_value=0, max_value=200_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        short_term_capital_gains=draw(st.floats(min_value=0, max_value=500_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        short_term_capital_losses=draw(st.floats(min_value=0, max_value=500_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        long_term_capital_gains=draw(st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        long_term_capital_losses=draw(st.floats(min_value=0, max_value=500_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        rental_income=draw(st.floats(min_value=0, max_value=500_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        unemployment_compensation=draw(st.floats(min_value=0, max_value=50_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        social_security_benefits=draw(st.floats(min_value=0, max_value=100_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        taxable_social_security=draw(st.floats(min_value=0, max_value=85_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
    )


@st.composite
def itemized_deductions_strategy(draw):
    """Generate random ItemizedDeductions."""
    return ItemizedDeductions(
        medical_expenses=draw(st.floats(min_value=0, max_value=100_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        state_local_income_tax=draw(st.floats(min_value=0, max_value=50_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        real_estate_tax=draw(st.floats(min_value=0, max_value=30_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        mortgage_interest=draw(st.floats(min_value=0, max_value=50_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        charitable_cash=draw(st.floats(min_value=0, max_value=100_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        charitable_non_cash=draw(st.floats(min_value=0, max_value=50_000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
    )


@st.composite
def deductions_strategy(draw):
    """Generate random Deductions."""
    return Deductions(
        itemized=draw(itemized_deductions_strategy()),
        student_loan_interest=draw(st.floats(min_value=0, max_value=2500, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        educator_expenses=draw(st.floats(min_value=0, max_value=300, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        ira_deduction=draw(st.floats(min_value=0, max_value=7000, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
        hsa_deduction=draw(st.floats(min_value=0, max_value=8300, allow_nan=False, allow_infinity=False, allow_subnormal=False)),
    )


@st.composite
def taxpayer_strategy(draw):
    """Generate a random valid TaxpayerInfo."""
    filing_status = draw(st.sampled_from(list(FilingStatus)))
    num_deps = draw(st.integers(min_value=0, max_value=5))
    dependents = [draw(dependent_strategy()) for _ in range(num_deps)]

    return TaxpayerInfo(
        first_name="Test",
        last_name="User",
        filing_status=filing_status,
        dependents=dependents,
        is_over_65=draw(st.booleans()),
        is_blind=draw(st.booleans()),
    )


@st.composite
def tax_return_strategy(draw):
    """Generate a complete random valid TaxReturn."""
    taxpayer = draw(taxpayer_strategy())
    income = draw(income_strategy())
    deductions = draw(deductions_strategy())
    state = draw(st.sampled_from(US_STATES + [None]))

    return TaxReturn(
        taxpayer=taxpayer,
        income=income,
        deductions=deductions,
        credits=TaxCredits(),
        state_of_residence=state,
    )
