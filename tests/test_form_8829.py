"""
Tests for Form 8829 - Expenses for Business Use of Your Home

Comprehensive test suite covering:
- Simplified method ($5/sqft, max 300 sqft = $1,500)
- Regular method (actual expenses prorated)
- Business use percentage calculations
- Daycare facility special rules
- Profit limitation and expense carryover
- Depreciation calculations
- Schedule C integration
"""

import pytest
from src.models.form_8829 import (
    Form8829,
    Form8829Part1,
    Form8829Part2,
    Form8829Part3,
    Form8829Part4,
    HomeOfficeMethod,
    HomeType,
    BusinessUseType,
    calculate_home_office_deduction,
)


class TestForm8829Part1BusinessPercentage:
    """Test Part I: Business use percentage calculation."""

    def test_basic_business_percentage(self):
        """Test basic business percentage calculation."""
        part1 = Form8829Part1(
            line_1_business_area=200,
            line_2_total_area=2000
        )
        assert part1.line_3_business_percentage == 10.0

    def test_business_percentage_20_percent(self):
        """Test 20% business use."""
        part1 = Form8829Part1(
            line_1_business_area=400,
            line_2_total_area=2000
        )
        assert part1.line_3_business_percentage == 20.0

    def test_business_percentage_rounding(self):
        """Test percentage rounding to 2 decimals."""
        part1 = Form8829Part1(
            line_1_business_area=333,
            line_2_total_area=2000
        )
        # 333/2000 = 16.65%
        assert part1.line_3_business_percentage == 16.65

    def test_zero_total_area(self):
        """Test zero total area returns 0%."""
        part1 = Form8829Part1(
            line_1_business_area=200,
            line_2_total_area=0
        )
        assert part1.line_3_business_percentage == 0.0

    def test_zero_business_area(self):
        """Test zero business area returns 0%."""
        part1 = Form8829Part1(
            line_1_business_area=0,
            line_2_total_area=2000
        )
        assert part1.line_3_business_percentage == 0.0

    def test_100_percent_use(self):
        """Test 100% business use (separate structure)."""
        part1 = Form8829Part1(
            line_1_business_area=500,
            line_2_total_area=500
        )
        assert part1.line_3_business_percentage == 100.0


class TestForm8829Part1Daycare:
    """Test Part I: Daycare facility special rules."""

    def test_daycare_no_hours(self):
        """Test no daycare hours uses standard percentage."""
        part1 = Form8829Part1(
            line_1_business_area=500,
            line_2_total_area=2000,
            line_4_daycare_hours=0
        )
        assert part1.line_6_daycare_percentage == 0.0
        assert part1.line_7_daycare_business_pct == 25.0  # Standard %

    def test_daycare_full_time(self):
        """Test full-time daycare (8,760 hours)."""
        part1 = Form8829Part1(
            line_1_business_area=1000,
            line_2_total_area=2000,  # 50% of space
            line_4_daycare_hours=8760  # All hours
        )
        assert part1.line_6_daycare_percentage == 100.0
        assert part1.line_7_daycare_business_pct == 50.0  # 50% × 100%

    def test_daycare_partial_time(self):
        """Test partial daycare hours."""
        part1 = Form8829Part1(
            line_1_business_area=1000,
            line_2_total_area=2000,  # 50% of space
            line_4_daycare_hours=4380  # 50% of year
        )
        assert part1.line_6_daycare_percentage == 50.0
        assert part1.line_7_daycare_business_pct == 25.0  # 50% × 50%

    def test_daycare_standard_hours(self):
        """Test typical daycare hours (weekday business hours)."""
        # 10 hours/day × 5 days × 50 weeks = 2,500 hours
        part1 = Form8829Part1(
            line_1_business_area=800,
            line_2_total_area=2000,  # 40% of space
            line_4_daycare_hours=2500
        )
        # 2500/8760 = 28.54%
        assert part1.line_6_daycare_percentage == 28.54
        # 40% × 28.54% = 11.42%
        assert part1.line_7_daycare_business_pct == 11.42


