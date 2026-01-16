"""
Schedule C - Profit or Loss From Business (Sole Proprietorship)

Implements IRS Form Schedule C (Form 1040) for reporting income and expenses
from a business operated as a sole proprietor.

Reference: IRS Instructions for Schedule C (Form 1040)
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from decimal import Decimal


class BusinessType(str, Enum):
    """Principal business or profession types."""
    RETAIL = "retail"
    WHOLESALE = "wholesale"
    MANUFACTURING = "manufacturing"
    SERVICES = "services"
    PROFESSIONAL = "professional"
    CONSTRUCTION = "construction"
    REAL_ESTATE = "real_estate"
    FOOD_SERVICE = "food_service"
    TRANSPORTATION = "transportation"
    HEALTHCARE = "healthcare"
    TECHNOLOGY = "technology"
    CONSULTING = "consulting"
    CREATIVE = "creative"
    AGRICULTURE = "agriculture"
    OTHER = "other"


class AccountingMethod(str, Enum):
    """Accounting method used for the business."""
    CASH = "cash"
    ACCRUAL = "accrual"
    OTHER = "other"


class InventoryMethod(str, Enum):
    """Inventory valuation method."""
    COST = "cost"
    LOWER_OF_COST_OR_MARKET = "lower_cost_market"
    OTHER = "other"


class VehicleExpenseMethod(str, Enum):
    """Method for calculating vehicle expenses."""
    STANDARD_MILEAGE = "standard_mileage"
    ACTUAL_EXPENSES = "actual_expenses"


class BusinessVehicle(BaseModel):
    """
    Vehicle information for Schedule C Part IV.

    Tracks business use of vehicles including mileage and expenses.
    """
    vehicle_description: str = Field(description="Year, make, model of vehicle")
    date_placed_in_service: Optional[str] = Field(None, description="Date vehicle placed in service")

    # Mileage tracking
    total_miles: float = Field(default=0.0, ge=0, description="Total miles driven during year")
    business_miles: float = Field(default=0.0, ge=0, description="Business miles driven")
    commuting_miles: float = Field(default=0.0, ge=0, description="Commuting miles (not deductible)")
    other_miles: float = Field(default=0.0, ge=0, description="Other personal miles")

    # Expense method
    expense_method: VehicleExpenseMethod = Field(
        default=VehicleExpenseMethod.STANDARD_MILEAGE,
        description="Method for calculating vehicle expenses"
    )

    # Actual expenses (if using actual method)
    gas_and_oil: float = Field(default=0.0, ge=0)
    repairs_and_maintenance: float = Field(default=0.0, ge=0)
    insurance: float = Field(default=0.0, ge=0)
    vehicle_registration: float = Field(default=0.0, ge=0)
    lease_payments: float = Field(default=0.0, ge=0)
    garage_rent: float = Field(default=0.0, ge=0)
    tolls_and_parking: float = Field(default=0.0, ge=0)  # Always deductible, both methods
    vehicle_depreciation: float = Field(default=0.0, ge=0)
    other_vehicle_expenses: float = Field(default=0.0, ge=0)

    # Evidence documentation
    has_written_evidence: bool = Field(default=True, description="Written evidence supporting business use")
    evidence_is_log: bool = Field(default=False, description="Evidence includes a written log")

    # Vehicle availability questions
    available_for_personal_use: bool = Field(default=True)
    another_vehicle_for_personal: bool = Field(default=False)

    def get_business_use_percentage(self) -> float:
        """Calculate business use percentage."""
        if self.total_miles <= 0:
            return 0.0
        return (self.business_miles / self.total_miles) * 100

    def calculate_standard_mileage_deduction(self, rate_per_mile: float = 0.70) -> float:
        """
        Calculate deduction using standard mileage rate.

        2025 rate: $0.70 per mile (estimated, subject to IRS announcement)
        Note: Tolls and parking are always deductible in addition to mileage.
        """
        return (self.business_miles * rate_per_mile) + self.tolls_and_parking

    def calculate_actual_expenses_deduction(self) -> float:
        """
        Calculate deduction using actual expenses method.

        Total actual expenses × business use percentage.
        """
        total_expenses = (
            self.gas_and_oil +
            self.repairs_and_maintenance +
            self.insurance +
            self.vehicle_registration +
            self.lease_payments +
            self.garage_rent +
            self.vehicle_depreciation +
            self.other_vehicle_expenses
        )

        business_pct = self.get_business_use_percentage() / 100
        return (total_expenses * business_pct) + self.tolls_and_parking

    def calculate_deduction(self, standard_mileage_rate: float = 0.70) -> float:
        """Calculate vehicle expense deduction based on chosen method."""
        if self.expense_method == VehicleExpenseMethod.STANDARD_MILEAGE:
            return self.calculate_standard_mileage_deduction(standard_mileage_rate)
        else:
            return self.calculate_actual_expenses_deduction()


class CostOfGoodsSold(BaseModel):
    """
    Schedule C Part III - Cost of Goods Sold.

    For businesses that sell products or have inventory.
    """
    # Inventory method
    inventory_method: InventoryMethod = Field(
        default=InventoryMethod.COST,
        description="Method used to value closing inventory"
    )
    inventory_method_changed: bool = Field(
        default=False,
        description="Was there any change in determining quantities, costs, or valuations?"
    )

    # Line 35 - Inventory at beginning of year
    beginning_inventory: float = Field(default=0.0, ge=0)

    # Line 36 - Purchases less cost of items withdrawn for personal use
    purchases: float = Field(default=0.0, ge=0)
    items_withdrawn_personal: float = Field(default=0.0, ge=0)

    # Line 37 - Cost of labor (don't include amounts paid to yourself)
    cost_of_labor: float = Field(default=0.0, ge=0)

    # Line 38 - Materials and supplies
    materials_and_supplies: float = Field(default=0.0, ge=0)

    # Line 39 - Other costs
    other_costs: float = Field(default=0.0, ge=0)
    other_costs_description: Optional[str] = None

    # Line 41 - Inventory at end of year
    ending_inventory: float = Field(default=0.0, ge=0)

    def calculate_cogs(self) -> float:
        """
        Calculate Cost of Goods Sold (Line 42).

        Formula: Beginning inventory + Purchases - Personal use + Labor +
                 Materials + Other costs - Ending inventory
        """
        net_purchases = self.purchases - self.items_withdrawn_personal

        total_available = (
            self.beginning_inventory +
            net_purchases +
            self.cost_of_labor +
            self.materials_and_supplies +
            self.other_costs
        )

        return max(0.0, total_available - self.ending_inventory)


class OtherExpense(BaseModel):
    """Individual other expense item for Part V."""
    description: str = Field(description="Description of expense")
    amount: float = Field(ge=0, description="Amount")


class ScheduleCExpenses(BaseModel):
    """
    Schedule C Part II - Expenses.

    All deductible business expenses organized by IRS line items.
    """
    # Line 8 - Advertising
    advertising: float = Field(default=0.0, ge=0, description="Line 8: Advertising expenses")

    # Line 9 - Car and truck expenses (from Part IV or actual expenses)
    # Note: This will be calculated from vehicles, but can be overridden
    car_and_truck_expenses: float = Field(
        default=0.0, ge=0,
        description="Line 9: Car and truck expenses (calculated from vehicles)"
    )

    # Line 10 - Commissions and fees
    commissions_and_fees: float = Field(
        default=0.0, ge=0,
        description="Line 10: Commissions and fees paid to non-employees"
    )

    # Line 11 - Contract labor
    contract_labor: float = Field(
        default=0.0, ge=0,
        description="Line 11: Contract labor (1099-NEC recipients)"
    )

    # Line 12 - Depletion
    depletion: float = Field(
        default=0.0, ge=0,
        description="Line 12: Depletion (for natural resources)"
    )

    # Line 13 - Depreciation and Section 179 expense deduction
    depreciation_section_179: float = Field(
        default=0.0, ge=0,
        description="Line 13: Depreciation and Section 179 (from Form 4562)"
    )

    # Line 14 - Employee benefit programs (other than on Line 19)
    employee_benefit_programs: float = Field(
        default=0.0, ge=0,
        description="Line 14: Employee benefit programs (not pension/profit-sharing)"
    )

    # Line 15 - Insurance (other than health)
    insurance_other: float = Field(
        default=0.0, ge=0,
        description="Line 15: Insurance other than health (liability, malpractice, etc.)"
    )

    # Line 16a - Interest on business debt (mortgage)
    interest_mortgage: float = Field(
        default=0.0, ge=0,
        description="Line 16a: Interest on mortgages to banks, etc."
    )

    # Line 16b - Interest on other business debt
    interest_other: float = Field(
        default=0.0, ge=0,
        description="Line 16b: Interest on other business debt"
    )

    # Line 17 - Legal and professional services
    legal_and_professional: float = Field(
        default=0.0, ge=0,
        description="Line 17: Legal and professional services (attorneys, accountants)"
    )

    # Line 18 - Office expense
    office_expense: float = Field(
        default=0.0, ge=0,
        description="Line 18: Office expense (supplies, postage, etc.)"
    )

    # Line 19 - Pension and profit-sharing plans
    pension_profit_sharing: float = Field(
        default=0.0, ge=0,
        description="Line 19: Pension and profit-sharing plans for employees"
    )

    # Line 20a - Rent or lease: Vehicles, machinery, equipment
    rent_vehicles_equipment: float = Field(
        default=0.0, ge=0,
        description="Line 20a: Rent/lease of vehicles, machinery, equipment"
    )

    # Line 20b - Rent or lease: Other business property
    rent_other_property: float = Field(
        default=0.0, ge=0,
        description="Line 20b: Rent/lease of other business property (office, warehouse)"
    )

    # Line 21 - Repairs and maintenance
    repairs_and_maintenance: float = Field(
        default=0.0, ge=0,
        description="Line 21: Repairs and maintenance"
    )

    # Line 22 - Supplies (not included in Part III)
    supplies: float = Field(
        default=0.0, ge=0,
        description="Line 22: Supplies not included in COGS"
    )

    # Line 23 - Taxes and licenses
    taxes_and_licenses: float = Field(
        default=0.0, ge=0,
        description="Line 23: Taxes and licenses (business taxes, permits)"
    )

    # Line 24a - Travel
    travel: float = Field(
        default=0.0, ge=0,
        description="Line 24a: Travel expenses (airfare, lodging, etc.)"
    )

    # Line 24b - Deductible meals (50% limitation already applied or full amount)
    meals_full_amount: float = Field(
        default=0.0, ge=0,
        description="Line 24b: Business meals (full amount before 50% limit)"
    )
    meals_limitation_percentage: float = Field(
        default=0.50,
        ge=0, le=1.0,
        description="Meals deduction limit (typically 50%, was 100% for 2021-2022)"
    )

    # Line 25 - Utilities
    utilities: float = Field(
        default=0.0, ge=0,
        description="Line 25: Utilities (telephone, internet, electric for business)"
    )

    # Line 26 - Wages (not including amounts paid to yourself)
    wages: float = Field(
        default=0.0, ge=0,
        description="Line 26: Wages paid to employees (not owner)"
    )

    # Line 27a - Other expenses (from Part V, Line 48)
    other_expenses: List[OtherExpense] = Field(
        default_factory=list,
        description="Line 27a: Other expenses itemized in Part V"
    )

    # Line 30 - Expenses for business use of home (Form 8829)
    home_office_deduction: float = Field(
        default=0.0, ge=0,
        description="Line 30: Business use of home (from Form 8829 or simplified)"
    )

    def get_deductible_meals(self) -> float:
        """Calculate deductible portion of meals (typically 50%)."""
        return self.meals_full_amount * self.meals_limitation_percentage

    def get_total_other_expenses(self) -> float:
        """Calculate total of other expenses from Part V."""
        return sum(exp.amount for exp in self.other_expenses)

    def calculate_total_expenses(self) -> float:
        """
        Calculate total expenses (Line 28).

        Sum of all expense lines 8-27 plus home office (Line 30).
        """
        return (
            self.advertising +
            self.car_and_truck_expenses +
            self.commissions_and_fees +
            self.contract_labor +
            self.depletion +
            self.depreciation_section_179 +
            self.employee_benefit_programs +
            self.insurance_other +
            self.interest_mortgage +
            self.interest_other +
            self.legal_and_professional +
            self.office_expense +
            self.pension_profit_sharing +
            self.rent_vehicles_equipment +
            self.rent_other_property +
            self.repairs_and_maintenance +
            self.supplies +
            self.taxes_and_licenses +
            self.travel +
            self.get_deductible_meals() +
            self.utilities +
            self.wages +
            self.get_total_other_expenses() +
            self.home_office_deduction
        )


class ScheduleCBusiness(BaseModel):
    """
    Complete Schedule C - Profit or Loss From Business.

    Represents a single sole proprietorship business for tax reporting.
    A taxpayer may have multiple Schedule C businesses.

    Reference: IRS Form Schedule C (Form 1040)
    """
    # Part I Header - Business Information
    business_name: str = Field(description="Principal business or profession name")
    business_address: Optional[str] = Field(None, description="Business address if different from home")

    # Business code from IRS list
    business_code: Optional[str] = Field(
        None,
        description="6-digit business activity code from IRS instructions"
    )
    business_type: BusinessType = Field(
        default=BusinessType.OTHER,
        description="Type of business"
    )

    # Employer Identification Number (if applicable)
    ein: Optional[str] = Field(None, description="EIN if you have employees or file excise/pension returns")

    # Accounting method
    accounting_method: AccountingMethod = Field(
        default=AccountingMethod.CASH,
        description="Accounting method used"
    )

    # Material participation (important for passive activity rules)
    materially_participated: bool = Field(
        default=True,
        description="Did you materially participate in the operation of this business?"
    )

    # Business start date
    started_or_acquired_in_year: bool = Field(
        default=False,
        description="Did you start or acquire this business during the year?"
    )

    # Statutory employee (W-2 with box 13 checked)
    is_statutory_employee: bool = Field(
        default=False,
        description="Are you a statutory employee (W-2 Box 13 checked)?"
    )

    # === Part I: Income ===

    # Line 1 - Gross receipts or sales
    gross_receipts: float = Field(
        default=0.0, ge=0,
        description="Line 1: Gross receipts or sales"
    )

    # Line 2 - Returns and allowances
    returns_and_allowances: float = Field(
        default=0.0, ge=0,
        description="Line 2: Returns and allowances"
    )

    # Line 4 - Cost of goods sold (from Part III, Line 42)
    # This will be calculated from cost_of_goods_sold model

    # Line 6 - Other income (including federal/state fuel tax credit)
    other_income: float = Field(
        default=0.0, ge=0,
        description="Line 6: Other income (fuel tax credit, recovered bad debts, etc.)"
    )
    other_income_description: Optional[str] = None

    # === Part II: Expenses ===
    expenses: ScheduleCExpenses = Field(
        default_factory=ScheduleCExpenses,
        description="Part II: Business expenses"
    )

    # === Part III: Cost of Goods Sold ===
    cost_of_goods_sold: Optional[CostOfGoodsSold] = Field(
        None,
        description="Part III: Cost of goods sold (for businesses with inventory)"
    )

    # === Part IV: Vehicle Information ===
    vehicles: List[BusinessVehicle] = Field(
        default_factory=list,
        description="Part IV: Information on business vehicles"
    )

    # === 1099 Reporting ===
    made_payments_requiring_1099: bool = Field(
        default=False,
        description="Did you make payments that would require filing Form 1099?"
    )
    filed_required_1099s: bool = Field(
        default=True,
        description="Did you or will you file all required 1099s?"
    )

    # === Standard Mileage Rate ===
    standard_mileage_rate: float = Field(
        default=0.70,
        description="Standard mileage rate for the year (2025: $0.70/mile estimated)"
    )

    def calculate_vehicle_expenses(self) -> float:
        """Calculate total vehicle expenses from all business vehicles."""
        return sum(
            vehicle.calculate_deduction(self.standard_mileage_rate)
            for vehicle in self.vehicles
        )

    def get_cogs(self) -> float:
        """Get cost of goods sold (Line 4)."""
        if self.cost_of_goods_sold:
            return self.cost_of_goods_sold.calculate_cogs()
        return 0.0

    def calculate_gross_income(self) -> float:
        """
        Calculate gross income (Line 5).

        Gross receipts - Returns - COGS
        """
        net_receipts = self.gross_receipts - self.returns_and_allowances
        return net_receipts - self.get_cogs()

    def calculate_gross_profit(self) -> float:
        """
        Calculate gross profit (Line 7).

        Gross income + Other income
        """
        return self.calculate_gross_income() + self.other_income

    def get_total_expenses(self) -> float:
        """
        Get total expenses (Line 28).

        Includes vehicle expenses calculated from Part IV.
        """
        # Update car expenses from vehicles if not manually set
        vehicle_expenses = self.calculate_vehicle_expenses()

        # Get base expenses
        base_expenses = self.expenses.calculate_total_expenses()

        # If car expenses were set to 0 but we have vehicles, use calculated
        if self.expenses.car_and_truck_expenses == 0 and vehicle_expenses > 0:
            return base_expenses + vehicle_expenses

        return base_expenses

    def calculate_tentative_profit_loss(self) -> float:
        """
        Calculate tentative profit or loss (Line 29).

        Gross profit - Total expenses
        """
        return self.calculate_gross_profit() - self.get_total_expenses()

    def calculate_net_profit_loss(self) -> float:
        """
        Calculate net profit or loss (Line 31).

        For most taxpayers: Tentative profit - Home office deduction
        (Home office already included in expenses, so this equals tentative)

        If loss and not materially participating, may be limited by PAL rules.
        """
        return self.calculate_tentative_profit_loss()

    def is_loss(self) -> bool:
        """Check if business has a loss."""
        return self.calculate_net_profit_loss() < 0

    def get_se_income(self) -> float:
        """
        Get self-employment income for SE tax calculation.

        Statutory employees don't pay SE tax (employer pays).
        """
        if self.is_statutory_employee:
            return 0.0
        return self.calculate_net_profit_loss()

    def get_qbi_income(self) -> float:
        """
        Get qualified business income for Section 199A deduction.

        Generally equals net profit, but may have adjustments for
        specified service trades or businesses (SSTB).
        """
        net = self.calculate_net_profit_loss()
        # QBI cannot be negative for the deduction calculation
        # (losses reduce QBI from other sources)
        return net

    def generate_summary(self) -> dict:
        """Generate a summary of the Schedule C calculation."""
        vehicle_expenses = self.calculate_vehicle_expenses()

        return {
            'business_name': self.business_name,
            'business_type': self.business_type.value,
            'accounting_method': self.accounting_method.value,
            'materially_participated': self.materially_participated,

            # Income
            'gross_receipts': round(self.gross_receipts, 2),
            'returns_and_allowances': round(self.returns_and_allowances, 2),
            'net_receipts': round(self.gross_receipts - self.returns_and_allowances, 2),
            'cost_of_goods_sold': round(self.get_cogs(), 2),
            'gross_income': round(self.calculate_gross_income(), 2),
            'other_income': round(self.other_income, 2),
            'gross_profit': round(self.calculate_gross_profit(), 2),

            # Expenses breakdown
            'expenses': {
                'advertising': self.expenses.advertising,
                'car_and_truck': self.expenses.car_and_truck_expenses + vehicle_expenses,
                'commissions_and_fees': self.expenses.commissions_and_fees,
                'contract_labor': self.expenses.contract_labor,
                'depletion': self.expenses.depletion,
                'depreciation': self.expenses.depreciation_section_179,
                'employee_benefits': self.expenses.employee_benefit_programs,
                'insurance': self.expenses.insurance_other,
                'interest': self.expenses.interest_mortgage + self.expenses.interest_other,
                'legal_professional': self.expenses.legal_and_professional,
                'office_expense': self.expenses.office_expense,
                'pension_plans': self.expenses.pension_profit_sharing,
                'rent_lease': self.expenses.rent_vehicles_equipment + self.expenses.rent_other_property,
                'repairs': self.expenses.repairs_and_maintenance,
                'supplies': self.expenses.supplies,
                'taxes_licenses': self.expenses.taxes_and_licenses,
                'travel': self.expenses.travel,
                'meals': self.expenses.get_deductible_meals(),
                'utilities': self.expenses.utilities,
                'wages': self.expenses.wages,
                'other': self.expenses.get_total_other_expenses(),
                'home_office': self.expenses.home_office_deduction,
            },
            'total_expenses': round(self.get_total_expenses(), 2),

            # Results
            'net_profit_or_loss': round(self.calculate_net_profit_loss(), 2),
            'is_loss': self.is_loss(),
            'se_income': round(self.get_se_income(), 2),
            'qbi_income': round(self.get_qbi_income(), 2),

            # Vehicle summary
            'vehicle_count': len(self.vehicles),
            'total_vehicle_expenses': round(vehicle_expenses, 2),
            'total_business_miles': sum(v.business_miles for v in self.vehicles),
        }


class HomeOfficeMethod(str, Enum):
    """Method for calculating home office deduction."""
    SIMPLIFIED = "simplified"  # $5 per sq ft, max 300 sq ft = $1,500
    REGULAR = "regular"  # Actual expenses pro-rated


class HomeOffice(BaseModel):
    """
    Home Office Deduction (Form 8829 or Simplified Method).

    For taxpayers who use part of their home regularly and exclusively
    for business purposes.
    """
    # Method selection
    method: HomeOfficeMethod = Field(
        default=HomeOfficeMethod.SIMPLIFIED,
        description="Method for calculating home office deduction"
    )

    # Square footage (used for both methods)
    home_total_square_feet: float = Field(ge=0, description="Total square feet of home")
    office_square_feet: float = Field(ge=0, description="Square feet used for business")

    # Simplified method limits
    simplified_rate: float = Field(default=5.0, description="Rate per square foot ($5)")
    simplified_max_square_feet: float = Field(default=300.0, description="Maximum square feet (300)")

    # Regular method expenses (Form 8829)
    # Direct expenses (100% deductible if only for office)
    direct_expenses: float = Field(default=0.0, ge=0, description="Expenses only for office")

    # Indirect expenses (pro-rated by business use percentage)
    mortgage_interest: float = Field(default=0.0, ge=0)
    real_estate_taxes: float = Field(default=0.0, ge=0)
    homeowners_insurance: float = Field(default=0.0, ge=0)
    utilities: float = Field(default=0.0, ge=0)
    repairs_maintenance: float = Field(default=0.0, ge=0)
    rent: float = Field(default=0.0, ge=0, description="If renting, rent amount")
    home_depreciation: float = Field(default=0.0, ge=0, description="Depreciation of home")
    other_indirect: float = Field(default=0.0, ge=0)

    # Carryover from prior year (if deduction was limited)
    prior_year_carryover: float = Field(default=0.0, ge=0)

    def get_business_use_percentage(self) -> float:
        """Calculate business use percentage of home."""
        if self.home_total_square_feet <= 0:
            return 0.0
        return (self.office_square_feet / self.home_total_square_feet) * 100

    def calculate_simplified_deduction(self) -> float:
        """
        Calculate deduction using simplified method.

        $5 per square foot, maximum 300 square feet = $1,500 max.
        """
        eligible_sqft = min(self.office_square_feet, self.simplified_max_square_feet)
        return eligible_sqft * self.simplified_rate

    def calculate_regular_deduction(self, gross_income_limit: float = float('inf')) -> float:
        """
        Calculate deduction using regular method (Form 8829).

        Deduction is limited to gross income from business use of home.
        """
        business_pct = self.get_business_use_percentage() / 100

        # Indirect expenses × business use percentage
        indirect_total = (
            self.mortgage_interest +
            self.real_estate_taxes +
            self.homeowners_insurance +
            self.utilities +
            self.repairs_maintenance +
            self.rent +
            self.home_depreciation +
            self.other_indirect
        )

        indirect_deduction = indirect_total * business_pct
        total_deduction = self.direct_expenses + indirect_deduction + self.prior_year_carryover

        # Limited to gross income from business (prevents creating a loss from home office)
        return min(total_deduction, gross_income_limit)

    def calculate_deduction(self, gross_income_limit: float = float('inf')) -> float:
        """Calculate home office deduction based on selected method."""
        if self.method == HomeOfficeMethod.SIMPLIFIED:
            return self.calculate_simplified_deduction()
        else:
            return self.calculate_regular_deduction(gross_income_limit)
