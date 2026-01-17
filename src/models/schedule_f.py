"""
Schedule F (Form 1040) - Profit or Loss From Farming

IRS Form for reporting income and expenses from farming operations.
Includes crop income, livestock, agricultural program payments,
and farm-related expenses.

Key Rules:
- Cash method or accrual method accounting allowed
- Self-employment tax applies to net farm profit
- Conservation expenses may be deductible
- Income averaging available (Schedule J)
- Farmer's 66⅔% estimated tax safe harbor (vs 90%)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

# At-risk warning threshold (IRC Section 465)
AT_RISK_WARNING_THRESHOLD = 10000


class FarmType(str, Enum):
    """Type of farming operation."""
    CROP = "crop"
    LIVESTOCK = "livestock"
    DAIRY = "dairy"
    POULTRY = "poultry"
    FRUIT_ORCHARD = "fruit_orchard"
    VEGETABLE = "vegetable"
    MIXED = "mixed"
    OTHER = "other"


class AccountingMethod(str, Enum):
    """Accounting method for farm."""
    CASH = "cash"
    ACCRUAL = "accrual"


class LivestockPurpose(str, Enum):
    """Purpose of livestock."""
    SALE = "sale"  # Raised primarily for sale
    DRAFT = "draft"  # Draft, breeding, sport, or dairy
    BREEDING = "breeding"


class FarmIncome(BaseModel):
    """Farm income sources."""
    # Line 1: Sales of livestock and other items bought for resale
    livestock_resale_gross: float = Field(default=0.0, ge=0)
    livestock_resale_cost: float = Field(default=0.0, ge=0)

    # Line 2: Sales of livestock, produce, grains, etc. you raised
    livestock_raised_sales: float = Field(default=0.0, ge=0)
    produce_sales: float = Field(default=0.0, ge=0)
    grain_sales: float = Field(default=0.0, ge=0)

    # Line 3a-3b: Cooperative distributions
    coop_distributions_taxable: float = Field(default=0.0, ge=0)
    coop_distributions_nontaxable: float = Field(default=0.0, ge=0)

    # Line 4: Agricultural program payments
    ag_program_payments: float = Field(default=0.0, ge=0)
    ccc_loans_reported: float = Field(default=0.0, ge=0)
    ccc_loans_forfeited: float = Field(default=0.0, ge=0)

    # Line 5: Crop insurance proceeds
    crop_insurance_proceeds: float = Field(default=0.0, ge=0)
    disaster_payments: float = Field(default=0.0, ge=0)

    # Line 6: Custom hire income
    custom_hire_income: float = Field(default=0.0, ge=0)

    # Line 7: Other farm income
    other_farm_income: float = Field(default=0.0, ge=0)
    patronage_dividends: float = Field(default=0.0, ge=0)
    fuel_credit_refund: float = Field(default=0.0, ge=0)


class FarmExpenses(BaseModel):
    """Farm expenses."""
    # Line 10-34 expenses
    car_truck: float = Field(default=0.0, ge=0, description="Car and truck expenses")
    chemicals: float = Field(default=0.0, ge=0)
    conservation: float = Field(default=0.0, ge=0, description="Conservation expenses")
    custom_hire: float = Field(default=0.0, ge=0, description="Custom hire (machine work)")
    depreciation_179: float = Field(default=0.0, ge=0, description="Depreciation and Section 179")
    employee_benefit: float = Field(default=0.0, ge=0, description="Employee benefit programs")
    feed: float = Field(default=0.0, ge=0, description="Feed purchased")
    fertilizers_lime: float = Field(default=0.0, ge=0)
    freight_trucking: float = Field(default=0.0, ge=0)
    gasoline_fuel_oil: float = Field(default=0.0, ge=0)
    insurance_other: float = Field(default=0.0, ge=0, description="Insurance (other than health)")
    interest_mortgage: float = Field(default=0.0, ge=0)
    interest_other: float = Field(default=0.0, ge=0)
    labor_hired: float = Field(default=0.0, ge=0)
    pension_profit_sharing: float = Field(default=0.0, ge=0)
    rent_vehicles: float = Field(default=0.0, ge=0, description="Rent - vehicles, machinery, equipment")
    rent_land_animals: float = Field(default=0.0, ge=0, description="Rent - land and animals")
    repairs_maintenance: float = Field(default=0.0, ge=0)
    seeds_plants: float = Field(default=0.0, ge=0)
    storage_warehousing: float = Field(default=0.0, ge=0)
    supplies: float = Field(default=0.0, ge=0)
    taxes: float = Field(default=0.0, ge=0, description="Taxes (not self-employment)")
    utilities: float = Field(default=0.0, ge=0)
    veterinary_breeding: float = Field(default=0.0, ge=0, description="Veterinary, breeding, medicine")
    other_expenses: float = Field(default=0.0, ge=0)

    def total(self) -> float:
        """Calculate total farm expenses."""
        return (
            self.car_truck +
            self.chemicals +
            self.conservation +
            self.custom_hire +
            self.depreciation_179 +
            self.employee_benefit +
            self.feed +
            self.fertilizers_lime +
            self.freight_trucking +
            self.gasoline_fuel_oil +
            self.insurance_other +
            self.interest_mortgage +
            self.interest_other +
            self.labor_hired +
            self.pension_profit_sharing +
            self.rent_vehicles +
            self.rent_land_animals +
            self.repairs_maintenance +
            self.seeds_plants +
            self.storage_warehousing +
            self.supplies +
            self.taxes +
            self.utilities +
            self.veterinary_breeding +
            self.other_expenses
        )


class ScheduleF(BaseModel):
    """
    Schedule F (Form 1040) - Profit or Loss From Farming

    Complete model for IRS Schedule F.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Farm information
    farm_name: str = Field(default="", description="Name of farm")
    farm_address: str = Field(default="", description="Farm address")
    farm_type: FarmType = Field(
        default=FarmType.MIXED,
        description="Principal agricultural activity"
    )
    accounting_method: AccountingMethod = Field(
        default=AccountingMethod.CASH,
        description="Accounting method"
    )
    employer_ein: str = Field(default="", description="Farm EIN if applicable")

    # Material participation
    materially_participated: bool = Field(
        default=True,
        description="Materially participated in farm operation"
    )

    # Income and expenses
    farm_income: FarmIncome = Field(
        default_factory=FarmIncome,
        description="Farm income sources"
    )
    farm_expenses: FarmExpenses = Field(
        default_factory=FarmExpenses,
        description="Farm expenses"
    )

    # Beginning/ending inventory (accrual method)
    inventory_beginning: float = Field(default=0.0, ge=0)
    inventory_ending: float = Field(default=0.0, ge=0)
    cost_of_items_purchased: float = Field(default=0.0, ge=0)

    # Optional farm income averaging
    use_income_averaging: bool = Field(
        default=False,
        description="Elect to use income averaging (Schedule J)"
    )

    # Prior year losses
    prior_year_nol_carryover: float = Field(
        default=0.0, ge=0,
        description="Net operating loss carryover"
    )

    def calculate_gross_income(self) -> Dict[str, float]:
        """
        Calculate gross farm income (Part I).
        """
        inc = self.farm_income

        # Line 1: Sales of livestock/items bought for resale
        line_1a = inc.livestock_resale_gross
        line_1b = inc.livestock_resale_cost
        line_1c = line_1a - line_1b

        # Line 2: Sales of livestock/produce raised
        line_2 = (
            inc.livestock_raised_sales +
            inc.produce_sales +
            inc.grain_sales
        )

        # Line 3: Cooperative distributions
        line_3a = inc.coop_distributions_taxable
        line_3b = inc.coop_distributions_nontaxable
        line_3 = line_3a

        # Line 4: Agricultural program payments
        line_4a = inc.ag_program_payments
        line_4b = inc.ccc_loans_reported

        # Line 5: Crop insurance proceeds and federal disaster
        line_5a = inc.crop_insurance_proceeds
        line_5b = inc.disaster_payments
        line_5c = line_5a  # Amount to defer (if elected)

        # Line 6: Custom hire income
        line_6 = inc.custom_hire_income

        # Line 7: Other income
        line_7 = (
            inc.other_farm_income +
            inc.patronage_dividends +
            inc.fuel_credit_refund
        )

        # Line 8: Gross farm income (accrual method adds inventory change)
        if self.accounting_method == AccountingMethod.ACCRUAL:
            inventory_change = self.inventory_ending - self.inventory_beginning
            gross_income_addition = inventory_change - self.cost_of_items_purchased
        else:
            gross_income_addition = 0.0

        line_9 = (
            line_1c +
            line_2 +
            line_3 +
            line_4a +
            line_4b +
            line_5a +
            line_6 +
            line_7 +
            gross_income_addition
        )

        return {
            'line_1a_livestock_resale_gross': round(line_1a, 2),
            'line_1b_livestock_resale_cost': round(line_1b, 2),
            'line_1c_livestock_resale_profit': round(line_1c, 2),
            'line_2_raised_sales': round(line_2, 2),
            'line_3_coop_distributions': round(line_3, 2),
            'line_4_ag_program_payments': round(line_4a + line_4b, 2),
            'line_5_crop_insurance': round(line_5a, 2),
            'line_6_custom_hire': round(line_6, 2),
            'line_7_other_income': round(line_7, 2),
            'line_9_gross_income': round(line_9, 2),
        }

    def calculate_expenses(self) -> Dict[str, float]:
        """
        Calculate farm expenses (Part II).
        """
        exp = self.farm_expenses

        return {
            'line_10_car_truck': exp.car_truck,
            'line_11_chemicals': exp.chemicals,
            'line_12_conservation': exp.conservation,
            'line_13_custom_hire': exp.custom_hire,
            'line_14_depreciation': exp.depreciation_179,
            'line_15_employee_benefit': exp.employee_benefit,
            'line_16_feed': exp.feed,
            'line_17_fertilizers': exp.fertilizers_lime,
            'line_18_freight': exp.freight_trucking,
            'line_19_fuel': exp.gasoline_fuel_oil,
            'line_20_insurance': exp.insurance_other,
            'line_21a_interest_mortgage': exp.interest_mortgage,
            'line_21b_interest_other': exp.interest_other,
            'line_22_labor_hired': exp.labor_hired,
            'line_23_pension': exp.pension_profit_sharing,
            'line_24a_rent_vehicles': exp.rent_vehicles,
            'line_24b_rent_land': exp.rent_land_animals,
            'line_25_repairs': exp.repairs_maintenance,
            'line_26_seeds': exp.seeds_plants,
            'line_27_storage': exp.storage_warehousing,
            'line_28_supplies': exp.supplies,
            'line_29_taxes': exp.taxes,
            'line_30_utilities': exp.utilities,
            'line_31_veterinary': exp.veterinary_breeding,
            'line_32_other': exp.other_expenses,
            'line_33_total_expenses': round(exp.total(), 2),
        }

    def calculate_net_profit_loss(self) -> Dict[str, Any]:
        """
        Calculate net farm profit or loss (Part III).
        """
        gross_income = self.calculate_gross_income()
        expenses = self.calculate_expenses()

        line_9 = gross_income['line_9_gross_income']
        line_33 = expenses['line_33_total_expenses']

        # Line 34: Net farm profit or loss
        line_34 = line_9 - line_33

        # Self-employment income (if materially participated)
        se_income = line_34 if self.materially_participated else 0.0

        # C2: At-risk rules warning (IRC Section 465)
        # For losses > $10,000, taxpayer may need Form 6198 to determine
        # at-risk limitation. This calculation assumes 100% at-risk which
        # may overstate deductible loss if taxpayer has nonrecourse debt
        # or is protected from loss by guarantees, stop-loss arrangements, etc.
        at_risk_amount = max(0, line_34)  # Simplified - assume full at-risk
        at_risk_warning = None

        if line_34 < 0 and abs(line_34) > AT_RISK_WARNING_THRESHOLD:
            at_risk_warning = (
                f"AT-RISK RULES MAY APPLY: Farm loss of ${abs(line_34):,.2f} exceeds "
                f"${AT_RISK_WARNING_THRESHOLD:,} threshold. Per IRC Section 465, losses "
                f"may be limited to taxpayer's at-risk amount. Form 6198 may be required. "
                f"CPA should verify: (1) nonrecourse financing, (2) guarantees or stop-loss "
                f"arrangements, (3) amounts borrowed from related parties. "
                f"See IRS Publication 925 for at-risk rules."
            )
            logger.warning(at_risk_warning)

        return {
            'gross_income': round(line_9, 2),
            'total_expenses': round(line_33, 2),
            'line_34_net_profit_loss': round(line_34, 2),
            'is_profit': line_34 >= 0,
            'is_loss': line_34 < 0,
            'self_employment_income': round(se_income, 2),
            'materially_participated': self.materially_participated,
            'at_risk_amount': round(at_risk_amount, 2),
            'at_risk_warning': at_risk_warning,
        }

    def calculate_schedule_f(self) -> Dict[str, Any]:
        """
        Calculate complete Schedule F.
        """
        gross_income = self.calculate_gross_income()
        expenses = self.calculate_expenses()
        net = self.calculate_net_profit_loss()

        return {
            'tax_year': self.tax_year,
            'farm_name': self.farm_name,
            'farm_type': self.farm_type.value,
            'accounting_method': self.accounting_method.value,

            # Summary
            'gross_farm_income': net['gross_income'],
            'total_farm_expenses': net['total_expenses'],
            'net_farm_profit_loss': net['line_34_net_profit_loss'],

            # Form 1040 flows
            'form_1040_line_6': net['line_34_net_profit_loss'],  # Flows to Line 6
            'schedule_se_income': net['self_employment_income'],

            # QBI eligible
            'qbi_eligible_income': net['line_34_net_profit_loss'] if net['is_profit'] else 0.0,

            # Farmer benefits
            'qualifies_for_farmer_safe_harbor': True,  # 66⅔% instead of 90%
            'eligible_for_income_averaging': self.use_income_averaging,

            # Detailed breakdowns
            'gross_income_detail': gross_income,
            'expenses_detail': expenses,
            'net_profit_detail': net,
        }

    def get_schedule_f_summary(self) -> Dict[str, float]:
        """Get a concise summary of Schedule F."""
        result = self.calculate_schedule_f()
        return {
            'gross_income': result['gross_farm_income'],
            'total_expenses': result['total_farm_expenses'],
            'net_profit_loss': result['net_farm_profit_loss'],
            'se_income': result['schedule_se_income'],
        }


