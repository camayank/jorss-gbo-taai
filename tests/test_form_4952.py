"""
Test suite for Form 4952 - Investment Interest Expense Deduction.

Tests cover:
- Investment income calculation
- Net investment income
- Investment interest deduction limitation
- Carryforward of disallowed interest
- Capital gains/qualified dividend elections
- Convenience function
"""

import pytest
from models.form_4952 import (
    Form4952,
    InvestmentIncomeElection,
    calculate_investment_interest_deduction,
)


class TestForm4952BasicDeduction:
    """Tests for basic investment interest deduction."""

    def test_deduction_limited_to_investment_income(self):
        """Deduction limited to net investment income."""
        form = Form4952(
            investment_interest_paid=10000.0,
            gross_investment_income=5000.0,
        )
        result = form.calculate_deduction()

        assert result['line_8_allowable_deduction'] == 5000.0
        assert result['carryforward_to_next_year'] == 5000.0

    def test_full_deduction_when_income_exceeds(self):
        """Full deduction when investment income exceeds interest."""
        form = Form4952(
            investment_interest_paid=5000.0,
            gross_investment_income=10000.0,
        )
        result = form.calculate_deduction()

        assert result['line_8_allowable_deduction'] == 5000.0
        assert result['carryforward_to_next_year'] == 0.0

    def test_zero_investment_income_no_deduction(self):
        """Zero investment income means no deduction."""
        form = Form4952(
            investment_interest_paid=10000.0,
            gross_investment_income=0.0,
        )
        result = form.calculate_deduction()

        assert result['line_8_allowable_deduction'] == 0.0
        assert result['carryforward_to_next_year'] == 10000.0

    def test_carryforward_from_prior_year(self):
        """Prior year carryforward is included."""
        form = Form4952(
            investment_interest_paid=3000.0,
            prior_year_carryforward=2000.0,
            gross_investment_income=4000.0,
        )
        result = form.calculate_deduction()

        # Total interest: $5,000
        # Net investment income: $4,000
        # Allowable: $4,000
        # Carryforward: $1,000
        assert result['line_3_total_investment_interest'] == 5000.0
        assert result['line_8_allowable_deduction'] == 4000.0
        assert result['carryforward_to_next_year'] == 1000.0


class TestForm4952InvestmentIncome:
    """Tests for investment income calculation."""

    def test_gross_investment_income_components(self):
        """Gross investment income includes various sources."""
        form = Form4952(
            investment_interest_paid=5000.0,
            gross_investment_income=8000.0,
            net_gain_form_4797=2000.0,
        )
        income = form.calculate_investment_income()

        # Total: $8,000 + $2,000 = $10,000
        assert income['total_investment_income'] == 10000.0

    def test_qualified_dividends_excluded_by_default(self):
        """Qualified dividends excluded unless elected."""
        form = Form4952(
            investment_interest_paid=5000.0,
            gross_investment_income=10000.0,
            qualified_dividends_in_line_4a=3000.0,
        )
        income = form.calculate_investment_income()

        # Line 4c: $10,000 - $3,000 = $7,000
        assert income['line_4c_income_less_qualified'] == 7000.0
        assert income['total_investment_income'] == 7000.0

    def test_investment_expenses_reduce_net_income(self):
        """Investment expenses reduce net investment income."""
        form = Form4952(
            investment_interest_paid=5000.0,
            gross_investment_income=10000.0,
            investment_expenses=2000.0,
        )
        result = form.calculate_net_investment_income()

        assert result['net_investment_income'] == 8000.0


