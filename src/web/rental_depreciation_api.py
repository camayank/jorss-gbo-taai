"""
Rental Property Depreciation API

REST API endpoints for calculating and managing rental property depreciation
using MACRS straight-line depreciation.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
import logging

# Import rental depreciation service
try:
    from services.rental_depreciation import (
        RentalDepreciationCalculator,
        RentalPropertyDepreciation,
        RentalAsset,
        PropertyType,
        DepreciationScheduleEntry
    )
    DEPRECIATION_AVAILABLE = True
except ImportError:
    DEPRECIATION_AVAILABLE = False

# Import audit logger
try:
    from audit.audit_logger import audit_depreciation, get_audit_logger
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rental-depreciation", tags=["Rental Property Depreciation"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class DepreciationCalculationInput(BaseModel):
    """Input for a one-time depreciation calculation."""
    cost_basis: float = Field(..., gt=0, description="Total cost of property including land")
    land_value: float = Field(default=0, ge=0, description="Value of land (not depreciable)")
    property_type: str = Field(default="residential_rental", description="residential_rental or commercial")
    date_placed_in_service: str = Field(..., description="Date placed in service (YYYY-MM-DD)")
    tax_year: int = Field(..., description="Tax year to calculate depreciation for")
    prior_depreciation: float = Field(default=0, ge=0, description="Total depreciation from prior years")
    business_use_percentage: float = Field(default=100.0, ge=0, le=100)


class DepreciationCalculationResponse(BaseModel):
    """Response for depreciation calculation."""
    depreciation_amount: float
    depreciable_basis: float
    land_value: float
    property_type: str
    recovery_period_years: float
    year_in_service: int
    annual_rate_percent: float
    rate_applied_percent: float
    prior_depreciation: float
    remaining_basis_after: float
    is_first_year: bool
    is_fully_depreciated: bool


class PropertyInput(BaseModel):
    """Input for creating a rental property with depreciation tracking."""
    property_address: str = Field(..., description="Property address")
    property_type: str = Field(default="residential_rental", description="residential_rental or commercial")

    # Building info
    building_cost: float = Field(..., gt=0, description="Total cost of building")
    land_value: float = Field(default=0, ge=0, description="Land value (not depreciable)")
    date_placed_in_service: str = Field(..., description="Date placed in service (YYYY-MM-DD)")
    prior_depreciation: float = Field(default=0, ge=0, description="Prior depreciation taken")
    business_use_percentage: float = Field(default=100.0, ge=0, le=100)


class ImprovementInput(BaseModel):
    """Input for adding an improvement to a property."""
    description: str = Field(..., description="Description of improvement")
    cost_basis: float = Field(..., gt=0, description="Cost of improvement")
    date_placed_in_service: str = Field(..., description="Date improvement placed in service (YYYY-MM-DD)")
    recovery_period_years: float = Field(default=27.5, description="Recovery period (27.5 residential, 39 commercial)")
    prior_depreciation: float = Field(default=0, ge=0)
    business_use_percentage: float = Field(default=100.0, ge=0, le=100)


class ScheduleEntryResponse(BaseModel):
    """Response for a single schedule entry."""
    year: int
    beginning_basis: float
    depreciation_amount: float
    ending_basis: float
    cumulative_depreciation: float
    rate_applied: float
    is_first_year: bool
    is_last_year: bool


class PropertySummaryResponse(BaseModel):
    """Summary response for a rental property's depreciation."""
    property_id: str
    property_address: str
    tax_year: int
    total_depreciation: float
    total_prior_depreciation: float
    total_adjusted_basis: float
    asset_count: int
    assets: List[Dict[str, Any]]


# =============================================================================
# IN-MEMORY STORAGE (replace with database in production)
# =============================================================================

# Session-based property storage
_properties: Dict[str, Dict[str, RentalPropertyDepreciation]] = {}


