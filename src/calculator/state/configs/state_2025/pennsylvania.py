"""Pennsylvania state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_pennsylvania_config() -> StateTaxConfig:
    """Create Pennsylvania tax configuration for 2025."""
    return StateTaxConfig(
        state_code="PA",
        state_name="Pennsylvania",
        tax_year=2025,
        is_flat_tax=True,
        flat_rate=0.0307,  # 3.07% flat rate
        brackets=None,
        starts_from="gross_income",  # PA uses its own definition of taxable income
        standard_deduction={
            # PA has no standard deduction
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        personal_exemption_amount={
            # PA has no personal exemptions
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        dependent_exemption_amount=0,
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # PA exempts Social Security
        pension_exclusion_limit=None,  # PA exempts all retirement income
        military_pay_exempt=True,  # PA exempts military pay
        eitc_percentage=0.25,  # PA EITC is 25% of federal (for qualifying workers)
        child_tax_credit_amount=0,
        has_local_tax=True,  # PA has local earned income tax (varies by municipality)
    )


@register_state("PA", 2025)
class PennsylvaniaCalculator(BaseStateCalculator):
    """
    Pennsylvania state tax calculator.

    Pennsylvania has a unique tax system:
    - Flat 3.07% tax rate (one of lowest state income taxes)
    - No standard deduction or personal exemptions
    - Uses 8 classes of income with specific rules for each
    - Full exemption of Social Security, pensions, and retirement income
    - Full exemption of military pay
    - Local earned income tax (EIT) varies by municipality (typically 1-3%)
    - PA EITC is 25% of federal (for qualifying workers with children)
    """

    def __init__(self):
        super().__init__(get_pennsylvania_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Pennsylvania state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Federal values for reference
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Pennsylvania calculates from gross income with specific exclusions
        # Start with compensation (wages, salaries)
        pa_compensation = tax_return.income.get_total_wages()

        # Add other PA taxable income classes
        # Class 2: Net profits from business
        net_business_income = (
            tax_return.income.self_employment_income -
            tax_return.income.self_employment_expenses
        )
        if net_business_income < 0:
            net_business_income = 0  # Losses don't offset in PA

        # Class 3: Interest (taxable in PA)
        interest_income = tax_return.income.interest_income

        # Class 4: Dividends (taxable in PA)
        # dividend_income includes both qualified and ordinary dividends
        dividend_income = tax_return.income.dividend_income

        # Class 5: Net gains from property (simplified)
        # Note: Losses don't offset gains in PA
        capital_gains = max(0, tax_return.income.short_term_capital_gains + tax_return.income.long_term_capital_gains)

        # Class 6: Rents/royalties (simplified)
        rental_income = max(0, tax_return.income.rental_income)

        # Class 7: Estate/trust income (not tracked separately in model)
        # Class 8: Gambling winnings (not tracked separately in model)

        # PA additions (income that's tax-exempt federally but taxable in PA)
        additions = self.calculate_state_additions(tax_return)

        # PA subtractions (income that's taxable federally but exempt in PA)
        subtractions = self.calculate_state_subtractions(tax_return)

        # PA taxable income
        pa_gross_income = (
            pa_compensation +
            net_business_income +
            interest_income +
            dividend_income +
            capital_gains +
            rental_income +
            additions -
            subtractions
        )

        # PA has no deductions or exemptions
        std_deduction = 0.0
        itemized = 0.0
        deduction_used = "none"
        deduction_amount = 0.0
        exemption_amount = 0.0

        pa_taxable_income = max(0.0, pa_gross_income)

        # Calculate tax at flat rate
        tax_before_credits = self.calculate_brackets(pa_taxable_income, filing_status)

        # State credits
        credits = {}

        # PA Tax Forgiveness (for low-income taxpayers)
        tax_forgiveness = self._calculate_tax_forgiveness(
            tax_return, filing_status, pa_taxable_income
        )
        if tax_forgiveness > 0:
            credits["tax_forgiveness"] = tax_forgiveness

        # PA EITC (25% of federal for those with children)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        pa_eitc = self.calculate_state_eitc(federal_eitc)
        if pa_eitc > 0 and len(tax_return.taxpayer.dependents) > 0:
            credits["pa_eitc"] = pa_eitc

        total_credits = sum(credits.values())

        # Net state tax
        state_tax_liability = max(0.0, tax_before_credits - total_credits)

        # Local earned income tax (simplified - using 1% as average)
        # Actual rate depends on municipality
        local_tax = pa_compensation * 0.01 if self.config.has_local_tax else 0.0

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
            state_adjusted_income=pa_gross_income,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=0,
            dependent_exemptions=0,
            exemption_amount=exemption_amount,
            state_taxable_income=pa_taxable_income,
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
        Calculate Pennsylvania income subtractions.

        Pennsylvania exempts:
        - Social Security benefits
        - Railroad retirement benefits
        - Pension and retirement income
        - Military pay
        - Unemployment compensation (unique to PA)
        """
        subtractions = 0.0

        # Social Security is fully exempt
        subtractions += tax_return.income.taxable_social_security

        # Retirement income is fully exempt
        subtractions += tax_return.income.retirement_income

        # Unemployment is exempt in PA (but taxable federally)
        subtractions += tax_return.income.unemployment_compensation

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """
        Calculate Pennsylvania income additions.

        Additions include items that are tax-exempt federally
        but taxable in PA. Most common additions are minimal.
        """
        additions = 0.0
        # Most additions would require additional tracking
        return additions

    def _calculate_tax_forgiveness(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        pa_taxable_income: float
    ) -> float:
        """
        Calculate Pennsylvania Tax Forgiveness credit.

        PA provides 100% tax forgiveness for very low income
        and partial forgiveness up to certain thresholds.
        """
        dependents = len(tax_return.taxpayer.dependents)

        # 2025 eligibility income limits (estimates)
        # Poverty level + $6,500 per dependent
        base_limit = 6500
        if filing_status in ("married_joint", "qualifying_widow"):
            base_limit = 13000

        eligibility_income = base_limit + (dependents * 9500)

        if pa_taxable_income <= eligibility_income:
            # 100% forgiveness
            return pa_taxable_income * self.config.flat_rate

        # Partial forgiveness phases out
        phase_out_limit = eligibility_income * 2.5
        if pa_taxable_income >= phase_out_limit:
            return 0.0

        # Calculate partial forgiveness
        forgiveness_pct = 1.0 - ((pa_taxable_income - eligibility_income) /
                                  (phase_out_limit - eligibility_income))
        tax_before = pa_taxable_income * self.config.flat_rate
        return round(tax_before * forgiveness_pct, 2)

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for PA EITC calculation."""
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
