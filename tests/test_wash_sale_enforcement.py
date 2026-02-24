"""Tests for wash sale enforcement per IRC §1091."""

import pytest
from models.form_8949 import WashSaleInfo


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