class TestSimplifiedMethod:
    """Test simplified method ($5/sqft, max 300 sqft)."""

    def test_simplified_small_office(self):
        """Test simplified method with small office."""
        form = Form8829(
            method=HomeOfficeMethod.SIMPLIFIED,
            part_1=Form8829Part1(
                line_1_business_area=100,
                line_2_total_area=2000
            )
        )
        # 100 sqft × $5 = $500
        assert form.calculate_simplified_deduction() == 500.0
        assert form.deduction == 500.0

    def test_simplified_max_300_sqft(self):
        """Test simplified method at 300 sqft max."""
        form = Form8829(
            method=HomeOfficeMethod.SIMPLIFIED,
            part_1=Form8829Part1(
                line_1_business_area=300,
                line_2_total_area=2000
            )
        )
        # 300 sqft × $5 = $1,500 max
        assert form.calculate_simplified_deduction() == 1500.0
        assert form.deduction == 1500.0

    def test_simplified_over_300_sqft_capped(self):
        """Test simplified method caps at 300 sqft."""
        form = Form8829(
            method=HomeOfficeMethod.SIMPLIFIED,
            part_1=Form8829Part1(
                line_1_business_area=500,
                line_2_total_area=2000
            )
        )
        # Capped at 300 sqft × $5 = $1,500
        assert form.calculate_simplified_deduction() == 1500.0
        assert form.deduction == 1500.0

    def test_simplified_very_large_office(self):
        """Test very large office still capped at $1,500."""
        form = Form8829(
            method=HomeOfficeMethod.SIMPLIFIED,
            part_1=Form8829Part1(
                line_1_business_area=1000,
                line_2_total_area=2000
            )
        )
        assert form.deduction == 1500.0

    def test_simplified_no_carryover(self):
        """Simplified method has no carryover."""
        form = Form8829(
            method=HomeOfficeMethod.SIMPLIFIED,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000
            )
        )
        assert form.operating_expense_carryover == 0.0
        assert form.depreciation_carryover == 0.0

    def test_simplified_150_sqft(self):
        """Test simplified method 150 sqft = $750."""
        form = Form8829(
            method=HomeOfficeMethod.SIMPLIFIED,
            part_1=Form8829Part1(
                line_1_business_area=150,
                line_2_total_area=1500
            )
        )
        assert form.deduction == 750.0


class TestRegularMethodBasic:
    """Test regular method basic calculations."""

    def test_regular_method_mortgage_and_taxes(self):
        """Test regular method with mortgage interest and taxes."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000  # 10%
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=50000,
                line_17_mortgage_interest=12000,
                line_18_real_estate_taxes=6000,
            )
        )
        # Mortgage + taxes = $18,000
        # Business portion = $18,000 × 10% = $1,800
        assert form.part_2.line_19_total_casualty_mortgage_taxes == 18000
        assert form.part_2.line_20_business_portion == 1800.0

    def test_regular_method_all_indirect_expenses(self):
        """Test regular method with all indirect expenses."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=400,
                line_2_total_area=2000  # 20%
            ),
            part_2=Form8829Part2(
                business_percentage=20.0,
                line_8_tentative_profit=100000,
                line_17_mortgage_interest=12000,
                line_18_real_estate_taxes=6000,
                line_25_insurance=2400,
                line_27_repairs=1500,
                line_28_utilities=4800,
            )
        )
        # Insurance + repairs + utilities = $8,700
        assert form.part_2.line_30_total_other_indirect == 8700.0
        # Business portion = $8,700 × 20% = $1,740
        assert form.part_2.line_31_business_other_indirect == 1740.0

    def test_regular_method_direct_expenses(self):
        """Test regular method with direct expenses (100% business)."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000  # 10%
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=50000,
                line_9_direct_expenses=500,  # Office paint, repairs only in office
            )
        )
        # Direct expenses are 100% deductible
        assert form.part_2.line_22_subtotal == 500.0

    def test_regular_method_total_deduction(self):
        """Test complete regular method deduction calculation."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=300,
                line_2_total_area=2000  # 15%
            ),
            part_2=Form8829Part2(
                business_percentage=15.0,
                line_8_tentative_profit=80000,
                line_9_direct_expenses=200,
                line_17_mortgage_interest=15000,
                line_18_real_estate_taxes=5000,
                line_25_insurance=2000,
                line_28_utilities=6000,
            )
        )
        # Line 19: 15000 + 5000 = 20000
        # Line 20: 20000 × 15% = 3000
        # Line 22: 200 + 3000 = 3200
        assert form.part_2.line_22_subtotal == 3200.0

        # Line 30: 2000 + 6000 = 8000
        # Line 31: 8000 × 15% = 1200
        assert form.part_2.line_31_business_other_indirect == 1200.0

        # Line 34: min(80000 - 3200, 1200) = min(76800, 1200) = 1200
        assert form.part_2.line_34_allowable_other == 1200.0

        # Line 35: 3200 + 1200 = 4400
        assert form.part_2.line_35_subtotal_before_depreciation == 4400.0


