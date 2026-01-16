"""
Form 8615 - Tax for Certain Children Who Have Unearned Income

Implements the "Kiddie Tax" rules per IRC Section 1(g) which taxes a child's
unearned income above a threshold at the parent's marginal tax rate.

Who Must File Form 8615:
1. Child was under age 19 at end of tax year, OR
2. Child was under age 24 at end of year AND a full-time student
3. Child's unearned income was more than $2,500 (2025)
4. Child is required to file a tax return
5. At least one parent was alive at end of year
6. Child doesn't file a joint return with spouse

How the Kiddie Tax Works (2025):
- First $1,300 of unearned income: Tax-free (child's standard deduction)
- Next $1,300 ($1,301-$2,600): Taxed at child's rate (typically 10%)
- Above $2,600: Taxed at parent's marginal rate

Alternative: Parent can elect to include child's income on their return
using Form 8814 if child's income is only from interest/dividends and
is less than $13,000 (2025). Form 8814 is NOT implemented here.

Per IRS Form 8615 Instructions and IRC Section 1(g).
"""

from typing import Optional, List, Dict, Any, ClassVar
from pydantic import BaseModel, Field
from enum import Enum


class ParentFilingStatus(str, Enum):
    """Parent's filing status for kiddie tax calculation."""
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    MARRIED_SEPARATE = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOW = "qualifying_widow"


class ParentTaxInfo(BaseModel):
    """
    Parent's tax information needed for Form 8615.

    If parents are married filing jointly, use combined info.
    If parents are married filing separately, use parent with higher taxable income.
    If parents are unmarried, use custodial parent's info.
    """
    filing_status: ParentFilingStatus = Field(
        default=ParentFilingStatus.MARRIED_JOINT,
        description="Parent's filing status"
    )
    taxable_income: float = Field(
        default=0.0,
        ge=0,
        description="Parent's taxable income (Form 1040 Line 15)"
    )
    tax_before_credits: float = Field(
        default=0.0,
        ge=0,
        description="Parent's tax before credits (Form 1040 Line 16)"
    )

    # If multiple children have Form 8615, need combined unearned income
    other_children_net_unearned_income: float = Field(
        default=0.0,
        ge=0,
        description="Sum of net unearned income from other Form 8615 children"
    )

    # Parent identification
    parent_name: str = Field(
        default="",
        description="Parent's name (custodial or higher-income parent)"
    )
    parent_ssn: Optional[str] = Field(
        default=None,
        description="Parent's SSN"
    )

    # For divorced/separated parents
    parents_married_filing_separately: bool = Field(
        default=False,
        description="Parents are MFS and lived together at any time"
    )
    is_custodial_parent: bool = Field(
        default=True,
        description="This is the custodial parent's info"
    )


