"""Mississippi state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_mississippi_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="MS",
        state_name="Mississippi",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.044,  # 4.4% flat rate (reduced from 4.7% in 2024)
        brackets=None,
        starts_from="federal_agi",
        standard_deduction={"single": 2300, "married_joint": 4600, "married_separate": 2300,
                           "head_of_household": 3400, "qualifying_widow": 4600},
        personal_exemption_amount={"single": 6000, "married_joint": 12000, "married_separate": 6000,
                                   "head_of_household": 8000, "qualifying_widow": 12000},
        dependent_exemption_amount=1500,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,
        pension_exclusion_limit=None,  # MS exempts all retirement income
        military_pay_exempt=True,
        eitc_percentage=0.0,
        child_tax_credit_amount=0,
        has_local_tax=False,
    )


@register_state("MS", 2025)
class MississippiCalculator(BaseStateCalculator):
    """Mississippi state tax calculator - flat 4.4% rate."""

    def __init__(self):
        super().__init__(get_mississippi_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        ms_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(ms_agi)

        deduction_used = "standard" if tax_return.deductions.use_standard_deduction or std_deduction >= itemized else "itemized"
        deduction_amount = std_deduction if deduction_used == "standard" else itemized

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        exemption_amount = self.config.get_personal_exemption(filing_status) + (dependent_exemptions * self.config.dependent_exemption_amount)

        ms_taxable_income = max(0.0, ms_agi - deduction_amount - exemption_amount)
        tax_before_credits = self.calculate_brackets(ms_taxable_income, filing_status)

        credits = {}
        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions,
            state_adjusted_income=ms_agi, state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized, deduction_used=deduction_used,
            deduction_amount=deduction_amount, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=exemption_amount,
            state_taxable_income=ms_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2), state_credits=credits,
            total_state_credits=round(total_credits, 2), local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = tax_return.income.taxable_social_security
        subtractions += tax_return.income.retirement_income  # MS exempts all retirement
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0