class TestRegularMethodProfitLimitation:
    """Test regular method profit limitation rules."""

    def test_expenses_limited_by_profit(self):
        """Test expenses limited when exceeding tentative profit."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000  # 10%
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=1000,  # Low profit
                line_17_mortgage_interest=20000,
                line_18_real_estate_taxes=8000,
                line_28_utilities=10000,
            )
        )
        # Line 20: (20000 + 8000) × 10% = 2800
        # Line 22: 0 + 2800 = 2800
        # But profit is only 1000, so expenses exceed profit
        # Line 23: max(0, 1000 - 2800) = 0
        assert form.part_2.line_23_limit_for_other == 0.0

        # Line 31: 10000 × 10% = 1000 (utilities business portion)
        # Line 34: min(0, 1000) = 0 (no room for other expenses)
        assert form.part_2.line_34_allowable_other == 0.0

    def test_operating_expense_carryover(self):
        """Test operating expenses carry over when limited."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000  # 10%
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=3000,
                line_17_mortgage_interest=20000,  # 2000 business
                line_28_utilities=20000,  # 2000 business
            )
        )
        # Line 20: 20000 × 10% = 2000
        # Line 22: 2000
        # Line 23: max(0, 3000 - 2000) = 1000 (limit for other)
        assert form.part_2.line_23_limit_for_other == 1000.0

        # Line 31: 20000 × 10% = 2000
        # Line 34: min(1000, 2000) = 1000
        assert form.part_2.line_34_allowable_other == 1000.0

        # Carryover: 2000 - 1000 = 1000
        assert form.operating_expense_carryover == 1000.0
        assert form.is_deduction_limited() is True

    def test_no_carryover_when_profit_sufficient(self):
        """Test no carryover when profit covers all expenses."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000  # 10%
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=100000,
                line_17_mortgage_interest=12000,
                line_28_utilities=6000,
            )
        )
        assert form.operating_expense_carryover == 0.0
        assert form.is_deduction_limited() is False

    def test_carryover_from_prior_year(self):
        """Test using carryover from prior year."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000  # 10%
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=50000,
                line_21_carryover_operating=500,  # From prior year
                line_17_mortgage_interest=10000,
            )
        )
        # Line 22 includes carryover: 1000 (mortgage) + 500 (carryover) = 1500
        assert form.part_2.line_22_subtotal == 1500.0


