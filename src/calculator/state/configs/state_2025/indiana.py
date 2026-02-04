"""Indiana state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_indiana_config() -> StateTaxConfig:
    """Create Indiana tax configuration for 2025."""
    return StateTaxConfig(
        state_code="IN",
        state_name="Indiana",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.030,  # 3.0% flat rate (reduced from 3.05% in 2024)
        brackets=None,
        starts_from="federal_agi",
        standard_deduction={
            # Indiana has no standard deduction (uses exemptions)
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        personal_exemption_amount={
            # Indiana personal exemption 2025
            "single": 1000,
            "married_joint": 2000,  # $1,000 each
            "married_separate": 1000,
            "head_of_household": 1000,
            "qualifying_widow": 1000,
        },
        dependent_exemption_amount=1500,  # Per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # IN exempts Social Security
        pension_exclusion_limit=None,  # IN has deductions for military/police pensions
        military_pay_exempt=True,  # IN exempts military pay
        eitc_percentage=0.10,  # IN EITC is 10% of federal
        child_tax_credit_amount=0,
        has_local_tax=True,  # All IN counties have local income tax (0.5% - 3.0%)
    )


@register_state("IN", 2025)
class IndianaCalculator(BaseStateCalculator):
    """
    Indiana state tax calculator.

    Indiana has:
    - Flat 3.0% state tax rate (2025, reduced from 3.05%)
    - County income tax (all 92 counties, 0.5% - 3.0%)
    - Personal exemption: $1,000 per taxpayer
    - Dependent exemption: $1,500 per dependent
    - Additional exemption for age 65+ and blind
    - Full exemption of Social Security
    - Military/police/firefighter pension exemption
    - Indiana EITC (10% of federal)
    - Unified tax credit for low income
    """

    def __init__(self):
        super().__init__(get_indiana_config())
        self._county_rate = 0.015  # Average county rate (actual varies)

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Indiana state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Indiana additions
        additions = self.calculate_state_additions(tax_return)

        # Indiana subtractions/deductions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Indiana adjusted gross income
        in_agi = federal_agi + additions - subtractions

        # Indiana has no standard/itemized deduction (uses exemptions only)
        std_deduction = 0.0
        itemized = 0.0
        deduction_used = "none"
        deduction_amount = 0.0

        # Exemptions
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)

        personal_exemption_amt = self.config.get_personal_exemption(filing_status)
        dependent_exemption_amt = (
            dependent_exemptions * self.config.dependent_exemption_amount
        )

        # Additional exemptions (age 65+, blind)
        additional_exemptions = self._calculate_additional_exemptions(tax_return)

        exemption_amount = personal_exemption_amt + dependent_exemption_amt + additional_exemptions

        # Indiana taxable income
        in_taxable_income = max(0.0, in_agi - exemption_amount)

        # Calculate state tax at flat rate
        tax_before_credits = self.calculate_brackets(in_taxable_income, filing_status)

        # Calculate county tax
        local_tax = self._calculate_county_tax(in_taxable_income)

        # State credits
        credits = {}

        # Indiana EITC (10% of federal)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        in_eitc = self.calculate_state_eitc(federal_eitc)
        if in_eitc > 0:
            credits["in_eitc"] = in_eitc

        # Unified tax credit (for very low income)
        unified_credit = self._calculate_unified_credit(
            in_agi, filing_status, dependent_exemptions
        )
        if unified_credit > 0:
            credits["unified_tax_credit"] = unified_credit

        total_credits = sum(credits.values())

        # Net state tax
        state_tax_only = max(0.0, tax_before_credits - total_credits)
        state_tax_liability = state_tax_only + local_tax

        # State withholding
        state_withholding = self.get_state_withholding(tax_return)

        # Refund or owed
        state_refund_or_owed = state_withholding - state_tax_liability

        return StateCalculationBreakdown(
            state_code=self.config.state_code,
            state_name=self.config.state_name,
            tax_year=self.config.tax_year,
            filing_status=filing_status,
            federal_agi=federal_agi,
            federal_taxable_income=federal_taxable_income,
            state_additions=additions,
            state_subtractions=subtractions,
            state_adjusted_income=in_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=in_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)),
            state_credits=credits,
            total_state_credits=float(money(total_credits)),
            local_tax=float(money(local_tax)),
            state_tax_liability=float(money(state_tax_liability)),
            state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_refund_or_owed)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Indiana income subtractions.

        Indiana allows:
        - Social Security benefits (fully exempt)
        - Railroad retirement
        - Military pay
        - Civil service annuity
        - Certain pension income
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Unemployment compensation (partially deductible in IN)
        unemployment = tax_return.income.unemployment_compensation
        if unemployment > 0:
            subtractions += min(unemployment, 2000)

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Indiana income additions."""
        additions = 0.0
        return additions

    def _calculate_additional_exemptions(
        self,
        tax_return: "TaxReturn"
    ) -> float:
        """
        Calculate additional exemptions for age 65+ and blind.

        $1,500 additional exemption per person for:
        - Age 65 or older
        - Blind
        """
        additional = 0.0

        # Simplified: check if retirement income suggests age 65+
        if tax_return.income.retirement_income > 0:
            # Assume at least one person is 65+
            additional += 1500

        return additional

    def _calculate_county_tax(self, in_taxable_income: float) -> float:
        """
        Calculate Indiana county income tax.

        All 92 counties have local income tax (0.5% - 3.0%).
        Using average rate of 1.5% as default.
        """
        return float(money(in_taxable_income * self._county_rate))

    def _calculate_unified_credit(
        self,
        in_agi: float,
        filing_status: str,
        num_dependents: int
    ) -> float:
        """
        Calculate Indiana Unified Tax Credit.

        Credit for low-income taxpayers to offset tax liability.
        """
        # Income threshold
        base_threshold = 5000
        per_dependent_add = 2500

        threshold = base_threshold + (num_dependents * per_dependent_add)
        if filing_status in ("married_joint", "qualifying_widow"):
            threshold += 2500

        if in_agi > threshold:
            return 0.0

        # Credit equals tax liability on income below threshold
        credit = in_agi * self.config.flat_rate
        return float(money(credit * 0.5))  # 50% of tax as credit

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for IN EITC calculation."""
        earned_income = (
            tax_return.income.get_total_wages() +
            tax_return.income.self_employment_income -
            tax_return.income.self_employment_expenses
        )
        agi = tax_return.adjusted_gross_income or 0.0
        num_children = len(tax_return.taxpayer.dependents)

        return tax_return.credits.calculate_eitc(
            earned_income,
            agi,
            filing_status,
            num_children
        )
