"""
Client Management Routes - Admin view of client operations.

Provides:
- Client listing and search
- Client assignment management
- Client status overview
- Bulk operations

All routes use database-backed queries.
"""

import json
import logging
from typing import Optional, List
from datetime import datetime
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.rbac import (
    get_current_user,
    get_current_firm,
    TenantContext,
    require_permission,
    require_firm_admin,
)
from ..models.user import UserPermission
from database.async_engine import get_async_session
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal


router = APIRouter(tags=["Client Management"])
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND MODELS
# =============================================================================

class ClientStatus(str, Enum):
    """Client status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PROSPECT = "prospect"
    CHURNED = "churned"
    ONBOARDING = "onboarding"


class ClientPriority(str, Enum):
    """Client priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClientSummary(BaseModel):
    """Client summary for list view."""
    client_id: str
    name: str
    email: Optional[str]
    status: str
    priority: str
    assigned_to: Optional[str]
    assigned_name: Optional[str]
    returns_count: int
    last_activity: Optional[datetime]
    created_at: datetime


class ClientDetails(BaseModel):
    """Detailed client information."""
    client_id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    status: str
    priority: str
    assigned_to: Optional[str]
    assigned_name: Optional[str]
    filing_status: Optional[str]
    estimated_income: Optional[float]
    source: Optional[str]
    tags: List[str]
    notes: Optional[str]
    returns_count: int
    total_revenue: float
    last_activity: Optional[datetime]
    created_at: datetime


class AssignmentRequest(BaseModel):
    """Request to assign clients."""
    client_ids: List[str]
    user_id: str
    notify: bool = True


class BulkStatusRequest(BaseModel):
    """Request to update status in bulk."""
    client_ids: List[str]
    new_status: str


# =============================================================================
# CLIENT LISTING ROUTES
# =============================================================================

