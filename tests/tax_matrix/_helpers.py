"""
Shared helper functions and constants for tax matrix tests.

This module is imported by the test files directly. Fixtures remain
in conftest.py (auto-discovered by pytest).
"""
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from models.taxpayer import TaxpayerInfo, FilingStatus, Dependent
from models.income import Income, W2Info
from models.deductions import Deductions, ItemizedDeductions
from models.credits import TaxCredits
from models.tax_return import TaxReturn


# ---------------------------------------------------------------------------
# 2025 tax year constants (IRS Rev. Proc. 2024-40)
# ---------------------------------------------------------------------------
STD_DEDUCTION = {
    "single": 15750.0,
    "married_joint": 31500.0,
    "married_separate": 15750.0,
    "head_of_household": 23850.0,
    "qualifying_widow": 31500.0,
}

BRACKETS_2025 = {
    "single": [
        (0, 0.10), (11925, 0.12), (48475, 0.22),
        (103350, 0.24), (197300, 0.32), (250525, 0.35), (626350, 0.37),
    ],
    "married_joint": [
        (0, 0.10), (23850, 0.12), (96950, 0.22),
        (206700, 0.24), (394600, 0.32), (501050, 0.35), (751600, 0.37),
    ],
    "married_separate": [
        (0, 0.10), (11925, 0.12), (48475, 0.22),
        (103350, 0.24), (197300, 0.32), (250525, 0.35), (375800, 0.37),
    ],
    "head_of_household": [
        (0, 0.10), (17050, 0.12), (64850, 0.22),
        (103350, 0.24), (197300, 0.32), (250525, 0.35), (626350, 0.37),
    ],
    "qualifying_widow": [
        (0, 0.10), (23850, 0.12), (96950, 0.22),
        (206700, 0.24), (394600, 0.32), (501050, 0.35), (751600, 0.37),
    ],
}

SS_WAGE_BASE_2025 = 176100.0
SE_TAX_RATE = 0.153
SE_NET_EARNINGS_FACTOR = 0.9235

ALL_FILING_STATUSES = [
    FilingStatus.SINGLE,
    FilingStatus.MARRIED_JOINT,
    FilingStatus.MARRIED_SEPARATE,
    FilingStatus.HEAD_OF_HOUSEHOLD,
    FilingStatus.QUALIFYING_WIDOW,
]

NO_INCOME_TAX_STATES = {"AK", "FL", "NV", "SD", "TX", "WA", "WY", "TN", "NH"}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def make_dependent(name: str = "Child", age: int = 5, relationship: str = "son") -> Dependent:
    """Create a Dependent with minimal required fields."""
    return Dependent(name=name, age=age, relationship=relationship)


def make_dependents(count: int) -> List[Dependent]:
    """Create a list of child dependents."""
    names = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
    return [
        make_dependent(
            name=names[i % len(names)],
            age=5 + i,
            relationship="son" if i % 2 == 0 else "daughter",
        )
        for i in range(count)
    ]


def make_taxpayer(
    filing_status: FilingStatus,
    num_dependents: int = 0,
    state: Optional[str] = None,
) -> TaxpayerInfo:
    """Create a TaxpayerInfo with sensible defaults."""
    return TaxpayerInfo(
        first_name="Test",
        last_name="Taxpayer",
        filing_status=filing_status,
        dependents=make_dependents(num_dependents),
        state=state,
    )


def make_income(
    wages: float = 0.0,
    se_income: float = 0.0,
    se_expenses: float = 0.0,
    interest: float = 0.0,
    dividends: float = 0.0,
    qualified_dividends: float = 0.0,
    federal_withheld: float = 0.0,
    state_withheld: float = 0.0,
    lt_cap_gains: float = 0.0,
    st_cap_gains: float = 0.0,
    other_income: float = 0.0,
) -> Income:
    """Create an Income object from common parameters."""
    w2_list = []
    if wages > 0:
        w2_list.append(W2Info(
            employer_name="Acme Corp",
            wages=wages,
            federal_tax_withheld=federal_withheld,
            state_wages=wages,
            state_tax_withheld=state_withheld,
        ))
    return Income(
        w2_forms=w2_list,
        self_employment_income=se_income,
        self_employment_expenses=se_expenses,
        interest_income=interest,
        dividend_income=dividends,
        qualified_dividends=qualified_dividends,
        long_term_capital_gains=lt_cap_gains,
        short_term_capital_gains=st_cap_gains,
        other_income=other_income,
    )


