"""
Tests for QBI W-2 wage limitation per IRC §199A(b)(2)(B).
"""

import pytest
from decimal import Decimal
from src.calculator.qbi_calculator import QBIBusinessDetail


class TestQBIBusinessDetailModel:
    """Tests for QBIBusinessDetail dataclass."""

    def test_default_values(self):
        """QBIBusinessDetail should have sensible defaults."""
        detail = QBIBusinessDetail()
        assert detail.business_name == ""
        assert detail.business_type == "sole_proprietorship"
        assert detail.qualified_business_income == Decimal("0")
        assert detail.w2_wages == Decimal("0")
        assert detail.ubia == Decimal("0")
        assert detail.is_sstb is False

    def test_wage_limitation_fields_exist(self):
        """QBIBusinessDetail should have wage limitation calculation fields."""
        detail = QBIBusinessDetail()
        assert hasattr(detail, 'wage_limit_50_pct')
        assert hasattr(detail, 'wage_limit_25_2_5_pct')
        assert hasattr(detail, 'wage_limitation')
        assert hasattr(detail, 'tentative_deduction')
        assert hasattr(detail, 'limited_deduction')
