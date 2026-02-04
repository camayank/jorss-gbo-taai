"""Montana state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_montana_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="MT",
        state_name="Montana",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            "single": [(0, 0.047), (20500, 0.059)],  # 2 brackets for 2025
            "married_joint": [(0, 0.047), (41000, 0.059)],
            "married_separate": [(0, 0.047), (20500, 0.059)],
            "head_of_household": [(0, 0.047), (30750, 0.059)],
            "qualifying_widow": [(0, 0.047), (41000, 0.059)],
        },
        starts_from="federal_agi",
        standard_deduction={"single": 15750, "married_joint": 31500, "married_separate": 15750,
                           "head_of_household": 23850, "qualifying_widow": 31500},
        personal_exemption_amount={"single": 3120, "married_joint": 6240, "married_separate": 3120,
                                   "head_of_household": 3120, "qualifying_widow": 3120},
        dependent_exemption_amount=3120,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,
        pension_exclusion_limit=5500,
        military_pay_exempt=True,
        eitc_percentage=0.03,  # Montana EITC 3% of federal
        child_tax_credit_amount=0,
        has_local_tax=False,
    )


@register_state("MT", 2025)
class MontanaCalculator(BaseStateCalculator):
    """Montana state tax calculator - 2 brackets (4.7%, 5.9%)."""

    def __init__(self):
        super().__init__(get_montana_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        mt_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(mt_agi)

        deduction_used = "standard" if tax_return.deductions.use_standard_deduction or std_deduction >= itemized else "itemized"
        deduction_amount = std_deduction if deduction_used == "standard" else itemized

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        exemption_amount = ((personal_exemptions * self.config.get_personal_exemption(filing_status)) +
                           (dependent_exemptions * self.config.dependent_exemption_amount))

        mt_taxable_income = max(0.0, mt_agi - deduction_amount - exemption_amount)
        tax_before_credits = self.calculate_brackets(mt_taxable_income, filing_status)

        credits = {}
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        mt_eitc = self.calculate_state_eitc(federal_eitc)
        if mt_eitc > 0:
            credits["mt_eitc"] = mt_eitc

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions,
            state_adjusted_income=mt_agi, state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized, deduction_used=deduction_used,
            deduction_amount=deduction_amount, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=exemption_amount,
            state_taxable_income=mt_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)), state_credits=credits,
            total_state_credits=float(money(total_credits)), local_tax=0.0,
            state_tax_liability=float(money(state_tax_liability)),
            state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_refund_or_owed)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = tax_return.income.taxable_social_security
        if tax_return.income.retirement_income > 0:
            subtractions += min(tax_return.income.retirement_income, 5500)
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0

    def _calculate_federal_eitc_estimate(self, tax_return: "TaxReturn", filing_status: str) -> float:
        earned_income = (tax_return.income.get_total_wages() + tax_return.income.self_employment_income -
                        tax_return.income.self_employment_expenses)
        return tax_return.credits.calculate_eitc(earned_income, tax_return.adjusted_gross_income or 0.0,
                                                 filing_status, len(tax_return.taxpayer.dependents))