def make_deductions(
    use_standard: bool = True,
    medical: float = 0.0,
    state_local_tax: float = 0.0,
    real_estate_tax: float = 0.0,
    mortgage_interest: float = 0.0,
    mortgage_principal: float = 0.0,
    is_grandfathered: bool = False,
    charitable_cash: float = 0.0,
    charitable_non_cash: float = 0.0,
    student_loan_interest: float = 0.0,
    personal_property_tax: float = 0.0,
) -> Deductions:
    """Create a Deductions object from common parameters."""
    itemized = ItemizedDeductions(
        medical_expenses=medical,
        state_local_income_tax=state_local_tax,
        real_estate_tax=real_estate_tax,
        mortgage_interest=mortgage_interest,
        mortgage_principal=mortgage_principal,
        is_grandfathered_debt=is_grandfathered,
        charitable_cash=charitable_cash,
        charitable_non_cash=charitable_non_cash,
        personal_property_tax=personal_property_tax,
    )
    return Deductions(
        use_standard_deduction=use_standard,
        itemized=itemized,
        student_loan_interest=student_loan_interest,
    )


def make_credits(
    child_care_expenses: float = 0.0,
    foreign_tax_credit: float = 0.0,
    residential_energy_credit: float = 0.0,
    other_credits: float = 0.0,
) -> TaxCredits:
    """Create a TaxCredits object from common parameters."""
    return TaxCredits(
        child_care_expenses=child_care_expenses,
        foreign_tax_credit=foreign_tax_credit,
        residential_energy_credit=residential_energy_credit,
        other_credits=other_credits,
    )


def make_tax_return(
    filing_status: FilingStatus = FilingStatus.SINGLE,
    wages: float = 0.0,
    se_income: float = 0.0,
    se_expenses: float = 0.0,
    interest: float = 0.0,
    dividends: float = 0.0,
    qualified_dividends: float = 0.0,
    federal_withheld: float = 0.0,
    state_withheld: float = 0.0,
    lt_cap_gains: float = 0.0,
    st_cap_gains: float = 0.0,
    other_income: float = 0.0,
    num_dependents: int = 0,
    use_standard_deduction: bool = True,
    medical: float = 0.0,
    state_local_tax: float = 0.0,
    real_estate_tax: float = 0.0,
    mortgage_interest: float = 0.0,
    mortgage_principal: float = 0.0,
    is_grandfathered: bool = False,
    charitable_cash: float = 0.0,
    charitable_non_cash: float = 0.0,
    student_loan_interest: float = 0.0,
    personal_property_tax: float = 0.0,
    child_care_expenses: float = 0.0,
    other_credits: float = 0.0,
    residential_energy_credit: float = 0.0,
    state: Optional[str] = None,
) -> TaxReturn:
    """
    Factory to build a complete TaxReturn from keyword arguments.

    This is the primary helper for parameterised matrix tests.
    """
    taxpayer = make_taxpayer(filing_status, num_dependents=num_dependents, state=state)
    income = make_income(
        wages=wages,
        se_income=se_income,
        se_expenses=se_expenses,
        interest=interest,
        dividends=dividends,
        qualified_dividends=qualified_dividends,
        federal_withheld=federal_withheld,
        state_withheld=state_withheld,
        lt_cap_gains=lt_cap_gains,
        st_cap_gains=st_cap_gains,
        other_income=other_income,
    )
    deductions = make_deductions(
        use_standard=use_standard_deduction,
        medical=medical,
        state_local_tax=state_local_tax,
        real_estate_tax=real_estate_tax,
        mortgage_interest=mortgage_interest,
        mortgage_principal=mortgage_principal,
        is_grandfathered=is_grandfathered,
        charitable_cash=charitable_cash,
        charitable_non_cash=charitable_non_cash,
        student_loan_interest=student_loan_interest,
        personal_property_tax=personal_property_tax,
    )
    credits = make_credits(
        child_care_expenses=child_care_expenses,
        other_credits=other_credits,
        residential_energy_credit=residential_energy_credit,
    )
    return TaxReturn(
        taxpayer=taxpayer,
        income=income,
        deductions=deductions,
        credits=credits,
        state_of_residence=state,
    )


def compute_expected_tax_on_ordinary(taxable_income: float, filing_status: str) -> float:
    """
    Manually compute expected ordinary-income tax from the 2025 bracket table.

    Useful as a reference implementation to validate the engine.
    """
    brackets = BRACKETS_2025[filing_status]
    tax = 0.0
    for i, (threshold, rate) in enumerate(brackets):
        upper = brackets[i + 1][0] if i + 1 < len(brackets) else float("inf")
        if taxable_income <= threshold:
            break
        taxed = min(taxable_income, upper) - threshold
        if taxed > 0:
            tax += taxed * rate
    return round(tax, 2)
