"""
Tests for Form 1099-K - Payment Card and Third Party Network Transactions

Comprehensive test suite covering:
- Basic 1099-K data capture
- Monthly breakdown calculations
- Transaction analysis
- Adjustments to arrive at taxable income
- Multiple 1099-K aggregation
- Reconciliation to bank deposits
- Schedule C integration
"""

import pytest
from src.models.form_1099_k import (
    Form1099K,
    Form1099KAdjustments,
    Form1099KSummary,
    TransactionType,
    PayerType,
    calculate_1099k_taxable_income,
    reconcile_1099k_to_deposits,
)


class TestForm1099KBasic:
    """Test basic Form 1099-K data capture."""

    def test_create_basic_form(self):
        """Test creating a basic 1099-K form."""
        form = Form1099K(
            tax_year=2025,
            payer_name="PayPal Holdings Inc",
            payer_tin="12-3456789",
            payee_name="John Doe",
            payee_tin="123-45-6789",
            box_1a_gross_amount=25000.00,
            box_3_transaction_count=500,
        )
        assert form.box_1a_gross_amount == 25000.00
        assert form.box_3_transaction_count == 500

    def test_transaction_types(self):
        """Test transaction type classification."""
        card_form = Form1099K(
            transaction_type=TransactionType.PAYMENT_CARD,
            box_1a_gross_amount=50000,
        )
        assert card_form.transaction_type == TransactionType.PAYMENT_CARD

        network_form = Form1099K(
            transaction_type=TransactionType.THIRD_PARTY_NETWORK,
            box_1a_gross_amount=30000,
        )
        assert network_form.transaction_type == TransactionType.THIRD_PARTY_NETWORK

    def test_payer_types(self):
        """Test payer type classification."""
        assert PayerType.MERCHANT_ACQUIRER.value == "merchant_acquirer"
        assert PayerType.THIRD_PARTY_PSE.value == "third_party_pse"
        assert PayerType.ELECTRONIC_PAYMENT_FACILITATOR.value == "epf"

    def test_card_present_vs_not_present(self):
        """Test card present/not present breakdown."""
        form = Form1099K(
            box_1a_gross_amount=100000,
            box_1b_card_not_present=75000,  # Online sales
        )
        # Card present = total - not present
        assert form.card_present_transactions == 25000
        assert form.card_present_percentage == 25.0

    def test_all_card_not_present(self):
        """Test 100% online transactions."""
        form = Form1099K(
            box_1a_gross_amount=50000,
            box_1b_card_not_present=50000,
        )
        assert form.card_present_transactions == 0
        assert form.card_present_percentage == 0.0

    def test_federal_and_state_withholding(self):
        """Test backup withholding tracking."""
        form = Form1099K(
            box_1a_gross_amount=100000,
            box_4_federal_tax_withheld=2400.00,  # 24% backup withholding
            box_6_state="CA",
            box_6_state_tax_withheld=700.00,
        )
        assert form.box_4_federal_tax_withheld == 2400.00
        assert form.box_6_state == "CA"
        assert form.box_6_state_tax_withheld == 700.00


class TestForm1099KMonthlyBreakdown:
    """Test monthly amount breakdown."""

    def test_monthly_amounts(self):
        """Test monthly breakdown tracking."""
        form = Form1099K(
            box_1a_gross_amount=120000,
            box_5a_january=10000,
            box_5b_february=10000,
            box_5c_march=10000,
            box_5d_april=10000,
            box_5e_may=10000,
            box_5f_june=10000,
            box_5g_july=10000,
            box_5h_august=10000,
            box_5i_september=10000,
            box_5j_october=10000,
            box_5k_november=10000,
            box_5l_december=10000,
        )
        assert form.monthly_gross_total == 120000
        assert form.average_monthly_gross == 10000.0

    def test_uneven_monthly_amounts(self):
        """Test uneven monthly distribution (seasonal business)."""
        form = Form1099K(
            box_1a_gross_amount=50000,
            box_5k_november=20000,  # Holiday season
            box_5l_december=30000,
        )
        assert form.monthly_gross_total == 50000
        # 2 active months
        assert form.average_monthly_gross == 25000.0

    def test_monthly_amounts_dict(self):
        """Test monthly amounts dictionary."""
        form = Form1099K(
            box_5a_january=5000,
            box_5f_june=8000,
        )
        amounts = form.monthly_amounts
        assert amounts["january"] == 5000
        assert amounts["june"] == 8000
        assert amounts["february"] == 0


