"""
Test suite for Form 8995 - Qualified Business Income Deduction.

Tests cover:
- Simplified method (below threshold)
- Standard method (above threshold)
- W-2 wage and UBIA limitations
- SSTB (Specified Service Trade or Business) rules
- QBI loss carryforward
- REIT/PTP income
"""

import pytest
from src.models.form_8995 import (
    Form8995,
    QualifiedBusiness,
    BusinessType,
    SSTBCategory,
    calculate_qbi_deduction,
)


class TestSimplifiedMethod:
    """Tests for simplified method (Form 8995) - income below threshold."""

    def test_basic_qbi_deduction(self):
        """Basic 20% QBI deduction."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="Consulting LLC",
                    qualified_business_income=100000.0,
                )
            ],
            taxable_income_before_qbi=100000.0,
        )
        result = form.calculate_simplified_deduction()

        assert result['form_type'] == '8995'
        assert result['below_threshold'] is True
        assert result['line_2_qbi_component'] == 20000.0  # 20% of $100k
        assert result['qbi_deduction'] == 20000.0

    def test_qbi_limited_by_taxable_income(self):
        """QBI deduction limited by 20% of taxable income."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="Business",
                    qualified_business_income=100000.0,
                )
            ],
            taxable_income_before_qbi=50000.0,  # Lower than QBI
        )
        result = form.calculate_simplified_deduction()

        # 20% of $100k QBI = $20k, but limited to 20% of $50k taxable = $10k
        assert result['line_5_income_limitation'] == 10000.0
        assert result['qbi_deduction'] == 10000.0

    def test_qbi_with_capital_gain(self):
        """QBI limited by taxable income minus net capital gain."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="Business",
                    qualified_business_income=100000.0,
                )
            ],
            taxable_income_before_qbi=100000.0,
            net_capital_gain=20000.0,
        )
        result = form.calculate_simplified_deduction()

        # Income limitation: 20% × ($100k - $20k) = $16k
        assert result['line_5_income_limitation'] == 16000.0
        assert result['qbi_deduction'] == 16000.0

    def test_qbi_with_loss(self):
        """QBI loss creates carryforward."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="Business",
                    qualified_business_income=-30000.0,  # Loss
                )
            ],
            taxable_income_before_qbi=50000.0,
        )
        result = form.calculate_simplified_deduction()

        assert result['line_1_total_qbi'] == -30000.0
        assert result['qbi_deduction'] == 0.0
        assert result['new_loss_carryforward'] == 30000.0

    def test_qbi_with_prior_loss_carryforward(self):
        """Prior year QBI loss carryforward reduces current QBI."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="Business",
                    qualified_business_income=50000.0,
                )
            ],
            taxable_income_before_qbi=50000.0,
            prior_year_loss_carryforward=20000.0,
        )
        result = form.calculate_simplified_deduction()

        # Net QBI: $50k - $20k carryforward = $30k
        assert result['line_1_total_qbi'] == 30000.0
        assert result['qbi_deduction'] == 6000.0  # 20% of $30k


class TestStandardMethod:
    """Tests for standard method (Form 8995-A) - income above threshold."""

    def test_above_threshold_single(self):
        """Single filer above threshold uses standard method."""
        form = Form8995(
            filing_status="single",
            businesses=[
                QualifiedBusiness(
                    business_name="Business",
                    qualified_business_income=100000.0,
                    w2_wages=50000.0,
                    ubia=200000.0,
                )
            ],
            taxable_income_before_qbi=300000.0,  # Above $197,300 threshold
        )
        result = form.calculate_form_8995()

        assert result['form_type'] == '8995-A'
        assert result['below_threshold'] is False

    def test_wage_ubia_limitation(self):
        """W-2 wage and UBIA limitation applies above threshold."""
        form = Form8995(
            filing_status="single",
            businesses=[
                QualifiedBusiness(
                    business_name="Business",
                    qualified_business_income=200000.0,
                    w2_wages=40000.0,  # Wage limitation will apply
                    ubia=100000.0,
                )
            ],
            taxable_income_before_qbi=300000.0,
        )
        result = form.calculate_standard_deduction()

        # 20% of QBI = $40k
        # Wage limit: greater of 50% × $40k = $20k OR 25% × $40k + 2.5% × $100k = $12.5k
        # Wage limit = $20k, which is less than $40k QBI deduction
        assert result['qbi_deduction'] < 40000.0

    def test_sstb_above_threshold(self):
        """SSTB income reduced above threshold."""
        form = Form8995(
            filing_status="single",
            businesses=[
                QualifiedBusiness(
                    business_name="Law Firm",
                    qualified_business_income=100000.0,
                    is_sstb=True,
                    sstb_category=SSTBCategory.LAW,
                )
            ],
            taxable_income_before_qbi=250000.0,  # In phase-in range
        )
        result = form.calculate_standard_deduction()

        # SSTB income is reduced during phase-in
        assert result['sstb_applicable_pct'] < 100.0

    def test_sstb_fully_phased_out(self):
        """SSTB income fully excluded when above phase-in range."""
        form = Form8995(
            filing_status="single",
            businesses=[
                QualifiedBusiness(
                    business_name="Consulting",
                    qualified_business_income=100000.0,
                    is_sstb=True,
                )
            ],
            taxable_income_before_qbi=350000.0,  # Well above threshold
        )
        result = form.calculate_standard_deduction()

        assert result['sstb_applicable_pct'] == 0.0
        assert result['qbi_deduction'] == 0.0


class TestREITPTPIncome:
    """Tests for REIT dividends and PTP income."""

    def test_reit_dividends(self):
        """Qualified REIT dividends get 20% deduction."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="REIT Investment",
                    reit_dividends=10000.0,
                )
            ],
            taxable_income_before_qbi=100000.0,
        )
        result = form.calculate_simplified_deduction()

        assert result['line_3_reit_ptp_component'] == 2000.0  # 20% of $10k

    def test_ptp_income(self):
        """Qualified PTP income gets 20% deduction."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="PTP Investment",
                    ptp_income=5000.0,
                )
            ],
            taxable_income_before_qbi=100000.0,
        )
        result = form.calculate_simplified_deduction()

        assert result['line_3_reit_ptp_component'] == 1000.0  # 20% of $5k

    def test_combined_qbi_and_reit(self):
        """Combined QBI and REIT/PTP income."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="Business",
                    qualified_business_income=50000.0,
                    reit_dividends=10000.0,
                )
            ],
            taxable_income_before_qbi=100000.0,
        )
        result = form.calculate_simplified_deduction()

        # 20% of $50k QBI + 20% of $10k REIT = $10k + $2k = $12k
        assert result['line_2_qbi_component'] == 10000.0
        assert result['line_3_reit_ptp_component'] == 2000.0
        assert result['qbi_deduction'] == 12000.0


