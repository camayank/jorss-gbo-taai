"""North Dakota state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_north_dakota_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="ND", state_name="North Dakota", tax_year=2025, is_flat_tax=False,
        brackets={
            "single": [(0, 0.0), (44725, 0.0195), (225975, 0.025)],  # 0% bracket up to std deduction
            "married_joint": [(0, 0.0), (74750, 0.0195), (275100, 0.025)],
            "married_separate": [(0, 0.0), (37375, 0.0195), (137550, 0.025)],
            "head_of_household": [(0, 0.0), (59850, 0.0195), (243700, 0.025)],
            "qualifying_widow": [(0, 0.0), (74750, 0.0195), (275100, 0.025)],
        },
        starts_from="federal_taxable_income",
        standard_deduction={"single": 0, "married_joint": 0, "married_separate": 0,
                           "head_of_household": 0, "qualifying_widow": 0},
        personal_exemption_amount={"single": 0, "married_joint": 0, "married_separate": 0,
                                   "head_of_household": 0, "qualifying_widow": 0},
        dependent_exemption_amount=0, allows_federal_tax_deduction=False, social_security_taxable=False,
        pension_exclusion_limit=None, military_pay_exempt=True, eitc_percentage=0.0,
        child_tax_credit_amount=0, has_local_tax=False,
    )


@register_state("ND", 2025)
class NorthDakotaCalculator(BaseStateCalculator):
    """North Dakota - 3 brackets (0%, 1.95%, 2.5%), uses federal taxable income."""

    def __init__(self):
        super().__init__(get_north_dakota_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        subtractions = self.calculate_state_subtractions(tax_return)
        nd_taxable_income = max(0.0, federal_taxable_income - subtractions)
        tax_before_credits = self.calculate_brackets(nd_taxable_income, filing_status)

        credits = {}
        state_tax_liability = max(0.0, tax_before_credits - sum(credits.values()))
        state_withholding = self.get_state_withholding(tax_return)

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=0.0, state_subtractions=subtractions, state_adjusted_income=nd_taxable_income,
            state_standard_deduction=0.0, state_itemized_deductions=0.0, deduction_used="federal",
            deduction_amount=0.0, personal_exemptions=personal_exemptions,
            dependent_exemptions=len(tax_return.taxpayer.dependents), exemption_amount=0.0,
            state_taxable_income=nd_taxable_income, state_tax_before_credits=float(money(tax_before_credits)),
            state_credits=credits, total_state_credits=0.0, local_tax=0.0,
            state_tax_liability=float(money(state_tax_liability)), state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_withholding - state_tax_liability)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        return tax_return.income.taxable_social_security

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0
