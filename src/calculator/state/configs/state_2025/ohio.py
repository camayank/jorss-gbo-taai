"""Ohio state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_ohio_config() -> StateTaxConfig:
    """Create Ohio tax configuration for 2025."""
    return StateTaxConfig(
        state_code="OH",
        state_name="Ohio",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Ohio 2025 brackets (reduced to 3 brackets after 2024 reform)
            # First $26,050 is now exempt (0% bracket)
            "single": [
                (0, 0.0),           # 0% on first $26,050
                (26050, 0.02765),   # 2.765% on $26,050 - $100,000
                (100000, 0.0375),   # 3.75% on over $100,000
            ],
            "married_joint": [
                (0, 0.0),
                (26050, 0.02765),
                (100000, 0.0375),
            ],
            "married_separate": [
                (0, 0.0),
                (26050, 0.02765),
                (100000, 0.0375),
            ],
            "head_of_household": [
                (0, 0.0),
                (26050, 0.02765),
                (100000, 0.0375),
            ],
            "qualifying_widow": [
                (0, 0.0),
                (26050, 0.02765),
                (100000, 0.0375),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            # Ohio has no standard deduction (uses exemptions and credits)
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        personal_exemption_amount={
            # Ohio personal exemption credits (2025)
            # $2,400 per exemption for income under $40,000
            "single": 2400,
            "married_joint": 2400,
            "married_separate": 2400,
            "head_of_household": 2400,
            "qualifying_widow": 2400,
        },
        dependent_exemption_amount=2400,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # Ohio exempts Social Security
        pension_exclusion_limit=None,  # Ohio has retirement income credit
        military_pay_exempt=True,
        eitc_percentage=0.30,  # Ohio EITC is 30% of federal
        child_tax_credit_amount=0,
        has_local_tax=True,  # Ohio municipalities have their own income taxes
    )


@register_state("OH", 2025)
class OhioCalculator(BaseStateCalculator):
    """
    Ohio state tax calculator.

    Ohio has:
    - Progressive brackets (now only 3 after 2024 reform)
    - 0% rate on first $26,050 (effective exemption)
    - Top rate of 3.75% on income over $100,000
    - Personal exemption credit of $2,400 (phases out at higher income)
    - Ohio EITC (30% of federal, nonrefundable)
    - School district taxes (separate, not included here)
    - Local/municipal income taxes (most cities: 1-3%)
    - Full exemption of Social Security
    - Retirement Income Credit
    """

    def __init__(self):
        super().__init__(get_ohio_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Ohio state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Ohio additions
        additions = self.calculate_state_additions(tax_return)

        # Ohio subtractions/deductions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Ohio adjusted gross income
        ohio_agi = federal_agi + additions - subtractions

        # Ohio has no standard/itemized deduction choice
        std_deduction = 0.0
        itemized = 0.0
        deduction_used = "none"
        deduction_amount = 0.0

        # Ohio taxable income
        ohio_taxable_income = max(0.0, ohio_agi)

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(ohio_taxable_income, filing_status)

        # Personal exemption credit (phases out above $100,000)
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2

        dependent_exemptions = len(tax_return.taxpayer.dependents)
        total_exemptions = personal_exemptions + dependent_exemptions

        exemption_credit = self._calculate_exemption_credit(
            total_exemptions, ohio_agi
        )

        # State credits
        credits = {}

        if exemption_credit > 0:
            credits["personal_exemption_credit"] = exemption_credit

        # Ohio EITC (30% of federal, nonrefundable)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        ohio_eitc = self.calculate_state_eitc(federal_eitc)
        if ohio_eitc > 0:
            # Nonrefundable - can't exceed tax liability
            credits["ohio_eitc"] = min(ohio_eitc, tax_before_credits)

        # Retirement income credit
        retirement_credit = self._calculate_retirement_income_credit(
            tax_return, ohio_agi
        )
        if retirement_credit > 0:
            credits["retirement_income_credit"] = retirement_credit

        # Child care credit (if applicable)
        child_care_credit = self._calculate_child_care_credit(tax_return, ohio_agi)
        if child_care_credit > 0:
            credits["child_care_credit"] = child_care_credit

        total_credits = sum(credits.values())

        # Net state tax
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # Local tax (simplified: using 2% average for major Ohio cities)
        earned_income = tax_return.income.get_total_wages()
        local_tax = earned_income * 0.02 if self.config.has_local_tax else 0.0

        # State withholding
        state_withholding = self.get_state_withholding(tax_return)

        # Refund or owed
        state_refund_or_owed = state_withholding - state_tax_liability

        exemption_amount = exemption_credit  # Using credit amount as equivalent

        return StateCalculationBreakdown(
            state_code=self.config.state_code,
            state_name=self.config.state_name,
            tax_year=self.config.tax_year,
            filing_status=filing_status,
            federal_agi=federal_agi,
            federal_taxable_income=federal_taxable_income,
            state_additions=additions,
            state_subtractions=subtractions,
            state_adjusted_income=ohio_agi,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=ohio_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)),
            state_credits=credits,
            total_state_credits=float(money(total_credits)),
            local_tax=float(money(local_tax)),
            state_tax_liability=float(money(state_tax_liability)),
            state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_refund_or_owed)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Ohio income subtractions.

        Ohio allows:
        - Social Security (fully exempt)
        - Interest on Ohio/US obligations
        - Federal interest/dividend income on Ohio obligations
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Ohio income additions."""
        additions = 0.0
        return additions

    def _calculate_exemption_credit(
        self,
        num_exemptions: int,
        ohio_agi: float
    ) -> float:
        """
        Calculate Ohio personal exemption credit.

        Credit phases out for income over $40,000.
        """
        if num_exemptions == 0:
            return 0.0

        # Base credit per exemption
        base_credit = 2400

        # Phase out for higher income
        if ohio_agi <= 40000:
            return num_exemptions * base_credit
        elif ohio_agi <= 80000:
            # Reduced credit
            return num_exemptions * 1900
        else:
            # Minimal credit for high income
            return num_exemptions * 1200

    def _calculate_retirement_income_credit(
        self,
        tax_return: "TaxReturn",
        ohio_agi: float
    ) -> float:
        """
        Calculate Ohio Retirement Income Credit.

        Credit based on retirement income for those 65+.
        """
        retirement_income = tax_return.income.retirement_income
        if retirement_income <= 0:
            return 0.0

        # Simplified: credit of up to $200 based on income
        # In reality, based on age and amount
        if ohio_agi <= 100000:
            credit = min(200, retirement_income * 0.05)
            return float(money(credit))
        return 0.0

    def _calculate_child_care_credit(
        self,
        tax_return: "TaxReturn",
        ohio_agi: float
    ) -> float:
        """
        Calculate Ohio child care credit.

        Credit based on federal child care credit.
        """
        # Simplified: 25% of federal child care credit if income under $40,000
        if ohio_agi > 40000:
            return 0.0

        # Would need federal child care credit amount
        # For now, estimate based on dependents
        num_children = len(tax_return.taxpayer.dependents)
        if num_children > 0:
            return min(500, num_children * 100)
        return 0.0

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for Ohio EITC calculation."""
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