class TestForm1099KTransactionAnalysis:
    """Test transaction analysis features."""

    def test_average_transaction_amount(self):
        """Test average transaction calculation."""
        form = Form1099K(
            box_1a_gross_amount=10000,
            box_3_transaction_count=200,
        )
        assert form.average_transaction_amount == 50.0

    def test_zero_transactions(self):
        """Test handling of zero transactions."""
        form = Form1099K(
            box_1a_gross_amount=0,
            box_3_transaction_count=0,
        )
        assert form.average_transaction_amount == 0.0
        assert form.average_monthly_gross == 0.0

    def test_high_volume_low_value(self):
        """Test high volume, low value transactions (coffee shop)."""
        form = Form1099K(
            box_1a_gross_amount=150000,
            box_3_transaction_count=30000,
        )
        # $150k / 30k transactions = $5/transaction
        assert form.average_transaction_amount == 5.0

    def test_low_volume_high_value(self):
        """Test low volume, high value transactions (jewelry)."""
        form = Form1099K(
            box_1a_gross_amount=500000,
            box_3_transaction_count=100,
        )
        assert form.average_transaction_amount == 5000.0


class TestForm1099KAdjustments:
    """Test adjustments to arrive at taxable income."""

    def test_basic_adjustments(self):
        """Test basic adjustment calculation."""
        adj = Form1099KAdjustments(
            gross_1099k_amount=50000,
            refunds_and_returns=2000,
            processing_fees=1500,
            platform_fees=5000,
        )
        assert adj.total_adjustments == 8500
        assert adj.adjusted_gross_receipts == 41500

    def test_all_adjustment_types(self):
        """Test all types of adjustments."""
        adj = Form1099KAdjustments(
            gross_1099k_amount=100000,
            refunds_and_returns=5000,
            chargebacks=500,
            processing_fees=2800,
            platform_fees=15000,
            non_taxable_amounts=1000,
            sales_tax_collected=7200,
            tips_already_reported=0,
        )
        total_adj = 5000 + 500 + 2800 + 15000 + 1000 + 7200
        assert adj.total_adjustments == total_adj
        assert adj.adjusted_gross_receipts == 100000 - total_adj

    def test_with_cogs(self):
        """Test with cost of goods sold."""
        adj = Form1099KAdjustments(
            gross_1099k_amount=80000,
            processing_fees=2000,
            cost_of_goods_sold=30000,
        )
        # Adjusted gross = 80000 - 2000 = 78000
        # Net before expenses = 78000 - 30000 = 48000
        assert adj.adjusted_gross_receipts == 78000
        assert adj.net_profit_before_expenses == 48000

    def test_with_other_expenses(self):
        """Test full calculation with all expenses."""
        adj = Form1099KAdjustments(
            gross_1099k_amount=100000,
            refunds_and_returns=5000,
            processing_fees=2500,
            cost_of_goods_sold=40000,
            other_deductible_expenses=15000,
        )
        # Adjusted gross = 100000 - 7500 = 92500
        # After COGS = 92500 - 40000 = 52500
        # Net taxable = 52500 - 15000 = 37500
        assert adj.adjusted_gross_receipts == 92500
        assert adj.net_profit_before_expenses == 52500
        assert adj.net_taxable_income == 37500

    def test_adjustments_exceed_gross(self):
        """Test when adjustments exceed gross (loss scenario)."""
        adj = Form1099KAdjustments(
            gross_1099k_amount=10000,
            refunds_and_returns=8000,
            processing_fees=3000,
        )
        # 8000 + 3000 = 11000 > 10000
        assert adj.adjusted_gross_receipts == 0  # Can't go negative


