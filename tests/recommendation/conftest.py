"""Shared fixtures and factories for recommendation engine tests."""

import os
import sys
from pathlib import Path
from decimal import Decimal
from copy import deepcopy
from typing import Optional

import pytest
from unittest.mock import Mock, MagicMock, patch

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from models.taxpayer import TaxpayerInfo, FilingStatus, Dependent
from models.tax_return import TaxReturn
from models.deductions import Deductions, ItemizedDeductions
from models.credits import TaxCredits
from models.income_legacy import Income


# ---------------------------------------------------------------------------
# Helper: build a minimal Income with optional overrides
# ---------------------------------------------------------------------------


def _make_income(**overrides) -> Income:
    """Create a minimal Income object, applying *overrides* on top of defaults."""
    defaults = dict(
        self_employment_income=0.0,
        self_employment_expenses=0.0,
        interest_income=0.0,
        dividend_income=0.0,
        qualified_dividends=0.0,
        short_term_capital_gains=0.0,
        short_term_capital_losses=0.0,
        long_term_capital_gains=0.0,
        long_term_capital_losses=0.0,
        rental_income=0.0,
        unemployment_compensation=0.0,
        social_security_benefits=0.0,
        taxable_social_security=0.0,
    )
    defaults.update(overrides)
    return Income(**defaults)


# ---------------------------------------------------------------------------
# Dependent presets
# ---------------------------------------------------------------------------


def _child(name: str = "Child One", age: int = 8, relationship: str = "son") -> Dependent:
    return Dependent(name=name, age=age, relationship=relationship)


def _teen(name: str = "Teen One", age: int = 15, relationship: str = "daughter") -> Dependent:
    return Dependent(name=name, age=age, relationship=relationship)


def _college_student(name: str = "Student One", age: int = 20, relationship: str = "son") -> Dependent:
    return Dependent(name=name, age=age, relationship=relationship, is_student=True)


def _adult_dependent(name: str = "Parent Dep", age: int = 72, relationship: str = "parent") -> Dependent:
    return Dependent(name=name, age=age, relationship=relationship)


# ---------------------------------------------------------------------------
# TaxpayerInfo presets
# ---------------------------------------------------------------------------


@pytest.fixture
def single_filer():
    """Single filer, no dependents, age 35."""
    return TaxpayerInfo(
        first_name="Alice",
        last_name="Smith",
        filing_status=FilingStatus.SINGLE,
    )


@pytest.fixture
def married_couple():
    """Married filing jointly, no dependents."""
    return TaxpayerInfo(
        first_name="Bob",
        last_name="Jones",
        filing_status=FilingStatus.MARRIED_JOINT,
        spouse_first_name="Carol",
        spouse_last_name="Jones",
        is_blind=False,
        is_over_65=False,
    )


@pytest.fixture
def married_couple_with_children():
    """Married filing jointly with two young children."""
    return TaxpayerInfo(
        first_name="Bob",
        last_name="Jones",
        filing_status=FilingStatus.MARRIED_JOINT,
        spouse_first_name="Carol",
        spouse_last_name="Jones",
        dependents=[_child("Child A", 5), _child("Child B", 10)],
    )


@pytest.fixture
def hoh_parent():
    """Head of Household with one child."""
    return TaxpayerInfo(
        first_name="Dana",
        last_name="Lee",
        filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
        dependents=[_child("Kid Lee", 7)],
    )


@pytest.fixture
def married_separate_filer():
    """Married filing separately."""
    return TaxpayerInfo(
        first_name="Eve",
        last_name="Rowe",
        filing_status=FilingStatus.MARRIED_SEPARATE,
        spouse_first_name="Frank",
        spouse_last_name="Rowe",
    )


@pytest.fixture
def qualifying_widow_filer():
    """Qualifying widow(er) with a dependent child."""
    tp = TaxpayerInfo(
        first_name="Grace",
        last_name="Kim",
        filing_status=FilingStatus.QUALIFYING_WIDOW,
        dependents=[_child("Child Kim", 6)],
    )
    # The optimizer checks for this attribute
    tp.__dict__["spouse_died_year"] = 2024
    return tp


@pytest.fixture
def senior_single_filer():
    """Single filer age 67, blind."""
    return TaxpayerInfo(
        first_name="Henry",
        last_name="Dunn",
        filing_status=FilingStatus.SINGLE,
        is_over_65=True,
        is_blind=True,
    )


