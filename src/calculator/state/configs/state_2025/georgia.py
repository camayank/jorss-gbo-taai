"""Georgia state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_georgia_config() -> StateTaxConfig:
    """Create Georgia tax configuration for 2025."""
    return StateTaxConfig(
        state_code="GA",
        state_name="Georgia",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.0539,  # 5.39% flat rate (moved to flat in 2024)
        brackets=None,
        starts_from="federal_agi",
        standard_deduction={
            # Georgia standard deductions for 2025
            "single": 12000,
            "married_joint": 24000,
            "married_separate": 12000,
            "head_of_household": 18000,
            "qualifying_widow": 24000,
        },
        personal_exemption_amount={
            # Georgia personal exemptions 2025
            "single": 2700,
            "married_joint": 5400,  # $2,700 each
            "married_separate": 2700,
            "head_of_household": 2700,
            "qualifying_widow": 2700,
        },
        dependent_exemption_amount=3000,  # Per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # GA exempts Social Security
        pension_exclusion_limit=65000,  # GA retirement exclusion (65+)
        military_pay_exempt=True,  # GA exempts military retirement
        eitc_percentage=0.0,  # Georgia has no EITC
        child_tax_credit_amount=0,
        has_local_tax=False,
    )


@register_state("GA", 2025)
class GeorgiaCalculator(BaseStateCalculator):
    """
    Georgia state tax calculator.

    Georgia transitioned to a flat tax starting 2024:
    - Flat 5.39% tax rate (2025)
    - Standard deduction: $12,000 single, $24,000 MFJ
    - Personal exemption: $2,700 per taxpayer
    - Dependent exemption: $3,000 per dependent
    - Full exemption of Social Security
    - Retirement income exclusion ($65,000 for age 62+, $35,000 for 59.5-62)
    - No state EITC
    """

    def __init__(self):
        super().__init__(get_georgia_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Georgia state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Georgia additions
        additions = self.calculate_state_additions(tax_return)

        # Georgia subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Georgia adjusted gross income
        ga_agi = federal_agi + additions - subtractions

        # Standard deduction
        std_deduction = self.config.get_standard_deduction(filing_status)

        # Georgia itemized deductions (mostly follows federal)
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(ga_agi)

        # Choose higher deduction
        if tax_return.deductions.use_standard_deduction or std_deduction >= itemized:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        # Personal exemptions
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)

        personal_exemption_amt = self.config.get_personal_exemption(filing_status)
        dependent_exemption_amt = (
            dependent_exemptions * self.config.dependent_exemption_amount
        )
        exemption_amount = personal_exemption_amt + dependent_exemption_amt

        # Georgia taxable income
        ga_taxable_income = max(
            0.0,
            ga_agi - deduction_amount - exemption_amount
        )

        # Calculate tax at flat rate
        tax_before_credits = self.calculate_brackets(ga_taxable_income, filing_status)

        # State credits
        credits = {}

        # Low Income Credit (for very low income)
        low_income_credit = self._calculate_low_income_credit(
            tax_return, ga_taxable_income, filing_status
        )
        if low_income_credit > 0:
            credits["low_income_credit"] = low_income_credit

        total_credits = sum(credits.values())

        # Net state tax
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # State withholding
        state_withholding = self.get_state_withholding(tax_return)

        # Refund or owed
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
            state_adjusted_income=ga_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=ga_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2),
            state_credits=credits,
            total_state_credits=round(total_credits, 2),
            local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Georgia income subtractions.

        Georgia exempts:
        - Social Security benefits
        - Retirement income (up to $65,000 for 65+, $35,000 for 59.5-62)
        - Military retirement pay
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Retirement income exclusion
        # Simplified: assume taxpayer is 65+ and qualifies for max exclusion
        if tax_return.income.retirement_income > 0:
            retirement_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 65000
            )
            subtractions += retirement_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Georgia income additions."""
        additions = 0.0
        return additions

    def _calculate_low_income_credit(
        self,
        tax_return: "TaxReturn",
        ga_taxable_income: float,
        filing_status: str
    ) -> float:
        """
        Calculate Georgia Low Income Credit.

        Available for very low income taxpayers.
        """
        # Income threshold for credit
        threshold = 10000 if filing_status == "single" else 20000

        if ga_taxable_income <= 0 or ga_taxable_income > threshold:
            return 0.0

        # Credit equals the tax liability for very low income
        tax_liability = ga_taxable_income * self.config.flat_rate
        credit_rate = 1.0 - (ga_taxable_income / threshold)
        return round(tax_liability * credit_rate, 2)
