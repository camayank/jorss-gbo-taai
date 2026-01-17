"""
Tests for Form 1040-ES - Estimated Tax for Individuals

Comprehensive test suite covering:
- Estimated tax worksheet calculations
- Safe harbor rules (90%/100%/110%)
- Quarterly payment scheduling
- Payment tracking and recording
- Underpayment penalty estimation
- Annualized income method
"""

import pytest
from datetime import date
from src.models.form_1040_es import (
    Form1040ES,
    Form1040ESWorksheet,
    EstimatedTaxPayment,
    Quarter,
    PaymentMethod,
    calculate_estimated_tax,
    calculate_penalty_estimate,
)


class TestForm1040ESWorksheetBasic:
    """Test basic worksheet calculations."""

    def test_taxable_income_calculation(self):
        """Test taxable income calculation."""
        worksheet = Form1040ESWorksheet(
            line_1_expected_agi=150000,
            line_2_deductions=30000,
        )
        assert worksheet.line_3_taxable_income == 120000

    def test_taxable_income_no_negative(self):
        """Test taxable income doesn't go negative."""
        worksheet = Form1040ESWorksheet(
            line_1_expected_agi=20000,
            line_2_deductions=30000,
        )
        assert worksheet.line_3_taxable_income == 0

    def test_total_tax_liability(self):
        """Test total tax liability calculation."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=25000,
            line_5_amt=0,
            line_7_se_tax=5000,
            line_8_other_taxes=1000,
        )
        # 25000 + 5000 + 1000 = 31000
        assert worksheet.line_9_total_tax_liability == 31000

    def test_net_tax_after_credits(self):
        """Test net tax after credits."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=30000,
            line_7_se_tax=5000,
            line_10_credits=8000,
        )
        # (30000 + 5000) - 8000 = 27000
        assert worksheet.line_11_net_tax == 27000

    def test_current_year_tax_with_refundable_credits(self):
        """Test current year tax with refundable credits."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=20000,
            line_10_credits=5000,
            line_13a_eic=3000,
            line_13b_actc=2000,
        )
        # Net tax = 20000 - 5000 = 15000
        # Refundable = 3000 + 2000 = 5000
        # Current year tax = 15000 - 5000 = 10000
        assert worksheet.line_14b_current_year_tax == 10000


class TestSafeHarborRules:
    """Test safe harbor calculations."""

    def test_safe_harbor_100_percent(self):
        """Test 100% safe harbor for AGI <= $150k."""
        worksheet = Form1040ESWorksheet(
            line_16b_prior_year_tax=10000,
            line_16c_prior_year_agi=100000,
        )
        assert worksheet.safe_harbor_percentage == 1.00
        assert worksheet.safe_harbor_amount == 10000

    def test_safe_harbor_110_percent(self):
        """Test 110% safe harbor for AGI > $150k."""
        worksheet = Form1040ESWorksheet(
            line_16b_prior_year_tax=10000,
            line_16c_prior_year_agi=200000,
        )
        assert worksheet.safe_harbor_percentage == 1.10
        assert worksheet.safe_harbor_amount == 11000

    def test_safe_harbor_exactly_150k(self):
        """Test safe harbor at exactly $150k AGI."""
        worksheet = Form1040ESWorksheet(
            line_16b_prior_year_tax=10000,
            line_16c_prior_year_agi=150000,
        )
        # At exactly $150k, use 100%
        assert worksheet.safe_harbor_percentage == 1.00

    def test_required_payment_uses_smaller(self):
        """Test required payment uses smaller of 90% current or safe harbor."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=50000,  # Current year tax = 50000
            line_16b_prior_year_tax=60000,  # Prior year = 60000
            line_16c_prior_year_agi=100000,
        )
        # 90% of current = 45000
        # 100% of prior = 60000
        # Use smaller = 45000
        assert worksheet.required_annual_payment == 45000

    def test_required_payment_prior_year_smaller(self):
        """Test when prior year safe harbor is smaller."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=100000,  # Current year = 100000
            line_16b_prior_year_tax=50000,  # Prior year = 50000
            line_16c_prior_year_agi=100000,
        )
        # 90% of current = 90000
        # 100% of prior = 50000
        # Use smaller = 50000
        assert worksheet.required_annual_payment == 50000

    def test_no_prior_year_tax(self):
        """Test when there's no prior year tax."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=40000,
            line_16b_prior_year_tax=0,
        )
        # Use 90% of current year
        assert worksheet.required_annual_payment == 36000