class TestForm8829Part3Depreciation:
    """Test Part III: Home depreciation calculations."""

    def test_basic_depreciation(self):
        """Test basic home depreciation calculation."""
        part3 = Form8829Part3(
            line_36_basis_or_fmv=400000,
            line_37_land_value=100000,  # Land not depreciable
            line_39_business_pct=10.0,
            line_41_depreciation_pct=2.564  # 39-year SL
        )
        # Building basis: 400000 - 100000 = 300000
        assert part3.line_38_building_basis == 300000.0
        # Business basis: 300000 × 10% = 30000
        assert part3.line_40_business_basis == 30000.0
        # Depreciation: 30000 × 2.564% = 769.20
        assert part3.line_42_depreciation_allowable == 769.2

    def test_depreciation_20_percent_use(self):
        """Test depreciation with 20% business use."""
        part3 = Form8829Part3(
            line_36_basis_or_fmv=500000,
            line_37_land_value=150000,
            line_39_business_pct=20.0,
        )
        # Building: 350000, Business: 70000
        assert part3.line_40_business_basis == 70000.0
        # Depreciation: 70000 × 2.564% = 1794.80
        assert part3.line_42_depreciation_allowable == 1794.8

    def test_zero_land_value(self):
        """Test depreciation when land value not separated (condo)."""
        part3 = Form8829Part3(
            line_36_basis_or_fmv=250000,
            line_37_land_value=0,
            line_39_business_pct=15.0,
        )
        # All value is building
        assert part3.line_38_building_basis == 250000.0
        assert part3.line_40_business_basis == 37500.0
        # 37500 × 2.564% = 961.50
        assert part3.line_42_depreciation_allowable == 961.5

    def test_land_exceeds_basis(self):
        """Test when land value >= basis (edge case)."""
        part3 = Form8829Part3(
            line_36_basis_or_fmv=100000,
            line_37_land_value=120000,  # More than basis
            line_39_business_pct=10.0,
        )
        # Building basis should be 0
        assert part3.line_38_building_basis == 0.0
        assert part3.line_42_depreciation_allowable == 0.0


class TestRegularMethodWithDepreciation:
    """Test regular method including depreciation."""

    def test_depreciation_limited_by_profit(self):
        """Test depreciation limited when profit insufficient."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000  # 10%
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=2000,  # Low profit
                line_17_mortgage_interest=10000,  # $1000 business
                line_28_utilities=5000,  # $500 business
                line_37_depreciation=800,  # From Part III
            )
        )
        # Line 22: 1000 (mortgage business)
        # Line 23: max(0, 2000 - 1000) = 1000
        # Line 34: min(1000, 500) = 500
        # Line 35: 1000 + 500 = 1500
        # Line 36: max(0, 2000 - 1500) = 500 (limit for depreciation)
        assert form.part_2.line_36_limit_depreciation == 500.0

        # Line 40: min(500, 800) = 500 (depreciation limited)
        assert form.part_2.line_40_allowable_depreciation == 500.0

        # Depreciation carryover: 800 - 500 = 300
        assert form.depreciation_carryover == 300.0

    def test_depreciation_carryover_from_prior(self):
        """Test using depreciation carryover from prior year."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000  # 10%
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=50000,
                line_37_depreciation=700,
                line_38_depreciation_carryover=200,  # From prior year
            )
        )
        # Line 39: 700 + 200 = 900
        assert form.part_2.line_39_total_depreciation == 900.0


