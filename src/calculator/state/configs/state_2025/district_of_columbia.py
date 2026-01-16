"""District of Columbia tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_dc_config() -> StateTaxConfig:
    """Create DC tax configuration for 2025."""
    return StateTaxConfig(
        state_code="DC",
        state_name="District of Columbia",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # DC 2025 brackets (6 brackets)
            "single": [
                (0, 0.04),          # 4% on first $10,000
                (10000, 0.06),      # 6% on $10,000 - $40,000
                (40000, 0.065),     # 6.5% on $40,000 - $60,000
                (60000, 0.085),     # 8.5% on $60,000 - $250,000
                (250000, 0.0925),   # 9.25% on $250,000 - $500,000
                (500000, 0.0975),   # 9.75% on $500,000 - $1,000,000
                (1000000, 0.1075),  # 10.75% on over $1,000,000
            ],
            "married_joint": [
                (0, 0.04),
                (10000, 0.06),
                (40000, 0.065),
                (60000, 0.085),
                (250000, 0.0925),
                (500000, 0.0975),
                (1000000, 0.1075),
            ],
            "married_separate": [
                (0, 0.04),
                (10000, 0.06),
                (40000, 0.065),
                (60000, 0.085),
                (250000, 0.0925),
                (500000, 0.0975),
                (1000000, 0.1075),
            ],
            "head_of_household": [
                (0, 0.04),
                (10000, 0.06),
                (40000, 0.065),
                (60000, 0.085),
                (250000, 0.0925),
                (500000, 0.0975),
                (1000000, 0.1075),
            ],
            "qualifying_widow": [
                (0, 0.04),
                (10000, 0.06),
                (40000, 0.065),
                (60000, 0.085),
                (250000, 0.0925),
                (500000, 0.0975),
                (1000000, 0.1075),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # DC standard deduction for 2025
            "single": 14600,
            "married_joint": 29200,
            "married_separate": 14600,
            "head_of_household": 21900,
            "qualifying_widow": 29200,
        },
        personal_exemption_amount={
            # DC personal exemptions
            "single": 4050,
            "married_joint": 8100,
            "married_separate": 4050,
            "head_of_household": 4050,
            "qualifying_widow": 4050,
        },
        dependent_exemption_amount=4050,  # Per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # DC exempts Social Security
        pension_exclusion_limit=3000,  # DC pension exclusion
        military_pay_exempt=True,  # DC exempts military retirement
        eitc_percentage=0.70,  # DC EITC is 70% of federal (highest in US)
        child_tax_credit_amount=0,
        has_local_tax=False,  # DC is its own jurisdiction
    )


@register_state("DC", 2025)
class DCCalculator(BaseStateCalculator):
    """
    District of Columbia tax calculator.

    DC has:
    - 7 progressive tax brackets (4% - 10.75%)
    - Standard deduction matches federal
    - Personal exemption: $4,050 per person
    - Dependent exemption: $4,050 per dependent
    - Full exemption of Social Security
    - Pension exclusion ($3,000)
    - DC EITC (70% of federal - highest in nation)
    - Schedule H (homeowner/renter credit)
    - No separate local tax (DC is its own entity)
    """

    def __init__(self):
        super().__init__(get_dc_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate DC tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # DC additions
        additions = self.calculate_state_additions(tax_return)

        # DC subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # DC adjusted gross income
        dc_agi = federal_agi + additions - subtractions

        # Standard deduction
        std_deduction = self.config.get_standard_deduction(filing_status)

        # DC itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(dc_agi)

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
        dependent_exemption_amt = dependent_exemptions * self.config.dependent_exemption_amount
        exemption_amount = personal_exemption_amt + dependent_exemption_amt

        # DC taxable income
        dc_taxable_income = max(
            0.0,
            dc_agi - deduction_amount - exemption_amount
        )

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(dc_taxable_income, filing_status)

        # State credits
        credits = {}

        # DC EITC (70% of federal - highest in nation)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        dc_eitc = self.calculate_state_eitc(federal_eitc)
        if dc_eitc > 0:
            credits["dc_eitc"] = dc_eitc

        # Schedule H (Property Tax Credit / Rent Credit)
        schedule_h_credit = self._calculate_schedule_h_credit(
            tax_return, dc_agi, filing_status
        )
        if schedule_h_credit > 0:
            credits["schedule_h_credit"] = schedule_h_credit

        total_credits = sum(credits.values())

        # Net tax
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # Withholding
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
            state_adjusted_income=dc_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=dc_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2),
            state_credits=credits,
            total_state_credits=round(total_credits, 2),
            local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """Calculate DC income subtractions."""
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Pension exclusion (up to $3,000)
        if tax_return.income.retirement_income > 0:
            pension_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 3000
            )
            subtractions += pension_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate DC income additions."""
        return 0.0

    def _calculate_schedule_h_credit(
        self,
        tax_return: "TaxReturn",
        dc_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate DC Schedule H Credit (property tax/rent credit).

        Credit for homeowners paying property tax or renters.
        """
        # Income limit
        if dc_agi > 57600:
            return 0.0

        # Check for property tax
        if hasattr(tax_return.deductions, 'itemized'):
            property_tax = tax_return.deductions.itemized.real_estate_tax
            if property_tax > 0:
                # Credit based on income and property tax
                return min(1200, property_tax * 0.05)

        return 0.0

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for DC EITC calculation."""
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