def get_or_create_properties(session_id: str) -> Dict[str, RentalPropertyDepreciation]:
    """Get or create property storage for a session."""
    if session_id not in _properties:
        _properties[session_id] = {}
    return _properties[session_id]


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/calculate", response_model=DepreciationCalculationResponse)
async def calculate_depreciation(input_data: DepreciationCalculationInput):
    """
    Calculate depreciation for a rental property for a specific tax year.

    Uses MACRS straight-line depreciation with mid-month convention:
    - Residential rental: 27.5 years
    - Commercial: 39 years
    """
    if not DEPRECIATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Depreciation service not available")

    try:
        # Parse date
        try:
            placed_date = datetime.strptime(input_data.date_placed_in_service, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Map property type
        prop_type = PropertyType.RESIDENTIAL_RENTAL
        if input_data.property_type.lower() == "commercial":
            prop_type = PropertyType.COMMERCIAL

        # Calculate
        result = RentalDepreciationCalculator.calculate_annual_depreciation(
            cost_basis=input_data.cost_basis,
            land_value=input_data.land_value,
            property_type=prop_type,
            date_placed_in_service=placed_date,
            tax_year=input_data.tax_year,
            prior_depreciation=input_data.prior_depreciation,
            business_use_percentage=input_data.business_use_percentage
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return DepreciationCalculationResponse(
            depreciation_amount=result["depreciation_amount"],
            depreciable_basis=result["depreciable_basis"],
            land_value=result["land_value"],
            property_type=result["property_type"],
            recovery_period_years=result["recovery_period_years"],
            year_in_service=result["year_in_service"],
            annual_rate_percent=result["annual_rate_percent"],
            rate_applied_percent=result["rate_applied_percent"],
            prior_depreciation=result["prior_depreciation"],
            remaining_basis_after=result["remaining_basis_after"],
            is_first_year=result["is_first_year"],
            is_fully_depreciated=result["is_fully_depreciated"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating depreciation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule", response_model=List[ScheduleEntryResponse])
async def generate_depreciation_schedule(
    cost_basis: float = Body(..., gt=0),
    land_value: float = Body(default=0, ge=0),
    property_type: str = Body(default="residential_rental"),
    date_placed_in_service: str = Body(...),
    business_use_percentage: float = Body(default=100.0)
):
    """
    Generate complete depreciation schedule for a property.

    Returns year-by-year depreciation over the recovery period.
    """
    if not DEPRECIATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Depreciation service not available")

    try:
        # Parse date
        try:
            placed_date = datetime.strptime(date_placed_in_service, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Map property type
        prop_type = PropertyType.RESIDENTIAL_RENTAL
        if property_type.lower() == "commercial":
            prop_type = PropertyType.COMMERCIAL

        # Generate schedule
        schedule = RentalDepreciationCalculator.generate_depreciation_schedule(
            cost_basis=cost_basis,
            land_value=land_value,
            property_type=prop_type,
            date_placed_in_service=placed_date,
            business_use_percentage=business_use_percentage
        )

        return [
            ScheduleEntryResponse(
                year=entry.year,
                beginning_basis=round(entry.beginning_basis, 2),
                depreciation_amount=round(entry.depreciation_amount, 2),
                ending_basis=round(entry.ending_basis, 2),
                cumulative_depreciation=round(entry.cumulative_depreciation, 2),
                rate_applied=round(entry.rate_applied, 3),
                is_first_year=entry.is_first_year,
                is_last_year=entry.is_last_year
            )
            for entry in schedule
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/property", response_model=PropertySummaryResponse)
async def create_rental_property(
    session_id: str,
    property_data: PropertyInput,
    tax_year: int = Query(..., description="Tax year for depreciation calculation")
):
    """
    Create a rental property with depreciation tracking.

    The property is associated with the session and its depreciation
    can be retrieved for Schedule E reporting.
    """
    if not DEPRECIATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Depreciation service not available")

    try:
        # Parse date
        try:
            placed_date = datetime.strptime(property_data.date_placed_in_service, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Map property type
        prop_type = PropertyType.RESIDENTIAL_RENTAL
        if property_data.property_type.lower() == "commercial":
            prop_type = PropertyType.COMMERCIAL

        # Create property
        rental_prop = RentalPropertyDepreciation(
            property_address=property_data.property_address,
            property_type=prop_type
        )

        # Add building
        rental_prop.add_building(
            cost_basis=property_data.building_cost,
            land_value=property_data.land_value,
            date_placed_in_service=placed_date,
            business_use_percentage=property_data.business_use_percentage,
            prior_depreciation=property_data.prior_depreciation
        )

        # Store property
        properties = get_or_create_properties(session_id)
        properties[rental_prop.property_id] = rental_prop

        # Calculate depreciation
        result = rental_prop.calculate_all_depreciation(tax_year)

        # Audit log
        if AUDIT_AVAILABLE:
            audit_depreciation(
                session_id=session_id,
                asset_id=rental_prop.property_id,
                action="add",
                asset_data={
                    "address": property_data.property_address,
                    "cost": property_data.building_cost,
                    "land": property_data.land_value,
                    "type": property_data.property_type
                },
                depreciation_amount=result["total_depreciation"]
            )

        return PropertySummaryResponse(
            property_id=result["property_id"],
            property_address=result["property_address"],
            tax_year=result["tax_year"],
            total_depreciation=result["total_depreciation"],
            total_prior_depreciation=result["total_prior_depreciation"],
            total_adjusted_basis=result["total_adjusted_basis"],
            asset_count=result["asset_count"],
            assets=result["assets"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating property: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/property/{property_id}/improvement")
async def add_improvement(
    session_id: str,
    property_id: str,
    improvement: ImprovementInput,
    tax_year: int = Query(..., description="Tax year for depreciation calculation")
):
    """
    Add an improvement to an existing rental property.

    Improvements (roof, HVAC, etc.) can have different recovery periods
    than the main building.
    """
    if not DEPRECIATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Depreciation service not available")

    properties = get_or_create_properties(session_id)

    if property_id not in properties:
        raise HTTPException(status_code=404, detail="Property not found")

    rental_prop = properties[property_id]

    try:
        # Parse date
        try:
            placed_date = datetime.strptime(improvement.date_placed_in_service, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Add improvement
        rental_prop.add_improvement(
            description=improvement.description,
            cost_basis=improvement.cost_basis,
            date_placed_in_service=placed_date,
            recovery_period_years=improvement.recovery_period_years,
            business_use_percentage=improvement.business_use_percentage,
            prior_depreciation=improvement.prior_depreciation
        )

        # Recalculate
        result = rental_prop.calculate_all_depreciation(tax_year)

        return {
            "status": "improvement_added",
            "property_id": property_id,
            "improvement_count": len(rental_prop.improvements),
            "total_depreciation": result["total_depreciation"],
            "assets": result["assets"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding improvement: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/properties", response_model=List[PropertySummaryResponse])
async def get_all_properties(
    session_id: str,
    tax_year: int = Query(..., description="Tax year for depreciation calculation")
):
    """
    Get all rental properties for a session with their depreciation.
    """
    if not DEPRECIATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Depreciation service not available")

    properties = get_or_create_properties(session_id)

    results = []
    for rental_prop in properties.values():
        result = rental_prop.calculate_all_depreciation(tax_year)
        results.append(PropertySummaryResponse(
            property_id=result["property_id"],
            property_address=result["property_address"],
            tax_year=result["tax_year"],
            total_depreciation=result["total_depreciation"],
            total_prior_depreciation=result["total_prior_depreciation"],
            total_adjusted_basis=result["total_adjusted_basis"],
            asset_count=result["asset_count"],
            assets=result["assets"]
        ))

    return results


@router.get("/session/{session_id}/total-depreciation")
async def get_total_depreciation(
    session_id: str,
    tax_year: int = Query(..., description="Tax year for depreciation calculation")
):
    """
    Get total depreciation for all rental properties in a session.

    This amount goes on Schedule E line 18.
    """
    if not DEPRECIATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Depreciation service not available")

    properties = get_or_create_properties(session_id)

    total = 0.0
    property_breakdowns = []

    for rental_prop in properties.values():
        result = rental_prop.calculate_all_depreciation(tax_year)
        total += result["total_depreciation"]
        property_breakdowns.append({
            "property_id": rental_prop.property_id,
            "address": rental_prop.property_address,
            "depreciation": result["total_depreciation"]
        })

    return {
        "session_id": session_id,
        "tax_year": tax_year,
        "total_depreciation": round(total, 2),
        "property_count": len(properties),
        "properties": property_breakdowns,
        "schedule_e_line_18": round(total, 2)
    }


@router.delete("/session/{session_id}/property/{property_id}")
async def delete_property(session_id: str, property_id: str):
    """
    Delete a rental property.
    """
    properties = get_or_create_properties(session_id)

    if property_id not in properties:
        raise HTTPException(status_code=404, detail="Property not found")

    del properties[property_id]

    return {"status": "deleted", "property_id": property_id}


@router.get("/health")
async def depreciation_health_check():
    """
    Check if depreciation API is operational.
    """
    return {
        "status": "operational" if DEPRECIATION_AVAILABLE else "unavailable",
        "depreciation_available": DEPRECIATION_AVAILABLE,
        "audit_available": AUDIT_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }
