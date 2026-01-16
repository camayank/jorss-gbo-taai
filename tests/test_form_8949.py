"""
Tests for Form 8949 - Sales and Other Dispositions of Capital Assets

Tests cover:
- Security transaction creation and gain/loss calculation
- Form 8949 box determination (A-F)
- Wash sale tracking and adjustments
- Section 1202 QSBS exclusion
- Section 1244 ordinary loss
- Form 1099-B integration
- Securities portfolio aggregation
- Schedule D amounts calculation
- Integration with Income model
"""

import pytest
from datetime import datetime

from models.form_8949 import (
    SecurityType,
    Form8949Box,
    AdjustmentCode,
    WashSaleInfo,
    SecurityTransaction,
    Form1099B,
    Form8949Summary,
    SecuritiesPortfolio,
)
from models.income import Income
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions
from models.credits import TaxCredits
from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig


class TestSecurityTransaction:
    """Tests for individual security transactions."""

    def test_basic_stock_gain(self):
        """Test basic stock sale with gain."""
        tx = SecurityTransaction(
            description="100 sh AAPL",
            ticker_symbol="AAPL",
            date_acquired="2020-01-15",
            date_sold="2024-06-20",
            proceeds=15000.0,
            cost_basis=10000.0,
        )
        assert tx.calculate_gain_loss() == 5000.0
        assert tx.is_long_term() is True

    def test_basic_stock_loss(self):
        """Test basic stock sale with loss."""
        tx = SecurityTransaction(
            description="50 sh XYZ",
            ticker_symbol="XYZ",
            date_acquired="2024-03-01",
            date_sold="2024-09-15",
            proceeds=5000.0,
            cost_basis=8000.0,
        )
        assert tx.calculate_gain_loss() == -3000.0
        assert tx.is_long_term() is False

    def test_short_term_holding_period(self):
        """Test holding period calculation for short-term."""
        tx = SecurityTransaction(
            description="100 sh TEST",
            date_acquired="2024-06-01",
            date_sold="2024-12-01",
            proceeds=10000.0,
            cost_basis=9000.0,
        )
        assert tx.is_long_term() is False
        assert tx.calculate_gain_loss() == 1000.0

    def test_long_term_exactly_one_year(self):
        """Test holding period at exactly one year (still short-term)."""
        tx = SecurityTransaction(
            description="100 sh TEST",
            date_acquired="2025-06-01",
            date_sold="2026-06-01",  # Exactly 365 days (2026 is not a leap year)
            proceeds=10000.0,
            cost_basis=9000.0,
        )
        # Per IRS rules, must hold MORE than 1 year for long-term
        assert tx.is_long_term() is False

    def test_long_term_over_one_year(self):
        """Test holding period over one year."""
        tx = SecurityTransaction(
            description="100 sh TEST",
            date_acquired="2023-06-01",
            date_sold="2024-06-02",  # 366 days
            proceeds=10000.0,
            cost_basis=9000.0,
        )
        assert tx.is_long_term() is True

    def test_various_date_acquired(self):
        """Test VARIOUS date acquired."""
        tx = SecurityTransaction(
            description="100 sh MIXED",
            date_acquired="VARIOUS",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=9000.0,
        )
        # VARIOUS defaults to long-term
        assert tx.is_long_term() is True


