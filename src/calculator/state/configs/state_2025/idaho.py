"""Idaho state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_idaho_config() -> StateTaxConfig:
    """Create Idaho tax configuration for 2025."""
    return StateTaxConfig(
        state_code="ID",
        state_name="Idaho",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.058,  # 5.8% flat rate (reduced from progressive in 2023)
        brackets=None,
        starts_from="federal_taxable_income",
        standard_deduction={
            "single": 15750,
            "married_joint": 31500,
            "married_separate": 15750,
            "head_of_household": 23850,
            "qualifying_widow": 31500,
        },
        personal_exemption_amount={
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        dependent_exemption_amount=0,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,
        pension_exclusion_limit=None,
        military_pay_exempt=True,
        eitc_percentage=0.0,
        child_tax_credit_amount=205,  # Idaho Child Tax Credit
        has_local_tax=False,
    )


@register_state("ID", 2025)
class IdahoCalculator(BaseStateCalculator):
    """Idaho state tax calculator - flat 5.8% rate."""

    def __init__(self):
        super().__init__(get_idaho_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)

        id_taxable_income = max(0.0, federal_taxable_income + additions - subtractions)

        tax_before_credits = self.calculate_brackets(id_taxable_income, filing_status)

        credits = {}
        # Idaho Child Tax Credit ($205 per child)
        num_children = len(tax_return.taxpayer.dependents)
        if num_children > 0:
            child_credit = num_children * self.config.child_tax_credit_amount
            credits["id_child_tax_credit"] = child_credit

        # Grocery credit ($120 per person)
        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        grocery_credit = (personal_exemptions + num_children) * 120
        credits["grocery_credit"] = grocery_credit

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions,
            state_adjusted_income=id_taxable_income, state_standard_deduction=0.0,
            state_itemized_deductions=0.0, deduction_used="federal", deduction_amount=0.0,
            personal_exemptions=personal_exemptions, dependent_exemptions=num_children,
            exemption_amount=0.0, state_taxable_income=id_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2), state_credits=credits,
            total_state_credits=round(total_credits, 2), local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = 0.0
        subtractions += tax_return.income.taxable_social_security
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0