class TestQuarterlyPayments:
    """Test quarterly payment calculations."""

    def test_quarterly_payment_calculation(self):
        """Test quarterly payment amount."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=40000,
            line_15_withholding=10000,
            line_16b_prior_year_tax=35000,
        )
        # Required = min(36000, 35000) = 35000
        # After withholding = 35000 - 10000 = 25000
        # Quarterly = 25000 / 4 = 6250
        assert worksheet.quarterly_payment == 6250.0

    def test_quarterly_payment_withholding_covers(self):
        """Test when withholding covers required amount."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=20000,
            line_15_withholding=20000,
            line_16b_prior_year_tax=18000,
        )
        # Required = min(18000, 18000) = 18000
        # After withholding = 18000 - 20000 = negative
        # Quarterly = 0
        assert worksheet.quarterly_payment == 0.0

    def test_is_estimated_tax_required(self):
        """Test determination of whether estimated tax is required."""
        # Required: balance >= $1000
        worksheet = Form1040ESWorksheet(
            line_4_tax=20000,
            line_15_withholding=18500,
        )
        # Balance = 20000 - 18500 = 1500
        assert worksheet.is_estimated_tax_required is True

    def test_estimated_tax_not_required(self):
        """Test when estimated tax is not required."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=20000,
            line_15_withholding=19500,
        )
        # Balance = 20000 - 19500 = 500 < 1000
        assert worksheet.is_estimated_tax_required is False


class TestEstimatedTaxPayment:
    """Test individual payment records."""

    def test_payment_creation(self):
        """Test creating a payment record."""
        payment = EstimatedTaxPayment(
            quarter=Quarter.Q1,
            due_date=date(2025, 4, 15),
            amount_due=5000,
        )
        assert payment.quarter == Quarter.Q1
        assert payment.amount_due == 5000
        assert payment.is_paid is False

    def test_payment_on_time(self):
        """Test on-time payment detection."""
        payment = EstimatedTaxPayment(
            quarter=Quarter.Q1,
            due_date=date(2025, 4, 15),
            amount_due=5000,
            amount_paid=5000,
            payment_date=date(2025, 4, 10),
        )
        assert payment.is_paid is True
        assert payment.is_on_time is True
        assert payment.days_late == 0

    def test_payment_late(self):
        """Test late payment detection."""
        payment = EstimatedTaxPayment(
            quarter=Quarter.Q1,
            due_date=date(2025, 4, 15),
            amount_due=5000,
            amount_paid=5000,
            payment_date=date(2025, 5, 1),
        )
        assert payment.is_on_time is False
        assert payment.days_late == 16

    def test_underpayment(self):
        """Test underpayment calculation."""
        payment = EstimatedTaxPayment(
            quarter=Quarter.Q1,
            due_date=date(2025, 4, 15),
            amount_due=5000,
            amount_paid=3000,
            payment_date=date(2025, 4, 15),
        )
        assert payment.underpayment == 2000
        assert payment.overpayment == 0

    def test_overpayment(self):
        """Test overpayment calculation."""
        payment = EstimatedTaxPayment(
            quarter=Quarter.Q1,
            due_date=date(2025, 4, 15),
            amount_due=5000,
            amount_paid=6000,
            payment_date=date(2025, 4, 15),
        )
        assert payment.underpayment == 0
        assert payment.overpayment == 1000


class TestForm1040ES:
    """Test complete Form 1040-ES."""

    def test_get_due_dates(self):
        """Test due date generation."""
        form = Form1040ES(tax_year=2025)
        dates = form.get_due_dates()

        assert dates[Quarter.Q1] == date(2025, 4, 15)
        assert dates[Quarter.Q2] == date(2025, 6, 15)
        assert dates[Quarter.Q3] == date(2025, 9, 15)
        assert dates[Quarter.Q4] == date(2026, 1, 15)

    def test_initialize_payments(self):
        """Test payment schedule initialization."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=40000,
            line_16b_prior_year_tax=40000,
        )
        form = Form1040ES(
            tax_year=2025,
            worksheet=worksheet,
        )
        form.initialize_payments()

        assert len(form.payments) == 4
        # Each quarter should have 36000/4 = 9000 due
        for payment in form.payments:
            assert payment.amount_due == 9000.0

    def test_record_payment(self):
        """Test recording a payment."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=40000,
            line_16b_prior_year_tax=40000,
        )
        form = Form1040ES(tax_year=2025, worksheet=worksheet)
        form.initialize_payments()

        form.record_payment(
            quarter=Quarter.Q1,
            amount=9000,
            payment_date=date(2025, 4, 10),
            method=PaymentMethod.DIRECT_PAY,
            confirmation="ABC123",
        )

        q1_payment = next(p for p in form.payments if p.quarter == Quarter.Q1)
        assert q1_payment.amount_paid == 9000
        assert q1_payment.is_on_time is True
        assert q1_payment.confirmation_number == "ABC123"

    def test_total_paid(self):
        """Test total paid calculation."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=40000,
            line_16b_prior_year_tax=40000,
        )
        form = Form1040ES(tax_year=2025, worksheet=worksheet)
        form.initialize_payments()

        # Pay Q1 and Q2
        form.record_payment(Quarter.Q1, 9000, date(2025, 4, 15))
        form.record_payment(Quarter.Q2, 9000, date(2025, 6, 15))

        assert form.total_paid == 18000
        assert form.payments_on_time == 2

    def test_remaining_balance(self):
        """Test remaining balance calculation."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=40000,
            line_16b_prior_year_tax=40000,
        )
        form = Form1040ES(tax_year=2025, worksheet=worksheet)
        form.initialize_payments()

        form.record_payment(Quarter.Q1, 9000, date(2025, 4, 15))

        # Required = 36000, Paid = 9000
        assert form.remaining_balance == 27000

    def test_get_next_payment(self):
        """Test getting next unpaid payment."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=40000,
            line_16b_prior_year_tax=40000,
        )
        form = Form1040ES(tax_year=2025, worksheet=worksheet)
        form.initialize_payments()

        form.record_payment(Quarter.Q1, 9000, date(2025, 4, 15))

        next_payment = form.get_next_payment()
        assert next_payment.quarter == Quarter.Q2


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_calculate_estimated_tax_basic(self):
        """Test basic estimated tax calculation."""
        result = calculate_estimated_tax(
            expected_income=150000,
            expected_deductions=30000,
            expected_tax=25000,
            expected_withholding=10000,
            prior_year_tax=20000,
            prior_year_agi=100000,
        )
        assert result["total_tax"] == 25000
        assert result["withholding"] == 10000
        assert result["balance_due"] == 15000
        assert result["safe_harbor_pct"] == 100
        # min(22500, 20000) = 20000
        assert result["required_annual"] == 20000
        assert result["quarterly_payment"] == 2500.0  # (20000-10000)/4

    def test_calculate_estimated_tax_high_income(self):
        """Test with high income (110% safe harbor)."""
        result = calculate_estimated_tax(
            expected_income=300000,
            expected_deductions=50000,
            expected_tax=70000,
            expected_withholding=20000,
            prior_year_tax=60000,
            prior_year_agi=250000,  # > 150k
        )
        assert abs(result["safe_harbor_pct"] - 110) < 0.01
        # 110% of 60000 = 66000
        # 90% of 70000 = 63000
        # min(63000, 66000) = 63000
        assert result["required_annual"] == 63000

    def test_calculate_penalty_estimate(self):
        """Test penalty estimation."""
        result = calculate_penalty_estimate(
            required_payment=10000,
            actual_payment=5000,
            days_late=30,
            annual_rate=0.08,
        )
        # Underpayment = 5000
        # Penalty = 5000 * 0.08 * (30/365) = 32.88
        assert result["underpayment"] == 5000
        assert result["penalty"] == 32.88
        assert result["days_late"] == 30

    def test_calculate_penalty_no_underpayment(self):
        """Test penalty when fully paid."""
        result = calculate_penalty_estimate(
            required_payment=10000,
            actual_payment=10000,
            days_late=0,
        )
        assert result["underpayment"] == 0
        assert result["penalty"] == 0


