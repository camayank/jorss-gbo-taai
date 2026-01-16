"""
Comprehensive tests for MACRS Depreciation (Form 4562 / IRC Section 168).

Tests cover:
- Section 179 immediate expensing
- Bonus depreciation (60% for 2025)
- MACRS depreciation tables (3, 5, 7, 10, 15, 20-year property)
- Real property depreciation (27.5, 39-year)
- Half-year convention
- Listed property restrictions
- Business use percentage adjustments
- Section 179 phaseout
"""

import pytest
from models.income import (
    Income,
    DepreciableAsset,
    MACRSPropertyClass,
    MACRSConvention,
    W2Info,
)
from models.deductions import Deductions
from models.credits import TaxCredits
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig


# ============================================
# Helper Functions
# ============================================

def make_taxpayer(filing_status: FilingStatus = FilingStatus.SINGLE) -> TaxpayerInfo:
    """Create a basic taxpayer for testing."""
    return TaxpayerInfo(
        first_name="Test",
        last_name="Taxpayer",
        ssn="123-45-6789",
        filing_status=filing_status,
    )


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Create a W2 for testing."""
    return W2Info(
        employer_name="Test Employer",
        employer_ein="12-3456789",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


def make_return(
    filing_status: FilingStatus = FilingStatus.SINGLE,
    income: Income = None,
    deductions: Deductions = None,
) -> TaxReturn:
    """Create a tax return for testing."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=make_taxpayer(filing_status),
        income=income or Income(),
        deductions=deductions or Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )


def make_asset(
    description: str = "Test Asset",
    cost_basis: float = 10000.0,
    property_class: MACRSPropertyClass = MACRSPropertyClass.YEAR_7,
    date_placed: str = "2025-01-15",
    section_179: float = 0.0,
    bonus_amount: float = 0.0,
    opted_out_bonus: bool = False,
    business_use_pct: float = 100.0,
    is_listed: bool = False,
    disposed: bool = False,
) -> DepreciableAsset:
    """Create a depreciable asset for testing."""
    return DepreciableAsset(
        description=description,
        cost_basis=cost_basis,
        property_class=property_class,
        date_placed_in_service=date_placed,
        section_179_amount=section_179,
        bonus_depreciation_amount=bonus_amount,
        opted_out_bonus=opted_out_bonus,
        business_use_percentage=business_use_pct,
        is_listed_property=is_listed,
        disposed=disposed,
    )


# ============================================
# Test: No Assets
# ============================================

class TestNoAssets:
    """Test behavior when no depreciable assets exist."""

    def test_no_assets_returns_zero_depreciation(self):
        """No assets should return zero depreciation."""
        engine = FederalTaxEngine()
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)])
        )
        result = engine.calculate(tax_return)

        assert result.depreciation_breakdown['total_depreciation'] == 0.0
        assert result.depreciation_breakdown['asset_count'] == 0

    def test_empty_asset_list(self):
        """Empty asset list should return zero."""
        engine = FederalTaxEngine()
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        assert result.depreciation_breakdown['total_depreciation'] == 0.0


# ============================================
# Test: Section 179 Expensing
# ============================================