class TestForm1099KSummary:
    """Test multiple 1099-K aggregation."""

    def test_single_form_summary(self):
        """Test summary with single form."""
        summary = Form1099KSummary(tax_year=2025)
        form = Form1099K(
            payer_name="Stripe",
            box_1a_gross_amount=75000,
            box_3_transaction_count=1500,
        )
        summary.add_form(form)

        assert summary.total_gross_receipts == 75000
        assert summary.total_transactions == 1500
        assert summary.number_of_forms == 1

    def test_multiple_forms_summary(self):
        """Test summary with multiple forms."""
        summary = Form1099KSummary(tax_year=2025)

        # PayPal
        summary.add_form(Form1099K(
            payer_name="PayPal",
            payer_type=PayerType.THIRD_PARTY_PSE,
            box_1a_gross_amount=30000,
            box_3_transaction_count=600,
        ))

        # Stripe
        summary.add_form(Form1099K(
            payer_name="Stripe",
            payer_type=PayerType.THIRD_PARTY_PSE,
            box_1a_gross_amount=45000,
            box_3_transaction_count=900,
        ))

        # Square (card processor)
        summary.add_form(Form1099K(
            payer_name="Square",
            payer_type=PayerType.MERCHANT_ACQUIRER,
            box_1a_gross_amount=25000,
            box_3_transaction_count=500,
        ))

        assert summary.total_gross_receipts == 100000
        assert summary.total_transactions == 2000
        assert summary.number_of_forms == 3

    def test_group_by_payer_type(self):
        """Test grouping by payer type."""
        summary = Form1099KSummary(tax_year=2025)

        summary.add_form(Form1099K(
            payer_type=PayerType.THIRD_PARTY_PSE,
            box_1a_gross_amount=50000,
        ))
        summary.add_form(Form1099K(
            payer_type=PayerType.THIRD_PARTY_PSE,
            box_1a_gross_amount=30000,
        ))
        summary.add_form(Form1099K(
            payer_type=PayerType.MERCHANT_ACQUIRER,
            box_1a_gross_amount=20000,
        ))

        by_type = summary.by_payer_type()
        assert by_type["third_party_pse"] == 80000
        assert by_type["merchant_acquirer"] == 20000

    def test_aggregate_withholding(self):
        """Test aggregate withholding calculations."""
        summary = Form1099KSummary(tax_year=2025)

        summary.add_form(Form1099K(
            box_1a_gross_amount=40000,
            box_4_federal_tax_withheld=960,
            box_6_state_tax_withheld=280,
        ))
        summary.add_form(Form1099K(
            box_1a_gross_amount=60000,
            box_4_federal_tax_withheld=1440,
            box_6_state_tax_withheld=420,
        ))

        assert summary.total_federal_tax_withheld == 2400
        assert summary.total_state_tax_withheld == 700


class TestForm1099KToScheduleC:
    """Test Schedule C integration."""

    def test_schedule_c_output(self):
        """Test Schedule C line mapping."""
        summary = Form1099KSummary(tax_year=2025)
        summary.add_form(Form1099K(
            box_1a_gross_amount=100000,
        ))

        summary.adjustments = Form1099KAdjustments(
            gross_1099k_amount=100000,
            refunds_and_returns=5000,
            processing_fees=2500,
            cost_of_goods_sold=40000,
        )

        result = summary.to_schedule_c()
        assert result["line_1099k_gross"] == 100000
        assert result["reconciliation_adjustment"] == 7500
        assert result["line_1_gross_receipts"] == 92500
        assert result["line_4_cogs"] == 40000

    def test_to_dict(self):
        """Test dictionary serialization."""
        summary = Form1099KSummary(tax_year=2025)
        summary.add_form(Form1099K(
            payer_name="PayPal",
            box_1a_gross_amount=50000,
            box_3_transaction_count=1000,
        ))

        result = summary.to_dict()
        assert result["tax_year"] == 2025
        assert result["form_count"] == 1
        assert result["total_gross_receipts"] == 50000
        assert len(result["forms"]) == 1
        assert result["forms"][0]["payer"] == "PayPal"


