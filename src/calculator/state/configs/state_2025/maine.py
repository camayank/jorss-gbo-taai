"""Maine state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_maine_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="ME",
        state_name="Maine",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            "single": [(0, 0.058), (26050, 0.0675), (61600, 0.0715)],
            "married_joint": [(0, 0.058), (52100, 0.0675), (123250, 0.0715)],
            "married_separate": [(0, 0.058), (26050, 0.0675), (61600, 0.0715)],
            "head_of_household": [(0, 0.058), (39100, 0.0675), (92400, 0.0715)],
            "qualifying_widow": [(0, 0.058), (52100, 0.0675), (123250, 0.0715)],
        },
        starts_from="federal_agi",
        standard_deduction={"single": 14600, "married_joint": 29200, "married_separate": 14600,
                           "head_of_household": 21900, "qualifying_widow": 29200},
        personal_exemption_amount={"single": 5000, "married_joint": 10000, "married_separate": 5000,
                                   "head_of_household": 5000, "qualifying_widow": 5000},
        dependent_exemption_amount=5000,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,
        pension_exclusion_limit=35000,  # Maine pension exclusion
        military_pay_exempt=True,
        eitc_percentage=0.25,  # Maine EITC 25% of federal
        child_tax_credit_amount=300,  # Maine Child Tax Credit
        has_local_tax=False,
    )


@register_state("ME", 2025)
class MaineCalculator(BaseStateCalculator):
    """Maine state tax calculator - 3 brackets (5.8%, 6.75%, 7.15%)."""

    def __init__(self):
        super().__init__(get_maine_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        me_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(me_agi)

        deduction_used = "standard" if tax_return.deductions.use_standard_deduction or std_deduction >= itemized else "itemized"
        deduction_amount = std_deduction if deduction_used == "standard" else itemized

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        exemption_amount = ((personal_exemptions * self.config.get_personal_exemption(filing_status)) +
                           (dependent_exemptions * self.config.dependent_exemption_amount))

        me_taxable_income = max(0.0, me_agi - deduction_amount - exemption_amount)
        tax_before_credits = self.calculate_brackets(me_taxable_income, filing_status)

        credits = {}
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        me_eitc = self.calculate_state_eitc(federal_eitc)
        if me_eitc > 0:
            credits["me_eitc"] = me_eitc

        if dependent_exemptions > 0:
            credits["me_child_credit"] = dependent_exemptions * self.config.child_tax_credit_amount

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions,
            state_adjusted_income=me_agi, state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized, deduction_used=deduction_used,
            deduction_amount=deduction_amount, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=exemption_amount,
            state_taxable_income=me_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2), state_credits=credits,
            total_state_credits=round(total_credits, 2), local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = tax_return.income.taxable_social_security
        if tax_return.income.retirement_income > 0:
            subtractions += min(tax_return.income.retirement_income, 35000)
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0

    def _calculate_federal_eitc_estimate(self, tax_return: "TaxReturn", filing_status: str) -> float:
        earned_income = (tax_return.income.get_total_wages() + tax_return.income.self_employment_income -
                        tax_return.income.self_employment_expenses)
        return tax_return.credits.calculate_eitc(earned_income, tax_return.adjusted_gross_income or 0.0,
                                                 filing_status, len(tax_return.taxpayer.dependents))
