"""
Tests for Educator Expense Deduction Cap per IRC §62(a)(2)(D).

Limits:
- Single educator: $300 maximum
- MFJ (two educators): $600 maximum ($300 each)
"""

import pytest
from models.deductions import Deductions


class TestEducatorExpenseCap:
    """Test educator expense cap enforcement."""

    def test_single_under_cap(self):
        """Single filer under $300 gets full deduction."""
        deductions = Deductions(educator_expenses=250.0)
        deductions_zero = Deductions(educator_expenses=0.0)

        total = deductions.get_total_adjustments(filing_status="single")
        total_zero = deductions_zero.get_total_adjustments(filing_status="single")

        assert total - total_zero == pytest.approx(250.0, rel=0.01)

    def test_single_at_cap(self):
        """Single filer at $300 gets full deduction."""
        deductions = Deductions(educator_expenses=300.0)
        deductions_zero = Deductions(educator_expenses=0.0)

        total = deductions.get_total_adjustments(filing_status="single")
        total_zero = deductions_zero.get_total_adjustments(filing_status="single")

        assert total - total_zero == pytest.approx(300.0, rel=0.01)

    def test_single_over_cap(self):
        """Single filer over $300 is capped at $300."""
        deductions = Deductions(educator_expenses=500.0)
        deductions_at_cap = Deductions(educator_expenses=300.0)

        total_over = deductions.get_total_adjustments(filing_status="single")
        total_at_cap = deductions_at_cap.get_total_adjustments(filing_status="single")

        assert total_over == pytest.approx(total_at_cap, rel=0.01)

    def test_mfj_under_cap(self):
        """MFJ under $600 gets full deduction."""
        deductions = Deductions(educator_expenses=500.0)
        deductions_zero = Deductions(educator_expenses=0.0)

        total = deductions.get_total_adjustments(filing_status="married_joint")
        total_zero = deductions_zero.get_total_adjustments(filing_status="married_joint")

        assert total - total_zero == pytest.approx(500.0, rel=0.01)

    def test_mfj_at_cap(self):
        """MFJ at $600 gets full deduction."""
        deductions = Deductions(educator_expenses=600.0)
        deductions_zero = Deductions(educator_expenses=0.0)

        total = deductions.get_total_adjustments(filing_status="married_joint")
        total_zero = deductions_zero.get_total_adjustments(filing_status="married_joint")

        assert total - total_zero == pytest.approx(600.0, rel=0.01)

    def test_mfj_over_cap(self):
        """MFJ over $600 is capped at $600."""
        deductions = Deductions(educator_expenses=1000.0)
        deductions_at_cap = Deductions(educator_expenses=600.0)

        total_over = deductions.get_total_adjustments(filing_status="married_joint")
        total_at_cap = deductions_at_cap.get_total_adjustments(filing_status="married_joint")

        assert total_over == pytest.approx(total_at_cap, rel=0.01)

    def test_zero_expenses(self):
        """Zero educator expenses results in zero educator deduction."""
        deductions = Deductions(educator_expenses=0.0)
        deductions_none = Deductions()

        total = deductions.get_total_adjustments(filing_status="single")
        total_none = deductions_none.get_total_adjustments(filing_status="single")

        assert total == pytest.approx(total_none, rel=0.01)


class TestEducatorExpenseExcess:
    """Test helper method for reporting excess to user."""

    def test_get_excess_single_over(self):
        """Calculate excess over cap for single filer."""
        deductions = Deductions(educator_expenses=450.0)
        excess = deductions.get_educator_expense_excess(filing_status="single")
        assert excess == pytest.approx(150.0, rel=0.01)

    def test_get_excess_single_under(self):
        """No excess when under cap."""
        deductions = Deductions(educator_expenses=200.0)
        excess = deductions.get_educator_expense_excess(filing_status="single")
        assert excess == 0.0

    def test_get_excess_mfj_over(self):
        """Calculate excess over cap for MFJ."""
        deductions = Deductions(educator_expenses=800.0)
        excess = deductions.get_educator_expense_excess(filing_status="married_joint")
        assert excess == pytest.approx(200.0, rel=0.01)
