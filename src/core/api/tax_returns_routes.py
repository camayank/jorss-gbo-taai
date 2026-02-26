"""
Core Tax Returns API Routes

Unified tax return management endpoints for all user types:
- View tax returns (with role-based filtering)
- Create/submit tax returns
- Update tax return status
- Tax return analytics

Access control is automatically applied based on UserContext.
All routes use database-backed queries.
"""

import json
import logging
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List
from datetime import datetime
from enum import Enum
from decimal import Decimal
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_routes import get_current_user
from ..models.user import UserContext, UserType
from database.async_engine import get_async_session

logger = logging.getLogger(__name__)

# Column whitelist for UPDATE queries — prevents SQL injection in dynamic SET clauses
_RETURN_UPDATABLE_COLUMNS = frozenset({
    "gross_income", "adjusted_gross_income", "taxable_income",
    "total_tax", "filing_status", "status", "notes",
    "refund_amount", "amount_due", "completion_percentage",
    "workflow_stage", "completed_at", "updated_at",
})

router = APIRouter(prefix="/tax-returns", tags=["Core Tax Returns"])


# =============================================================================
# MODELS
# =============================================================================

class TaxReturnStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    UNDER_REVIEW = "under_review"
    NEEDS_INFO = "needs_info"
    APPROVED = "approved"
    FILED = "filed"
    REJECTED = "rejected"


class TaxReturnType(str, Enum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    PARTNERSHIP = "partnership"
    CORPORATION = "corporation"
    TRUST = "trust"


class TaxReturn(BaseModel):
    """Tax return model."""
    id: str
    user_id: str
    firm_id: Optional[str] = None
    assigned_cpa_id: Optional[str] = None

    tax_year: int
    return_type: TaxReturnType
    status: TaxReturnStatus

    # Financial data — use Decimal with range validation to prevent NaN/Infinity
    gross_income: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))
    adjusted_gross_income: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))
    taxable_income: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))
    total_tax: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))
    refund_amount: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))
    amount_due: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))

    # Metadata
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    filed_at: Optional[datetime] = None

    # Progress tracking
    completion_percentage: int = 0
    documents_uploaded: int = 0
    documents_required: int = 0


class TaxReturnSummary(BaseModel):
    """Summary view of tax return."""
    id: str
    user_id: str
    user_name: str
    tax_year: int
    return_type: TaxReturnType
    status: TaxReturnStatus
    gross_income: float
    total_tax: float
    completion_percentage: int
    updated_at: datetime


class CreateTaxReturnRequest(BaseModel):
    """Request to create a new tax return."""
    tax_year: int
    return_type: TaxReturnType = TaxReturnType.INDIVIDUAL
    # For CPA creating on behalf of client
    client_user_id: Optional[str] = None


class UpdateTaxReturnRequest(BaseModel):
    """Request to update tax return."""
    status: Optional[TaxReturnStatus] = None
    gross_income: Optional[float] = None
    adjusted_gross_income: Optional[float] = None
    taxable_income: Optional[float] = None
    total_tax: Optional[float] = None
    refund_amount: Optional[float] = None
    amount_due: Optional[float] = None
    completion_percentage: Optional[int] = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_dt(val):
    """Parse datetime from database."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val.replace('Z', '+00:00'))


def _build_access_conditions(context: UserContext) -> tuple:
    """Build SQL conditions for role-based access."""
    conditions = []
    params = {}

    if context.user_type == UserType.PLATFORM_ADMIN:
        # Platform admins can access all
        conditions.append("1=1")
    elif context.user_type == UserType.CPA_TEAM:
        # CPA team can access returns in their firm or assigned to them
        conditions.append("(r.firm_id = :firm_id OR r.preparer_id = :user_id OR r.client_id IN (SELECT client_id FROM clients WHERE preparer_id = :user_id))")
        params["firm_id"] = context.firm_id
        params["user_id"] = context.user_id
    else:
        # Consumers/clients can only see their own returns
        conditions.append("r.client_id = :user_id")
        params["user_id"] = context.user_id

    return " AND ".join(conditions), params


def _can_access_return_data(context: UserContext, return_data: dict) -> bool:
    """Check if user can access a tax return based on dict data."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    user_id = return_data.get("user_id") or return_data.get("client_id")
    if user_id == context.user_id:
        return True

    if context.user_type == UserType.CPA_TEAM:
        if return_data.get("firm_id") == context.firm_id:
            return True
        if return_data.get("preparer_id") == context.user_id:
            return True

    return False


