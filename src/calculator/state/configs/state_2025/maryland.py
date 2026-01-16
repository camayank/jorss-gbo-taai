"""Maryland state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_maryland_config() -> StateTaxConfig:
    """Create Maryland tax configuration for 2025."""
    return StateTaxConfig(
        state_code="MD",
        state_name="Maryland",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Maryland 2025 brackets (8 brackets)
            "single": [
                (0, 0.02),         # 2% on first $1,000
                (1000, 0.03),      # 3% on $1,000 - $2,000
                (2000, 0.04),      # 4% on $2,000 - $3,000
                (3000, 0.0475),    # 4.75% on $3,000 - $100,000
                (100000, 0.05),    # 5% on $100,000 - $125,000
                (125000, 0.0525),  # 5.25% on $125,000 - $150,000
                (150000, 0.055),   # 5.5% on $150,000 - $250,000
                (250000, 0.0575),  # 5.75% on over $250,000
            ],
            "married_joint": [
                (0, 0.02),
                (1000, 0.03),
                (2000, 0.04),
                (3000, 0.0475),
                (150000, 0.05),
                (175000, 0.0525),
                (225000, 0.055),
                (300000, 0.0575),
            ],
            "married_separate": [
                (0, 0.02),
                (1000, 0.03),
                (2000, 0.04),
                (3000, 0.0475),
                (100000, 0.05),
                (125000, 0.0525),
                (150000, 0.055),
                (250000, 0.0575),
            ],
            "head_of_household": [
                (0, 0.02),
                (1000, 0.03),
                (2000, 0.04),
                (3000, 0.0475),
                (150000, 0.05),
                (175000, 0.0525),
                (225000, 0.055),
                (300000, 0.0575),
            ],
            "qualifying_widow": [
                (0, 0.02),
                (1000, 0.03),
                (2000, 0.04),
                (3000, 0.0475),
                (150000, 0.05),
                (175000, 0.0525),
                (225000, 0.055),
                (300000, 0.0575),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # MD standard deduction (15% of AGI with limits)
            "single": 2550,  # Minimum
            "married_joint": 5100,
            "married_separate": 2550,
            "head_of_household": 2550,
            "qualifying_widow": 5100,
        },
        personal_exemption_amount={
            # Maryland personal exemption 2025
            "single": 3200,
            "married_joint": 3200,  # Per person
            "married_separate": 3200,
            "head_of_household": 3200,
            "qualifying_widow": 3200,
        },
        dependent_exemption_amount=3200,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # MD exempts Social Security
        pension_exclusion_limit=39500,  # MD pension exclusion (2025)
        military_pay_exempt=True,
        eitc_percentage=0.45,  # MD EITC is 45% of federal (refundable) or 100% (nonrefundable)
        child_tax_credit_amount=500,  # MD Child Tax Credit
        has_local_tax=True,  # MD has county income taxes (2.25% - 3.2%)
        local_tax_brackets={
            # County tax rates vary; using 3.0% as average
            "single": [(0, 0.03)],
            "married_joint": [(0, 0.03)],
            "married_separate": [(0, 0.03)],
            "head_of_household": [(0, 0.03)],
            "qualifying_widow": [(0, 0.03)],
        },
    )


@register_state("MD", 2025)
class MarylandCalculator(BaseStateCalculator):
    """
    Maryland state tax calculator.

    Maryland has:
    - 8 progressive state tax brackets (up to 5.75%)
    - County local income tax (2.25% - 3.2%, varies by county)
    - Standard deduction: 15% of AGI ($2,550 min, $2,550 max single)
    - Personal exemption: $3,200 per person
    - Dependent exemption: $3,200 per dependent
    - Full exemption of Social Security
    - Pension exclusion ($39,500 for 2025)
    - Maryland EITC (45% refundable or 100% nonrefundable)
    - Child Tax Credit ($500 per child under 17)
    """

    def __init__(self):
        super().__init__(get_maryland_config())
        self._county_rate = 0.03  # Default county rate

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Maryland state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Maryland additions
        additions = self.calculate_state_additions(tax_return)

        # Maryland subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Maryland adjusted gross income
        md_agi = federal_agi + additions - subtractions

        # Maryland standard deduction (15% of AGI with min/max)
        std_deduction = self._calculate_standard_deduction(md_agi, filing_status)

        # Maryland itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(md_agi)

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
        total_exemptions = personal_exemptions + dependent_exemptions

        exemption_per_person = self.config.get_personal_exemption(filing_status)
        exemption_amount = total_exemptions * exemption_per_person

        # Maryland taxable income
        md_taxable_income = max(
            0.0,
            md_agi - deduction_amount - exemption_amount
        )

        # Calculate state tax using brackets
        tax_before_credits = self.calculate_brackets(md_taxable_income, filing_status)

        # Calculate county (local) tax
        local_tax = self.calculate_local_tax(md_taxable_income, filing_status)

        # State credits
        credits = {}

        # Maryland EITC
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        md_eitc = self._calculate_md_eitc(federal_eitc, tax_before_credits)
        if md_eitc > 0:
            credits["md_eitc"] = md_eitc

        # Maryland Child Tax Credit
        child_credit = self._calculate_child_tax_credit(
            tax_return, md_agi, filing_status
        )
        if child_credit > 0:
            credits["md_child_tax_credit"] = child_credit

        # Poverty Level Credit (for very low income)
        poverty_credit = self._calculate_poverty_level_credit(
            tax_return, md_agi, filing_status
        )
        if poverty_credit > 0:
            credits["poverty_level_credit"] = poverty_credit

        total_credits = sum(credits.values())

        # Net state tax (credits apply to state, not local)
        state_tax_only = max(0.0, tax_before_credits - total_credits)
        state_tax_liability = state_tax_only + local_tax

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
            state_adjusted_income=md_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=md_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2),
            state_credits=credits,
            total_state_credits=round(total_credits, 2),
            local_tax=round(local_tax, 2),
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def _calculate_standard_deduction(
        self,
        md_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Maryland standard deduction.

        15% of AGI with minimum and maximum limits.
        """
        base_deduction = md_agi * 0.15

        if filing_status in ("married_joint", "qualifying_widow"):
            min_deduction = 5100
            max_deduction = 5100
        else:
            min_deduction = 2550
            max_deduction = 2550

        return min(max(base_deduction, min_deduction), max_deduction)

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Maryland income subtractions.

        Maryland allows:
        - Social Security (fully exempt)
        - Pension exclusion ($39,500 for 2025)
        - Military retirement (fully exempt)
        - Two-income married couple subtraction
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Pension exclusion
        if tax_return.income.retirement_income > 0:
            pension_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 39500
            )
            subtractions += pension_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Maryland income additions."""
        additions = 0.0
        return additions

    def _calculate_md_eitc(
        self,
        federal_eitc: float,
        state_tax: float
    ) -> float:
        """
        Calculate Maryland EITC.

        Taxpayer can choose:
        - 45% of federal EITC (refundable)
        - 100% of federal EITC (nonrefundable, limited to tax)

        We calculate the better option.
        """
        if federal_eitc <= 0:
            return 0.0

        refundable_credit = federal_eitc * 0.45
        nonrefundable_credit = min(federal_eitc, state_tax)

        return max(refundable_credit, nonrefundable_credit)

    def _calculate_child_tax_credit(
        self,
        tax_return: "TaxReturn",
        md_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Maryland Child Tax Credit.

        $500 per qualifying child under 17.
        Income limits apply.
        """
        num_children = len(tax_return.taxpayer.dependents)
        if num_children == 0:
            return 0.0

        # Income limits
        if filing_status in ("married_joint", "qualifying_widow"):
            income_limit = 15000
        else:
            income_limit = 6000

        if md_agi > income_limit:
            return 0.0

        return num_children * self.config.child_tax_credit_amount

    def _calculate_poverty_level_credit(
        self,
        tax_return: "TaxReturn",
        md_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Maryland Poverty Level Credit.

        Credit for very low income taxpayers.
        """
        # Poverty level thresholds (2025 estimates)
        if filing_status in ("married_joint", "qualifying_widow"):
            poverty_level = 20000
        else:
            poverty_level = 15000

        if md_agi > poverty_level:
            return 0.0

        # Credit reduces tax proportionally
        return 0.0  # Simplified - would need full calculation

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for MD EITC calculation."""
        earned_income = (
            tax_return.income.get_total_wages() +
            tax_return.income.self_employment_income -
            tax_return.income.self_employment_expenses
        )
        agi = tax_return.adjusted_gross_income or 0.0
        num_children = len(tax_return.taxpayer.dependents)

        return tax_return.credits.calculate_eitc(
            earned_income,
            agi,
            filing_status,
            num_children
        )
