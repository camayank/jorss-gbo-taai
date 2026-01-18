"""
Client Management Routes - Admin view of client operations.

Provides:
- Client listing and search
- Client assignment management
- Client status overview
- Bulk operations
"""

from typing import Optional, List
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..auth.rbac import (
    get_current_user,
    TenantContext,
    require_permission,
    require_firm_admin,
)
from ..models.user import UserPermission


router = APIRouter(tags=["Client Management"])


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
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List clients for the firm.

    Supports filtering by status, assignment, priority, and search.
    """
    # TODO: Implement actual query
    return [
        ClientSummary(
            client_id="client-1",
            name="Acme Corporation",
            email="accounting@acme.com",
            status="active",
            priority="high",
            assigned_to="user-1",
            assigned_name="John Smith",
            returns_count=3,
            last_activity=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
        ClientSummary(
            client_id="client-2",
            name="Smith Family Trust",
            email="trust@smithfamily.com",
            status="active",
            priority="medium",
            assigned_to="user-2",
            assigned_name="Sarah Johnson",
            returns_count=1,
            last_activity=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
        ClientSummary(
            client_id="client-3",
            name="Tech Startup Inc",
            email="cfo@techstartup.io",
            status="prospect",
            priority="high",
            assigned_to=None,
            assigned_name=None,
            returns_count=0,
            last_activity=None,
            created_at=datetime.utcnow(),
        ),
    ]


@router.get("/clients/{client_id}", response_model=ClientDetails)
@require_permission(UserPermission.VIEW_CLIENT)
async def get_client(
    client_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get detailed information about a client."""
    # TODO: Implement actual query
    return ClientDetails(
        client_id=client_id,
        name="Acme Corporation",
        email="accounting@acme.com",
        phone="555-0100",
        status="active",
        priority="high",
        assigned_to="user-1",
        assigned_name="John Smith",
        filing_status="C-Corp",
        estimated_income=1500000.0,
        source="lead_magnet",
        tags=["enterprise", "manufacturing", "multi-state"],
        notes="Key client - CEO referred by existing client. Very responsive.",
        returns_count=3,
        total_revenue=4500.0,
        last_activity=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )


# =============================================================================
# CLIENT ASSIGNMENT ROUTES
# =============================================================================

@router.get("/clients/unassigned")
@require_permission(UserPermission.MANAGE_CLIENT)
async def get_unassigned_clients(
    user: TenantContext = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
):
    """Get list of unassigned clients."""
    # TODO: Implement actual query
    return {
        "clients": [
            {
                "client_id": "client-3",
                "name": "Tech Startup Inc",
                "email": "cfo@techstartup.io",
                "status": "prospect",
                "priority": "high",
                "created_at": datetime.utcnow().isoformat(),
            },
        ],
        "total": 1,
    }


@router.post("/clients/assign")
@require_permission(UserPermission.MANAGE_CLIENT)
async def assign_clients(
    request: AssignmentRequest,
    user: TenantContext = Depends(get_current_user),
):
    """
    Assign clients to a team member.

    Can assign multiple clients at once.
    """
    # TODO: Implement actual assignment
    return {
        "status": "success",
        "assigned_count": len(request.client_ids),
        "assigned_to": request.user_id,
        "notification_sent": request.notify,
    }


@router.post("/clients/{client_id}/reassign")
@require_permission(UserPermission.MANAGE_CLIENT)
async def reassign_client(
    client_id: str,
    new_user_id: str = Query(..., description="User ID to reassign to"),
    reason: Optional[str] = Query(None, description="Reason for reassignment"),
    user: TenantContext = Depends(get_current_user),
):
    """Reassign a client to a different team member."""
    # TODO: Implement actual reassignment
    return {
        "status": "success",
        "client_id": client_id,
        "previous_assigned_to": "user-1",
        "new_assigned_to": new_user_id,
        "reason": reason,
    }