class TestForm8949BoxDetermination:
    """Tests for Form 8949 box assignment."""

    def test_box_a_short_term_basis_reported(self):
        """Box A: Short-term, basis reported on 1099-B."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2024-03-01",
            date_sold="2024-09-01",
            proceeds=10000.0,
            cost_basis=9000.0,
            reported_on_1099b=True,
            basis_reported_to_irs=True,
        )
        assert tx.determine_form_8949_box() == Form8949Box.A

    def test_box_b_short_term_basis_not_reported(self):
        """Box B: Short-term, basis NOT reported on 1099-B."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2024-03-01",
            date_sold="2024-09-01",
            proceeds=10000.0,
            cost_basis=9000.0,
            reported_on_1099b=True,
            basis_reported_to_irs=False,
        )
        assert tx.determine_form_8949_box() == Form8949Box.B

    def test_box_c_short_term_no_1099b(self):
        """Box C: Short-term, no Form 1099-B received."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2024-03-01",
            date_sold="2024-09-01",
            proceeds=10000.0,
            cost_basis=9000.0,
            reported_on_1099b=False,
        )
        assert tx.determine_form_8949_box() == Form8949Box.C

    def test_box_d_long_term_basis_reported(self):
        """Box D: Long-term, basis reported on 1099-B."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2020-01-01",
            date_sold="2024-09-01",
            proceeds=10000.0,
            cost_basis=5000.0,
            reported_on_1099b=True,
            basis_reported_to_irs=True,
        )
        assert tx.determine_form_8949_box() == Form8949Box.D

    def test_box_e_long_term_basis_not_reported(self):
        """Box E: Long-term, basis NOT reported on 1099-B."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2020-01-01",
            date_sold="2024-09-01",
            proceeds=10000.0,
            cost_basis=5000.0,
            reported_on_1099b=True,
            basis_reported_to_irs=False,
        )
        assert tx.determine_form_8949_box() == Form8949Box.E

    def test_box_f_long_term_no_1099b(self):
        """Box F: Long-term, no Form 1099-B received."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2020-01-01",
            date_sold="2024-09-01",
            proceeds=10000.0,
            cost_basis=5000.0,
            reported_on_1099b=False,
        )
        assert tx.determine_form_8949_box() == Form8949Box.F


class TestWashSale:
    """Tests for wash sale tracking and adjustments."""

    def test_wash_sale_disallows_loss(self):
        """Wash sale disallows loss and adds to adjustment."""
        tx = SecurityTransaction(
            description="100 sh XYZ",
            date_acquired="2024-03-01",
            date_sold="2024-06-15",
            proceeds=5000.0,
            cost_basis=8000.0,  # $3000 loss
        )
        tx.apply_wash_sale(
            disallowed_loss=3000.0,
            replacement_date="2024-06-20",
            replacement_quantity=100.0
        )

        assert tx.wash_sale.is_wash_sale is True
        assert tx.wash_sale.disallowed_loss == 3000.0
        assert AdjustmentCode.W in tx.adjustment_codes
        assert tx.adjustment_amount == 3000.0

    def test_wash_sale_adjusted_gain_loss(self):
        """Wash sale adjustment zeros out the loss."""
        tx = SecurityTransaction(
            description="100 sh XYZ",
            date_acquired="2024-03-01",
            date_sold="2024-06-15",
            proceeds=5000.0,
            cost_basis=8000.0,  # $3000 loss
        )
        tx.apply_wash_sale(disallowed_loss=3000.0)

        # Original loss is -3000, adjustment adds +3000
        assert tx.calculate_adjusted_gain_loss() == 0.0

    def test_partial_wash_sale(self):
        """Partial wash sale (some shares replaced)."""
        tx = SecurityTransaction(
            description="100 sh XYZ",
            date_acquired="2024-03-01",
            date_sold="2024-06-15",
            proceeds=5000.0,
            cost_basis=8000.0,  # $3000 loss
        )
        # Only 50 shares replaced, so only half the loss is disallowed
        tx.apply_wash_sale(disallowed_loss=1500.0)

        assert tx.wash_sale.disallowed_loss == 1500.0
        assert tx.calculate_adjusted_gain_loss() == -1500.0  # $1500 loss allowed

    def test_wash_sale_info_model(self):
        """Test WashSaleInfo model directly."""
        wash = WashSaleInfo(
            is_wash_sale=True,
            disallowed_loss=2000.0,
            replacement_shares_date="2024-07-01",
            replacement_shares_quantity=100.0,
            basis_adjustment=2000.0
        )
        # Original loss of -5000 with 2000 disallowed = -3000 allowed
        assert wash.calculate_adjusted_loss(-5000.0) == -3000.0


