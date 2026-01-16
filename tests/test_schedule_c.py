"""
Tests for Schedule C - Profit or Loss From Business (Sole Proprietorship).

Covers:
- Business income and expense calculations
- Cost of Goods Sold (COGS)
- Vehicle expenses (standard mileage vs actual)
- Home office deduction
- Net profit/loss calculation
- Integration with Income model and SE tax

Reference: IRS Form Schedule C (Form 1040)
"""

import pytest
from models.schedule_c import (
    ScheduleCBusiness,
    ScheduleCExpenses,
    CostOfGoodsSold,
    BusinessVehicle,
    HomeOffice,
    OtherExpense,
    BusinessType,
    AccountingMethod,
    InventoryMethod,
    VehicleExpenseMethod,
    HomeOfficeMethod,
)
from models.income import Income


class TestScheduleCExpenses:
    """Tests for expense calculations."""

    def test_basic_expenses(self):
        """Test basic expense total calculation."""
        expenses = ScheduleCExpenses(
            advertising=1000,
            office_expense=500,
            supplies=300,
            utilities=200,
        )
        total = expenses.calculate_total_expenses()
        assert total == 2000.0

    def test_all_expense_categories(self):
        """Test all expense line items."""
        expenses = ScheduleCExpenses(
            advertising=100,
            car_and_truck_expenses=500,
            commissions_and_fees=200,
            contract_labor=1000,
            depletion=50,
            depreciation_section_179=2000,
            employee_benefit_programs=300,
            insurance_other=400,
            interest_mortgage=600,
            interest_other=100,
            legal_and_professional=500,
            office_expense=200,
            pension_profit_sharing=1000,
            rent_vehicles_equipment=300,
            rent_other_property=1200,
            repairs_and_maintenance=150,
            supplies=100,
            taxes_and_licenses=250,
            travel=800,
            meals_full_amount=400,  # 50% deductible
            utilities=300,
            wages=5000,
            home_office_deduction=1500,
        )

        total = expenses.calculate_total_expenses()
        # Meals: 400 × 50% = 200
        expected = (
            100 + 500 + 200 + 1000 + 50 + 2000 + 300 + 400 +
            600 + 100 + 500 + 200 + 1000 + 300 + 1200 + 150 +
            100 + 250 + 800 + 200 + 300 + 5000 + 1500
        )
        assert total == expected

    def test_meals_deduction_limit(self):
        """Test 50% meals deduction limitation."""
        expenses = ScheduleCExpenses(
            meals_full_amount=1000,
            meals_limitation_percentage=0.50,
        )
        assert expenses.get_deductible_meals() == 500.0

    def test_other_expenses(self):
        """Test other expenses from Part V."""
        expenses = ScheduleCExpenses(
            other_expenses=[
                OtherExpense(description="Bank fees", amount=50),
                OtherExpense(description="Software subscriptions", amount=200),
                OtherExpense(description="Continuing education", amount=300),
            ]
        )
        assert expenses.get_total_other_expenses() == 550.0
        assert expenses.calculate_total_expenses() == 550.0


class TestCostOfGoodsSold:
    """Tests for Cost of Goods Sold calculation."""

    def test_basic_cogs(self):
        """Test basic COGS calculation."""
        cogs = CostOfGoodsSold(
            beginning_inventory=10000,
            purchases=50000,
            cost_of_labor=5000,
            materials_and_supplies=2000,
            ending_inventory=12000,
        )
        # COGS = 10000 + 50000 + 5000 + 2000 - 12000 = 55000
        assert cogs.calculate_cogs() == 55000.0

    def test_cogs_with_personal_withdrawal(self):
        """Test COGS with items withdrawn for personal use."""
        cogs = CostOfGoodsSold(
            beginning_inventory=5000,
            purchases=20000,
            items_withdrawn_personal=500,
            cost_of_labor=1000,
            ending_inventory=4000,
        )
        # Net purchases = 20000 - 500 = 19500
        # COGS = 5000 + 19500 + 1000 - 4000 = 21500
        assert cogs.calculate_cogs() == 21500.0

    def test_cogs_with_other_costs(self):
        """Test COGS with other costs."""
        cogs = CostOfGoodsSold(
            beginning_inventory=1000,
            purchases=5000,
            other_costs=500,
            other_costs_description="Freight and shipping",
            ending_inventory=1500,
        )
        # COGS = 1000 + 5000 + 500 - 1500 = 5000
        assert cogs.calculate_cogs() == 5000.0

    def test_cogs_zero_when_ending_exceeds(self):
        """Test COGS cannot be negative."""
        cogs = CostOfGoodsSold(
            beginning_inventory=1000,
            purchases=500,
            ending_inventory=2000,
        )
        # Would be 1000 + 500 - 2000 = -500, but capped at 0
        assert cogs.calculate_cogs() == 0.0


