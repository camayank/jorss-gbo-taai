"""Wisconsin state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_wisconsin_config() -> StateTaxConfig:
    """Create Wisconsin tax configuration for 2025."""
    return StateTaxConfig(
        state_code="WI",
        state_name="Wisconsin",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Wisconsin 2025 brackets (4 brackets, indexed)
            "single": [
                (0, 0.035),        # 3.5% on first $14,320
                (14320, 0.044),    # 4.4% on $14,320 - $28,640
                (28640, 0.053),    # 5.3% on $28,640 - $315,310
                (315310, 0.0765),  # 7.65% on over $315,310
            ],
            "married_joint": [
                (0, 0.035),
                (19090, 0.044),
                (38190, 0.053),
                (420420, 0.0765),
            ],
            "married_separate": [
                (0, 0.035),
                (9545, 0.044),
                (19095, 0.053),
                (210210, 0.0765),
            ],
            "head_of_household": [
                (0, 0.035),
                (14320, 0.044),
                (28640, 0.053),
                (315310, 0.0765),
            ],
            "qualifying_widow": [
                (0, 0.035),
                (19090, 0.044),
                (38190, 0.053),
                (420420, 0.0765),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # Wisconsin standard deduction (sliding scale based on income)
            "single": 13230,
            "married_joint": 24500,
            "married_separate": 11680,
            "head_of_household": 16720,
            "qualifying_widow": 24500,
        },
        personal_exemption_amount={
            # Wisconsin has exemption credits, not deductions
            "single": 700,  # Exemption credit amount
            "married_joint": 700,
            "married_separate": 700,
            "head_of_household": 700,
            "qualifying_widow": 700,
        },
        dependent_exemption_amount=700,  # Per dependent credit
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # WI exempts Social Security
        pension_exclusion_limit=5000,  # WI retirement income exclusion
        military_pay_exempt=True,
        eitc_percentage=0.0,  # WI has Earned Income Credit but different calculation
        child_tax_credit_amount=0,
        has_local_tax=False,
    )


@register_state("WI", 2025)
class WisconsinCalculator(BaseStateCalculator):
    """
    Wisconsin state tax calculator.

    Wisconsin has:
    - 4 progressive tax brackets (up to 7.65%)
    - Sliding scale standard deduction (reduces at higher income)
    - Exemption credits ($700 per person/dependent)
    - Full exemption of Social Security
    - Retirement income exclusion ($5,000 single / $10,000 joint)
    - Wisconsin Earned Income Credit (varies by children)
    - Homestead Credit for property tax relief
    - No local income tax
    """

    def __init__(self):
        super().__init__(get_wisconsin_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Wisconsin state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Wisconsin additions
        additions = self.calculate_state_additions(tax_return)

        # Wisconsin subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Wisconsin adjusted gross income
        wi_agi = federal_agi + additions - subtractions

        # Wisconsin sliding scale standard deduction
        std_deduction = self._calculate_sliding_deduction(wi_agi, filing_status)

        # Wisconsin itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(wi_agi)

        # Choose higher deduction
        if tax_return.deductions.use_standard_deduction or std_deduction >= itemized:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        # Wisconsin taxable income
        wi_taxable_income = max(0.0, wi_agi - deduction_amount)

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(wi_taxable_income, filing_status)

        # State credits
        credits = {}

        # Exemption credits (nonrefundable)
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)
        total_exemptions = personal_exemptions + dependent_exemptions

        exemption_credit = total_exemptions * self.config.get_personal_exemption(filing_status)
        if exemption_credit > 0:
            credits["exemption_credit"] = min(exemption_credit, tax_before_credits)

        # Wisconsin Earned Income Credit
        wi_eic = self._calculate_wi_earned_income_credit(
            tax_return, filing_status
        )
        if wi_eic > 0:
            credits["wi_earned_income_credit"] = wi_eic

        # Homestead Credit
        homestead_credit = self._calculate_homestead_credit(
            tax_return, wi_agi
        )
        if homestead_credit > 0:
            credits["homestead_credit"] = homestead_credit

        total_credits = sum(credits.values())

        # Net state tax
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # State withholding
        state_withholding = self.get_state_withholding(tax_return)

        # Refund or owed
        state_refund_or_owed = state_withholding - state_tax_liability

        exemption_amount = exemption_credit

        return StateCalculationBreakdown(
            state_code=self.config.state_code,
            state_name=self.config.state_name,
            tax_year=self.config.tax_year,
            filing_status=filing_status,
            federal_agi=federal_agi,
            federal_taxable_income=federal_taxable_income,
            state_additions=additions,
            state_subtractions=subtractions,
            state_adjusted_income=wi_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=wi_taxable_income,
            state_tax_before_credits=round(tax_before_credits, 2),
            state_credits=credits,
            total_state_credits=round(total_credits, 2),
            local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2),
            state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_refund_or_owed, 2),
        )

    def _calculate_sliding_deduction(
        self,
        wi_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Wisconsin sliding scale standard deduction.

        Deduction decreases as income increases.
        """
        if filing_status in ("married_joint", "qualifying_widow"):
            max_deduction = 24500
            phase_out_start = 23630
            phase_out_rate = 0.12048
        elif filing_status == "head_of_household":
            max_deduction = 16720
            phase_out_start = 17960
            phase_out_rate = 0.22515
        else:  # single, married_separate
            max_deduction = 13230
            phase_out_start = 17060
            phase_out_rate = 0.12048

        if wi_agi <= phase_out_start:
            return max_deduction

        reduction = (wi_agi - phase_out_start) * phase_out_rate
        return max(0, max_deduction - reduction)

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Wisconsin income subtractions.

        Wisconsin exempts:
        - Social Security (fully exempt)
        - Retirement income exclusion (up to $5,000/$10,000)
        - Military retirement
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Retirement income exclusion
        if tax_return.income.retirement_income > 0:
            retirement_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 5000
            )
            subtractions += retirement_exclusion

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Wisconsin income additions."""
        additions = 0.0
        return additions

    def _calculate_wi_earned_income_credit(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """
        Calculate Wisconsin Earned Income Credit.

        Percentage of federal EITC based on number of children:
        - 1 child: 4%
        - 2 children: 11%
        - 3+ children: 34%
        """
        num_children = len(tax_return.taxpayer.dependents)
        if num_children == 0:
            return 0.0

        # Get federal EITC estimate
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        if federal_eitc <= 0:
            return 0.0

        # WI credit percentage based on children
        if num_children == 1:
            percentage = 0.04
        elif num_children == 2:
            percentage = 0.11
        else:
            percentage = 0.34

        return round(federal_eitc * percentage, 2)

    def _calculate_homestead_credit(
        self,
        tax_return: "TaxReturn",
        wi_agi: float
    ) -> float:
        """
        Calculate Wisconsin Homestead Credit.

        Property tax relief for low-income homeowners/renters.
        """
        # Income limit
        if wi_agi > 24680:
            return 0.0

        # Would need property tax info
        if hasattr(tax_return.deductions, 'itemized'):
            property_tax = tax_return.deductions.itemized.real_estate_tax
            if property_tax > 0:
                # Credit based on excess property tax over income threshold
                credit = min(1168, property_tax * 0.10)
                return round(credit, 2)
        return 0.0

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for WI EIC calculation."""
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
