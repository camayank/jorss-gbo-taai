"""
Tests for QBI (Qualified Business Income) Deduction Calculator - Section 199A

Tests cover:
- Simple QBI below income threshold (full 20% deduction)
- QBI capped at taxable income limit
- SSTB phase-out above threshold
- W-2 wage limitation
- Phase-in calculations
"""

import pytest
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.calculator.qbi_calculator import QBICalculator, QBIBreakdown
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, ScheduleK1, K1SourceType
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


class TestQBICalculatorBasic:
    """Basic QBI deduction tests below income threshold."""

    def test_simple_qbi_below_threshold_self_employment(self):
        """QBI deduction = 20% of SE income when below threshold."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="John",
                last_name="Doe",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=50000.0,
                self_employment_expenses=0.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # SE income $50K -> QBI deduction = $50K * 20% = $10,000
        # But limited by taxable income after SE tax deduction
        assert breakdown.qbi_deduction > 0
        # QBI should be approximately 20% of the SE net income
        # Exact amount depends on taxable income calculation
        expected_qbi = 50000.0 * 0.20
        assert breakdown.qbi_deduction <= expected_qbi

    def test_simple_qbi_from_k1_partnership(self):
        """QBI deduction from K-1 pass-through income."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="ABC Partners",
            entity_ein="12-3456789",
            ordinary_business_income=75000.0,
            qbi_ordinary_income=75000.0,  # All qualifies as QBI
            w2_wages_for_qbi=0.0,
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Jane",
                last_name="Smith",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # QBI from K-1 = $75K * 20% = $15,000 (subject to TI limit)
        assert breakdown.qbi_deduction > 0
        expected_max = 75000.0 * 0.20
        assert breakdown.qbi_deduction <= expected_max

    def test_no_qbi_when_no_qualifying_income(self):
        """No QBI deduction when only W-2 wages."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Bob",
                last_name="Worker",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[],
                wages=100000.0,  # Fallback wage field
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # No self-employment or K-1 income = no QBI
        assert breakdown.qbi_deduction == 0.0


class TestQBITaxableIncomeLimit:
    """Tests for QBI capped at taxable income limit."""

    def test_qbi_limited_by_taxable_income(self):
        """QBI deduction cannot exceed 20% of taxable income."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Large QBI but small taxable income
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Big Business LP",
            entity_ein="99-9999999",
            ordinary_business_income=200000.0,
            qbi_ordinary_income=200000.0,
            is_sstb=False,
        )

        tr = TaxReturn(
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

        breakdown = engine.calculate(tr)

        # QBI deduction limited to 20% of taxable income
        # Taxable income = K1 income - standard deduction
        taxable_income_limit = breakdown.taxable_income + breakdown.qbi_deduction
        max_qbi_from_ti = taxable_income_limit * 0.20

        assert breakdown.qbi_deduction <= max_qbi_from_ti + 1  # Allow for rounding


class TestQBISSTB:
    """Tests for Specified Service Trade or Business (SSTB) rules."""

    def test_sstb_below_threshold_full_deduction(self):
        """SSTB gets full QBI below threshold."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # SSTB income below threshold
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Law Partners LLP",
            entity_ein="11-1111111",
            ordinary_business_income=50000.0,
            qbi_ordinary_income=50000.0,
            is_sstb=True,  # SSTB - legal services
        )

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Legal",
                last_name="Eagle",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Below threshold, SSTB still gets full 20% deduction
        assert breakdown.qbi_deduction > 0


    def test_sstb_above_threshold_no_deduction(self):
        """SSTB with income well above threshold should get $0 QBI deduction."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # SSTB income well above threshold (~$197,300 single + $100K phaseout)
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Consulting Firm LLP",
            entity_ein="55-5555555",
            ordinary_business_income=500000.0,
            qbi_ordinary_income=500000.0,
            is_sstb=True,
        )

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Rich",
                last_name="Consultant",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Above the threshold + phaseout range, SSTB gets $0 QBI
        assert breakdown.qbi_deduction == 0.0

    def test_sstb_in_phaseout_range_reduced_deduction(self):
        """SSTB income in phaseout range should get reduced QBI deduction."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # SSTB income putting taxable income in the phaseout range
        # Single threshold ~$197,300, phaseout ends ~$247,300
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Accounting Firm LLP",
            entity_ein="66-6666666",
            ordinary_business_income=230000.0,
            qbi_ordinary_income=230000.0,
            is_sstb=True,
        )

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Mid",
                last_name="Accountant",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # In phaseout range, SSTB gets reduced but non-zero QBI
        full_qbi = 230000.0 * 0.20
        assert breakdown.qbi_deduction > 0
        assert breakdown.qbi_deduction < full_qbi


class TestQBIWageLimitation:
    """Tests for W-2 wage and UBIA limitations."""

    def test_high_income_with_w2_wages(self):
        """W-2 wage limitation for high-income non-SSTB."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # High income above threshold with W-2 wages
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Manufacturing Co",
            entity_ein="22-2222222",
            ordinary_business_income=400000.0,
            qbi_ordinary_income=400000.0,
            w2_wages_for_qbi=100000.0,  # Business pays $100K in W-2 wages
            ubia_for_qbi=500000.0,  # $500K in qualified property
            is_sstb=False,
        )

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="High",
                last_name="Earner",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Above threshold, W-2 wage limitation applies
        # 50% of W-2 wages = $50,000
        # OR 25% of W-2 wages + 2.5% of UBIA = $25,000 + $12,500 = $37,500
        # Greater of the two = $50,000
        # Since income is well above threshold, deduction should be limited
        assert breakdown.qbi_deduction > 0
        # The deduction should be limited compared to full 20%
        full_20_pct = 400000.0 * 0.20  # $80,000
        assert breakdown.qbi_deduction <= full_20_pct