@router.get("/clients", response_model=List[ClientSummary])
@require_permission(UserPermission.VIEW_CLIENT)
async def list_clients(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
):
    """
    List clients for the firm.

    Supports filtering by status, assignment, priority, and search.
    """
    # Build conditions
    conditions = ["u.firm_id = :firm_id"]
    params = {"firm_id": firm_id, "limit": limit, "offset": offset}

    if status_filter:
        conditions.append("c.status = :status")
        params["status"] = status_filter

    if assigned_to:
        conditions.append("c.preparer_id = :assigned_to")
        params["assigned_to"] = assigned_to

    if priority:
        conditions.append("c.priority = :priority")
        params["priority"] = priority

    if search:
        conditions.append("(c.first_name ILIKE :search OR c.last_name ILIKE :search OR c.email ILIKE :search)")
        params["search"] = f"%{search}%"

    where_clause = " AND ".join(conditions)

    # Validate sort field
    valid_sort_fields = {"created_at", "first_name", "last_name", "email", "status", "priority"}
    if sort_by not in valid_sort_fields:
        sort_by = "created_at"
    sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

    query = text(f"""
        SELECT c.client_id, c.first_name, c.last_name, c.email, c.status, c.priority,
               c.preparer_id, p.first_name || ' ' || p.last_name as preparer_name,
               (SELECT COUNT(*) FROM returns r WHERE r.client_id = c.client_id) as returns_count,
               c.last_activity_at, c.created_at
        FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        LEFT JOIN users p ON c.preparer_id = p.user_id
        WHERE {where_clause}
        ORDER BY c.{sort_by} {sort_dir}
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    clients = []
    for row in rows:
        # Parse dates
        def parse_dt(val):
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(val.replace('Z', '+00:00'))

        clients.append(ClientSummary(
            client_id=str(row[0]),
            name=f"{row[1]} {row[2]}".strip(),
            email=row[3],
            status=row[4] or "active",
            priority=row[5] or "medium",
            assigned_to=str(row[6]) if row[6] else None,
            assigned_name=row[7],
            returns_count=row[8] or 0,
            last_activity=parse_dt(row[9]),
            created_at=parse_dt(row[10]) or datetime.utcnow(),
        ))

    return clients


@router.get("/clients/{client_id}", response_model=ClientDetails)
@require_permission(UserPermission.VIEW_CLIENT)
async def get_client(
    client_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get detailed information about a client."""
    query = text("""
        SELECT c.client_id, c.first_name, c.last_name, c.email, c.phone,
               c.status, c.priority, c.preparer_id,
               p.first_name || ' ' || p.last_name as preparer_name,
               c.filing_status, c.estimated_income, c.source,
               c.tags, c.notes, c.created_at, c.last_activity_at,
               (SELECT COUNT(*) FROM returns r WHERE r.client_id = c.client_id) as returns_count,
               (SELECT COALESCE(SUM(fee_amount), 0) FROM returns r WHERE r.client_id = c.client_id) as total_revenue
        FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        LEFT JOIN users p ON c.preparer_id = p.user_id
        WHERE c.client_id = :client_id AND u.firm_id = :firm_id
    """)

    result = await session.execute(query, {"client_id": client_id, "firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    # Parse dates
    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    tags = json.loads(row[12]) if row[12] else []

    return ClientDetails(
        client_id=str(row[0]),
        name=f"{row[1]} {row[2]}".strip(),
        email=row[3],
        phone=row[4],
        status=row[5] or "active",
        priority=row[6] or "medium",
        assigned_to=str(row[7]) if row[7] else None,
        assigned_name=row[8],
        filing_status=row[9],
        estimated_income=float(row[10]) if row[10] else None,
        source=row[11],
        tags=tags,
        notes=row[13],
        returns_count=row[16] or 0,
        total_revenue=float(row[17]) if row[17] else 0.0,
        last_activity=parse_dt(row[15]),
        created_at=parse_dt(row[14]) or datetime.utcnow(),
    )


# =============================================================================
# CLIENT ASSIGNMENT ROUTES
# =============================================================================

@router.get("/clients/unassigned")
@require_permission(UserPermission.MANAGE_CLIENT)
async def get_unassigned_clients(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
):
    """Get list of unassigned clients."""
    query = text("""
        SELECT c.client_id, c.first_name, c.last_name, c.email, c.status,
               c.priority, c.created_at
        FROM clients c
        WHERE c.preparer_id IS NULL
        AND EXISTS (
            SELECT 1 FROM users u WHERE u.firm_id = :firm_id
            AND (c.source_firm_id = :firm_id OR c.source_firm_id IS NULL)
        )
        ORDER BY c.created_at DESC
        LIMIT :limit
    """)

    result = await session.execute(query, {"firm_id": firm_id, "limit": limit})
    rows = result.fetchall()

    clients = []
    for row in rows:
        created_at = row[6]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        clients.append({
            "client_id": str(row[0]),
            "name": f"{row[1]} {row[2]}".strip(),
            "email": row[3],
            "status": row[4] or "prospect",
            "priority": row[5] or "medium",
            "created_at": created_at.isoformat() if created_at else datetime.utcnow().isoformat(),
        })

    # Get total count
    count_query = text("""
        SELECT COUNT(*) FROM clients c
        WHERE c.preparer_id IS NULL
        AND EXISTS (
            SELECT 1 FROM users u WHERE u.firm_id = :firm_id
            AND (c.source_firm_id = :firm_id OR c.source_firm_id IS NULL)
        )
    """)
    count_result = await session.execute(count_query, {"firm_id": firm_id})
    total = count_result.fetchone()[0] or 0

    return {
        "clients": clients,
        "total": total,
    }


@router.post("/clients/assign")
@require_permission(UserPermission.MANAGE_CLIENT)
async def assign_clients(
    request: AssignmentRequest,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Assign clients to a team member.

    Can assign multiple clients at once.
    """
    # Verify target user belongs to firm
    user_check = text("""
        SELECT user_id, first_name, last_name FROM users
        WHERE user_id = :user_id AND firm_id = :firm_id AND is_active = true
    """)
    user_result = await session.execute(user_check, {"user_id": request.user_id, "firm_id": firm_id})
    target_user = user_result.fetchone()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found or not active in this firm",
        )

    # Update clients
    now = datetime.utcnow().isoformat()
    assigned_count = 0

    for client_id in request.client_ids:
        update_query = text("""
            UPDATE clients SET
                preparer_id = :preparer_id,
                assigned_at = :assigned_at,
                updated_at = :updated_at
            WHERE client_id = :client_id
        """)
        result = await session.execute(update_query, {
            "client_id": client_id,
            "preparer_id": request.user_id,
            "assigned_at": now,
            "updated_at": now,
        })
        if result.rowcount > 0:
            assigned_count += 1

    await session.commit()
    logger.info(f"Assigned {assigned_count} clients to {request.user_id} by {user.email}")

    # FREEZE & FINISH: Email notifications deferred to Phase 2
    # Manual notification recommended for now
    notification_msg = None
    if request.notify:
        notification_msg = "Email notifications coming soon. Please notify the assignee manually."
        logger.info(f"Notification requested but email service not available - manual notification needed for {request.user_id}")

    return {
        "status": "success",
        "assigned_count": assigned_count,
        "assigned_to": request.user_id,
        "assigned_name": f"{target_user[1]} {target_user[2]}",
        "notification_sent": False,
        "notification_note": notification_msg or "No notification requested",
    }


@router.post("/clients/{client_id}/reassign")
@require_permission(UserPermission.MANAGE_CLIENT)
async def reassign_client(
    client_id: str,
    new_user_id: str = Query(..., description="User ID to reassign to"),
    reason: Optional[str] = Query(None, description="Reason for reassignment"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Reassign a client to a different team member."""
    # Get current assignment
    client_query = text("""
        SELECT c.preparer_id, p.first_name || ' ' || p.last_name as old_name
        FROM clients c
        LEFT JOIN users p ON c.preparer_id = p.user_id
        JOIN users u ON c.preparer_id = u.user_id
        WHERE c.client_id = :client_id AND u.firm_id = :firm_id
    """)
    client_result = await session.execute(client_query, {"client_id": client_id, "firm_id": firm_id})
    client_row = client_result.fetchone()

    if not client_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    previous_id = str(client_row[0]) if client_row[0] else None

    # Verify new user belongs to firm
    new_user_query = text("""
        SELECT user_id, first_name || ' ' || last_name as name FROM users
        WHERE user_id = :user_id AND firm_id = :firm_id AND is_active = true
    """)
    new_user_result = await session.execute(new_user_query, {"user_id": new_user_id, "firm_id": firm_id})
    new_user_row = new_user_result.fetchone()

    if not new_user_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found or not active in this firm",
        )

    # Update assignment
    now = datetime.utcnow().isoformat()
    update_query = text("""
        UPDATE clients SET
            preparer_id = :new_preparer_id,
            assigned_at = :assigned_at,
            updated_at = :updated_at
        WHERE client_id = :client_id
    """)
    await session.execute(update_query, {
        "client_id": client_id,
        "new_preparer_id": new_user_id,
        "assigned_at": now,
        "updated_at": now,
    })

    # Log reassignment
    log_id = str(uuid4())
    log_query = text("""
        INSERT INTO audit_logs (
            log_id, firm_id, user_id, action, resource_type, resource_id,
            details, created_at
        ) VALUES (
            :log_id, :firm_id, :user_id, 'client_reassigned', 'client', :client_id,
            :details, :created_at
        )
    """)
    await session.execute(log_query, {
        "log_id": log_id,
        "firm_id": firm_id,
        "user_id": user.user_id,
        "client_id": client_id,
        "details": json.dumps({
            "previous_assigned_to": previous_id,
            "new_assigned_to": new_user_id,
            "reason": reason,
        }),
        "created_at": now,
    })

    await session.commit()
    logger.info(f"Client {client_id} reassigned from {previous_id} to {new_user_id} by {user.email}")

    return {
        "status": "success",
        "client_id": client_id,
        "previous_assigned_to": previous_id,
        "previous_name": client_row[1],
        "new_assigned_to": new_user_id,
        "new_name": new_user_row[1],
        "reason": reason,
    }


@router.get("/clients/assignment-summary")
@require_permission(UserPermission.VIEW_CLIENT)
async def get_assignment_summary(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get summary of client assignments across team."""
    # Get total clients count
    total_query = text("""
        SELECT COUNT(*) FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
    """)
    total_result = await session.execute(total_query, {"firm_id": firm_id})
    total_clients = total_result.fetchone()[0] or 0

    # Get unassigned count
    unassigned_query = text("""
        SELECT COUNT(*) FROM clients c
        WHERE c.preparer_id IS NULL
        AND (c.source_firm_id = :firm_id OR c.source_firm_id IS NULL)
    """)
    unassigned_result = await session.execute(unassigned_query, {"firm_id": firm_id})
    unassigned = unassigned_result.fetchone()[0] or 0

    # Get assignments by user
    by_user_query = text("""
        SELECT u.user_id, u.first_name || ' ' || u.last_name as name,
               COUNT(c.client_id) as client_count,
               COALESCE(u.client_capacity, 50) as capacity
        FROM users u
        LEFT JOIN clients c ON u.user_id = c.preparer_id
        WHERE u.firm_id = :firm_id AND u.is_active = true
        GROUP BY u.user_id, u.first_name, u.last_name, u.client_capacity
        ORDER BY client_count DESC
    """)
    by_user_result = await session.execute(by_user_query, {"firm_id": firm_id})
    by_user_rows = by_user_result.fetchall()

    by_user = []
    for row in by_user_rows:
        by_user.append({
            "user_id": str(row[0]),
            "name": row[1],
            "client_count": row[2] or 0,
            "capacity": row[3] or 50,
        })

    return {
        "total_clients": total_clients,
        "unassigned": unassigned,
        "by_user": by_user,
    }


# =============================================================================
# CLIENT STATUS ROUTES
# =============================================================================

@router.patch("/clients/{client_id}/status")
@require_permission(UserPermission.MANAGE_CLIENT)
async def update_client_status(
    client_id: str,
    new_status: str = Query(..., description="New status value"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update a client's status."""
    # Validate status
    try:
        ClientStatus(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in ClientStatus]}",
        )

    # Verify client belongs to firm
    check_query = text("""
        SELECT c.client_id FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE c.client_id = :client_id AND u.firm_id = :firm_id
    """)
    check_result = await session.execute(check_query, {"client_id": client_id, "firm_id": firm_id})
    if not check_result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    # Update status
    update_query = text("""
        UPDATE clients SET status = :status, updated_at = :updated_at
        WHERE client_id = :client_id
    """)
    await session.execute(update_query, {
        "client_id": client_id,
        "status": new_status,
        "updated_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    logger.info(f"Client {client_id} status updated to {new_status} by {user.email}")

    return {
        "status": "success",
        "client_id": client_id,
        "new_status": new_status,
    }


@router.post("/clients/bulk-status")
@require_permission(UserPermission.MANAGE_CLIENT)
async def bulk_update_status(
    request: BulkStatusRequest,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update status for multiple clients at once."""
    # Validate status
    try:
        ClientStatus(request.new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in ClientStatus]}",
        )

    now = datetime.utcnow().isoformat()
    updated_count = 0

    for client_id in request.client_ids:
        # Only update clients belonging to firm
        update_query = text("""
            UPDATE clients SET status = :status, updated_at = :updated_at
            WHERE client_id = :client_id
            AND EXISTS (
                SELECT 1 FROM users u WHERE u.user_id = clients.preparer_id AND u.firm_id = :firm_id
            )
        """)
        result = await session.execute(update_query, {
            "client_id": client_id,
            "status": request.new_status,
            "updated_at": now,
            "firm_id": firm_id,
        })
        if result.rowcount > 0:
            updated_count += 1

    await session.commit()
    logger.info(f"Bulk status update: {updated_count} clients set to {request.new_status} by {user.email}")

    return {
        "status": "success",
        "updated_count": updated_count,
        "new_status": request.new_status,
    }


@router.patch("/clients/{client_id}/priority")
@require_permission(UserPermission.MANAGE_CLIENT)
async def update_client_priority(
    client_id: str,
    priority: str = Query(..., description="New priority level"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update a client's priority level."""
    # Validate priority
    try:
        ClientPriority(priority)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority. Must be one of: {[p.value for p in ClientPriority]}",
        )

    # Verify client belongs to firm
    check_query = text("""
        SELECT c.client_id FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE c.client_id = :client_id AND u.firm_id = :firm_id
    """)
    check_result = await session.execute(check_query, {"client_id": client_id, "firm_id": firm_id})
    if not check_result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    # Update priority
    update_query = text("""
        UPDATE clients SET priority = :priority, updated_at = :updated_at
        WHERE client_id = :client_id
    """)
    await session.execute(update_query, {
        "client_id": client_id,
        "priority": priority,
        "updated_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    logger.info(f"Client {client_id} priority updated to {priority} by {user.email}")

    return {
        "status": "success",
        "client_id": client_id,
        "new_priority": priority,
    }


# =============================================================================
# CLIENT METRICS ROUTES
# =============================================================================

@router.get("/clients/metrics")
@require_permission(UserPermission.VIEW_CLIENT)
async def get_client_metrics(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get client metrics for dashboard."""
    # Get total count and by status
    status_query = text("""
        SELECT c.status, COUNT(*) as count
        FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        GROUP BY c.status
    """)
    status_result = await session.execute(status_query, {"firm_id": firm_id})
    status_rows = status_result.fetchall()

    by_status = {"active": 0, "inactive": 0, "prospect": 0, "onboarding": 0, "churned": 0}
    total_clients = 0
    for row in status_rows:
        status_val = row[0] or "active"
        count = row[1] or 0
        by_status[status_val] = count
        total_clients += count

    # Get by priority
    priority_query = text("""
        SELECT c.priority, COUNT(*) as count
        FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        GROUP BY c.priority
    """)
    priority_result = await session.execute(priority_query, {"firm_id": firm_id})
    priority_rows = priority_result.fetchall()

    by_priority = {"high": 0, "medium": 0, "low": 0}
    for row in priority_rows:
        priority_val = row[0] or "medium"
        by_priority[priority_val] = row[1] or 0

    # Get growth metrics
    growth_query = text("""
        SELECT
            (SELECT COUNT(*) FROM clients c JOIN users u ON c.preparer_id = u.user_id
             WHERE u.firm_id = :firm_id AND c.created_at >= DATE_TRUNC('month', NOW())) as this_month,
            (SELECT COUNT(*) FROM clients c JOIN users u ON c.preparer_id = u.user_id
             WHERE u.firm_id = :firm_id
             AND c.created_at >= DATE_TRUNC('month', NOW() - INTERVAL '1 month')
             AND c.created_at < DATE_TRUNC('month', NOW())) as last_month
    """)
    growth_result = await session.execute(growth_query, {"firm_id": firm_id})
    growth_row = growth_result.fetchone()

    this_month = growth_row[0] or 0
    last_month = growth_row[1] or 0
    change_percent = ((this_month - last_month) / last_month * 100) if last_month > 0 else 0

    # Get churn metrics
    churn_query = text("""
        SELECT COUNT(*) FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND c.status = 'churned'
        AND c.updated_at >= DATE_TRUNC('quarter', NOW())
    """)
    churn_result = await session.execute(churn_query, {"firm_id": firm_id})
    churn_count = churn_result.fetchone()[0] or 0
    churn_rate = (churn_count / total_clients * 100) if total_clients > 0 else 0

    return {
        "total_clients": total_clients,
        "by_status": by_status,
        "by_priority": by_priority,
        "growth": {
            "this_month": this_month,
            "last_month": last_month,
            "change_percent": round(change_percent, 1),
        },
        "churn": {
            "this_quarter": churn_count,
            "rate_percent": round(churn_rate, 1),
        },
    }


@router.get("/clients/revenue-summary")
@require_permission(UserPermission.VIEW_BILLING)
async def get_client_revenue_summary(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    period: str = Query("year", description="Period: month, quarter, year"),
    session: AsyncSession = Depends(get_async_session),
):
    """Get revenue summary by client."""
    # Determine date range
    period_intervals = {
        "month": "1 month",
        "quarter": "3 months",
        "year": "12 months",
    }
    interval = period_intervals.get(period, "12 months")

    # Get total revenue
    total_query = text(f"""
        SELECT COALESCE(SUM(r.fee_amount), 0) as total
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.created_at >= NOW() - INTERVAL '{interval}'
    """)
    total_result = await session.execute(total_query, {"firm_id": firm_id})
    total_revenue = float(total_result.fetchone()[0] or 0)

    # Get top clients by revenue
    top_query = text(f"""
        SELECT c.client_id, c.first_name || ' ' || c.last_name as name,
               COALESCE(SUM(r.fee_amount), 0) as revenue
        FROM clients c
        JOIN returns r ON c.client_id = r.client_id
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.created_at >= NOW() - INTERVAL '{interval}'
        GROUP BY c.client_id, c.first_name, c.last_name
        ORDER BY revenue DESC
        LIMIT 5
    """)
    top_result = await session.execute(top_query, {"firm_id": firm_id})
    top_rows = top_result.fetchall()

    top_clients = []
    for row in top_rows:
        top_clients.append({
            "client_id": str(row[0]),
            "name": row[1],
            "revenue": float(row[2]) if row[2] else 0.0,
        })

    # Get revenue by service type
    service_query = text(f"""
        SELECT r.return_type, COALESCE(SUM(r.fee_amount), 0) as revenue
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.created_at >= NOW() - INTERVAL '{interval}'
        GROUP BY r.return_type
    """)
    service_result = await session.execute(service_query, {"firm_id": firm_id})
    service_rows = service_result.fetchall()

    by_service = {}
    for row in service_rows:
        service_type = row[0] or "other"
        by_service[service_type] = float(row[1]) if row[1] else 0.0

    # Get client count for average
    client_count_query = text("""
        SELECT COUNT(DISTINCT c.client_id)
        FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id AND c.status = 'active'
    """)
    client_count_result = await session.execute(client_count_query, {"firm_id": firm_id})
    client_count = client_count_result.fetchone()[0] or 0
    avg_revenue = (total_revenue / client_count) if client_count > 0 else 0

    return {
        "period": period,
        "total_revenue": float(money(total_revenue)),
        "top_clients": top_clients,
        "by_service": by_service,
        "avg_revenue_per_client": float(money(avg_revenue)),
    }


# =============================================================================
# CLIENT SEARCH AND EXPORT
# =============================================================================

@router.get("/clients/search")
@require_permission(UserPermission.VIEW_CLIENT)
async def search_clients(
    q: str = Query(..., min_length=2, description="Search query"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    limit: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_async_session),
):
    """Quick search for clients by name, email, or ID."""
    search_term = f"%{q}%"

    query = text("""
        SELECT c.client_id, c.first_name, c.last_name, c.email, c.status,
               CASE
                   WHEN c.client_id::text ILIKE :search THEN 'id'
                   WHEN c.email ILIKE :search THEN 'email'
                   ELSE 'name'
               END as match_field
        FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND (
            c.first_name ILIKE :search
            OR c.last_name ILIKE :search
            OR c.email ILIKE :search
            OR c.client_id::text ILIKE :search
        )
        ORDER BY
            CASE WHEN c.email ILIKE :search THEN 0
                 WHEN c.first_name ILIKE :search OR c.last_name ILIKE :search THEN 1
                 ELSE 2 END,
            c.first_name
        LIMIT :limit
    """)

    result = await session.execute(query, {
        "firm_id": firm_id,
        "search": search_term,
        "limit": limit,
    })
    rows = result.fetchall()

    results = []
    for row in rows:
        results.append({
            "client_id": str(row[0]),
            "name": f"{row[1]} {row[2]}".strip(),
            "email": row[3],
            "status": row[4] or "active",
            "match_field": row[5],
        })

    return {
        "query": q,
        "results": results,
        "total": len(results),
    }


@router.post("/clients/export")
@require_firm_admin
async def export_clients(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    format: str = Query("csv", description="Export format: csv, xlsx"),
    include_sensitive: bool = Query(False, description="Include sensitive data"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Export client list.

    Requires firm admin permission. Sensitive data export is logged.
    """
    # Get client count
    count_query = text("""
        SELECT COUNT(*) FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
    """)
    count_result = await session.execute(count_query, {"firm_id": firm_id})
    client_count = count_result.fetchone()[0] or 0

    # Log the export request
    log_id = str(uuid4())
    log_query = text("""
        INSERT INTO audit_logs (
            log_id, firm_id, user_id, action, resource_type, resource_id,
            details, created_at
        ) VALUES (
            :log_id, :firm_id, :user_id, 'client_export', 'client', :firm_id,
            :details, :created_at
        )
    """)
    await session.execute(log_query, {
        "log_id": log_id,
        "firm_id": firm_id,
        "user_id": user.user_id,
        "details": json.dumps({
            "format": format,
            "include_sensitive": include_sensitive,
            "client_count": client_count,
        }),
        "created_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    logger.info(f"Client export requested by {user.email}: {client_count} clients, format={format}")

    # Generate CSV export
    import csv
    import io
    import tempfile

    columns = ["client_id", "first_name", "last_name", "email", "phone", "status", "created_at"]
    if include_sensitive:
        columns.extend(["ssn_last4", "address"])

    cols_sql = ", ".join(f"c.{col}" for col in columns if col != "ssn_last4" and col != "address")
    export_query = text(f"""
        SELECT {cols_sql} FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        ORDER BY c.last_name, c.first_name
    """)
    export_result = await session.execute(export_query, {"firm_id": firm_id})
    rows = export_result.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)

    csv_content = output.getvalue()
    output.close()

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8")),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=clients-{firm_id}.csv",
        },
    )


# =============================================================================
# CLIENT TAGS ROUTES
# =============================================================================

@router.get("/clients/tags")
@require_permission(UserPermission.VIEW_CLIENT)
async def list_client_tags(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get all tags used across clients."""
    # Query to extract and count tags from JSONB array
    query = text("""
        SELECT tag, COUNT(*) as count
        FROM (
            SELECT jsonb_array_elements_text(c.tags) as tag
            FROM clients c
            JOIN users u ON c.preparer_id = u.user_id
            WHERE u.firm_id = :firm_id AND c.tags IS NOT NULL
        ) as tag_data
        GROUP BY tag
        ORDER BY count DESC
    """)

    result = await session.execute(query, {"firm_id": firm_id})
    rows = result.fetchall()

    tags = []
    for row in rows:
        tags.append({
            "name": row[0],
            "count": row[1] or 0,
        })

    return {"tags": tags}


@router.patch("/clients/{client_id}/tags")
@require_permission(UserPermission.MANAGE_CLIENT)
async def update_client_tags(
    client_id: str,
    tags: List[str] = Query(..., description="New tags list"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update tags for a client."""
    # Verify client belongs to firm
    check_query = text("""
        SELECT c.client_id FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE c.client_id = :client_id AND u.firm_id = :firm_id
    """)
    check_result = await session.execute(check_query, {"client_id": client_id, "firm_id": firm_id})
    if not check_result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    # Update tags
    update_query = text("""
        UPDATE clients SET tags = :tags, updated_at = :updated_at
        WHERE client_id = :client_id
    """)
    await session.execute(update_query, {
        "client_id": client_id,
        "tags": json.dumps(tags),
        "updated_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    logger.info(f"Client {client_id} tags updated by {user.email}")

    return {
        "status": "success",
        "client_id": client_id,
        "tags": tags,
    }