class TestQSBSExclusion:
    """Tests for Section 1202 Qualified Small Business Stock exclusion."""

    def test_qsbs_100_percent_exclusion(self):
        """Test 100% QSBS exclusion (stock acquired after 9/27/2010)."""
        tx = SecurityTransaction(
            description="QSBS Stock",
            date_acquired="2019-01-01",
            date_sold="2024-06-01",
            proceeds=500000.0,
            cost_basis=100000.0,  # $400k gain
            is_qualified_small_business_stock=True,
            qsbs_exclusion_percentage=100.0,
        )
        exclusion = tx.apply_qsbs_exclusion()

        assert exclusion == 400000.0
        assert AdjustmentCode.X in tx.adjustment_codes

    def test_qsbs_50_percent_exclusion(self):
        """Test 50% QSBS exclusion (stock acquired before 2/18/2009)."""
        tx = SecurityTransaction(
            description="QSBS Stock",
            date_acquired="2008-01-01",
            date_sold="2024-06-01",
            proceeds=200000.0,
            cost_basis=100000.0,  # $100k gain
            is_qualified_small_business_stock=True,
            qsbs_exclusion_percentage=50.0,
        )
        exclusion = tx.apply_qsbs_exclusion()

        assert exclusion == 50000.0  # 50% of $100k gain

    def test_non_qsbs_no_exclusion(self):
        """Non-QSBS stock gets no exclusion."""
        tx = SecurityTransaction(
            description="Regular Stock",
            date_acquired="2019-01-01",
            date_sold="2024-06-01",
            proceeds=200000.0,
            cost_basis=100000.0,
            is_qualified_small_business_stock=False,
        )
        exclusion = tx.apply_qsbs_exclusion()
        assert exclusion == 0.0


class TestSection1244:
    """Tests for Section 1244 small business stock ordinary loss."""

    def test_section_1244_single_filer(self):
        """Section 1244 loss limited to $50,000 for single filer."""
        tx = SecurityTransaction(
            description="Small Business Stock",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=80000.0,  # $70k loss
            is_section_1244_stock=True,
        )
        ordinary_loss = tx.get_section_1244_ordinary_loss(filing_status="single")
        assert ordinary_loss == 50000.0  # Capped at $50k

    def test_section_1244_mfj(self):
        """Section 1244 loss limited to $100,000 for MFJ."""
        tx = SecurityTransaction(
            description="Small Business Stock",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=150000.0,  # $140k loss
            is_section_1244_stock=True,
        )
        ordinary_loss = tx.get_section_1244_ordinary_loss(filing_status="married_filing_jointly")
        assert ordinary_loss == 100000.0  # Capped at $100k

    def test_section_1244_small_loss(self):
        """Section 1244 with loss under limit."""
        tx = SecurityTransaction(
            description="Small Business Stock",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=20000.0,
            cost_basis=40000.0,  # $20k loss
            is_section_1244_stock=True,
        )
        ordinary_loss = tx.get_section_1244_ordinary_loss(filing_status="single")
        assert ordinary_loss == 20000.0  # Full loss as ordinary

    def test_section_1244_gain_no_ordinary(self):
        """Section 1244 with gain has no ordinary loss treatment."""
        tx = SecurityTransaction(
            description="Small Business Stock",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=50000.0,
            cost_basis=30000.0,  # $20k gain
            is_section_1244_stock=True,
        )
        ordinary_loss = tx.get_section_1244_ordinary_loss()
        assert ordinary_loss == 0.0


