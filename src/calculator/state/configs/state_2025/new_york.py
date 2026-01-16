"""New York state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_new_york_config() -> StateTaxConfig:
    """Create New York tax configuration for 2025."""
    return StateTaxConfig(
        state_code="NY",
        state_name="New York",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # New York has 8 brackets (2025 inflation-adjusted estimates)
            "single": [
                (0, 0.04),          # 4% on first $8,500
                (8500, 0.045),      # 4.5% on $8,500 - $11,700
                (11700, 0.0525),    # 5.25% on $11,700 - $13,900
                (13900, 0.0585),    # 5.85% on $13,900 - $80,650
                (80650, 0.0625),    # 6.25% on $80,650 - $215,400
                (215400, 0.0685),   # 6.85% on $215,400 - $1,077,550
                (1077550, 0.0965),  # 9.65% on $1,077,550 - $5,000,000
                (5000000, 0.103),   # 10.3% on $5M - $25M
                (25000000, 0.109),  # 10.9% on over $25M
            ],
            "married_joint": [
                (0, 0.04),
                (17150, 0.045),
                (23600, 0.0525),
                (27900, 0.0585),
                (161550, 0.0625),
                (323200, 0.0685),
                (2155350, 0.0965),
                (5000000, 0.103),
                (25000000, 0.109),
            ],
            "married_separate": [
                (0, 0.04),
                (8500, 0.045),
                (11700, 0.0525),
                (13900, 0.0585),
                (80650, 0.0625),
                (215400, 0.0685),
                (1077550, 0.0965),
                (5000000, 0.103),
                (25000000, 0.109),
            ],
            "head_of_household": [
                (0, 0.04),
                (12800, 0.045),
                (17650, 0.0525),
                (20900, 0.0585),
                (107650, 0.0625),
                (269300, 0.0685),
                (1616450, 0.0965),
                (5000000, 0.103),
                (25000000, 0.109),
            ],
            "qualifying_widow": [
                (0, 0.04),
                (17150, 0.045),
                (23600, 0.0525),
                (27900, 0.0585),
                (161550, 0.0625),
                (323200, 0.0685),
                (2155350, 0.0965),
                (5000000, 0.103),
                (25000000, 0.109),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            "single": 8000,
            "married_joint": 16050,
            "married_separate": 8000,
            "head_of_household": 11200,
            "qualifying_widow": 16050,
        },
        personal_exemption_amount={
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        dependent_exemption_amount=1000,  # Dependent exemption
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # NY exempts Social Security
        pension_exclusion_limit=20000,  # NY excludes up to $20,000 of pension income
        military_pay_exempt=True,  # NY exempts military pay
        eitc_percentage=0.30,  # NY EITC is 30% of federal
        child_tax_credit_amount=330,  # Empire State Child Credit
        has_local_tax=True,  # NYC has additional tax
        local_tax_brackets={
            # NYC resident tax (simplified - actual has more brackets)
            "single": [
                (0, 0.03078),
                (12000, 0.03762),
                (25000, 0.03819),
                (50000, 0.03876),
            ],
            "married_joint": [
                (0, 0.03078),
                (21600, 0.03762),
                (45000, 0.03819),
                (90000, 0.03876),
            ],
            "married_separate": [
                (0, 0.03078),
                (12000, 0.03762),
                (25000, 0.03819),
                (50000, 0.03876),
            ],
            "head_of_household": [
                (0, 0.03078),
                (14400, 0.03762),
                (30000, 0.03819),
                (60000, 0.03876),
            ],
            "qualifying_widow": [
                (0, 0.03078),
                (21600, 0.03762),
                (45000, 0.03819),
                (90000, 0.03876),
            ],
        },
    )


@register_state("NY", 2025)
class NewYorkCalculator(BaseStateCalculator):
    """
    New York state tax calculator.

    New York has:
    - 8 progressive tax brackets (up to 10.9% top rate)
    - NYC additional resident tax (up to ~3.9%)
    - NY EITC (30% of federal)
    - Empire State Child Credit ($330 per child)
    - $20,000 pension income exclusion
    - Social Security exemption
    - Military pay exemption
    """

    def __init__(self):
        super().__init__(get_new_york_config())
        self._is_nyc_resident = False  # Would be determined from address

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate New York state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Check if NYC resident (simplified - based on city field)
        self._is_nyc_resident = self._check_nyc_residency(tax_return)

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # New York additions
        additions = self.calculate_state_additions(tax_return)

        # New York subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # New York adjusted income
        ny_adjusted_income = federal_agi + additions - subtractions

        # Deductions
        std_deduction = self.config.get_standard_deduction(filing_status)

        # NY itemized deductions
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(ny_adjusted_income)

        if tax_return.deductions.use_standard_deduction:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        # Dependent exemption
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        dependent_exemption_total = dependent_exemptions * self.config.dependent_exemption_amount

        # NY taxable income
        ny_taxable_income = max(0.0, ny_adjusted_income - deduction_amount - dependent_exemption_total)

        # Calculate state tax using brackets
        tax_before_credits = self.calculate_brackets(ny_taxable_income, filing_status)

        # NYC local tax if NYC resident
        local_tax = 0.0
        if self._is_nyc_resident:
            local_tax = self.calculate_local_tax(ny_taxable_income, filing_status)

        # State credits
        credits = {}

        # NY EITC
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        ny_eitc = self.calculate_state_eitc(federal_eitc)
        if ny_eitc > 0:
            credits["ny_eitc"] = ny_eitc

        # Empire State Child Credit
        child_credit = self.calculate_state_child_tax_credit(
            dependent_exemptions,
            ny_adjusted_income
        )
        if child_credit > 0:
            credits["empire_state_child_credit"] = child_credit

        total_credits = sum(credits.values())

        # Net state tax (state + local - credits)
        total_state_tax = tax_before_credits + local_tax
        state_tax_liability = max(0.0, total_state_tax - total_credits)

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
            state_adjusted_income=ny_adjusted_income,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=1 if filing_status != "married_joint" else 2,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=dependent_exemption_total,
            state_taxable_income=ny_taxable_income,
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
        Calculate New York income subtractions.

        Subtractions include:
        - Social Security benefits (fully exempt)
        - Pension income exclusion (up to $20,000)
        - Military pay
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Pension exclusion (up to $20,000 for those 59.5+)
        # Simplified: assume taxpayer qualifies if has retirement income
        if tax_return.income.retirement_income > 0:
            pension_exclusion = min(
                tax_return.income.retirement_income,
                self.config.pension_exclusion_limit or 20000
            )
            subtractions += pension_exclusion

        return subtractions

    def calculate_state_child_tax_credit(
        self,
        num_children: int,
        ny_agi: float
    ) -> float:
        """
        Calculate Empire State Child Credit.

        $330 per qualifying child, with income phaseout.
        """
        if num_children == 0:
            return 0.0

        # Basic credit amount
        credit = num_children * self.config.child_tax_credit_amount

        # Income phaseout (simplified)
        # Full credit phases out at higher incomes
        if ny_agi > 110000:
            reduction = (ny_agi - 110000) * 0.02
            credit = max(0, credit - reduction)

        return round(credit, 2)

    def _check_nyc_residency(self, tax_return: "TaxReturn") -> bool:
        """
        Check if taxpayer is NYC resident.

        Based on city field in taxpayer info.
        """
        city = tax_return.taxpayer.city
        if city:
            nyc_names = ["new york", "new york city", "nyc", "manhattan", "brooklyn",
                        "queens", "bronx", "staten island"]
            return city.lower().strip() in nyc_names
        return False

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for NY EITC calculation."""
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