class TestForm8829Integration:
    """Test complete Form 8829 integration scenarios."""

    def test_typical_home_office_simplified(self):
        """Test typical home office using simplified method."""
        form = Form8829(
            method=HomeOfficeMethod.SIMPLIFIED,
            business_name="Consulting LLC",
            business_use_type=BusinessUseType.PRINCIPAL_PLACE,
            home_type=HomeType.HOUSE,
            part_1=Form8829Part1(
                line_1_business_area=200,  # 200 sqft office
                line_2_total_area=2500
            )
        )
        assert form.deduction == 1000.0  # 200 × $5
        assert form.business_use_percentage == 8.0
        assert form.to_schedule_c_line_30() == 1000.0

    def test_typical_home_office_regular(self):
        """Test typical home office using regular method."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            business_name="Freelance Design",
            business_use_type=BusinessUseType.PRINCIPAL_PLACE,
            home_type=HomeType.HOUSE,
            part_1=Form8829Part1(
                line_1_business_area=250,
                line_2_total_area=2000  # 12.5%
            ),
            part_2=Form8829Part2(
                business_percentage=12.5,
                line_8_tentative_profit=75000,
                line_9_direct_expenses=300,  # Office paint
                line_17_mortgage_interest=18000,  # $2,250 business
                line_18_real_estate_taxes=4800,  # $600 business
                line_25_insurance=1800,  # $225 business
                line_28_utilities=4800,  # $600 business
                line_37_depreciation=962,
            )
        )
        # Business percentage
        assert form.business_use_percentage == 12.5

        # Line 19: 18000 + 4800 = 22800
        # Line 20: 22800 × 12.5% = 2850
        # Line 22: 300 + 2850 = 3150
        assert form.part_2.line_22_subtotal == 3150.0

        # Line 30: 1800 + 4800 = 6600
        # Line 31: 6600 × 12.5% = 825
        # Line 34: min(75000 - 3150, 825) = 825
        assert form.part_2.line_34_allowable_other == 825.0

        # Line 35: 3150 + 825 = 3975
        assert form.part_2.line_35_subtotal_before_depreciation == 3975.0

        # Line 40: min(75000 - 3975, 962) = 962
        assert form.part_2.line_40_allowable_depreciation == 962.0

        # Total: 3975 + 962 = 4937
        assert form.deduction == 4937.0

    def test_renter_home_office(self):
        """Test home office for renter (no depreciation)."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            home_type=HomeType.APARTMENT,
            part_1=Form8829Part1(
                line_1_business_area=150,
                line_2_total_area=1200  # 12.5%
            ),
            part_2=Form8829Part2(
                business_percentage=12.5,
                line_8_tentative_profit=40000,
                line_26_rent=24000,  # $3,000 business
                line_28_utilities=3600,  # $450 business
            )
        )
        # Rent + utilities business: 24000 × 12.5% + 3600 × 12.5%
        assert form.part_2.line_31_business_other_indirect == 3450.0
        assert form.deduction == 3450.0

    def test_separate_structure(self):
        """Test separate structure (100% business use)."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            business_use_type=BusinessUseType.SEPARATE_STRUCTURE,
            part_1=Form8829Part1(
                line_1_business_area=400,
                line_2_total_area=400  # 100% - it's a separate building
            ),
            part_2=Form8829Part2(
                business_percentage=100.0,
                line_8_tentative_profit=60000,
                line_28_utilities=2400,
                line_37_depreciation=1500,
            )
        )
        assert form.business_use_percentage == 100.0
        # Utilities 100% deductible
        assert form.part_2.line_31_business_other_indirect == 2400.0
        # Total: 2400 + 1500 = 3900
        assert form.deduction == 3900.0


class TestConvenienceFunction:
    """Test calculate_home_office_deduction convenience function."""

    def test_convenience_simplified(self):
        """Test convenience function with simplified method."""
        result = calculate_home_office_deduction(
            office_sqft=200,
            total_home_sqft=2000,
            method="simplified"
        )
        assert result["method"] == "simplified"
        assert result["deduction"] == 1000.0
        assert result["business_use_percentage"] == 10.0
        assert result["simplified"]["square_feet"] == 200
        assert result["simplified"]["max_deduction"] == 1500.0

    def test_convenience_simplified_over_max(self):
        """Test convenience function when office exceeds 300 sqft."""
        result = calculate_home_office_deduction(
            office_sqft=500,
            total_home_sqft=2000,
            method="simplified"
        )
        assert result["deduction"] == 1500.0  # Capped
        assert result["simplified"]["eligible_square_feet"] == 300

    def test_convenience_regular(self):
        """Test convenience function with regular method."""
        result = calculate_home_office_deduction(
            office_sqft=200,
            total_home_sqft=2000,
            method="regular",
            tentative_profit=50000,
            mortgage_interest=12000,
            real_estate_taxes=5000,
            insurance=1800,
            utilities=4200
        )
        assert result["method"] == "regular"
        assert result["business_use_percentage"] == 10.0
        assert "regular" in result
        # (12000 + 5000) × 10% = 1700 for mortgage/taxes
        # (1800 + 4200) × 10% = 600 for other indirect
        # Total = 2300
        assert result["regular"]["total_allowable"] == 2300.0


class TestForm8829ToDictionary:
    """Test Form 8829 to_dict serialization."""

    def test_simplified_to_dict(self):
        """Test simplified method dictionary output."""
        form = Form8829(
            method=HomeOfficeMethod.SIMPLIFIED,
            part_1=Form8829Part1(
                line_1_business_area=250,
                line_2_total_area=2000
            )
        )
        result = form.to_dict()

        assert result["method"] == "simplified"
        assert result["deduction"] == 1250.0
        assert result["business_use_percentage"] == 12.5
        assert result["simplified"]["rate_per_sqft"] == 5.0
        assert result["simplified"]["max_deduction"] == 1500.0

    def test_regular_to_dict(self):
        """Test regular method dictionary output."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=50000,
                line_9_direct_expenses=100,
                line_28_utilities=6000,
            )
        )
        result = form.to_dict()

        assert result["method"] == "regular"
        assert result["regular"]["direct_expenses"] == 100
        assert result["regular"]["indirect_expenses_business"] == 600.0
        assert result["regular"]["is_limited"] is False


