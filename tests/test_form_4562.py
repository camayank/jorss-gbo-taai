"""
Comprehensive Tests for Form 4562 - Depreciation and Amortization

Tests cover:
- MACRS depreciation tables (all property classes)
- Half-year, mid-quarter, mid-month conventions
- Section 179 expensing with limits and phase-outs
- Bonus depreciation (40% for 2025)
- Listed property (Section 280F)
- Amortization (Section 197 intangibles)
- Complete form calculation
"""

import pytest
from src.models.form_4562 import (
    Form4562,
    DepreciableAsset,
    AmortizableAsset,
    MACRSPropertyClass,
    MACRSMethod,
    MACRSConvention,
    ListedPropertyType,
    AmortizationType,
    Section179Limits,
    Section280FLimits,
    BonusDepreciationRates,
    DepreciationCalculator,
    MACRS_200DB_HY,
    MACRS_150DB_HY,
)


# =============================================================================
# MACRS Depreciation Table Tests
# =============================================================================

class TestMACRSTables:
    """Verify MACRS depreciation tables match IRS Publication 946."""

    def test_5_year_property_rates_sum_to_100(self):
        """5-year MACRS rates should sum to 100%."""
        rates = MACRS_200DB_HY[5]
        assert abs(sum(rates) - 1.0) < 0.0001

    def test_7_year_property_rates_sum_to_100(self):
        """7-year MACRS rates should sum to 100%."""
        rates = MACRS_200DB_HY[7]
        assert abs(sum(rates) - 1.0) < 0.0001

    def test_15_year_property_rates_sum_to_100(self):
        """15-year MACRS rates should sum to 100%."""
        rates = MACRS_150DB_HY[15]
        assert abs(sum(rates) - 1.0) < 0.0001

    def test_5_year_first_year_rate(self):
        """5-year property first year rate is 20%."""
        assert MACRS_200DB_HY[5][0] == 0.20

    def test_7_year_first_year_rate(self):
        """7-year property first year rate is 14.29%."""
        assert abs(MACRS_200DB_HY[7][0] - 0.1429) < 0.0001


# =============================================================================
# DepreciableAsset Model Tests
# =============================================================================

class TestDepreciableAsset:
    """Test DepreciableAsset model calculations."""

    def test_year_placed_in_service(self):
        """Extract year from date placed in service."""
        asset = DepreciableAsset(
            description="Computer",
            date_placed_in_service="2025-06-15",
            cost_basis=2000.0
        )
        assert asset.get_year_placed_in_service() == 2025

    def test_month_placed_in_service(self):
        """Extract month from date placed in service."""
        asset = DepreciableAsset(
            description="Computer",
            date_placed_in_service="2025-06-15",
            cost_basis=2000.0
        )
        assert asset.get_month_placed_in_service() == 6

    def test_quarter_placed_in_service(self):
        """Calculate quarter from date."""
        asset_q1 = DepreciableAsset(
            description="Q1 Asset",
            date_placed_in_service="2025-02-15",
            cost_basis=1000.0
        )
        asset_q4 = DepreciableAsset(
            description="Q4 Asset",
            date_placed_in_service="2025-11-15",
            cost_basis=1000.0
        )
        assert asset_q1.get_quarter_placed_in_service() == 1
        assert asset_q4.get_quarter_placed_in_service() == 4

    def test_depreciable_basis_after_179_and_bonus(self):
        """Depreciable basis reduced by Section 179 and bonus."""
        asset = DepreciableAsset(
            description="Equipment",
            date_placed_in_service="2025-03-01",
            cost_basis=50000.0,
            section_179_elected=20000.0,
            bonus_depreciation_elected=12000.0
        )
        # Basis = 50000 - 20000 - 12000 = 18000
        assert asset.get_depreciable_basis() == 18000.0

    def test_year_in_service_calculation(self):
        """Calculate year in service correctly."""
        asset = DepreciableAsset(
            description="Furniture",
            date_placed_in_service="2023-01-15",
            cost_basis=10000.0
        )
        assert asset.get_year_in_service(2023) == 1
        assert asset.get_year_in_service(2024) == 2
        assert asset.get_year_in_service(2025) == 3


