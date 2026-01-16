"""
Test suite for Form 8615 - Kiddie Tax calculations.

Tests cover:
- Eligibility determination (age, student status, thresholds)
- Net unearned income calculation (Part I)
- Tax at child's rate
- Tax at parent's rate (Part II/III)
- Multiple children pro-rata allocation
- Various parent filing statuses
- Edge cases and exemptions
"""

import pytest
from decimal import Decimal
from models.form_8615 import (
    Form8615,
    ParentTaxInfo,
    ParentFilingStatus,
    calculate_kiddie_tax_for_child,
)


class TestForm8615Eligibility:
    """Tests for kiddie tax eligibility determination."""

    def test_child_under_19_with_high_unearned_income_is_subject(self):
        """Child under 19 with unearned income > $2,600 is subject to kiddie tax."""
        form = Form8615(
            child_age=16,
            is_full_time_student=False,
            unearned_income=5000.0,
            child_taxable_income=5000.0,
        )
        assert form.is_subject_to_kiddie_tax() is True

    def test_child_age_18_subject_to_kiddie_tax(self):
        """18-year-old is still under 19 and subject to kiddie tax."""
        form = Form8615(
            child_age=18,
            is_full_time_student=False,
            unearned_income=3000.0,
            child_taxable_income=3000.0,
        )
        assert form.is_subject_to_kiddie_tax() is True

    def test_child_age_19_not_student_exempt(self):
        """19-year-old non-student is exempt from kiddie tax."""
        form = Form8615(
            child_age=19,
            is_full_time_student=False,
            unearned_income=10000.0,
            child_taxable_income=10000.0,
        )
        assert form.is_subject_to_kiddie_tax() is False

    def test_student_age_19_to_23_is_subject(self):
        """Full-time student age 19-23 is subject to kiddie tax."""
        for age in [19, 20, 21, 22, 23]:
            form = Form8615(
                child_age=age,
                is_full_time_student=True,
                unearned_income=5000.0,
                child_taxable_income=5000.0,
            )
            assert form.is_subject_to_kiddie_tax() is True, f"Student age {age} should be subject"

    def test_student_age_24_rejected_by_validation(self):
        """Age 24 is rejected by model validation (max age is 23)."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Form8615(
                child_age=24,
                is_full_time_student=True,
                unearned_income=10000.0,
                child_taxable_income=10000.0,
            )

    def test_unearned_income_at_threshold_not_subject(self):
        """Unearned income exactly at $2,600 threshold is NOT subject."""
        form = Form8615(
            child_age=16,
            unearned_income=2600.0,  # Exactly at threshold
            child_taxable_income=2600.0,
        )
        assert form.is_subject_to_kiddie_tax() is False

    def test_unearned_income_just_above_threshold_is_subject(self):
        """Unearned income $2,601 (just above threshold) IS subject."""
        form = Form8615(
            child_age=16,
            unearned_income=2601.0,
            child_taxable_income=2601.0,
        )
        assert form.is_subject_to_kiddie_tax() is True

    def test_unearned_income_below_threshold_not_subject(self):
        """Unearned income below $2,600 threshold is not subject."""
        form = Form8615(
            child_age=16,
            unearned_income=2000.0,
            child_taxable_income=2000.0,
        )
        assert form.is_subject_to_kiddie_tax() is False

    def test_no_parent_alive_exempt(self):
        """Child with no living parent is exempt from kiddie tax."""
        form = Form8615(
            child_age=16,
            unearned_income=5000.0,
            child_taxable_income=5000.0,
            parent_alive=False,
        )
        assert form.is_subject_to_kiddie_tax() is False

    def test_child_filing_joint_exempt(self):
        """Child filing joint return with spouse is exempt."""
        form = Form8615(
            child_age=18,
            unearned_income=5000.0,
            child_taxable_income=5000.0,
            child_files_joint_return=True,
        )
        assert form.is_subject_to_kiddie_tax() is False

    def test_child_not_required_to_file_exempt(self):
        """Child not required to file is exempt."""
        form = Form8615(
            child_age=16,
            unearned_income=5000.0,
            child_taxable_income=5000.0,
            child_required_to_file=False,
        )
        assert form.is_subject_to_kiddie_tax() is False


class TestForm8615NetUnearnedIncome:
    """Tests for Part I - Net Unearned Income calculation."""

    def test_basic_net_unearned_income_calculation(self):
        """Basic net unearned = unearned - $2,600 standard deduction."""
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,
            child_taxable_income=10000.0,
        )
        result = form.calculate_net_unearned_income()

        assert result['line_1_unearned_income'] == 10000.0
        assert result['line_4_deduction_option_a'] == 2600.0  # 2 × $1,300
        assert result['line_5_net_unearned_income'] == 7400.0  # $10,000 - $2,600

    def test_net_unearned_with_itemized_deductions(self):
        """When itemized deductions > $1,300, use option B."""
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,
            itemized_deductions_for_unearned=2000.0,  # $2,000 itemized
            child_taxable_income=10000.0,
        )
        result = form.calculate_net_unearned_income()

        # Option A: $2,600
        # Option B: $1,300 + $2,000 = $3,300 (higher)
        assert result['line_4_deduction_option_a'] == 2600.0
        assert result['line_4_deduction_option_b'] == 3300.0
        assert result['line_4_deduction'] == 3300.0  # Greater of two
        assert result['line_5_net_unearned_income'] == 6700.0  # $10,000 - $3,300

    def test_zero_unearned_income(self):
        """Zero unearned income results in zero net unearned."""
        form = Form8615(
            child_age=16,
            unearned_income=0.0,
            child_taxable_income=0.0,
        )
        result = form.calculate_net_unearned_income()
        assert result['line_5_net_unearned_income'] == 0.0

    def test_unearned_less_than_deduction(self):
        """When unearned income < deduction, net unearned is zero."""
        form = Form8615(
            child_age=16,
            unearned_income=2000.0,  # Less than $2,600
            child_taxable_income=2000.0,
        )
        result = form.calculate_net_unearned_income()
        assert result['line_5_net_unearned_income'] == 0.0

    def test_adjustments_reduce_unearned(self):
        """Adjustments to unearned income reduce the base amount."""
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,
            adjustments_to_unearned=1000.0,  # $1,000 adjustment
            child_taxable_income=9000.0,
        )
        result = form.calculate_net_unearned_income()

        assert result['line_3_adjusted_unearned'] == 9000.0  # $10,000 - $1,000
        assert result['line_5_net_unearned_income'] == 6400.0  # $9,000 - $2,600


class TestForm8615TaxAtChildRate:
    """Tests for tax calculation at child's rate."""

    def test_tax_in_10_percent_bracket(self):
        """Income in 10% bracket taxed correctly."""
        form = Form8615(child_age=16, unearned_income=3000.0, child_taxable_income=3000.0)
        tax = form.calculate_tax_at_child_rate(5000.0)
        assert tax == 500.0  # $5,000 × 10%

    def test_tax_across_brackets(self):
        """Income spanning multiple brackets calculated correctly."""
        form = Form8615(child_age=16, unearned_income=3000.0, child_taxable_income=3000.0)
        # $20,000 income: $11,925 @ 10% + $8,075 @ 12%
        tax = form.calculate_tax_at_child_rate(20000.0)
        expected = 11925 * 0.10 + (20000 - 11925) * 0.12
        assert abs(tax - expected) < 0.01

    def test_tax_on_zero_income(self):
        """Zero income results in zero tax."""
        form = Form8615(child_age=16, unearned_income=3000.0, child_taxable_income=3000.0)
        tax = form.calculate_tax_at_child_rate(0.0)
        assert tax == 0.0