class TestForm1099B:
    """Tests for Form 1099-B integration."""

    def test_1099b_with_transactions(self):
        """Test 1099-B with detailed transactions."""
        tx1 = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2024-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=8000.0,  # $2k ST gain
        )
        tx2 = SecurityTransaction(
            description="50 sh XYZ",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=15000.0,
            cost_basis=10000.0,  # $5k LT gain
        )

        form_1099b = Form1099B(
            broker_name="Test Broker",
            transactions=[tx1, tx2],
        )

        assert form_1099b.get_net_short_term_gain_loss() == 2000.0
        assert form_1099b.get_net_long_term_gain_loss() == 5000.0

    def test_1099b_summary_amounts(self):
        """Test 1099-B with summary amounts only."""
        form_1099b = Form1099B(
            broker_name="Test Broker",
            proceeds_short_term_covered=50000.0,
            cost_basis_short_term_covered=45000.0,
            proceeds_long_term_covered=100000.0,
            cost_basis_long_term_covered=80000.0,
        )

        assert form_1099b.get_net_short_term_gain_loss() == 5000.0
        assert form_1099b.get_net_long_term_gain_loss() == 20000.0


class TestSecuritiesPortfolio:
    """Tests for securities portfolio aggregation."""

    def test_empty_portfolio(self):
        """Test empty portfolio."""
        portfolio = SecuritiesPortfolio()
        summary = portfolio.calculate_summary()

        assert summary.get_total_short_term_gain_loss() == 0.0
        assert summary.get_total_long_term_gain_loss() == 0.0
        assert summary.get_transaction_count() == 0

    def test_portfolio_with_transactions(self):
        """Test portfolio with multiple transactions."""
        tx1 = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2024-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=8000.0,  # $2k ST gain, Box A
        )
        tx2 = SecurityTransaction(
            description="50 sh XYZ",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=15000.0,
            cost_basis=20000.0,  # $5k LT loss, Box D
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx1, tx2]
        )

        summary = portfolio.calculate_summary()
        assert summary.box_a_gain_loss == 2000.0
        assert summary.box_d_gain_loss == -5000.0
        assert summary.get_total_short_term_gain_loss() == 2000.0
        assert summary.get_total_long_term_gain_loss() == -5000.0

    def test_portfolio_with_carryforward(self):
        """Test portfolio with loss carryforward."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2024-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=8000.0,  # $2k ST gain
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx],
            short_term_loss_carryforward=5000.0,
        )

        # Net ST: 2000 gain - 5000 carryforward = -3000
        assert portfolio.get_net_short_term_gain_loss() == -3000.0

    def test_schedule_d_amounts(self):
        """Test Schedule D amounts calculation."""
        tx1 = SecurityTransaction(
            description="ST gain",
            date_acquired="2024-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=7000.0,  # $3k ST gain
        )
        tx2 = SecurityTransaction(
            description="LT gain",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=20000.0,
            cost_basis=10000.0,  # $10k LT gain
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx1, tx2]
        )

        amounts = portfolio.get_schedule_d_amounts()
        assert amounts['schedule_d_line_7'] == 3000.0  # Net ST
        assert amounts['schedule_d_line_15'] == 10000.0  # Net LT
        assert amounts['schedule_d_line_16'] == 13000.0  # Combined
        assert amounts['capital_loss_deduction'] == 0.0  # No loss

    def test_schedule_d_loss_deduction(self):
        """Test Schedule D capital loss deduction."""
        tx = SecurityTransaction(
            description="Big loss",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=5000.0,
            cost_basis=15000.0,  # $10k LT loss
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx]
        )

        amounts = portfolio.get_schedule_d_amounts()
        assert amounts['schedule_d_line_15'] == -10000.0  # Net LT loss
        assert amounts['capital_loss_deduction'] == 3000.0  # Limited to $3k
        assert amounts['new_long_term_carryforward'] == 7000.0  # Excess


class TestWashSaleDetection:
    """Tests for automatic wash sale detection."""

    def test_detect_wash_sale_within_window(self):
        """Detect wash sale when replacement purchased within 30 days."""
        tx1 = SecurityTransaction(
            description="100 sh ABC",
            ticker_symbol="ABC",
            date_acquired="2024-01-01",
            date_sold="2024-06-15",  # Sold at loss
            proceeds=5000.0,
            cost_basis=8000.0,
        )
        tx2 = SecurityTransaction(
            description="100 sh ABC",
            ticker_symbol="ABC",
            date_acquired="2024-06-20",  # Repurchased 5 days later
            date_sold="2024-12-15",
            proceeds=7000.0,
            cost_basis=5000.0,
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx1, tx2]
        )

        wash_sales = portfolio.detect_wash_sales()
        assert len(wash_sales) == 1
        assert wash_sales[0]['days_difference'] == 5

    def test_no_wash_sale_outside_window(self):
        """No wash sale when replacement is outside 30-day window."""
        tx1 = SecurityTransaction(
            description="100 sh ABC",
            ticker_symbol="ABC",
            date_acquired="2024-01-01",
            date_sold="2024-06-15",
            proceeds=5000.0,
            cost_basis=8000.0,
        )
        tx2 = SecurityTransaction(
            description="100 sh ABC",
            ticker_symbol="ABC",
            date_acquired="2024-08-01",  # 47 days later, outside window
            date_sold="2024-12-15",
            proceeds=7000.0,
            cost_basis=5000.0,
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx1, tx2]
        )

        wash_sales = portfolio.detect_wash_sales()
        assert len(wash_sales) == 0


class TestForm8949Report:
    """Tests for Form 8949 report generation."""

    def test_generate_report(self):
        """Test complete Form 8949 report generation."""
        tx1 = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2024-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=8000.0,
        )
        tx2 = SecurityTransaction(
            description="50 sh XYZ",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=15000.0,
            cost_basis=10000.0,
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx1, tx2]
        )

        report = portfolio.generate_form_8949_report()

        assert 'part_i_short_term' in report
        assert 'part_ii_long_term' in report
        assert report['part_i_short_term']['total_short_term'] == 2000.0
        assert report['part_ii_long_term']['total_long_term'] == 5000.0

    def test_form_8949_line_generation(self):
        """Test individual Form 8949 line generation."""
        tx = SecurityTransaction(
            description="100 sh TEST",
            date_acquired="2024-01-15",
            date_sold="2024-06-20",
            proceeds=12000.0,
            cost_basis=10000.0,
        )

        line = tx.generate_form_8949_line()

        assert line['description'] == "100 sh TEST"
        assert line['date_acquired'] == "2024-01-15"
        assert line['date_sold'] == "2024-06-20"
        assert line['proceeds'] == 12000.0
        assert line['cost_basis'] == 10000.0
        assert line['gain_loss'] == 2000.0
        assert line['form_8949_box'] == 'A'


class TestIncomeIntegration:
    """Tests for integration with Income model."""

    def test_income_with_securities_portfolio(self):
        """Test Income model with securities portfolio."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2024-01-01",
            date_sold="2024-06-01",
            proceeds=15000.0,
            cost_basis=10000.0,  # $5k ST gain
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx]
        )

        income = Income(
            securities_portfolio=portfolio
        )

        st, lt = income.get_securities_net_gain_loss()
        assert st == 5000.0
        assert lt == 0.0

    def test_income_capital_gains_with_portfolio(self):
        """Test capital gains calculation uses portfolio."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=20000.0,
            cost_basis=10000.0,  # $10k LT gain
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx]
        )

        income = Income(
            securities_portfolio=portfolio
        )

        result = income.calculate_net_capital_gain_loss("single")
        net_gain, _, _, _, net_st, net_lt = result

        assert net_lt == 10000.0
        assert net_gain == 10000.0

    def test_income_form_8949_summary(self):
        """Test Form 8949 summary from Income model."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2024-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=8000.0,
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx]
        )

        income = Income(
            securities_portfolio=portfolio
        )

        summary = income.get_form_8949_summary()
        assert summary is not None
        assert summary['box_a_gain_loss'] == 2000.0

    def test_income_without_portfolio(self):
        """Test Income model without securities portfolio returns None/empty."""
        income = Income()

        assert income.get_form_8949_summary() is None
        assert income.get_securities_schedule_d_amounts() is None
        assert income.detect_wash_sales() == []
        assert income.get_total_wash_sale_disallowed() == 0.0


