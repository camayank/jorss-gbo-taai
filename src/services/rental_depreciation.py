"""
Rental Property Depreciation Service

Provides simplified depreciation calculation for residential and commercial
rental properties using MACRS straight-line depreciation.

Key Rules:
- Residential Rental (27.5 years): Mid-month convention, straight-line
- Commercial Property (39 years): Mid-month convention, straight-line
- Land is NOT depreciable - must be separated from building cost
- Improvements may have different recovery periods
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal, ROUND_HALF_UP
import uuid
from calculator.decimal_math import money, to_decimal


class PropertyType(str, Enum):
    """Types of depreciable rental property."""
    RESIDENTIAL_RENTAL = "residential_rental"  # 27.5 years
    COMMERCIAL = "commercial"  # 39 years
    IMPROVEMENT = "improvement"  # Varies by type


class DepreciationMethod(str, Enum):
    """Depreciation methods."""
    STRAIGHT_LINE = "straight_line"
    MACRS_GDS = "macrs_gds"  # General Depreciation System


# MACRS Mid-Month Convention Rates for First Year
# Based on month property is placed in service
RESIDENTIAL_FIRST_YEAR_RATES = {
    # Month: First year rate (out of 3.636% annual rate)
    1: 3.485,   # January
    2: 3.182,   # February
    3: 2.879,   # March
    4: 2.576,   # April
    5: 2.273,   # May
    6: 1.970,   # June
    7: 1.667,   # July
    8: 1.364,   # August
    9: 1.061,   # September
    10: 0.758,  # October
    11: 0.455,  # November
    12: 0.152,  # December
}

COMMERCIAL_FIRST_YEAR_RATES = {
    # Month: First year rate (out of 2.564% annual rate)
    1: 2.461,
    2: 2.247,
    3: 2.033,
    4: 1.819,
    5: 1.605,
    6: 1.391,
    7: 1.177,
    8: 0.963,
    9: 0.749,
    10: 0.535,
    11: 0.321,
    12: 0.107,
}


@dataclass
class RentalAsset:
    """A depreciable asset for a rental property."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    property_id: str = ""  # Links to rental property
    description: str = ""
    asset_type: PropertyType = PropertyType.RESIDENTIAL_RENTAL

    # Cost basis
    cost_basis: float = 0.0
    land_value: float = 0.0  # Not depreciable

    @property
    def depreciable_basis(self) -> float:
        """Cost basis less land value."""
        return max(0, self.cost_basis - self.land_value)

    # Service dates
    date_placed_in_service: Optional[date] = None
    date_disposed: Optional[date] = None

    # Recovery period (years)
    recovery_period: int = 275  # 27.5 years (stored as int for precision)

    # Accumulated depreciation from prior years
    prior_depreciation: float = 0.0

    # Current year
    current_year_depreciation: float = 0.0

    @property
    def adjusted_basis(self) -> float:
        """Cost basis less all depreciation taken."""
        return max(0, self.depreciable_basis - self.prior_depreciation - self.current_year_depreciation)

    # Business use percentage (for mixed-use properties)
    business_use_percentage: float = 100.0

    # Metadata
    notes: Optional[str] = None

    def get_recovery_period_years(self) -> float:
        """Get recovery period in years."""
        if self.asset_type == PropertyType.RESIDENTIAL_RENTAL:
            return 27.5
        elif self.asset_type == PropertyType.COMMERCIAL:
            return 39.0
        else:
            return self.recovery_period / 10.0  # Stored as int * 10


@dataclass
class DepreciationScheduleEntry:
    """A single year's depreciation entry."""
    year: int
    beginning_basis: float
    depreciation_amount: float
    ending_basis: float
    cumulative_depreciation: float
    rate_applied: float  # Percentage rate
    is_first_year: bool = False
    is_last_year: bool = False
    months_in_service: int = 12