class TestSection179:
    """Test Section 179 immediate expensing."""

    def test_basic_section_179_deduction(self):
        """Section 179 should allow immediate expense of asset."""
        engine = FederalTaxEngine()
        asset = make_asset(
            description="Office Equipment",
            cost_basis=50000.0,
            property_class=MACRSPropertyClass.YEAR_7,
            section_179=50000.0,
            opted_out_bonus=True,  # No bonus, just 179
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        assert depr['total_section_179'] == 50000.0
        assert depr['total_depreciation'] == 50000.0
        # No MACRS since fully expensed
        assert depr['total_macrs_depreciation'] == 0.0

    def test_section_179_respects_limit(self):
        """Section 179 should respect the annual limit ($1,220,000 for 2025)."""
        engine = FederalTaxEngine()
        config = engine.config

        # Request more than the limit
        asset = make_asset(
            cost_basis=1500000.0,
            section_179=1500000.0,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(200000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Should be capped at limit
        assert depr['total_section_179'] == config.section_179_limit
        assert depr['section_179_limit'] == config.section_179_limit

    def test_section_179_phaseout(self):
        """Section 179 phases out when total property exceeds threshold."""
        engine = FederalTaxEngine()
        config = engine.config

        # Place property exceeding phaseout threshold ($3,050,000)
        asset = make_asset(
            cost_basis=config.section_179_phaseout_threshold + 500000,  # $3.55M
            section_179=1000000.0,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(200000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Section 179 reduced by $500k (excess over threshold)
        expected_179 = max(0, config.section_179_limit - 500000)
        assert depr['total_section_179'] == expected_179

    def test_section_179_multiple_assets(self):
        """Section 179 should be allocated across multiple assets."""
        engine = FederalTaxEngine()

        asset1 = make_asset(
            description="Computer",
            cost_basis=30000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            section_179=30000.0,
            opted_out_bonus=True,
        )
        asset2 = make_asset(
            description="Furniture",
            cost_basis=20000.0,
            property_class=MACRSPropertyClass.YEAR_7,
            section_179=20000.0,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset1, asset2],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        assert depr['total_section_179'] == 50000.0
        assert depr['asset_count'] == 2


# ============================================
# Test: Bonus Depreciation
# ============================================

class TestBonusDepreciation:
    """Test bonus depreciation (60% for 2025)."""

    def test_automatic_bonus_depreciation(self):
        """Bonus depreciation should be applied automatically (60% for 2025)."""
        engine = FederalTaxEngine()
        config = engine.config

        asset = make_asset(
            cost_basis=100000.0,
            property_class=MACRSPropertyClass.YEAR_7,
            # No explicit bonus amount - should calculate automatically
        )
        income = Income(
            w2_forms=[make_w2(150000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        expected_bonus = 100000.0 * config.bonus_depreciation_rate  # 60%
        assert depr['total_bonus_depreciation'] == expected_bonus

    def test_opt_out_bonus_depreciation(self):
        """Taxpayer can opt out of bonus depreciation."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=100000.0,
            property_class=MACRSPropertyClass.YEAR_7,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(150000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # No bonus depreciation
        assert depr['total_bonus_depreciation'] == 0.0
        # Full MACRS instead
        assert depr['total_macrs_depreciation'] > 0

    def test_real_property_no_bonus(self):
        """Real property (27.5, 39-year) is NOT eligible for bonus depreciation."""
        engine = FederalTaxEngine()

        asset = make_asset(
            description="Rental Building",
            cost_basis=500000.0,
            property_class=MACRSPropertyClass.YEAR_27_5,  # Residential rental
        )
        income = Income(
            w2_forms=[make_w2(150000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # No bonus for real property
        assert depr['total_bonus_depreciation'] == 0.0
        # Should have MACRS depreciation instead
        assert depr['total_macrs_depreciation'] > 0

    def test_bonus_after_section_179(self):
        """Bonus applies to basis remaining after Section 179."""
        engine = FederalTaxEngine()
        config = engine.config

        asset = make_asset(
            cost_basis=100000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            section_179=40000.0,  # Expense $40k
        )
        income = Income(
            w2_forms=[make_w2(150000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Section 179: $40k
        assert depr['total_section_179'] == 40000.0
        # Bonus on remaining $60k at 60%
        remaining = 100000.0 - 40000.0
        expected_bonus = remaining * config.bonus_depreciation_rate
        assert depr['total_bonus_depreciation'] == expected_bonus


# ============================================
# Test: MACRS Tables
# ============================================

class TestMACRSTables:
    """Test MACRS depreciation tables for different property classes."""

    def test_5_year_property_year_1(self):
        """5-year property should use 20% in year 1 (half-year convention)."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            date_placed="2025-06-15",
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Year 1: 20% of $10,000 = $2,000
        assert depr['total_macrs_depreciation'] == 2000.0

    def test_7_year_property_year_1(self):
        """7-year property should use 14.29% in year 1."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_7,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Year 1: 14.29% of $10,000 = $1,429
        assert depr['total_macrs_depreciation'] == 1429.0

    def test_3_year_property(self):
        """3-year property should use 33.33% in year 1."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=9000.0,
            property_class=MACRSPropertyClass.YEAR_3,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Year 1: 33.33% of $9,000 = $2,999.70
        assert abs(depr['total_macrs_depreciation'] - 2999.7) < 0.01

    def test_15_year_property(self):
        """15-year property (land improvements) uses 150% DB."""
        engine = FederalTaxEngine()

        asset = make_asset(
            description="Parking Lot",
            cost_basis=100000.0,
            property_class=MACRSPropertyClass.YEAR_15,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Year 1: 5% of $100,000 = $5,000
        assert depr['total_macrs_depreciation'] == 5000.0


# ============================================
# Test: Real Property (27.5 and 39-Year)
# ============================================

class TestRealProperty:
    """Test real property depreciation (straight-line, mid-month)."""

    def test_residential_rental_27_5_year(self):
        """Residential rental uses 27.5-year straight-line."""
        engine = FederalTaxEngine()

        asset = make_asset(
            description="Rental House",
            cost_basis=275000.0,
            property_class=MACRSPropertyClass.YEAR_27_5,
            date_placed="2025-07-01",  # Mid-year placement
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Annual rate: 1/27.5 = 3.636%
        # Year 1 (mid-month, ~6.5 months): $275,000 * (1/27.5) * (6.5/12) = $5,417
        annual = 275000.0 / 27.5
        first_year = annual * (6.5 / 12)
        assert abs(depr['total_macrs_depreciation'] - first_year) < 1.0

    def test_commercial_building_39_year(self):
        """Commercial property uses 39-year straight-line."""
        engine = FederalTaxEngine()

        asset = make_asset(
            description="Office Building",
            cost_basis=390000.0,
            property_class=MACRSPropertyClass.YEAR_39,
            date_placed="2025-01-15",
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Annual: $390,000 / 39 = $10,000
        # Year 1 mid-month: ~$5,417
        annual = 390000.0 / 39.0
        first_year = annual * (6.5 / 12)
        assert abs(depr['total_macrs_depreciation'] - first_year) < 1.0


# ============================================
# Test: Business Use Percentage
# ============================================

class TestBusinessUsePercentage:
    """Test adjustments for partial business use."""

    def test_partial_business_use(self):
        """Depreciation should be adjusted for business use percentage."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            business_use_pct=80.0,  # 80% business use
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Business basis: $10,000 * 80% = $8,000
        # Year 1: 20% of $8,000 = $1,600
        assert depr['total_macrs_depreciation'] == 1600.0

    def test_100_percent_business_use(self):
        """100% business use should not reduce basis."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            business_use_pct=100.0,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Full depreciation: 20% of $10,000
        assert depr['total_macrs_depreciation'] == 2000.0


# ============================================
# Test: Listed Property
# ============================================

class TestListedProperty:
    """Test listed property restrictions."""

    def test_listed_property_over_50_percent(self):
        """Listed property >50% business use qualifies for MACRS."""
        engine = FederalTaxEngine()

        asset = make_asset(
            description="Business Vehicle",
            cost_basis=50000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            business_use_pct=60.0,  # 60% > 50%
            is_listed=True,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Business basis: $50,000 * 60% = $30,000
        # MACRS should be calculated
        assert depr['total_macrs_depreciation'] == 6000.0  # 20% of $30k

    def test_listed_property_50_percent_or_less(self):
        """Listed property <=50% business use requires ADS (no MACRS)."""
        engine = FederalTaxEngine()

        asset = make_asset(
            description="Personal Vehicle",
            cost_basis=50000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            business_use_pct=50.0,  # Exactly 50% = not > 50%
            is_listed=True,
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Listed property at 50% doesn't qualify for MACRS
        assert depr['total_macrs_depreciation'] == 0.0


# ============================================
# Test: Disposed Assets
# ============================================

class TestDisposedAssets:
    """Test handling of disposed assets."""

    def test_disposed_asset_no_depreciation(self):
        """Disposed assets should not receive current year depreciation (simplified)."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=10000.0,
            disposed=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Simplified: disposed assets get no depreciation
        assert depr['total_depreciation'] == 0.0


# ============================================
# Test: Multiple Assets
# ============================================

class TestMultipleAssets:
    """Test depreciation with multiple assets."""

    def test_multiple_assets_different_classes(self):
        """Multiple assets with different property classes."""
        engine = FederalTaxEngine()
        config = engine.config

        asset1 = make_asset(
            description="Computer",
            cost_basis=5000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            opted_out_bonus=True,
        )
        asset2 = make_asset(
            description="Office Furniture",
            cost_basis=7000.0,
            property_class=MACRSPropertyClass.YEAR_7,
            opted_out_bonus=True,
        )
        asset3 = make_asset(
            description="Land Improvement",
            cost_basis=50000.0,
            property_class=MACRSPropertyClass.YEAR_15,
            opted_out_bonus=True,
        )

        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset1, asset2, asset3],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        assert depr['asset_count'] == 3

        # Calculate expected:
        # 5-year: $5,000 * 20% = $1,000
        # 7-year: $7,000 * 14.29% = $1,000.30
        # 15-year: $50,000 * 5% = $2,500
        expected = 1000.0 + 1000.3 + 2500.0
        assert abs(depr['total_macrs_depreciation'] - expected) < 1.0

    def test_mixed_section_179_and_bonus(self):
        """Mix of Section 179 and bonus depreciation."""
        engine = FederalTaxEngine()
        config = engine.config

        asset1 = make_asset(
            description="Equipment A",
            cost_basis=50000.0,
            property_class=MACRSPropertyClass.YEAR_7,
            section_179=50000.0,
            opted_out_bonus=True,
        )
        asset2 = make_asset(
            description="Equipment B",
            cost_basis=100000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            # Uses automatic bonus depreciation
        )

        income = Income(
            w2_forms=[make_w2(200000)],
            depreciable_assets=[asset1, asset2],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        assert depr['asset_count'] == 2
        assert depr['total_section_179'] == 50000.0
        # Asset 2: $100k * 60% bonus = $60k
        assert depr['total_bonus_depreciation'] == 60000.0


# ============================================
# Test: Year 2+ Assets
# ============================================

class TestMultiYearDepreciation:
    """Test assets placed in service in prior years."""

    def test_asset_year_2(self):
        """Asset in year 2 of recovery period."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            date_placed="2024-01-15",  # Year 2 in 2025
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Year 2: 32% of $10,000 = $3,200
        assert depr['total_macrs_depreciation'] == 3200.0

    def test_asset_year_3(self):
        """Asset in year 3 of recovery period."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            date_placed="2023-06-01",  # Year 3 in 2025
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Year 3: 19.2% of $10,000 = $1,920
        assert depr['total_macrs_depreciation'] == 1920.0

    def test_asset_past_recovery_period(self):
        """Asset past recovery period should have no depreciation."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            date_placed="2018-01-01",  # Year 8 in 2025 (past 6-year table)
            opted_out_bonus=True,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        # Past recovery period - no more depreciation
        assert depr['total_macrs_depreciation'] == 0.0


# ============================================
# Test: Integration with Tax Calculation
# ============================================

class TestDepreciationIntegration:
    """Test depreciation integrates with overall tax calculation."""

    def test_depreciation_breakdown_populated(self):
        """Depreciation breakdown should be populated in result."""
        engine = FederalTaxEngine()

        asset = make_asset(
            cost_basis=100000.0,
            property_class=MACRSPropertyClass.YEAR_7,
        )
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        # Depreciation breakdown should exist
        assert 'depreciation_breakdown' in dir(result)
        depr = result.depreciation_breakdown
        assert 'total_depreciation' in depr
        assert 'asset_details' in depr
        assert len(depr['asset_details']) == 1

    def test_depreciation_config_values_in_result(self):
        """Config values should be reflected in result."""
        engine = FederalTaxEngine()
        config = engine.config

        asset = make_asset(cost_basis=10000.0)
        income = Income(
            w2_forms=[make_w2(100000)],
            depreciable_assets=[asset],
        )
        tax_return = make_return(income=income)
        result = engine.calculate(tax_return)

        depr = result.depreciation_breakdown
        assert depr['section_179_limit'] == config.section_179_limit
        assert depr['bonus_depreciation_rate'] == config.bonus_depreciation_rate