class TestEngineIntegration:
    """Tests for integration with tax calculation engine."""

    def test_engine_with_securities_gain(self):
        """Test engine calculation with securities gain."""
        tx = SecurityTransaction(
            description="100 sh ABC",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=50000.0,
            cost_basis=30000.0,  # $20k LT gain
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx]
        )

        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                securities_portfolio=portfolio
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # Should have taxable income from capital gain
        assert breakdown.net_long_term_gain_loss > 0

    def test_engine_with_securities_loss(self):
        """Test engine calculation with securities loss."""
        tx = SecurityTransaction(
            description="100 sh XYZ",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=20000.0,  # $10k LT loss
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[tx]
        )

        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                securities_portfolio=portfolio
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # Should have capital loss deduction (max $3k)
        assert breakdown.capital_loss_deduction == 3000.0
        assert breakdown.new_lt_loss_carryforward == 7000.0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_proceeds(self):
        """Test transaction with zero proceeds (worthless stock)."""
        tx = SecurityTransaction(
            description="Worthless Stock",
            date_acquired="2020-01-01",
            date_sold="2024-12-31",
            proceeds=0.0,
            cost_basis=10000.0,
        )
        assert tx.calculate_gain_loss() == -10000.0

    def test_zero_cost_basis(self):
        """Test transaction with zero basis (gift or inheritance edge case)."""
        tx = SecurityTransaction(
            description="Gift Stock",
            date_acquired="2010-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=0.0,
            acquired_from_gift=True,
        )
        assert tx.calculate_gain_loss() == 10000.0

    def test_multiple_adjustment_codes(self):
        """Test transaction with multiple adjustment codes."""
        tx = SecurityTransaction(
            description="Complex Transaction",
            date_acquired="2024-01-01",
            date_sold="2024-06-01",
            proceeds=10000.0,
            cost_basis=8000.0,
            adjustment_codes=[AdjustmentCode.W, AdjustmentCode.B],
        )
        assert tx.get_adjustment_code_string() == "W,B"

    def test_collectibles_security_type(self):
        """Test collectibles security type."""
        tx = SecurityTransaction(
            security_type=SecurityType.COLLECTIBLE,
            description="Gold Coins",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=50000.0,
            cost_basis=30000.0,
        )
        assert tx.security_type == SecurityType.COLLECTIBLE
        assert tx.calculate_gain_loss() == 20000.0

    def test_mixed_short_long_term(self):
        """Test portfolio with both short and long-term transactions."""
        st_gain = SecurityTransaction(
            description="ST Gain",
            date_acquired="2024-01-01",
            date_sold="2024-06-01",
            proceeds=15000.0,
            cost_basis=10000.0,
        )
        st_loss = SecurityTransaction(
            description="ST Loss",
            date_acquired="2024-02-01",
            date_sold="2024-06-15",
            proceeds=5000.0,
            cost_basis=8000.0,
        )
        lt_gain = SecurityTransaction(
            description="LT Gain",
            date_acquired="2020-01-01",
            date_sold="2024-06-01",
            proceeds=25000.0,
            cost_basis=15000.0,
        )
        lt_loss = SecurityTransaction(
            description="LT Loss",
            date_acquired="2019-01-01",
            date_sold="2024-06-15",
            proceeds=10000.0,
            cost_basis=18000.0,
        )

        portfolio = SecuritiesPortfolio(
            additional_transactions=[st_gain, st_loss, lt_gain, lt_loss]
        )

        summary = portfolio.calculate_summary()

        # ST: 5000 gain - 3000 loss = 2000
        assert summary.get_total_short_term_gain_loss() == 2000.0
        # LT: 10000 gain - 8000 loss = 2000
        assert summary.get_total_long_term_gain_loss() == 2000.0
