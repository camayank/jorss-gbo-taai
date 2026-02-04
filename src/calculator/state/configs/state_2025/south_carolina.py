"""South Carolina state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_south_carolina_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="SC", state_name="South Carolina", tax_year=2025, is_flat_tax=False,
        brackets={
            "single": [(0, 0.0), (3460, 0.03), (6920, 0.04), (10380, 0.05), (13840, 0.06), (17310, 0.064)],
            "married_joint": [(0, 0.0), (3460, 0.03), (6920, 0.04), (10380, 0.05), (13840, 0.06), (17310, 0.064)],
            "married_separate": [(0, 0.0), (3460, 0.03), (6920, 0.04), (10380, 0.05), (13840, 0.06), (17310, 0.064)],
            "head_of_household": [(0, 0.0), (3460, 0.03), (6920, 0.04), (10380, 0.05), (13840, 0.06), (17310, 0.064)],
            "qualifying_widow": [(0, 0.0), (3460, 0.03), (6920, 0.04), (10380, 0.05), (13840, 0.06), (17310, 0.064)],
        },
        starts_from="federal_taxable_income",
        standard_deduction={"single": 15750, "married_joint": 31500, "married_separate": 15750,
                           "head_of_household": 23850, "qualifying_widow": 31500},
        personal_exemption_amount={"single": 0, "married_joint": 0, "married_separate": 0,
                                   "head_of_household": 0, "qualifying_widow": 0},
        dependent_exemption_amount=4720, allows_federal_tax_deduction=False, social_security_taxable=False,
        pension_exclusion_limit=10000, military_pay_exempt=True, eitc_percentage=0.0,
        child_tax_credit_amount=0, has_local_tax=False,
    )


@register_state("SC", 2025)
class SouthCarolinaCalculator(BaseStateCalculator):
    """South Carolina - 6 brackets (0% - 6.4%), uses federal taxable income."""

    def __init__(self):
        super().__init__(get_south_carolina_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)

        dependent_exemptions = len(tax_return.taxpayer.dependents)
        dependent_deduction = dependent_exemptions * self.config.dependent_exemption_amount

        sc_taxable_income = max(0.0, federal_taxable_income + additions - subtractions - dependent_deduction)
        tax_before_credits = self.calculate_brackets(sc_taxable_income, filing_status)

        credits = {}
        # SC Two-Wage Earner Credit
        if filing_status == "married_joint":
            wages = tax_return.income.get_total_wages()
            if wages > 0:
                credits["two_wage_credit"] = min(210, wages * 0.01)

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions, state_adjusted_income=sc_taxable_income,
            state_standard_deduction=0.0, state_itemized_deductions=0.0, deduction_used="federal",
            deduction_amount=0.0, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=dependent_deduction,
            state_taxable_income=sc_taxable_income, state_tax_before_credits=float(money(tax_before_credits)),
            state_credits=credits, total_state_credits=float(money(total_credits)), local_tax=0.0,
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
