"""
Form 4562 - Depreciation and Amortization

Comprehensive IRS Form 4562 implementation for Tax Year 2025.

Covers:
- Part I: Section 179 Election to Expense
- Part II: Special Depreciation Allowance (Bonus Depreciation)
- Part III: MACRS Depreciation
- Part IV: Summary
- Part V: Listed Property (Section 280F)
- Part VI: Amortization (Section 197)

References:
- IRC Section 167: Depreciation
- IRC Section 168: MACRS
- IRC Section 179: Election to Expense
- IRC Section 197: Amortization of Intangibles
- IRC Section 280F: Listed Property Limitations
- IRS Publication 946: How to Depreciate Property
"""

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator
import logging
from models._decimal_utils import money, to_decimal

logger = logging.getLogger(__name__)


class DispositionRequiresManualReviewError(Exception):
    """
    C1: Raised when an asset disposition is encountered that requires manual CPA review.

    This is a BLOCKING error - calculation cannot proceed without manual intervention.
    The system does NOT calculate disposition-year depreciation to prevent silent reliance.

    Required manual actions:
    1. Calculate partial-year depreciation per convention (half-year, mid-quarter, mid-month)
    2. Complete Form 4797 for gain/loss on disposition
    3. Determine Section 1245/1250 recapture amounts
    4. Update basis tracking for any replacement property

    References: IRS Publication 946, Form 4797 Instructions
    """
    pass


# =============================================================================
# MACRS Property Classification
# =============================================================================

class MACRSPropertyClass(str, Enum):
    """
    MACRS Property Classes (IRC Section 168) - Recovery Periods.

    GDS (General Depreciation System) - Default
    ADS (Alternative Depreciation System) - Required for certain properties
    """
    YEAR_3 = "3"      # Tractors, racehorses (2+ years old), rent-to-own property
    YEAR_5 = "5"      # Autos, trucks, computers, office equipment, R&D equipment
    YEAR_7 = "7"      # Office furniture, fixtures, agricultural machinery
    YEAR_10 = "10"    # Vessels, barges, single-purpose ag structures
    YEAR_15 = "15"    # Land improvements, qualified improvement property (QIP)
    YEAR_20 = "20"    # Farm buildings, municipal sewers
    YEAR_27_5 = "27.5"  # Residential rental property
    YEAR_39 = "39"    # Nonresidential real property
    YEAR_50 = "50"    # Railroad grading/tunnel bores (ADS only)


class MACRSMethod(str, Enum):
    """MACRS Depreciation Methods."""
    GDS_200DB = "200db"      # 200% declining balance (default for 3-10 year)
    GDS_150DB = "150db"      # 150% declining balance (15, 20 year property)
    GDS_SL = "sl"            # Straight-line (27.5 and 39 year)
    ADS_SL = "ads_sl"        # ADS straight-line (required for some)


class MACRSConvention(str, Enum):
    """
    MACRS Conventions - Determines first/last year depreciation.
    """
    HALF_YEAR = "half_year"      # Default: Mid-year placed in service
    MID_QUARTER = "mid_quarter"  # If >40% placed in service in Q4
    MID_MONTH = "mid_month"      # Real property (27.5 and 39-year)


class ListedPropertyType(str, Enum):
    """Listed Property Types (Section 280F)."""
    PASSENGER_AUTO = "passenger_auto"
    OTHER_VEHICLE = "other_vehicle"
    COMPUTER = "computer"
    CELL_PHONE = "cell_phone"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


class AmortizationType(str, Enum):
    """Amortization Categories (Section 197 and others)."""
    SECTION_197 = "section_197"          # Goodwill, customer lists, covenants not to compete (15 years)
    STARTUP_COSTS = "startup_costs"       # Section 195 (180 months)
    ORGANIZATIONAL = "organizational"     # Section 248 (180 months)
    RESEARCH = "research"                 # Section 174 (60 months domestic)
    POLLUTION_CONTROL = "pollution_control"
    BOND_PREMIUM = "bond_premium"
    LEASE_ACQUISITION = "lease_acquisition"
    OTHER = "other"


# =============================================================================
# MACRS Depreciation Tables (IRS Publication 946, Appendix A)
# =============================================================================

