"""Iowa state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_iowa_config() -> StateTaxConfig:
    """Create Iowa tax configuration for 2025."""
    return StateTaxConfig(
        state_code="IA",
        state_name="Iowa",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.038,  # 3.8% flat rate (new for 2025, converted from progressive)
        brackets=None,
        starts_from="federal_agi",
        standard_deduction={
            "single": 2210,
            "married_joint": 5450,
            "married_separate": 2210,
            "head_of_household": 5450,
            "qualifying_widow": 5450,
        },
        personal_exemption_amount={
            "single": 40,  # Tax credit
            "married_joint": 80,
            "married_separate": 40,
            "head_of_household": 40,
            "qualifying_widow": 40,
        },
        dependent_exemption_amount=40,
        allows_federal_tax_deduction=False,  # Changed in 2023
        social_security_taxable=False,
        pension_exclusion_limit=6000,
        military_pay_exempt=True,
        eitc_percentage=0.15,  # Iowa EITC is 15% of federal
        child_tax_credit_amount=0,
        has_local_tax=False,
    )


@register_state("IA", 2025)
class IowaCalculator(BaseStateCalculator):
    """Iowa state tax calculator - flat 3.8% rate for 2025."""

    def __init__(self):
        super().__init__(get_iowa_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        ia_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(ia_agi)

        if tax_return.deductions.use_standard_deduction or std_deduction >= itemized:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        ia_taxable_income = max(0.0, ia_agi - deduction_amount)
        tax_before_credits = self.calculate_brackets(ia_taxable_income, filing_status)

        credits = {}
        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        total_exemptions = personal_exemptions + dependent_exemptions

        exemption_credit = total_exemptions * self.config.get_personal_exemption(filing_status)
        if exemption_credit > 0:
            credits["exemption_credit"] = exemption_credit

        # Iowa EITC (15% of federal)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        ia_eitc = self.calculate_state_eitc(federal_eitc)
        if ia_eitc > 0:
            credits["ia_eitc"] = ia_eitc

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions,
            state_adjusted_income=ia_agi, state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized, deduction_used=deduction_used,
            deduction_amount=deduction_amount, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=exemption_credit,
            state_taxable_income=ia_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)), state_credits=credits,
            total_state_credits=float(money(total_credits)), local_tax=0.0,
            state_tax_liability=float(money(state_tax_liability)),
            state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_refund_or_owed)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = 0.0
        subtractions += tax_return.income.taxable_social_security
        if tax_return.income.retirement_income > 0:
            subtractions += min(tax_return.income.retirement_income, 6000)
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0

    def _calculate_federal_eitc_estimate(self, tax_return: "TaxReturn", filing_status: str) -> float:
        earned_income = (tax_return.income.get_total_wages() +
                        tax_return.income.self_employment_income -
                        tax_return.income.self_employment_expenses)
        agi = tax_return.adjusted_gross_income or 0.0
        num_children = len(tax_return.taxpayer.dependents)
        return tax_return.credits.calculate_eitc(earned_income, agi, filing_status, num_children)
