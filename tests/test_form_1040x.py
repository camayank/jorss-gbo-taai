"""
Test suite for Form 1040-X - Amended U.S. Individual Income Tax Return.

Tests cover:
- Line item changes (original vs. corrected)
- Tax calculation changes
- Refund due calculation
- Amount owed calculation
- Complete amended return calculation
- Convenience function
"""

import pytest
from models.form_1040x import (
    Form1040X,
    Form1040X_Line,
    FilingStatusChange,
    DependentChange,
    AmendmentReason,
    create_amended_return,
)


class TestForm1040XLineItem:
    """Tests for individual line item changes."""

    def test_line_corrected_amount_increase(self):
        """Positive net change increases corrected amount."""
        line = Form1040X_Line(
            line_number="1",
            description="AGI",
            original_amount=50000.0,
            net_change=5000.0,
        )

        assert line.corrected_amount == 55000.0

    def test_line_corrected_amount_decrease(self):
        """Negative net change decreases corrected amount."""
        line = Form1040X_Line(
            line_number="1",
            description="AGI",
            original_amount=50000.0,
            net_change=-5000.0,
        )

        assert line.corrected_amount == 45000.0

    def test_line_no_change(self):
        """Zero net change means no change."""
        line = Form1040X_Line(
            line_number="1",
            description="AGI",
            original_amount=50000.0,
            net_change=0.0,
        )

        assert line.corrected_amount == 50000.0


class TestForm1040XRefundCalculation:
    """Tests for refund due calculations."""

    def test_refund_due_increased_payments(self):
        """Increased payments result in refund due."""
        form = Form1040X(
            tax_year=2024,
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                description="Total tax",
                original_amount=10000.0,
                net_change=0.0,  # Tax unchanged
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                description="Total payments",
                original_amount=10000.0,
                net_change=2000.0,  # Found $2k more withholding
            ),
        )

        result = form.calculate_refund_or_amount_owed()

        assert result['refund_due'] == 2000.0
        assert result['amount_owed'] == 0.0

    def test_refund_due_decreased_tax(self):
        """Decreased tax results in refund due."""
        form = Form1040X(
            tax_year=2024,
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                description="Total tax",
                original_amount=10000.0,
                net_change=-3000.0,  # Tax decreased by $3k
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                description="Total payments",
                original_amount=10000.0,
                net_change=0.0,
            ),
        )

        result = form.calculate_refund_or_amount_owed()

        assert result['refund_due'] == 3000.0

    def test_refund_due_accounting_for_prior_refund(self):
        """Prior refund received is deducted from new refund."""
        form = Form1040X(
            tax_year=2024,
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                description="Total tax",
                original_amount=8000.0,
                net_change=-2000.0,  # Tax now $6k
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                description="Total payments",
                original_amount=10000.0,
                net_change=0.0,  # Still $10k
            ),
            line_15_refund_received=2000.0,  # Already got $2k refund
        )

        result = form.calculate_refund_or_amount_owed()

        # Corrected: $10k payments - $6k tax = $4k overpayment
        # Already received $2k, so $2k additional refund due
        assert result['refund_due'] == 2000.0


class TestForm1040XAmountOwed:
    """Tests for additional amount owed calculations."""

    def test_amount_owed_increased_tax(self):
        """Increased tax results in amount owed."""
        form = Form1040X(
            tax_year=2024,
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                description="Total tax",
                original_amount=10000.0,
                net_change=3000.0,  # Tax increased to $13k
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                description="Total payments",
                original_amount=10000.0,
                net_change=0.0,
            ),
        )

        result = form.calculate_refund_or_amount_owed()

        assert result['amount_owed'] == 3000.0
        assert result['refund_due'] == 0.0

    def test_amount_owed_missed_income(self):
        """Missed income increases tax owed."""
        form = Form1040X(
            tax_year=2024,
            line_1_agi=Form1040X_Line(
                line_number="1",
                description="AGI",
                original_amount=50000.0,
                net_change=10000.0,  # Found $10k missed income
            ),
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                description="Total tax",
                original_amount=5000.0,
                net_change=2200.0,  # Tax increases by $2,200
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                description="Total payments",
                original_amount=5000.0,
                net_change=0.0,
            ),
        )

        result = form.calculate_refund_or_amount_owed()

        assert result['amount_owed'] == 2200.0

    def test_amount_owed_after_refund_received(self):
        """If refund was received but tax increases, must repay."""
        form = Form1040X(
            tax_year=2024,
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                description="Total tax",
                original_amount=8000.0,
                net_change=3000.0,  # Tax now $11k
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                description="Total payments",
                original_amount=10000.0,
                net_change=0.0,  # Still $10k
            ),
            line_15_refund_received=2000.0,  # Got $2k refund
        )

        result = form.calculate_refund_or_amount_owed()

        # Corrected: $10k payments - $11k tax = -$1k (owe)
        # Plus repay $2k refund received = $3k owed
        assert result['amount_owed'] == 3000.0