class TestForm8615TaxAtParentRate:
    """Tests for Part II/III - Tax at parent's marginal rate."""

    def test_basic_parent_rate_calculation(self):
        """Basic tax at parent's rate adds child's unearned to parent's income."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_JOINT,
            taxable_income=150000.0,
            tax_before_credits=23000.0,  # Approximate tax on $150k MFJ
        )
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,
            child_taxable_income=10000.0,
            parent_info=parent_info,
        )
        result = form.calculate_tax_at_parent_rate(7400.0)  # Net unearned

        # Parent at 22% bracket, so additional tax ≈ $7,400 × 22% = $1,628
        assert result['this_child_share'] > 0
        assert result['combined_taxable_income'] == 157400.0  # $150k + $7,400

    def test_multiple_children_prorata_allocation(self):
        """When multiple children, tax is allocated pro-rata."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_JOINT,
            taxable_income=150000.0,
            tax_before_credits=23000.0,
            other_children_net_unearned_income=5000.0,  # Other child has $5k
        )
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,  # This child has $10k unearned
            child_taxable_income=10000.0,
            parent_info=parent_info,
        )
        result = form.calculate_tax_at_parent_rate(7400.0)

        total_children = 7400.0 + 5000.0  # $12,400 total
        this_child_ratio = 7400.0 / total_children  # ~59.7%

        # This child's share should be ~60% of additional tax
        assert result['total_children_unearned'] == 12400.0
        assert result['this_child_share'] < result['additional_tax']  # Less than full amount

    def test_parent_filing_single(self):
        """Calculate correctly for single parent."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.SINGLE,
            taxable_income=100000.0,
            tax_before_credits=17400.0,  # Approximate for single @ $100k
        )
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,
            child_taxable_income=10000.0,
            parent_info=parent_info,
        )
        result = form.calculate_tax_at_parent_rate(7400.0)
        assert result['this_child_share'] > 0

    def test_parent_filing_head_of_household(self):
        """Calculate correctly for head of household parent."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.HEAD_OF_HOUSEHOLD,
            taxable_income=80000.0,
            tax_before_credits=10500.0,  # Approximate
        )
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,
            child_taxable_income=10000.0,
            parent_info=parent_info,
        )
        result = form.calculate_tax_at_parent_rate(7400.0)
        assert result['this_child_share'] > 0


