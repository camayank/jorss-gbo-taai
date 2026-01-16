"""
Form 8814 - Parent's Election To Report Child's Interest and Dividends

IRS Form for parents to include child's unearned income on their return
instead of filing a separate return for the child.

Eligibility:
- Child was under 19 (or under 24 if full-time student) at year end
- Child's only income was interest and dividends (including capital gains distributions)
- Child's gross income was less than $12,500 (2024)
- Child would otherwise be required to file a return
- No estimated tax payments made in child's name
- No federal income tax withheld from child's income

Key Differences from Form 8615:
- Form 8814: Parent elects to include child's income on parent's return
- Form 8615: Child files own return, but kiddie tax calculates at parent's rate

Note: Using Form 8814 may result in higher tax than filing separately
due to tax computed at parent's marginal rate.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChildIncome(BaseModel):
    """Child's income information for Form 8814."""
    child_name: str = Field(description="Child's name")
    child_ssn: str = Field(default="", description="Child's SSN")
    child_age: int = Field(ge=0, le=23, description="Child's age at end of tax year")
    is_full_time_student: bool = Field(
        default=False,
        description="Child was a full-time student (for age 19-23)"
    )

    # Income amounts from child's 1099s
    taxable_interest: float = Field(
        default=0.0, ge=0,
        description="Child's taxable interest income"
    )
    tax_exempt_interest: float = Field(
        default=0.0, ge=0,
        description="Child's tax-exempt interest"
    )
    ordinary_dividends: float = Field(
        default=0.0, ge=0,
        description="Child's ordinary dividends"
    )
    qualified_dividends: float = Field(
        default=0.0, ge=0,
        description="Child's qualified dividends"
    )
    capital_gain_distributions: float = Field(
        default=0.0, ge=0,
        description="Child's capital gain distributions"
    )
    alaska_pfd: float = Field(
        default=0.0, ge=0,
        description="Alaska Permanent Fund dividends"
    )

    # Withholding
    federal_tax_withheld: float = Field(
        default=0.0, ge=0,
        description="Federal tax withheld from child's income"
    )

    def gross_income(self) -> float:
        """Calculate child's gross income."""
        return (
            self.taxable_interest +
            self.ordinary_dividends +
            self.capital_gain_distributions +
            self.alaska_pfd
        )

    def qualifies_for_8814(self) -> bool:
        """
        Check if child qualifies for Form 8814 election.

        Requirements:
        - Under 19, or under 24 if full-time student
        - Only income is interest/dividends
        - Gross income < $12,500
        - No estimated tax payments
        - No federal withholding (simplified check)
        """
        # Age check
        if self.is_full_time_student:
            age_ok = self.child_age < 24
        else:
            age_ok = self.child_age < 19

        # Income threshold check (2025)
        income_ok = self.gross_income() < 12500

        # No withholding check (simplified)
        withholding_ok = self.federal_tax_withheld == 0

        return age_ok and income_ok and withholding_ok


