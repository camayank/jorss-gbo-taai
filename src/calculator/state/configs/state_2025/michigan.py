"""Michigan state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_michigan_config() -> StateTaxConfig:
    """Create Michigan tax configuration for 2025."""
    return StateTaxConfig(
        state_code="MI",
        state_name="Michigan",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.0425,  # 4.25% flat rate
        brackets=None,
        starts_from="federal_agi",
        standard_deduction={
            # Michigan has no standard deduction (uses exemptions)
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        personal_exemption_amount={
            # Michigan personal exemption 2025 (inflation adjusted)
            "single": 5600,
            "married_joint": 5600,  # Per person
            "married_separate": 5600,
            "head_of_household": 5600,
            "qualifying_widow": 5600,
        },
        dependent_exemption_amount=5600,  # Same as personal
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # MI exempts Social Security
        pension_exclusion_limit=None,  # MI has tiered pension exclusion
        military_pay_exempt=True,  # MI exempts military pay
        eitc_percentage=0.30,  # MI EITC is 30% of federal
        child_tax_credit_amount=0,
        has_local_tax=True,  # Some MI cities have income tax (Detroit, etc.)
    )


@register_state("MI", 2025)
class MichiganCalculator(BaseStateCalculator):
    """
    Michigan state tax calculator.

    Michigan has:
    - Flat 4.25% tax rate
    - Personal exemption: $5,600 per person (2025, indexed)
    - Dependent exemption: $5,600 per dependent
    - Full exemption of Social Security
    - Tiered pension/retirement income exclusion based on birth year
    - Military pay exemption
    - Michigan EITC (30% of federal)
    - City income taxes (Detroit 2.4%, others 0.5-1%)
    - Homestead Property Tax Credit
    """

    def __init__(self):
        super().__init__(get_michigan_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Michigan state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Michigan additions
        additions = self.calculate_state_additions(tax_return)

        # Michigan subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Michigan adjusted gross income
        mi_agi = federal_agi + additions - subtractions

        # No standard deduction (uses exemptions)
        std_deduction = 0.0
        itemized = 0.0
        deduction_used = "none"
        deduction_amount = 0.0

        # Personal exemptions
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)
        total_exemptions = personal_exemptions + dependent_exemptions

        exemption_per_person = self.config.get_personal_exemption(filing_status)
        exemption_amount = total_exemptions * exemption_per_person

        # Michigan taxable income
        mi_taxable_income = max(0.0, mi_agi - exemption_amount)

        # Calculate tax at flat rate
        tax_before_credits = self.calculate_brackets(mi_taxable_income, filing_status)

        # State credits
        credits = {}

        # Michigan EITC (30% of federal)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        mi_eitc = self.calculate_state_eitc(federal_eitc)
        if mi_eitc > 0:
            credits["mi_eitc"] = mi_eitc

        # Homestead Property Tax Credit (simplified)
        homestead_credit = self._calculate_homestead_credit(
            tax_return, mi_agi, filing_status
        )
        if homestead_credit > 0:
            credits["homestead_property_tax_credit"] = homestead_credit

        total_credits = sum(credits.values())

        # Net state tax
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # City income tax (simplified - using 0 as default, would need city info)
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
            state_adjusted_income=mi_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=mi_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2),
            state_credits=credits,
            total_state_credits=round(total_credits, 2),
            local_tax=round(local_tax, 2),
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Michigan income subtractions.

        Michigan exempts:
        - Social Security benefits (fully)
        - Retirement/pension income (tiered by birth year)
        - Military pay/pensions
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Retirement income subtraction (tiered by birth year)
        # Simplified: assume standard exclusion applies
        if tax_return.income.retirement_income > 0:
            # Standard tier: up to $15,000 single / $30,000 joint
            retirement_exclusion = min(
                tax_return.income.retirement_income,
                30000  # Use joint amount as simplification
            )
            subtractions += retirement_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Michigan income additions."""
        additions = 0.0
        return additions

    def _calculate_homestead_credit(
        self,
        tax_return: "TaxReturn",
        mi_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Michigan Homestead Property Tax Credit.

        Credit based on property taxes paid vs income.
        Available for homeowners and renters.
        """
        # Income limit for credit (approximately)
        if mi_agi > 63000:
            return 0.0

        # Check for property tax or rent
        if hasattr(tax_return.deductions, 'itemized'):
            property_tax = tax_return.deductions.itemized.real_estate_tax
            if property_tax > 0:
                # Credit = (Property Tax - 3.2% of income) * 60%
                # Up to $1,600 maximum
                threshold = mi_agi * 0.032
                excess = max(0, property_tax - threshold)
                credit = min(1600, excess * 0.60)
                return round(credit, 2)
        return 0.0

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for MI EITC calculation."""
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