# =============================================================================
# Section 179 Tests (Part I)
# =============================================================================

class TestSection179:
    """Test Section 179 expensing calculations."""

    def test_basic_section_179_deduction(self):
        """Basic Section 179 deduction within limits."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Office Equipment",
            date_placed_in_service="2025-04-01",
            cost_basis=50000.0,
            section_179_elected=50000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        result = form.calculate_section_179_deduction(business_income=100000.0)

        assert result['total_elected'] == 50000.0
        assert result['allowed_deduction'] == 50000.0
        assert result['carryover_to_next_year'] == 0.0

    def test_section_179_business_income_limitation(self):
        """Section 179 limited to taxable business income."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Equipment",
            date_placed_in_service="2025-04-01",
            cost_basis=100000.0,
            section_179_elected=100000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        # Business income only $30,000
        result = form.calculate_section_179_deduction(business_income=30000.0)

        assert result['total_elected'] == 100000.0
        assert result['allowed_deduction'] == 30000.0
        assert result['carryover_to_next_year'] == 70000.0

    def test_section_179_phase_out(self):
        """Section 179 phases out above threshold."""
        form = Form4562(tax_year=2025)

        # Add $3,200,000 of property (above $3,130,000 threshold)
        form.add_asset(DepreciableAsset(
            description="Heavy Equipment",
            date_placed_in_service="2025-01-15",
            cost_basis=3200000.0,
            section_179_elected=1250000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        result = form.calculate_section_179_deduction(business_income=2000000.0)

        # Phase-out: $3,200,000 - $3,130,000 = $70,000 reduction
        # Adjusted limit: $1,250,000 - $70,000 = $1,180,000
        assert result['phase_out_reduction'] == 70000.0
        assert result['adjusted_limit'] == 1180000.0
        assert result['allowed_deduction'] == 1180000.0

    def test_section_179_suv_limit(self):
        """Section 179 SUV limit ($30,500 for 2025)."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Heavy SUV",
            date_placed_in_service="2025-05-01",
            cost_basis=70000.0,
            section_179_elected=70000.0,
            vehicle_is_qualified_suv=True,
            property_class=MACRSPropertyClass.YEAR_5
        ))

        result = form.calculate_section_179_deduction(business_income=100000.0)

        # Limited to SUV cap
        assert result['assets'][0]['elected'] == Section179Limits.SUV_LIMIT

    def test_section_179_zero_business_income(self):
        """Section 179 with zero business income creates full carryover."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Equipment",
            date_placed_in_service="2025-03-01",
            cost_basis=25000.0,
            section_179_elected=25000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        result = form.calculate_section_179_deduction(business_income=0.0)

        assert result['allowed_deduction'] == 0.0
        assert result['carryover_to_next_year'] == 25000.0


# =============================================================================
# Bonus Depreciation Tests (Part II)
# =============================================================================

class TestBonusDepreciation:
    """Test bonus depreciation calculations."""

    def test_bonus_rate_2025(self):
        """2025 bonus depreciation rate is 40%."""
        assert BonusDepreciationRates.get_rate(2025) == 0.40

    def test_bonus_rate_2024(self):
        """2024 bonus depreciation rate is 60%."""
        assert BonusDepreciationRates.get_rate(2024) == 0.60

    def test_bonus_rate_phase_out(self):
        """Bonus depreciation phases out over time."""
        assert BonusDepreciationRates.get_rate(2022) == 1.00
        assert BonusDepreciationRates.get_rate(2023) == 0.80
        assert BonusDepreciationRates.get_rate(2026) == 0.20
        assert BonusDepreciationRates.get_rate(2027) == 0.00

    def test_basic_bonus_depreciation(self):
        """Calculate bonus depreciation on new 5-year property."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Computer Equipment",
            date_placed_in_service="2025-06-01",
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5
        ))

        result = form.calculate_bonus_depreciation()

        # 40% of $10,000 = $4,000
        assert result['rate'] == 0.40
        assert result['total_bonus'] == 4000.0

    def test_bonus_after_section_179(self):
        """Bonus depreciation calculated after Section 179."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Equipment",
            date_placed_in_service="2025-03-01",
            cost_basis=50000.0,
            section_179_elected=20000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        result = form.calculate_bonus_depreciation()

        # Bonus basis = $50,000 - $20,000 = $30,000
        # Bonus = $30,000 × 40% = $12,000
        assert result['total_bonus'] == 12000.0

    def test_bonus_opt_out(self):
        """No bonus when taxpayer elects out."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Equipment",
            date_placed_in_service="2025-03-01",
            cost_basis=50000.0,
            opted_out_of_bonus=True,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        result = form.calculate_bonus_depreciation()

        assert result['total_bonus'] == 0.0

    def test_bonus_not_on_real_property(self):
        """Real property (27.5/39 year) not eligible for bonus."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Commercial Building",
            date_placed_in_service="2025-01-15",
            cost_basis=500000.0,
            property_class=MACRSPropertyClass.YEAR_39
        ))

        result = form.calculate_bonus_depreciation()

        assert result['total_bonus'] == 0.0

    def test_bonus_prior_year_asset_excluded(self):
        """Assets from prior years not eligible for bonus."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Prior Year Asset",
            date_placed_in_service="2024-06-01",  # Prior year
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5
        ))

        result = form.calculate_bonus_depreciation()

        assert result['total_bonus'] == 0.0


# =============================================================================
# MACRS Depreciation Tests (Part III)
# =============================================================================

class TestMACRSDepreciation:
    """Test MACRS depreciation calculations."""

    def test_5_year_first_year_half_year(self):
        """5-year property first year with half-year convention."""
        form = Form4562(tax_year=2025)
        asset = DepreciableAsset(
            description="Computer",
            date_placed_in_service="2025-06-01",
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            convention=MACRSConvention.HALF_YEAR,
            opted_out_of_bonus=True  # No bonus to simplify test
        )

        depreciation = form.calculate_macrs_depreciation(asset)

        # Year 1: 20% of $10,000 = $2,000
        assert depreciation == 2000.0

    def test_7_year_property_depreciation(self):
        """7-year property depreciation with half-year convention."""
        form = Form4562(tax_year=2025)
        asset = DepreciableAsset(
            description="Office Furniture",
            date_placed_in_service="2025-03-15",
            cost_basis=7000.0,
            property_class=MACRSPropertyClass.YEAR_7,
            convention=MACRSConvention.HALF_YEAR,
            opted_out_of_bonus=True
        )

        depreciation = form.calculate_macrs_depreciation(asset)

        # Year 1: 14.29% of $7,000 = $1,000.30
        assert abs(depreciation - 1000.30) < 0.01

    def test_second_year_depreciation(self):
        """Second year depreciation calculation."""
        form = Form4562(tax_year=2025)
        asset = DepreciableAsset(
            description="Equipment",
            date_placed_in_service="2024-04-01",  # Prior year
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            convention=MACRSConvention.HALF_YEAR,
            opted_out_of_bonus=True,
            prior_depreciation=2000.0  # First year taken
        )

        depreciation = form.calculate_macrs_depreciation(asset)

        # Year 2: 32% of $10,000 = $3,200
        assert depreciation == 3200.0

    def test_27_5_year_mid_month_convention(self):
        """Residential rental property with mid-month convention."""
        form = Form4562(tax_year=2025)
        asset = DepreciableAsset(
            description="Rental House",
            date_placed_in_service="2025-06-15",  # June
            cost_basis=275000.0,
            property_class=MACRSPropertyClass.YEAR_27_5,
            convention=MACRSConvention.MID_MONTH,
            opted_out_of_bonus=True
        )

        depreciation = form.calculate_macrs_depreciation(asset)

        # June placement: 1.970% first year (7.5 months / 27.5 × 12)
        # $275,000 × 0.01970 = $5,417.50
        expected = 275000.0 * 0.01970
        assert abs(depreciation - expected) < 1.0

    def test_39_year_nonresidential(self):
        """Nonresidential real property depreciation."""
        form = Form4562(tax_year=2025)
        asset = DepreciableAsset(
            description="Office Building",
            date_placed_in_service="2025-01-15",
            cost_basis=390000.0,
            property_class=MACRSPropertyClass.YEAR_39,
            convention=MACRSConvention.MID_MONTH,
            opted_out_of_bonus=True
        )

        depreciation = form.calculate_macrs_depreciation(asset)

        # January placement: 2.461% first year
        expected = 390000.0 * 0.02461
        assert abs(depreciation - expected) < 1.0

    def test_business_use_percentage_applied(self):
        """Depreciation limited by business use percentage."""
        form = Form4562(tax_year=2025)
        asset = DepreciableAsset(
            description="Computer",
            date_placed_in_service="2025-06-01",
            cost_basis=10000.0,
            business_use_percentage=0.80,  # 80% business use
            property_class=MACRSPropertyClass.YEAR_5,
            opted_out_of_bonus=True
        )

        depreciation = form.calculate_macrs_depreciation(asset)

        # Year 1: 20% of ($10,000 × 80%) = 20% of $8,000 = $1,600
        assert depreciation == 1600.0


# =============================================================================
# Listed Property Tests (Part V)
# =============================================================================

class TestListedProperty:
    """Test listed property (Section 280F) limitations."""

    def test_passenger_auto_first_year_limit(self):
        """Passenger auto depreciation limited by Section 280F."""
        form = Form4562(tax_year=2025)
        asset = DepreciableAsset(
            description="Company Car",
            date_placed_in_service="2025-04-01",
            cost_basis=45000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            is_listed_property=True,
            is_vehicle=True,
            listed_property_type=ListedPropertyType.PASSENGER_AUTO,
            opted_out_of_bonus=True
        )

        depreciation = form.calculate_macrs_depreciation(asset)

        # Without bonus, first year limit is $12,400
        assert depreciation <= Section280FLimits.YEAR_1_WITHOUT_BONUS

    def test_listed_property_under_50_percent_no_bonus(self):
        """Listed property under 50% business use: no bonus depreciation."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Vehicle",
            date_placed_in_service="2025-06-01",
            cost_basis=30000.0,
            business_use_percentage=0.40,  # Under 50%
            is_listed_property=True,
            property_class=MACRSPropertyClass.YEAR_5
        ))

        result = form.calculate_bonus_depreciation()

        assert result['total_bonus'] == 0.0


# =============================================================================
# Amortization Tests (Part VI)
# =============================================================================

class TestAmortization:
    """Test amortization calculations."""

    def test_section_197_15_year_amortization(self):
        """Section 197 intangibles amortize over 15 years (180 months)."""
        asset = AmortizableAsset(
            description="Goodwill",
            date_acquired="2025-01-01",
            cost_basis=180000.0,
            amortization_type=AmortizationType.SECTION_197,
            amortization_period_months=180
        )

        annual = asset.get_annual_amortization(2025)

        # $180,000 / 180 months × 12 months = $12,000/year
        assert annual == 12000.0

    def test_startup_costs_amortization(self):
        """Startup costs amortize over 180 months (Section 195)."""
        asset = AmortizableAsset(
            description="Startup Legal Fees",
            date_acquired="2025-04-01",
            cost_basis=18000.0,
            amortization_type=AmortizationType.STARTUP_COSTS,
            amortization_period_months=180
        )

        annual = asset.get_annual_amortization(2025)

        # First year: 9 months (April-December)
        # $18,000 / 180 × 9 = $900
        assert annual == 900.0

    def test_full_year_amortization(self):
        """Full year amortization after first year."""
        asset = AmortizableAsset(
            description="Customer List",
            date_acquired="2024-01-01",
            cost_basis=90000.0,
            amortization_type=AmortizationType.SECTION_197,
            amortization_period_months=180
        )

        # Second full year
        annual = asset.get_annual_amortization(2025)

        # $90,000 / 180 × 12 = $6,000
        assert annual == 6000.0

    def test_form_amortization_total(self):
        """Form calculates total amortization across all assets."""
        form = Form4562(tax_year=2025)
        form.add_amortizable(AmortizableAsset(
            description="Goodwill",
            date_acquired="2025-01-01",
            cost_basis=150000.0,
            amortization_type=AmortizationType.SECTION_197
        ))
        form.add_amortizable(AmortizableAsset(
            description="Covenant",
            date_acquired="2025-01-01",
            cost_basis=30000.0,
            amortization_type=AmortizationType.SECTION_197
        ))

        result = form.calculate_amortization()

        # $180,000 / 180 × 12 = $12,000 total
        assert result['total_amortization'] == 12000.0


