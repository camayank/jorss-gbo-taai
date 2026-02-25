"""
Tests for QBI W-2 wage limitation per IRC §199A(b)(2)(B).
"""

import pytest
from decimal import Decimal
from src.calculator.qbi_calculator import QBICalculator, QBIBusinessDetail, QBIBreakdown
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, ScheduleK1, K1SourceType
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


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


class TestPerBusinessWageLimitation:
    """Tests for per-business W-2 wage limitation per IRC §199A(b)(2)(B)."""

    def test_two_businesses_different_wage_ratios_above_threshold(self):
        """
        Per-business limitation should apply to each business separately.

        Business A: $100K QBI, $80K W-2 wages (50% limit = $40K, 20% QBI = $20K) -> gets $20K
        Business B: $100K QBI, $0 W-2 wages (50% limit = $0, 20% QBI = $20K) -> gets $0

        Aggregate approach (WRONG): $200K QBI, $80K wages -> limit $40K, deduction $40K
        Per-business approach (CORRECT): $20K + $0 = $20K
        """
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        # Two K-1s with different W-2 wage situations
        k1_with_wages = ScheduleK1(
            k1_type=K1SourceType.S_CORPORATION,
            entity_name="S-Corp With Wages",
            entity_ein="11-1111111",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=80000.0,  # Has W-2 wages
            ubia_for_qbi=0.0,
            is_sstb=False,
        )
        k1_no_wages = ScheduleK1(
            k1_type=K1SourceType.S_CORPORATION,
            entity_name="S-Corp No Wages",
            entity_ein="22-2222222",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=0.0,  # No W-2 wages
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        # Note: W-2 income not needed here - taxable_income_before_qbi is passed directly
        # to the calculator and determines threshold position
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1_with_wages, k1_no_wages]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=350000.0,  # Well above $247,300 threshold
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        # Per-business breakdown should exist
        assert len(result.business_details) == 2

        # Business A (with wages): $20K deduction (20% of $100K QBI, not limited by $40K wage cap)
        biz_a = result.business_details[0]
        assert biz_a.business_name == "S-Corp With Wages"
        assert biz_a.limited_deduction == Decimal("20000")

        # Business B (no wages): $0 deduction (limited by $0 wage cap)
        biz_b = result.business_details[1]
        assert biz_b.business_name == "S-Corp No Wages"
        assert biz_b.limited_deduction == Decimal("0")

        # Total should be $20K (per-business), not $40K (aggregate)
        assert result.final_qbi_deduction == Decimal("20000")
