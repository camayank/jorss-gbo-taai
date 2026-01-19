"""
Core Tax Scenarios API Routes

Unified tax planning scenario endpoints for all user types:
- Create what-if scenarios
- Compare tax outcomes
- Optimize tax strategies
- Multi-year projections

Access control is automatically applied based on UserContext.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from uuid import uuid4
import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_routes import get_current_user
from ..models.user import UserContext, UserType
from database.async_engine import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["Core Tax Scenarios"])


# =============================================================================
# MODELS
# =============================================================================

class ScenarioType(str, Enum):
    INCOME_CHANGE = "income_change"
    DEDUCTION = "deduction"
    INVESTMENT = "investment"
    RETIREMENT = "retirement"
    REAL_ESTATE = "real_estate"
    BUSINESS = "business"
    LIFE_EVENT = "life_event"
    CUSTOM = "custom"


class ScenarioStatus(str, Enum):
    DRAFT = "draft"
    CALCULATED = "calculated"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


class TaxProjection(BaseModel):
    """Tax projection for a scenario."""
    gross_income: float
    adjusted_gross_income: float
    taxable_income: float
    federal_tax: float
    state_tax: float
    total_tax: float
    effective_rate: float
    marginal_rate: float
    refund_or_due: float


class ScenarioVariable(BaseModel):
    """A variable that can be adjusted in the scenario."""
    name: str
    label: str
    current_value: float
    scenario_value: float
    unit: str = "dollars"  # dollars, percent, units


class TaxScenario(BaseModel):
    """Tax planning scenario model."""
    id: str
    user_id: str
    firm_id: Optional[str] = None
    tax_return_id: Optional[str] = None

    name: str
    description: Optional[str] = None
    scenario_type: ScenarioType
    status: ScenarioStatus
    tax_year: int

    # Variables being modeled
    variables: List[ScenarioVariable] = []

    # Projections
    baseline: Optional[TaxProjection] = None
    projected: Optional[TaxProjection] = None
    savings: float = 0.0  # positive = savings, negative = cost

    # Metadata
    created_by: str
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None


class ScenarioSummary(BaseModel):
    """Summary view of scenario."""
    id: str
    name: str
    scenario_type: ScenarioType
    status: ScenarioStatus
    tax_year: int
    savings: float
    updated_at: datetime


class CreateScenarioRequest(BaseModel):
    """Request to create a scenario."""
    name: str
    scenario_type: ScenarioType
    tax_year: int = 2024
    description: Optional[str] = None
    tax_return_id: Optional[str] = None
    # For CPA creating on behalf of client
    client_user_id: Optional[str] = None


class UpdateScenarioRequest(BaseModel):
    """Request to update a scenario."""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ScenarioStatus] = None
    notes: Optional[str] = None


class AddVariableRequest(BaseModel):
    """Request to add a variable to scenario."""
    name: str
    label: str
    current_value: float
    scenario_value: float
    unit: str = "dollars"


# =============================================================================
# DATABASE HELPER FUNCTIONS
# =============================================================================

def _parse_dt(val) -> Optional[datetime]:
    """Parse datetime from database value."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _scenario_type_to_db(scenario_type: ScenarioType) -> str:
    """Map API scenario type to database enum value."""
    type_map = {
        ScenarioType.INCOME_CHANGE: "what_if",
        ScenarioType.DEDUCTION: "deduction_bunching",
        ScenarioType.INVESTMENT: "capital_gains",
        ScenarioType.RETIREMENT: "retirement",
        ScenarioType.REAL_ESTATE: "what_if",
        ScenarioType.BUSINESS: "entity_structure",
        ScenarioType.LIFE_EVENT: "filing_status",
        ScenarioType.CUSTOM: "what_if",
    }
    return type_map.get(scenario_type, "what_if")


def _db_type_to_scenario(db_type: str) -> ScenarioType:
    """Map database scenario type to API enum."""
    type_map = {
        "filing_status": ScenarioType.LIFE_EVENT,
        "what_if": ScenarioType.CUSTOM,
        "entity_structure": ScenarioType.BUSINESS,
        "deduction_bunching": ScenarioType.DEDUCTION,
        "retirement": ScenarioType.RETIREMENT,
        "multi_year": ScenarioType.CUSTOM,
        "roth_conversion": ScenarioType.RETIREMENT,
        "capital_gains": ScenarioType.INVESTMENT,
        "estimated_tax": ScenarioType.CUSTOM,
    }
    return type_map.get(db_type, ScenarioType.CUSTOM)


