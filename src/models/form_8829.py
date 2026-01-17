"""
Form 8829 - Expenses for Business Use of Your Home

Complete IRS Form 8829 implementation for home office deduction:

Part I: Part of Your Home Used for Business
- Square footage calculation
- Business use percentage
- Daycare facility exception

Part II: Figure Your Allowable Deduction
- Direct expenses (100% deductible)
- Indirect expenses (prorated by business %)
- Depreciation of home
- Carryover from prior year
- Gross income limitation

Part III: Depreciation of Your Home
- Cost/basis of home
- Land value (not depreciable)
- Depreciation calculation (39-year SL for home)

Part IV: Carryover of Unallowed Expenses to Next Year
- Operating expenses carryover
- Excess casualty/depreciation carryover

Two methods available:
1. Simplified Method: $5/sq ft, max 300 sq ft = $1,500 max
2. Regular Method (Form 8829): Actual expenses prorated

Requirements for deduction:
- Regular and exclusive use
- Principal place of business OR
- Place to meet clients/customers OR
- Separate structure used for business
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field
from datetime import date


class HomeOfficeMethod(str, Enum):
    """Method for calculating home office deduction."""
    SIMPLIFIED = "simplified"  # $5/sq ft, max 300 sq ft = $1,500
    REGULAR = "regular"  # Actual expenses - Form 8829


class HomeType(str, Enum):
    """Type of home for depreciation purposes."""
    HOUSE = "house"
    CONDO = "condo"
    APARTMENT = "apartment"  # Rent, no depreciation
    MOBILE_HOME = "mobile_home"
    BOAT = "boat"  # If used as residence
    OTHER = "other"


class BusinessUseType(str, Enum):
    """Type of business use qualifying for deduction."""
    PRINCIPAL_PLACE = "principal_place"  # Principal place of business
    MEETING_CLIENTS = "meeting_clients"  # Place to meet clients/customers
    SEPARATE_STRUCTURE = "separate_structure"  # Separate structure
    STORAGE = "storage"  # Storage of inventory/samples
    DAYCARE = "daycare"  # Daycare facility (special rules)


class Form8829Part1(BaseModel):
    """
    Form 8829 Part I: Part of Your Home Used for Business

    Calculates the business use percentage of the home.
    """
    # Line 1: Area used regularly and exclusively for business
    line_1_business_area: float = Field(
        default=0.0, ge=0,
        description="Line 1: Square footage used for business"
    )

    # Line 2: Total area of home
    line_2_total_area: float = Field(
        default=0.0, ge=0,
        description="Line 2: Total square footage of home"
    )

    # Line 3: Business percentage (Line 1 / Line 2)
    @computed_field
    @property
    def line_3_business_percentage(self) -> float:
        """Line 3: Business use percentage."""
        if self.line_2_total_area <= 0:
            return 0.0
        return round((self.line_1_business_area / self.line_2_total_area) * 100, 2)

    # Line 4: Hours home used for daycare (if applicable)
    line_4_daycare_hours: float = Field(
        default=0.0, ge=0, le=8760,  # Max hours in a year
        description="Line 4: Hours home used for daycare"
    )

    # Line 5: Total hours in year (8,760)
    line_5_total_hours: float = Field(
        default=8760.0,
        description="Line 5: Total hours available in year (8,760)"
    )

    # Line 6: Daycare percentage
    @computed_field
    @property
    def line_6_daycare_percentage(self) -> float:
        """Line 6: Daycare time percentage (Line 4 / Line 5)."""
        if self.line_4_daycare_hours <= 0:
            return 0.0
        return round((self.line_4_daycare_hours / self.line_5_total_hours) * 100, 2)

    # Line 7: Business percentage for daycare
    @computed_field
    @property
    def line_7_daycare_business_pct(self) -> float:
        """Line 7: Daycare business percentage (Line 3 × Line 6 / 100)."""
        if self.line_4_daycare_hours > 0:
            return round(self.line_3_business_percentage * self.line_6_daycare_percentage / 100, 2)
        return self.line_3_business_percentage


class Form8829Part2(BaseModel):
    """
    Form 8829 Part II: Figure Your Allowable Deduction

    Calculates the deductible home office expenses.
    """
    # Business use percentage from Part I
    business_percentage: float = Field(
        default=0.0, ge=0, le=100,
        description="Business use percentage from Part I"
    )

    # Line 8: Tentative profit from Schedule C (before home office deduction)
    line_8_tentative_profit: float = Field(
        default=0.0,
        description="Line 8: Tentative profit/loss from Schedule C Line 29"
    )

    # Direct expenses (100% deductible)
    # Line 9-15 are individual expense categories
    # We use a single field for simplicity
    line_9_direct_expenses: float = Field(
        default=0.0, ge=0,
        description="Direct expenses (used only for business)"
    )

    # Indirect expenses (Column a: total, Column b: business portion)
    # Line 16: Casualty losses
    line_16_casualty_losses: float = Field(
        default=0.0, ge=0,
        description="Line 16: Casualty losses (Form 4684)"
    )

    # Line 17: Deductible mortgage interest
    line_17_mortgage_interest: float = Field(
        default=0.0, ge=0,
        description="Line 17: Deductible mortgage interest"
    )

    # Line 18: Real estate taxes
    line_18_real_estate_taxes: float = Field(
        default=0.0, ge=0,
        description="Line 18: Real estate taxes"
    )

    # Line 19: Add lines 16-18
    @computed_field
    @property
    def line_19_total_casualty_mortgage_taxes(self) -> float:
        """Line 19: Sum of casualty, mortgage, taxes."""
        return self.line_16_casualty_losses + self.line_17_mortgage_interest + self.line_18_real_estate_taxes

    # Line 20: Business portion (Line 19 × business %)
    @computed_field
    @property
    def line_20_business_portion(self) -> float:
        """Line 20: Business portion of casualty/mortgage/taxes."""
        return round(self.line_19_total_casualty_mortgage_taxes * (self.business_percentage / 100), 2)

    # Line 21: Carryover from prior year (Form 8829, line 44)
    line_21_carryover_operating: float = Field(
        default=0.0, ge=0,
        description="Line 21: Operating expenses carryover from prior year"
    )

    # Line 22: Add lines 9, 20, and 21
    @computed_field
    @property
    def line_22_subtotal(self) -> float:
        """Line 22: Subtotal (Direct + business casualty/mortgage/taxes + carryover)."""
        return self.line_9_direct_expenses + self.line_20_business_portion + self.line_21_carryover_operating

    # Line 23: Subtract Line 22 from Line 8 (limit for other expenses)
    @computed_field
    @property
    def line_23_limit_for_other(self) -> float:
        """Line 23: Limit for remaining expenses (Line 8 - Line 22)."""
        return max(0, self.line_8_tentative_profit - self.line_22_subtotal)

    # Other indirect expenses
    # Line 24: Excess mortgage interest
    line_24_excess_mortgage: float = Field(
        default=0.0, ge=0,
        description="Line 24: Excess mortgage interest"
    )

    # Line 25: Insurance
    line_25_insurance: float = Field(
        default=0.0, ge=0,
        description="Line 25: Insurance"
    )

    # Line 26: Rent
    line_26_rent: float = Field(
        default=0.0, ge=0,
        description="Line 26: Rent"
    )

    # Line 27: Repairs and maintenance
    line_27_repairs: float = Field(
        default=0.0, ge=0,
        description="Line 27: Repairs and maintenance"
    )

    # Line 28: Utilities
    line_28_utilities: float = Field(
        default=0.0, ge=0,
        description="Line 28: Utilities"
    )

    # Line 29: Other expenses
    line_29_other: float = Field(
        default=0.0, ge=0,
        description="Line 29: Other indirect expenses"
    )

    # Line 30: Add lines 24-29
    @computed_field
    @property
    def line_30_total_other_indirect(self) -> float:
        """Line 30: Total other indirect expenses."""
        return (
            self.line_24_excess_mortgage +
            self.line_25_insurance +
            self.line_26_rent +
            self.line_27_repairs +
            self.line_28_utilities +
            self.line_29_other
        )

    # Line 31: Business portion of Line 30
    @computed_field
    @property
    def line_31_business_other_indirect(self) -> float:
        """Line 31: Business portion of other indirect."""
        return round(self.line_30_total_other_indirect * (self.business_percentage / 100), 2)

    # Line 32: Carryover from prior year (operating)
    line_32_carryover_other: float = Field(
        default=0.0, ge=0,
        description="Line 32: Operating expense carryover (other)"
    )

    # Line 33: Add lines 31 and 32
    @computed_field
    @property
    def line_33_total_other(self) -> float:
        """Line 33: Total other expenses plus carryover."""
        return self.line_31_business_other_indirect + self.line_32_carryover_other

    # Line 34: Allowable other expenses (smaller of Line 23 or 33)
    @computed_field
    @property
    def line_34_allowable_other(self) -> float:
        """Line 34: Allowable other expenses (limited by profit)."""
        return min(self.line_23_limit_for_other, self.line_33_total_other)

    # Line 35: Add lines 22 and 34
    @computed_field
    @property
    def line_35_subtotal_before_depreciation(self) -> float:
        """Line 35: Subtotal before depreciation."""
        return self.line_22_subtotal + self.line_34_allowable_other

    # Line 36: Limit for casualty and depreciation (Line 8 - Line 35)
    @computed_field
    @property
    def line_36_limit_depreciation(self) -> float:
        """Line 36: Limit for depreciation."""
        return max(0, self.line_8_tentative_profit - self.line_35_subtotal_before_depreciation)

    # Depreciation (from Part III)
    line_37_depreciation: float = Field(
        default=0.0, ge=0,
        description="Line 37: Depreciation from Part III"
    )

    # Line 38: Carryover of excess casualty/depreciation
    line_38_depreciation_carryover: float = Field(
        default=0.0, ge=0,
        description="Line 38: Depreciation carryover from prior year"
    )

    # Line 39: Add lines 37 and 38
    @computed_field
    @property
    def line_39_total_depreciation(self) -> float:
        """Line 39: Total depreciation plus carryover."""
        return self.line_37_depreciation + self.line_38_depreciation_carryover

    # Line 40: Allowable depreciation (smaller of Line 36 or 39)
    @computed_field
    @property
    def line_40_allowable_depreciation(self) -> float:
        """Line 40: Allowable depreciation (limited by profit)."""
        return min(self.line_36_limit_depreciation, self.line_39_total_depreciation)

    # Line 41: Add lines 14, 35, and 40 (total allowable expenses)
    @computed_field
    @property
    def line_41_total_allowable(self) -> float:
        """Line 41: Total allowable expenses (deduction to Schedule C)."""
        # Note: Line 14 is part of line_9_direct_expenses in this implementation
        return self.line_35_subtotal_before_depreciation + self.line_40_allowable_depreciation


class Form8829Part3(BaseModel):
    """
    Form 8829 Part III: Depreciation of Your Home

    Calculates annual depreciation for business use portion of home.
    """
    # Line 36: Smaller of adjusted basis or fair market value
    line_36_basis_or_fmv: float = Field(
        default=0.0, ge=0,
        description="Line 36: Smaller of adjusted basis or FMV"
    )

    # Line 37: Value of land (not depreciable)
    line_37_land_value: float = Field(
        default=0.0, ge=0,
        description="Line 37: Value of land"
    )

    # Line 38: Basis of building (Line 36 - Line 37)
    @computed_field
    @property
    def line_38_building_basis(self) -> float:
        """Line 38: Basis of building (excluding land)."""
        return max(0, self.line_36_basis_or_fmv - self.line_37_land_value)

    # Line 39: Business use percentage
    line_39_business_pct: float = Field(
        default=0.0, ge=0, le=100,
        description="Line 39: Business use percentage"
    )

    # Line 40: Business basis (Line 38 × Line 39)
    @computed_field
    @property
    def line_40_business_basis(self) -> float:
        """Line 40: Business basis of building."""
        return round(self.line_38_building_basis * (self.line_39_business_pct / 100), 2)

    # Line 41: Depreciation percentage (residential = 39 years SL = 2.564%)
    line_41_depreciation_pct: float = Field(
        default=2.564,
        description="Line 41: Depreciation percentage (2.564% for 39-year)"
    )

    # Line 42: Depreciation allowable (Line 40 × Line 41 / 100)
    @computed_field
    @property
    def line_42_depreciation_allowable(self) -> float:
        """Line 42: Depreciation allowable."""
        return round(self.line_40_business_basis * (self.line_41_depreciation_pct / 100), 2)


class Form8829Part4(BaseModel):
    """
    Form 8829 Part IV: Carryover of Unallowed Expenses to Next Year

    Tracks expenses that couldn't be deducted due to profit limitations.
    """
    # Line 43: Operating expenses carryover
    line_43_operating_carryover: float = Field(
        default=0.0, ge=0,
        description="Line 43: Operating expenses to carryover"
    )

    # Line 44: Excess casualty/depreciation carryover
    line_44_depreciation_carryover: float = Field(
        default=0.0, ge=0,
        description="Line 44: Excess depreciation to carryover"
    )


class Form8829(BaseModel):
    """
    Form 8829 - Expenses for Business Use of Your Home

    Complete implementation of IRS Form 8829 for home office deduction.

    Can be used with either:
    - Simplified Method ($5/sq ft, max 300 sq ft)
    - Regular Method (actual expenses, Form 8829)
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Method selection
    method: HomeOfficeMethod = Field(
        default=HomeOfficeMethod.REGULAR,
        description="Deduction method"
    )

    # Business information
    business_name: str = Field(default="", description="Name of business")
    business_use_type: BusinessUseType = Field(
        default=BusinessUseType.PRINCIPAL_PLACE,
        description="Type of qualifying business use"
    )

    # Home information
    home_type: HomeType = Field(default=HomeType.HOUSE, description="Type of home")
    date_home_used_for_business: Optional[str] = Field(
        default=None,
        description="Date home was first used for business"
    )

    # Part I: Business Use Calculation
    part_1: Form8829Part1 = Field(
        default_factory=Form8829Part1,
        description="Part I: Business use percentage"
    )

    # Part II: Deduction Calculation (only for regular method)
    part_2: Form8829Part2 = Field(
        default_factory=Form8829Part2,
        description="Part II: Allowable deduction"
    )

    # Part III: Depreciation (only for regular method)
    part_3: Form8829Part3 = Field(
        default_factory=Form8829Part3,
        description="Part III: Home depreciation"
    )

    # Part IV: Carryover
    part_4: Form8829Part4 = Field(
        default_factory=Form8829Part4,
        description="Part IV: Expense carryover"
    )

    # Simplified method specific
    simplified_rate: float = Field(
        default=5.0,
        description="Simplified method rate ($5/sq ft)"
    )
    simplified_max_sqft: float = Field(
        default=300.0,
        description="Simplified method max square feet"
    )

    def calculate_simplified_deduction(self) -> float:
        """
        Calculate deduction using simplified method.

        $5 per square foot, maximum 300 square feet = $1,500 max.
        Cannot create a loss from home office.
        """
        eligible_sqft = min(self.part_1.line_1_business_area, self.simplified_max_sqft)
        return eligible_sqft * self.simplified_rate

    def calculate_regular_deduction(self) -> float:
        """
        Calculate deduction using regular method (Form 8829).

        Returns the allowable deduction from Part II Line 41.
        """
        # Update Part II with business percentage from Part I
        if self.part_2.business_percentage == 0:
            part2_data = self.part_2.model_dump(exclude={'business_percentage'})
            self.part_2 = Form8829Part2(
                **part2_data,
                business_percentage=self.part_1.line_3_business_percentage
            )

        # Update Part III with business percentage
        if self.part_3.line_39_business_pct == 0:
            part3_data = self.part_3.model_dump(exclude={'line_39_business_pct'})
            self.part_3 = Form8829Part3(
                **part3_data,
                line_39_business_pct=self.part_1.line_3_business_percentage
            )

        # Part II already computed depreciation (line 37 should be set from Part III)
        return self.part_2.line_41_total_allowable

    @computed_field
    @property
    def deduction(self) -> float:
        """Calculate the home office deduction based on selected method."""
        if self.method == HomeOfficeMethod.SIMPLIFIED:
            return self.calculate_simplified_deduction()
        return self.calculate_regular_deduction()

    @computed_field
    @property
    def business_use_percentage(self) -> float:
        """Business use percentage of home."""
        return self.part_1.line_3_business_percentage

    @computed_field
    @property
    def operating_expense_carryover(self) -> float:
        """Operating expenses to carryover to next year."""
        if self.method == HomeOfficeMethod.SIMPLIFIED:
            return 0.0
        # Carryover = total expenses - allowable expenses
        excess_other = max(0, self.part_2.line_33_total_other - self.part_2.line_34_allowable_other)
        return excess_other

    @computed_field
    @property
    def depreciation_carryover(self) -> float:
        """Depreciation to carryover to next year."""
        if self.method == HomeOfficeMethod.SIMPLIFIED:
            return 0.0
        return max(0, self.part_2.line_39_total_depreciation - self.part_2.line_40_allowable_depreciation)

    def is_deduction_limited(self) -> bool:
        """Check if deduction is limited by gross income."""
        if self.method == HomeOfficeMethod.SIMPLIFIED:
            return False
        return (
            self.operating_expense_carryover > 0 or
            self.depreciation_carryover > 0
        )

    def to_schedule_c_line_30(self) -> float:
        """Get the amount for Schedule C Line 30."""
        return self.deduction

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "tax_year": self.tax_year,
            "method": self.method.value,
            "business_use_type": self.business_use_type.value,
            "business_use_percentage": self.business_use_percentage,
            "deduction": self.deduction,
        }

        if self.method == HomeOfficeMethod.SIMPLIFIED:
            result["simplified"] = {
                "square_feet": self.part_1.line_1_business_area,
                "eligible_square_feet": min(self.part_1.line_1_business_area, self.simplified_max_sqft),
                "rate_per_sqft": self.simplified_rate,
                "max_deduction": 1500.0,
            }
        else:
            result["regular"] = {
                "direct_expenses": self.part_2.line_9_direct_expenses,
                "indirect_expenses_total": self.part_2.line_30_total_other_indirect,
                "indirect_expenses_business": self.part_2.line_31_business_other_indirect,
                "depreciation_allowable": self.part_2.line_40_allowable_depreciation,
                "total_allowable": self.part_2.line_41_total_allowable,
                "operating_carryover": self.operating_expense_carryover,
                "depreciation_carryover": self.depreciation_carryover,
                "is_limited": self.is_deduction_limited(),
            }

        return result


