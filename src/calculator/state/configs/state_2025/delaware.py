"""Delaware state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_delaware_config() -> StateTaxConfig:
    """Create Delaware tax configuration for 2025."""
    return StateTaxConfig(
        state_code="DE",
        state_name="Delaware",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Delaware 2025 brackets (7 brackets)
            "single": [
                (0, 0.0),           # 0% on first $2,000
                (2000, 0.022),      # 2.2% on $2,000 - $5,000
                (5000, 0.039),      # 3.9% on $5,000 - $10,000
                (10000, 0.048),     # 4.8% on $10,000 - $20,000
                (20000, 0.052),     # 5.2% on $20,000 - $25,000
                (25000, 0.0555),    # 5.55% on $25,000 - $60,000
                (60000, 0.066),     # 6.6% on over $60,000
            ],
            "married_joint": [
                (0, 0.0),
                (2000, 0.022),
                (5000, 0.039),
                (10000, 0.048),
                (20000, 0.052),
                (25000, 0.0555),
                (60000, 0.066),
            ],
            "married_separate": [
                (0, 0.0),
                (2000, 0.022),
                (5000, 0.039),
                (10000, 0.048),
                (20000, 0.052),
                (25000, 0.0555),
                (60000, 0.066),
            ],
            "head_of_household": [
                (0, 0.0),
                (2000, 0.022),
                (5000, 0.039),
                (10000, 0.048),
                (20000, 0.052),
                (25000, 0.0555),
                (60000, 0.066),
            ],
            "qualifying_widow": [
                (0, 0.0),
                (2000, 0.022),
                (5000, 0.039),
                (10000, 0.048),
                (20000, 0.052),
                (25000, 0.0555),
                (60000, 0.066),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # Delaware standard deductions for 2025
            "single": 3250,
            "married_joint": 6500,
            "married_separate": 3250,
            "head_of_household": 3250,
            "qualifying_widow": 6500,
        },
        personal_exemption_amount={
            # Delaware personal exemption
            "single": 110,  # Tax credit
            "married_joint": 110,
            "married_separate": 110,
            "head_of_household": 110,
            "qualifying_widow": 110,
        },
        dependent_exemption_amount=110,  # Tax credit per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # DE exempts Social Security
        pension_exclusion_limit=12500,  # DE pension exclusion (age 60+)
        military_pay_exempt=True,  # DE exempts military retirement
        eitc_percentage=0.0,  # Delaware has no state EITC
        child_tax_credit_amount=0,
        has_local_tax=True,  # Wilmington has city wage tax
    )


@register_state("DE", 2025)
class DelawareCalculator(BaseStateCalculator):
    """
    Delaware state tax calculator.

    Delaware has:
    - 7 progressive tax brackets (0% - 6.6%)
    - Standard deduction: $3,250 single, $6,500 MFJ
    - Personal/dependent exemption as tax credit ($110 each)
    - Full exemption of Social Security
    - Pension exclusion ($12,500 for 60+)
    - Military retirement pay exemption
    - Wilmington city wage tax (1.25%)
    - No sales tax (offset by income tax)
    - No state EITC
    """

    def __init__(self):
        super().__init__(get_delaware_config())
        self._is_wilmington_resident = False

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Delaware state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Check for Wilmington residency
        self._is_wilmington_resident = self._check_wilmington_residency(tax_return)

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Delaware additions
        additions = self.calculate_state_additions(tax_return)

        # Delaware subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Delaware adjusted gross income
        de_agi = federal_agi + additions - subtractions

        # Standard deduction
        std_deduction = self.config.get_standard_deduction(filing_status)

        # Delaware itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(de_agi)

        # Choose higher deduction
        if tax_return.deductions.use_standard_deduction or std_deduction >= itemized:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        # Delaware taxable income
        de_taxable_income = max(0.0, de_agi - deduction_amount)

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(de_taxable_income, filing_status)

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
            credits["exemption_credit"] = min(exemption_credit, tax_before_credits)

        total_credits = sum(credits.values())

        exemption_amount = exemption_credit

        # Net state tax
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # Wilmington city wage tax (1.25%)
        local_tax = 0.0
        if self._is_wilmington_resident:
            wages = tax_return.income.get_total_wages()
            local_tax = float(money(wages * 0.0125))

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
            state_adjusted_income=de_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=de_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)),
            state_credits=credits,
            total_state_credits=float(money(total_credits)),
            local_tax=local_tax,
            state_tax_liability=float(money(state_tax_liability)),
            state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_refund_or_owed)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Delaware income subtractions.

        Delaware exempts:
        - Social Security benefits
        - Pension/retirement income (up to $12,500 for 60+)
        - Military retirement pay
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Pension exclusion (up to $12,500 for 60+)
        if tax_return.income.retirement_income > 0:
            pension_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 12500
            )
            subtractions += pension_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Delaware income additions."""
        additions = 0.0
        return additions

    def _check_wilmington_residency(self, tax_return: "TaxReturn") -> bool:
        """Check if taxpayer is Wilmington resident."""
        city = tax_return.taxpayer.city
        if city:
            return city.lower().strip() == "wilmington"
        return False
