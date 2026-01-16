"""Hawaii state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_hawaii_config() -> StateTaxConfig:
    """Create Hawaii tax configuration for 2025."""
    return StateTaxConfig(
        state_code="HI",
        state_name="Hawaii",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Hawaii 2025 brackets (12 brackets - most in US)
            "single": [
                (0, 0.014),         # 1.4% on first $2,400
                (2400, 0.032),      # 3.2% on $2,400 - $4,800
                (4800, 0.055),      # 5.5% on $4,800 - $9,600
                (9600, 0.064),      # 6.4% on $9,600 - $14,400
                (14400, 0.068),     # 6.8% on $14,400 - $19,200
                (19200, 0.072),     # 7.2% on $19,200 - $24,000
                (24000, 0.076),     # 7.6% on $24,000 - $36,000
                (36000, 0.079),     # 7.9% on $36,000 - $48,000
                (48000, 0.0825),    # 8.25% on $48,000 - $150,000
                (150000, 0.09),     # 9% on $150,000 - $175,000
                (175000, 0.10),     # 10% on $175,000 - $200,000
                (200000, 0.11),     # 11% on over $200,000
            ],
            "married_joint": [
                (0, 0.014),
                (4800, 0.032),
                (9600, 0.055),
                (19200, 0.064),
                (28800, 0.068),
                (38400, 0.072),
                (48000, 0.076),
                (72000, 0.079),
                (96000, 0.0825),
                (300000, 0.09),
                (350000, 0.10),
                (400000, 0.11),
            ],
            "married_separate": [
                (0, 0.014),
                (2400, 0.032),
                (4800, 0.055),
                (9600, 0.064),
                (14400, 0.068),
                (19200, 0.072),
                (24000, 0.076),
                (36000, 0.079),
                (48000, 0.0825),
                (150000, 0.09),
                (175000, 0.10),
                (200000, 0.11),
            ],
            "head_of_household": [
                (0, 0.014),
                (3600, 0.032),
                (7200, 0.055),
                (14400, 0.064),
                (21600, 0.068),
                (28800, 0.072),
                (36000, 0.076),
                (54000, 0.079),
                (72000, 0.0825),
                (225000, 0.09),
                (262500, 0.10),
                (300000, 0.11),
            ],
            "qualifying_widow": [
                (0, 0.014),
                (4800, 0.032),
                (9600, 0.055),
                (19200, 0.064),
                (28800, 0.068),
                (38400, 0.072),
                (48000, 0.076),
                (72000, 0.079),
                (96000, 0.0825),
                (300000, 0.09),
                (350000, 0.10),
                (400000, 0.11),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # Hawaii standard deductions for 2025
            "single": 2200,
            "married_joint": 4400,
            "married_separate": 2200,
            "head_of_household": 3212,
            "qualifying_widow": 4400,
        },
        personal_exemption_amount={
            # Hawaii personal exemption
            "single": 1144,
            "married_joint": 2288,
            "married_separate": 1144,
            "head_of_household": 1144,
            "qualifying_widow": 1144,
        },
        dependent_exemption_amount=1144,  # Per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # HI exempts Social Security
        pension_exclusion_limit=None,  # No general exclusion
        military_pay_exempt=True,
        eitc_percentage=0.40,  # Hawaii EITC is 40% of federal
        child_tax_credit_amount=0,
        has_local_tax=False,
    )


@register_state("HI", 2025)
class HawaiiCalculator(BaseStateCalculator):
    """
    Hawaii state tax calculator.

    Hawaii has:
    - 12 progressive tax brackets (most in US, 1.4% - 11%)
    - Standard deduction: $2,200 single, $4,400 MFJ
    - Personal exemption: $1,144 per person
    - Dependent exemption: $1,144 per dependent
    - Full exemption of Social Security
    - Hawaii EITC (40% of federal)
    - Food/excise tax credit
    - High cost of living offset credits
    """

    def __init__(self):
        super().__init__(get_hawaii_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Hawaii state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)

        hi_agi = federal_agi + additions - subtractions

        std_deduction = self.config.get_standard_deduction(filing_status)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(hi_agi)

        if tax_return.deductions.use_standard_deduction or std_deduction >= itemized:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)
        total_exemptions = personal_exemptions + dependent_exemptions

        exemption_per_person = self.config.get_personal_exemption(filing_status)
        exemption_amount = total_exemptions * exemption_per_person

        hi_taxable_income = max(0.0, hi_agi - deduction_amount - exemption_amount)

        tax_before_credits = self.calculate_brackets(hi_taxable_income, filing_status)

        credits = {}

        # Hawaii EITC (40% of federal)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        hi_eitc = self.calculate_state_eitc(federal_eitc)
        if hi_eitc > 0:
            credits["hi_eitc"] = hi_eitc

        # Food/Excise Tax Credit
        food_credit = self._calculate_food_excise_credit(hi_agi, total_exemptions)
        if food_credit > 0:
            credits["food_excise_credit"] = food_credit

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)
        state_refund_or_owed = state_withholding - state_tax_liability

        return StateCalculationBreakdown(
            state_code=self.config.state_code,
            state_name=self.config.state_name,
            tax_year=self.config.tax_year,
            filing_status=filing_status,
            federal_agi=federal_agi,
            federal_taxable_income=federal_taxable_income,
            state_additions=additions,
            state_subtractions=subtractions,
            state_adjusted_income=hi_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=hi_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2),
            state_credits=credits,
            total_state_credits=round(total_credits, 2),
            local_tax=0.0,
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

    def _calculate_food_excise_credit(self, hi_agi: float, num_exemptions: int) -> float:
        """Calculate Hawaii Food/Excise Tax Credit."""
        if hi_agi > 50000:
            return 0.0
        # $110 per exemption for low income
        return num_exemptions * 110

    def _calculate_federal_eitc_estimate(self, tax_return: "TaxReturn", filing_status: str) -> float:
        earned_income = (
            tax_return.income.get_total_wages() +
            tax_return.income.self_employment_income -
            tax_return.income.self_employment_expenses
        )
        agi = tax_return.adjusted_gross_income or 0.0
        num_children = len(tax_return.taxpayer.dependents)
        return tax_return.credits.calculate_eitc(earned_income, agi, filing_status, num_children)