class TestBusinessVehicle:
    """Tests for business vehicle expense calculations."""

    def test_business_use_percentage(self):
        """Test business use percentage calculation."""
        vehicle = BusinessVehicle(
            vehicle_description="2022 Toyota Camry",
            total_miles=20000,
            business_miles=15000,
            commuting_miles=3000,
            other_miles=2000,
        )
        assert vehicle.get_business_use_percentage() == 75.0

    def test_standard_mileage_deduction(self):
        """Test standard mileage rate deduction."""
        vehicle = BusinessVehicle(
            vehicle_description="2023 Honda Accord",
            total_miles=20000,
            business_miles=12000,
            expense_method=VehicleExpenseMethod.STANDARD_MILEAGE,
            tolls_and_parking=500,
        )
        # 12000 miles × $0.70 = $8,400 + $500 tolls = $8,900
        deduction = vehicle.calculate_standard_mileage_deduction(0.70)
        assert deduction == 8900.0

    def test_actual_expenses_deduction(self):
        """Test actual expenses method deduction."""
        vehicle = BusinessVehicle(
            vehicle_description="2021 Ford F-150",
            total_miles=25000,
            business_miles=20000,  # 80% business use
            expense_method=VehicleExpenseMethod.ACTUAL_EXPENSES,
            gas_and_oil=3000,
            repairs_and_maintenance=500,
            insurance=1200,
            vehicle_registration=200,
            vehicle_depreciation=5000,
            tolls_and_parking=300,
        )
        # Total expenses (excl tolls): 3000 + 500 + 1200 + 200 + 5000 = 9900
        # Business portion: 9900 × 80% = 7920
        # Plus tolls: 7920 + 300 = 8220
        deduction = vehicle.calculate_actual_expenses_deduction()
        assert deduction == 8220.0

    def test_vehicle_zero_miles(self):
        """Test vehicle with zero miles."""
        vehicle = BusinessVehicle(
            vehicle_description="New Vehicle",
            total_miles=0,
            business_miles=0,
        )
        assert vehicle.get_business_use_percentage() == 0.0
        assert vehicle.calculate_standard_mileage_deduction() == 0.0


