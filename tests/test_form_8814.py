"""
Test suite for Form 8814 - Parent's Election To Report Child's Interest and Dividends.

Tests cover:
- Child eligibility requirements
- Income calculation and base amount exclusion
- Tax at 10% rate
- Amount to include on parent's return
- Multiple children
"""

import pytest
from src.models.form_8814 import (
    Form8814,
    ChildIncome,
    calculate_parent_election,
)


class TestChildEligibility:
    """Tests for child eligibility requirements."""

    def test_child_under_19_qualifies(self):
        """Child under 19 qualifies."""
        child = ChildIncome(
            child_name="Child",
            child_age=14,
            taxable_interest=2000.0,
        )

        assert child.qualifies_for_8814() is True

    def test_child_19_or_over_not_student(self):
        """Child 19+ without student status doesn't qualify."""
        child = ChildIncome(
            child_name="Adult Child",
            child_age=19,
            is_full_time_student=False,
            taxable_interest=2000.0,
        )

        assert child.qualifies_for_8814() is False

    def test_student_under_24_qualifies(self):
        """Full-time student under 24 qualifies."""
        child = ChildIncome(
            child_name="Student",
            child_age=21,
            is_full_time_student=True,
            taxable_interest=2000.0,
        )

        assert child.qualifies_for_8814() is True

    def test_student_at_age_limit_not_qualify(self):
        """Student at age 23 (will turn 24) qualifies, but 24+ doesn't."""
        # Age 23 student still qualifies
        child_23 = ChildIncome(
            child_name="Student 23",
            child_age=23,
            is_full_time_student=True,
            taxable_interest=2000.0,
        )
        assert child_23.qualifies_for_8814() is True

        # Model constraint is le=23, so we test the boundary
        # A 23-year-old student qualifies (under 24)

    def test_income_over_limit_not_qualify(self):
        """Income over $12,500 doesn't qualify."""
        child = ChildIncome(
            child_name="High Income Child",
            child_age=15,
            taxable_interest=8000.0,
            ordinary_dividends=5000.0,  # Total $13,000
        )

        assert child.qualifies_for_8814() is False

    def test_withholding_disqualifies(self):
        """Federal withholding disqualifies."""
        child = ChildIncome(
            child_name="Child",
            child_age=12,
            taxable_interest=2000.0,
            federal_tax_withheld=100.0,
        )

        assert child.qualifies_for_8814() is False


class TestIncomeCalculation:
    """Tests for child income calculation."""

    def test_interest_only(self):
        """Child with only interest income."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child",
                    child_age=10,
                    taxable_interest=3000.0,
                )
            ]
        )
        result = form.calculate_form_8814()

        child_calc = result['child_calculations'][0]
        assert child_calc['line_4_total_income'] == 3000.0

    def test_dividends_only(self):
        """Child with only dividend income."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child",
                    child_age=12,
                    ordinary_dividends=2500.0,
                    qualified_dividends=2000.0,
                )
            ]
        )
        result = form.calculate_form_8814()

        child_calc = result['child_calculations'][0]
        assert child_calc['line_2a_ordinary_dividends'] == 2500.0
        assert child_calc['line_2b_qualified_dividends'] == 2000.0

    def test_capital_gain_distributions(self):
        """Child with capital gain distributions."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child",
                    child_age=14,
                    ordinary_dividends=1000.0,
                    capital_gain_distributions=500.0,
                )
            ]
        )
        result = form.calculate_form_8814()

        child_calc = result['child_calculations'][0]
        assert child_calc['line_3_capital_gains'] == 500.0

    def test_gross_income_calculation(self):
        """Child gross income calculation."""
        child = ChildIncome(
            child_name="Child",
            child_age=10,
            taxable_interest=1000.0,
            ordinary_dividends=2000.0,
            capital_gain_distributions=500.0,
        )

        assert child.gross_income() == 3500.0


class TestBaseAmountExclusion:
    """Tests for base amount and tax calculation."""

    def test_under_base_amount(self):
        """Income under $1,300 base amount."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child",
                    child_age=10,
                    taxable_interest=1000.0,
                )
            ]
        )
        result = form.calculate_form_8814()

        child_calc = result['child_calculations'][0]
        assert child_calc['line_6_over_base'] == 0.0
        assert child_calc['child_tax'] == 0.0
        assert child_calc['amount_to_include'] == 0.0

    def test_in_10_percent_tier(self):
        """Income in 10% tier ($1,300-$2,600)."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child",
                    child_age=12,
                    taxable_interest=2000.0,
                )
            ]
        )
        result = form.calculate_form_8814()

        child_calc = result['child_calculations'][0]
        # Over base: $2,000 - $1,300 = $700
        # Tax: $700 × 10% = $70
        # Amount to include: $0 (still under $2,600 total exclusion)
        assert child_calc['line_6_over_base'] == 700.0
        assert child_calc['child_tax'] == 70.0
        assert child_calc['amount_to_include'] == 0.0

    def test_over_10_percent_tier(self):
        """Income over $2,600 threshold."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child",
                    child_age=14,
                    taxable_interest=4000.0,
                )
            ]
        )
        result = form.calculate_form_8814()

        child_calc = result['child_calculations'][0]
        # Over base: $4,000 - $1,300 = $2,700
        # Tax on first $1,300 of over-base at 10%: $130
        # Amount to include: $4,000 - $2,600 = $1,400
        assert child_calc['line_7_tax_at_10_pct'] == 130.0
        assert child_calc['amount_to_include'] == 1400.0