@pytest.fixture
def senior_married_couple():
    """Married couple both over 65."""
    return TaxpayerInfo(
        first_name="Irene",
        last_name="Park",
        filing_status=FilingStatus.MARRIED_JOINT,
        spouse_first_name="Jack",
        spouse_last_name="Park",
        is_over_65=True,
        spouse_is_over_65=True,
    )


# ---------------------------------------------------------------------------
# Income-level presets
# ---------------------------------------------------------------------------


INCOME_LEVELS = {
    "low": 25000,
    "moderate": 60000,
    "middle": 100000,
    "upper_middle": 200000,
    "high": 500000,
}


@pytest.fixture(params=INCOME_LEVELS.values(), ids=INCOME_LEVELS.keys())
def income_level(request):
    """Parametrized income level fixture."""
    return request.param


@pytest.fixture
def low_income():
    return _make_income()


@pytest.fixture
def moderate_w2_income():
    return _make_income()


@pytest.fixture
def high_w2_income():
    return _make_income()


@pytest.fixture
def self_employment_income():
    return _make_income(self_employment_income=120000, self_employment_expenses=20000)


@pytest.fixture
def investment_income():
    return _make_income(
        interest_income=15000,
        dividend_income=25000,
        qualified_dividends=20000,
        long_term_capital_gains=50000,
    )


@pytest.fixture
def mixed_income():
    return _make_income(
        self_employment_income=40000,
        interest_income=5000,
        dividend_income=3000,
        long_term_capital_gains=10000,
    )


# ---------------------------------------------------------------------------
# Deduction presets
# ---------------------------------------------------------------------------


@pytest.fixture
def standard_deductions():
    return Deductions(use_standard_deduction=True)


@pytest.fixture
def itemized_heavy():
    return Deductions(
        use_standard_deduction=False,
        itemized=ItemizedDeductions(
            medical_expenses=15000,
            state_local_income_tax=8000,
            real_estate_tax=6000,
            mortgage_interest=12000,
            charitable_cash=5000,
            charitable_non_cash=2000,
        ),
    )


@pytest.fixture
def itemized_light():
    return Deductions(
        use_standard_deduction=False,
        itemized=ItemizedDeductions(
            state_local_income_tax=3000,
            mortgage_interest=4000,
            charitable_cash=1000,
        ),
    )


# ---------------------------------------------------------------------------
# Credit presets
# ---------------------------------------------------------------------------


@pytest.fixture
def no_credits():
    return TaxCredits()


@pytest.fixture
def family_credits():
    return TaxCredits(
        child_care_expenses=6000,
        child_tax_credit_children=2,
    )


@pytest.fixture
def education_credits():
    return TaxCredits(education_expenses=4000, education_credit_type="AOTC")


# ---------------------------------------------------------------------------
# Full TaxReturn factory
# ---------------------------------------------------------------------------


def make_tax_return(
    taxpayer: Optional[TaxpayerInfo] = None,
    income: Optional[Income] = None,
    deductions: Optional[Deductions] = None,
    credits: Optional[TaxCredits] = None,
    agi: Optional[float] = None,
    tax_liability: Optional[float] = None,
) -> TaxReturn:
    """Build a TaxReturn with sensible defaults; override any piece."""
    tp = taxpayer or TaxpayerInfo(
        first_name="Test",
        last_name="User",
        filing_status=FilingStatus.SINGLE,
    )
    inc = income or _make_income()
    ded = deductions or Deductions(use_standard_deduction=True)
    crd = credits or TaxCredits()

    tr = TaxReturn(
        taxpayer=tp,
        income=inc,
        deductions=ded,
        credits=crd,
    )
    if agi is not None:
        tr.adjusted_gross_income = agi
    if tax_liability is not None:
        tr.tax_liability = tax_liability
    return tr


@pytest.fixture
def make_return():
    """Expose make_tax_return as a fixture callable."""
    return make_tax_return


# ---------------------------------------------------------------------------
# W2 helper for income with wages (creates W2Info objects)
# ---------------------------------------------------------------------------


def make_w2_income(wages: float, federal_withheld: float = 0.0) -> Income:
    """Create an Income object containing a single W-2 with given wages."""
    from models.income_legacy import W2Info

    w2 = W2Info(
        employer_name="Acme Corp",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )
    return _make_income(w2_forms=[w2])


@pytest.fixture
def w2_income_factory():
    """Expose make_w2_income as a fixture callable."""
    return make_w2_income
