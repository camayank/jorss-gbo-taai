"""Nebraska state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_nebraska_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="NE",
        state_name="Nebraska",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            "single": [(0, 0.0246), (3700, 0.0351), (22170, 0.0501), (35730, 0.0584)],
            "married_joint": [(0, 0.0246), (7390, 0.0351), (44350, 0.0501), (71460, 0.0584)],
            "married_separate": [(0, 0.0246), (3700, 0.0351), (22170, 0.0501), (35730, 0.0584)],
            "head_of_household": [(0, 0.0246), (5920, 0.0351), (34170, 0.0501), (53600, 0.0584)],
            "qualifying_widow": [(0, 0.0246), (7390, 0.0351), (44350, 0.0501), (71460, 0.0584)],
        },
        starts_from="federal_agi",
        standard_deduction={"single": 8300, "married_joint": 16600, "married_separate": 8300,
                           "head_of_household": 12100, "qualifying_widow": 16600},
        personal_exemption_amount={"single": 159, "married_joint": 318, "married_separate": 159,
                                   "head_of_household": 159, "qualifying_widow": 159},
        dependent_exemption_amount=159,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,
        pension_exclusion_limit=None,
        military_pay_exempt=True,
        eitc_percentage=0.10,  # Nebraska EITC 10% of federal
        child_tax_credit_amount=0,
        has_local_tax=False,
    )


@register_state("NE", 2025)
class NebraskaCalculator(BaseStateCalculator):
    """Nebraska state tax calculator - 4 brackets (2.46% - 5.84%)."""

    def __init__(self):
        super().__init__(get_nebraska_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        ne_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(ne_agi)

        deduction_used = "standard" if tax_return.deductions.use_standard_deduction or std_deduction >= itemized else "itemized"
        deduction_amount = std_deduction if deduction_used == "standard" else itemized

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        exemption_credit = ((personal_exemptions + dependent_exemptions) * self.config.get_personal_exemption(filing_status))

        ne_taxable_income = max(0.0, ne_agi - deduction_amount)
        tax_before_credits = self.calculate_brackets(ne_taxable_income, filing_status)

        credits = {}
        if exemption_credit > 0:
            credits["exemption_credit"] = exemption_credit

        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        ne_eitc = self.calculate_state_eitc(federal_eitc)
        if ne_eitc > 0:
            credits["ne_eitc"] = ne_eitc

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions,
            state_adjusted_income=ne_agi, state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized, deduction_used=deduction_used,
            deduction_amount=deduction_amount, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=exemption_credit,
            state_taxable_income=ne_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2), state_credits=credits,
            total_state_credits=round(total_credits, 2), local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
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