# =============================================================================
# Mid-Quarter Convention Tests
# =============================================================================

class TestMidQuarterConvention:
    """Test mid-quarter convention detection."""

    def test_mid_quarter_not_required(self):
        """Mid-quarter not required when Q4 is under 40%."""
        form = Form4562(tax_year=2025)

        # Add assets spread across quarters
        form.add_asset(DepreciableAsset(
            description="Q1 Equipment",
            date_placed_in_service="2025-02-15",
            cost_basis=30000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))
        form.add_asset(DepreciableAsset(
            description="Q4 Equipment",
            date_placed_in_service="2025-11-15",
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        must_use_mq, quarterly = form.check_mid_quarter_convention()

        # Q4 = $10,000 / $40,000 = 25% (under 40%)
        assert must_use_mq is False

    def test_mid_quarter_required(self):
        """Mid-quarter required when Q4 exceeds 40%."""
        form = Form4562(tax_year=2025)

        # Most property in Q4
        form.add_asset(DepreciableAsset(
            description="Q1 Equipment",
            date_placed_in_service="2025-02-15",
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))
        form.add_asset(DepreciableAsset(
            description="Q4 Equipment",
            date_placed_in_service="2025-11-15",
            cost_basis=30000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        must_use_mq, quarterly = form.check_mid_quarter_convention()

        # Q4 = $30,000 / $40,000 = 75% (over 40%)
        assert must_use_mq is True

    def test_real_property_excluded_from_mid_quarter(self):
        """Real property excluded from mid-quarter calculation."""
        form = Form4562(tax_year=2025)

        # Q4 building (excluded from test)
        form.add_asset(DepreciableAsset(
            description="Building",
            date_placed_in_service="2025-11-15",
            cost_basis=500000.0,
            property_class=MACRSPropertyClass.YEAR_39
        ))
        # Q1 equipment
        form.add_asset(DepreciableAsset(
            description="Equipment",
            date_placed_in_service="2025-02-15",
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        must_use_mq, quarterly = form.check_mid_quarter_convention()

        # Building excluded, only Q1 equipment counts
        # Q4 = 0%
        assert must_use_mq is False


# =============================================================================
# Complete Form Calculation Tests
# =============================================================================

class TestCompleteFormCalculation:
    """Test complete Form 4562 calculation."""

    def test_complete_form_all_parts(self):
        """Complete form calculation with all parts populated."""
        form = Form4562(
            tax_year=2025,
            business_name="Test Business",
            carryover_from_prior_year=5000.0
        )

        # Part I: Section 179 asset
        form.add_asset(DepreciableAsset(
            description="Heavy Equipment",
            date_placed_in_service="2025-03-01",
            cost_basis=100000.0,
            section_179_elected=50000.0,
            property_class=MACRSPropertyClass.YEAR_7
        ))

        # Part II/III: Regular MACRS asset
        form.add_asset(DepreciableAsset(
            description="Computer",
            date_placed_in_service="2025-06-01",
            cost_basis=5000.0,
            property_class=MACRSPropertyClass.YEAR_5
        ))

        # Part VI: Amortization
        form.add_amortizable(AmortizableAsset(
            description="Goodwill",
            date_acquired="2025-01-01",
            cost_basis=60000.0,
            amortization_type=AmortizationType.SECTION_197
        ))

        result = form.calculate(business_income=150000.0)

        # Verify all parts present
        assert 'part_i_section_179' in result
        assert 'part_ii_bonus_depreciation' in result
        assert 'part_iii_macrs' in result
        assert 'part_iv_summary' in result
        assert 'part_v_listed_property' in result
        assert 'part_vi_amortization' in result

        # Verify totals
        assert result['total_depreciation'] > 0
        assert result['total_amortization'] > 0
        assert result['total_deduction'] > 0

    def test_no_assets(self):
        """Form with no assets returns zero deduction."""
        form = Form4562(tax_year=2025)
        result = form.calculate(business_income=50000.0)

        assert result['total_depreciation'] == 0.0
        assert result['total_amortization'] == 0.0
        assert result['total_deduction'] == 0.0


# =============================================================================
# Depreciation Calculator Tests
# =============================================================================

class TestDepreciationCalculator:
    """Test standalone DepreciationCalculator."""

    def test_single_asset_calculation(self):
        """Calculate depreciation for single asset."""
        calc = DepreciationCalculator(tax_year=2025)

        result = calc.calculate_single_asset_depreciation(
            cost_basis=10000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            date_placed_in_service="2025-06-01",
            section_179=0.0,
            bonus_depreciation=4000.0,  # 40%
            business_use_pct=1.0
        )

        assert result['bonus_depreciation'] == 4000.0
        assert result['total_current_year'] > 0
        assert result['remaining_basis'] < 10000.0

    def test_full_section_179_with_bonus(self):
        """Combined Section 179 and bonus depreciation."""
        calc = DepreciationCalculator(tax_year=2025)

        result = calc.calculate_single_asset_depreciation(
            cost_basis=50000.0,
            property_class=MACRSPropertyClass.YEAR_7,
            date_placed_in_service="2025-03-01",
            section_179=20000.0,
            bonus_depreciation=12000.0,  # 40% of remaining $30k
            business_use_pct=1.0
        )

        assert result['section_179'] == 20000.0
        assert result['bonus_depreciation'] == 12000.0
        # MACRS on remaining $18,000
        assert result['macrs_depreciation'] > 0


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_cost_basis(self):
        """Asset with zero cost basis."""
        asset = DepreciableAsset(
            description="Gift Asset",
            date_placed_in_service="2025-01-01",
            cost_basis=0.0,
            property_class=MACRSPropertyClass.YEAR_7
        )
        form = Form4562(tax_year=2025)
        depreciation = form.calculate_macrs_depreciation(asset)
        assert depreciation == 0.0

    def test_fully_depreciated_asset(self):
        """Fully depreciated asset returns zero."""
        asset = DepreciableAsset(
            description="Old Computer",
            date_placed_in_service="2019-01-01",
            cost_basis=5000.0,
            property_class=MACRSPropertyClass.YEAR_5,
            prior_depreciation=5000.0  # Fully depreciated
        )
        assert asset.is_fully_depreciated() is True

    def test_section_179_exceeds_cost(self):
        """Section 179 limited to cost basis."""
        form = Form4562(tax_year=2025)
        form.add_asset(DepreciableAsset(
            description="Equipment",
            date_placed_in_service="2025-03-01",
            cost_basis=10000.0,
            section_179_elected=20000.0,  # More than cost
            property_class=MACRSPropertyClass.YEAR_7
        ))

        result = form.calculate_section_179_deduction(business_income=50000.0)

        # Limited to cost basis
        assert result['assets'][0]['elected'] == 10000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
