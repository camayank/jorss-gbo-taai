"""New Mexico state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_new_mexico_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="NM",
        state_name="New Mexico",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            "single": [(0, 0.017), (5500, 0.032), (11000, 0.047), (16000, 0.049), (210000, 0.059)],
            "married_joint": [(0, 0.017), (8000, 0.032), (16000, 0.047), (24000, 0.049), (315000, 0.059)],
            "married_separate": [(0, 0.017), (4000, 0.032), (8000, 0.047), (12000, 0.049), (157500, 0.059)],
            "head_of_household": [(0, 0.017), (8000, 0.032), (16000, 0.047), (24000, 0.049), (315000, 0.059)],
            "qualifying_widow": [(0, 0.017), (8000, 0.032), (16000, 0.047), (24000, 0.049), (315000, 0.059)],
        },
        starts_from="federal_agi",
        standard_deduction={"single": 15750, "married_joint": 31500, "married_separate": 15750,
                           "head_of_household": 23850, "qualifying_widow": 31500},
        personal_exemption_amount={"single": 4150, "married_joint": 8300, "married_separate": 4150,
                                   "head_of_household": 4150, "qualifying_widow": 4150},
        dependent_exemption_amount=4150,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,
        pension_exclusion_limit=8000,
        military_pay_exempt=True,
        eitc_percentage=0.25,  # New Mexico EITC 25% of federal
        child_tax_credit_amount=600,  # NM Child Tax Credit
        has_local_tax=False,
    )


@register_state("NM", 2025)
class NewMexicoCalculator(BaseStateCalculator):
    """New Mexico state tax calculator - 5 brackets (1.7% - 5.9%)."""

    def __init__(self):
        super().__init__(get_new_mexico_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        nm_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(nm_agi)

        deduction_used = "standard" if tax_return.deductions.use_standard_deduction or std_deduction >= itemized else "itemized"
        deduction_amount = std_deduction if deduction_used == "standard" else itemized

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        exemption_amount = ((personal_exemptions * self.config.get_personal_exemption(filing_status)) +
                           (dependent_exemptions * self.config.dependent_exemption_amount))

        nm_taxable_income = max(0.0, nm_agi - deduction_amount - exemption_amount)
        tax_before_credits = self.calculate_brackets(nm_taxable_income, filing_status)

        credits = {}
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        nm_eitc = self.calculate_state_eitc(federal_eitc)
        if nm_eitc > 0:
            credits["nm_eitc"] = nm_eitc

        if dependent_exemptions > 0 and nm_agi < 30000:
            credits["nm_child_credit"] = dependent_exemptions * self.config.child_tax_credit_amount

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions,
            state_adjusted_income=nm_agi, state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized, deduction_used=deduction_used,
            deduction_amount=deduction_amount, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=exemption_amount,
            state_taxable_income=nm_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2), state_credits=credits,
            total_state_credits=round(total_credits, 2), local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = tax_return.income.taxable_social_security
        if tax_return.income.retirement_income > 0:
            subtractions += min(tax_return.income.retirement_income, 8000)
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0

    def _calculate_federal_eitc_estimate(self, tax_return: "TaxReturn", filing_status: str) -> float:
        earned_income = (tax_return.income.get_total_wages() + tax_return.income.self_employment_income -
                        tax_return.income.self_employment_expenses)
        return tax_return.credits.calculate_eitc(earned_income, tax_return.adjusted_gross_income or 0.0,
                                                 filing_status, len(tax_return.taxpayer.dependents))