class TestConvenienceFunction:
    """Test calculate_1099k_taxable_income convenience function."""

    def test_simple_calculation(self):
        """Test simple taxable income calculation."""
        result = calculate_1099k_taxable_income(
            gross_1099k=50000,
            refunds=2000,
            processing_fees=1500,
        )
        assert result["gross_1099k"] == 50000
        assert result["total_adjustments"] == 3500
        assert result["adjusted_gross_receipts"] == 46500
        assert result["net_taxable_income"] == 46500

    def test_full_calculation(self):
        """Test full calculation with all parameters."""
        result = calculate_1099k_taxable_income(
            gross_1099k=100000,
            refunds=5000,
            processing_fees=2800,
            platform_fees=15000,
            sales_tax=7200,
            cogs=35000,
            other_expenses=10000,
        )
        # Adjustments = 5000 + 2800 + 15000 + 7200 = 30000
        # Adjusted gross = 70000
        # After COGS = 35000
        # Net = 25000
        assert result["adjusted_gross_receipts"] == 70000
        assert result["gross_profit"] == 35000
        assert result["net_taxable_income"] == 25000
        # Effective rate = 25000/100000 = 25%
        assert result["effective_rate"] == 25.0

    def test_zero_gross(self):
        """Test with zero gross amount."""
        result = calculate_1099k_taxable_income(gross_1099k=0)
        assert result["effective_rate"] == 0


class TestReconciliation:
    """Test reconciliation to bank deposits."""

    def test_simple_reconciliation(self):
        """Test simple reconciliation."""
        result = reconcile_1099k_to_deposits(
            gross_1099k=50000,
            actual_deposits=47000,
            processing_fees=3000,
        )
        assert result["expected_deposit"] == 47000
        assert result["reconciles"] is True
        assert result["action_needed"] is None

    def test_reconciliation_with_all_deductions(self):
        """Test reconciliation with multiple deductions."""
        result = reconcile_1099k_to_deposits(
            gross_1099k=100000,
            actual_deposits=80000,
            refunds=8000,
            processing_fees=2800,
            platform_fees=9000,
            chargebacks=200,
        )
        # Expected = 100000 - 8000 - 2800 - 9000 - 200 = 80000
        assert result["expected_deposit"] == 80000
        assert result["reconciles"] is True

    def test_reconciliation_discrepancy_positive(self):
        """Test reconciliation with positive discrepancy."""
        result = reconcile_1099k_to_deposits(
            gross_1099k=50000,
            actual_deposits=48000,  # More than expected
            processing_fees=1500,
        )
        # Expected = 48500, Actual = 48000
        assert result["reconciles"] is False
        assert result["action_needed"] == "Identify missing deductions"

    def test_reconciliation_discrepancy_negative(self):
        """Test reconciliation with negative discrepancy."""
        result = reconcile_1099k_to_deposits(
            gross_1099k=50000,
            actual_deposits=50000,  # More than expected after fees
            processing_fees=2000,
        )
        # Expected = 48000, Actual = 50000
        assert result["reconciles"] is False
        assert "Review 1099-K for accuracy" in result["action_needed"]

    def test_reconciliation_within_tolerance(self):
        """Test reconciliation within $1 tolerance."""
        result = reconcile_1099k_to_deposits(
            gross_1099k=50000,
            actual_deposits=47000.50,
            processing_fees=3000,
        )
        # Difference = 0.50, within tolerance
        assert result["reconciles"] is True


