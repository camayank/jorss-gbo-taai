"""Vermont state tax calculator for tax year 2025."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_vermont_config() -> StateTaxConfig:
    return StateTaxConfig(
        state_code="VT", state_name="Vermont", tax_year=2025, is_flat_tax=False,
        brackets={
            "single": [(0, 0.0335), (45400, 0.066), (110050, 0.076), (229550, 0.0875)],
            "married_joint": [(0, 0.0335), (75850, 0.066), (183400, 0.076), (279450, 0.0875)],
            "married_separate": [(0, 0.0335), (37925, 0.066), (91700, 0.076), (139725, 0.0875)],
            "head_of_household": [(0, 0.0335), (60600, 0.066), (156550, 0.076), (254400, 0.0875)],
            "qualifying_widow": [(0, 0.0335), (75850, 0.066), (183400, 0.076), (279450, 0.0875)],
        },
        starts_from="federal_taxable_income",
        standard_deduction={"single": 7100, "married_joint": 14200, "married_separate": 7100,
                           "head_of_household": 10600, "qualifying_widow": 14200},
        personal_exemption_amount={"single": 4850, "married_joint": 9700, "married_separate": 4850,
                                   "head_of_household": 4850, "qualifying_widow": 4850},
        dependent_exemption_amount=4850, allows_federal_tax_deduction=False, social_security_taxable=False,
        pension_exclusion_limit=None, military_pay_exempt=True, eitc_percentage=0.38,
        child_tax_credit_amount=1000,  # VT Child Tax Credit
        has_local_tax=False,
    )


@register_state("VT", 2025)
class VermontCalculator(BaseStateCalculator):
    """Vermont - 4 brackets (3.35% - 8.75%), starts from federal taxable income."""

    def __init__(self):
        super().__init__(get_vermont_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        filing_status = self._get_filing_status_key(tax_return.taxpayer.filing_status.value)
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        additions = self.calculate_state_additions(tax_return)
        subtractions = self.calculate_state_subtractions(tax_return)
        vt_taxable_income = max(0.0, federal_taxable_income + additions - subtractions)

        tax_before_credits = self.calculate_brackets(vt_taxable_income, filing_status)

        credits = {}
        personal_exemptions = 2 if filing_status in ("married_joint", "qualifying_widow") else 1
        dependent_exemptions = len(tax_return.taxpayer.dependents)

        # Vermont EITC (38% of federal - highest non-DC)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        vt_eitc = self.calculate_state_eitc(federal_eitc)
        if vt_eitc > 0:
            credits["vt_eitc"] = vt_eitc

        # Vermont Child Tax Credit ($1,000 per child under 6)
        if dependent_exemptions > 0 and federal_agi < 125000:
            # Simplified: assume half under 6
            children_under_6 = max(1, dependent_exemptions // 2)
            credits["vt_child_credit"] = children_under_6 * self.config.child_tax_credit_amount

        total_credits = sum(credits.values())
        state_tax_liability = max(0.0, tax_before_credits - total_credits)
        state_withholding = self.get_state_withholding(tax_return)

        return StateCalculationBreakdown(
            state_code=self.config.state_code, state_name=self.config.state_name,
            tax_year=self.config.tax_year, filing_status=filing_status,
            federal_agi=federal_agi, federal_taxable_income=federal_taxable_income,
            state_additions=additions, state_subtractions=subtractions, state_adjusted_income=vt_taxable_income,
            state_standard_deduction=0.0, state_itemized_deductions=0.0, deduction_used="federal",
            deduction_amount=0.0, personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions, exemption_amount=0.0,
            state_taxable_income=vt_taxable_income, state_tax_before_credits=round(tax_before_credits, 2),
            state_credits=credits, total_state_credits=round(total_credits, 2), local_tax=0.0,
            state_tax_liability=round(state_tax_liability, 2), state_withholding=round(state_withholding, 2),
            state_refund_or_owed=round(state_withholding - state_tax_liability, 2),
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
