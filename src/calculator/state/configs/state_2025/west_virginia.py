"""West Virginia state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_west_virginia_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="WV", state_name="West Virginia", tax_year=2025, is_flat_tax=False,
        brackets={
            "single": [(0, 0.0236), (10000, 0.0315), (25000, 0.0354), (40000, 0.0472), (60000, 0.0512)],
            "married_joint": [(0, 0.0236), (10000, 0.0315), (25000, 0.0354), (40000, 0.0472), (60000, 0.0512)],
            "married_separate": [(0, 0.0236), (5000, 0.0315), (12500, 0.0354), (20000, 0.0472), (30000, 0.0512)],
            "head_of_household": [(0, 0.0236), (10000, 0.0315), (25000, 0.0354), (40000, 0.0472), (60000, 0.0512)],
            "qualifying_widow": [(0, 0.0236), (10000, 0.0315), (25000, 0.0354), (40000, 0.0472), (60000, 0.0512)],
        },
        starts_from="federal_agi",
        standard_deduction={"single": 0, "married_joint": 0, "married_separate": 0,
                           "head_of_household": 0, "qualifying_widow": 0},
        personal_exemption_amount={"single": 2000, "married_joint": 4000, "married_separate": 2000,
                                   "head_of_household": 2000, "qualifying_widow": 2000},
        dependent_exemption_amount=2000, allows_federal_tax_deduction=False, social_security_taxable=False,
        pension_exclusion_limit=8000, military_pay_exempt=True, eitc_percentage=0.0,
        child_tax_credit_amount=0, has_local_tax=True,  # Some WV cities have B&O tax
    )


@register_state("WV", 2025)
class WestVirginiaCalculator(BaseStateCalculator):
    """West Virginia - 5 brackets (2.36% - 5.12%)."""

    def __init__(self):
        super().__init__(get_west_virginia_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        wv_agi = federal_agi + additions - subtractions

        # WV has no standard deduction - uses exemptions
        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        exemption_amount = ((personal_exemptions * self.config.get_personal_exemption(filing_status)) +
                           (dependent_exemptions * self.config.dependent_exemption_amount))

        wv_taxable_income = max(0.0, wv_agi - exemption_amount)
        tax_before_credits = self.calculate_brackets(wv_taxable_income, filing_status)

        credits = {}
        # WV Low-Income Family Tax Credit
        if wv_agi < 10000:
            credits["low_income_credit"] = min(tax_before_credits * 0.20, 500)

        # WV Senior Citizen Tax Credit
        if tax_return.income.retirement_income > 0:
            credits["senior_credit"] = min(tax_before_credits * 0.05, 200)

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions, state_adjusted_income=wv_agi,
            state_standard_deduction=0.0, state_itemized_deductions=0.0, deduction_used="none",
            deduction_amount=0.0, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=exemption_amount,
            state_taxable_income=wv_taxable_income, state_tax_before_credits=round(tax_before_credits, 2),
            state_credits=credits, total_state_credits=round(total_credits, 2), local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2), state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_withholding - state_tax_liability, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = tax_return.income.taxable_social_security
        if tax_return.income.retirement_income > 0:
            subtractions += min(tax_return.income.retirement_income, 8000)
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0
