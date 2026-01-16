"""North Carolina state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_north_carolina_config() -> StateTaxConfig:
    """Create North Carolina tax configuration for 2025."""
    return StateTaxConfig(
        state_code="NC",
        state_name="North Carolina",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.0425,  # 4.25% flat rate for 2025
        brackets=None,
        starts_from="federal_agi",
        standard_deduction={
            # NC standard deductions for 2025 (indexed)
            "single": 12750,
            "married_joint": 25500,
            "married_separate": 12750,
            "head_of_household": 19125,
            "qualifying_widow": 25500,
        },
        personal_exemption_amount={
            # NC has no personal exemptions
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        dependent_exemption_amount=0,  # NC uses child deduction instead
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # NC exempts Social Security
        pension_exclusion_limit=None,  # NC has Bailey Settlement exclusion
        military_pay_exempt=True,  # NC exempts military retirement
        eitc_percentage=0.0,  # NC has no state EITC
        child_tax_credit_amount=0,  # NC has child deduction, not credit
        has_local_tax=False,
        # Note: NC child deduction ($500/child) handled in calculator
    )


@register_state("NC", 2025)
class NorthCarolinaCalculator(BaseStateCalculator):
    """
    North Carolina state tax calculator.

    North Carolina has:
    - Flat 4.25% tax rate (2025, down from 4.5% in 2024)
    - Standard deduction: $12,750 single, $25,500 MFJ
    - Child deduction: $500 per qualifying child
    - No personal exemptions
    - Full exemption of Social Security
    - Bailey Settlement retirement income exclusion (federal/state pensions vested by 1998)
    - Military retirement pay exemption
    - No state EITC
    - No local income tax
    """

    def __init__(self):
        super().__init__(get_north_carolina_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate North Carolina state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # NC additions
        additions = self.calculate_state_additions(tax_return)

        # NC subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # NC adjusted gross income
        nc_agi = federal_agi + additions - subtractions

        # Standard deduction
        std_deduction = self.config.get_standard_deduction(filing_status)

        # NC itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(nc_agi)

        # Choose higher deduction
        if tax_return.deductions.use_standard_deduction or std_deduction >= itemized:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        # Child deduction (NC specific)
        num_children = len(tax_return.taxpayer.dependents)
        child_deduction = self._calculate_child_deduction(num_children, nc_agi)

        # Total deductions
        total_deductions = deduction_amount + child_deduction

        # NC taxable income
        nc_taxable_income = max(0.0, nc_agi - total_deductions)

        # Calculate tax at flat rate
        tax_before_credits = self.calculate_brackets(nc_taxable_income, filing_status)

        # State credits (NC has limited credits)
        credits = {}

        # Credit for income tax paid to other states
        # (not calculated here - would need multi-state info)

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
            state_adjusted_income=nc_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=total_deductions,  # Including child deduction
            personal_exemptions=personal_exemptions,
            dependent_exemptions=num_children,
            exemption_amount=child_deduction,  # Child deduction as "exemption"
            state_taxable_income=nc_taxable_income,
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
        Calculate North Carolina income subtractions.

        NC exempts:
        - Social Security benefits
        - Bailey Settlement retirement income (vested by 1998)
        - Military retirement pay
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Military retirement is exempt
        # Would need to track separately in model

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate North Carolina income additions.

        Additions include:
        - Bonus depreciation addback (NC phases this in)
        - Section 179 expense addback (NC limits)
        """
        additions = 0.0
        return additions

    def _calculate_child_deduction(
        self,
        num_children: int,
        nc_agi: float
    ) -> float:
        """
        Calculate NC child deduction.

        $500 per qualifying child, with income phaseout.
        """
        if num_children == 0:
            return 0.0

        # Base deduction
        deduction_per_child = 500

        # Income phaseout (simplified)
        # Full deduction phases out above $40,000 single / $60,000 MFJ
        if nc_agi > 100000:
            return 0.0
        elif nc_agi > 60000:
            phase_out_pct = (nc_agi - 60000) / 40000
            deduction_per_child = 500 * (1 - phase_out_pct)

        return round(num_children * deduction_per_child, 2)