class TestForm1040XCompleteCalculation:
    """Tests for complete Form 1040-X calculation."""

    def test_complete_amended_return(self):
        """Complete amended return calculation."""
        form = Form1040X(
            taxpayer_name="John Smith",
            tax_year=2024,
            line_1_agi=Form1040X_Line(
                line_number="1",
                description="AGI",
                original_amount=75000.0,
                net_change=5000.0,
            ),
            line_2_itemized_or_standard=Form1040X_Line(
                line_number="2",
                description="Deductions",
                original_amount=14600.0,
                net_change=0.0,
            ),
            line_5_tax=Form1040X_Line(
                line_number="5",
                description="Tax",
                original_amount=8500.0,
                net_change=1100.0,
            ),
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                description="Total tax",
                original_amount=8500.0,
                net_change=1100.0,
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                description="Total payments",
                original_amount=9000.0,
                net_change=0.0,
            ),
            amendment_reasons=[AmendmentReason.MISSED_INCOME],
            explanation="Forgot to report 1099-INT interest income",
        )

        result = form.calculate_amended_return()

        assert result['taxpayer_name'] == "John Smith"
        assert result['tax_year'] == 2024
        assert result['agi_change'] == 5000.0
        assert result['total_tax_change'] == 1100.0
        assert result['corrected_agi'] == 80000.0
        assert result['corrected_total_tax'] == 9600.0
        assert 'missed_income' in result['amendment_reasons']

    def test_filing_status_change(self):
        """Track filing status change."""
        form = Form1040X(
            tax_year=2024,
            filing_status_change=FilingStatusChange(
                original_status="single",
                amended_status="head_of_household",
                status_changed=True,
            ),
        )

        result = form.calculate_amended_return()
        assert result['filing_status_changed'] is True


class TestForm1040XConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_refund(self):
        """Convenience function calculates refund scenario."""
        result = create_amended_return(
            tax_year=2024,
            original_agi=60000.0,
            original_tax=7000.0,
            original_payments=7500.0,
            corrected_agi=60000.0,
            corrected_tax=6000.0,  # Found missed credit
            corrected_payments=7500.0,
            refund_received=500.0,  # Original refund
            explanation="Claimed education credit not on original",
        )

        # Corrected: $7,500 - $6,000 = $1,500 overpayment
        # Already got $500, so $1,000 additional refund
        assert result['refund_or_owed']['refund_due'] == 1000.0

    def test_convenience_function_owed(self):
        """Convenience function calculates amount owed scenario."""
        result = create_amended_return(
            tax_year=2024,
            original_agi=50000.0,
            original_tax=5000.0,
            original_payments=5500.0,
            corrected_agi=55000.0,  # Missed income
            corrected_tax=6200.0,
            corrected_payments=5500.0,
            refund_received=500.0,
            explanation="Added unreported 1099 income",
        )

        # Corrected: $5,500 - $6,200 = -$700 (owe)
        # Plus repay $500 refund = $1,200 owed
        assert result['refund_or_owed']['amount_owed'] == 1200.0

    def test_convenience_function_with_deductions(self):
        """Convenience function with deduction changes."""
        result = create_amended_return(
            tax_year=2024,
            original_agi=80000.0,
            original_tax=10000.0,
            original_payments=10000.0,
            corrected_agi=80000.0,
            corrected_tax=9000.0,
            corrected_payments=10000.0,
            original_deductions=14600.0,
            corrected_deductions=20000.0,  # Itemizing instead
        )

        # Tax decreased, so refund due
        assert result['refund_or_owed']['refund_due'] == 1000.0


class TestForm1040XSummary:
    """Tests for summary methods."""

    def test_get_form_1040x_summary(self):
        """Summary method returns correct fields."""
        form = Form1040X(
            tax_year=2024,
            line_1_agi=Form1040X_Line(
                line_number="1",
                original_amount=50000.0,
                net_change=5000.0,
            ),
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                original_amount=5000.0,
                net_change=1000.0,
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                original_amount=5000.0,
                net_change=0.0,
            ),
        )

        summary = form.get_form_1040x_summary()

        assert 'tax_year' in summary
        assert 'agi_change' in summary
        assert 'tax_change' in summary
        assert 'refund_due' in summary
        assert 'amount_owed' in summary

        assert summary['tax_year'] == 2024
        assert summary['agi_change'] == 5000.0


class TestForm1040XEdgeCases:
    """Tests for edge cases."""

    def test_no_changes(self):
        """No changes results in no refund or amount owed."""
        form = Form1040X(
            tax_year=2024,
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                original_amount=5000.0,
                net_change=0.0,
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                original_amount=5000.0,
                net_change=0.0,
            ),
        )

        result = form.calculate_refund_or_amount_owed()

        assert result['refund_due'] == 0.0
        assert result['amount_owed'] == 0.0

    def test_exact_break_even(self):
        """Changes result in exact break-even."""
        form = Form1040X(
            tax_year=2024,
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                original_amount=5000.0,
                net_change=500.0,  # Tax increases
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                original_amount=5000.0,
                net_change=500.0,  # Payments also increase
            ),
        )

        result = form.calculate_refund_or_amount_owed()

        assert result['refund_due'] == 0.0
        assert result['amount_owed'] == 0.0

    def test_large_refund_due(self):
        """Large refund due scenario."""
        form = Form1040X(
            tax_year=2024,
            line_9_total_tax=Form1040X_Line(
                line_number="9",
                original_amount=20000.0,
                net_change=-8000.0,  # Major tax reduction
            ),
            line_13_total_payments=Form1040X_Line(
                line_number="13",
                original_amount=20000.0,
                net_change=0.0,
            ),
        )

        result = form.calculate_refund_or_amount_owed()

        assert result['refund_due'] == 8000.0


class TestForm1040XAmendmentReasons:
    """Tests for amendment reason tracking."""

    def test_multiple_amendment_reasons(self):
        """Multiple amendment reasons can be specified."""
        form = Form1040X(
            tax_year=2024,
            amendment_reasons=[
                AmendmentReason.MISSED_INCOME,
                AmendmentReason.MISSED_DEDUCTION,
            ],
            explanation="Added unreported income and claimed education credit",
        )

        result = form.calculate_amended_return()

        assert len(result['amendment_reasons']) == 2
        assert 'missed_income' in result['amendment_reasons']
        assert 'missed_deduction' in result['amendment_reasons']
