"""Tests for wash sale enforcement per IRC §1091."""

import pytest
from models.form_8949 import WashSaleInfo, SecurityTransaction, SecurityType


class TestWashSaleInfoModel:
    """Test WashSaleInfo model has required fields."""

    def test_holding_period_adjustment_days_field_exists(self):
        """WashSaleInfo should have holding_period_adjustment_days field."""
        info = WashSaleInfo(
            is_wash_sale=True,
            disallowed_loss=500.0,
            holding_period_adjustment_days=180,
        )
        assert info.holding_period_adjustment_days == 180

    def test_is_permanent_disallowance_field_exists(self):
        """WashSaleInfo should have is_permanent_disallowance field."""
        info = WashSaleInfo(
            is_wash_sale=True,
            disallowed_loss=500.0,
            is_permanent_disallowance=True,
        )
        assert info.is_permanent_disallowance is True

    def test_replacement_account_type_field_exists(self):
        """WashSaleInfo should have replacement_account_type field."""
        info = WashSaleInfo(
            is_wash_sale=True,
            disallowed_loss=500.0,
            replacement_account_type="ira",
        )
        assert info.replacement_account_type == "ira"

    def test_default_values(self):
        """New fields should have sensible defaults."""
        info = WashSaleInfo()
        assert info.holding_period_adjustment_days == 0
        assert info.is_permanent_disallowance is False
        assert info.replacement_account_type is None


class TestSecurityTransactionAccountType:
    """Test SecurityTransaction account type field."""

    def test_account_type_field_exists(self):
        """SecurityTransaction should have account_type field."""
        txn = SecurityTransaction(
            description="100 sh XYZ",
            date_acquired="2025-01-15",
            date_sold="2025-02-20",
            proceeds=5000.0,
            cost_basis=6000.0,
            account_type="taxable",
        )
        assert txn.account_type == "taxable"

    def test_account_type_ira(self):
        """SecurityTransaction should accept IRA account type."""
        txn = SecurityTransaction(
            description="100 sh XYZ",
            date_acquired="2025-01-15",
            date_sold="2025-02-20",
            proceeds=5000.0,
            cost_basis=6000.0,
            account_type="ira",
        )
        assert txn.account_type == "ira"

    def test_account_type_defaults_to_taxable(self):
        """Account type should default to taxable."""
        txn = SecurityTransaction(
            description="100 sh XYZ",
            date_acquired="2025-01-15",
            date_sold="2025-02-20",
            proceeds=5000.0,
            cost_basis=6000.0,
        )
        assert txn.account_type == "taxable"


class TestSecurityTransactionHoldingPeriod:
    """Test SecurityTransaction adjusted holding period field."""

    def test_adjusted_holding_period_days_field_exists(self):
        """SecurityTransaction should have adjusted_holding_period_days field."""
        txn = SecurityTransaction(
            description="100 sh XYZ",
            date_acquired="2025-01-15",
            date_sold="2025-02-20",
            proceeds=5000.0,
            cost_basis=6000.0,
            adjusted_holding_period_days=180,
        )
        assert txn.adjusted_holding_period_days == 180

    def test_adjusted_holding_period_days_defaults_to_zero(self):
        """adjusted_holding_period_days should default to 0."""
        txn = SecurityTransaction(
            description="100 sh XYZ",
            date_acquired="2025-01-15",
            date_sold="2025-02-20",
            proceeds=5000.0,
            cost_basis=6000.0,
        )
        assert txn.adjusted_holding_period_days == 0


def make_transaction(
    ticker: str,
    date_acquired: str,
    date_sold: str,
    proceeds: float,
    cost_basis: float,
    shares: float = 100.0,
    account_type: str = "taxable",
) -> SecurityTransaction:
    """Helper to create SecurityTransaction for tests."""
    return SecurityTransaction(
        description=f"{shares:.0f} sh {ticker}",
        ticker_symbol=ticker,
        date_acquired=date_acquired,
        date_sold=date_sold,
        proceeds=proceeds,
        cost_basis=cost_basis,
        shares_sold=shares,
        account_type=account_type,
    )


class TestDetectWashSalesEnhanced:
    """Test enhanced detect_wash_sales with new fields."""

    def test_detect_returns_wash_sale_info_objects(self):
        """detect_wash_sales should return WashSaleInfo objects."""
        from models.form_8949 import SecuritiesPortfolio

        # Sell at loss on Jan 15, repurchase on Jan 20 (within 30 days)
        portfolio = SecuritiesPortfolio(
            additional_transactions=[
                make_transaction("XYZ", "2024-06-01", "2025-01-15", 5000, 6000),  # Loss sale
                make_transaction("XYZ", "2025-01-20", "2025-12-01", 7000, 5000),  # Repurchase
            ]
        )
        wash_sales = portfolio.detect_wash_sales()
        assert len(wash_sales) >= 1
        # Should now return WashSaleInfo objects
        assert hasattr(wash_sales[0], 'is_wash_sale')
        assert wash_sales[0].is_wash_sale is True

    def test_detect_identifies_ira_permanent_disallowance(self):
        """detect_wash_sales should identify IRA replacements as permanent disallowance."""
        from models.form_8949 import SecuritiesPortfolio

        portfolio = SecuritiesPortfolio(
            additional_transactions=[
                make_transaction("XYZ", "2024-06-01", "2025-01-15", 5000, 6000, account_type="taxable"),
                make_transaction("XYZ", "2025-01-20", "2025-12-01", 7000, 5000, account_type="ira"),
            ]
        )
        wash_sales = portfolio.detect_wash_sales()
        assert len(wash_sales) >= 1
        ws = wash_sales[0]
        assert ws.is_permanent_disallowance is True
        assert ws.replacement_account_type == "ira"
