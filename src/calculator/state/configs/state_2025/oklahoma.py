"""Oklahoma state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_oklahoma_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="OK", state_name="Oklahoma", tax_year=2025, is_flat_tax=False,
        brackets={
            "single": [(0, 0.0025), (1000, 0.0075), (2500, 0.0175), (3750, 0.0275),
                      (4900, 0.0375), (7200, 0.0475)],
            "married_joint": [(0, 0.0025), (2000, 0.0075), (5000, 0.0175), (7500, 0.0275),
                             (9800, 0.0375), (12200, 0.0475)],
            "married_separate": [(0, 0.0025), (1000, 0.0075), (2500, 0.0175), (3750, 0.0275),
                                (4900, 0.0375), (7200, 0.0475)],
            "head_of_household": [(0, 0.0025), (2000, 0.0075), (5000, 0.0175), (7500, 0.0275),
                                 (9800, 0.0375), (12200, 0.0475)],
            "qualifying_widow": [(0, 0.0025), (2000, 0.0075), (5000, 0.0175), (7500, 0.0275),
                                (9800, 0.0375), (12200, 0.0475)],
        },
        starts_from="federal_agi",
        standard_deduction={"single": 6350, "married_joint": 12700, "married_separate": 6350,
                           "head_of_household": 9350, "qualifying_widow": 12700},
        personal_exemption_amount={"single": 1000, "married_joint": 2000, "married_separate": 1000,
                                   "head_of_household": 1000, "qualifying_widow": 1000},
        dependent_exemption_amount=1000, allows_federal_tax_deduction=False, social_security_taxable=False,
        pension_exclusion_limit=10000, military_pay_exempt=True, eitc_percentage=0.05,
        child_tax_credit_amount=0, has_local_tax=False,
    )


@register_state("OK", 2025)
class OklahomaCalculator(BaseStateCalculator):
    """Oklahoma - 6 brackets (0.25% - 4.75%)."""

    def __init__(self):
        super().__init__(get_oklahoma_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        ok_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(ok_agi)

        deduction_used = "standard" if tax_return.deductions.use_standard_deduction or std_deduction >= itemized else "itemized"
        deduction_amount = std_deduction if deduction_used == "standard" else itemized

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        exemption_amount = ((personal_exemptions * self.config.get_personal_exemption(filing_status)) +
                           (dependent_exemptions * self.config.dependent_exemption_amount))

        ok_taxable_income = max(0.0, ok_agi - deduction_amount - exemption_amount)
        tax_before_credits = self.calculate_brackets(ok_taxable_income, filing_status)

        credits = {}
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        ok_eitc = self.calculate_state_eitc(federal_eitc)
        if ok_eitc > 0:
            credits["ok_eitc"] = ok_eitc

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions, state_adjusted_income=ok_agi,
            state_standard_deduction=std_deduction, state_itemized_deductions=itemized,
            deduction_used=deduction_used, deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions, dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount, state_taxable_income=ok_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)), state_credits=credits,
            total_state_credits=float(money(total_credits)), local_tax=0.0,
            state_tax_liability=float(money(state_tax_liability)), state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_withholding - state_tax_liability)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = tax_return.income.taxable_social_security
        if tax_return.income.retirement_income > 0:
            subtractions += min(tax_return.income.retirement_income, 10000)
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0

    def _calculate_federal_eitc_estimate(self, tax_return: "TaxReturn", filing_status: str) -> float:
        earned_income = (tax_return.income.get_total_wages() + tax_return.income.self_employment_income -
                        tax_return.income.self_employment_expenses)
        return tax_return.credits.calculate_eitc(earned_income, tax_return.adjusted_gross_income or 0.0,
                                                 filing_status, len(tax_return.taxpayer.dependents))
