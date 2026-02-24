"""
Tests for QBI W-2 wage limitation per IRC §199A(b)(2)(B).
"""

import pytest
from decimal import Decimal
from src.calculator.qbi_calculator import QBIBusinessDetail, QBIBreakdown


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


class TestQBIBreakdownBusinessDetails:
    """Tests for business_details field in QBIBreakdown."""

    def test_breakdown_has_business_details_field(self):
        """QBIBreakdown should have business_details list."""
        breakdown = QBIBreakdown()
        assert hasattr(breakdown, 'business_details')
        assert isinstance(breakdown.business_details, list)
        assert len(breakdown.business_details) == 0

    def test_business_details_can_hold_qbi_business_detail(self):
        """business_details should accept QBIBusinessDetail objects."""
        breakdown = QBIBreakdown()
        detail = QBIBusinessDetail(
            business_name="Test LLC",
            qualified_business_income=Decimal("50000"),
        )
        breakdown.business_details.append(detail)
        assert len(breakdown.business_details) == 1
        assert breakdown.business_details[0].business_name == "Test LLC"
