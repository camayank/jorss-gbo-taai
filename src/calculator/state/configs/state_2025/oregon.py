"""Oregon state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_oregon_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="OR", state_name="Oregon", tax_year=2025, is_flat_tax=False,
        brackets={
            "single": [(0, 0.0475), (4300, 0.0675), (10750, 0.0875), (125000, 0.099)],
            "married_joint": [(0, 0.0475), (8600, 0.0675), (21500, 0.0875), (250000, 0.099)],
            "married_separate": [(0, 0.0475), (4300, 0.0675), (10750, 0.0875), (125000, 0.099)],
            "head_of_household": [(0, 0.0475), (8600, 0.0675), (21500, 0.0875), (250000, 0.099)],
            "qualifying_widow": [(0, 0.0475), (8600, 0.0675), (21500, 0.0875), (250000, 0.099)],
        },
        starts_from="federal_taxable_income",
        standard_deduction={"single": 2745, "married_joint": 5495, "married_separate": 2745,
                           "head_of_household": 4440, "qualifying_widow": 5495},
        personal_exemption_amount={"single": 236, "married_joint": 472, "married_separate": 236,
                                   "head_of_household": 236, "qualifying_widow": 236},
        dependent_exemption_amount=236, allows_federal_tax_deduction=True,  # Oregon allows federal tax deduction
        social_security_taxable=False, pension_exclusion_limit=None, military_pay_exempt=True,
        eitc_percentage=0.12,  # Oregon EITC 12% of federal
        child_tax_credit_amount=0, has_local_tax=True,  # Some OR cities have income tax
    )


@register_state("OR", 2025)
class OregonCalculator(BaseStateCalculator):
    """Oregon - 4 brackets (4.75% - 9.9%), allows federal tax deduction."""

    def __init__(self):
        super().__init__(get_oregon_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)

        # Oregon allows federal tax deduction
        federal_tax = tax_return.tax_liability or 0.0
        federal_tax_deduction = min(federal_tax, 7500)  # Limited to $7,500
        subtractions += federal_tax_deduction

        or_agi = federal_taxable_income + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(or_agi)

        deduction_used = "standard" if tax_return.deductions.use_standard_deduction or std_deduction >= itemized else "itemized"
        deduction_amount = std_deduction if deduction_used == "standard" else itemized

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        exemption_credit = ((personal_exemptions + dependent_exemptions) * self.config.get_personal_exemption(filing_status))

        or_taxable_income = max(0.0, or_agi - deduction_amount)
        tax_before_credits = self.calculate_brackets(or_taxable_income, filing_status)

        credits = {}
        if exemption_credit > 0:
            credits["exemption_credit"] = exemption_credit

        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        or_eitc = self.calculate_state_eitc(federal_eitc)
        if or_eitc > 0:
            credits["or_eitc"] = or_eitc

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions, state_adjusted_income=or_agi,
            state_standard_deduction=std_deduction, state_itemized_deductions=itemized,
            deduction_used=deduction_used, deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions, dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_credit, state_taxable_income=or_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2), state_credits=credits,
            total_state_credits=round(total_credits, 2), local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2), state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_withholding - state_tax_liability, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        return tax_return.income.taxable_social_security

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0

    def _calculate_federal_eitc_estimate(self, tax_return: "TaxReturn", filing_status: str) -> float:
        earned_income = (tax_return.income.get_total_wages() + tax_return.income.self_employment_income -
                        tax_return.income.self_employment_expenses)
        return tax_return.credits.calculate_eitc(earned_income, tax_return.adjusted_gross_income or 0.0,
                                                 filing_status, len(tax_return.taxpayer.dependents))