class Form8814(BaseModel):
    """
    Form 8814 - Parent's Election To Report Child's Interest and Dividends

    Allows parents to include qualifying child's unearned income on their return.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Children
    children: List[ChildIncome] = Field(
        default_factory=list,
        description="Children whose income is being reported"
    )

    # 2025 thresholds
    BASE_AMOUNT: float = 1300.0  # First $1,300 tax-free
    SECOND_TIER: float = 1300.0  # Next $1,300 at 10%
    GROSS_INCOME_LIMIT: float = 12500.0  # Maximum gross income for election

    def calculate_child_addition(self, child: ChildIncome) -> Dict[str, Any]:
        """
        Calculate the amount to add to parent's return for one child.

        Lines 1-15 of Form 8814.
        """
        if not child.qualifies_for_8814():
            return {
                'child_name': child.child_name,
                'qualifies': False,
                'reason': 'Does not meet Form 8814 requirements',
                'amount_to_include': 0.0,
                'child_tax': 0.0,
            }

        # Line 1a: Child's taxable interest
        line_1a = child.taxable_interest

        # Line 1b: Child's tax-exempt interest
        line_1b = child.tax_exempt_interest

        # Line 2a: Child's ordinary dividends
        line_2a = child.ordinary_dividends

        # Line 2b: Child's qualified dividends
        line_2b = child.qualified_dividends

        # Line 3: Child's capital gain distributions
        line_3 = child.capital_gain_distributions

        # Line 4: Add lines 1a, 2a, and 3
        line_4 = line_1a + line_2a + line_3

        # Line 5: Base amount
        line_5 = self.BASE_AMOUNT

        # Line 6: Subtract line 5 from line 4
        line_6 = max(0, line_4 - line_5)

        # Line 7: Tax (10% of next tier, up to $1,300)
        # First $1,300 of line 6 taxed at 10%
        taxable_at_10 = min(line_6, self.SECOND_TIER)
        line_7 = taxable_at_10 * 0.10

        # Line 8: Net amount excluded (line 5 + taxable at 10%)
        line_8 = line_5 + taxable_at_10

        # Line 9: Subtract line 8 from line 4 (amount to include on parent's return)
        line_9 = max(0, line_4 - line_8)

        # Calculate qualified dividends portion to include
        # Proportionate allocation
        if line_4 > 0:
            qd_ratio = line_2b / line_4
            cg_ratio = line_3 / line_4
        else:
            qd_ratio = 0.0
            cg_ratio = 0.0

        qualified_dividends_to_include = line_9 * qd_ratio
        capital_gains_to_include = line_9 * cg_ratio
        ordinary_income_to_include = line_9 - qualified_dividends_to_include - capital_gains_to_include

        return {
            'child_name': child.child_name,
            'child_age': child.child_age,
            'qualifies': True,

            # Line items
            'line_1a_interest': round(line_1a, 2),
            'line_1b_exempt_interest': round(line_1b, 2),
            'line_2a_ordinary_dividends': round(line_2a, 2),
            'line_2b_qualified_dividends': round(line_2b, 2),
            'line_3_capital_gains': round(line_3, 2),
            'line_4_total_income': round(line_4, 2),
            'line_5_base_amount': line_5,
            'line_6_over_base': round(line_6, 2),
            'line_7_tax_at_10_pct': round(line_7, 2),
            'line_8_excluded': round(line_8, 2),
            'line_9_to_include': round(line_9, 2),

            # Amounts for parent's return
            'amount_to_include': round(line_9, 2),
            'child_tax': round(line_7, 2),
            'qualified_dividends_to_include': round(qualified_dividends_to_include, 2),
            'capital_gains_to_include': round(capital_gains_to_include, 2),
            'ordinary_income_to_include': round(ordinary_income_to_include, 2),
        }

    def calculate_form_8814(self) -> Dict[str, Any]:
        """
        Calculate Form 8814 for all children.

        Returns total amounts to add to parent's return.
        """
        total_to_include = 0.0
        total_qualified_dividends = 0.0
        total_capital_gains = 0.0
        total_ordinary_income = 0.0
        total_child_tax = 0.0

        child_calculations = []
        qualifying_children = 0

        for child in self.children:
            calc = self.calculate_child_addition(child)
            child_calculations.append(calc)

            if calc['qualifies']:
                qualifying_children += 1
                total_to_include += calc['amount_to_include']
                total_qualified_dividends += calc['qualified_dividends_to_include']
                total_capital_gains += calc['capital_gains_to_include']
                total_ordinary_income += calc['ordinary_income_to_include']
                total_child_tax += calc['child_tax']

        return {
            'tax_year': self.tax_year,
            'children_count': len(self.children),
            'qualifying_children': qualifying_children,

            # Totals for parent's return
            'total_to_include_in_income': round(total_to_include, 2),
            'total_qualified_dividends': round(total_qualified_dividends, 2),
            'total_capital_gains': round(total_capital_gains, 2),
            'total_ordinary_income': round(total_ordinary_income, 2),
            'total_child_tax': round(total_child_tax, 2),

            # Form 1040 lines
            'add_to_line_2b_interest': round(total_ordinary_income, 2),  # Interest portion
            'add_to_line_3a_qualified_div': round(total_qualified_dividends, 2),
            'add_to_line_3b_ordinary_div': round(total_to_include - total_capital_gains, 2),
            'add_to_line_7_capital_gain': round(total_capital_gains, 2),
            'add_to_tax': round(total_child_tax, 2),

            # Child details
            'child_calculations': child_calculations,
        }

    def get_form_8814_summary(self) -> Dict[str, float]:
        """Get a concise summary of Form 8814."""
        result = self.calculate_form_8814()
        return {
            'children_reported': result['qualifying_children'],
            'income_to_include': result['total_to_include_in_income'],
            'tax_from_children': result['total_child_tax'],
        }

    def compare_with_8615(self, parent_marginal_rate: float) -> Dict[str, Any]:
        """
        Compare Form 8814 election vs Form 8615 (filing separately).

        Form 8814 may result in higher tax because child's income above
        the $2,600 threshold is taxed at parent's marginal rate, not
        the kiddie tax calculation.
        """
        form_8814_result = self.calculate_form_8814()

        # Estimate tax using Form 8615 method
        # (Simplified - actual 8615 calculation is more complex)
        total_8615_tax = 0.0

        for child in self.children:
            if not child.qualifies_for_8814():
                continue

            gross = child.gross_income()

            # First $1,300 tax-free
            # Next $1,300 at child's rate (assume 10%)
            # Amount over $2,600 at parent's rate
            if gross <= self.BASE_AMOUNT:
                child_tax = 0.0
            elif gross <= self.BASE_AMOUNT + self.SECOND_TIER:
                child_tax = (gross - self.BASE_AMOUNT) * 0.10
            else:
                child_tax = self.SECOND_TIER * 0.10
                child_tax += (gross - self.BASE_AMOUNT - self.SECOND_TIER) * parent_marginal_rate

            total_8615_tax += child_tax

        # Form 8814 tax: first $1,300 at 10%, rest at parent's marginal rate
        form_8814_tax = form_8814_result['total_child_tax']
        form_8814_tax += form_8814_result['total_to_include_in_income'] * parent_marginal_rate

        return {
            'form_8814_total_tax': round(form_8814_tax, 2),
            'form_8615_estimated_tax': round(total_8615_tax, 2),
            'difference': round(form_8814_tax - total_8615_tax, 2),
            'recommendation': 'Form 8814' if form_8814_tax <= total_8615_tax else 'Form 8615 (file separately)',
        }


def calculate_parent_election(
    child_interest: float,
    child_dividends: float,
    child_qualified_dividends: float = 0.0,
    child_capital_gains: float = 0.0,
    child_age: int = 10,
    is_student: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to calculate Form 8814.

    Args:
        child_interest: Child's taxable interest
        child_dividends: Child's ordinary dividends
        child_qualified_dividends: Child's qualified dividends
        child_capital_gains: Child's capital gain distributions
        child_age: Child's age at year end
        is_student: Whether child is a full-time student (for ages 19-23)

    Returns:
        Dictionary with Form 8814 calculation results
    """
    child = ChildIncome(
        child_name="Child",
        child_age=child_age,
        is_full_time_student=is_student,
        taxable_interest=child_interest,
        ordinary_dividends=child_dividends,
        qualified_dividends=child_qualified_dividends,
        capital_gain_distributions=child_capital_gains,
    )

    form = Form8814(children=[child])
    return form.calculate_form_8814()