class Form8615(BaseModel):
    """
    Form 8615 - Tax for Certain Children Who Have Unearned Income.

    Calculates the "kiddie tax" when a child's unearned income exceeds
    the threshold, taxing the excess at the parent's marginal rate.

    Key 2025 Thresholds:
    - Unearned income threshold: $2,600 (triggers Form 8615)
    - Child's standard deduction for unearned: $1,300
    - Taxable at child's rate: $1,300 ($1,301 to $2,600)
    - Taxable at parent's rate: Above $2,600
    """

    # 2025 thresholds (indexed for inflation)
    UNEARNED_INCOME_THRESHOLD_2025: ClassVar[float] = 2600.0
    CHILD_STANDARD_DEDUCTION_2025: ClassVar[float] = 1300.0
    MIN_AGE_EXEMPTION: ClassVar[int] = 19  # Under 19 subject to kiddie tax
    STUDENT_AGE_EXEMPTION: ClassVar[int] = 24  # Under 24 if full-time student

    # Child information
    child_name: str = Field(
        default="",
        description="Child's name"
    )
    child_ssn: Optional[str] = Field(
        default=None,
        description="Child's SSN"
    )
    child_age: int = Field(
        ge=0,
        le=23,
        description="Child's age at end of tax year"
    )
    is_full_time_student: bool = Field(
        default=False,
        description="Child was full-time student during tax year (5+ months)"
    )

    # Part I: Child's Net Unearned Income
    # Line 1: Unearned income (interest, dividends, capital gains, etc.)
    unearned_income: float = Field(
        default=0.0,
        ge=0,
        description="Line 1: Child's total unearned income"
    )

    # Line 2: Adjustments to unearned income (if any)
    adjustments_to_unearned: float = Field(
        default=0.0,
        ge=0,
        description="Line 2: Adjustments to unearned income"
    )

    # Child's earned income (for standard deduction calculation)
    earned_income: float = Field(
        default=0.0,
        ge=0,
        description="Child's earned income (wages, self-employment)"
    )

    # Child's itemized deductions directly connected to unearned income
    itemized_deductions_for_unearned: float = Field(
        default=0.0,
        ge=0,
        description="Itemized deductions directly connected to unearned income"
    )

    # Part II: Child's Tax
    child_taxable_income: float = Field(
        default=0.0,
        ge=0,
        description="Child's taxable income (from child's Form 1040)"
    )

    # Parent's tax information
    parent_info: ParentTaxInfo = Field(
        default_factory=ParentTaxInfo,
        description="Parent's tax information for rate calculation"
    )

    # Eligibility flags
    parent_alive: bool = Field(
        default=True,
        description="At least one parent was alive at end of year"
    )
    child_files_joint_return: bool = Field(
        default=False,
        description="Child files joint return with spouse"
    )
    child_required_to_file: bool = Field(
        default=True,
        description="Child is required to file a tax return"
    )

    def is_subject_to_kiddie_tax(self) -> bool:
        """
        Determine if child is subject to kiddie tax rules.

        Child must:
        1. Be under 19, OR under 24 and full-time student
        2. Have unearned income over threshold ($2,600 for 2025)
        3. Have at least one living parent
        4. Not file joint return
        5. Be required to file
        """
        # Age test
        if self.child_age >= self.MIN_AGE_EXEMPTION:
            if not self.is_full_time_student:
                return False
            if self.child_age >= self.STUDENT_AGE_EXEMPTION:
                return False

        # Unearned income test
        if self.unearned_income <= self.UNEARNED_INCOME_THRESHOLD_2025:
            return False

        # Other requirements
        if not self.parent_alive:
            return False
        if self.child_files_joint_return:
            return False
        if not self.child_required_to_file:
            return False

        return True

    def calculate_child_standard_deduction(self) -> float:
        """
        Calculate child's standard deduction for unearned income.

        For a child who can be claimed as a dependent:
        Standard deduction = greater of:
        - $1,300 (2025), OR
        - Earned income + $450, up to regular standard deduction

        For Form 8615, we use the portion allocable to unearned income.
        """
        # Minimum standard deduction for dependent
        min_deduction = self.CHILD_STANDARD_DEDUCTION_2025

        # Earned income-based deduction
        earned_based = self.earned_income + 450.0

        # Regular standard deduction limit (single filer 2025)
        max_standard_deduction = 15000.0  # Would come from config in production

        # Child's standard deduction
        child_standard = min(max(min_deduction, earned_based), max_standard_deduction)

        # For Form 8615, the deduction against unearned income is limited
        # to the child's standard deduction or $1,300, whichever applies
        return min(child_standard, self.CHILD_STANDARD_DEDUCTION_2025)

    def calculate_net_unearned_income(self) -> dict:
        """
        Calculate Part I - Child's Net Unearned Income.

        Net Unearned Income = Unearned Income - Greater of:
        - $2,600 (2x standard deduction), OR
        - $1,300 + itemized deductions directly connected to unearned income

        This is the amount taxed at parent's rate.
        """
        result = {
            'line_1_unearned_income': self.unearned_income,
            'line_2_adjustments': self.adjustments_to_unearned,
            'line_3_adjusted_unearned': 0.0,
            'line_4_deduction_option_a': 0.0,  # 2 × $1,300 = $2,600
            'line_4_deduction_option_b': 0.0,  # $1,300 + itemized
            'line_4_deduction': 0.0,
            'line_5_net_unearned_income': 0.0,
        }

        # Line 3: Adjusted unearned income
        adjusted_unearned = self.unearned_income - self.adjustments_to_unearned
        result['line_3_adjusted_unearned'] = max(0.0, adjusted_unearned)

        if adjusted_unearned <= 0:
            return result

        # Line 4: Deduction (greater of option a or b)
        # Option A: 2 × standard deduction = $2,600
        option_a = 2 * self.CHILD_STANDARD_DEDUCTION_2025
        result['line_4_deduction_option_a'] = option_a

        # Option B: $1,300 + itemized deductions for unearned
        option_b = self.CHILD_STANDARD_DEDUCTION_2025 + self.itemized_deductions_for_unearned
        result['line_4_deduction_option_b'] = option_b

        deduction = max(option_a, option_b)
        result['line_4_deduction'] = deduction

        # Line 5: Net unearned income
        net_unearned = max(0.0, adjusted_unearned - deduction)
        result['line_5_net_unearned_income'] = round(net_unearned, 2)

        return result

    def calculate_tax_at_child_rate(self, taxable_income: float) -> float:
        """
        Calculate tax on child's taxable income at child's own rates.

        Uses 2025 single filer brackets (child typically files as single).
        """
        # 2025 tax brackets for single filers
        brackets = [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250525, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37),
        ]

        tax = 0.0
        remaining = taxable_income
        prev_threshold = 0

        for threshold, rate in brackets:
            bracket_income = min(remaining, threshold - prev_threshold)
            if bracket_income <= 0:
                break
            tax += bracket_income * rate
            remaining -= bracket_income
            prev_threshold = threshold

        return round(tax, 2)

    def calculate_tax_at_parent_rate(
        self,
        net_unearned_income: float
    ) -> dict:
        """
        Calculate tax on child's net unearned income at parent's marginal rate.

        Method:
        1. Add child's net unearned income to parent's taxable income
        2. Calculate tax on combined amount
        3. Subtract parent's actual tax
        4. Result is additional tax at parent's rate
        """
        result = {
            'parent_taxable_income': self.parent_info.taxable_income,
            'parent_tax': self.parent_info.tax_before_credits,
            'other_children_unearned': self.parent_info.other_children_net_unearned_income,
            'this_child_unearned': net_unearned_income,
            'total_children_unearned': 0.0,
            'combined_taxable_income': 0.0,
            'tax_on_combined': 0.0,
            'additional_tax': 0.0,
            'this_child_share': 0.0,
        }

        if net_unearned_income <= 0:
            return result

        # Total children's net unearned income (this child + others)
        total_children = net_unearned_income + self.parent_info.other_children_net_unearned_income
        result['total_children_unearned'] = total_children

        # Combined taxable income
        combined = self.parent_info.taxable_income + total_children
        result['combined_taxable_income'] = combined

        # Calculate tax on combined amount using parent's filing status
        tax_on_combined = self._calculate_tax_for_status(
            combined,
            self.parent_info.filing_status
        )
        result['tax_on_combined'] = tax_on_combined

        # Additional tax from children's unearned income
        additional = max(0.0, tax_on_combined - self.parent_info.tax_before_credits)
        result['additional_tax'] = round(additional, 2)

        # This child's share (pro-rata if multiple children)
        if total_children > 0:
            this_child_share = additional * (net_unearned_income / total_children)
        else:
            this_child_share = 0.0
        result['this_child_share'] = round(this_child_share, 2)

        return result

    def _calculate_tax_for_status(
        self,
        taxable_income: float,
        filing_status: ParentFilingStatus
    ) -> float:
        """Calculate tax for given income and filing status."""
        # 2025 tax brackets by filing status
        brackets = {
            ParentFilingStatus.SINGLE: [
                (11925, 0.10),
                (48475, 0.12),
                (103350, 0.22),
                (197300, 0.24),
                (250525, 0.32),
                (626350, 0.35),
                (float('inf'), 0.37),
            ],
            ParentFilingStatus.MARRIED_JOINT: [
                (23850, 0.10),
                (96950, 0.12),
                (206700, 0.22),
                (394600, 0.24),
                (501050, 0.32),
                (751600, 0.35),
                (float('inf'), 0.37),
            ],
            ParentFilingStatus.MARRIED_SEPARATE: [
                (11925, 0.10),
                (48475, 0.12),
                (103350, 0.22),
                (197300, 0.24),
                (250525, 0.32),
                (375800, 0.35),
                (float('inf'), 0.37),
            ],
            ParentFilingStatus.HEAD_OF_HOUSEHOLD: [
                (17000, 0.10),
                (64850, 0.12),
                (103350, 0.22),
                (197300, 0.24),
                (250500, 0.32),
                (626350, 0.35),
                (float('inf'), 0.37),
            ],
            ParentFilingStatus.QUALIFYING_WIDOW: [
                (23850, 0.10),
                (96950, 0.12),
                (206700, 0.22),
                (394600, 0.24),
                (501050, 0.32),
                (751600, 0.35),
                (float('inf'), 0.37),
            ],
        }

        status_brackets = brackets.get(filing_status, brackets[ParentFilingStatus.SINGLE])

        tax = 0.0
        remaining = taxable_income
        prev_threshold = 0

        for threshold, rate in status_brackets:
            bracket_income = min(remaining, threshold - prev_threshold)
            if bracket_income <= 0:
                break
            tax += bracket_income * rate
            remaining -= bracket_income
            prev_threshold = threshold

        return round(tax, 2)

    def calculate_kiddie_tax(self) -> dict:
        """
        Complete Form 8615 calculation.

        Returns comprehensive breakdown including:
        - Eligibility determination
        - Net unearned income (Part I)
        - Tax at child's rate on earned + first $1,300 unearned
        - Tax at parent's rate on net unearned income (Part II/III)
        - Total kiddie tax
        """
        result = {
            'child_name': self.child_name,
            'child_age': self.child_age,
            'is_full_time_student': self.is_full_time_student,

            # Eligibility
            'subject_to_kiddie_tax': False,
            'reason_not_subject': '',

            # Income breakdown
            'unearned_income': self.unearned_income,
            'earned_income': self.earned_income,
            'child_taxable_income': self.child_taxable_income,

            # Part I: Net Unearned Income
            'net_unearned_income_breakdown': {},
            'net_unearned_income': 0.0,

            # Part II: Tax calculation
            'tax_on_child_taxable_at_child_rate': 0.0,
            'tax_at_parent_rate_breakdown': {},
            'tax_at_parent_rate': 0.0,

            # Part III: Child's tax
            'child_tax_without_kiddie_rules': 0.0,
            'kiddie_tax_increase': 0.0,
            'total_child_tax': 0.0,
        }

        # Check eligibility
        if not self.is_subject_to_kiddie_tax():
            result['reason_not_subject'] = self._get_exemption_reason()
            # Calculate normal tax without kiddie rules
            result['child_tax_without_kiddie_rules'] = self.calculate_tax_at_child_rate(
                self.child_taxable_income
            )
            result['total_child_tax'] = result['child_tax_without_kiddie_rules']
            return result

        result['subject_to_kiddie_tax'] = True

        # Part I: Calculate net unearned income
        part_i = self.calculate_net_unearned_income()
        result['net_unearned_income_breakdown'] = part_i
        net_unearned = part_i['line_5_net_unearned_income']
        result['net_unearned_income'] = net_unearned

        # Calculate tax on child's taxable income at child's rate
        # (This is for comparison / computing the increase)
        child_tax_normal = self.calculate_tax_at_child_rate(self.child_taxable_income)
        result['child_tax_without_kiddie_rules'] = child_tax_normal

        if net_unearned <= 0:
            # No kiddie tax if net unearned is zero or less
            result['total_child_tax'] = child_tax_normal
            return result

        # Part II/III: Calculate tax at parent's rate
        parent_rate_calc = self.calculate_tax_at_parent_rate(net_unearned)
        result['tax_at_parent_rate_breakdown'] = parent_rate_calc
        result['tax_at_parent_rate'] = parent_rate_calc['this_child_share']

        # Calculate tax on income NOT subject to parent's rate
        # This is child's taxable income minus net unearned income
        income_at_child_rate = max(0.0, self.child_taxable_income - net_unearned)
        tax_at_child_rate = self.calculate_tax_at_child_rate(income_at_child_rate)
        result['tax_on_child_taxable_at_child_rate'] = tax_at_child_rate

        # Total child's tax = tax at child rate + tax at parent rate
        total_tax = tax_at_child_rate + parent_rate_calc['this_child_share']
        result['total_child_tax'] = round(total_tax, 2)

        # Kiddie tax increase
        result['kiddie_tax_increase'] = round(
            max(0.0, total_tax - child_tax_normal), 2
        )

        return result

    def _get_exemption_reason(self) -> str:
        """Get reason why child is not subject to kiddie tax."""
        if self.child_age >= self.STUDENT_AGE_EXEMPTION:
            return f"Child age {self.child_age} is 24 or older"

        if self.child_age >= self.MIN_AGE_EXEMPTION and not self.is_full_time_student:
            return f"Child age {self.child_age} is 19+ and not a full-time student"

        if self.unearned_income <= self.UNEARNED_INCOME_THRESHOLD_2025:
            return f"Unearned income ${self.unearned_income:,.0f} is at or below ${self.UNEARNED_INCOME_THRESHOLD_2025:,.0f} threshold"

        if not self.parent_alive:
            return "No parent alive at end of year"

        if self.child_files_joint_return:
            return "Child files joint return with spouse"

        if not self.child_required_to_file:
            return "Child not required to file tax return"

        return "Unknown exemption"


