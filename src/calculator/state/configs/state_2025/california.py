"""California state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_california_config() -> StateTaxConfig:
    """Create California tax configuration for 2025."""
    return StateTaxConfig(
        state_code="CA",
        state_name="California",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # California has 9 brackets (2025 inflation-adjusted estimates)
            "single": [
                (0, 0.01),         # 1% on first $10,412
                (10412, 0.02),     # 2% on $10,412 - $24,684
                (24684, 0.04),     # 4% on $24,684 - $38,959
                (38959, 0.06),     # 6% on $38,959 - $54,081
                (54081, 0.08),     # 8% on $54,081 - $68,350
                (68350, 0.093),    # 9.3% on $68,350 - $349,137
                (349137, 0.103),   # 10.3% on $349,137 - $418,961
                (418961, 0.113),   # 11.3% on $418,961 - $698,271
                (698271, 0.123),   # 12.3% on over $698,271
            ],
            "married_joint": [
                (0, 0.01),
                (20824, 0.02),
                (49368, 0.04),
                (77918, 0.06),
                (108162, 0.08),
                (136700, 0.093),
                (698274, 0.103),
                (837922, 0.113),
                (1396542, 0.123),
            ],
            "married_separate": [
                (0, 0.01),
                (10412, 0.02),
                (24684, 0.04),
                (38959, 0.06),
                (54081, 0.08),
                (68350, 0.093),
                (349137, 0.103),
                (418961, 0.113),
                (698271, 0.123),
            ],
            "head_of_household": [
                (0, 0.01),
                (20839, 0.02),
                (49371, 0.04),
                (63644, 0.06),
                (78796, 0.08),
                (93065, 0.093),
                (474824, 0.103),
                (569790, 0.113),
                (949649, 0.123),
            ],
            "qualifying_widow": [
                (0, 0.01),
                (20824, 0.02),
                (49368, 0.04),
                (77918, 0.06),
                (108162, 0.08),
                (136700, 0.093),
                (698274, 0.103),
                (837922, 0.113),
                (1396542, 0.123),
            ],
        },
        starts_from="federal_agi",
        standard_deduction={
            "single": 5363,
            "married_joint": 10726,
            "married_separate": 5363,
            "head_of_household": 10726,
            "qualifying_widow": 10726,
        },
        # California uses exemption credits, not deductions
        # These are the credit amounts per exemption
        personal_exemption_amount={
            "single": 144,  # Credit per personal exemption
            "married_joint": 144,
            "married_separate": 144,
            "head_of_household": 144,
            "qualifying_widow": 144,
        },
        dependent_exemption_amount=446,  # Credit per dependent
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # CA fully exempts SS
        pension_exclusion_limit=None,  # No general pension exclusion
        military_pay_exempt=False,
        eitc_percentage=0.45,  # CalEITC is 45% of federal (for low income)
        child_tax_credit_amount=0,  # No general state CTC
        has_local_tax=False,
        renter_credit_single=60,
        renter_credit_joint=120,
        renter_credit_income_limit=50746,  # Single income limit for renter credit
    )


@register_state("CA", 2025)
class CaliforniaCalculator(BaseStateCalculator):
    """
    California state tax calculator.

    California has one of the most complex state tax systems with:
    - 9 progressive tax brackets (highest top rate in US at 12.3%)
    - Additional 1% mental health tax on income over $1M
    - CalEITC (California Earned Income Tax Credit)
    - Renter's Credit for low/moderate income
    - Full exemption of Social Security benefits
    - Uses exemption credits instead of deductions
    """

    def __init__(self):
        super().__init__(get_california_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate California state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Start from federal AGI
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # California additions (income added back)
        additions = self.calculate_state_additions(tax_return)

        # California subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # California adjusted income
        ca_adjusted_income = federal_agi + additions - subtractions

        # Deductions
        std_deduction = self.config.get_standard_deduction(filing_status)

        # California itemized deductions (similar to federal but with modifications)
        # For simplicity, use federal itemized amount
        itemized = 0.0
        if hasattr(tax_return.deductions, 'itemized'):
            itemized = tax_return.deductions.itemized.get_total_itemized(ca_adjusted_income)

        # Use same choice as federal (or choose higher)
        if tax_return.deductions.use_standard_deduction:
            deduction_used = "standard"
            deduction_amount = std_deduction
        else:
            deduction_used = "itemized"
            deduction_amount = itemized

        # Taxable income before exemptions
        ca_taxable_income = max(0.0, ca_adjusted_income - deduction_amount)

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(ca_taxable_income, filing_status)

        # Mental health tax: additional 1% on income over $1M
        if ca_taxable_income > 1000000:
            mental_health_tax = (ca_taxable_income - 1000000) * 0.01
            tax_before_credits += mental_health_tax

        # Exemption credits (California uses credits, not deductions)
        personal_exemptions = 1
        if filing_status in ("married_joint", "qualifying_widow"):
            personal_exemptions = 2
        dependent_exemptions = len(tax_return.taxpayer.dependents)

        personal_credit = personal_exemptions * self.config.get_personal_exemption(filing_status)
        dependent_credit = dependent_exemptions * self.config.dependent_exemption_amount
        exemption_amount = personal_credit + dependent_credit

        # State credits
        credits = {}

        # CalEITC - for very low income earners
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        cal_eitc = self.calculate_state_eitc(federal_eitc)
        if cal_eitc > 0:
            credits["caleitc"] = cal_eitc

        # Exemption credits
        if exemption_amount > 0:
            credits["exemption_credits"] = exemption_amount

        # Renter's credit (low income only)
        renters_credit = self._calculate_renters_credit(tax_return, filing_status, ca_adjusted_income)
        if renters_credit > 0:
            credits["renters_credit"] = renters_credit

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
            state_adjusted_income=ca_adjusted_income,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=exemption_amount,
            state_taxable_income=ca_taxable_income,
            state_tax_before_credits=float(money(tax_before_credits)),
            state_credits=credits,
            total_state_credits=float(money(total_credits)),
            local_tax=0.0,
            state_tax_liability=float(money(state_tax_liability)),
            state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_refund_or_owed)),
        )

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate California income additions.

        Additions include:
        - Interest from other states' municipal bonds
        - HSA contributions (CA doesn't follow federal treatment)
        - Other federally deducted items CA doesn't allow
        """
        additions = 0.0

        # HSA contributions are not deductible in CA
        if hasattr(tax_return.deductions, 'hsa_contributions'):
            additions += tax_return.deductions.hsa_contributions

        return additions

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate California income subtractions.

        Subtractions include:
        - Social Security benefits (fully exempt)
        - California lottery winnings
        """
        subtractions = 0.0

        # Social Security is fully exempt in California
        subtractions += tax_return.income.taxable_social_security

        return subtractions

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for CalEITC calculation."""
        earned_income = (
            tax_return.income.get_total_wages() +
            tax_return.income.self_employment_income -
            tax_return.income.self_employment_expenses
        )
        agi = tax_return.adjusted_gross_income or 0.0
        num_children = len(tax_return.taxpayer.dependents)

        # Use the credits model's EITC calculation if available
        return tax_return.credits.calculate_eitc(
            earned_income,
            agi,
            filing_status,
            num_children
        )

    def _calculate_renters_credit(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        ca_agi: float
    ) -> float:
        """
        Calculate California Renter's Credit.

        Available to CA residents who rent their principal residence
        and meet income limits.
        """
        # Income limits for renter's credit (2025 estimates)
        if filing_status in ("married_joint", "qualifying_widow"):
            income_limit = 101492
            credit_amount = self.config.renter_credit_joint
        else:
            income_limit = 50746
            credit_amount = self.config.renter_credit_single

        # Must be under income limit
        if ca_agi > income_limit:
            return 0.0

        # For now, return credit amount if income qualifies
        # In reality, would need to know if taxpayer rents
        # This is a simplification - could be enhanced with rent info
        return credit_amount