class TestAnnualizedIncomeMethod:
    """Test annualized income installment method."""

    def test_annualized_income_calculation(self):
        """Test annualized income method calculation."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=40000,
        )
        form = Form1040ES(tax_year=2025, worksheet=worksheet)

        # Income by period (cumulative)
        income = {
            "Q1": 30000,          # Jan-Mar income
            "Q1-Q2": 60000,       # Jan-May income
            "Q1-Q3": 100000,      # Jan-Aug income
            "Q1-Q4": 150000,      # Full year income
        }

        result = form.calculate_annualized_income_installment(income)

        # Should have payments for all 4 quarters
        assert Quarter.Q1 in result
        assert Quarter.Q2 in result
        assert Quarter.Q3 in result
        assert Quarter.Q4 in result


class TestToDictionary:
    """Test dictionary serialization."""

    def test_to_dict(self):
        """Test complete dictionary output."""
        worksheet = Form1040ESWorksheet(
            line_1_expected_agi=100000,
            line_4_tax=20000,
            line_15_withholding=5000,
            line_16b_prior_year_tax=18000,
        )
        form = Form1040ES(
            tax_year=2025,
            filing_status="single",
            worksheet=worksheet,
        )
        form.initialize_payments()

        result = form.to_dict()

        assert result["tax_year"] == 2025
        assert result["filing_status"] == "single"
        assert result["worksheet"]["expected_agi"] == 100000
        assert len(result["payments"]) == 4
        assert "summary" in result


class TestEdgeCases:
    """Test edge cases."""

    def test_zero_tax_liability(self):
        """Test when no tax is owed."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=0,
            line_16b_prior_year_tax=0,
        )
        assert worksheet.quarterly_payment == 0.0
        assert worksheet.is_estimated_tax_required is False

    def test_all_tax_withheld(self):
        """Test when withholding covers everything."""
        worksheet = Form1040ESWorksheet(
            line_4_tax=30000,
            line_15_withholding=35000,
            line_16b_prior_year_tax=28000,
        )
        assert worksheet.line_16a_balance == 0
        assert worksheet.quarterly_payment == 0.0

    def test_first_year_filer(self):
        """Test first year filer (no prior year data)."""
        result = calculate_estimated_tax(
            expected_income=100000,
            expected_deductions=15000,
            expected_tax=15000,
            expected_withholding=0,
            prior_year_tax=0,  # First year
            prior_year_agi=0,
        )
        # Should use 90% of current year
        assert result["required_annual"] == 13500  # 90% of 15000

    def test_payment_methods(self):
        """Test payment method enum values."""
        assert PaymentMethod.DIRECT_PAY.value == "direct_pay"
        assert PaymentMethod.EFTPS.value == "eftps"
        assert PaymentMethod.CHECK.value == "check"
        assert PaymentMethod.CREDIT_CARD.value == "credit_card"

    def test_quarter_enum(self):
        """Test quarter enum values."""
        assert Quarter.Q1.value == "Q1"
        assert Quarter.Q2.value == "Q2"
        assert Quarter.Q3.value == "Q3"
        assert Quarter.Q4.value == "Q4"
