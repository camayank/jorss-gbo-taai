"""Minnesota state tax calculator for tax year 2025."""

from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.state_tax_config import StateTaxConfig
from calculator.state.base_state_calculator import BaseStateCalculator, StateCalculationBreakdown
from calculator.state.state_registry import register_state


def get_minnesota_config() -> StateTaxConfig:
    """Create Minnesota tax configuration for 2025."""
    return StateTaxConfig(
        state_code="MN",
        state_name="Minnesota",
        tax_year=2025,
        is_flat_tax=False,
        brackets={
            # Minnesota 2025 brackets (4 brackets, indexed)
            "single": [
                (0, 0.0535),        # 5.35% on first $31,690
                (31690, 0.068),     # 6.8% on $31,690 - $104,090
                (104090, 0.0785),   # 7.85% on $104,090 - $193,240
                (193240, 0.0985),   # 9.85% on over $193,240
            ],
            "married_joint": [
                (0, 0.0535),
                (46330, 0.068),
                (184040, 0.0785),
                (321450, 0.0985),
            ],
            "married_separate": [
                (0, 0.0535),
                (23165, 0.068),
                (92020, 0.0785),
                (160725, 0.0985),
            ],
            "head_of_household": [
                (0, 0.0535),
                (39010, 0.068),
                (156520, 0.0785),
                (257350, 0.0985),
            ],
            "qualifying_widow": [
                (0, 0.0535),
                (46330, 0.068),
                (184040, 0.0785),
                (321450, 0.0985),
            ],
        },
        starts_from="federal_taxable_income",  # MN starts from federal taxable income
        standard_deduction={
            # MN standard deductions for 2025 (indexed)
            "single": 14575,
            "married_joint": 29150,
            "married_separate": 14575,
            "head_of_household": 21850,
            "qualifying_widow": 29150,
        },
        personal_exemption_amount={
            # MN has no personal exemptions (uses deductions)
            "single": 0,
            "married_joint": 0,
            "married_separate": 0,
            "head_of_household": 0,
            "qualifying_widow": 0,
        },
        dependent_exemption_amount=4950,  # Dependent exemption
        allows_federal_tax_deduction=False,
        social_security_taxable=False,  # MN exempts SS (fully exempt for income under threshold)
        pension_exclusion_limit=0,  # MN has no general pension exclusion
        military_pay_exempt=True,
        eitc_percentage=0.45,  # MN Working Family Credit (45% of federal)
        child_tax_credit_amount=1750,  # MN Child Tax Credit
        has_local_tax=False,
    )