class RentalDepreciationCalculator:
    """
    Calculates depreciation for rental properties using MACRS straight-line.

    Supports:
    - Residential rental (27.5 years, mid-month convention)
    - Commercial property (39 years, mid-month convention)
    - Property improvements (various periods)
    """

    @staticmethod
    def calculate_annual_depreciation(
        cost_basis: float,
        land_value: float,
        property_type: PropertyType,
        date_placed_in_service: date,
        tax_year: int,
        prior_depreciation: float = 0,
        business_use_percentage: float = 100.0
    ) -> Dict[str, Any]:
        """
        Calculate depreciation for a specific tax year.

        Args:
            cost_basis: Total cost of property (including land)
            land_value: Value of land (not depreciable)
            property_type: RESIDENTIAL_RENTAL or COMMERCIAL
            date_placed_in_service: Date property placed in service
            tax_year: Year to calculate depreciation for
            prior_depreciation: Total depreciation taken in prior years
            business_use_percentage: Percentage used for rental (0-100)

        Returns:
            Dict with depreciation amount and supporting details
        """
        # Calculate depreciable basis
        depreciable_basis = max(0, cost_basis - land_value)

        if depreciable_basis <= 0:
            return {
                "depreciation_amount": 0,
                "depreciable_basis": 0,
                "message": "No depreciable basis (land value equals or exceeds cost)"
            }

        # Determine recovery period
        if property_type == PropertyType.RESIDENTIAL_RENTAL:
            recovery_years = 27.5
            annual_rate = 100 / 27.5  # 3.636%
            first_year_rates = RESIDENTIAL_FIRST_YEAR_RATES
        elif property_type == PropertyType.COMMERCIAL:
            recovery_years = 39.0
            annual_rate = 100 / 39.0  # 2.564%
            first_year_rates = COMMERCIAL_FIRST_YEAR_RATES
        else:
            # Default to residential
            recovery_years = 27.5
            annual_rate = 100 / 27.5
            first_year_rates = RESIDENTIAL_FIRST_YEAR_RATES

        # Calculate year in service
        service_year = date_placed_in_service.year
        years_in_service = tax_year - service_year + 1

        if years_in_service < 1:
            return {
                "depreciation_amount": 0,
                "message": "Property not yet in service for this tax year"
            }

        # Check if fully depreciated
        max_recovery_years = int(recovery_years) + 1  # Extra year due to mid-month
        if years_in_service > max_recovery_years:
            return {
                "depreciation_amount": 0,
                "message": "Property fully depreciated",
                "total_depreciation": depreciable_basis
            }

        # Calculate depreciation
        if years_in_service == 1:
            # First year - use mid-month convention
            month_placed = date_placed_in_service.month
            rate = first_year_rates.get(month_placed, annual_rate)
            depreciation = depreciable_basis * (rate / 100)
        elif years_in_service <= int(recovery_years):
            # Full year depreciation
            depreciation = depreciable_basis * (annual_rate / 100)
        else:
            # Final year - remaining depreciation
            # Calculate what should remain
            total_should_be = depreciable_basis
            already_taken = prior_depreciation
            remaining = max(0, total_should_be - already_taken)

            # Final year gets whatever is left (prorated)
            depreciation = min(remaining, depreciable_basis * (annual_rate / 100))

        # Apply business use percentage
        depreciation = depreciation * (business_use_percentage / 100)

        # Round to cents
        depreciation = float(money(depreciation))

        # Check against remaining basis
        remaining_basis = depreciable_basis - prior_depreciation
        depreciation = min(depreciation, remaining_basis)

        return {
            "depreciation_amount": depreciation,
            "depreciable_basis": depreciable_basis,
            "land_value": land_value,
            "property_type": property_type.value,
            "recovery_period_years": recovery_years,
            "year_in_service": years_in_service,
            "annual_rate_percent": round(annual_rate, 3),
            "rate_applied_percent": round((depreciation / depreciable_basis) * 100, 3) if depreciable_basis > 0 else 0,
            "prior_depreciation": prior_depreciation,
            "remaining_basis_before": remaining_basis,
            "remaining_basis_after": remaining_basis - depreciation,
            "business_use_percent": business_use_percentage,
            "is_first_year": years_in_service == 1,
            "is_fully_depreciated": (remaining_basis - depreciation) <= 0.01
        }

    @staticmethod
    def generate_depreciation_schedule(
        cost_basis: float,
        land_value: float,
        property_type: PropertyType,
        date_placed_in_service: date,
        business_use_percentage: float = 100.0
    ) -> List[DepreciationScheduleEntry]:
        """
        Generate complete depreciation schedule for the life of the asset.

        Returns a list of yearly depreciation entries.
        """
        depreciable_basis = max(0, cost_basis - land_value)

        if depreciable_basis <= 0:
            return []

        # Determine recovery period
        if property_type == PropertyType.RESIDENTIAL_RENTAL:
            recovery_years = 27.5
            max_years = 29  # 27.5 + partial year + potential final partial
        else:
            recovery_years = 39.0
            max_years = 41

        schedule = []
        cumulative = 0.0
        year = date_placed_in_service.year

        for i in range(int(max_years)):
            tax_year = year + i

            result = RentalDepreciationCalculator.calculate_annual_depreciation(
                cost_basis=cost_basis,
                land_value=land_value,
                property_type=property_type,
                date_placed_in_service=date_placed_in_service,
                tax_year=tax_year,
                prior_depreciation=cumulative,
                business_use_percentage=business_use_percentage
            )

            depreciation = result["depreciation_amount"]

            if depreciation <= 0 and cumulative >= depreciable_basis * (business_use_percentage / 100) - 0.01:
                break  # Fully depreciated

            entry = DepreciationScheduleEntry(
                year=tax_year,
                beginning_basis=depreciable_basis - cumulative,
                depreciation_amount=depreciation,
                ending_basis=depreciable_basis - cumulative - depreciation,
                cumulative_depreciation=cumulative + depreciation,
                rate_applied=result.get("rate_applied_percent", 0),
                is_first_year=(i == 0),
                is_last_year=result.get("is_fully_depreciated", False)
            )
            schedule.append(entry)

            cumulative += depreciation

            if result.get("is_fully_depreciated", False):
                break

        return schedule

    @staticmethod
    def calculate_property_depreciation(asset: RentalAsset, tax_year: int) -> Dict[str, Any]:
        """
        Calculate depreciation for a RentalAsset.

        Updates the asset's current_year_depreciation field and returns details.
        """
        if not asset.date_placed_in_service:
            return {
                "error": "Date placed in service is required",
                "depreciation_amount": 0
            }

        result = RentalDepreciationCalculator.calculate_annual_depreciation(
            cost_basis=asset.cost_basis,
            land_value=asset.land_value,
            property_type=asset.asset_type,
            date_placed_in_service=asset.date_placed_in_service,
            tax_year=tax_year,
            prior_depreciation=asset.prior_depreciation,
            business_use_percentage=asset.business_use_percentage
        )

        # Update asset
        asset.current_year_depreciation = result.get("depreciation_amount", 0)

        return result


