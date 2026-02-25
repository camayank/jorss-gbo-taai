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


class TestUBIAAlternativeCalculation:
    """Tests for 25% W-2 + 2.5% UBIA alternative calculation."""

    def test_ubia_alternative_greater_than_50_pct_wages(self):
        """
        When 25% W-2 + 2.5% UBIA > 50% W-2, use the greater amount.

        W-2 wages: $20K → 50% = $10K, 25% = $5K
        UBIA: $400K → 2.5% = $10K
        25% + 2.5% = $15K (greater than $10K)
        """
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.S_CORPORATION,
            entity_name="Capital-Heavy Business",
            entity_ein="33-3333333",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=20000.0,
            ubia_for_qbi=400000.0,  # Large UBIA
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=300000.0,  # Above threshold
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        biz = result.business_details[0]

        # 50% of W-2 = $10K
        assert biz.wage_limit_50_pct == Decimal("10000")

        # 25% of W-2 + 2.5% of UBIA = $5K + $10K = $15K
        assert biz.wage_limit_25_2_5_pct == Decimal("15000")

        # Greater of the two = $15K
        assert biz.wage_limitation == Decimal("15000")

        # Limited deduction = min($20K tentative, $15K limit) = $15K
        assert biz.limited_deduction == Decimal("15000")


class TestPhaseInRangePerBusiness:
    """Tests for partial wage limitation in phase-in range."""

    def test_phase_in_partial_limitation(self):
        """
        In phase-in range, wage limitation is applied proportionally per business.

        Single threshold: $197,300 start, $247,300 end ($50K range)
        At $222,300 taxable income: 50% through phase-in

        Business: $100K QBI, $10K W-2 wages
        Tentative: $20K (20% of $100K)
        Wage limit: $5K (50% of $10K)
        Reduction: $15K ($20K - $5K)
        Phased reduction: $7,500 (50% × $15K)
        Limited: $12,500 ($20K - $7,500)
        """
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Phase-In Business",
            entity_ein="44-4444444",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=10000.0,
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        # Exactly 50% through phase-in: ($197,300 + $247,300) / 2 = $222,300
        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=222300.0,
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        assert result.phase_in_ratio == pytest.approx(Decimal("0.5"), rel=0.01)

        biz = result.business_details[0]
        assert biz.tentative_deduction == Decimal("20000")
        assert biz.wage_limitation == Decimal("5000")
        # Limited = $20K - (50% × $15K) = $12,500
        assert biz.limited_deduction == pytest.approx(Decimal("12500"), rel=0.01)


class TestQBIWarnings:
    """Tests for QBI warning generation."""

    def test_scorp_with_zero_wages_generates_warning(self):
        """S-corp with QBI but $0 W-2 wages should generate warning."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.S_CORPORATION,
            entity_name="Zero Wage S-Corp",
            entity_ein="55-5555555",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=0.0,  # No wages!
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=150000.0,  # Below threshold for now
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        warnings = calculator.get_qbi_warnings(result)

        assert len(warnings) >= 1
        assert "Zero Wage S-Corp" in warnings[0]
        assert "$0 W-2 wages" in warnings[0]
        assert "K-1 Box 17 Code V" in warnings[0]

    def test_partnership_above_threshold_with_zero_wages_generates_warning(self):
        """Partnership above threshold with $0 wages should warn about limitation."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Zero Wage Partnership",
            entity_ein="66-6666666",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=0.0,
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=300000.0,  # Above threshold
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        warnings = calculator.get_qbi_warnings(result)

        assert len(warnings) >= 1
        assert "Zero Wage Partnership" in warnings[0]
        assert "$0 W-2 wage limitation" in warnings[0]


class TestQBIEdgeCases:
    """Edge case tests for per-business QBI calculation."""

    def test_sole_proprietorship_no_wage_limit_below_threshold(self):
        """Sole prop below threshold should get full 20% (no wage limitation)."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=50000.0,
                self_employment_expenses=0.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=50000.0,
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        assert len(result.business_details) == 1
        biz = result.business_details[0]
        assert biz.business_type == "sole_proprietorship"
        assert biz.limited_deduction == Decimal("10000")  # Full 20%

    def test_mixed_se_and_k1_businesses(self):
        """Mixed self-employment and K-1 income should create separate businesses."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="K1 Business",
            entity_ein="77-7777777",
            ordinary_business_income=30000.0,
            qbi_ordinary_income=30000.0,
            w2_wages_for_qbi=0.0,
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=20000.0,
                self_employment_expenses=0.0,
                schedule_k1_forms=[k1],
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=50000.0,
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        # Should have 2 businesses
        assert len(result.business_details) == 2

        # First is Schedule C
        assert result.business_details[0].business_name == "Self-Employment (Schedule C)"
        assert result.business_details[0].qualified_business_income == Decimal("20000")

        # Second is K-1
        assert result.business_details[1].business_name == "K1 Business"
        assert result.business_details[1].qualified_business_income == Decimal("30000")

        # Total QBI = $50K, deduction = $10K
        assert result.final_qbi_deduction == Decimal("10000")

    def test_no_qbi_returns_empty_business_details(self):
        """No QBI income should return empty business_details."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(wages=100000.0),  # Only W-2 wages, no QBI
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=100000.0,
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        assert len(result.business_details) == 0
        assert result.final_qbi_deduction == Decimal("0")
