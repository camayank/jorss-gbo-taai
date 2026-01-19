"""Arizona state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_arizona_config() -> StateTaxConfig:
    """Create Arizona tax configuration for 2025."""
    return StateTaxConfig(
        state_code="AZ",
        state_name="Arizona",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.025,  # 2.5% flat rate (reduced from 2.55% in 2024)
        brackets=None,
        starts_from="federal_agi",
        standard_deduction={
            # Arizona standard deductions for 2025 (indexed)
            "single": 15750,
            "married_joint": 31500,
            "married_separate": 15750,
            "head_of_household": 23850,
            "qualifying_widow": 31500,
        },
        personal_exemption_amount={
            # Arizona has no personal exemptions
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        dependent_exemption_amount=100,  # Dependent tax credit (not exemption)
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # AZ exempts Social Security
        pension_exclusion_limit=2500,  # AZ up to $2,500 exclusion
        military_pay_exempt=True,  # AZ exempts military pay
        eitc_percentage=0.0,  # Arizona has no state EITC
        child_tax_credit_amount=100,  # AZ dependent tax credit
        has_local_tax=False,
    )


@register_state("AZ", 2025)
class ArizonaCalculator(BaseStateCalculator):
    """
    Arizona state tax calculator.

    Arizona has:
    - Flat 2.5% tax rate (one of lowest in US)
    - Standard deduction matches federal ($14,600 single, $29,200 MFJ)
    - No personal exemptions (removed)
    - Dependent tax credit ($100 per dependent)
    - Full exemption of Social Security
    - Up to $2,500 public retirement income exclusion
    - Military pay exemption
    - No state EITC
    - No local income tax
    """

    def __init__(self):
        super().__init__(get_arizona_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Arizona state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Arizona additions
        additions = self.calculate_state_additions(tax_return)

        # Arizona subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Arizona adjusted gross income
        az_agi = federal_agi + additions - subtractions

        # Standard deduction (same as federal or itemized)
        std_deduction = self.config.get_standard_deduction(filing_status)

        # Arizona itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(az_agi)

        # Choose higher deduction
        if tax_return.deductions.use_standard_deduction or std_deduction >= itemized:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        # Arizona taxable income
        az_taxable_income = max(0.0, az_agi - deduction_amount)

        # Calculate tax at flat rate
        tax_before_credits = self.calculate_brackets(az_taxable_income, filing_status)

        # State credits
        credits = {}

        # Dependent credit ($100 per dependent under 17)
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        if dependent_exemptions > 0:
            dependent_credit = dependent_exemptions * self.config.child_tax_credit_amount
            credits["dependent_credit"] = dependent_credit

        # Family tax credit (for low income families)
        family_credit = self._calculate_family_credit(
            tax_return, az_agi, filing_status, dependent_exemptions
        )
        if family_credit > 0:
            credits["family_tax_credit"] = family_credit

        # Property tax credit (seniors/disabled)
        property_credit = self._calculate_property_tax_credit(
            tax_return, az_agi, filing_status
        )
        if property_credit > 0:
            credits["property_tax_credit"] = property_credit

        total_credits = sum(credits.values())

        # Net state tax
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # State withholding
        state_withholding = self.get_state_withholding(tax_return)

        # Refund or owed
        state_refund_or_owed = state_withholding - state_tax_liability

        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        return StateCalculationBreakdown(
            state_code=self.config.state_code,
            state_name=self.config.state_name,
            tax_year=self.config.tax_year,
            filing_status=filing_status,
            federal_agi=federal_agi,
            federal_taxable_income=federal_taxable_income,
            state_additions=additions,
            state_subtractions=subtractions,
            state_adjusted_income=az_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=0.0,  # AZ has no exemptions
            state_taxable_income=az_taxable_income,
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
        Calculate Arizona income subtractions.

        Arizona exempts:
        - Social Security benefits
        - Up to $2,500 public retirement income
        - Military pay
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Public retirement income exclusion (up to $2,500)
        if tax_return.income.retirement_income > 0:
            retirement_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 2500
            )
            subtractions += retirement_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Arizona income additions."""
        additions = 0.0
        return additions

    def _calculate_family_credit(
        self,
        tax_return: "TaxReturn",
        az_agi: float,
        filing_status: str,
        num_dependents: int
    ) -> float:
        """
        Calculate Arizona Family Tax Credit.

        Credit for low-income families with dependents.
        """
        # Income limits for credit
        if filing_status in ("married_joint", "qualifying_widow"):
            income_limit = 40000
        else:
            income_limit = 20000

        if az_agi > income_limit:
            return 0.0

        if num_dependents == 0:
            return 0.0

        # Credit amount based on income and dependents
        if num_dependents == 1:
            return 40.0
        elif num_dependents == 2:
            return 100.0
        else:
            return 100.0 + (num_dependents - 2) * 25

    def _calculate_property_tax_credit(
        self,
        tax_return: "TaxReturn",
        az_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Arizona Property Tax Credit.

        Credit for seniors (65+) or disabled with limited income.
        """
        # Would need age/disability status
        # Simplified: assume qualifies if has retirement income and low AGI
        if tax_return.income.retirement_income > 0 and az_agi < 3751:
            if hasattr(tax_return.deductions, 'itemized'):
                property_tax = tax_return.deductions.itemized.real_estate_tax
                # Credit up to $502
                return min(502, property_tax)
        return 0.0