class TestForm4952Elections:
    """Tests for capital gains/qualified dividend elections."""

    def test_elect_capital_gains_as_investment_income(self):
        """Election to treat capital gains as investment income."""
        election = InvestmentIncomeElection(
            elect_capital_gains=True,
            capital_gains_amount=5000.0,
        )
        form = Form4952(
            investment_interest_paid=10000.0,
            gross_investment_income=3000.0,
            net_capital_gain_investment=5000.0,
            election=election,
        )
        result = form.calculate_deduction()

        # With election, investment income = $3,000 + $5,000 = $8,000
        assert result['elected_capital_gains'] == 5000.0
        assert result['line_8_allowable_deduction'] == 8000.0

    def test_elect_qualified_dividends_as_investment_income(self):
        """Election to treat qualified dividends as investment income."""
        election = InvestmentIncomeElection(
            elect_qualified_dividends=True,
            qualified_dividends_amount=4000.0,
        )
        form = Form4952(
            investment_interest_paid=10000.0,
            gross_investment_income=8000.0,
            qualified_dividends_in_line_4a=4000.0,
            election=election,
        )
        result = form.calculate_deduction()

        # Without election: $8,000 - $4,000 = $4,000
        # With election: $8,000 (qualified divs restored)
        assert result['elected_qualified_dividends'] == 4000.0
        assert result['gross_investment_income'] == 8000.0

    def test_election_limited_to_actual_gains(self):
        """Election amount limited to actual capital gains."""
        election = InvestmentIncomeElection(
            elect_capital_gains=True,
            capital_gains_amount=10000.0,  # More than actual
        )
        form = Form4952(
            investment_interest_paid=15000.0,
            gross_investment_income=5000.0,
            net_capital_gain_investment=3000.0,  # Only $3k actual
            election=election,
        )
        result = form.calculate_deduction()

        # Limited to actual $3,000
        assert result['elected_capital_gains'] == 3000.0

    def test_no_election_no_capital_gains_included(self):
        """Without election, capital gains not included."""
        form = Form4952(
            investment_interest_paid=10000.0,
            gross_investment_income=5000.0,
            net_capital_gain_investment=5000.0,
            # No election
        )
        income = form.calculate_investment_income()

        assert income['line_4g_elected_capital_gains'] == 0.0


class TestForm4952EdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_interest_paid_no_deduction(self):
        """No deduction when no interest paid."""
        form = Form4952(
            investment_interest_paid=0.0,
            gross_investment_income=10000.0,
        )
        result = form.calculate_deduction()

        assert result['line_8_allowable_deduction'] == 0.0

    def test_negative_net_income_no_deduction(self):
        """Negative net investment income means no deduction."""
        form = Form4952(
            investment_interest_paid=5000.0,
            gross_investment_income=1000.0,
            investment_expenses=2000.0,  # Expenses > income
        )
        result = form.calculate_deduction()

        # Net investment income is floored at 0
        assert result['line_6_net_investment_income'] == 0.0
        assert result['line_8_allowable_deduction'] == 0.0
        assert result['carryforward_to_next_year'] == 5000.0

    def test_collectibles_excluded_from_election(self):
        """Collectibles gains at 28% rate excluded from election."""
        election = InvestmentIncomeElection(
            elect_capital_gains=True,
            capital_gains_amount=10000.0,
        )
        form = Form4952(
            investment_interest_paid=15000.0,
            gross_investment_income=5000.0,
            net_capital_gain_investment=8000.0,
            capital_gain_collectibles=3000.0,  # $3k is collectibles
            election=election,
        )
        result = form.calculate_deduction()

        # Max electable: $8,000 - $3,000 = $5,000
        assert result['elected_capital_gains'] == 5000.0

    def test_exact_match_no_carryforward(self):
        """Interest exactly equals income, no carryforward."""
        form = Form4952(
            investment_interest_paid=5000.0,
            gross_investment_income=5000.0,
        )
        result = form.calculate_deduction()

        assert result['line_8_allowable_deduction'] == 5000.0
        assert result['carryforward_to_next_year'] == 0.0


