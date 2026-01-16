"""
Test suite for Schedule F (Form 1040) - Profit or Loss From Farming.

Tests cover:
- Farm income sources (crops, livestock, ag payments)
- Farm expenses
- Net farm profit/loss calculation
- Self-employment income from farming
- Material participation
"""

import pytest
from src.models.schedule_f import (
    ScheduleF,
    FarmType,
    AccountingMethod,
    FarmIncome,
    FarmExpenses,
    calculate_farm_profit_loss,
)


class TestFarmIncome:
    """Tests for farm income calculation."""

    def test_crop_sales(self):
        """Crop sales income."""
        schedule = ScheduleF(
            farm_income=FarmIncome(
                produce_sales=50000.0,
                grain_sales=30000.0,
            )
        )
        result = schedule.calculate_gross_income()

        assert result['line_2_raised_sales'] == 80000.0

    def test_livestock_raised_sales(self):
        """Livestock raised for sale."""
        schedule = ScheduleF(
            farm_income=FarmIncome(
                livestock_raised_sales=40000.0,
            )
        )
        result = schedule.calculate_gross_income()

        assert result['line_2_raised_sales'] == 40000.0

    def test_livestock_resale(self):
        """Livestock bought for resale (profit = proceeds - cost)."""
        schedule = ScheduleF(
            farm_income=FarmIncome(
                livestock_resale_gross=25000.0,
                livestock_resale_cost=18000.0,
            )
        )
        result = schedule.calculate_gross_income()

        assert result['line_1c_livestock_resale_profit'] == 7000.0

    def test_ag_program_payments(self):
        """Agricultural program payments."""
        schedule = ScheduleF(
            farm_income=FarmIncome(
                ag_program_payments=12000.0,
                ccc_loans_reported=5000.0,
            )
        )
        result = schedule.calculate_gross_income()

        assert result['line_4_ag_program_payments'] == 17000.0

    def test_crop_insurance(self):
        """Crop insurance proceeds."""
        schedule = ScheduleF(
            farm_income=FarmIncome(
                crop_insurance_proceeds=15000.0,
            )
        )
        result = schedule.calculate_gross_income()

        assert result['line_5_crop_insurance'] == 15000.0

    def test_cooperative_distributions(self):
        """Cooperative distributions."""
        schedule = ScheduleF(
            farm_income=FarmIncome(
                coop_distributions_taxable=3000.0,
            )
        )
        result = schedule.calculate_gross_income()

        assert result['line_3_coop_distributions'] == 3000.0

    def test_custom_hire_income(self):
        """Custom hire (machine work) income."""
        schedule = ScheduleF(
            farm_income=FarmIncome(
                custom_hire_income=8000.0,
            )
        )
        result = schedule.calculate_gross_income()

        assert result['line_6_custom_hire'] == 8000.0


class TestFarmExpenses:
    """Tests for farm expense calculation."""

    def test_basic_expenses(self):
        """Basic farm expenses."""
        expenses = FarmExpenses(
            feed=10000.0,
            seeds_plants=5000.0,
            fertilizers_lime=3000.0,
            labor_hired=8000.0,
        )

        assert expenses.total() == 26000.0

    def test_depreciation(self):
        """Depreciation and Section 179."""
        schedule = ScheduleF(
            farm_expenses=FarmExpenses(
                depreciation_179=15000.0,
            )
        )
        result = schedule.calculate_expenses()

        assert result['line_14_depreciation'] == 15000.0

    def test_interest_expenses(self):
        """Farm interest expenses."""
        schedule = ScheduleF(
            farm_expenses=FarmExpenses(
                interest_mortgage=6000.0,
                interest_other=2000.0,
            )
        )
        result = schedule.calculate_expenses()

        assert result['line_21a_interest_mortgage'] == 6000.0
        assert result['line_21b_interest_other'] == 2000.0

    def test_rent_expenses(self):
        """Farm rent expenses."""
        schedule = ScheduleF(
            farm_expenses=FarmExpenses(
                rent_vehicles=4000.0,
                rent_land_animals=12000.0,
            )
        )
        result = schedule.calculate_expenses()

        assert result['line_24a_rent_vehicles'] == 4000.0
        assert result['line_24b_rent_land'] == 12000.0

    def test_all_expenses(self):
        """All farm expense categories."""
        schedule = ScheduleF(
            farm_expenses=FarmExpenses(
                car_truck=2000.0,
                chemicals=1500.0,
                conservation=500.0,
                custom_hire=3000.0,
                depreciation_179=10000.0,
                feed=15000.0,
                fertilizers_lime=4000.0,
                gasoline_fuel_oil=5000.0,
                insurance_other=2500.0,
                labor_hired=12000.0,
                repairs_maintenance=3500.0,
                seeds_plants=6000.0,
                supplies=1000.0,
                taxes=2000.0,
                utilities=1500.0,
                veterinary_breeding=2500.0,
            )
        )
        result = schedule.calculate_expenses()

        assert result['line_33_total_expenses'] == 72000.0


