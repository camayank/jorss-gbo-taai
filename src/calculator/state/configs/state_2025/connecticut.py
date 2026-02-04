"""Connecticut state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_connecticut_config() -> StateTaxConfig:
    """Create Connecticut tax configuration for 2025."""
    return StateTaxConfig(
        state_code="CT",
        state_name="Connecticut",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Connecticut 2025 brackets (7 brackets)
            "single": [
                (0, 0.03),          # 3% on first $10,000
                (10000, 0.05),      # 5% on $10,000 - $50,000
                (50000, 0.055),     # 5.5% on $50,000 - $100,000
                (100000, 0.06),     # 6% on $100,000 - $200,000
                (200000, 0.065),    # 6.5% on $200,000 - $250,000
                (250000, 0.069),    # 6.9% on $250,000 - $500,000
                (500000, 0.0699),   # 6.99% on over $500,000
            ],
            "married_joint": [
                (0, 0.03),
                (20000, 0.05),
                (100000, 0.055),
                (200000, 0.06),
                (400000, 0.065),
                (500000, 0.069),
                (1000000, 0.0699),
            ],
            "married_separate": [
                (0, 0.03),
                (10000, 0.05),
                (50000, 0.055),
                (100000, 0.06),
                (200000, 0.065),
                (250000, 0.069),
                (500000, 0.0699),
            ],
            "head_of_household": [
                (0, 0.03),
                (16000, 0.05),
                (80000, 0.055),
                (160000, 0.06),
                (320000, 0.065),
                (400000, 0.069),
                (800000, 0.0699),
            ],
            "qualifying_widow": [
                (0, 0.03),
                (20000, 0.05),
                (100000, 0.055),
                (200000, 0.06),
                (400000, 0.065),
                (500000, 0.069),
                (1000000, 0.0699),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # CT has no standard deduction (uses personal exemption)
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        personal_exemption_amount={
            # Connecticut personal exemption 2025 (income-based phase-out)
            "single": 15000,
            "married_joint": 24000,
            "married_separate": 12000,
            "head_of_household": 19000,
            "qualifying_widow": 24000,
        },
        dependent_exemption_amount=0,  # CT uses dependent credit instead
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # CT exempts SS below income threshold
        pension_exclusion_limit=None,  # CT has income-based pension exemption
        military_pay_exempt=True,  # CT exempts military retirement
        eitc_percentage=0.30,  # CT EITC is 30% of federal
        child_tax_credit_amount=250,  # CT Child Tax Credit
        has_local_tax=False,
    )


@register_state("CT", 2025)
class ConnecticutCalculator(BaseStateCalculator):
    """
    Connecticut state tax calculator.

    Connecticut has:
    - 7 progressive tax brackets (3% - 6.99%)
    - No standard deduction
    - Personal exemption with income phase-out ($15,000 single)
    - Social Security exemption (income-based)
    - CT EITC (30% of federal)
    - Child Tax Credit ($250 per child)
    - Property tax credit (up to $300)
    - No local income tax
    - Complex "tax recapture" for high income
    """

    def __init__(self):
        super().__init__(get_connecticut_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Connecticut state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Connecticut additions
        additions = self.calculate_state_additions(tax_return)

        # Connecticut subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Connecticut adjusted gross income
        ct_agi = federal_agi + additions - subtractions

        # No standard deduction
        std_deduction = 0.0
        itemized = 0.0
        deduction_used = "none"
        deduction_amount = 0.0

        # Personal exemption (phases out at higher income)
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        exemption_amount = self._calculate_personal_exemption(
            ct_agi, filing_status
        )

        # Connecticut taxable income
        ct_taxable_income = max(0.0, ct_agi - exemption_amount)

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(ct_taxable_income, filing_status)

        # Apply tax recapture for high income (3% surtax)
        tax_before_credits += self._calculate_tax_recapture(
            ct_agi, tax_before_credits, filing_status
        )

        # State credits
        credits = {}

        # CT EITC (30% of federal)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        ct_eitc = self.calculate_state_eitc(federal_eitc)
        if ct_eitc > 0:
            credits["ct_eitc"] = ct_eitc

        # Child Tax Credit ($250 per child)
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        if dependent_exemptions > 0:
            child_credit = self._calculate_child_tax_credit(
                dependent_exemptions, ct_agi, filing_status
            )
            if child_credit > 0:
                credits["ct_child_tax_credit"] = child_credit

        # Property Tax Credit (for homeowners/renters)
        property_credit = self._calculate_property_tax_credit(
            tax_return, ct_agi, filing_status
        )
        if property_credit > 0:
            credits["property_tax_credit"] = property_credit

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
            state_adjusted_income=ct_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=ct_taxable_income,
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
        Calculate Connecticut income subtractions.

        Connecticut allows:
        - Social Security (income-based exemption)
        - Military retirement
        - Teacher pension (partial)
        """
        subtractions = 0.0

        # Social Security exemption (income-based)
        # Full exemption below $75,000 single / $100,000 joint
        agi = tax_return.adjusted_gross_income or 0.0
        ss_income = tax_return.income.taxable_social_security
        if ss_income > 0:
            if agi < 100000:
                subtractions += ss_income
            elif agi < 150000:
                subtractions += ss_income * 0.75

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Connecticut income additions."""
        additions = 0.0
        return additions

    def _calculate_personal_exemption(
        self,
        ct_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Connecticut personal exemption with phase-out.

        Exemption phases out starting at $30,000 for single.
        """
        base_exemption = self.config.get_personal_exemption(filing_status)

        # Phase-out thresholds
        if filing_status in ("married_joint", "qualifying_widow"):
            phase_out_start = 48000
        elif filing_status == "head_of_household":
            phase_out_start = 38000
        else:
            phase_out_start = 30000

        if ct_agi <= phase_out_start:
            return base_exemption

        # Exemption reduces by $1,000 for each $1,000 over threshold
        reduction = ct_agi - phase_out_start
        exemption = max(0, base_exemption - reduction)
        return exemption

    def _calculate_tax_recapture(
        self,
        ct_agi: float,
        base_tax: float,
        filing_status: str
    ) -> float:
        """
        Calculate Connecticut tax recapture (3% surtax on high income).

        Applies when AGI exceeds certain thresholds.
        """
        # Recapture thresholds
        if filing_status in ("married_joint", "qualifying_widow"):
            threshold = 200000
        else:
            threshold = 100000

        if ct_agi <= threshold:
            return 0.0

        # 3% recapture on income over threshold
        excess = ct_agi - threshold
        return float(money(excess * 0.03))

    def _calculate_child_tax_credit(
        self,
        num_children: int,
        ct_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Connecticut Child Tax Credit.

        $250 per child with income phase-out.
        """
        if num_children == 0:
            return 0.0

        # Income limits
        if filing_status in ("married_joint", "qualifying_widow"):
            income_limit = 200000
        else:
            income_limit = 100000

        if ct_agi > income_limit:
            return 0.0

        return num_children * self.config.child_tax_credit_amount

    def _calculate_property_tax_credit(
        self,
        tax_return: "TaxReturn",
        ct_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Connecticut Property Tax Credit.

        Credit for property taxes/rent paid, up to $300.
        """
        # Income limit
        if ct_agi > 107000:
            return 0.0

        # Check property tax
        if hasattr(tax_return.deductions, 'itemized'):
            property_tax = tax_return.deductions.itemized.real_estate_tax
            if property_tax > 0:
                return min(300, property_tax * 0.10)
        return 0.0

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for CT EITC calculation."""
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