class TestForm4952CompleteCalculation:
    """Tests for complete Form 4952 calculation."""

    def test_comprehensive_calculation(self):
        """Full calculation with all components."""
        election = InvestmentIncomeElection(
            elect_capital_gains=True,
            capital_gains_amount=3000.0,
        )
        form = Form4952(
            investment_interest_paid=15000.0,
            prior_year_carryforward=2000.0,
            gross_investment_income=12000.0,
            qualified_dividends_in_line_4a=2000.0,
            net_gain_form_4797=1000.0,
            net_capital_gain_investment=5000.0,
            investment_expenses=1500.0,
            election=election,
        )
        result = form.calculate_deduction()

        # Total interest: $15,000 + $2,000 = $17,000
        assert result['line_3_total_investment_interest'] == 17000.0

        # Investment income calculated with election
        assert result['gross_investment_income'] > 0
        assert result['line_6_net_investment_income'] > 0

        # Deduction limited
        assert result['line_8_allowable_deduction'] <= result['line_3_total_investment_interest']


class TestForm4952ConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_basic(self):
        """Convenience function calculates correctly."""
        result = calculate_investment_interest_deduction(
            interest_paid=5000.0,
            gross_investment_income=10000.0,
        )

        assert result['line_8_allowable_deduction'] == 5000.0

    def test_convenience_function_with_carryforward(self):
        """Convenience function handles prior carryforward."""
        result = calculate_investment_interest_deduction(
            interest_paid=5000.0,
            prior_carryforward=3000.0,
            gross_investment_income=6000.0,
        )

        # Total: $8,000 interest, $6,000 income
        assert result['line_3_total_investment_interest'] == 8000.0
        assert result['line_8_allowable_deduction'] == 6000.0
        assert result['carryforward_to_next_year'] == 2000.0

    def test_convenience_function_with_elections(self):
        """Convenience function handles elections."""
        result = calculate_investment_interest_deduction(
            interest_paid=10000.0,
            gross_investment_income=3000.0,
            capital_gains=5000.0,
            elect_capital_gains=True,
        )

        assert result['elected_capital_gains'] == 5000.0
        assert result['line_8_allowable_deduction'] == 8000.0


class TestForm4952SummaryMethod:
    """Tests for summary method."""

    def test_get_form_4952_summary(self):
        """Summary method returns correct fields."""
        form = Form4952(
            investment_interest_paid=8000.0,
            prior_year_carryforward=2000.0,
            gross_investment_income=7000.0,
        )
        summary = form.get_form_4952_summary()

        assert 'total_investment_interest' in summary
        assert 'net_investment_income' in summary
        assert 'allowable_deduction' in summary
        assert 'carryforward' in summary

        assert summary['total_investment_interest'] == 10000.0
        assert summary['allowable_deduction'] == 7000.0
        assert summary['carryforward'] == 3000.0


class TestForm4952Integration:
    """Integration tests for Form 4952."""

    def test_margin_interest_deduction_scenario(self):
        """Typical margin interest scenario."""
        # Investor has $8,000 margin interest
        # Investment income: $3,000 dividends + $2,000 interest + $1,000 gains
        form = Form4952(
            investment_interest_paid=8000.0,
            gross_investment_income=5000.0,  # Non-qualified dividends + interest
            qualified_dividends_in_line_4a=0.0,  # Already excluded
            net_capital_gain_investment=1000.0,  # Would be taxed at cap gains rate
        )
        result = form.calculate_deduction()

        # Without electing gains: $5,000 deduction, $3,000 carryforward
        assert result['line_8_allowable_deduction'] == 5000.0
        assert result['carryforward_to_next_year'] == 3000.0

    def test_investment_advisor_fees_scenario(self):
        """Investment advisor fees reduce net investment income."""
        form = Form4952(
            investment_interest_paid=10000.0,
            gross_investment_income=15000.0,
            investment_expenses=3000.0,  # Advisor fees
        )
        result = form.calculate_deduction()

        # Net investment income: $15,000 - $3,000 = $12,000
        assert result['line_6_net_investment_income'] == 12000.0
        # Full deduction possible
        assert result['line_8_allowable_deduction'] == 10000.0
