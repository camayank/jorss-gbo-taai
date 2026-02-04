"""Illinois state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_illinois_config() -> StateTaxConfig:
    """Create Illinois tax configuration for 2025."""
    return StateTaxConfig(
        state_code="IL",
        state_name="Illinois",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.0495,  # 4.95% flat rate
        brackets=None,  # Not applicable for flat tax
        starts_from="federal_agi",
        standard_deduction={
            # Illinois doesn't have standard deduction - uses exemptions
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        # Personal exemption amounts (2025 estimates)
        personal_exemption_amount={
            "single": 2625,
            "married_joint": 2625,  # Per person
            "married_separate": 2625,
            "head_of_household": 2625,
            "qualifying_widow": 2625,
        },
        dependent_exemption_amount=2625,  # Per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # IL exempts Social Security
        pension_exclusion_limit=None,  # IL exempts most retirement income
        military_pay_exempt=True,  # IL exempts military pay
        eitc_percentage=0.20,  # IL EITC is 20% of federal
        child_tax_credit_amount=0,
        has_local_tax=False,  # Chicago has no additional income tax
    )


@register_state("IL", 2025)
class IllinoisCalculator(BaseStateCalculator):
    """
    Illinois state tax calculator.

    Illinois has a flat tax system:
    - Flat 4.95% tax rate on net income
    - Personal exemption of $2,625 per person
    - IL EITC is 20% of federal EITC
    - Full exemption of Social Security
    - Full exemption of retirement income (pensions, 401k, IRA distributions)
    - Military pay exemption
    - No local income tax
    """

    def __init__(self):
        super().__init__(get_illinois_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Illinois state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Illinois additions
        additions = self.calculate_state_additions(tax_return)

        # Illinois subtractions (retirement income, Social Security, etc.)
        subtractions = self.calculate_state_subtractions(tax_return)

        # Illinois base income
        il_base_income = federal_agi + additions - subtractions

        # Personal exemptions
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)
        total_exemptions = personal_exemptions + dependent_exemptions

        exemption_per_person = self.config.get_personal_exemption(filing_status)
        exemption_amount = total_exemptions * exemption_per_person

        # Illinois has no standard/itemized deduction - only exemptions
        # But for consistency with other states, we report 0
        std_deduction = 0.0
        itemized = 0.0
        deduction_used = "none"
        deduction_amount = 0.0

        # Illinois net income (taxable income)
        il_taxable_income = max(0.0, il_base_income - exemption_amount)

        # Calculate tax at flat rate
        tax_before_credits = self.calculate_brackets(il_taxable_income, filing_status)

        # State credits
        credits = {}

        # IL EITC (20% of federal)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        il_eitc = self.calculate_state_eitc(federal_eitc)
        if il_eitc > 0:
            credits["il_eitc"] = il_eitc

        # Property tax credit (for homeowners)
        property_tax_credit = self._calculate_property_tax_credit(tax_return)
        if property_tax_credit > 0:
            credits["property_tax_credit"] = property_tax_credit

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
            state_adjusted_income=il_base_income,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=il_taxable_income,
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
        Calculate Illinois income subtractions.

        Illinois exempts:
        - Social Security benefits
        - Retirement income (pensions, 401k, IRA)
        - Military pay
        - Interest from US government obligations
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Retirement income is fully exempt in Illinois
        # This includes pensions, 401k distributions, IRA distributions
        subtractions += tax_return.income.retirement_income

        # Note: In a complete implementation, would also subtract:
        # - Military pay (would need to track separately)
        # - US government bond interest (would need to track separately)

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Illinois income additions.

        Additions include:
        - Interest from other states' municipal bonds
        - Items deducted federally but not allowed by Illinois
        """
        additions = 0.0

        # Most additions would require additional tracking fields
        # that aren't currently in the model

        return additions

    def _calculate_property_tax_credit(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Illinois property tax credit.

        Credit is 5% of property taxes paid on principal residence.
        """
        # Would need property tax information
        # For now, check if itemized deductions include real estate tax
        if hasattr(tax_return.deductions, 'itemized'):
            property_tax = tax_return.deductions.itemized.real_estate_tax
            if property_tax > 0:
                # 5% of property taxes paid
                return float(money(property_tax * 0.05))
        return 0.0

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for IL EITC calculation."""
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