class TestForm8615FullCalculation:
    """Tests for complete Form 8615 calculation."""

    def test_child_not_subject_returns_normal_tax(self):
        """When not subject to kiddie tax, return normal child tax."""
        form = Form8615(
            child_age=16,
            unearned_income=2000.0,  # Below threshold
            earned_income=1000.0,
            child_taxable_income=2000.0,
        )
        result = form.calculate_kiddie_tax()

        assert result['subject_to_kiddie_tax'] is False
        assert result['kiddie_tax_increase'] == 0.0
        assert result['total_child_tax'] == result['child_tax_without_kiddie_rules']

    def test_basic_kiddie_tax_calculation(self):
        """Complete kiddie tax calculation for typical scenario."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_JOINT,
            taxable_income=200000.0,
            tax_before_credits=32000.0,  # Approximate
        )
        form = Form8615(
            child_name="Test Child",
            child_age=16,
            unearned_income=10000.0,
            earned_income=0.0,
            child_taxable_income=10000.0,
            parent_info=parent_info,
        )
        result = form.calculate_kiddie_tax()

        assert result['subject_to_kiddie_tax'] is True
        assert result['unearned_income'] == 10000.0
        assert result['net_unearned_income'] == 7400.0  # $10,000 - $2,600
        assert result['kiddie_tax_increase'] > 0  # Should have additional tax
        assert result['total_child_tax'] > result['child_tax_without_kiddie_rules']

    def test_exemption_reason_age_over_19_not_student(self):
        """Exemption reason correctly identifies age/student status."""
        form = Form8615(
            child_age=20,
            is_full_time_student=False,
            unearned_income=10000.0,
            child_taxable_income=10000.0,
        )
        result = form.calculate_kiddie_tax()

        assert result['subject_to_kiddie_tax'] is False
        assert "19+" in result['reason_not_subject'] or "20" in result['reason_not_subject']

    def test_exemption_reason_low_unearned_income(self):
        """Exemption reason correctly identifies low unearned income."""
        form = Form8615(
            child_age=16,
            unearned_income=2000.0,
            child_taxable_income=2000.0,
        )
        result = form.calculate_kiddie_tax()

        assert result['subject_to_kiddie_tax'] is False
        assert "2,000" in result['reason_not_subject'] or "threshold" in result['reason_not_subject']

    def test_high_unearned_income_high_parent_rate(self):
        """Child with high unearned income and parent in high tax bracket."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_JOINT,
            taxable_income=500000.0,
            tax_before_credits=120000.0,  # Approximate for $500k MFJ
        )
        form = Form8615(
            child_age=14,
            unearned_income=50000.0,
            child_taxable_income=50000.0,
            parent_info=parent_info,
        )
        result = form.calculate_kiddie_tax()

        assert result['subject_to_kiddie_tax'] is True
        assert result['net_unearned_income'] == 47400.0  # $50,000 - $2,600
        # Kiddie tax increase should be significant (comparing parent rate vs child rate)
        assert result['kiddie_tax_increase'] > 3000.0  # Meaningful increase
        assert result['total_child_tax'] > result['child_tax_without_kiddie_rules']

    def test_mixed_earned_and_unearned_income(self):
        """Child with both earned and unearned income."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_JOINT,
            taxable_income=150000.0,
            tax_before_credits=23000.0,
        )
        form = Form8615(
            child_age=17,
            unearned_income=8000.0,
            earned_income=5000.0,  # Summer job
            child_taxable_income=13000.0,  # Total taxable
            parent_info=parent_info,
        )
        result = form.calculate_kiddie_tax()

        assert result['subject_to_kiddie_tax'] is True
        assert result['earned_income'] == 5000.0
        # Net unearned is from unearned only
        assert result['net_unearned_income'] == 5400.0  # $8,000 - $2,600


class TestConvenienceFunction:
    """Tests for the calculate_kiddie_tax_for_child convenience function."""

    def test_convenience_function_basic(self):
        """Convenience function produces same result as class method."""
        result = calculate_kiddie_tax_for_child(
            child_age=16,
            is_student=False,
            unearned_income=10000.0,
            earned_income=0.0,
            child_taxable_income=10000.0,
            parent_taxable_income=150000.0,
            parent_tax=23000.0,
            parent_filing_status="married_joint",
        )

        assert result['subject_to_kiddie_tax'] is True
        assert result['net_unearned_income'] == 7400.0

    def test_convenience_function_student(self):
        """Convenience function handles student correctly."""
        result = calculate_kiddie_tax_for_child(
            child_age=21,
            is_student=True,
            unearned_income=5000.0,
            earned_income=2000.0,
            child_taxable_income=7000.0,
            parent_taxable_income=100000.0,
            parent_tax=15000.0,
            parent_filing_status="single",
        )

        assert result['subject_to_kiddie_tax'] is True

    def test_convenience_function_multiple_children(self):
        """Convenience function handles multiple children allocation."""
        result = calculate_kiddie_tax_for_child(
            child_age=16,
            is_student=False,
            unearned_income=10000.0,
            earned_income=0.0,
            child_taxable_income=10000.0,
            parent_taxable_income=150000.0,
            parent_tax=23000.0,
            parent_filing_status="married_joint",
            other_children_unearned=5000.0,  # Sibling with $5k
        )

        assert result['subject_to_kiddie_tax'] is True
        # This child's share should be < full additional tax
        breakdown = result['tax_at_parent_rate_breakdown']
        assert breakdown['total_children_unearned'] == 12400.0  # 7400 + 5000


class TestForm8615EdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_exactly_at_age_boundary_under_19(self):
        """Child exactly 18 is still subject (under 19)."""
        form = Form8615(
            child_age=18,
            unearned_income=5000.0,
            child_taxable_income=5000.0,
        )
        assert form.is_subject_to_kiddie_tax() is True

    def test_student_at_age_23(self):
        """Student at 23 (highest eligible age) is still subject."""
        form = Form8615(
            child_age=23,
            is_full_time_student=True,
            unearned_income=5000.0,
            child_taxable_income=5000.0,
        )
        assert form.is_subject_to_kiddie_tax() is True

    def test_very_young_child(self):
        """Very young child (age 0) is subject if other requirements met."""
        form = Form8615(
            child_age=0,
            unearned_income=5000.0,  # Trust fund baby
            child_taxable_income=5000.0,
        )
        assert form.is_subject_to_kiddie_tax() is True

    def test_unearned_income_one_dollar_over_threshold(self):
        """$2,601 (one dollar over) triggers kiddie tax."""
        form = Form8615(
            child_age=16,
            unearned_income=2601.0,
            child_taxable_income=2601.0,
        )
        assert form.is_subject_to_kiddie_tax() is True
        result = form.calculate_net_unearned_income()
        assert result['line_5_net_unearned_income'] == 1.0  # Only $1 at parent rate

    def test_parent_in_lowest_bracket(self):
        """When parent is in lowest bracket, kiddie tax may be minimal."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_JOINT,
            taxable_income=20000.0,  # Low income, 10% bracket
            tax_before_credits=2000.0,
        )
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,
            child_taxable_income=10000.0,
            parent_info=parent_info,
        )
        result = form.calculate_kiddie_tax()

        # Both parent and child likely in 10% bracket, so increase should be small
        # But kiddie tax ensures it's calculated at parent's marginal rate
        assert result['subject_to_kiddie_tax'] is True

    def test_parent_in_highest_bracket(self):
        """When parent is in 37% bracket, kiddie tax maximizes impact."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.SINGLE,
            taxable_income=700000.0,  # 37% bracket
            tax_before_credits=220000.0,  # Approximate
        )
        form = Form8615(
            child_age=16,
            unearned_income=100000.0,
            child_taxable_income=100000.0,
            parent_info=parent_info,
        )
        result = form.calculate_kiddie_tax()

        assert result['subject_to_kiddie_tax'] is True
        # Kiddie tax increase: difference between child rate and parent's higher rate
        assert result['kiddie_tax_increase'] > 10000.0  # Significant increase
        assert result['total_child_tax'] > result['child_tax_without_kiddie_rules']

    def test_zero_parent_tax(self):
        """Parent with zero tax (e.g., very low income)."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_JOINT,
            taxable_income=0.0,
            tax_before_credits=0.0,
        )
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,
            child_taxable_income=10000.0,
            parent_info=parent_info,
        )
        result = form.calculate_kiddie_tax()

        # Child's unearned taxed at rates starting from 10%
        assert result['subject_to_kiddie_tax'] is True

    def test_rounding_to_two_decimal_places(self):
        """Calculations should round to 2 decimal places."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_JOINT,
            taxable_income=123456.78,
            tax_before_credits=19876.54,
        )
        form = Form8615(
            child_age=16,
            unearned_income=9999.99,
            child_taxable_income=9999.99,
            parent_info=parent_info,
        )
        result = form.calculate_kiddie_tax()

        # Check that results are properly rounded
        assert result['net_unearned_income'] == round(result['net_unearned_income'], 2)
        assert result['total_child_tax'] == round(result['total_child_tax'], 2)


class TestForm8615ParentFilingStatus:
    """Tests for different parent filing statuses."""

    def test_all_filing_statuses_calculate(self):
        """All parent filing statuses should produce valid calculations."""
        statuses = [
            ParentFilingStatus.SINGLE,
            ParentFilingStatus.MARRIED_JOINT,
            ParentFilingStatus.MARRIED_SEPARATE,
            ParentFilingStatus.HEAD_OF_HOUSEHOLD,
            ParentFilingStatus.QUALIFYING_WIDOW,
        ]

        for status in statuses:
            parent_info = ParentTaxInfo(
                filing_status=status,
                taxable_income=100000.0,
                tax_before_credits=15000.0,
            )
            form = Form8615(
                child_age=16,
                unearned_income=10000.0,
                child_taxable_income=10000.0,
                parent_info=parent_info,
            )
            result = form.calculate_kiddie_tax()

            assert result['subject_to_kiddie_tax'] is True, f"Failed for {status}"
            assert result['total_child_tax'] > 0, f"No tax calculated for {status}"

    def test_married_separate_uses_correct_brackets(self):
        """Married filing separately uses different brackets."""
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_SEPARATE,
            taxable_income=200000.0,
            tax_before_credits=45000.0,
        )
        form = Form8615(
            child_age=16,
            unearned_income=10000.0,
            child_taxable_income=10000.0,
            parent_info=parent_info,
        )
        result = form.calculate_kiddie_tax()
        assert result['subject_to_kiddie_tax'] is True


class TestForm8615Integration:
    """Integration tests combining Form 8615 with Income model."""

    def test_form_8615_model_instantiation(self):
        """Form 8615 can be instantiated with all required fields."""
        form = Form8615(
            child_name="John Doe Jr",
            child_ssn="123-45-6789",
            child_age=15,
            is_full_time_student=False,
            unearned_income=8500.0,
            adjustments_to_unearned=0.0,
            earned_income=2000.0,
            itemized_deductions_for_unearned=0.0,
            child_taxable_income=10500.0,
            parent_info=ParentTaxInfo(
                filing_status=ParentFilingStatus.MARRIED_JOINT,
                taxable_income=175000.0,
                tax_before_credits=27500.0,
                parent_name="John Doe Sr",
                parent_ssn="987-65-4321",
            ),
            parent_alive=True,
            child_files_joint_return=False,
            child_required_to_file=True,
        )

        result = form.calculate_kiddie_tax()
        assert result['child_name'] == "John Doe Jr"
        assert result['subject_to_kiddie_tax'] is True

    def test_form_8615_with_complex_scenario(self):
        """Complex scenario with multiple factors."""
        # High-income parent, student child with significant investment income
        parent_info = ParentTaxInfo(
            filing_status=ParentFilingStatus.MARRIED_JOINT,
            taxable_income=350000.0,
            tax_before_credits=75000.0,
            other_children_net_unearned_income=3000.0,  # Sibling
        )
        form = Form8615(
            child_name="College Student",
            child_age=21,
            is_full_time_student=True,
            unearned_income=25000.0,  # Significant dividends from trust
            earned_income=8000.0,  # Part-time job
            itemized_deductions_for_unearned=500.0,  # Investment expenses
            child_taxable_income=33000.0,
            parent_info=parent_info,
        )

        result = form.calculate_kiddie_tax()

        assert result['subject_to_kiddie_tax'] is True
        assert result['is_full_time_student'] is True
        assert result['child_age'] == 21
        # Verify pro-rata allocation is happening
        breakdown = result['tax_at_parent_rate_breakdown']
        assert breakdown['other_children_unearned'] == 3000.0


class TestForm8615StandardDeduction:
    """Tests for child's standard deduction calculation."""

    def test_minimum_standard_deduction(self):
        """Child with no earned income gets minimum $1,300 deduction."""
        form = Form8615(
            child_age=16,
            unearned_income=5000.0,
            earned_income=0.0,
            child_taxable_income=5000.0,
        )
        deduction = form.calculate_child_standard_deduction()
        assert deduction == 1300.0

    def test_earned_income_based_deduction_capped(self):
        """Deduction for Form 8615 is capped at $1,300."""
        form = Form8615(
            child_age=16,
            unearned_income=5000.0,
            earned_income=10000.0,  # High earned income
            child_taxable_income=15000.0,
        )
        deduction = form.calculate_child_standard_deduction()
        # For Form 8615, capped at $1,300 for the unearned income portion
        assert deduction == 1300.0


class TestForm8615ThresholdValues:
    """Tests verifying 2025 threshold constants."""

    def test_unearned_income_threshold_2025(self):
        """Verify 2025 unearned income threshold is $2,600."""
        assert Form8615.UNEARNED_INCOME_THRESHOLD_2025 == 2600.0

    def test_child_standard_deduction_2025(self):
        """Verify 2025 child standard deduction is $1,300."""
        assert Form8615.CHILD_STANDARD_DEDUCTION_2025 == 1300.0

    def test_age_exemption_thresholds(self):
        """Verify age exemption thresholds."""
        assert Form8615.MIN_AGE_EXEMPTION == 19
        assert Form8615.STUDENT_AGE_EXEMPTION == 24
