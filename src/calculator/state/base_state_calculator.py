"""Base class for state tax calculators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional, TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig


@dataclass
class StateCalculationBreakdown:
    """
    Complete breakdown of state tax calculation.
    Mirrors federal CalculationBreakdown for consistency.
    """

    state_code: str
    state_name: str
    tax_year: int
    filing_status: str

    # Income calculation
    federal_agi: float
    federal_taxable_income: float
    state_additions: float
    state_subtractions: float
    state_adjusted_income: float

    # Deductions
    state_standard_deduction: float
    state_itemized_deductions: float
    deduction_used: str  # "standard" or "itemized"
    deduction_amount: float

    # Exemptions
    personal_exemptions: int
    dependent_exemptions: int
    exemption_amount: float

    # Taxable income
    state_taxable_income: float

    # Tax calculation
    state_tax_before_credits: float

    # Credits
    state_credits: Dict[str, float] = field(default_factory=dict)
    total_state_credits: float = 0.0

    # Local tax (if applicable)
    local_tax: float = 0.0

    # Final amounts
    state_tax_liability: float = 0.0
    state_withholding: float = 0.0
    state_refund_or_owed: float = 0.0


class BaseStateCalculator(ABC):
    """
    Abstract base class for state tax calculators.

    Each state implements this class with state-specific logic for:
    - Income adjustments (additions and subtractions)
    - Deduction calculations
    - Credit calculations
    - Special rules (Social Security, pension exclusions, etc.)
    """

    def __init__(self, config: StateTaxConfig):
        self.config = config

    @abstractmethod
    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """
        Calculate state tax for the given return.

        Args:
            tax_return: The federal tax return with income, deductions, etc.

        Returns:
            StateCalculationBreakdown with complete state tax calculation.
        """
        pass

    def get_starting_income(self, tax_return: "TaxReturn") -> float:
        """
        Get the starting point for state taxable income calculation.

        Different states start from different federal amounts:
        - federal_agi: Most common (CA, NY, etc.)
        - federal_taxable_income: MN, OR, VT, etc.
        - gross_income: NJ
        """
        if self.config.starts_from == "federal_taxable_income":
            return tax_return.taxable_income or 0.0
        elif self.config.starts_from == "gross_income":
            return tax_return.income.get_total_income()
        else:  # federal_agi (default)
            return tax_return.adjusted_gross_income or 0.0

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate additions to federal income for state purposes.

        Common additions include:
        - Interest from other states' municipal bonds
        - Federal deductions not allowed by state
        - Income excluded federally but taxable by state

        Override in subclasses for state-specific additions.
        """
        return 0.0

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate subtractions from federal income for state purposes.

        Common subtractions include:
        - Social Security benefits (exempt in many states)
        - US government interest
        - State income tax refund
        - Pension/retirement income exclusions

        Override in subclasses for state-specific subtractions.
        """
        subtractions = 0.0

        # Social Security exemption (if state doesn't tax it)
        if not self.config.social_security_taxable:
            subtractions += tax_return.income.taxable_social_security

        return subtractions

    def calculate_brackets(self, taxable_income: float, filing_status: str) -> float:
        """
        Calculate tax using progressive brackets or flat rate.

        Args:
            taxable_income: State taxable income after deductions
            filing_status: Filing status for bracket lookup

        Returns:
            Tax amount before credits
        """
        if taxable_income <= 0:
            return 0.0

        if self.config.is_flat_tax:
            return float(money(taxable_income * (self.config.flat_rate or 0.0)))

        brackets = self.config.get_brackets(filing_status)
        if not brackets:
            return 0.0

        tax = 0.0
        for idx, (floor, rate) in enumerate(brackets):
            if idx == len(brackets) - 1:
                # Top bracket - no ceiling
                amount = max(0.0, taxable_income - floor)
                tax += amount * rate
                break

            next_floor = brackets[idx + 1][0]
            amount = min(max(taxable_income - floor, 0.0), next_floor - floor)
            tax += amount * rate

        return float(money(tax))

    def calculate_local_tax(
        self,
        taxable_income: float,
        filing_status: str
    ) -> float:
        """
        Calculate local income tax (NYC, Maryland counties, etc.).

        Override in subclasses for states with local taxes.
        """
        if not self.config.has_local_tax or not self.config.local_tax_brackets:
            return 0.0

        brackets = self.config.local_tax_brackets.get(
            filing_status,
            self.config.local_tax_brackets.get("single", [])
        )

        tax = 0.0
        for idx, (floor, rate) in enumerate(brackets):
            if idx == len(brackets) - 1:
                amount = max(0.0, taxable_income - floor)
                tax += amount * rate
                break

            next_floor = brackets[idx + 1][0]
            amount = min(max(taxable_income - floor, 0.0), next_floor - floor)
            tax += amount * rate

        return float(money(tax))

    def calculate_state_eitc(self, federal_eitc: float) -> float:
        """
        Calculate state EITC based on federal EITC.

        Many states provide a state EITC as a percentage of the federal credit.
        """
        if self.config.eitc_percentage and federal_eitc > 0:
            return float(money(federal_eitc * self.config.eitc_percentage))
        return 0.0

    def calculate_state_child_tax_credit(
        self,
        num_children: int,
        agi: float
    ) -> float:
        """
        Calculate state child tax credit.

        Override in subclasses for states with more complex credit rules.
        """
        if self.config.child_tax_credit_amount and num_children > 0:
            return float(money(num_children * self.config.child_tax_credit_amount))
        return 0.0

    def get_state_withholding(self, tax_return: "TaxReturn") -> float:
        """Get total state tax withholding from W-2 forms."""
        return sum(
            w2.state_tax_withheld or 0.0
            for w2 in tax_return.income.w2_forms
        )

    def _get_filing_status_key(self, filing_status: str) -> str:
        """
        Normalize filing status to match bracket keys.

        Some state configs may use different key formats.
        """
        status_map = {
            "single": "single",
            "married_joint": "married_joint",
            "married_filing_jointly": "married_joint",
            "married_separate": "married_separate",
            "married_filing_separately": "married_separate",
            "head_of_household": "head_of_household",
            "qualifying_widow": "qualifying_widow",
            "qualifying_surviving_spouse": "qualifying_widow",
        }
        return status_map.get(filing_status.lower(), "single")
