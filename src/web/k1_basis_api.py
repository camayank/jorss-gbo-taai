"""
K-1 Basis Tracking API

REST API endpoints for managing K-1 partner/shareholder basis tracking
per IRC Section 705 and Section 704(d).
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
import logging

# Import K-1 basis models
try:
    from models.k1_basis import (
        K1BasisRecord,
        K1BasisTracker,
        BasisAdjustment,
        BasisAdjustmentType,
        Distribution,
        EntityType
    )
    K1_BASIS_AVAILABLE = True
except ImportError:
    K1_BASIS_AVAILABLE = False

# Import audit logger
try:
    from audit.audit_logger import audit_k1_import, audit_k1_basis_adjustment, get_audit_logger
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/k1-basis", tags=["K-1 Basis Tracking"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class K1BasisInput(BaseModel):
    """Input model for creating/updating K-1 basis record."""
    entity_name: str = Field(..., description="Name of the partnership/S-corp")
    entity_ein: Optional[str] = Field(None, description="EIN of the entity")
    entity_type: str = Field(default="partnership", description="partnership, s_corporation, trust_estate")
    tax_year: int = Field(..., description="Tax year")

    beginning_basis: float = Field(default=0.0, ge=0, description="Beginning of year basis")
    prior_year_suspended_losses: float = Field(default=0.0, ge=0, description="Suspended losses from prior years")
    ownership_percentage: float = Field(default=0.0, ge=0, le=100, description="Ownership percentage")

    # K-1 Box amounts (optional - can be populated from K-1)
    ordinary_income: Optional[float] = Field(None, description="Box 1 - Ordinary income/loss")
    net_rental_income: Optional[float] = Field(None, description="Box 2 - Net rental income/loss")
    portfolio_income: Optional[float] = Field(None, description="Box 5/6/7 - Interest, dividends, royalties")
    guaranteed_payments: Optional[float] = Field(None, description="Box 4 - Guaranteed payments")
    capital_gains_losses: Optional[float] = Field(None, description="Box 8/9 - Capital gains/losses")
    section_1231_gains_losses: Optional[float] = Field(None, description="Box 10 - Section 1231 gain/loss")
    other_income: Optional[float] = Field(None, description="Box 11 - Other income")
    section_179_deduction: Optional[float] = Field(None, description="Box 12 - Section 179 deduction")
    other_deductions: Optional[float] = Field(None, description="Box 13 - Other deductions")
    tax_exempt_interest: Optional[float] = Field(None, description="Box 18 - Tax-exempt income")

    distributions: Optional[float] = Field(None, description="Total distributions received")
    contributions: Optional[float] = Field(None, description="Capital contributions made")


class K1BasisResponse(BaseModel):
    """Response model for K-1 basis record."""
    id: str
    entity_name: str
    entity_ein: Optional[str]
    entity_type: str
    tax_year: int
    beginning_basis: float
    ending_basis: float
    total_increases: float
    total_decreases: float
    losses_allowed: float
    losses_suspended: float
    ownership_percentage: float


class BasisWorksheetResponse(BaseModel):
    """Response model for detailed basis worksheet."""
    entity: Dict[str, Any]
    tax_year: int
    basis_calculation: Dict[str, float]
    loss_limitation: Dict[str, float]
    at_risk: Dict[str, float]


class BasisSummaryResponse(BaseModel):
    """Summary response for all K-1 basis records."""
    total_entities: int
    total_ending_basis: float
    total_deductible_losses: float
    total_suspended_losses: float
    entities: List[Dict[str, Any]]


# =============================================================================
# IN-MEMORY STORAGE (replace with database in production)
# =============================================================================

# Session-based basis tracker storage
_trackers: Dict[str, K1BasisTracker] = {}


def get_or_create_tracker(session_id: str) -> K1BasisTracker:
    """Get or create a K-1 basis tracker for a session."""
    if session_id not in _trackers:
        _trackers[session_id] = K1BasisTracker()
    return _trackers[session_id]


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/session/{session_id}/record", response_model=K1BasisResponse)
async def create_basis_record(
    session_id: str,
    k1_data: K1BasisInput
):
    """
    Create or update a K-1 basis record for an entity.

    Calculates ending basis based on K-1 amounts and enforces
    loss limitations per IRC Section 704(d).
    """
    if not K1_BASIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="K-1 basis tracking not available")

    try:
        # Map entity type
        entity_type_map = {
            "partnership": EntityType.PARTNERSHIP,
            "s_corporation": EntityType.S_CORPORATION,
            "trust_estate": EntityType.TRUST_ESTATE
        }
        entity_type = entity_type_map.get(k1_data.entity_type.lower(), EntityType.PARTNERSHIP)

        # Create basis record
        record = K1BasisRecord(
            entity_name=k1_data.entity_name,
            entity_ein=k1_data.entity_ein,
            entity_type=entity_type,
            tax_year=k1_data.tax_year,
            beginning_basis=k1_data.beginning_basis,
            prior_year_suspended_losses=k1_data.prior_year_suspended_losses,
            ownership_percentage=k1_data.ownership_percentage
        )

        # Apply K-1 amounts if provided
        record.apply_from_k1(
            ordinary_income=k1_data.ordinary_income or 0,
            net_rental_income=k1_data.net_rental_income or 0,
            portfolio_income=k1_data.portfolio_income or 0,
            guaranteed_payments=k1_data.guaranteed_payments or 0,
            capital_gains_losses=k1_data.capital_gains_losses or 0,
            section_1231_gains_losses=k1_data.section_1231_gains_losses or 0,
            other_income=k1_data.other_income or 0,
            section_179_deduction=k1_data.section_179_deduction or 0,
            other_deductions=k1_data.other_deductions or 0,
            tax_exempt_interest=k1_data.tax_exempt_interest or 0,
            distributions=k1_data.distributions or 0,
            contributions=k1_data.contributions or 0
        )

        # Add to tracker
        tracker = get_or_create_tracker(session_id)
        tracker.add_record(record)

        # Audit log
        if AUDIT_AVAILABLE:
            audit_k1_import(
                session_id=session_id,
                k1_id=record.id,
                k1_data=record.to_dict(),
                entity_name=record.entity_name,
                entity_ein=record.entity_ein
            )

        return K1BasisResponse(
            id=record.id,
            entity_name=record.entity_name,
            entity_ein=record.entity_ein,
            entity_type=record.entity_type.value,
            tax_year=record.tax_year,
            beginning_basis=record.beginning_basis,
            ending_basis=record.ending_basis,
            total_increases=record.calculate_total_increases(),
            total_decreases=record.calculate_total_decreases(),
            losses_allowed=record.losses_allowed,
            losses_suspended=record.losses_suspended,
            ownership_percentage=record.ownership_percentage
        )

    except Exception as e:
        logger.error(f"Error creating K-1 basis record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/records", response_model=List[K1BasisResponse])
async def get_all_basis_records(session_id: str):
    """
    Get all K-1 basis records for a session.
    """
    if not K1_BASIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="K-1 basis tracking not available")

    tracker = get_or_create_tracker(session_id)

    records = []
    for record in tracker.get_all_records():
        records.append(K1BasisResponse(
            id=record.id,
            entity_name=record.entity_name,
            entity_ein=record.entity_ein,
            entity_type=record.entity_type.value,
            tax_year=record.tax_year,
            beginning_basis=record.beginning_basis,
            ending_basis=record.ending_basis,
            total_increases=record.calculate_total_increases(),
            total_decreases=record.calculate_total_decreases(),
            losses_allowed=record.losses_allowed,
            losses_suspended=record.losses_suspended,
            ownership_percentage=record.ownership_percentage
        ))

    return records


@router.get("/session/{session_id}/record/{entity_id}", response_model=K1BasisResponse)
async def get_basis_record(session_id: str, entity_id: str):
    """
    Get a specific K-1 basis record by entity identifier.
    """
    if not K1_BASIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="K-1 basis tracking not available")

    tracker = get_or_create_tracker(session_id)
    record = tracker.get_record(entity_id)

    if not record:
        raise HTTPException(status_code=404, detail="K-1 basis record not found")

    return K1BasisResponse(
        id=record.id,
        entity_name=record.entity_name,
        entity_ein=record.entity_ein,
        entity_type=record.entity_type.value,
        tax_year=record.tax_year,
        beginning_basis=record.beginning_basis,
        ending_basis=record.ending_basis,
        total_increases=record.calculate_total_increases(),
        total_decreases=record.calculate_total_decreases(),
        losses_allowed=record.losses_allowed,
        losses_suspended=record.losses_suspended,
        ownership_percentage=record.ownership_percentage
    )


@router.get("/session/{session_id}/record/{entity_id}/worksheet", response_model=BasisWorksheetResponse)
async def get_basis_worksheet(session_id: str, entity_id: str):
    """
    Get detailed basis worksheet for an entity.

    Shows step-by-step calculation per IRC §705 for CPA review.
    """
    if not K1_BASIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="K-1 basis tracking not available")

    tracker = get_or_create_tracker(session_id)
    record = tracker.get_record(entity_id)

    if not record:
        raise HTTPException(status_code=404, detail="K-1 basis record not found")

    worksheet = record.get_basis_worksheet()

    return BasisWorksheetResponse(
        entity=worksheet["entity"],
        tax_year=worksheet["tax_year"],
        basis_calculation=worksheet["basis_calculation"],
        loss_limitation=worksheet["loss_limitation"],
        at_risk=worksheet["at_risk"]
    )


@router.get("/session/{session_id}/summary", response_model=BasisSummaryResponse)
async def get_basis_summary(session_id: str):
    """
    Get summary of all K-1 basis tracking for a session.

    Shows totals for ending basis, deductible losses, and suspended losses.
    """
    if not K1_BASIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="K-1 basis tracking not available")

    tracker = get_or_create_tracker(session_id)
    summary = tracker.get_summary()

    return BasisSummaryResponse(
        total_entities=summary["total_entities"],
        total_ending_basis=summary["total_ending_basis"],
        total_deductible_losses=summary["total_deductible_losses"],
        total_suspended_losses=summary["total_suspended_losses"],
        entities=summary["entities"]
    )


@router.post("/session/{session_id}/record/{entity_id}/adjustment")
async def add_basis_adjustment(
    session_id: str,
    entity_id: str,
    adjustment_type: str = Body(..., description="Type of adjustment"),
    amount: float = Body(..., description="Adjustment amount"),
    description: Optional[str] = Body(None),
    k1_line_reference: Optional[str] = Body(None)
):
    """
    Add a manual basis adjustment to a K-1 record.
    """
    if not K1_BASIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="K-1 basis tracking not available")

    tracker = get_or_create_tracker(session_id)
    record = tracker.get_record(entity_id)

    if not record:
        raise HTTPException(status_code=404, detail="K-1 basis record not found")

    try:
        adj_type = BasisAdjustmentType(adjustment_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid adjustment type: {adjustment_type}")

    old_basis = record.ending_basis
    adjustment = BasisAdjustment(
        adjustment_type=adj_type,
        amount=amount,
        description=description,
        k1_line_reference=k1_line_reference
    )
    record.add_adjustment(adjustment)
    record.calculate_ending_basis()

    # Audit log
    if AUDIT_AVAILABLE:
        audit_k1_basis_adjustment(
            session_id=session_id,
            k1_id=entity_id,
            adjustment_type=adjustment_type,
            old_basis=old_basis,
            new_basis=record.ending_basis,
            reason=description
        )

    return {
        "status": "adjustment_added",
        "adjustment_id": adjustment.id,
        "new_ending_basis": record.ending_basis
    }


@router.post("/session/{session_id}/record/{entity_id}/distribution")
async def add_distribution(
    session_id: str,
    entity_id: str,
    cash_distributed: float = Body(default=0.0),
    property_fmv: float = Body(default=0.0),
    property_basis: float = Body(default=0.0),
    distribution_date: Optional[str] = Body(None)
):
    """
    Add a distribution to a K-1 basis record.
    """
    if not K1_BASIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="K-1 basis tracking not available")

    tracker = get_or_create_tracker(session_id)
    record = tracker.get_record(entity_id)

    if not record:
        raise HTTPException(status_code=404, detail="K-1 basis record not found")

    dist_date = date.today()
    if distribution_date:
        try:
            dist_date = datetime.strptime(distribution_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    distribution = Distribution(
        distribution_date=dist_date,
        cash_distributed=cash_distributed,
        property_fmv=property_fmv,
        property_basis=property_basis
    )
    record.add_distribution(distribution)
    record.calculate_ending_basis()

    return {
        "status": "distribution_added",
        "distribution_id": distribution.id,
        "total_distribution": distribution.total_distribution,
        "new_ending_basis": record.ending_basis
    }


@router.delete("/session/{session_id}/record/{entity_id}")
async def delete_basis_record(session_id: str, entity_id: str):
    """
    Delete a K-1 basis record.
    """
    if not K1_BASIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="K-1 basis tracking not available")

    tracker = get_or_create_tracker(session_id)

    if entity_id not in tracker.records:
        raise HTTPException(status_code=404, detail="K-1 basis record not found")

    del tracker.records[entity_id]

    return {"status": "deleted", "entity_id": entity_id}


@router.get("/health")
async def k1_basis_health_check():
    """
    Check if K-1 basis tracking API is operational.
    """
    return {
        "status": "operational" if K1_BASIS_AVAILABLE else "unavailable",
        "k1_basis_available": K1_BASIS_AVAILABLE,
        "audit_available": AUDIT_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }
