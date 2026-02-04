"""Alabama state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_alabama_config() -> StateTaxConfig:
    """Create Alabama tax configuration for 2025."""
    return StateTaxConfig(
        state_code="AL",
        state_name="Alabama",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Alabama 2025 brackets (3 brackets)
            "single": [
                (0, 0.02),       # 2% on first $500
                (500, 0.04),    # 4% on $500 - $3,000
                (3000, 0.05),   # 5% on over $3,000
            ],
            "married_joint": [
                (0, 0.02),
                (1000, 0.04),
                (6000, 0.05),
            ],
            "married_separate": [
                (0, 0.02),
                (500, 0.04),
                (3000, 0.05),
            ],
            "head_of_household": [
                (0, 0.02),
                (500, 0.04),
                (3000, 0.05),
            ],
            "qualifying_widow": [
                (0, 0.02),
                (1000, 0.04),
                (6000, 0.05),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # Alabama standard deductions for 2025
            "single": 2500,
            "married_joint": 7500,
            "married_separate": 3750,
            "head_of_household": 4700,
            "qualifying_widow": 7500,
        },
        personal_exemption_amount={
            # Alabama personal exemptions (income-based)
            "single": 1500,
            "married_joint": 3000,
            "married_separate": 1500,
            "head_of_household": 3000,
            "qualifying_widow": 3000,
        },
        dependent_exemption_amount=1000,  # Per dependent (income-based)
        allows_federal_tax_deduction=True,  # Alabama allows federal tax deduction
        social_security_taxable=False,  # AL exempts Social Security
        pension_exclusion_limit=None,  # No specific pension exclusion
        military_pay_exempt=True,  # AL exempts military retirement
        eitc_percentage=0.0,  # Alabama has no state EITC
        child_tax_credit_amount=0,
        has_local_tax=True,  # Some AL cities/counties have occupational tax
    )


@register_state("AL", 2025)
class AlabamaCalculator(BaseStateCalculator):
    """
    Alabama state tax calculator.

    Alabama has unique features:
    - 3 progressive tax brackets (2%, 4%, 5%)
    - Federal income tax deduction allowed (one of few states)
    - Standard deduction varies by filing status
    - Personal/dependent exemptions phase out at higher income
    - Full exemption of Social Security
    - Military retirement pay exemption
    - Some cities have occupational taxes
    - No state EITC
    """

    def __init__(self):
        super().__init__(get_alabama_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Alabama state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Alabama additions
        additions = self.calculate_state_additions(tax_return)

        # Alabama subtractions (including federal tax deduction)
        subtractions = self.calculate_state_subtractions(tax_return)

        # Federal income tax deduction (unique to AL)
        federal_tax_deduction = self._calculate_federal_tax_deduction(tax_return)
        subtractions += federal_tax_deduction

        # Alabama adjusted gross income
        al_agi = federal_agi + additions - subtractions

        # Standard deduction
        std_deduction = self.config.get_standard_deduction(filing_status)

        # Alabama itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(al_agi)

        # Choose higher deduction
        if tax_return.deductions.use_standard_deduction or std_deduction >= itemized:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        # Personal exemptions (phase out at higher income)
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)

        exemption_amount = self._calculate_exemptions(
            al_agi, filing_status, personal_exemptions, dependent_exemptions
        )

        # Alabama taxable income
        al_taxable_income = max(
            0.0,
            al_agi - deduction_amount - exemption_amount
        )

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(al_taxable_income, filing_status)

        # State credits (Alabama has limited credits)
        credits = {}

        total_credits = sum(credits.values())

        # Net state tax
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # Local tax (simplified - some cities have occupational tax)
        local_tax = 0.0

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
            state_adjusted_income=al_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=al_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)),
            state_credits=credits,
            total_state_credits=float(money(total_credits)),
            local_tax=float(money(local_tax)),
            state_tax_liability=float(money(state_tax_liability)),
            state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_refund_or_owed)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Alabama income subtractions.

        Alabama exempts:
        - Social Security benefits
        - Military retirement pay
        - Federal income tax paid (calculated separately)
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Alabama income additions."""
        additions = 0.0
        return additions

    def _calculate_federal_tax_deduction(self, tax_return: "TaxReturn") -> float:
        """
        Calculate federal income tax deduction.

        Alabama is one of few states that allows deducting federal income tax.
        """
        federal_tax = tax_return.tax_liability or 0.0
        return federal_tax

    def _calculate_exemptions(
        self,
        al_agi: float,
        filing_status: str,
        personal_exemptions: int,
        dependent_exemptions: int
    ) -> float:
        """
        Calculate Alabama exemptions with income-based phase-out.

        Exemption amounts decrease as income increases.
        """
        # Base exemption amounts
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_base = 3000
            income_threshold = 100000
        else:
            personal_base = 1500
            income_threshold = 50000

        dependent_base = 1000

        # Phase out exemptions at higher income
        if al_agi > income_threshold:
            phase_out_pct = min(1.0, (al_agi - income_threshold) / income_threshold)
            personal_base = personal_base * (1 - phase_out_pct)
            dependent_base = dependent_base * (1 - phase_out_pct)

        total_exemption = personal_base + (dependent_exemptions * dependent_base)
        return float(money(total_exemption))