def _status_to_db(status: ScenarioStatus) -> str:
    """Map API status to database enum value."""
    status_map = {
        ScenarioStatus.DRAFT: "draft",
        ScenarioStatus.CALCULATED: "calculated",
        ScenarioStatus.REVIEWED: "calculated",
        ScenarioStatus.ARCHIVED: "archived",
    }
    return status_map.get(status, "draft")


def _db_status_to_api(db_status: str) -> ScenarioStatus:
    """Map database status to API enum."""
    status_map = {
        "draft": ScenarioStatus.DRAFT,
        "calculated": ScenarioStatus.CALCULATED,
        "applied": ScenarioStatus.REVIEWED,
        "archived": ScenarioStatus.ARCHIVED,
    }
    return status_map.get(db_status, ScenarioStatus.DRAFT)


def _row_to_scenario(row) -> TaxScenario:
    """Convert database row to TaxScenario model."""
    scenario_data = json.loads(row[6]) if row[6] else {}

    # Parse variables from scenario_data
    variables = []
    for var_data in scenario_data.get("variables", []):
        variables.append(ScenarioVariable(**var_data))

    # Parse projections
    baseline = None
    if scenario_data.get("baseline"):
        baseline = TaxProjection(**scenario_data["baseline"])

    projected = None
    if scenario_data.get("projected"):
        projected = TaxProjection(**scenario_data["projected"])

    return TaxScenario(
        id=str(row[0]),
        user_id=scenario_data.get("user_id", ""),
        firm_id=scenario_data.get("firm_id"),
        tax_return_id=str(row[1]) if row[1] else None,
        name=row[2],
        description=scenario_data.get("description"),
        scenario_type=_db_type_to_scenario(row[3]),
        status=_db_status_to_api(row[4]),
        tax_year=scenario_data.get("tax_year", 2024),
        variables=variables,
        baseline=baseline,
        projected=projected,
        savings=scenario_data.get("savings", 0.0),
        created_by=scenario_data.get("created_by", ""),
        created_at=_parse_dt(row[7]) or datetime.utcnow(),
        updated_at=_parse_dt(row[8]) or datetime.utcnow(),
        notes=scenario_data.get("notes"),
    )


def _scenario_to_json(scenario: TaxScenario) -> str:
    """Convert TaxScenario to JSON for database storage."""
    data = {
        "user_id": scenario.user_id,
        "firm_id": scenario.firm_id,
        "tax_year": scenario.tax_year,
        "description": scenario.description,
        "variables": [var.model_dump() for var in scenario.variables],
        "baseline": scenario.baseline.model_dump() if scenario.baseline else None,
        "projected": scenario.projected.model_dump() if scenario.projected else None,
        "savings": scenario.savings,
        "created_by": scenario.created_by,
        "notes": scenario.notes,
    }
    return json.dumps(data)


async def _build_access_conditions(context: UserContext) -> tuple:
    """Build SQL conditions for role-based scenario access."""
    conditions = []
    params = {}

    if context.user_type == UserType.PLATFORM_ADMIN:
        conditions.append("1=1")
    elif context.user_type == UserType.CPA_TEAM:
        # CPA team can see scenarios for their firm or created by them
        conditions.append(
            "(scenario_data->>'firm_id' = :firm_id OR scenario_data->>'created_by' = :user_id)"
        )
        params["firm_id"] = context.firm_id
        params["user_id"] = context.user_id
    else:
        # Consumers see only their own scenarios
        conditions.append("scenario_data->>'user_id' = :user_id")
        params["user_id"] = context.user_id

    return " AND ".join(conditions), params


# =============================================================================
# ACCESS CONTROL HELPERS
# =============================================================================