# 200% Declining Balance with Half-Year Convention
MACRS_200DB_HY = {
    3: [0.3333, 0.4445, 0.1481, 0.0741],
    5: [0.2000, 0.3200, 0.1920, 0.1152, 0.1152, 0.0576],
    7: [0.1429, 0.2449, 0.1749, 0.1249, 0.0893, 0.0892, 0.0893, 0.0446],
    10: [0.1000, 0.1800, 0.1440, 0.1152, 0.0922, 0.0737, 0.0655, 0.0655, 0.0656, 0.0655, 0.0328],
}

# 150% Declining Balance with Half-Year Convention
MACRS_150DB_HY = {
    15: [0.0500, 0.0950, 0.0855, 0.0770, 0.0693, 0.0623, 0.0590, 0.0590, 0.0591, 0.0590,
         0.0591, 0.0590, 0.0591, 0.0590, 0.0591, 0.0295],
    20: [0.0375, 0.0722, 0.0668, 0.0618, 0.0571, 0.0528, 0.0489, 0.0452, 0.0447, 0.0447,
         0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0223],
}

# Straight-Line with Mid-Month Convention (Real Property)
# These are the first-year percentages based on month placed in service
MACRS_SL_MM_27_5 = {
    1: 0.03485, 2: 0.03182, 3: 0.02879, 4: 0.02576, 5: 0.02273, 6: 0.01970,
    7: 0.01667, 8: 0.01364, 9: 0.01061, 10: 0.00758, 11: 0.00455, 12: 0.00152
}

MACRS_SL_MM_39 = {
    1: 0.02461, 2: 0.02247, 3: 0.02033, 4: 0.01819, 5: 0.01605, 6: 0.01391,
    7: 0.01177, 8: 0.00963, 9: 0.00749, 10: 0.00535, 11: 0.00321, 12: 0.00107
}

# Mid-Quarter Convention Tables (by quarter placed in service)
MACRS_200DB_MQ = {
    5: {
        1: [0.3500, 0.2600, 0.1560, 0.1110, 0.1110, 0.0120],
        2: [0.2500, 0.3000, 0.1800, 0.1110, 0.1110, 0.0480],
        3: [0.1500, 0.3400, 0.2040, 0.1220, 0.1110, 0.0730],
        4: [0.0500, 0.3800, 0.2280, 0.1370, 0.1090, 0.0910],
    },
    7: {
        1: [0.2500, 0.2143, 0.1531, 0.1093, 0.0875, 0.0875, 0.0875, 0.0313],
        2: [0.1786, 0.2388, 0.1706, 0.1218, 0.0875, 0.0875, 0.0875, 0.0277],
        3: [0.1071, 0.2633, 0.1879, 0.1342, 0.0958, 0.0875, 0.0875, 0.0367],
        4: [0.0357, 0.2878, 0.2054, 0.1467, 0.1047, 0.0875, 0.0875, 0.0447],
    }
}


# =============================================================================
# Section 179 Limits (IRC Section 179)
# =============================================================================

class Section179Limits:
    """Section 179 expense limits for 2025."""
    MAX_DEDUCTION = 1250000      # Maximum Section 179 deduction
    PHASE_OUT_THRESHOLD = 3130000  # Phase-out begins
    # Deduction reduced dollar-for-dollar once purchases exceed threshold

    # SUV/Vehicle limits (IRC Section 179(b)(5)(A))
    SUV_LIMIT = 30500  # Heavy SUV limit (GVW > 6,000 lbs)

    # Qualified real property improvements
    QUALIFIED_IMPROVEMENT_PROPERTY = True  # QIP eligible for 179


# =============================================================================
# Bonus Depreciation Rates (IRC Section 168(k))
# =============================================================================

class BonusDepreciationRates:
    """
    Bonus Depreciation Phase-Down Schedule (TCJA).

    Property placed in service after September 27, 2017:
    - 2017-2022: 100%
    - 2023: 80%
    - 2024: 60%
    - 2025: 40%
    - 2026: 20%
    - 2027+: 0%
    """
    RATES_BY_YEAR = {
        2022: 1.00,
        2023: 0.80,
        2024: 0.60,
        2025: 0.40,
        2026: 0.20,
        2027: 0.00,
    }

    @classmethod
    def get_rate(cls, tax_year: int) -> float:
        """Get bonus depreciation rate for tax year."""
        if tax_year <= 2022:
            return 1.00
        return cls.RATES_BY_YEAR.get(tax_year, 0.00)


# =============================================================================
# Listed Property Limits (Section 280F)
# =============================================================================