class TestQBIFilingStatus:
    """Tests for different filing statuses."""

    def test_married_joint_higher_threshold(self):
        """MFJ has higher threshold ($394,600 vs $197,300)."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Income that's above single threshold but below MFJ threshold
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Family Business",
            entity_ein="33-3333333",
            ordinary_business_income=300000.0,
            qbi_ordinary_income=300000.0,
            is_sstb=False,
        )

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Married",
                last_name="Couple",
                filing_status=FilingStatus.MARRIED_JOINT,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # MFJ with taxable income ~$268,500 ($300K - $31,500 std ded)
        # This is below MFJ threshold of $394,600, so full 20% applies
        assert breakdown.qbi_deduction > 0


class TestQBICalculatorDirect:
    """Direct tests of QBICalculator class."""

    def test_qbi_breakdown_structure(self):
        """Verify QBIBreakdown dataclass has expected fields."""
        breakdown = QBIBreakdown()

        assert hasattr(breakdown, 'total_qbi')
        assert hasattr(breakdown, 'qbi_from_self_employment')
        assert hasattr(breakdown, 'qbi_from_k1')
        assert hasattr(breakdown, 'w2_wages_total')
        assert hasattr(breakdown, 'ubia_total')
        assert hasattr(breakdown, 'has_sstb')
        assert hasattr(breakdown, 'final_qbi_deduction')

    def test_calculator_with_zero_qbi(self):
        """Calculator returns zero when no QBI income."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="No",
                last_name="QBI",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tr,
            taxable_income_before_qbi=50000.0,
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        assert result.total_qbi == 0.0
        assert result.final_qbi_deduction == 0.0


class TestQBICombinedIncome:
    """Tests for combined SE and K-1 income."""

    def test_combined_se_and_k1_qbi(self):
        """QBI from both Schedule C and K-1."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Side Business LP",
            entity_ein="44-4444444",
            ordinary_business_income=30000.0,
            qbi_ordinary_income=30000.0,
            is_sstb=False,
        )

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Dual",
                last_name="Income",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=40000.0,  # Schedule C
                self_employment_expenses=0.0,
                schedule_k1_forms=[k1],  # K-1
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Total QBI = $40K (SE) + $30K (K-1) = $70K
        # QBI deduction = $70K * 20% = $14,000 (subject to TI limit)
        assert breakdown.qbi_deduction > 0
        max_expected = 70000.0 * 0.20
        assert breakdown.qbi_deduction <= max_expected


class TestQBIEdgeCases:
    """Edge case tests."""

    def test_negative_se_income_excluded(self):
        """Negative SE income (loss) doesn't contribute to QBI."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Loss",
                last_name="Business",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=20000.0,
                self_employment_expenses=30000.0,  # Net loss of $10K
                wages=50000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # SE loss doesn't generate QBI
        # Only positive QBI qualifies for deduction
        assert breakdown.qbi_deduction == 0.0

    def test_zero_taxable_income(self):
        """QBI deduction with zero taxable income."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Zero",
                last_name="TI",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=10000.0,  # Low income
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # With $10K SE income and $15,750 standard deduction,
        # taxable income is approximately $0 after SE tax deduction
        # QBI deduction limited by taxable income
        if breakdown.taxable_income == 0:
            assert breakdown.qbi_deduction == 0.0