class TestNetProfitLoss:
    """Tests for net farm profit/loss calculation."""

    def test_farm_profit(self):
        """Farm with net profit."""
        schedule = ScheduleF(
            farm_income=FarmIncome(
                produce_sales=80000.0,
                livestock_raised_sales=30000.0,
            ),
            farm_expenses=FarmExpenses(
                feed=20000.0,
                seeds_plants=10000.0,
                labor_hired=15000.0,
                depreciation_179=12000.0,
            ),
        )
        result = schedule.calculate_net_profit_loss()

        # Income: $110k, Expenses: $57k, Net: $53k
        assert result['gross_income'] == 110000.0
        assert result['total_expenses'] == 57000.0
        assert result['line_34_net_profit_loss'] == 53000.0
        assert result['is_profit'] is True

    def test_farm_loss(self):
        """Farm with net loss."""
        schedule = ScheduleF(
            farm_income=FarmIncome(
                produce_sales=40000.0,
            ),
            farm_expenses=FarmExpenses(
                feed=25000.0,
                seeds_plants=15000.0,
                labor_hired=20000.0,
            ),
        )
        result = schedule.calculate_net_profit_loss()

        assert result['line_34_net_profit_loss'] == -20000.0
        assert result['is_loss'] is True

    def test_self_employment_income(self):
        """SE income when materially participated."""
        schedule = ScheduleF(
            farm_income=FarmIncome(produce_sales=60000.0),
            farm_expenses=FarmExpenses(seeds_plants=10000.0),
            materially_participated=True,
        )
        result = schedule.calculate_net_profit_loss()

        assert result['self_employment_income'] == 50000.0

    def test_no_se_without_material_participation(self):
        """No SE income without material participation."""
        schedule = ScheduleF(
            farm_income=FarmIncome(produce_sales=60000.0),
            farm_expenses=FarmExpenses(seeds_plants=10000.0),
            materially_participated=False,
        )
        result = schedule.calculate_net_profit_loss()

        assert result['self_employment_income'] == 0.0


class TestCompleteScheduleF:
    """Tests for complete Schedule F calculation."""

    def test_complete_calculation(self):
        """Complete Schedule F calculation."""
        schedule = ScheduleF(
            farm_name="Smith Family Farm",
            farm_type=FarmType.CROP,
            farm_income=FarmIncome(
                produce_sales=100000.0,
                ag_program_payments=5000.0,
            ),
            farm_expenses=FarmExpenses(
                seeds_plants=15000.0,
                fertilizers_lime=8000.0,
                labor_hired=20000.0,
                depreciation_179=10000.0,
            ),
        )

        result = schedule.calculate_schedule_f()

        assert result['farm_name'] == "Smith Family Farm"
        assert result['farm_type'] == "crop"
        assert result['gross_farm_income'] == 105000.0
        assert result['total_farm_expenses'] == 53000.0
        assert result['net_farm_profit_loss'] == 52000.0
        assert result['schedule_se_income'] == 52000.0
        assert result['qualifies_for_farmer_safe_harbor'] is True

    def test_accrual_method(self):
        """Accrual method with inventory change."""
        schedule = ScheduleF(
            accounting_method=AccountingMethod.ACCRUAL,
            farm_income=FarmIncome(produce_sales=50000.0),
            farm_expenses=FarmExpenses(seeds_plants=10000.0),
            inventory_beginning=20000.0,
            inventory_ending=25000.0,
            cost_of_items_purchased=3000.0,
        )

        result = schedule.calculate_gross_income()

        # Gross income includes inventory change: $50k + ($25k - $20k - $3k) = $52k
        assert result['line_9_gross_income'] == 52000.0

    def test_summary_method(self):
        """Get Schedule F summary."""
        schedule = ScheduleF(
            farm_income=FarmIncome(produce_sales=80000.0),
            farm_expenses=FarmExpenses(seeds_plants=20000.0),
        )

        summary = schedule.get_schedule_f_summary()

        assert summary['gross_income'] == 80000.0
        assert summary['total_expenses'] == 20000.0
        assert summary['net_profit_loss'] == 60000.0
        assert summary['se_income'] == 60000.0


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_profit(self):
        """Calculate farm profit with convenience function."""
        result = calculate_farm_profit_loss(
            crop_sales=100000.0,
            livestock_sales=30000.0,
            feed_expense=20000.0,
            seed_expense=15000.0,
            fertilizer_expense=8000.0,
            labor_expense=25000.0,
            depreciation=10000.0,
        )

        # Income: $130k, Expenses: $78k, Net: $52k
        assert result['gross_farm_income'] == 130000.0
        assert result['total_farm_expenses'] == 78000.0
        assert result['net_farm_profit_loss'] == 52000.0

    def test_convenience_function_loss(self):
        """Calculate farm loss with convenience function."""
        result = calculate_farm_profit_loss(
            crop_sales=40000.0,
            feed_expense=30000.0,
            labor_expense=25000.0,
        )

        assert result['net_farm_profit_loss'] == -15000.0

    def test_convenience_function_with_ag_payments(self):
        """Farm with agricultural program payments."""
        result = calculate_farm_profit_loss(
            crop_sales=50000.0,
            ag_program_payments=10000.0,
            seed_expense=15000.0,
        )

        assert result['gross_farm_income'] == 60000.0
        assert result['net_farm_profit_loss'] == 45000.0

    def test_convenience_function_no_material_participation(self):
        """Farm without material participation."""
        result = calculate_farm_profit_loss(
            crop_sales=50000.0,
            seed_expense=10000.0,
            materially_participated=False,
        )

        assert result['net_farm_profit_loss'] == 40000.0
        assert result['schedule_se_income'] == 0.0