class TestGigEconomyScenarios:
    """Test real-world gig economy scenarios."""

    def test_uber_driver(self):
        """Test Uber driver 1099-K scenario."""
        form = Form1099K(
            payer_name="Uber Technologies",
            payer_type=PayerType.THIRD_PARTY_PSE,
            box_1a_gross_amount=45000,  # Gross fares
            box_3_transaction_count=2000,  # 2000 rides
            transaction_type=TransactionType.THIRD_PARTY_NETWORK,
        )

        adj = Form1099KAdjustments(
            gross_1099k_amount=45000,
            # Uber's fees are already netted, but service fees might be on 1099-K
            platform_fees=0,  # Usually pre-deducted
            # Driver expenses tracked separately
            other_deductible_expenses=15000,  # Mileage, phone, etc.
        )

        assert form.average_transaction_amount == 22.5  # $22.50/ride
        assert adj.net_taxable_income == 30000

    def test_etsy_seller(self):
        """Test Etsy seller 1099-K scenario."""
        form = Form1099K(
            payer_name="Etsy Inc",
            payer_type=PayerType.ELECTRONIC_PAYMENT_FACILITATOR,
            box_1a_gross_amount=35000,
            box_3_transaction_count=700,
            box_1b_card_not_present=35000,  # All online
        )

        adj = Form1099KAdjustments(
            gross_1099k_amount=35000,
            refunds_and_returns=1500,
            processing_fees=1050,  # 3% payment processing
            platform_fees=1750,  # 5% transaction fee
            sales_tax_collected=2800,  # Pass-through
            cost_of_goods_sold=12000,
            other_deductible_expenses=3000,
        )

        # Adjustments = 1500 + 1050 + 1750 + 2800 = 7100
        assert adj.total_adjustments == 7100
        # Adjusted gross = 27900
        # After COGS = 15900
        # Net = 12900
        assert adj.net_taxable_income == 12900

    def test_ebay_seller(self):
        """Test eBay seller with high volume."""
        form = Form1099K(
            payer_name="eBay Inc",
            payer_type=PayerType.ELECTRONIC_PAYMENT_FACILITATOR,
            box_1a_gross_amount=150000,
            box_3_transaction_count=3000,
        )

        adj = Form1099KAdjustments(
            gross_1099k_amount=150000,
            refunds_and_returns=12000,  # 8% return rate
            chargebacks=500,
            processing_fees=4500,  # 3%
            platform_fees=19500,  # 13% final value fee
            sales_tax_collected=10500,  # 7% on some sales
            cost_of_goods_sold=60000,  # 40% COGS
            other_deductible_expenses=8000,  # Shipping supplies, etc.
        )

        assert adj.adjusted_gross_receipts == 103000
        assert adj.net_taxable_income == 35000


class TestForm1099KEdgeCases:
    """Test edge cases."""

    def test_zero_gross_amount(self):
        """Test form with zero gross amount."""
        form = Form1099K(
            box_1a_gross_amount=0,
            box_3_transaction_count=0,
        )
        assert form.average_transaction_amount == 0.0
        assert form.card_present_percentage == 0.0

    def test_empty_summary(self):
        """Test empty summary."""
        summary = Form1099KSummary(tax_year=2025)
        assert summary.total_gross_receipts == 0
        assert summary.total_transactions == 0
        assert summary.number_of_forms == 0

    def test_adjustments_greater_than_income(self):
        """Test when business has a loss."""
        adj = Form1099KAdjustments(
            gross_1099k_amount=20000,
            cost_of_goods_sold=15000,
            other_deductible_expenses=10000,
        )
        # Adjusted = 20000, After COGS = 5000
        # After expenses = 0 (can't go negative through this model)
        assert adj.net_taxable_income == 0

    def test_merchant_category_code(self):
        """Test MCC tracking."""
        form = Form1099K(
            box_1a_gross_amount=50000,
            box_2_merchant_category_code="5812",  # Restaurants
        )
        assert form.box_2_merchant_category_code == "5812"
