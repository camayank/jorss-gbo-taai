"""Virginia state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_virginia_config() -> StateTaxConfig:
    """Create Virginia tax configuration for 2025."""
    return StateTaxConfig(
        state_code="VA",
        state_name="Virginia",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Virginia 2025 brackets (4 brackets, not indexed)
            "single": [
                (0, 0.02),        # 2% on first $3,000
                (3000, 0.03),     # 3% on $3,000 - $5,000
                (5000, 0.05),     # 5% on $5,000 - $17,000
                (17000, 0.0575),  # 5.75% on over $17,000
            ],
            "married_joint": [
                (0, 0.02),
                (3000, 0.03),
                (5000, 0.05),
                (17000, 0.0575),
            ],
            "married_separate": [
                (0, 0.02),
                (3000, 0.03),
                (5000, 0.05),
                (17000, 0.0575),
            ],
            "head_of_household": [
                (0, 0.02),
                (3000, 0.03),
                (5000, 0.05),
                (17000, 0.0575),
            ],
            "qualifying_widow": [
                (0, 0.02),
                (3000, 0.03),
                (5000, 0.05),
                (17000, 0.0575),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # Virginia standard deductions for 2025
            "single": 8500,
            "married_joint": 17000,
            "married_separate": 8500,
            "head_of_household": 8500,
            "qualifying_widow": 17000,
        },
        personal_exemption_amount={
            # Virginia personal exemption
            "single": 930,
            "married_joint": 930,  # Per person
            "married_separate": 930,
            "head_of_household": 930,
            "qualifying_widow": 930,
        },
        dependent_exemption_amount=930,  # Per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # VA exempts Social Security
        pension_exclusion_limit=None,  # VA has age deduction instead
        military_pay_exempt=False,  # VA has partial military income subtraction
        eitc_percentage=0.20,  # VA EITC is 20% of federal
        child_tax_credit_amount=0,
        has_local_tax=False,  # VA has no local income tax
    )


@register_state("VA", 2025)
class VirginiaCalculator(BaseStateCalculator):
    """
    Virginia state tax calculator.

    Virginia has:
    - 4 progressive tax brackets (top rate 5.75%)
    - Standard deduction: $8,500 single, $17,000 MFJ
    - Personal exemption: $930 per person
    - Dependent exemption: $930 per dependent
    - Full exemption of Social Security
    - Age deduction ($12,000 for 65+)
    - Virginia EITC (20% of federal, refundable)
    - No local income tax
    """

    def __init__(self):
        super().__init__(get_virginia_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Virginia state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Virginia additions
        additions = self.calculate_state_additions(tax_return)

        # Virginia subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Virginia adjusted gross income
        va_agi = federal_agi + additions - subtractions

        # Standard deduction
        std_deduction = self.config.get_standard_deduction(filing_status)

        # Virginia itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(va_agi)

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

        # Virginia taxable income
        va_taxable_income = max(
            0.0,
            va_agi - deduction_amount - exemption_amount
        )

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(va_taxable_income, filing_status)

        # State credits
        credits = {}

        # Virginia EITC (20% of federal, refundable)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        va_eitc = self.calculate_state_eitc(federal_eitc)
        if va_eitc > 0:
            credits["va_eitc"] = va_eitc

        # Low-Income Credit (for very low income, against tax only)
        low_income_credit = self._calculate_low_income_credit(
            tax_return, va_taxable_income, filing_status
        )
        if low_income_credit > 0:
            credits["low_income_credit"] = low_income_credit

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
            state_adjusted_income=va_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=va_taxable_income,
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
        Calculate Virginia income subtractions.

        Virginia exempts/deducts:
        - Social Security benefits (fully exempt)
        - Age deduction ($12,000 for age 65+)
        - Military income subtraction (up to $15,000)
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Age deduction (simplified: assume taxpayer is 65+)
        # In reality, would need age information
        # For now, assume they qualify if they have retirement income
        if tax_return.income.retirement_income > 0:
            subtractions += 12000  # Max age deduction

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Virginia income additions."""
        additions = 0.0
        return additions

    def _calculate_low_income_credit(
        self,
        tax_return: "TaxReturn",
        va_taxable_income: float,
        filing_status: str
    ) -> float:
        """
        Calculate Virginia Low-Income Credit.

        Credit available for very low income taxpayers.
        """
        # Income threshold
        threshold = 15000 if filing_status == "single" else 30000

        if va_taxable_income > threshold:
            return 0.0

        # Credit reduces tax liability for very low income
        if va_taxable_income <= 0:
            return 0.0

        # Calculate potential credit (simplified)
        tax_rate = 0.0575  # Top rate
        potential_credit = va_taxable_income * tax_rate * 0.2
        return round(potential_credit, 2)

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for VA EITC calculation."""
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