def calculate_farm_profit_loss(
    crop_sales: float = 0.0,
    livestock_sales: float = 0.0,
    ag_program_payments: float = 0.0,
    feed_expense: float = 0.0,
    seed_expense: float = 0.0,
    fertilizer_expense: float = 0.0,
    labor_expense: float = 0.0,
    depreciation: float = 0.0,
    other_expenses: float = 0.0,
    materially_participated: bool = True,
) -> Dict[str, Any]:
    """
    Convenience function to calculate Schedule F farm profit/loss.

    Args:
        crop_sales: Sales of crops
        livestock_sales: Sales of livestock raised
        ag_program_payments: Agricultural program payments
        feed_expense: Feed purchased
        seed_expense: Seeds and plants
        fertilizer_expense: Fertilizers and lime
        labor_expense: Hired labor
        depreciation: Depreciation expense
        other_expenses: Other farm expenses
        materially_participated: Whether farmer materially participated

    Returns:
        Dictionary with Schedule F calculation results
    """
    farm_income = FarmIncome(
        produce_sales=crop_sales,
        livestock_raised_sales=livestock_sales,
        ag_program_payments=ag_program_payments,
    )

    farm_expenses = FarmExpenses(
        feed=feed_expense,
        seeds_plants=seed_expense,
        fertilizers_lime=fertilizer_expense,
        labor_hired=labor_expense,
        depreciation_179=depreciation,
        other_expenses=other_expenses,
    )

    schedule_f = ScheduleF(
        farm_income=farm_income,
        farm_expenses=farm_expenses,
        materially_participated=materially_participated,
    )

    return schedule_f.calculate_schedule_f()
