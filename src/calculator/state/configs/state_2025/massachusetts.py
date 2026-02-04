"""Massachusetts state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_massachusetts_config() -> StateTaxConfig:
    """Create Massachusetts tax configuration for 2025."""
    return StateTaxConfig(
        state_code="MA",
        state_name="Massachusetts",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.05,  # 5% flat rate (Part A income)
        brackets=None,
        starts_from="federal_agi",
        standard_deduction={
            # MA has no standard deduction (uses exemptions)
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        personal_exemption_amount={
            # Massachusetts personal exemption 2025
            "single": 4400,
            "married_joint": 8800,
            "married_separate": 4400,
            "head_of_household": 6800,
            "qualifying_widow": 4400,
        },
        dependent_exemption_amount=1000,  # Per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # MA exempts Social Security
        pension_exclusion_limit=2000,  # MA pension income deduction
        military_pay_exempt=True,  # MA exempts military pay
        eitc_percentage=0.40,  # MA EITC is 40% of federal
        child_tax_credit_amount=180,  # MA child care credit
        has_local_tax=False,
        # Note: Millionaire tax (4% surtax on income over $1M) handled in calculator
    )


@register_state("MA", 2025)
class MassachusettsCalculator(BaseStateCalculator):
    """
    Massachusetts state tax calculator.

    Massachusetts has:
    - Base 5% flat tax rate
    - Additional 4% "millionaire tax" on income over $1,000,000 (total 9%)
    - Personal exemption: $4,400 single, $8,800 MFJ
    - Dependent deduction: $1,000 per dependent
    - Full exemption of Social Security
    - $2,000 pension income deduction
    - MA EITC (40% of federal, refundable)
    - No-tax status for very low income
    - Rental deduction (up to $4,000)
    """

    def __init__(self):
        super().__init__(get_massachusetts_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Massachusetts state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Massachusetts additions
        additions = self.calculate_state_additions(tax_return)

        # Massachusetts deductions (different from subtractions)
        subtractions = self.calculate_state_subtractions(tax_return)

        # Massachusetts gross income
        ma_gross_income = federal_agi + additions - subtractions

        # Personal exemption
        personal_exemption = self.config.get_personal_exemption(filing_status)

        # Dependent deduction
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        dependent_deduction = dependent_exemptions * self.config.dependent_exemption_amount

        # Other deductions
        other_deductions = self._calculate_ma_deductions(tax_return, filing_status)

        # Total exemptions/deductions
        exemption_amount = personal_exemption + dependent_deduction

        # Massachusetts taxable income
        ma_taxable_income = max(
            0.0,
            ma_gross_income - exemption_amount - other_deductions
        )

        # Check no-tax status
        if self._qualifies_for_no_tax_status(ma_gross_income, filing_status, dependent_exemptions):
            tax_before_credits = 0.0
        else:
            # Calculate base tax (5%)
            tax_before_credits = self.calculate_brackets(ma_taxable_income, filing_status)

            # Add millionaire surtax (4% on income over $1M)
            if ma_taxable_income > 1000000:
                surtax = (ma_taxable_income - 1000000) * 0.04
                tax_before_credits += surtax

        # State credits
        credits = {}

        # Massachusetts EITC (40% of federal, refundable)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        ma_eitc = self.calculate_state_eitc(federal_eitc)
        if ma_eitc > 0:
            credits["ma_eitc"] = ma_eitc

        # Senior Circuit Breaker Credit (property tax relief for seniors)
        circuit_breaker = self._calculate_circuit_breaker_credit(
            tax_return, ma_gross_income, filing_status
        )
        if circuit_breaker > 0:
            credits["circuit_breaker_credit"] = circuit_breaker

        # Limited Income Credit
        limited_income_credit = self._calculate_limited_income_credit(
            ma_gross_income, filing_status
        )
        if limited_income_credit > 0:
            credits["limited_income_credit"] = limited_income_credit

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
            state_adjusted_income=ma_gross_income,
            state_standard_deduction=0.0,
            state_itemized_deductions=other_deductions,
            deduction_used="exemption_based",
            deduction_amount=other_deductions,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=ma_taxable_income,
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
        Calculate Massachusetts income subtractions.

        MA exempts:
        - Social Security benefits
        - Pension income (up to $2,000)
        - Military pay
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Pension income deduction (up to $2,000)
        if tax_return.income.retirement_income > 0:
            pension_deduction = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 2000
            )
            subtractions += pension_deduction

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Massachusetts income additions."""
        additions = 0.0
        return additions

    def _calculate_ma_deductions(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """
        Calculate Massachusetts-specific deductions.

        Includes:
        - Rental deduction (up to $4,000)
        - Commuter deduction
        - Student loan interest
        """
        deductions = 0.0

        # Rental deduction (50% of rent paid, up to $4,000)
        # Would need rent information - simplified
        # For now, assume standard amount if no home ownership
        if hasattr(tax_return.deductions, 'itemized'):
            if tax_return.deductions.itemized.real_estate_tax == 0:
                # Likely a renter - estimate deduction
                deductions += 2000  # Average estimate

        return deductions

    def _qualifies_for_no_tax_status(
        self,
        ma_gross_income: float,
        filing_status: str,
        num_dependents: int
    ) -> bool:
        """
        Check if taxpayer qualifies for no-tax status.

        MA has specific income thresholds below which no tax is owed.
        """
        # 2025 no-tax status thresholds (estimates)
        base_threshold = 8000 if filing_status == "single" else 16000
        threshold = base_threshold + (num_dependents * 1700)
        return ma_gross_income <= threshold

    def _calculate_circuit_breaker_credit(
        self,
        tax_return: "TaxReturn",
        ma_income: float,
        filing_status: str
    ) -> float:
        """
        Calculate Senior Circuit Breaker Credit.

        Property tax relief for seniors 65+ with limited income.
        """
        # Simplified: would need age and property tax info
        if hasattr(tax_return.deductions, 'itemized'):
            property_tax = tax_return.deductions.itemized.real_estate_tax
            if property_tax > 0 and ma_income < 68000:
                # Assume taxpayer is 65+ if has retirement income
                if tax_return.income.retirement_income > 0:
                    # Credit = property tax above 10% of income, up to $1,360
                    threshold = ma_income * 0.10
                    excess = max(0, property_tax - threshold)
                    return min(1360, excess)
        return 0.0

    def _calculate_limited_income_credit(
        self,
        ma_income: float,
        filing_status: str
    ) -> float:
        """
        Calculate Limited Income Credit.

        Credit for taxpayers with income below certain threshold.
        """
        # Threshold based on filing status
        threshold = 15000 if filing_status == "single" else 30000

        if ma_income > threshold:
            return 0.0

        # Credit phases in based on income
        return 0.0  # Simplified - full calculation complex

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for MA EITC calculation."""
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