class Section280FLimits:
    """
    Listed Property Limitations for Passenger Automobiles (2025).

    Luxury auto depreciation caps for vehicles placed in service in 2025.
    """
    # First year with bonus depreciation
    YEAR_1_WITH_BONUS = 20400
    YEAR_1_WITHOUT_BONUS = 12400

    # Subsequent years
    YEAR_2 = 19800
    YEAR_3 = 11900
    YEAR_4_PLUS = 7160

    # Electric vehicles may have higher limits
    EV_ADJUSTMENT = 8000  # Additional amount for EVs

    # Business use threshold
    BUSINESS_USE_THRESHOLD = 0.50  # Must be >50% business use


# =============================================================================
# Depreciable Asset Model
# =============================================================================

class DepreciableAsset(BaseModel):
    """
    Complete depreciable asset model for Form 4562.

    Tracks all IRS-required information for depreciation calculation.
    """
    # Identification
    asset_id: str = Field(default="", description="Unique asset identifier")
    description: str = Field(description="Description of property")

    # Acquisition
    date_placed_in_service: str = Field(description="Date placed in service (YYYY-MM-DD)")
    cost_basis: float = Field(ge=0, description="Cost or other basis")

    # For determining acquisition source
    is_new_property: bool = Field(default=True, description="New vs used property")
    acquisition_type: str = Field(default="purchase", description="purchase, inheritance, gift, like-kind")

    # MACRS Classification
    property_class: MACRSPropertyClass = Field(
        default=MACRSPropertyClass.YEAR_7,
        description="MACRS recovery period"
    )
    depreciation_method: MACRSMethod = Field(
        default=MACRSMethod.GDS_200DB,
        description="Depreciation method"
    )
    convention: MACRSConvention = Field(
        default=MACRSConvention.HALF_YEAR,
        description="Averaging convention"
    )

    # Business/Investment Use
    business_use_percentage: float = Field(
        default=1.0, ge=0, le=1,
        description="Business/investment use percentage (0-1)"
    )

    # Section 179 Election
    section_179_elected: float = Field(
        default=0.0, ge=0,
        description="Section 179 expense elected"
    )

    # Bonus Depreciation
    bonus_depreciation_elected: float = Field(
        default=0.0, ge=0,
        description="Bonus depreciation taken"
    )
    opted_out_of_bonus: bool = Field(
        default=False,
        description="Elected out of bonus depreciation"
    )

    # Depreciation History
    prior_depreciation: float = Field(
        default=0.0, ge=0,
        description="Accumulated depreciation from prior years"
    )
    prior_section_179: float = Field(
        default=0.0, ge=0,
        description="Section 179 taken in prior years"
    )
    prior_bonus: float = Field(
        default=0.0, ge=0,
        description="Bonus depreciation taken in prior years"
    )

    # Listed Property (Section 280F)
    is_listed_property: bool = Field(
        default=False,
        description="Subject to listed property rules"
    )
    listed_property_type: Optional[ListedPropertyType] = Field(
        default=None,
        description="Type of listed property"
    )

    # Vehicle-specific
    is_vehicle: bool = Field(default=False)
    vehicle_weight_gvw: float = Field(default=0.0, ge=0, description="Gross vehicle weight")
    vehicle_is_qualified_suv: bool = Field(default=False, description="Qualifies as heavy SUV")

    # Disposition tracking
    disposed_this_year: bool = Field(default=False)
    disposition_date: Optional[str] = Field(default=None)
    disposition_amount: float = Field(default=0.0, ge=0)

    def get_year_placed_in_service(self) -> int:
        """Extract year from date placed in service."""
        return int(self.date_placed_in_service[:4])

    def get_month_placed_in_service(self) -> int:
        """Extract month from date placed in service."""
        return int(self.date_placed_in_service[5:7])

    def get_quarter_placed_in_service(self) -> int:
        """Get quarter (1-4) asset was placed in service."""
        month = self.get_month_placed_in_service()
        return (month - 1) // 3 + 1

    def get_recovery_period(self) -> float:
        """Get recovery period in years."""
        return float(self.property_class.value)

    def get_depreciable_basis(self) -> float:
        """
        Calculate depreciable basis after Section 179 and bonus.

        Depreciable Basis = Cost - Section 179 - Bonus Depreciation
        """
        return max(0, self.cost_basis - self.section_179_elected - self.bonus_depreciation_elected)

    def get_year_in_service(self, tax_year: int) -> int:
        """Get which year of service this is (1 = first year)."""
        placed_year = self.get_year_placed_in_service()
        return tax_year - placed_year + 1

    def is_fully_depreciated(self) -> bool:
        """Check if asset is fully depreciated."""
        total_taken = self.prior_depreciation + self.section_179_elected + self.bonus_depreciation_elected
        return total_taken >= self.cost_basis * self.business_use_percentage


