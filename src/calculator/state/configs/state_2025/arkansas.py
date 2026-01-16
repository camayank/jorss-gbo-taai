"""Arkansas state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_arkansas_config() -> StateTaxConfig:
    """Create Arkansas tax configuration for 2025."""
    return StateTaxConfig(
        state_code="AR",
        state_name="Arkansas",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Arkansas 2025 brackets (3 brackets after reform)
            "single": [
                (0, 0.02),          # 2% on first $4,400
                (4400, 0.04),       # 4% on $4,400 - $8,800
                (8800, 0.044),      # 4.4% on over $8,800 (reduced from 4.7% in 2024)
            ],
            "married_joint": [
                (0, 0.02),
                (4400, 0.04),
                (8800, 0.044),
            ],
            "married_separate": [
                (0, 0.02),
                (4400, 0.04),
                (8800, 0.044),
            ],
            "head_of_household": [
                (0, 0.02),
                (4400, 0.04),
                (8800, 0.044),
            ],
            "qualifying_widow": [
                (0, 0.02),
                (4400, 0.04),
                (8800, 0.044),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # Arkansas standard deductions for 2025
            "single": 2340,
            "married_joint": 4680,
            "married_separate": 2340,
            "head_of_household": 2340,
            "qualifying_widow": 4680,
        },
        personal_exemption_amount={
            # Arkansas personal exemptions (tax credit)
            "single": 29,  # $29 tax credit per exemption
            "married_joint": 29,
            "married_separate": 29,
            "head_of_household": 29,
            "qualifying_widow": 29,
        },
        dependent_exemption_amount=29,  # $29 tax credit per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # AR exempts Social Security
        pension_exclusion_limit=6000,  # AR pension exclusion
        military_pay_exempt=True,  # AR exempts military retirement
        eitc_percentage=0.0,  # Arkansas has no state EITC
        child_tax_credit_amount=0,
        has_local_tax=False,
    )


@register_state("AR", 2025)
class ArkansasCalculator(BaseStateCalculator):
    """
    Arkansas state tax calculator.

    Arkansas has:
    - 3 progressive tax brackets (2%, 4%, 4.4% for 2025)
    - Standard deduction: $2,340 single, $4,680 MFJ
    - Personal/dependent exemption as tax credit ($29 each)
    - Full exemption of Social Security
    - Retirement income exclusion ($6,000)
    - Military retirement pay exemption
    - Low income tax credit
    - No local income tax
    """

    def __init__(self):
        super().__init__(get_arkansas_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Arkansas state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Arkansas additions
        additions = self.calculate_state_additions(tax_return)

        # Arkansas subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Arkansas adjusted gross income
        ar_agi = federal_agi + additions - subtractions

        # Standard deduction
        std_deduction = self.config.get_standard_deduction(filing_status)

        # Arkansas itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(ar_agi)

        # Choose higher deduction
        if tax_return.deductions.use_standard_deduction or std_deduction >= itemized:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        # Arkansas taxable income
        ar_taxable_income = max(0.0, ar_agi - deduction_amount)

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(ar_taxable_income, filing_status)

        # State credits
        credits = {}

        # Personal/dependent exemption credits
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)
        total_exemptions = personal_exemptions + dependent_exemptions

        exemption_credit = total_exemptions * self.config.get_personal_exemption(filing_status)
        if exemption_credit > 0:
            credits["exemption_credit"] = exemption_credit

        # Low income tax credit
        low_income_credit = self._calculate_low_income_credit(
            ar_agi, filing_status, dependent_exemptions
        )
        if low_income_credit > 0:
            credits["low_income_credit"] = low_income_credit

        total_credits = sum(credits.values())

        exemption_amount = exemption_credit

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
            state_adjusted_income=ar_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=ar_taxable_income,
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
        Calculate Arkansas income subtractions.

        Arkansas exempts:
        - Social Security benefits
        - Retirement income (up to $6,000)
        - Military retirement pay
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Retirement income exclusion (up to $6,000)
        if tax_return.income.retirement_income > 0:
            retirement_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 6000
            )
            subtractions += retirement_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Arkansas income additions."""
        additions = 0.0
        return additions

    def _calculate_low_income_credit(
        self,
        ar_agi: float,
        filing_status: str,
        num_dependents: int
    ) -> float:
        """
        Calculate Arkansas Low Income Tax Credit.

        Credit for taxpayers with income below poverty level.
        """
        # Income thresholds (2025 estimates)
        if filing_status in ("married_joint", "qualifying_widow"):
            threshold = 22500 + (num_dependents * 4000)
        else:
            threshold = 15000 + (num_dependents * 4000)

        if ar_agi > threshold:
            return 0.0

        # Credit up to $30 per person
        persons = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            persons = 2
        persons += num_dependents

        return persons * 30