class TestMultipleChildren:
    """Tests for multiple children."""

    def test_two_qualifying_children(self):
        """Two qualifying children."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child 1",
                    child_age=10,
                    taxable_interest=3000.0,
                ),
                ChildIncome(
                    child_name="Child 2",
                    child_age=12,
                    ordinary_dividends=2500.0,
                ),
            ]
        )
        result = form.calculate_form_8814()

        assert result['children_count'] == 2
        assert result['qualifying_children'] == 2
        # Both children have income to include
        assert result['total_to_include_in_income'] > 0

    def test_one_qualifying_one_not(self):
        """One qualifying child, one not."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Qualifying",
                    child_age=10,
                    taxable_interest=3000.0,
                ),
                ChildIncome(
                    child_name="Not Qualifying",
                    child_age=20,  # Too old, not student
                    taxable_interest=2000.0,
                ),
            ]
        )
        result = form.calculate_form_8814()

        assert result['qualifying_children'] == 1

    def test_aggregate_totals(self):
        """Aggregate totals from multiple children."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child 1",
                    child_age=10,
                    taxable_interest=4000.0,
                ),
                ChildIncome(
                    child_name="Child 2",
                    child_age=14,
                    ordinary_dividends=3500.0,
                    qualified_dividends=2000.0,
                ),
            ]
        )
        result = form.calculate_form_8814()

        # Total tax from both children
        assert result['total_child_tax'] > 0
        assert result['total_to_include_in_income'] > 0


class TestQualifiedDividendsAllocation:
    """Tests for qualified dividends allocation."""

    def test_qualified_dividends_proportionate(self):
        """Qualified dividends allocated proportionately."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child",
                    child_age=14,
                    ordinary_dividends=4000.0,
                    qualified_dividends=3000.0,
                )
            ]
        )
        result = form.calculate_form_8814()

        child_calc = result['child_calculations'][0]
        # Amount to include should have proportionate QD
        assert child_calc['qualified_dividends_to_include'] > 0


class TestFormComparison:
    """Tests for Form 8814 vs Form 8615 comparison."""

    def test_comparison_method(self):
        """Compare Form 8814 with Form 8615."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child",
                    child_age=14,
                    taxable_interest=5000.0,
                )
            ]
        )
        comparison = form.compare_with_8615(parent_marginal_rate=0.24)

        assert 'form_8814_total_tax' in comparison
        assert 'form_8615_estimated_tax' in comparison
        assert 'recommendation' in comparison


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_basic(self):
        """Calculate parent election with convenience function."""
        result = calculate_parent_election(
            child_interest=3000.0,
            child_dividends=0.0,
            child_age=12,
        )

        assert result['qualifying_children'] == 1
        # $3,000 - $2,600 excluded = $400 to include
        assert result['total_to_include_in_income'] == 400.0

    def test_convenience_function_with_dividends(self):
        """Parent election with interest and dividends."""
        result = calculate_parent_election(
            child_interest=2000.0,
            child_dividends=2000.0,
            child_qualified_dividends=1500.0,
            child_age=10,
        )

        # $4,000 total - $2,600 excluded = $1,400 to include
        assert result['total_to_include_in_income'] == 1400.0

    def test_convenience_function_student(self):
        """Parent election for full-time student."""
        result = calculate_parent_election(
            child_interest=3000.0,
            child_dividends=0.0,
            child_age=21,
            is_student=True,
        )

        assert result['qualifying_children'] == 1

    def test_convenience_function_not_eligible(self):
        """Non-eligible child."""
        result = calculate_parent_election(
            child_interest=15000.0,  # Over $12,500 limit
            child_dividends=0.0,
            child_age=12,
        )

        assert result['qualifying_children'] == 0


class TestSummaryMethod:
    """Tests for summary method."""

    def test_get_summary(self):
        """Get Form 8814 summary."""
        form = Form8814(
            children=[
                ChildIncome(
                    child_name="Child",
                    child_age=10,
                    taxable_interest=4000.0,
                )
            ]
        )

        summary = form.get_form_8814_summary()

        assert 'children_reported' in summary
        assert 'income_to_include' in summary
        assert 'tax_from_children' in summary