# =============================================================================
# Amortizable Asset Model
# =============================================================================

class AmortizableAsset(BaseModel):
    """
    Amortizable intangible asset for Form 4562 Part VI.
    """
    description: str = Field(description="Description of intangible")
    date_acquired: str = Field(description="Date acquired (YYYY-MM-DD)")
    cost_basis: float = Field(ge=0, description="Cost or other basis")

    amortization_type: AmortizationType = Field(
        default=AmortizationType.SECTION_197,
        description="Type of amortization"
    )
    amortization_period_months: int = Field(
        default=180,  # 15 years = 180 months for Section 197
        description="Amortization period in months"
    )

    prior_amortization: float = Field(
        default=0.0, ge=0,
        description="Accumulated amortization from prior years"
    )

    code_section: str = Field(
        default="197",
        description="IRC code section (197, 195, 248, etc.)"
    )

    def get_monthly_amortization(self) -> float:
        """Calculate monthly amortization amount."""
        return self.cost_basis / self.amortization_period_months

    def get_annual_amortization(self, tax_year: int) -> float:
        """
        Calculate amortization for tax year.

        First year: Pro-rated from month acquired
        Full years: 12 months
        Final year: Remaining balance
        """
        acquired_year = int(self.date_acquired[:4])
        acquired_month = int(self.date_acquired[5:7])

        monthly = self.get_monthly_amortization()

        if tax_year < acquired_year:
            return 0.0

        if tax_year == acquired_year:
            # First year: months from acquisition to year-end
            months = 12 - acquired_month + 1
            return monthly * months

        # Check if fully amortized
        months_elapsed = (tax_year - acquired_year) * 12 + (12 - acquired_month + 1)
        if months_elapsed >= self.amortization_period_months:
            return 0.0

        # Full year or partial final year
        remaining_months = self.amortization_period_months - months_elapsed + 12
        if remaining_months < 12:
            return monthly * remaining_months

        return monthly * 12


# =============================================================================
# Form 4562 Main Model
# =============================================================================