def _can_modify_return_data(context: UserContext, return_data: dict) -> bool:
    """Check if user can modify a tax return based on dict data."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    status_val = return_data.get("status") or return_data.get("workflow_stage")
    user_id = return_data.get("user_id") or return_data.get("client_id")

    if user_id == context.user_id:
        return status_val not in ["filed", "complete", "rejected"]

    if context.user_type == UserType.CPA_TEAM:
        if return_data.get("preparer_id") == context.user_id:
            return True
        if return_data.get("firm_id") == context.firm_id and context.has_permission("manage_returns"):
            return True

    return False


def _map_workflow_to_status(workflow_stage: str) -> str:
    """Map workflow stage to TaxReturnStatus."""
    stage_map = {
        "intake": "draft",
        "document_collection": "in_progress",
        "preparation": "in_progress",
        "review": "under_review",
        "client_review": "pending_review",
        "approval": "approved",
        "filing": "approved",
        "complete": "filed",
    }
    return stage_map.get(workflow_stage, "in_progress")


def _map_status_to_workflow(status_str: str) -> str:
    """Map TaxReturnStatus to workflow stage."""
    status_map = {
        "draft": "intake",
        "in_progress": "preparation",
        "pending_review": "review",
        "under_review": "review",
        "needs_info": "document_collection",
        "approved": "approval",
        "filed": "complete",
        "rejected": "preparation",
    }
    return status_map.get(status_str, "preparation")


# =============================================================================
# LIST & SEARCH ENDPOINTS
# =============================================================================

@router.get("", response_model=List[TaxReturnSummary])
async def list_tax_returns(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    tax_year: Optional[int] = None,
    status: Optional[TaxReturnStatus] = None,
    return_type: Optional[TaxReturnType] = None,
    user_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """
    List tax returns with role-based filtering.

    Access control:
    - Consumers/CPA Clients: See only their own returns
    - CPA Team: See returns in their firm or assigned to them
    - Platform Admins: See all returns
    """
    # Build access conditions
    access_conditions, params = _build_access_conditions(context)
    conditions = [access_conditions]
    params["limit"] = limit
    params["offset"] = offset

    # Apply search filters
    if tax_year:
        conditions.append("r.tax_year = :tax_year")
        params["tax_year"] = tax_year

    if status:
        workflow_stage = _map_status_to_workflow(status.value)
        conditions.append("r.workflow_stage = :workflow_stage")
        params["workflow_stage"] = workflow_stage

    if return_type:
        conditions.append("r.return_type = :return_type")
        params["return_type"] = return_type.value

    if user_id:
        conditions.append("r.client_id = :filter_user_id")
        params["filter_user_id"] = user_id

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT r.return_id, r.client_id, c.first_name || ' ' || c.last_name as client_name,
               r.tax_year, r.return_type, r.workflow_stage, r.gross_income, r.total_tax,
               r.completion_percentage, r.updated_at
        FROM returns r
        LEFT JOIN clients c ON r.client_id = c.client_id
        WHERE {where_clause}
        ORDER BY r.updated_at DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    results = []
    for row in rows:
        status_val = _map_workflow_to_status(row[5] or "intake")
        results.append(TaxReturnSummary(
            id=str(row[0]),
            user_id=str(row[1]) if row[1] else "",
            user_name=row[2] or "Unknown",
            tax_year=row[3] or datetime.utcnow().year,
            return_type=TaxReturnType(row[4]) if row[4] else TaxReturnType.INDIVIDUAL,
            status=TaxReturnStatus(status_val),
            gross_income=float(row[6] or 0),
            total_tax=float(row[7] or 0),
            completion_percentage=row[8] or 0,
            updated_at=_parse_dt(row[9]) or datetime.utcnow(),
        ))

    return results


@router.get("/my")
async def get_my_tax_returns(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    tax_year: Optional[int] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """
    Get current user's tax returns.

    Shortcut for listing only the authenticated user's returns.
    """
    return await list_tax_returns(
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

@router.get("/{return_id}", response_model=TaxReturn)
async def get_tax_return(
    return_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get a specific tax return.

    Returns full tax return details if user has access.
    """
    query = text("""
        SELECT r.return_id, r.client_id, r.firm_id, r.preparer_id,
               r.tax_year, r.return_type, r.workflow_stage,
               r.gross_income, r.adjusted_gross_income, r.taxable_income,
               r.total_tax, r.refund_amount, r.amount_due,
               r.created_at, r.updated_at, r.submitted_at, r.completed_at,
               r.completion_percentage, r.documents_uploaded, r.documents_required
        FROM returns r
        WHERE r.return_id = :return_id
    """)
    result = await session.execute(query, {"return_id": return_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tax return not found"
        )

    return_data = {
        "client_id": str(row[1]) if row[1] else None,
        "firm_id": str(row[2]) if row[2] else None,
        "preparer_id": str(row[3]) if row[3] else None,
        "workflow_stage": row[6],
    }

    if not _can_access_return_data(context, return_data):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this tax return"
        )

    status_val = _map_workflow_to_status(row[6] or "intake")
    return TaxReturn(
        id=str(row[0]),
        user_id=str(row[1]) if row[1] else "",
        firm_id=str(row[2]) if row[2] else None,
        assigned_cpa_id=str(row[3]) if row[3] else None,
        tax_year=row[4] or datetime.utcnow().year,
        return_type=TaxReturnType(row[5]) if row[5] else TaxReturnType.INDIVIDUAL,
        status=TaxReturnStatus(status_val),
        gross_income=float(row[7] or 0),
        adjusted_gross_income=float(row[8] or 0),
        taxable_income=float(row[9] or 0),
        total_tax=float(row[10] or 0),
        refund_amount=float(row[11] or 0),
        amount_due=float(row[12] or 0),
        created_at=_parse_dt(row[13]) or datetime.utcnow(),
        updated_at=_parse_dt(row[14]) or datetime.utcnow(),
        submitted_at=_parse_dt(row[15]),
        filed_at=_parse_dt(row[16]),
        completion_percentage=row[17] or 0,
        documents_uploaded=row[18] or 0,
        documents_required=row[19] or 8,
    )