def _can_access_scenario_data(context: UserContext, scenario_data: dict, user_id: str, firm_id: Optional[str], created_by: str) -> bool:
    """Check if user can access a scenario based on scenario data."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    if user_id == context.user_id:
        return True

    if context.user_type == UserType.CPA_TEAM:
        if firm_id == context.firm_id:
            return True
        if created_by == context.user_id:
            return True

    return False


def _can_modify_scenario_data(context: UserContext, user_id: str, firm_id: Optional[str], created_by: str) -> bool:
    """Check if user can modify a scenario."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    if user_id == context.user_id:
        return True

    if context.user_type == UserType.CPA_TEAM:
        if created_by == context.user_id:
            return True
        if firm_id == context.firm_id and context.has_permission("manage_scenarios"):
            return True

    return False


def _calculate_projection(variables: List[ScenarioVariable], baseline: TaxProjection) -> TaxProjection:
    """Calculate tax projection based on scenario variables."""
    # Simplified calculation - in production this would use actual tax logic
    total_adjustment = sum(v.scenario_value - v.current_value for v in variables)

    new_agi = baseline.adjusted_gross_income - total_adjustment
    new_taxable = max(0, new_agi - 15750)  # 2025 Standard deduction

    # Simplified tax brackets (2025 single - IRS Rev. Proc. 2024-40)
    if new_taxable <= 11925:
        federal = new_taxable * 0.10
        marginal = 10
    elif new_taxable <= 48475:
        federal = 1192.50 + (new_taxable - 11925) * 0.12
        marginal = 12
    elif new_taxable <= 103350:
        federal = 5578.50 + (new_taxable - 48475) * 0.22
        marginal = 22
    else:
        federal = 17651 + (new_taxable - 103350) * 0.24
        marginal = 24

    state = new_taxable * 0.05  # Simplified state tax
    total = federal + state

    return TaxProjection(
        gross_income=baseline.gross_income,
        adjusted_gross_income=new_agi,
        taxable_income=new_taxable,
        federal_tax=round(federal, 2),
        state_tax=round(state, 2),
        total_tax=round(total, 2),
        effective_rate=round((total / baseline.gross_income) * 100, 1) if baseline.gross_income > 0 else 0,
        marginal_rate=marginal,
        refund_or_due=round(baseline.refund_or_due + (baseline.total_tax - total), 2)
    )


# =============================================================================
# LIST & SEARCH ENDPOINTS
# =============================================================================