def calculate_kiddie_tax_for_child(
    child_age: int,
    is_student: bool,
    unearned_income: float,
    earned_income: float,
    child_taxable_income: float,
    parent_taxable_income: float,
    parent_tax: float,
    parent_filing_status: str = "married_joint",
    other_children_unearned: float = 0.0,
) -> dict:
    """
    Convenience function to calculate kiddie tax.

    Args:
        child_age: Child's age at end of tax year
        is_student: Whether child is full-time student
        unearned_income: Child's unearned income (interest, dividends, gains)
        earned_income: Child's earned income (wages)
        child_taxable_income: Child's total taxable income
        parent_taxable_income: Parent's taxable income
        parent_tax: Parent's tax before credits
        parent_filing_status: Parent's filing status
        other_children_unearned: Other children's net unearned income

    Returns:
        Complete kiddie tax calculation result
    """
    parent_info = ParentTaxInfo(
        filing_status=ParentFilingStatus(parent_filing_status),
        taxable_income=parent_taxable_income,
        tax_before_credits=parent_tax,
        other_children_net_unearned_income=other_children_unearned,
    )

    form = Form8615(
        child_age=child_age,
        is_full_time_student=is_student,
        unearned_income=unearned_income,
        earned_income=earned_income,
        child_taxable_income=child_taxable_income,
        parent_info=parent_info,
    )

    return form.calculate_kiddie_tax()