@router.post("", response_model=TaxReturn)
async def create_tax_return(
    request: CreateTaxReturnRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a new tax return.

    - Consumers/CPA Clients: Create for themselves
    - CPA Team: Create for clients (specify client_user_id)
    - Platform Admins: Create for any user
    """
    # Determine the user_id for the return
    target_user_id = context.user_id
    firm_id = context.firm_id
    assigned_cpa_id = None

    if request.client_user_id:
        # CPA creating for client
        if context.user_type not in [UserType.CPA_TEAM, UserType.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only CPA team can create returns for other users"
            )
        target_user_id = request.client_user_id
        assigned_cpa_id = context.user_id

    # Check for existing return for same year
    check_query = text("""
        SELECT return_id FROM returns
        WHERE client_id = :client_id AND tax_year = :tax_year
    """)
    check_result = await session.execute(check_query, {
        "client_id": target_user_id,
        "tax_year": request.tax_year,
    })
    if check_result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tax return already exists for {request.tax_year}"
        )

    return_id = str(uuid4())
    now = datetime.utcnow()
    documents_required = 8 if request.return_type == TaxReturnType.INDIVIDUAL else 15

    insert_query = text("""
        INSERT INTO returns (
            return_id, client_id, firm_id, preparer_id, tax_year, return_type,
            workflow_stage, gross_income, adjusted_gross_income, taxable_income,
            total_tax, refund_amount, amount_due, completion_percentage,
            documents_uploaded, documents_required, created_at, updated_at
        ) VALUES (
            :return_id, :client_id, :firm_id, :preparer_id, :tax_year, :return_type,
            'intake', 0, 0, 0, 0, 0, 0, 0, 0, :documents_required, :created_at, :updated_at
        )
    """)

    await session.execute(insert_query, {
        "return_id": return_id,
        "client_id": target_user_id,
        "firm_id": firm_id,
        "preparer_id": assigned_cpa_id,
        "tax_year": request.tax_year,
        "return_type": request.return_type.value,
        "documents_required": documents_required,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"Tax return created: {return_id} for user {target_user_id} by {context.user_id}")

    return TaxReturn(
        id=return_id,
        user_id=target_user_id,
        firm_id=firm_id,
        assigned_cpa_id=assigned_cpa_id,
        tax_year=request.tax_year,
        return_type=request.return_type,
        status=TaxReturnStatus.DRAFT,
        created_at=now,
        updated_at=now,
        documents_required=documents_required,
    )


@router.patch("/{return_id}", response_model=TaxReturn)
async def update_tax_return(
    return_id: str,
    request: UpdateTaxReturnRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update a tax return.

    Access control:
    - Owner can update if not filed
    - Assigned CPA can update
    - Platform admins can update any return
    """
    # Get current return
    check_query = text("""
        SELECT client_id, firm_id, preparer_id, workflow_stage
        FROM returns WHERE return_id = :return_id
    """)
    check_result = await session.execute(check_query, {"return_id": return_id})
    row = check_result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tax return not found"
        )

    return_data = {
        "client_id": str(row[0]) if row[0] else None,
        "firm_id": str(row[1]) if row[1] else None,
        "preparer_id": str(row[2]) if row[2] else None,
        "workflow_stage": row[3],
    }

    if not _can_modify_return_data(context, return_data):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this tax return"
        )

    # Build update query
    updates = []
    params = {"return_id": return_id, "updated_at": datetime.utcnow().isoformat()}

    if request.status is not None:
        workflow_stage = _map_status_to_workflow(request.status.value)
        updates.append("workflow_stage = :workflow_stage")
        params["workflow_stage"] = workflow_stage
        if request.status == TaxReturnStatus.FILED:
            updates.append("completed_at = :updated_at")

    if request.gross_income is not None:
        updates.append("gross_income = :gross_income")
        params["gross_income"] = request.gross_income
    if request.adjusted_gross_income is not None:
        updates.append("adjusted_gross_income = :agi")
        params["agi"] = request.adjusted_gross_income
    if request.taxable_income is not None:
        updates.append("taxable_income = :taxable_income")
        params["taxable_income"] = request.taxable_income
    if request.total_tax is not None:
        updates.append("total_tax = :total_tax")
        params["total_tax"] = request.total_tax
    if request.refund_amount is not None:
        updates.append("refund_amount = :refund_amount")
        params["refund_amount"] = request.refund_amount
    if request.amount_due is not None:
        updates.append("amount_due = :amount_due")
        params["amount_due"] = request.amount_due
    if request.completion_percentage is not None:
        updates.append("completion_percentage = :completion_percentage")
        params["completion_percentage"] = request.completion_percentage

    if updates:
        updates.append("updated_at = :updated_at")
        # Validate all column names against whitelist before building query
        for clause in updates:
            col = clause.split("=")[0].strip()
            if col not in _RETURN_UPDATABLE_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Invalid field: {col}")
        update_query = text(f"UPDATE returns SET {', '.join(updates)} WHERE return_id = :return_id")
        await session.execute(update_query, params)
        await session.commit()

    logger.info(f"Tax return updated: {return_id} by {context.user_id}")

    # Return updated record
    return await get_tax_return(return_id, context, session)