@router.get("", response_model=List[ScenarioSummary])
async def list_scenarios(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    scenario_type: Optional[ScenarioType] = None,
    status_filter: Optional[ScenarioStatus] = Query(None, alias="status"),
    tax_year: Optional[int] = None,
    user_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """
    List tax scenarios with role-based filtering.

    Access control:
    - Consumers/CPA Clients: See only their own scenarios
    - CPA Team: See scenarios in their firm or created by them
    - Platform Admins: See all scenarios
    """
    # Build access conditions
    access_where, params = await _build_access_conditions(context)
    conditions = [access_where]

    # Apply filters
    if scenario_type:
        conditions.append("scenario_type = :scenario_type")
        params["scenario_type"] = _scenario_type_to_db(scenario_type)

    if status_filter:
        conditions.append("status = :status")
        params["status"] = _status_to_db(status_filter)

    if tax_year:
        conditions.append("(scenario_data->>'tax_year')::int = :tax_year")
        params["tax_year"] = tax_year

    if user_id:
        conditions.append("scenario_data->>'user_id' = :filter_user_id")
        params["filter_user_id"] = user_id

    where_clause = " AND ".join(conditions)
    params["limit"] = limit
    params["offset"] = offset

    query = text(f"""
        SELECT scenario_id, return_id, name, scenario_type, status,
               is_recommended, scenario_data, created_at, updated_at
        FROM scenarios
        WHERE {where_clause}
        ORDER BY updated_at DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    results = []
    for row in rows:
        scenario_data = json.loads(row[6]) if row[6] else {}
        results.append(ScenarioSummary(
            id=str(row[0]),
            name=row[2],
            scenario_type=_db_type_to_scenario(row[3]),
            status=_db_status_to_api(row[4]),
            tax_year=scenario_data.get("tax_year", 2024),
            savings=scenario_data.get("savings", 0.0),
            updated_at=_parse_dt(row[8]) or datetime.utcnow()
        ))

    return results


@router.get("/my")
async def get_my_scenarios(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    tax_year: Optional[int] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """Get current user's scenarios."""
    return await list_scenarios(
        context=context,
        session=session,
        user_id=context.user_id,
        tax_year=tax_year,
        limit=limit,
        offset=offset
    )


# =============================================================================
# CRUD ENDPOINTS
# =============================================================================

@router.get("/{scenario_id}", response_model=TaxScenario)
async def get_scenario(
    scenario_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get a specific scenario with full details."""
    query = text("""
        SELECT scenario_id, return_id, name, scenario_type, status,
               is_recommended, scenario_data, created_at, updated_at
        FROM scenarios
        WHERE scenario_id = :scenario_id
    """)

    result = await session.execute(query, {"scenario_id": scenario_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )

    scenario_data = json.loads(row[6]) if row[6] else {}
    user_id = scenario_data.get("user_id", "")
    firm_id = scenario_data.get("firm_id")
    created_by = scenario_data.get("created_by", "")

    if not _can_access_scenario_data(context, scenario_data, user_id, firm_id, created_by):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this scenario"
        )

    return _row_to_scenario(row)


@router.post("", response_model=TaxScenario)
async def create_scenario(
    request: CreateScenarioRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Create a new tax scenario.

    - Consumers/CPA Clients: Create for themselves
    - CPA Team: Create for clients (specify client_user_id)
    """
    target_user_id = context.user_id
    firm_id = context.firm_id

    if request.client_user_id:
        if context.user_type not in [UserType.CPA_TEAM, UserType.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only CPA team can create scenarios for other users"
            )
        target_user_id = request.client_user_id

    now = datetime.utcnow()
    scenario_id = str(uuid4())

    scenario = TaxScenario(
        id=scenario_id,
        user_id=target_user_id,
        firm_id=firm_id,
        tax_return_id=request.tax_return_id,
        name=request.name,
        description=request.description,
        scenario_type=request.scenario_type,
        status=ScenarioStatus.DRAFT,
        tax_year=request.tax_year,
        variables=[],
        created_by=context.user_id,
        created_at=now,
        updated_at=now
    )

    # Insert into database
    query = text("""
        INSERT INTO scenarios (
            scenario_id, return_id, name, scenario_type, status,
            is_recommended, scenario_data, created_at, updated_at
        ) VALUES (
            :scenario_id, :return_id, :name, :scenario_type, :status,
            false, :scenario_data, :created_at, :updated_at
        )
    """)

    await session.execute(query, {
        "scenario_id": scenario_id,
        "return_id": request.tax_return_id,
        "name": request.name,
        "scenario_type": _scenario_type_to_db(request.scenario_type),
        "status": "draft",
        "scenario_data": _scenario_to_json(scenario),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"Scenario created: {scenario_id} by {context.user_id}")

    return scenario


@router.patch("/{scenario_id}", response_model=TaxScenario)
async def update_scenario(
    scenario_id: str,
    request: UpdateScenarioRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Update a scenario."""
    # Fetch existing scenario
    query = text("""
        SELECT scenario_id, return_id, name, scenario_type, status,
               is_recommended, scenario_data, created_at, updated_at
        FROM scenarios
        WHERE scenario_id = :scenario_id
    """)
    result = await session.execute(query, {"scenario_id": scenario_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )

    scenario_data = json.loads(row[6]) if row[6] else {}
    user_id = scenario_data.get("user_id", "")
    firm_id = scenario_data.get("firm_id")
    created_by = scenario_data.get("created_by", "")

    if not _can_modify_scenario_data(context, user_id, firm_id, created_by):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this scenario"
        )

    # Build the scenario object
    scenario = _row_to_scenario(row)

    # Apply updates
    if request.name is not None:
        scenario.name = request.name
    if request.description is not None:
        scenario.description = request.description
    if request.status is not None:
        scenario.status = request.status
    if request.notes is not None:
        scenario.notes = request.notes

    scenario.updated_at = datetime.utcnow()

    # Update database
    update_query = text("""
        UPDATE scenarios SET
            name = :name,
            status = :status,
            scenario_data = :scenario_data,
            updated_at = :updated_at
        WHERE scenario_id = :scenario_id
    """)

    await session.execute(update_query, {
        "scenario_id": scenario_id,
        "name": scenario.name,
        "status": _status_to_db(scenario.status),
        "scenario_data": _scenario_to_json(scenario),
        "updated_at": scenario.updated_at.isoformat(),
    })
    await session.commit()

    logger.info(f"Scenario updated: {scenario_id} by {context.user_id}")

    return scenario


@router.delete("/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a scenario."""
    # Fetch existing scenario to check permissions
    query = text("""
        SELECT scenario_id, scenario_data
        FROM scenarios
        WHERE scenario_id = :scenario_id
    """)
    result = await session.execute(query, {"scenario_id": scenario_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )

    scenario_data = json.loads(row[1]) if row[1] else {}
    user_id = scenario_data.get("user_id", "")
    firm_id = scenario_data.get("firm_id")
    created_by = scenario_data.get("created_by", "")

    if not _can_modify_scenario_data(context, user_id, firm_id, created_by):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete this scenario"
        )

    # Delete from database
    delete_query = text("DELETE FROM scenarios WHERE scenario_id = :scenario_id")
    await session.execute(delete_query, {"scenario_id": scenario_id})
    await session.commit()

    logger.info(f"Scenario deleted: {scenario_id} by {context.user_id}")

    return {"success": True, "message": "Scenario deleted"}


# =============================================================================
# VARIABLE MANAGEMENT
# =============================================================================

@router.post("/{scenario_id}/variables", response_model=TaxScenario)
async def add_variable(
    scenario_id: str,
    request: AddVariableRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Add a variable to a scenario."""
    # Fetch existing scenario
    query = text("""
        SELECT scenario_id, return_id, name, scenario_type, status,
               is_recommended, scenario_data, created_at, updated_at
        FROM scenarios
        WHERE scenario_id = :scenario_id
    """)
    result = await session.execute(query, {"scenario_id": scenario_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )

    scenario_data = json.loads(row[6]) if row[6] else {}
    user_id = scenario_data.get("user_id", "")
    firm_id = scenario_data.get("firm_id")
    created_by = scenario_data.get("created_by", "")

    if not _can_modify_scenario_data(context, user_id, firm_id, created_by):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this scenario"
        )

    # Build scenario object
    scenario = _row_to_scenario(row)

    # Check for duplicate variable name
    for var in scenario.variables:
        if var.name == request.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Variable '{request.name}' already exists"
            )

    scenario.variables.append(ScenarioVariable(
        name=request.name,
        label=request.label,
        current_value=request.current_value,
        scenario_value=request.scenario_value,
        unit=request.unit
    ))

    scenario.status = ScenarioStatus.DRAFT
    scenario.updated_at = datetime.utcnow()

    # Update database
    update_query = text("""
        UPDATE scenarios SET
            status = :status,
            scenario_data = :scenario_data,
            updated_at = :updated_at
        WHERE scenario_id = :scenario_id
    """)

    await session.execute(update_query, {
        "scenario_id": scenario_id,
        "status": "draft",
        "scenario_data": _scenario_to_json(scenario),
        "updated_at": scenario.updated_at.isoformat(),
    })
    await session.commit()

    return scenario


@router.delete("/{scenario_id}/variables/{variable_name}")
async def remove_variable(
    scenario_id: str,
    variable_name: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Remove a variable from a scenario."""
    # Fetch existing scenario
    query = text("""
        SELECT scenario_id, return_id, name, scenario_type, status,
               is_recommended, scenario_data, created_at, updated_at
        FROM scenarios
        WHERE scenario_id = :scenario_id
    """)
    result = await session.execute(query, {"scenario_id": scenario_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )

    scenario_data = json.loads(row[6]) if row[6] else {}
    user_id = scenario_data.get("user_id", "")
    firm_id = scenario_data.get("firm_id")
    created_by = scenario_data.get("created_by", "")

    if not _can_modify_scenario_data(context, user_id, firm_id, created_by):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this scenario"
        )

    # Build scenario object
    scenario = _row_to_scenario(row)

    scenario.variables = [v for v in scenario.variables if v.name != variable_name]
    scenario.status = ScenarioStatus.DRAFT
    scenario.updated_at = datetime.utcnow()

    # Update database
    update_query = text("""
        UPDATE scenarios SET
            status = :status,
            scenario_data = :scenario_data,
            updated_at = :updated_at
        WHERE scenario_id = :scenario_id
    """)

    await session.execute(update_query, {
        "scenario_id": scenario_id,
        "status": "draft",
        "scenario_data": _scenario_to_json(scenario),
        "updated_at": scenario.updated_at.isoformat(),
    })
    await session.commit()

    return {"success": True, "message": "Variable removed"}


# =============================================================================
# CALCULATION
# =============================================================================

@router.post("/{scenario_id}/calculate", response_model=TaxScenario)
async def calculate_scenario(
    scenario_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Calculate tax projections for a scenario.

    Uses the variables to project the tax impact.
    """
    # Fetch existing scenario
    query = text("""
        SELECT scenario_id, return_id, name, scenario_type, status,
               is_recommended, scenario_data, created_at, updated_at
        FROM scenarios
        WHERE scenario_id = :scenario_id
    """)
    result = await session.execute(query, {"scenario_id": scenario_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )

    scenario_data_raw = json.loads(row[6]) if row[6] else {}
    user_id = scenario_data_raw.get("user_id", "")
    firm_id = scenario_data_raw.get("firm_id")
    created_by = scenario_data_raw.get("created_by", "")

    if not _can_access_scenario_data(context, scenario_data_raw, user_id, firm_id, created_by):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Build scenario object
    scenario = _row_to_scenario(row)

    if not scenario.variables:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one variable before calculating"
        )

    # Create or use existing baseline
    if not scenario.baseline:
        # Try to fetch baseline from linked tax return
        baseline_data = None
        if scenario.tax_return_id:
            return_query = text("""
                SELECT line_9_total_income, line_11_agi, line_15_taxable_income,
                       line_16_tax, state_tax_liability, line_35a_refund, line_37_amount_owed,
                       effective_tax_rate, marginal_tax_rate
                FROM tax_returns
                WHERE return_id = :return_id
            """)
            return_result = await session.execute(return_query, {"return_id": scenario.tax_return_id})
            return_row = return_result.fetchone()
            if return_row:
                federal_tax = float(return_row[3] or 0)
                state_tax = float(return_row[4] or 0)
                refund = float(return_row[5] or 0)
                owed = float(return_row[6] or 0)
                baseline_data = TaxProjection(
                    gross_income=float(return_row[0] or 0),
                    adjusted_gross_income=float(return_row[1] or 0),
                    taxable_income=float(return_row[2] or 0),
                    federal_tax=federal_tax,
                    state_tax=state_tax,
                    total_tax=federal_tax + state_tax,
                    effective_rate=float(return_row[7] or 0) * 100,
                    marginal_rate=float(return_row[8] or 0) * 100,
                    refund_or_due=refund if refund > 0 else -owed
                )

        if not baseline_data:
            # Default baseline
            baseline_data = TaxProjection(
                gross_income=85000,
                adjusted_gross_income=79000,
                taxable_income=65000,
                federal_tax=9800,
                state_tax=3250,
                total_tax=13050,
                effective_rate=15.4,
                marginal_rate=22,
                refund_or_due=2100
            )
        scenario.baseline = baseline_data

    # Calculate projection
    scenario.projected = _calculate_projection(scenario.variables, scenario.baseline)
    scenario.savings = round(scenario.baseline.total_tax - scenario.projected.total_tax, 2)
    scenario.status = ScenarioStatus.CALCULATED
    scenario.updated_at = datetime.utcnow()

    # Update database
    update_query = text("""
        UPDATE scenarios SET
            status = :status,
            scenario_data = :scenario_data,
            updated_at = :updated_at
        WHERE scenario_id = :scenario_id
    """)

    await session.execute(update_query, {
        "scenario_id": scenario_id,
        "status": "calculated",
        "scenario_data": _scenario_to_json(scenario),
        "updated_at": scenario.updated_at.isoformat(),
    })
    await session.commit()

    logger.info(f"Scenario calculated: {scenario_id}, savings: ${scenario.savings}")

    return scenario


# =============================================================================
# COMPARISON
# =============================================================================

@router.get("/{scenario_id}/compare")
async def compare_scenarios(
    scenario_id: str,
    compare_to: str = Query(..., description="ID of scenario to compare"),
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Compare two scenarios side by side."""
    # Fetch both scenarios
    query = text("""
        SELECT scenario_id, return_id, name, scenario_type, status,
               is_recommended, scenario_data, created_at, updated_at
        FROM scenarios
        WHERE scenario_id IN (:scenario_id_1, :scenario_id_2)
    """)
    result = await session.execute(query, {"scenario_id_1": scenario_id, "scenario_id_2": compare_to})
    rows = result.fetchall()

    if len(rows) < 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both scenarios not found"
        )

    # Map scenarios by ID
    scenarios_map = {}
    for row in rows:
        scenario_data = json.loads(row[6]) if row[6] else {}
        user_id = scenario_data.get("user_id", "")
        firm_id = scenario_data.get("firm_id")
        created_by = scenario_data.get("created_by", "")

        if not _can_access_scenario_data(context, scenario_data, user_id, firm_id, created_by):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to one or both scenarios"
            )

        scenarios_map[str(row[0])] = _row_to_scenario(row)

    scenario1 = scenarios_map.get(scenario_id)
    scenario2 = scenarios_map.get(compare_to)

    if not scenario1 or not scenario2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both scenarios not found"
        )

    return {
        "scenario_a": {
            "id": scenario1.id,
            "name": scenario1.name,
            "type": scenario1.scenario_type,
            "projected": scenario1.projected,
            "savings": scenario1.savings
        },
        "scenario_b": {
            "id": scenario2.id,
            "name": scenario2.name,
            "type": scenario2.scenario_type,
            "projected": scenario2.projected,
            "savings": scenario2.savings
        },
        "difference": {
            "savings": scenario1.savings - scenario2.savings,
            "total_tax": (
                (scenario1.projected.total_tax if scenario1.projected else 0) -
                (scenario2.projected.total_tax if scenario2.projected else 0)
            ),
            "effective_rate": (
                (scenario1.projected.effective_rate if scenario1.projected else 0) -
                (scenario2.projected.effective_rate if scenario2.projected else 0)
            )
        },
        "recommendation": "Scenario A" if scenario1.savings > scenario2.savings else "Scenario B"
    }


# =============================================================================
# TEMPLATES
# =============================================================================

@router.get("/templates/list")
async def list_scenario_templates():
    """Get available scenario templates."""
    return [
        {
            "id": "retirement_401k",
            "name": "401(k) Contribution Optimization",
            "type": ScenarioType.RETIREMENT,
            "description": "Analyze the tax impact of increasing your 401(k) contributions",
            "suggested_variables": [
                {"name": "retirement_contribution", "label": "401(k) Contribution", "unit": "dollars"}
            ]
        },
        {
            "id": "ira_contribution",
            "name": "Traditional vs Roth IRA",
            "type": ScenarioType.RETIREMENT,
            "description": "Compare traditional and Roth IRA contribution strategies",
            "suggested_variables": [
                {"name": "traditional_ira", "label": "Traditional IRA", "unit": "dollars"},
                {"name": "roth_ira", "label": "Roth IRA", "unit": "dollars"}
            ]
        },
        {
            "id": "home_office",
            "name": "Home Office Deduction",
            "type": ScenarioType.DEDUCTION,
            "description": "Calculate home office deduction using simplified or actual expense method",
            "suggested_variables": [
                {"name": "home_office_sqft", "label": "Office Square Footage", "unit": "sqft"},
                {"name": "total_home_sqft", "label": "Total Home Square Footage", "unit": "sqft"}
            ]
        },
        {
            "id": "income_change",
            "name": "Salary Change Impact",
            "type": ScenarioType.INCOME_CHANGE,
            "description": "Analyze tax impact of a salary change or bonus",
            "suggested_variables": [
                {"name": "salary_change", "label": "Salary Change", "unit": "dollars"}
            ]
        },
        {
            "id": "charitable",
            "name": "Charitable Giving Strategy",
            "type": ScenarioType.DEDUCTION,
            "description": "Optimize charitable giving for tax benefits",
            "suggested_variables": [
                {"name": "charitable_cash", "label": "Cash Donations", "unit": "dollars"},
                {"name": "charitable_property", "label": "Property Donations", "unit": "dollars"}
            ]
        }
    ]
