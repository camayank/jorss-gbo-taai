"""Utah state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_utah_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="UT", state_name="Utah", tax_year=2025, is_flat_tax=True,
        flat_rate=0.0465,  # 4.65% flat rate
        brackets=None, starts_from="federal_agi",
        standard_deduction={"single": 0, "married_joint": 0, "married_separate": 0,
                           "head_of_household": 0, "qualifying_widow": 0},
        personal_exemption_amount={"single": 0, "married_joint": 0, "married_separate": 0,
                                   "head_of_household": 0, "qualifying_widow": 0},
        dependent_exemption_amount=0, allows_federal_tax_deduction=False, social_security_taxable=False,
        pension_exclusion_limit=None, military_pay_exempt=True, eitc_percentage=0.20,
        child_tax_credit_amount=0, has_local_tax=False,
        # Utah uses taxpayer credit system instead of deductions
    )


@register_state("UT", 2025)
class UtahCalculator(BaseStateCalculator):
    """Utah - flat 4.65% rate with taxpayer credit system."""

    def __init__(self):
        super().__init__(get_utah_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        ut_agi = federal_agi + additions - subtractions

        # Utah has no deductions - uses credit system
        ut_taxable_income = max(0.0, ut_agi)
        tax_before_credits = self.calculate_brackets(ut_taxable_income, filing_status)

        credits = {}

        # Utah Taxpayer Tax Credit (6% of federal deductions and exemptions)
        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        federal_std_ded = 15750 if filing_status not in ("married_joint", "qualifying_widow") else 31500

        taxpayer_credit = (federal_std_ded + ((personal_exemptions + dependent_exemptions) * 4150)) * 0.06
        # Credit phases out at higher income
        if ut_agi > 15548:
            reduction = (ut_agi - 15548) * 0.013
            taxpayer_credit = max(0, taxpayer_credit - reduction)
        if taxpayer_credit > 0:
            credits["taxpayer_credit"] = float(money(taxpayer_credit))

        # Utah EITC (20% of federal)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        ut_eitc = self.calculate_state_eitc(federal_eitc)
        if ut_eitc > 0:
            credits["ut_eitc"] = ut_eitc

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions, state_adjusted_income=ut_agi,
            state_standard_deduction=0.0, state_itemized_deductions=0.0, deduction_used="credit_based",
            deduction_amount=0.0, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=0.0,
            state_taxable_income=ut_taxable_income, state_tax_before_credits=float(money(tax_before_credits)),
            state_credits=credits, total_state_credits=float(money(total_credits)), local_tax=0.0,
            state_tax_liability=float(money(state_tax_liability)), state_withholding=float(money(state_withholding)),
            state_refund_or_owed=float(money(state_withholding - state_tax_liability)),
        )

    def calculate_state_subtractions(self, tax_return: "TaxReturn") -> float:
        return tax_return.income.taxable_social_security

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        return 0.0

    def _calculate_federal_eitc_estimate(self, tax_return: "TaxReturn", filing_status: str) -> float:
        earned_income = (tax_return.income.get_total_wages() + tax_return.income.self_employment_income -
                        tax_return.income.self_employment_expenses)
        return tax_return.credits.calculate_eitc(earned_income, tax_return.adjusted_gross_income or 0.0,
                                                 filing_status, len(tax_return.taxpayer.dependents))
