"""Missouri state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_missouri_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="MO",
        state_name="Missouri",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            "single": [(0, 0.0), (1207, 0.02), (2414, 0.025), (3621, 0.03), (4828, 0.035),
                      (6035, 0.04), (7242, 0.045), (8449, 0.048)],
            "married_joint": [(0, 0.0), (1207, 0.02), (2414, 0.025), (3621, 0.03), (4828, 0.035),
                             (6035, 0.04), (7242, 0.045), (8449, 0.048)],
            "married_separate": [(0, 0.0), (1207, 0.02), (2414, 0.025), (3621, 0.03), (4828, 0.035),
                                (6035, 0.04), (7242, 0.045), (8449, 0.048)],
            "head_of_household": [(0, 0.0), (1207, 0.02), (2414, 0.025), (3621, 0.03), (4828, 0.035),
                                 (6035, 0.04), (7242, 0.045), (8449, 0.048)],
            "qualifying_widow": [(0, 0.0), (1207, 0.02), (2414, 0.025), (3621, 0.03), (4828, 0.035),
                                (6035, 0.04), (7242, 0.045), (8449, 0.048)],
        },
        starts_from="federal_agi",
        standard_deduction={"single": 15750, "married_joint": 31500, "married_separate": 15750,
                           "head_of_household": 23850, "qualifying_widow": 31500},
        personal_exemption_amount={"single": 0, "married_joint": 0, "married_separate": 0,
                                   "head_of_household": 0, "qualifying_widow": 0},
        dependent_exemption_amount=0,
        allows_federal_tax_deduction=True,  # Missouri allows federal tax deduction
        social_security_taxable=False,
        pension_exclusion_limit=6000,
        military_pay_exempt=True,
        eitc_percentage=0.0,
        child_tax_credit_amount=0,
        has_local_tax=True,  # Kansas City, St. Louis have earnings tax
    )


@register_state("MO", 2025)
class MissouriCalculator(BaseStateCalculator):
    """Missouri state tax calculator - 8 brackets (0% - 4.8%)."""

    def __init__(self):
        super().__init__(get_missouri_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)

        # Missouri allows federal tax deduction
        federal_tax_deduction = tax_return.tax_liability or 0.0
        subtractions += federal_tax_deduction

        mo_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(mo_agi)

        deduction_used = "standard" if tax_return.deductions.use_standard_deduction or std_deduction >= itemized else "itemized"
        deduction_amount = std_deduction if deduction_used == "standard" else itemized

        mo_taxable_income = max(0.0, mo_agi - deduction_amount)
        tax_before_credits = self.calculate_brackets(mo_taxable_income, filing_status)

        credits = {}
        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # Local tax (KC/STL 1% earnings tax)
        local_tax = 0.0

        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions,
            state_adjusted_income=mo_agi, state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized, deduction_used=deduction_used,
            deduction_amount=deduction_amount, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=0.0,
            state_taxable_income=mo_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)), state_credits=credits,
            total_state_credits=float(money(total_credits)), local_tax=local_tax,
            state_tax_liability=float(money(state_tax_liability)),
            state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_refund_or_owed)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = tax_return.income.taxable_social_security
        if tax_return.income.retirement_income > 0:
            subtractions += min(tax_return.income.retirement_income, 6000)
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0