class TestScheduleCBusiness:
    """Tests for complete Schedule C business calculation."""

    def test_basic_service_business(self):
        """Test basic service business with no inventory."""
        business = ScheduleCBusiness(
            business_name="Consulting Services",
            business_type=BusinessType.CONSULTING,
            gross_receipts=100000,
            expenses=ScheduleCExpenses(
                advertising=2000,
                office_expense=1000,
                supplies=500,
                utilities=1200,
                travel=3000,
                legal_and_professional=2500,
            ),
        )

        assert business.calculate_gross_income() == 100000.0
        assert business.calculate_gross_profit() == 100000.0
        assert business.get_total_expenses() == 10200.0
        assert business.calculate_net_profit_loss() == 89800.0
        assert business.is_loss() is False

    def test_retail_business_with_cogs(self):
        """Test retail business with cost of goods sold."""
        business = ScheduleCBusiness(
            business_name="Online Retail Store",
            business_type=BusinessType.RETAIL,
            gross_receipts=150000,
            returns_and_allowances=5000,
            cost_of_goods_sold=CostOfGoodsSold(
                beginning_inventory=20000,
                purchases=80000,
                ending_inventory=25000,
            ),
            expenses=ScheduleCExpenses(
                advertising=5000,
                office_expense=2000,
                utilities=1500,
            ),
        )

        # Net receipts: 150000 - 5000 = 145000
        # COGS: 20000 + 80000 - 25000 = 75000
        # Gross income: 145000 - 75000 = 70000
        assert business.get_cogs() == 75000.0
        assert business.calculate_gross_income() == 70000.0
        assert business.calculate_gross_profit() == 70000.0
        assert business.get_total_expenses() == 8500.0
        assert business.calculate_net_profit_loss() == 61500.0

    def test_business_with_loss(self):
        """Test business with net loss."""
        business = ScheduleCBusiness(
            business_name="Startup Business",
            business_type=BusinessType.TECHNOLOGY,
            gross_receipts=20000,
            expenses=ScheduleCExpenses(
                rent_other_property=12000,
                utilities=2400,
                advertising=5000,
                office_expense=3000,
                legal_and_professional=2000,
            ),
        )

        # Gross profit: 20000
        # Expenses: 24400
        # Net loss: -4400
        assert business.calculate_net_profit_loss() == -4400.0
        assert business.is_loss() is True

    def test_business_with_vehicle(self):
        """Test business with vehicle expenses."""
        business = ScheduleCBusiness(
            business_name="Delivery Service",
            business_type=BusinessType.TRANSPORTATION,
            gross_receipts=80000,
            vehicles=[
                BusinessVehicle(
                    vehicle_description="Delivery Van",
                    total_miles=30000,
                    business_miles=25000,
                    expense_method=VehicleExpenseMethod.STANDARD_MILEAGE,
                    tolls_and_parking=1000,
                ),
            ],
            expenses=ScheduleCExpenses(
                insurance_other=2000,
                office_expense=500,
            ),
        )

        # Vehicle: 25000 × 0.70 + 1000 = 18500
        # Other expenses: 2500
        # Total expenses: 21000
        assert business.calculate_vehicle_expenses() == 18500.0
        assert business.get_total_expenses() == 21000.0
        assert business.calculate_net_profit_loss() == 59000.0

    def test_business_with_other_income(self):
        """Test business with other income."""
        business = ScheduleCBusiness(
            business_name="Manufacturing",
            business_type=BusinessType.MANUFACTURING,
            gross_receipts=200000,
            other_income=5000,
            other_income_description="Scrap sales and fuel tax credit",
            expenses=ScheduleCExpenses(
                wages=50000,
                rent_other_property=24000,
                utilities=6000,
            ),
        )

        # Gross income: 200000
        # Gross profit: 200000 + 5000 = 205000
        # Expenses: 80000
        # Net profit: 125000
        assert business.calculate_gross_profit() == 205000.0
        assert business.calculate_net_profit_loss() == 125000.0

    def test_statutory_employee_no_se_tax(self):
        """Test statutory employee doesn't generate SE income."""
        business = ScheduleCBusiness(
            business_name="Commission Sales",
            business_type=BusinessType.SERVICES,
            is_statutory_employee=True,
            gross_receipts=50000,
            expenses=ScheduleCExpenses(
                travel=5000,
                supplies=1000,
            ),
        )

        assert business.calculate_net_profit_loss() == 44000.0
        assert business.get_se_income() == 0.0  # No SE tax for statutory employees

    def test_business_summary(self):
        """Test business summary generation."""
        business = ScheduleCBusiness(
            business_name="Web Design",
            business_type=BusinessType.CREATIVE,
            accounting_method=AccountingMethod.CASH,
            gross_receipts=75000,
            expenses=ScheduleCExpenses(
                advertising=1500,
                office_expense=800,
                supplies=300,
            ),
        )

        summary = business.generate_summary()

        assert summary['business_name'] == "Web Design"
        assert summary['business_type'] == "creative"
        assert summary['accounting_method'] == "cash"
        assert summary['gross_receipts'] == 75000.0
        assert summary['total_expenses'] == 2600.0
        assert summary['net_profit_or_loss'] == 72400.0
        assert summary['is_loss'] is False


