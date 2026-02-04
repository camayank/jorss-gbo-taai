"""New Jersey state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_new_jersey_config() -> StateTaxConfig:
    """Create New Jersey tax configuration for 2025."""
    return StateTaxConfig(
        state_code="NJ",
        state_name="New Jersey",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # New Jersey 2025 brackets (7 brackets)
            "single": [
                (0, 0.014),         # 1.4% on first $20,000
                (20000, 0.0175),    # 1.75% on $20,000 - $35,000
                (35000, 0.035),     # 3.5% on $35,000 - $40,000
                (40000, 0.05525),   # 5.525% on $40,000 - $75,000
                (75000, 0.0637),    # 6.37% on $75,000 - $500,000
                (500000, 0.0897),   # 8.97% on $500,000 - $1,000,000
                (1000000, 0.1075),  # 10.75% on over $1,000,000
            ],
            "married_joint": [
                (0, 0.014),
                (20000, 0.0175),
                (50000, 0.0245),    # 2.45% on $50,000 - $70,000
                (70000, 0.035),
                (80000, 0.05525),
                (150000, 0.0637),
                (500000, 0.0897),
                (1000000, 0.1075),
            ],
            "married_separate": [
                (0, 0.014),
                (20000, 0.0175),
                (35000, 0.035),
                (40000, 0.05525),
                (75000, 0.0637),
                (500000, 0.0897),
                (1000000, 0.1075),
            ],
            "head_of_household": [
                (0, 0.014),
                (20000, 0.0175),
                (50000, 0.0245),
                (70000, 0.035),
                (80000, 0.05525),
                (150000, 0.0637),
                (500000, 0.0897),
                (1000000, 0.1075),
            ],
            "qualifying_widow": [
                (0, 0.014),
                (20000, 0.0175),
                (50000, 0.0245),
                (70000, 0.035),
                (80000, 0.05525),
                (150000, 0.0637),
                (500000, 0.0897),
                (1000000, 0.1075),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # NJ has no standard deduction (uses exemptions)
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        personal_exemption_amount={
            # NJ personal exemption 2025
            "single": 1000,
            "married_joint": 2000,  # $1000 each
            "married_separate": 1000,
            "head_of_household": 1000,
            "qualifying_widow": 1000,
        },
        dependent_exemption_amount=1500,  # Per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # NJ exempts Social Security
        pension_exclusion_limit=100000,  # NJ pension exclusion up to $100K (for 62+)
        military_pay_exempt=True,  # NJ exempts military pay
        eitc_percentage=0.40,  # NJ EITC is 40% of federal
        child_tax_credit_amount=500,  # NJ Child Tax Credit
        has_local_tax=False,
    )


@register_state("NJ", 2025)
class NewJerseyCalculator(BaseStateCalculator):
    """
    New Jersey state tax calculator.

    New Jersey has:
    - 7 progressive tax brackets (up to 10.75% top rate)
    - No standard deduction (uses exemptions only)
    - Personal exemption of $1,000 per person
    - Dependent exemption of $1,500 per dependent
    - NJ EITC (40% of federal)
    - Child Tax Credit ($500 per child under 6, income limits apply)
    - Full exemption of Social Security
    - Pension exclusion up to $100,000 (age 62+)
    - Property tax deduction/credit
    """

    def __init__(self):
        super().__init__(get_new_jersey_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate New Jersey state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # NJ additions
        additions = self.calculate_state_additions(tax_return)

        # NJ subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # NJ gross income
        nj_gross_income = federal_agi + additions - subtractions

        # NJ uses exemptions, not deductions
        std_deduction = 0.0
        itemized = 0.0
        deduction_used = "none"
        deduction_amount = 0.0

        # Personal exemptions
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)

        personal_exemption_amount = (
            personal_exemptions * self.config.get_personal_exemption(filing_status)
        )
        dependent_exemption_amount = (
            dependent_exemptions * self.config.dependent_exemption_amount
        )
        exemption_amount = personal_exemption_amount + dependent_exemption_amount

        # NJ taxable income
        nj_taxable_income = max(0.0, nj_gross_income - exemption_amount)

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(nj_taxable_income, filing_status)

        # State credits
        credits = {}

        # NJ EITC (40% of federal)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        nj_eitc = self.calculate_state_eitc(federal_eitc)
        if nj_eitc > 0:
            credits["nj_eitc"] = nj_eitc

        # NJ Child Tax Credit (children under 6)
        child_credit = self._calculate_child_tax_credit(tax_return, nj_gross_income)
        if child_credit > 0:
            credits["nj_child_tax_credit"] = child_credit

        # Property tax deduction/credit (simplified)
        property_tax_benefit = self._calculate_property_tax_benefit(
            tax_return, nj_gross_income, filing_status
        )
        if property_tax_benefit > 0:
            credits["property_tax_credit"] = property_tax_benefit

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
            state_adjusted_income=nj_gross_income,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=nj_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)),
            state_credits=credits,
            total_state_credits=float(money(total_credits)),
            local_tax=0.0,
            state_tax_liability=float(money(state_tax_liability)),
            state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_refund_or_owed)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate New Jersey income subtractions.

        NJ exempts:
        - Social Security benefits
        - Pension/retirement income (up to $100K for age 62+)
        - Military pensions
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Pension exclusion (up to $100,000 for qualified seniors)
        # Simplified: assume taxpayer qualifies
        if tax_return.income.retirement_income > 0:
            pension_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 100000
            )
            subtractions += pension_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate New Jersey income additions."""
        additions = 0.0
        return additions

    def _calculate_child_tax_credit(
        self,
        tax_return: "TaxReturn",
        nj_income: float
    ) -> float:
        """
        Calculate NJ Child Tax Credit.

        $500 per qualifying child under 6, with income phaseout.
        """
        # Count children under 6 (simplified: assume all dependents qualify)
        # In reality, would need age information
        num_children = len(tax_return.taxpayer.dependents)
        if num_children == 0:
            return 0.0

        # Assume half of dependents are under 6 (simplified)
        children_under_6 = max(1, num_children // 2) if num_children > 0 else 0

        # Income limit: $80,000 (phases out after)
        if nj_income > 80000:
            return 0.0

        credit = children_under_6 * self.config.child_tax_credit_amount
        return float(money(credit))

    def _calculate_property_tax_benefit(
        self,
        tax_return: "TaxReturn",
        nj_income: float,
        filing_status: str
    ) -> float:
        """
        Calculate NJ property tax deduction or credit.

        NJ allows up to $15,000 property tax deduction, or
        credit for lower-income homeowners/renters.
        """
        # Check if property tax was paid
        if hasattr(tax_return.deductions, 'itemized'):
            property_tax = tax_return.deductions.itemized.real_estate_tax
            if property_tax > 0:
                # For higher income: deduction (already in itemized)
                # For lower income: credit of up to $50
                if nj_income < 150000:
                    return min(50.0, property_tax * 0.01)
        return 0.0

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for NJ EITC calculation."""
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