def calculate_home_office_deduction(
    office_sqft: float,
    total_home_sqft: float,
    method: str = "simplified",
    tentative_profit: float = 0.0,
    **expenses
) -> Dict[str, Any]:
    """
    Convenience function to calculate home office deduction.

    Args:
        office_sqft: Square footage of office
        total_home_sqft: Total square footage of home
        method: "simplified" or "regular"
        tentative_profit: Schedule C tentative profit (for regular method limit)
        **expenses: For regular method - mortgage_interest, taxes, insurance, etc.

    Returns:
        Dictionary with deduction amount and details
    """
    part1 = Form8829Part1(
        line_1_business_area=office_sqft,
        line_2_total_area=total_home_sqft
    )

    if method == "simplified":
        form = Form8829(
            method=HomeOfficeMethod.SIMPLIFIED,
            part_1=part1
        )
    else:
        part2 = Form8829Part2(
            business_percentage=part1.line_3_business_percentage,
            line_8_tentative_profit=tentative_profit,
            line_9_direct_expenses=expenses.get('direct_expenses', 0),
            line_17_mortgage_interest=expenses.get('mortgage_interest', 0),
            line_18_real_estate_taxes=expenses.get('real_estate_taxes', 0),
            line_25_insurance=expenses.get('insurance', 0),
            line_26_rent=expenses.get('rent', 0),
            line_27_repairs=expenses.get('repairs', 0),
            line_28_utilities=expenses.get('utilities', 0),
            line_29_other=expenses.get('other', 0),
        )

        form = Form8829(
            method=HomeOfficeMethod.REGULAR,
            part_1=part1,
            part_2=part2
        )

    return form.to_dict()
