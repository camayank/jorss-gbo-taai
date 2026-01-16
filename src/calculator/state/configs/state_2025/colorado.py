"""Colorado state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_colorado_config() -> StateTaxConfig:
    """Create Colorado tax configuration for 2025."""
    return StateTaxConfig(
        state_code="CO",
        state_name="Colorado",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.044,  # 4.4% flat rate (reduced from 4.55% in 2024)
        brackets=None,
        starts_from="federal_taxable_income",  # CO starts from federal taxable income
        standard_deduction={
            # CO uses federal taxable income, so no additional deduction
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        personal_exemption_amount={
            # CO has no personal exemptions
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        dependent_exemption_amount=0,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # CO exempts Social Security for age 55+
        pension_exclusion_limit=24000,  # CO pension/annuity exclusion (age 55-64)
        military_pay_exempt=True,  # CO exempts military pay
        eitc_percentage=0.25,  # CO EITC is 25% of federal (for 2025)
        child_tax_credit_amount=1200,  # CO Child Tax Credit ($1,200 ages 0-6)
        has_local_tax=False,
    )


@register_state("CO", 2025)
class ColoradoCalculator(BaseStateCalculator):
    """
    Colorado state tax calculator.

    Colorado has:
    - Flat 4.4% tax rate (2025)
    - Uses federal taxable income as starting point
    - No state standard deduction (already in federal)
    - Social Security exempt for age 55+
    - Pension exclusion ($24,000 for 55-64, $20,000 for 65+)
    - Colorado EITC (25% of federal, refundable)
    - Colorado Child Tax Credit ($1,200 for ages 0-6, $1,000 for 6-16)
    - TABOR refund mechanism
    - No local income tax
    """

    def __init__(self):
        super().__init__(get_colorado_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Colorado state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Federal values
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Colorado starts from federal taxable income
        starting_income = federal_taxable_income

        # Colorado additions
        additions = self.calculate_state_additions(tax_return)

        # Colorado subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Colorado taxable income
        co_taxable_income = max(0.0, starting_income + additions - subtractions)

        # No additional deductions (already in federal)
        std_deduction = 0.0
        itemized = 0.0
        deduction_used = "federal"
        deduction_amount = 0.0

        # Calculate tax at flat rate
        tax_before_credits = self.calculate_brackets(co_taxable_income, filing_status)

        # State credits
        credits = {}

        # Colorado EITC (25% of federal, refundable)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        co_eitc = self.calculate_state_eitc(federal_eitc)
        if co_eitc > 0:
            credits["co_eitc"] = co_eitc

        # Colorado Child Tax Credit
        child_credit = self._calculate_child_tax_credit(
            tax_return, co_taxable_income, filing_status
        )
        if child_credit > 0:
            credits["co_child_tax_credit"] = child_credit

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
            state_adjusted_income=co_taxable_income,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=len(tax_return.taxpayer.dependents),
            exemption_amount=0.0,
            state_taxable_income=co_taxable_income,
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
        Calculate Colorado income subtractions.

        Colorado allows subtractions for:
        - Social Security (for age 55+, already partially exempt federally)
        - Pension/annuity income exclusion
        - Military retirement pay
        - Colorado capital gains exclusion (for assets held 5+ years)
        """
        subtractions = 0.0

        # Social Security - CO allows additional subtraction
        # Federal taxable SS is already reduced, CO exempts remainder
        subtractions += tax_return.income.taxable_social_security

        # Pension/annuity exclusion (up to $24,000 for 55-64, $20,000 for 65+)
        if tax_return.income.retirement_income > 0:
            pension_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 24000
            )
            subtractions += pension_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Colorado income additions.

        Additions include:
        - State income tax refund (if itemized previous year)
        - Out-of-state losses
        """
        additions = 0.0
        return additions

    def _calculate_child_tax_credit(
        self,
        tax_return: "TaxReturn",
        co_taxable_income: float,
        filing_status: str
    ) -> float:
        """
        Calculate Colorado Child Tax Credit.

        $1,200 per child ages 0-5
        $1,000 per child ages 6-16
        Full credit for income under $75,000 single / $85,000 MFJ
        """
        num_children = len(tax_return.taxpayer.dependents)
        if num_children == 0:
            return 0.0

        # Income limits
        if filing_status in ("married_joint", "qualifying_widow"):
            income_limit = 85000
        else:
            income_limit = 75000

        if co_taxable_income > income_limit * 1.5:
            return 0.0

        # Simplified: assume average credit of $1,100 per child
        # In reality would need child age information
        credit_per_child = 1100

        # Phase out above income limit
        if co_taxable_income > income_limit:
            phase_out_pct = min(1.0, (co_taxable_income - income_limit) / (income_limit * 0.5))
            credit_per_child = 1100 * (1 - phase_out_pct)

        return round(num_children * credit_per_child, 2)

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for CO EITC calculation."""
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