class TestForm8829EdgeCases:
    """Test Form 8829 edge cases."""

    def test_zero_profit_limits_all(self):
        """Test zero profit limits all deductions."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=0,  # No profit
                line_17_mortgage_interest=12000,
                line_28_utilities=6000,
            )
        )
        # Can't deduct anything (creates loss)
        # Actually, mortgage interest/taxes can still be deducted even with loss
        # But other expenses are limited
        # Line 22: 1200 (mortgage business)
        # Line 23: max(0, 0 - 1200) = 0
        assert form.part_2.line_23_limit_for_other == 0.0

        # All utilities carry over
        assert form.part_2.line_34_allowable_other == 0.0

    def test_negative_profit(self):
        """Test handling of negative (loss) from Schedule C."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=200,
                line_2_total_area=2000
            ),
            part_2=Form8829Part2(
                business_percentage=10.0,
                line_8_tentative_profit=-5000,  # Loss
                line_17_mortgage_interest=12000,
            )
        )
        # With loss, limit for other expenses is 0
        assert form.part_2.line_23_limit_for_other == 0.0

    def test_very_small_percentage(self):
        """Test very small business use percentage."""
        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=Form8829Part1(
                line_1_business_area=50,
                line_2_total_area=5000  # 1%
            ),
            part_2=Form8829Part2(
                business_percentage=1.0,
                line_8_tentative_profit=50000,
                line_17_mortgage_interest=24000,
                line_28_utilities=6000,
            )
        )
        assert form.business_use_percentage == 1.0
        # $24000 × 1% = $240
        assert form.part_2.line_20_business_portion == 240.0
        # $6000 × 1% = $60
        assert form.part_2.line_31_business_other_indirect == 60.0

    def test_method_defaults_to_regular(self):
        """Test default method is regular."""
        form = Form8829()
        assert form.method == HomeOfficeMethod.REGULAR


class TestForm8829Enums:
    """Test Form 8829 enum values."""

    def test_home_office_methods(self):
        """Test home office method enum."""
        assert HomeOfficeMethod.SIMPLIFIED.value == "simplified"
        assert HomeOfficeMethod.REGULAR.value == "regular"

    def test_home_types(self):
        """Test home type enum."""
        assert HomeType.HOUSE.value == "house"
        assert HomeType.CONDO.value == "condo"
        assert HomeType.APARTMENT.value == "apartment"

    def test_business_use_types(self):
        """Test business use type enum."""
        assert BusinessUseType.PRINCIPAL_PLACE.value == "principal_place"
        assert BusinessUseType.MEETING_CLIENTS.value == "meeting_clients"
        assert BusinessUseType.DAYCARE.value == "daycare"


class TestForm8829Part4Carryover:
    """Test Part IV: Expense carryover."""

    def test_part4_defaults(self):
        """Test Part IV default values."""
        part4 = Form8829Part4()
        assert part4.line_43_operating_carryover == 0.0
        assert part4.line_44_depreciation_carryover == 0.0

    def test_part4_with_carryover(self):
        """Test Part IV with carryover amounts."""
        part4 = Form8829Part4(
            line_43_operating_carryover=500,
            line_44_depreciation_carryover=300
        )
        assert part4.line_43_operating_carryover == 500
        assert part4.line_44_depreciation_carryover == 300