@router.post("/{return_id}/submit")
async def submit_tax_return(
    return_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Submit tax return for review.

    Changes status from DRAFT/IN_PROGRESS to PENDING_REVIEW.
    """
    # Get current return
    check_query = text("""
        SELECT client_id, firm_id, preparer_id, workflow_stage
        FROM returns WHERE return_id = :return_id
    """)
    check_result = await session.execute(check_query, {"return_id": return_id})
    row = check_result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tax return not found"
        )

    return_data = {
        "client_id": str(row[0]) if row[0] else None,
        "firm_id": str(row[1]) if row[1] else None,
        "preparer_id": str(row[2]) if row[2] else None,
        "workflow_stage": row[3],
    }

    if not _can_modify_return_data(context, return_data):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot submit this tax return"
        )

    current_stage = row[3] or "intake"
    if current_stage not in ["intake", "document_collection", "preparation"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit return with stage {current_stage}"
        )

    now = datetime.utcnow()
    update_query = text("""
        UPDATE returns SET
            workflow_stage = 'review',
            submitted_at = :submitted_at,
            updated_at = :updated_at
        WHERE return_id = :return_id
    """)
    await session.execute(update_query, {
        "return_id": return_id,
        "submitted_at": now.isoformat(),
        "updated_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"Tax return submitted: {return_id} by {context.user_id}")

    return {"success": True, "message": "Tax return submitted for review"}


@router.delete("/{return_id}")
async def delete_tax_return(
    return_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Delete a tax return.

    Only draft returns can be deleted.
    """
    # Get current return
    check_query = text("""
        SELECT client_id, firm_id, preparer_id, workflow_stage
        FROM returns WHERE return_id = :return_id
    """)
    check_result = await session.execute(check_query, {"return_id": return_id})
    row = check_result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tax return not found"
        )

    return_data = {
        "client_id": str(row[0]) if row[0] else None,
        "firm_id": str(row[1]) if row[1] else None,
        "preparer_id": str(row[2]) if row[2] else None,
        "workflow_stage": row[3],
    }

    if not _can_modify_return_data(context, return_data):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete this tax return"
        )

    if row[3] != "intake":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft returns can be deleted"
        )

    delete_query = text("DELETE FROM returns WHERE return_id = :return_id")
    await session.execute(delete_query, {"return_id": return_id})
    await session.commit()

    logger.info(f"Tax return deleted: {return_id} by {context.user_id}")

    return {"success": True, "message": "Tax return deleted"}


# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

@router.get("/analytics/summary")
async def get_tax_return_analytics(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    tax_year: Optional[int] = None
):
    """
    Get tax return analytics.

    Access control:
    - Consumers/CPA Clients: Analytics for their own returns
    - CPA Team: Analytics for their firm
    - Platform Admins: Platform-wide analytics
    """
    # Build access conditions
    access_conditions, params = _build_access_conditions(context)

    if tax_year:
        access_conditions += " AND r.tax_year = :tax_year"
        params["tax_year"] = tax_year

    # Get aggregated stats
    query = text(f"""
        SELECT
            COUNT(*) as total,
            SUM(r.total_tax) as total_tax,
            SUM(r.refund_amount) as total_refunds,
            AVG(r.completion_percentage) as avg_completion
        FROM returns r
        WHERE {access_conditions}
    """)
    result = await session.execute(query, params)
    stats_row = result.fetchone()

    if not stats_row or stats_row[0] == 0:
        return {
            "total_returns": 0,
            "by_status": {},
            "by_type": {},
            "total_tax": 0,
            "total_refunds": 0,
            "average_completion": 0
        }

    # Get by status (workflow_stage)
    status_query = text(f"""
        SELECT r.workflow_stage, COUNT(*) as count
        FROM returns r
        WHERE {access_conditions}
        GROUP BY r.workflow_stage
    """)
    status_result = await session.execute(status_query, params)
    status_rows = status_result.fetchall()

    by_status = {}
    for row in status_rows:
        status_val = _map_workflow_to_status(row[0] or "intake")
        by_status[status_val] = by_status.get(status_val, 0) + row[1]

    # Get by type
    type_query = text(f"""
        SELECT r.return_type, COUNT(*) as count
        FROM returns r
        WHERE {access_conditions}
        GROUP BY r.return_type
    """)
    type_result = await session.execute(type_query, params)
    type_rows = type_result.fetchall()

    by_type = {}
    for row in type_rows:
        by_type[row[0] or "individual"] = row[1]

    return {
        "total_returns": stats_row[0] or 0,
        "by_status": by_status,
        "by_type": by_type,
        "total_tax": float(stats_row[1] or 0),
        "total_refunds": float(stats_row[2] or 0),
        "average_completion": float(stats_row[3] or 0)
    }