class Form4562(BaseModel):
    """
    IRS Form 4562 - Depreciation and Amortization.

    Complete form model with all six parts:
    - Part I: Election to Expense Certain Property (Section 179)
    - Part II: Special Depreciation Allowance (Bonus)
    - Part III: MACRS Depreciation
    - Part IV: Summary
    - Part V: Listed Property
    - Part VI: Amortization
    """

    # Form identification
    tax_year: int = Field(default=2025)
    business_name: str = Field(default="", description="Name of business or activity")
    business_activity: str = Field(default="", description="Business or activity type")

    # Assets
    depreciable_assets: List[DepreciableAsset] = Field(
        default_factory=list,
        description="All depreciable assets"
    )
    amortizable_assets: List[AmortizableAsset] = Field(
        default_factory=list,
        description="All amortizable intangibles"
    )

    # Part I: Section 179
    section_179_limit: float = Field(
        default=Section179Limits.MAX_DEDUCTION,
        description="Maximum Section 179 deduction"
    )
    section_179_threshold: float = Field(
        default=Section179Limits.PHASE_OUT_THRESHOLD,
        description="Phase-out threshold"
    )
    total_section_179_property_cost: float = Field(
        default=0.0,
        description="Total cost of Section 179 property"
    )
    carryover_from_prior_year: float = Field(
        default=0.0,
        description="Section 179 carryover from prior year"
    )

    # Part II: Bonus Depreciation
    bonus_rate: float = Field(
        default=0.40,  # 40% for 2025
        description="Bonus depreciation rate for the year"
    )

    # Part V: Listed Property
    has_listed_property: bool = Field(
        default=False,
        description="Has listed property subject to Section 280F"
    )

    # Computed fields (populated by calculate methods)
    _computed_depreciation: Dict[str, float] = {}

    def add_asset(self, asset: DepreciableAsset) -> None:
        """Add a depreciable asset."""
        self.depreciable_assets.append(asset)
        if asset.is_listed_property:
            self.has_listed_property = True

    def add_amortizable(self, asset: AmortizableAsset) -> None:
        """Add an amortizable asset."""
        self.amortizable_assets.append(asset)

    # =========================================================================
    # Section 179 Calculations (Part I)
    # =========================================================================

    def calculate_section_179_deduction(self, business_income: float = 0.0) -> Dict[str, float]:
        """
        Calculate Section 179 deduction per IRS rules.

        Limits:
        1. Maximum deduction ($1,250,000 for 2025)
        2. Phase-out if total cost > threshold ($3,130,000)
        3. Taxable income limitation
        4. Per-asset limits (SUV limit, etc.)

        Args:
            business_income: Net business income for taxable income limit

        Returns:
            Dictionary with Section 179 breakdown
        """
        result = {
            'total_elected': 0.0,
            'maximum_allowable': self.section_179_limit,
            'phase_out_reduction': 0.0,
            'adjusted_limit': self.section_179_limit,
            'business_income_limit': business_income,
            'allowed_deduction': 0.0,
            'carryover_to_next_year': 0.0,
            'assets': []
        }

        # Calculate total Section 179 property cost
        total_179_cost = sum(
            a.cost_basis for a in self.depreciable_assets
            if a.section_179_elected > 0
        )
        self.total_section_179_property_cost = total_179_cost

        # Phase-out reduction (dollar-for-dollar over threshold)
        if total_179_cost > self.section_179_threshold:
            result['phase_out_reduction'] = total_179_cost - self.section_179_threshold
            result['adjusted_limit'] = max(0, self.section_179_limit - result['phase_out_reduction'])

        # Sum elected amounts (respect per-asset limits)
        total_elected = 0.0
        for asset in self.depreciable_assets:
            if asset.section_179_elected > 0:
                elected = asset.section_179_elected

                # SUV limit check
                if asset.vehicle_is_qualified_suv:
                    elected = min(elected, Section179Limits.SUV_LIMIT)

                # Cannot exceed cost basis
                elected = min(elected, asset.cost_basis * asset.business_use_percentage)

                total_elected += elected
                result['assets'].append({
                    'description': asset.description,
                    'elected': elected,
                    'cost_basis': asset.cost_basis
                })

        result['total_elected'] = total_elected

        # Apply maximum limit
        tentative_deduction = min(
            total_elected + self.carryover_from_prior_year,
            result['adjusted_limit']
        )

        # Apply taxable income limitation
        # Section 179 cannot create or increase a loss
        if business_income > 0:
            result['allowed_deduction'] = min(tentative_deduction, business_income)
            result['carryover_to_next_year'] = tentative_deduction - result['allowed_deduction']
        else:
            result['allowed_deduction'] = 0.0
            result['carryover_to_next_year'] = tentative_deduction

        return result

    # =========================================================================
    # Bonus Depreciation Calculations (Part II)
    # =========================================================================

    def calculate_bonus_depreciation(self) -> Dict[str, float]:
        """
        Calculate bonus depreciation (special depreciation allowance).

        For 2025: 40% bonus depreciation rate

        Eligible property:
        - MACRS property with recovery period ≤ 20 years
        - Qualified improvement property
        - Must be placed in service during the year

        Returns:
            Dictionary with bonus depreciation breakdown
        """
        result = {
            'rate': self.bonus_rate,
            'total_bonus': 0.0,
            'assets': []
        }

        for asset in self.depreciable_assets:
            # Skip if asset opted out or not placed in service this year
            if asset.opted_out_of_bonus:
                continue

            if asset.get_year_placed_in_service() != self.tax_year:
                continue

            # Only new property eligible (used property has different rules)
            # 20-year or less recovery period
            recovery = asset.get_recovery_period()
            if recovery > 20 and asset.property_class not in [
                MACRSPropertyClass.YEAR_27_5,
                MACRSPropertyClass.YEAR_39
            ]:
                continue

            # Real property generally not eligible (except QIP)
            if asset.property_class in [MACRSPropertyClass.YEAR_27_5, MACRSPropertyClass.YEAR_39]:
                continue

            # Calculate bonus basis (cost - Section 179)
            bonus_basis = asset.cost_basis - asset.section_179_elected
            bonus_basis *= asset.business_use_percentage

            # Listed property with <50% business use: no bonus
            if asset.is_listed_property and asset.business_use_percentage <= 0.5:
                continue

            bonus_amount = bonus_basis * self.bonus_rate

            # Vehicle limits (Section 280F)
            if asset.is_vehicle and asset.listed_property_type == ListedPropertyType.PASSENGER_AUTO:
                max_first_year = Section280FLimits.YEAR_1_WITH_BONUS
                bonus_amount = min(bonus_amount, max_first_year - asset.section_179_elected)

            result['total_bonus'] += bonus_amount
            result['assets'].append({
                'description': asset.description,
                'basis': bonus_basis,
                'rate': self.bonus_rate,
                'bonus': bonus_amount
            })

        return result

    # =========================================================================
    # MACRS Depreciation Calculations (Part III)
    # =========================================================================

    def _get_macrs_rate(
        self,
        property_class: MACRSPropertyClass,
        year: int,
        convention: MACRSConvention,
        month_placed: int = 1,
        quarter_placed: int = 1
    ) -> float:
        """
        Get MACRS depreciation rate for a specific year.

        Args:
            property_class: MACRS property class
            year: Year of recovery (1, 2, 3, etc.)
            convention: Averaging convention
            month_placed: Month placed in service (for mid-month)
            quarter_placed: Quarter placed in service (for mid-quarter)

        Returns:
            Depreciation rate as decimal
        """
        recovery = int(float(property_class.value))

        # Mid-month convention for real property
        if convention == MACRSConvention.MID_MONTH:
            if property_class == MACRSPropertyClass.YEAR_27_5:
                if year == 1:
                    return MACRS_SL_MM_27_5.get(month_placed, 0.03636)
                elif year <= 28:
                    return 0.03636
                elif year == 29:
                    return 0.03636 - MACRS_SL_MM_27_5.get(month_placed, 0.03636)
                return 0.0

            elif property_class == MACRSPropertyClass.YEAR_39:
                if year == 1:
                    return MACRS_SL_MM_39.get(month_placed, 0.02564)
                elif year <= 39:
                    return 0.02564
                elif year == 40:
                    return 0.02564 - MACRS_SL_MM_39.get(month_placed, 0.02564)
                return 0.0

        # Mid-quarter convention
        if convention == MACRSConvention.MID_QUARTER:
            if recovery in MACRS_200DB_MQ and quarter_placed in MACRS_200DB_MQ[recovery]:
                rates = MACRS_200DB_MQ[recovery][quarter_placed]
                if year <= len(rates):
                    return rates[year - 1]
                return 0.0

        # Half-year convention (default)
        if recovery in MACRS_200DB_HY:
            rates = MACRS_200DB_HY[recovery]
            if year <= len(rates):
                return rates[year - 1]
            return 0.0

        if recovery in MACRS_150DB_HY:
            rates = MACRS_150DB_HY[recovery]
            if year <= len(rates):
                return rates[year - 1]
            return 0.0

        # Straight-line fallback
        return 1.0 / recovery if year <= recovery else 0.0

    def calculate_macrs_depreciation(self, asset: DepreciableAsset) -> float:
        """
        Calculate current year MACRS depreciation for an asset.

        Args:
            asset: Depreciable asset

        Returns:
            Current year MACRS depreciation amount
        """
        # C1: BLOCKING ERROR - Asset disposed this year
        # Per IRS Pub 946, disposition year requires partial depreciation based on convention.
        # Full implementation requires: mid-quarter vs half-year proration, Section 1245/1250
        # recapture calculations, and Form 4797 integration.
        #
        # CRITICAL: We RAISE an exception here, not return 0.
        # Returning 0 could be mistaken for "handled" - this is a CPA reliance risk.
        # The calculation HALTS and requires explicit manual intervention.
        if asset.disposed_this_year:
            error_msg = (
                f"DISPOSITION REQUIRES MANUAL REVIEW - CALCULATION BLOCKED: "
                f"Asset '{asset.description}' (cost basis ${asset.cost_basis:,.2f}) "
                f"was disposed in tax year {self.tax_year}. "
                f"Disposition-year depreciation is NOT calculated by this system. "
                f"CPA must manually: (1) calculate partial-year depreciation per convention, "
                f"(2) complete Form 4797, (3) determine Section 1245/1250 recapture. "
                f"See IRS Publication 946."
            )
            logger.error(error_msg)
            raise DispositionRequiresManualReviewError(error_msg)

        # Skip if fully depreciated
        if asset.is_fully_depreciated():
            return 0.0

        # Get depreciable basis (after 179 and bonus)
        basis = asset.get_depreciable_basis()
        if basis <= 0:
            return 0.0

        # Apply business use percentage
        basis *= asset.business_use_percentage

        # Get year of service
        year_in_service = asset.get_year_in_service(self.tax_year)
        if year_in_service < 1:
            return 0.0

        # Get MACRS rate
        rate = self._get_macrs_rate(
            property_class=asset.property_class,
            year=year_in_service,
            convention=asset.convention,
            month_placed=asset.get_month_placed_in_service(),
            quarter_placed=asset.get_quarter_placed_in_service()
        )

        depreciation = basis * rate

        # Listed property limitations
        if asset.is_listed_property and asset.is_vehicle:
            if asset.listed_property_type == ListedPropertyType.PASSENGER_AUTO:
                # Apply Section 280F limits
                if year_in_service == 1:
                    max_dep = Section280FLimits.YEAR_1_WITHOUT_BONUS
                elif year_in_service == 2:
                    max_dep = Section280FLimits.YEAR_2
                elif year_in_service == 3:
                    max_dep = Section280FLimits.YEAR_3
                else:
                    max_dep = Section280FLimits.YEAR_4_PLUS

                depreciation = min(depreciation, max_dep)

        return float(money(depreciation))

    def calculate_all_macrs_depreciation(self) -> Dict[str, Any]:
        """
        Calculate MACRS depreciation for all assets.

        Returns:
            Dictionary with depreciation breakdown by asset and category
        """
        result = {
            'total_depreciation': 0.0,
            'by_property_class': {},
            'assets': []
        }

        for asset in self.depreciable_assets:
            depreciation = self.calculate_macrs_depreciation(asset)

            result['total_depreciation'] += depreciation

            # Group by property class
            pc = asset.property_class.value
            if pc not in result['by_property_class']:
                result['by_property_class'][pc] = 0.0
            result['by_property_class'][pc] += depreciation

            result['assets'].append({
                'description': asset.description,
                'property_class': asset.property_class.value,
                'basis': asset.get_depreciable_basis(),
                'year_in_service': asset.get_year_in_service(self.tax_year),
                'depreciation': depreciation
            })

        return result

    # =========================================================================
    # Amortization Calculations (Part VI)
    # =========================================================================

    def calculate_amortization(self) -> Dict[str, Any]:
        """
        Calculate amortization for all intangible assets.

        Returns:
            Dictionary with amortization breakdown
        """
        result = {
            'total_amortization': 0.0,
            'by_type': {},
            'assets': []
        }

        for asset in self.amortizable_assets:
            amortization = asset.get_annual_amortization(self.tax_year)

            result['total_amortization'] += amortization

            # Group by type
            atype = asset.amortization_type.value
            if atype not in result['by_type']:
                result['by_type'][atype] = 0.0
            result['by_type'][atype] += amortization

            result['assets'].append({
                'description': asset.description,
                'type': asset.amortization_type.value,
                'code_section': asset.code_section,
                'cost': asset.cost_basis,
                'period_months': asset.amortization_period_months,
                'amortization': amortization
            })

        return result

    # =========================================================================
    # Complete Form Calculation (Part IV Summary)
    # =========================================================================

    def calculate(self, business_income: float = 0.0) -> Dict[str, Any]:
        """
        Calculate complete Form 4562 depreciation and amortization.

        Args:
            business_income: Net business income for Section 179 limit

        Returns:
            Complete form breakdown with all parts
        """
        # Update bonus rate for tax year
        self.bonus_rate = BonusDepreciationRates.get_rate(self.tax_year)

        # Part I: Section 179
        section_179 = self.calculate_section_179_deduction(business_income)

        # Part II: Bonus Depreciation
        bonus = self.calculate_bonus_depreciation()

        # Part III: MACRS Depreciation
        macrs = self.calculate_all_macrs_depreciation()

        # Part VI: Amortization
        amortization = self.calculate_amortization()

        # Part IV: Summary
        total_depreciation = (
            section_179['allowed_deduction'] +
            bonus['total_bonus'] +
            macrs['total_depreciation']
        )

        total_deduction = total_depreciation + amortization['total_amortization']

        return {
            'tax_year': self.tax_year,
            'business_name': self.business_name,

            # Part I: Section 179
            'part_i_section_179': section_179,

            # Part II: Bonus Depreciation
            'part_ii_bonus_depreciation': bonus,

            # Part III: MACRS Depreciation
            'part_iii_macrs': macrs,

            # Part IV: Summary
            'part_iv_summary': {
                'section_179_deduction': section_179['allowed_deduction'],
                'bonus_depreciation': bonus['total_bonus'],
                'macrs_depreciation': macrs['total_depreciation'],
                'total_depreciation': total_depreciation,
                'section_179_carryover': section_179['carryover_to_next_year'],
            },

            # Part V: Listed Property
            'part_v_listed_property': {
                'has_listed_property': self.has_listed_property,
                'assets': [a for a in self.depreciable_assets if a.is_listed_property]
            },

            # Part VI: Amortization
            'part_vi_amortization': amortization,

            # Totals
            'total_depreciation': total_depreciation,
            'total_amortization': amortization['total_amortization'],
            'total_deduction': total_deduction,
        }

    # =========================================================================
    # Mid-Quarter Convention Detection
    # =========================================================================

    def check_mid_quarter_convention(self) -> Tuple[bool, Dict[str, float]]:
        """
        Determine if mid-quarter convention must be used.

        Rule: If more than 40% of depreciable property (by basis) is placed
        in service during the last 3 months (Q4), mid-quarter convention
        applies to ALL property placed in service during the year.

        Excludes: Real property (27.5 and 39 year)

        Returns:
            Tuple of (must_use_mid_quarter, quarterly_breakdown)
        """
        quarterly_totals = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        total_basis = 0.0

        for asset in self.depreciable_assets:
            # Only current year placements
            if asset.get_year_placed_in_service() != self.tax_year:
                continue

            # Exclude real property
            if asset.property_class in [MACRSPropertyClass.YEAR_27_5, MACRSPropertyClass.YEAR_39]:
                continue

            quarter = asset.get_quarter_placed_in_service()
            basis = asset.cost_basis - asset.section_179_elected

            quarterly_totals[quarter] += basis
            total_basis += basis

        if total_basis == 0:
            return False, quarterly_totals

        q4_percentage = quarterly_totals[4] / total_basis
        must_use_mq = q4_percentage > 0.40

        return must_use_mq, quarterly_totals


