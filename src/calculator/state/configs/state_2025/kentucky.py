"""Kentucky state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_kentucky_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="KY",
        state_name="Kentucky",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.04,  # 4% flat rate (reduced from 4.5% in 2024)
        brackets=None,
        starts_from="federal_agi",
        standard_deduction={"single": 3160, "married_joint": 6320, "married_separate": 3160,
                           "head_of_household": 3160, "qualifying_widow": 6320},
        personal_exemption_amount={"single": 0, "married_joint": 0, "married_separate": 0,
                                   "head_of_household": 0, "qualifying_widow": 0},
        dependent_exemption_amount=0,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,
        pension_exclusion_limit=31110,  # Kentucky pension exclusion
        military_pay_exempt=True,
        eitc_percentage=0.0,
        child_tax_credit_amount=0,
        has_local_tax=True,  # Kentucky has local occupational taxes
    )


@register_state("KY", 2025)
class KentuckyCalculator(BaseStateCalculator):
    """Kentucky state tax calculator - flat 4% rate."""

    def __init__(self):
        super().__init__(get_kentucky_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        ky_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(ky_agi)

        deduction_used = "standard" if tax_return.deductions.use_standard_deduction or std_deduction >= itemized else "itemized"
        deduction_amount = std_deduction if deduction_used == "standard" else itemized

        ky_taxable_income = max(0.0, ky_agi - deduction_amount)
        tax_before_credits = self.calculate_brackets(ky_taxable_income, filing_status)

        credits = {}
        # Family size tax credit (for low income)
        family_credit = self._calculate_family_credit(ky_agi, filing_status, len(tax_return.taxpayer.dependents))
        if family_credit > 0:
            credits["family_size_credit"] = family_credit

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # Local occupational tax (simplified - average 2%)
        local_tax = round(tax_return.income.get_total_wages() * 0.02, 2)

        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions,
            state_adjusted_income=ky_agi, state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized, deduction_used=deduction_used,
            deduction_amount=deduction_amount, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=0.0,
            state_taxable_income=ky_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2), state_credits=credits,
            total_state_credits=round(total_credits, 2), local_tax=local_tax,
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        subtractions = tax_return.income.taxable_social_security
        if tax_return.income.retirement_income > 0:
            subtractions += min(tax_return.income.retirement_income, self.config.pension_exclusion_limit or 31110)
        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0

    def _calculate_family_credit(self, ky_agi: float, filing_status: str, num_dependents: int) -> float:
        threshold = 14870 + (num_dependents * 4070)
        if filing_status in ("married_joint", "qualifying_widow"):
            threshold += 4070
        if ky_agi > threshold:
            return 0.0
        return min(tax_return.income.get_total_wages() * 0.04 if hasattr(self, 'tax_return') else 0, 200)