class TestMultipleBusinesses:
    """Tests for multiple businesses."""

    def test_multiple_businesses_aggregated(self):
        """Multiple businesses' QBI is aggregated."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="Business A",
                    qualified_business_income=30000.0,
                ),
                QualifiedBusiness(
                    business_name="Business B",
                    qualified_business_income=20000.0,
                ),
            ],
            taxable_income_before_qbi=100000.0,
        )
        result = form.calculate_simplified_deduction()

        # Total QBI: $30k + $20k = $50k, deduction = 20% = $10k
        assert result['qbi_totals']['net_qbi'] == 50000.0
        assert result['qbi_deduction'] == 10000.0

    def test_business_loss_offsets_gain(self):
        """Business loss offsets other business gain."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="Profitable",
                    qualified_business_income=50000.0,
                ),
                QualifiedBusiness(
                    business_name="Loss Business",
                    qualified_business_income=-20000.0,
                ),
            ],
            taxable_income_before_qbi=100000.0,
        )
        result = form.calculate_simplified_deduction()

        # Net QBI: $50k - $20k = $30k
        assert result['qbi_totals']['net_qbi'] == 30000.0
        assert result['qbi_deduction'] == 6000.0


class TestThresholds:
    """Tests for threshold determination."""

    def test_single_below_threshold(self):
        """Single filer below $197,300 threshold."""
        form = Form8995(
            filing_status="single",
            taxable_income_before_qbi=150000.0,
        )
        assert form.is_below_threshold() is True

    def test_single_above_threshold(self):
        """Single filer above threshold."""
        form = Form8995(
            filing_status="single",
            taxable_income_before_qbi=250000.0,
        )
        assert form.is_below_threshold() is False

    def test_mfj_below_threshold(self):
        """MFJ below $394,600 threshold."""
        form = Form8995(
            filing_status="married_joint",
            taxable_income_before_qbi=350000.0,
        )
        assert form.is_below_threshold() is True

    def test_mfj_above_threshold(self):
        """MFJ above threshold."""
        form = Form8995(
            filing_status="married_joint",
            taxable_income_before_qbi=450000.0,
        )
        assert form.is_below_threshold() is False


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_basic(self):
        """Calculate QBI deduction with convenience function."""
        result = calculate_qbi_deduction(
            qualified_business_income=100000.0,
            taxable_income=100000.0,
        )

        assert result['qbi_deduction'] == 20000.0

    def test_convenience_function_with_wages(self):
        """QBI with W-2 wages and UBIA."""
        result = calculate_qbi_deduction(
            qualified_business_income=100000.0,
            taxable_income=300000.0,
            w2_wages=50000.0,
            ubia=200000.0,
        )

        # Above threshold, limitations apply
        assert result['qbi_deduction'] > 0

    def test_convenience_function_sstb(self):
        """QBI for SSTB business."""
        result = calculate_qbi_deduction(
            qualified_business_income=100000.0,
            taxable_income=150000.0,
            is_sstb=True,
        )

        # Below threshold, SSTB doesn't matter
        assert result['qbi_deduction'] == 20000.0

    def test_convenience_function_with_reit(self):
        """QBI with REIT dividends."""
        result = calculate_qbi_deduction(
            qualified_business_income=50000.0,
            taxable_income=100000.0,
            reit_dividends=10000.0,
        )

        # $50k QBI + $10k REIT = $60k, 20% = $12k
        assert result['qbi_deduction'] == 12000.0


class TestSummaryMethod:
    """Tests for summary method."""

    def test_get_summary(self):
        """Get Form 8995 summary."""
        form = Form8995(
            businesses=[
                QualifiedBusiness(
                    business_name="Business",
                    qualified_business_income=50000.0,
                )
            ],
            taxable_income_before_qbi=80000.0,
        )

        summary = form.get_form_8995_summary()

        assert summary['qbi_deduction'] == 10000.0
        assert summary['below_threshold'] is True
        assert summary['new_carryforward'] == 0.0