# =============================================================================
# Depreciation Calculator (Engine Integration)
# =============================================================================

class DepreciationCalculator:
    """
    Standalone depreciation calculator for use with tax engine.
    """

    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year
        self.bonus_rate = BonusDepreciationRates.get_rate(tax_year)

    def calculate_single_asset_depreciation(
        self,
        cost_basis: float,
        property_class: MACRSPropertyClass,
        date_placed_in_service: str,
        section_179: float = 0.0,
        bonus_depreciation: float = 0.0,
        opted_out_bonus: bool = False,
        business_use_pct: float = 1.0,
        convention: MACRSConvention = MACRSConvention.HALF_YEAR,
        prior_depreciation: float = 0.0,
        is_listed_property: bool = False,
        is_vehicle: bool = False
    ) -> Dict[str, float]:
        """
        Calculate depreciation for a single asset.

        Returns complete breakdown of all depreciation components.
        """
        result = {
            'cost_basis': cost_basis,
            'section_179': 0.0,
            'bonus_depreciation': 0.0,
            'macrs_depreciation': 0.0,
            'total_current_year': 0.0,
            'accumulated_depreciation': prior_depreciation,
            'remaining_basis': 0.0
        }

        # Apply business use percentage
        depreciable_cost = cost_basis * business_use_pct

        # Section 179 (limited to depreciable cost)
        result['section_179'] = min(section_179, depreciable_cost)

        # Bonus depreciation (on remaining basis)
        if not opted_out_bonus and bonus_depreciation > 0:
            bonus_basis = depreciable_cost - result['section_179']
            result['bonus_depreciation'] = min(bonus_depreciation, bonus_basis * self.bonus_rate)

        # MACRS basis
        macrs_basis = depreciable_cost - result['section_179'] - result['bonus_depreciation']

        if macrs_basis > 0:
            # Create temporary asset for calculation
            asset = DepreciableAsset(
                description="temp",
                date_placed_in_service=date_placed_in_service,
                cost_basis=macrs_basis / business_use_pct if business_use_pct > 0 else 0,
                property_class=property_class,
                convention=convention,
                business_use_percentage=business_use_pct,
                prior_depreciation=prior_depreciation,
                is_listed_property=is_listed_property,
                is_vehicle=is_vehicle
            )

            form = Form4562(tax_year=self.tax_year)
            result['macrs_depreciation'] = form.calculate_macrs_depreciation(asset)

        result['total_current_year'] = (
            result['section_179'] +
            result['bonus_depreciation'] +
            result['macrs_depreciation']
        )

        result['accumulated_depreciation'] = prior_depreciation + result['total_current_year']
        result['remaining_basis'] = depreciable_cost - result['accumulated_depreciation']

        return result
