"""
Tests for Residential Energy Credits (Form 5695)

Tests cover:
- Part I: Residential Clean Energy Credit (Section 25D)
  - Solar, wind, geothermal, battery storage at 30%
  - Fuel cell with $500/0.5 kW capacity limit
- Part II: Energy Efficient Home Improvement Credit (Section 25C)
  - $1,200 aggregate annual limit
  - $600 window limit, $500 door limit, $600 panel limit, $150 audit limit
  - $2,000 separate heat pump/biomass limit
- Engine integration
"""

import pytest
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, W2Info
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


class TestCleanEnergyCredit:
    """Tests for Part I - Residential Clean Energy Credit (Section 25D)."""

    def test_solar_electric_30_percent(self):
        """Solar electric gets 30% credit with no limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(solar_electric_expenses=10000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $10,000 * 30% = $3,000
        assert clean_credit == 3000.0
        assert home_credit == 0.0

    def test_solar_water_heating(self):
        """Solar water heating gets 30% credit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(solar_water_heating_expenses=5000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $5,000 * 30% = $1,500
        assert clean_credit == 1500.0

    def test_small_wind_turbine(self):
        """Small wind turbine gets 30% credit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(small_wind_expenses=20000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $20,000 * 30% = $6,000
        assert clean_credit == 6000.0

    def test_geothermal_heat_pump(self):
        """Geothermal heat pump gets 30% credit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(geothermal_heat_pump_expenses=15000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $15,000 * 30% = $4,500
        assert clean_credit == 4500.0

    def test_battery_storage(self):
        """Battery storage gets 30% credit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(battery_storage_expenses=8000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $8,000 * 30% = $2,400
        assert clean_credit == 2400.0

    def test_combined_clean_energy(self):
        """Multiple clean energy items sum together."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            solar_electric_expenses=15000.0,
            battery_storage_expenses=8000.0,
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # ($15,000 + $8,000) * 30% = $6,900
        assert clean_credit == 6900.0

    def test_no_annual_limit_clean_energy(self):
        """Clean energy has no annual dollar limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(solar_electric_expenses=100000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $100,000 * 30% = $30,000 (no cap)
        assert clean_credit == 30000.0


class TestFuelCellCredit:
    """Tests for fuel cell with capacity-based limit."""

    def test_fuel_cell_under_limit(self):
        """Fuel cell under capacity limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            fuel_cell_expenses=3000.0,
            fuel_cell_kilowatt_capacity=2.0,  # 2 kW = 4 × $500 = $2,000 limit
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $3,000 * 30% = $900 (under $2,000 limit)
        assert clean_credit == 900.0

    def test_fuel_cell_at_capacity_limit(self):
        """Fuel cell capped at capacity limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            fuel_cell_expenses=10000.0,
            fuel_cell_kilowatt_capacity=2.0,  # 2 kW = 4 × $500 = $2,000 limit
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $10,000 * 30% = $3,000, but capped at $2,000
        assert clean_credit == 2000.0

    def test_fuel_cell_high_capacity(self):
        """Fuel cell with higher capacity has higher limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            fuel_cell_expenses=10000.0,
            fuel_cell_kilowatt_capacity=5.0,  # 5 kW = 10 × $500 = $5,000 limit
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $10,000 * 30% = $3,000 (under $5,000 limit)
        assert clean_credit == 3000.0

    def test_fuel_cell_no_capacity_no_credit(self):
        """Fuel cell expenses without capacity info gets no credit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            fuel_cell_expenses=10000.0,
            fuel_cell_kilowatt_capacity=0.0,
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # No capacity = no credit
        assert clean_credit == 0.0


class TestHomeImprovementCredit:
    """Tests for Part II - Energy Efficient Home Improvement Credit (Section 25C)."""

    def test_windows_at_limit(self):
        """Windows capped at $600."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(window_expenses=3000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $3,000 * 30% = $900, but capped at $600
        assert home_credit == 600.0

    def test_windows_under_limit(self):
        """Windows under limit get full credit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(window_expenses=1000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $1,000 * 30% = $300
        assert home_credit == 300.0

    def test_doors_with_count(self):
        """Doors get $250 per door, max $500."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            door_expenses=1500.0,
            door_count=3,  # 3 doors × $250 = $750, but max $500
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $1,500 * 30% = $450, limit is min(3×$250, $500) = $500
        # Credit is $450 (under $500 limit)
        assert home_credit == 450.0

    def test_doors_under_per_door_limit(self):
        """Door credit under per-door limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            door_expenses=600.0,
            door_count=2,  # 2 doors × $250 = $500 limit
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $600 * 30% = $180 (under $500 limit)
        assert home_credit == 180.0

    def test_electric_panel_at_limit(self):
        """Electric panel capped at $600."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(electric_panel_expenses=3000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $3,000 * 30% = $900, but capped at $600
        assert home_credit == 600.0

    def test_home_energy_audit_at_limit(self):
        """Home energy audit capped at $150."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(home_energy_audit_expenses=1000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $1,000 * 30% = $300, but capped at $150
        assert home_credit == 150.0

    def test_insulation_30_percent(self):
        """Insulation gets 30% toward aggregate limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(insulation_expenses=2000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $2,000 * 30% = $600
        assert home_credit == 600.0

    def test_central_ac_30_percent(self):
        """Central A/C gets 30% toward aggregate limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(central_ac_expenses=3000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $3,000 * 30% = $900
        assert home_credit == 900.0


class TestAggregateLimit:
    """Tests for the $1,200 aggregate annual limit."""

    def test_aggregate_limit_reached(self):
        """Multiple improvements capped at $1,200 total."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            insulation_expenses=5000.0,  # $1,500
            window_expenses=3000.0,  # $600 (capped)
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # Total would be $1,500 + $600 = $2,100, but capped at $1,200
        assert home_credit == 1200.0

    def test_under_aggregate_limit(self):
        """Multiple improvements under $1,200."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            insulation_expenses=1000.0,  # $300
            window_expenses=1000.0,  # $300
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # Total: $300 + $300 = $600
        assert home_credit == 600.0


class TestHeatPumpCredit:
    """Tests for heat pump with separate $2,000 limit."""

    def test_heat_pump_30_percent(self):
        """Heat pump gets 30% up to $2,000."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(heat_pump_expenses=5000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $5,000 * 30% = $1,500
        assert home_credit == 1500.0

    def test_heat_pump_at_limit(self):
        """Heat pump capped at $2,000."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(heat_pump_expenses=8000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $8,000 * 30% = $2,400, but capped at $2,000
        assert home_credit == 2000.0

    def test_heat_pump_water_heater(self):
        """Heat pump water heater counts toward $2,000 limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(heat_pump_water_heater_expenses=4000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $4,000 * 30% = $1,200
        assert home_credit == 1200.0

    def test_biomass_stove(self):
        """Biomass stove counts toward $2,000 limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(biomass_stove_expenses=3000.0)

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # $3,000 * 30% = $900
        assert home_credit == 900.0

    def test_combined_heat_pump_at_limit(self):
        """Combined heat pump items capped at $2,000."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            heat_pump_expenses=5000.0,  # $1,500
            heat_pump_water_heater_expenses=4000.0,  # $1,200
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # Total would be $2,700, but capped at $2,000
        assert home_credit == 2000.0


class TestCombinedCredits:
    """Tests for combining Part I and Part II credits."""

    def test_clean_and_home_improvement(self):
        """Solar and windows are separate credits."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            solar_electric_expenses=10000.0,
            window_expenses=2000.0,
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # Solar: $10,000 * 30% = $3,000
        # Windows: $2,000 * 30% = $600
        assert clean_credit == 3000.0
        assert home_credit == 600.0

    def test_heat_pump_plus_standard_improvements(self):
        """Heat pump is separate from $1,200 limit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            heat_pump_expenses=7000.0,  # $2,000 (capped)
            insulation_expenses=2000.0,  # $600
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # Heat pump $2,000 + insulation $600 = $2,600
        assert home_credit == 2600.0

    def test_full_credits_scenario(self):
        """Complex scenario with all credit types."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            solar_electric_expenses=20000.0,  # $6,000
            battery_storage_expenses=10000.0,  # $3,000
            window_expenses=3000.0,  # $600 (capped)
            insulation_expenses=3000.0,  # $900
            heat_pump_expenses=8000.0,  # $2,000 (capped)
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        # Clean energy: $6,000 + $3,000 = $9,000
        # Home improvement: min($600 + $900, $1,200) + $2,000 = $1,200 + $2,000 = $3,200
        assert clean_credit == 9000.0
        assert home_credit == 3200.0


class TestEdgeCases:
    """Edge case tests."""

    def test_no_expenses_no_credit(self):
        """No expenses = no credit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits()

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        assert clean_credit == 0.0
        assert home_credit == 0.0

    def test_zero_expenses(self):
        """Zero expenses = zero credit."""
        config = TaxYearConfig.for_2025()
        credits = TaxCredits(
            solar_electric_expenses=0.0,
            window_expenses=0.0,
        )

        clean_credit, home_credit = credits.calculate_residential_energy_credit(config)

        assert clean_credit == 0.0
        assert home_credit == 0.0


class TestEngineIntegration:
    """Tests for engine integration."""

    def test_basic_engine_calculation(self):
        """Engine correctly calculates energy credits."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                solar_electric_expenses=10000.0,
            ),
        )

        breakdown = engine.calculate(tr)

        # $10,000 * 30% = $3,000
        assert breakdown.credit_breakdown['residential_clean_energy_credit'] == 3000.0
        assert breakdown.credit_breakdown['energy_efficient_home_credit'] == 0.0

    def test_engine_home_improvement(self):
        """Engine calculates home improvement credit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                heat_pump_expenses=5000.0,
            ),
        )

        breakdown = engine.calculate(tr)

        # $5,000 * 30% = $1,500
        assert breakdown.credit_breakdown['residential_clean_energy_credit'] == 0.0
        assert breakdown.credit_breakdown['energy_efficient_home_credit'] == 1500.0

    def test_credits_in_nonrefundable_total(self):
        """Energy credits included in nonrefundable total."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                solar_electric_expenses=10000.0,
                heat_pump_expenses=5000.0,
            ),
        )

        breakdown = engine.calculate(tr)

        clean_energy = breakdown.credit_breakdown['residential_clean_energy_credit']
        home_improvement = breakdown.credit_breakdown['energy_efficient_home_credit']
        total_nonref = breakdown.credit_breakdown['total_nonrefundable']

        # Both credits should be in nonrefundable total
        assert clean_energy == 3000.0
        assert home_improvement == 1500.0
        assert clean_energy + home_improvement <= total_nonref

    def test_no_energy_expenses_zero_credit(self):
        """No energy expenses = zero credit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        assert breakdown.credit_breakdown['residential_clean_energy_credit'] == 0.0
        assert breakdown.credit_breakdown['energy_efficient_home_credit'] == 0.0