@register_state("MN", 2025)
class MinnesotaCalculator(BaseStateCalculator):
    """
    Minnesota state tax calculator.

    Minnesota has:
    - 4 progressive tax brackets (up to 9.85% top rate)
    - Starts from federal taxable income with adjustments
    - Standard deduction: $14,575 single, $29,150 MFJ
    - Dependent exemption: $4,950 per dependent
    - Full exemption of Social Security (income limits apply)
    - Working Family Credit (45% of federal EITC)
    - Minnesota Child Tax Credit ($1,750 per child)
    - Marriage credit (for two-income couples)
    - No local income tax
    """

    def __init__(self):
        super().__init__(get_minnesota_config())

    def calculate(self, tax_return: "TaxReturn") -> StateCalculationBreakdown:
        """Calculate Minnesota state tax."""
        filing_status = self._get_filing_status_key(
            tax_return.taxpayer.filing_status.value
        )

        # Federal values
        federal_agi = tax_return.adjusted_gross_income or 0.0
        federal_taxable_income = tax_return.taxable_income or 0.0

        # Minnesota starts from federal taxable income
        starting_income = federal_taxable_income

        # Minnesota additions
        additions = self.calculate_state_additions(tax_return)

        # Minnesota subtractions
        subtractions = self.calculate_state_subtractions(tax_return)

        # Minnesota income after adjustments
        mn_adjusted_income = starting_income + additions - subtractions

        # Dependent exemption
        dependent_exemptions = len(tax_return.taxpayer.dependents)
        dependent_exemption_amt = dependent_exemptions * self.config.dependent_exemption_amount

        # MN standard deduction vs federal (may need adjustment)
        std_deduction = 0.0  # Already included in federal taxable income
        itemized = 0.0
        deduction_used = "federal"
        deduction_amount = 0.0

        # Minnesota taxable income
        mn_taxable_income = max(0.0, mn_adjusted_income - dependent_exemption_amt)

        # Calculate tax using brackets
        tax_before_credits = self.calculate_brackets(mn_taxable_income, filing_status)

        # State credits
        credits = {}

        # Working Family Credit (MN's EITC - 45% of federal)
        federal_eitc = self._calculate_federal_eitc_estimate(tax_return, filing_status)
        mn_wfc = self.calculate_state_eitc(federal_eitc)
        if mn_wfc > 0:
            credits["working_family_credit"] = mn_wfc

        # Minnesota Child Tax Credit
        child_credit = self._calculate_child_tax_credit(
            tax_return, federal_agi, filing_status
        )
        if child_credit > 0:
            credits["mn_child_tax_credit"] = child_credit

        # Marriage credit (for two-income married couples)
        marriage_credit = self._calculate_marriage_credit(
            tax_return, filing_status, mn_taxable_income
        )
        if marriage_credit > 0:
            credits["marriage_credit"] = marriage_credit

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
            state_adjusted_income=mn_adjusted_income,
            state_standard_deduction=std_deduction,
            state_itemized_deductions=itemized,
            deduction_used=deduction_used,
            deduction_amount=deduction_amount,
            personal_exemptions=personal_exemptions,
            dependent_exemptions=dependent_exemptions,
            exemption_amount=dependent_exemption_amt,
            state_taxable_income=mn_taxable_income,
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
        Calculate Minnesota income subtractions.

        Minnesota allows:
        - Social Security subtraction (income limits apply)
        - Railroad retirement
        - Military pay
        - K-12 education expenses
        """
        subtractions = 0.0

        # Social Security subtraction (phased out at higher income)
        # Full subtraction for income under ~$82,190 single / $105,380 joint
        ss_income = tax_return.income.taxable_social_security
        if ss_income > 0:
            agi = tax_return.adjusted_gross_income or 0.0
            if agi < 105000:  # Simplified threshold
                subtractions += ss_income
            elif agi < 140000:
                # Partial subtraction
                subtractions += ss_income * 0.5

        return subtractions

    def calculate_state_additions(self, tax_return: "TaxReturn") -> float:
        """Calculate Minnesota income additions."""
        additions = 0.0
        return additions

    def _calculate_child_tax_credit(
        self,
        tax_return: "TaxReturn",
        federal_agi: float,
        filing_status: str
    ) -> float:
        """
        Calculate Minnesota Child Tax Credit.

        $1,750 per qualifying child under 18.
        Phases out at higher incomes.
        """
        num_children = len(tax_return.taxpayer.dependents)
        if num_children == 0:
            return 0.0

        # Income limits (phaseout begins)
        if filing_status in ("married_joint", "qualifying_widow"):
            income_limit = 35000
        else:
            income_limit = 29500

        # Full credit below limit
        if federal_agi <= income_limit:
            return num_children * self.config.child_tax_credit_amount

        # Phase out above limit
        excess = federal_agi - income_limit
        reduction = excess * 0.12  # 12% reduction per $1,000 over
        credit = max(0, (num_children * self.config.child_tax_credit_amount) - reduction)
        return float(money(credit))

    def _calculate_marriage_credit(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        mn_taxable_income: float
    ) -> float:
        """
        Calculate Minnesota Marriage Credit.

        Credit for married couples where both spouses have income.
        """
        if filing_status != "married_joint":
            return 0.0

        # Simplified: assume both spouses work if wages > $30,000
        wages = tax_return.income.get_total_wages()
        if wages < 30000:
            return 0.0

        # Credit up to $1,346, phases out at higher income
        if mn_taxable_income > 195000:
            return 0.0

        # Simplified credit calculation
        return min(1346, wages * 0.02)

    def _calculate_federal_eitc_estimate(
        self,
        tax_return: "TaxReturn",
        filing_status: str
    ) -> float:
        """Estimate federal EITC for Working Family Credit calculation."""
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