class TestHomeOffice:
    """Tests for home office deduction."""

    def test_simplified_method(self):
        """Test simplified home office deduction."""
        home_office = HomeOffice(
            method=HomeOfficeMethod.SIMPLIFIED,
            home_total_square_feet=2000,
            office_square_feet=200,
        )
        # 200 sq ft × $5 = $1,000
        assert home_office.calculate_simplified_deduction() == 1000.0
        assert home_office.calculate_deduction() == 1000.0

    def test_simplified_method_max_limit(self):
        """Test simplified method capped at 300 sq ft."""
        home_office = HomeOffice(
            method=HomeOfficeMethod.SIMPLIFIED,
            home_total_square_feet=3000,
            office_square_feet=500,  # Exceeds 300 sq ft max
        )
        # Capped at 300 sq ft × $5 = $1,500
        assert home_office.calculate_simplified_deduction() == 1500.0

    def test_regular_method(self):
        """Test regular method (Form 8829) calculation."""
        home_office = HomeOffice(
            method=HomeOfficeMethod.REGULAR,
            home_total_square_feet=2000,
            office_square_feet=200,  # 10% business use
            mortgage_interest=12000,
            real_estate_taxes=4000,
            homeowners_insurance=1200,
            utilities=2400,
            repairs_maintenance=1000,
            home_depreciation=3000,
        )

        # Business use: 10%
        # Total indirect: 12000 + 4000 + 1200 + 2400 + 1000 + 3000 = 23600
        # Deduction: 23600 × 10% = 2360
        assert home_office.get_business_use_percentage() == 10.0
        deduction = home_office.calculate_regular_deduction()
        assert deduction == 2360.0

    def test_regular_method_with_direct_expenses(self):
        """Test regular method with direct expenses."""
        home_office = HomeOffice(
            method=HomeOfficeMethod.REGULAR,
            home_total_square_feet=2000,
            office_square_feet=400,  # 20% business use
            direct_expenses=500,  # 100% deductible
            utilities=3000,  # Pro-rated
        )

        # Direct: 500 (full)
        # Indirect: 3000 × 20% = 600
        # Total: 1100
        assert home_office.calculate_regular_deduction() == 1100.0

    def test_regular_method_income_limit(self):
        """Test regular method limited by gross income."""
        home_office = HomeOffice(
            method=HomeOfficeMethod.REGULAR,
            home_total_square_feet=1000,
            office_square_feet=500,  # 50% business use
            mortgage_interest=24000,
            utilities=6000,
        )

        # Total potential: (24000 + 6000) × 50% = 15000
        # But limited by gross income
        deduction = home_office.calculate_regular_deduction(gross_income_limit=5000)
        assert deduction == 5000.0


class TestScheduleCIntegration:
    """Tests for Schedule C integration with Income model."""

    def test_income_with_schedule_c(self):
        """Test Income model with Schedule C businesses."""
        from models.schedule_c import ScheduleCBusiness, ScheduleCExpenses

        income = Income(
            schedule_c_businesses=[
                ScheduleCBusiness(
                    business_name="Consulting",
                    gross_receipts=100000,
                    expenses=ScheduleCExpenses(
                        office_expense=5000,
                        travel=3000,
                    ),
                ),
                ScheduleCBusiness(
                    business_name="Freelance Writing",
                    gross_receipts=30000,
                    expenses=ScheduleCExpenses(
                        supplies=500,
                        home_office_deduction=1500,
                    ),
                ),
            ],
        )

        # Business 1: 100000 - 8000 = 92000
        # Business 2: 30000 - 2000 = 28000
        # Total: 120000
        assert income.get_schedule_c_net_profit() == 120000.0
        assert income.get_schedule_c_se_income() == 120000.0

    def test_income_with_simple_se_fallback(self):
        """Test Income model falls back to simple SE fields."""
        income = Income(
            self_employment_income=50000,
            self_employment_expenses=10000,
        )

        assert income.get_schedule_c_net_profit() == 40000.0
        assert income.get_schedule_c_se_income() == 40000.0

    def test_schedule_c_takes_precedence(self):
        """Test Schedule C businesses take precedence over simple fields."""
        from models.schedule_c import ScheduleCBusiness, ScheduleCExpenses

        income = Income(
            # Simple fields (should be ignored)
            self_employment_income=50000,
            self_employment_expenses=10000,
            # Schedule C (should be used)
            schedule_c_businesses=[
                ScheduleCBusiness(
                    business_name="Primary Business",
                    gross_receipts=80000,
                    expenses=ScheduleCExpenses(
                        office_expense=5000,
                    ),
                ),
            ],
        )

        # Should use Schedule C (75000), not simple (40000)
        assert income.get_schedule_c_net_profit() == 75000.0

    def test_schedule_c_summary(self):
        """Test Schedule C summary generation."""
        from models.schedule_c import ScheduleCBusiness, ScheduleCExpenses

        income = Income(
            schedule_c_businesses=[
                ScheduleCBusiness(
                    business_name="Business A",
                    gross_receipts=50000,
                    expenses=ScheduleCExpenses(office_expense=5000),
                ),
                ScheduleCBusiness(
                    business_name="Business B",
                    gross_receipts=30000,
                    expenses=ScheduleCExpenses(supplies=2000),
                ),
            ],
        )

        summaries = income.get_schedule_c_summary()
        assert len(summaries) == 2
        assert summaries[0]['business_name'] == "Business A"
        assert summaries[1]['business_name'] == "Business B"

    def test_qbi_from_schedule_c(self):
        """Test QBI calculation from Schedule C."""
        from models.schedule_c import ScheduleCBusiness, ScheduleCExpenses

        income = Income(
            schedule_c_businesses=[
                ScheduleCBusiness(
                    business_name="QBI Business",
                    gross_receipts=100000,
                    expenses=ScheduleCExpenses(
                        wages=20000,
                        rent_other_property=10000,
                    ),
                ),
            ],
        )

        # Net profit: 100000 - 30000 = 70000
        assert income.get_schedule_c_qbi() == 70000.0
        assert income.get_total_qbi() == 70000.0


class TestScheduleCEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_gross_receipts(self):
        """Test business with zero gross receipts."""
        business = ScheduleCBusiness(
            business_name="Startup",
            gross_receipts=0,
            expenses=ScheduleCExpenses(
                office_expense=1000,
                advertising=500,
            ),
        )

        assert business.calculate_net_profit_loss() == -1500.0
        assert business.is_loss() is True

    def test_high_returns_and_allowances(self):
        """Test high returns relative to gross receipts."""
        business = ScheduleCBusiness(
            business_name="Retail",
            gross_receipts=10000,
            returns_and_allowances=3000,
        )

        assert business.calculate_gross_income() == 7000.0

    def test_multiple_vehicles(self):
        """Test business with multiple vehicles."""
        business = ScheduleCBusiness(
            business_name="Delivery Service",
            gross_receipts=200000,
            vehicles=[
                BusinessVehicle(
                    vehicle_description="Van 1",
                    total_miles=40000,
                    business_miles=35000,
                    expense_method=VehicleExpenseMethod.STANDARD_MILEAGE,
                ),
                BusinessVehicle(
                    vehicle_description="Van 2",
                    total_miles=30000,
                    business_miles=28000,
                    expense_method=VehicleExpenseMethod.STANDARD_MILEAGE,
                ),
            ],
        )

        # Van 1: 35000 × 0.70 = 24500
        # Van 2: 28000 × 0.70 = 19600
        # Total: 44100
        assert business.calculate_vehicle_expenses() == 44100.0

    def test_business_not_materially_participated(self):
        """Test business with no material participation (passive)."""
        business = ScheduleCBusiness(
            business_name="Passive Investment",
            materially_participated=False,
            gross_receipts=50000,
            expenses=ScheduleCExpenses(
                office_expense=2000,
            ),
        )

        # Still calculates profit, but PAL rules would apply separately
        assert business.calculate_net_profit_loss() == 48000.0
        assert business.materially_participated is False

    def test_accrual_accounting(self):
        """Test business using accrual accounting."""
        business = ScheduleCBusiness(
            business_name="Manufacturing",
            accounting_method=AccountingMethod.ACCRUAL,
            gross_receipts=500000,
            cost_of_goods_sold=CostOfGoodsSold(
                inventory_method=InventoryMethod.LOWER_OF_COST_OR_MARKET,
                beginning_inventory=50000,
                purchases=200000,
                ending_inventory=60000,
            ),
        )

        assert business.accounting_method == AccountingMethod.ACCRUAL
        assert business.cost_of_goods_sold.inventory_method == InventoryMethod.LOWER_OF_COST_OR_MARKET
        assert business.get_cogs() == 190000.0