@dataclass
class RentalPropertyDepreciation:
    """
    Container for all depreciable assets associated with a rental property.
    """
    property_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    property_address: str = ""
    property_type: PropertyType = PropertyType.RESIDENTIAL_RENTAL

    # Assets
    building: Optional[RentalAsset] = None
    improvements: List[RentalAsset] = field(default_factory=list)

    # Totals (calculated)
    total_current_year_depreciation: float = 0.0
    total_prior_depreciation: float = 0.0
    total_adjusted_basis: float = 0.0

    def add_building(
        self,
        cost_basis: float,
        land_value: float,
        date_placed_in_service: date,
        business_use_percentage: float = 100.0,
        prior_depreciation: float = 0
    ) -> RentalAsset:
        """Add the main building asset."""
        self.building = RentalAsset(
            property_id=self.property_id,
            description=f"Building - {self.property_address}",
            asset_type=self.property_type,
            cost_basis=cost_basis,
            land_value=land_value,
            date_placed_in_service=date_placed_in_service,
            business_use_percentage=business_use_percentage,
            prior_depreciation=prior_depreciation
        )
        return self.building

    def add_improvement(
        self,
        description: str,
        cost_basis: float,
        date_placed_in_service: date,
        recovery_period_years: float = 27.5,
        business_use_percentage: float = 100.0,
        prior_depreciation: float = 0
    ) -> RentalAsset:
        """Add an improvement (roof, HVAC, etc.)."""
        # Determine asset type based on recovery period
        if recovery_period_years == 27.5:
            asset_type = PropertyType.RESIDENTIAL_RENTAL
        elif recovery_period_years == 39:
            asset_type = PropertyType.COMMERCIAL
        else:
            asset_type = PropertyType.IMPROVEMENT

        improvement = RentalAsset(
            property_id=self.property_id,
            description=description,
            asset_type=asset_type,
            cost_basis=cost_basis,
            land_value=0,  # Improvements don't include land
            date_placed_in_service=date_placed_in_service,
            recovery_period=int(recovery_period_years * 10),
            business_use_percentage=business_use_percentage,
            prior_depreciation=prior_depreciation
        )
        self.improvements.append(improvement)
        return improvement

    def calculate_all_depreciation(self, tax_year: int) -> Dict[str, Any]:
        """
        Calculate depreciation for all assets for a tax year.

        Returns summary with breakdowns by asset.
        """
        total_depreciation = 0.0
        asset_details = []

        # Calculate building depreciation
        if self.building:
            result = RentalDepreciationCalculator.calculate_property_depreciation(
                self.building, tax_year
            )
            total_depreciation += result.get("depreciation_amount", 0)
            asset_details.append({
                "asset_id": self.building.id,
                "description": self.building.description,
                "depreciation": result.get("depreciation_amount", 0),
                "details": result
            })

        # Calculate improvement depreciation
        for improvement in self.improvements:
            result = RentalDepreciationCalculator.calculate_property_depreciation(
                improvement, tax_year
            )
            total_depreciation += result.get("depreciation_amount", 0)
            asset_details.append({
                "asset_id": improvement.id,
                "description": improvement.description,
                "depreciation": result.get("depreciation_amount", 0),
                "details": result
            })

        # Update totals
        self.total_current_year_depreciation = total_depreciation
        self.total_prior_depreciation = (
            (self.building.prior_depreciation if self.building else 0) +
            sum(imp.prior_depreciation for imp in self.improvements)
        )
        self.total_adjusted_basis = (
            (self.building.adjusted_basis if self.building else 0) +
            sum(imp.adjusted_basis for imp in self.improvements)
        )

        return {
            "property_id": self.property_id,
            "property_address": self.property_address,
            "tax_year": tax_year,
            "total_depreciation": float(money(total_depreciation)),
            "total_prior_depreciation": float(money(self.total_prior_depreciation)),
            "total_adjusted_basis": float(money(self.total_adjusted_basis)),
            "asset_count": len(asset_details),
            "assets": asset_details
        }

    def to_schedule_e_depreciation(self, tax_year: int) -> float:
        """
        Get total depreciation amount for Schedule E line 18.

        Returns the depreciation expense to report on Schedule E.
        """
        result = self.calculate_all_depreciation(tax_year)
        return result["total_depreciation"]