@router.get("/clients/assignment-summary")
@require_permission(UserPermission.VIEW_CLIENT)
async def get_assignment_summary(
    user: TenantContext = Depends(get_current_user),
):
    """Get summary of client assignments across team."""
    # TODO: Implement actual query
    return {
        "total_clients": 156,
        "unassigned": 5,
        "by_user": [
            {"user_id": "user-1", "name": "John Smith", "client_count": 45, "capacity": 50},
            {"user_id": "user-2", "name": "Sarah Johnson", "client_count": 52, "capacity": 60},
            {"user_id": "user-3", "name": "Mike Williams", "client_count": 38, "capacity": 50},
            {"user_id": "user-4", "name": "Emily Davis", "client_count": 16, "capacity": 40},
        ],
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

    # TODO: Implement actual update
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

    # TODO: Implement actual bulk update
    return {
        "status": "success",
        "updated_count": len(request.client_ids),
        "new_status": request.new_status,
    }


@router.patch("/clients/{client_id}/priority")
@require_permission(UserPermission.MANAGE_CLIENT)
async def update_client_priority(
    client_id: str,
    priority: str = Query(..., description="New priority level"),
    user: TenantContext = Depends(get_current_user),
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

    # TODO: Implement actual update
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
):
    """Get client metrics for dashboard."""
    # TODO: Implement actual metrics
    return {
        "total_clients": 156,
        "by_status": {
            "active": 120,
            "inactive": 15,
            "prospect": 18,
            "onboarding": 3,
        },
        "by_priority": {
            "high": 35,
            "medium": 85,
            "low": 36,
        },
        "growth": {
            "this_month": 8,
            "last_month": 12,
            "change_percent": -33.3,
        },
        "churn": {
            "this_quarter": 5,
            "rate_percent": 3.2,
        },
    }


@router.get("/clients/revenue-summary")
@require_permission(UserPermission.VIEW_BILLING)
async def get_client_revenue_summary(
    user: TenantContext = Depends(get_current_user),
    period: str = Query("year", description="Period: month, quarter, year"),
):
    """Get revenue summary by client."""
    # TODO: Implement actual revenue tracking
    return {
        "period": period,
        "total_revenue": 485000.0,
        "top_clients": [
            {"client_id": "client-1", "name": "Acme Corporation", "revenue": 45000.0},
            {"client_id": "client-5", "name": "Big Enterprise LLC", "revenue": 38000.0},
            {"client_id": "client-8", "name": "Real Estate Holdings", "revenue": 32000.0},
        ],
        "by_service": {
            "tax_returns": 325000.0,
            "advisory": 95000.0,
            "planning": 65000.0,
        },
        "avg_revenue_per_client": 3109.0,
    }


# =============================================================================
# CLIENT SEARCH AND EXPORT
# =============================================================================

@router.get("/clients/search")
@require_permission(UserPermission.VIEW_CLIENT)
async def search_clients(
    q: str = Query(..., min_length=2, description="Search query"),
    user: TenantContext = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=50),
):
    """Quick search for clients by name, email, or ID."""
    # TODO: Implement actual search
    return {
        "query": q,
        "results": [
            {
                "client_id": "client-1",
                "name": "Acme Corporation",
                "email": "accounting@acme.com",
                "status": "active",
                "match_field": "name",
            },
        ],
        "total": 1,
    }


@router.post("/clients/export")
@require_firm_admin
async def export_clients(
    user: TenantContext = Depends(get_current_user),
    format: str = Query("csv", description="Export format: csv, xlsx"),
    include_sensitive: bool = Query(False, description="Include sensitive data"),
):
    """
    Export client list.

    Requires firm admin permission. Sensitive data export is logged.
    """
    # TODO: Implement actual export
    return {
        "status": "success",
        "format": format,
        "client_count": 156,
        "download_url": f"/api/v1/admin/clients/export/download/clients-{user.firm_id}.{format}",
        "expires_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# CLIENT TAGS ROUTES
# =============================================================================

@router.get("/clients/tags")
@require_permission(UserPermission.VIEW_CLIENT)
async def list_client_tags(
    user: TenantContext = Depends(get_current_user),
):
    """Get all tags used across clients."""
    # TODO: Implement actual query
    return {
        "tags": [
            {"name": "enterprise", "count": 15},
            {"name": "small-business", "count": 85},
            {"name": "individual", "count": 45},
            {"name": "multi-state", "count": 28},
            {"name": "manufacturing", "count": 12},
            {"name": "real-estate", "count": 18},
            {"name": "high-net-worth", "count": 22},
        ],
    }


@router.patch("/clients/{client_id}/tags")
@require_permission(UserPermission.MANAGE_CLIENT)
async def update_client_tags(
    client_id: str,
    tags: List[str] = Query(..., description="New tags list"),
    user: TenantContext = Depends(get_current_user),
):
    """Update tags for a client."""
    # TODO: Implement actual update
    return {
        "status": "success",
        "client_id": client_id,
        "tags": tags,
    }
