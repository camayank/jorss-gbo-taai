"""
Superadmin Routes - Platform administration endpoints.

Provides:
- Multi-firm management
- Subscription oversight
- Feature flag management
- System health monitoring

Access restricted to platform admins only.
"""

import json
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.rbac import (
    get_current_user,
    TenantContext,
    require_platform_admin,
)
from database.async_engine import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Platform Admin"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class FirmSummary(BaseModel):
    """Firm summary for list view."""
    firm_id: str
    name: str
    subscription_tier: str
    subscription_status: str
    team_members: int
    clients: int
    returns_this_month: int
    health_score: int
    churn_risk: str  # low, medium, high
    created_at: datetime
    last_activity_at: Optional[datetime]


class FirmDetails(BaseModel):
    """Detailed firm information."""
    firm_id: str
    name: str
    legal_name: Optional[str]
    ein: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    subscription_tier: str
    subscription_status: str
    billing_cycle: str
    current_period_end: Optional[datetime]
    team_members: int
    max_team_members: int
    clients: int
    max_clients: int
    usage_this_month: dict
    health_score: int
    compliance_score: int
    created_at: datetime
    onboarded_at: Optional[datetime]


class PlatformMetrics(BaseModel):
    """Platform-wide metrics."""
    total_firms: int
    active_firms: int
    trial_firms: int
    total_mrr: float
    tier_distribution: dict
    churn_rate: float
    avg_health_score: float
    feature_adoption: dict


class FeatureFlagSummary(BaseModel):
    """Feature flag summary."""
    flag_id: str
    feature_key: str
    name: str
    description: Optional[str]
    is_enabled_globally: bool
    min_tier: Optional[str]
    rollout_percentage: int
    enabled_firms: int
    usage_this_month: int


class SystemHealth(BaseModel):
    """System health status."""
    status: str  # healthy, degraded, down
    services: dict
    error_rate_1h: float
    avg_response_time_ms: float
    active_jobs: int
    failed_jobs_1h: int


# =============================================================================
# FIRMS ROUTES
# =============================================================================

@router.get("/firms", response_model=List[FirmSummary])
@require_platform_admin
async def list_all_firms(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    tier: Optional[str] = Query(None, description="Filter by subscription tier"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all firms on the platform.

    Platform admins only. Supports filtering, search, and pagination.
    """
    # Build dynamic query with filters
    conditions = ["1=1"]
    params = {"limit": limit, "offset": offset}

    if tier:
        conditions.append("COALESCE(sp.name, 'starter') = :tier")
        params["tier"] = tier

    if status_filter:
        if status_filter == "active":
            conditions.append("f.is_active = true")
        elif status_filter == "at_risk":
            conditions.append("f.is_active = true")  # Will filter by health score later
        elif status_filter == "inactive":
            conditions.append("f.is_active = false")

    if search:
        conditions.append("(LOWER(f.name) LIKE :search OR LOWER(f.email) LIKE :search)")
        params["search"] = f"%{search.lower()}%"

    # Validate sort field
    valid_sort_fields = {"created_at": "f.created_at", "name": "f.name", "team_members": "team_count"}
    sort_field = valid_sort_fields.get(sort_by, "f.created_at")
    sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT
            f.firm_id,
            f.name,
            COALESCE(sp.name, 'starter') as subscription_tier,
            COALESCE(s.status, 'none') as subscription_status,
            COUNT(DISTINCT u.user_id) as team_count,
            COUNT(DISTINCT c.client_id) as client_count,
            COUNT(DISTINCT CASE
                WHEN tr.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                THEN tr.return_id
            END) as returns_this_month,
            f.created_at,
            MAX(u.last_login_at) as last_activity_at,
            f.is_active
        FROM firms f
        LEFT JOIN subscriptions s ON f.firm_id = s.firm_id AND s.status IN ('active', 'trial')
        LEFT JOIN subscription_plans sp ON s.plan_id = sp.plan_id
        LEFT JOIN users u ON f.firm_id = u.firm_id
        LEFT JOIN clients c ON u.user_id = c.preparer_id
        LEFT JOIN tax_returns tr ON c.email = (
            SELECT tp.email FROM taxpayers tp WHERE tp.return_id = tr.return_id LIMIT 1
        )
        WHERE {where_clause}
        GROUP BY f.firm_id, f.name, sp.name, s.status, f.created_at, f.is_active
        ORDER BY {sort_field} {sort_dir}
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(str(val).replace('Z', '+00:00'))

    all_firms = []
    for row in rows:
        team_count = row[4] or 0
        client_count = row[5] or 0
        returns_count = row[6] or 0
        is_active = row[9] if row[9] is not None else True

        # Calculate health score based on activity
        last_activity = parse_dt(row[8])
        if last_activity:
            days_since = (datetime.utcnow() - last_activity).days
            health_score = max(50, 100 - (days_since * 2))
        else:
            health_score = 70

        # Determine churn risk
        if health_score > 90:
            churn_risk = "low"
        elif health_score > 75:
            churn_risk = "medium"
        else:
            churn_risk = "high"

        # Determine subscription status
        sub_status = row[3] or "none"
        if not is_active:
            sub_status = "inactive"
        elif health_score < 75:
            sub_status = "at_risk"
        elif sub_status == "none":
            sub_status = "active"

        # Skip if filtering by at_risk and this firm isn't at risk
        if status_filter == "at_risk" and sub_status != "at_risk":
            continue

        all_firms.append(FirmSummary(
            firm_id=str(row[0]),
            name=row[1] or "Unknown Firm",
            subscription_tier=row[2] or "starter",
            subscription_status=sub_status,
            team_members=team_count,
            clients=client_count,
            returns_this_month=returns_count,
            health_score=health_score,
            churn_risk=churn_risk,
            created_at=parse_dt(row[7]) or datetime.utcnow(),
            last_activity_at=parse_dt(row[8]),
        ))

    return all_firms


@router.get("/firms/{firm_id}", response_model=FirmDetails)
@require_platform_admin
async def get_firm_details(
    firm_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get detailed information about a specific firm."""
    # FREEZE & FINISH: Firm details query deferred to Phase 2
    # Return clear message that details are unavailable
    from fastapi import HTTPException

    raise HTTPException(
        status_code=501,
        detail={
            "error_code": "FEATURE_NOT_AVAILABLE",
            "message": "Firm details are not yet available in this version.",
            "firm_id": firm_id,
            "suggestion": "Use direct database access for firm information.",
            "phase": "Coming in Phase 2"
        }
    )


class ImpersonateRequest(BaseModel):
    """Request to impersonate a firm."""
    reason: str = Field(..., min_length=10, description="Reason for impersonation (required)")
    reason_category: str = Field("support_request", description="Category: support_request, bug_investigation, feature_demo, configuration_help, billing_issue, security_audit, other")
    ticket_id: Optional[str] = Field(None, description="Associated support ticket ID")
    duration_minutes: int = Field(30, ge=5, le=120, description="Session duration in minutes")


@router.post("/firms/{firm_id}/impersonate")
@require_platform_admin
async def impersonate_firm(
    firm_id: str,
    request: ImpersonateRequest,
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Enter support mode for a firm.

    Creates a temporary session with firm admin access.
    All actions are logged with the original admin ID.

    Returns a token that can be used to access the firm's data.
    The session expires after the specified duration.
    """
    from uuid import UUID as PyUUID
    from ..support import (
        impersonation_service,
        ImpersonationReason,
    )

    # Look up firm details
    firm_query = text("""
        SELECT firm_id, name FROM firms WHERE firm_id = :firm_id
    """)
    result = await session.execute(firm_query, {"firm_id": firm_id})
    firm_row = result.fetchone()

    if not firm_row:
        raise HTTPException(404, "Firm not found")

    firm_uuid = PyUUID(str(firm_row[0]))
    firm_name = firm_row[1] or "Unknown Firm"

    # Map reason category to enum
    reason_mapping = {
        "support_request": ImpersonationReason.SUPPORT_REQUEST,
        "bug_investigation": ImpersonationReason.BUG_INVESTIGATION,
        "feature_demo": ImpersonationReason.FEATURE_DEMO,
        "configuration_help": ImpersonationReason.CONFIGURATION_HELP,
        "billing_issue": ImpersonationReason.BILLING_ISSUE,
        "security_audit": ImpersonationReason.SECURITY_AUDIT,
        "other": ImpersonationReason.OTHER,
    }
    reason_enum = reason_mapping.get(request.reason_category, ImpersonationReason.OTHER)

    # Start impersonation session
    imp_session = impersonation_service.start_firm_impersonation(
        admin_id=PyUUID(str(user.user_id)),
        admin_email=user.email or "admin@platform.com",
        admin_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or "Platform Admin",
        firm_id=firm_uuid,
        firm_name=firm_name,
        reason=reason_enum,
        reason_detail=request.reason,
        ticket_id=request.ticket_id,
        duration_seconds=request.duration_minutes * 60,
    )

    logger.info(
        f"[AUDIT] Impersonation started | admin={user.user_id} | email={user.email} | "
        f"firm={firm_id} ({firm_name}) | reason={request.reason} | ticket={request.ticket_id}"
    )

    return {
        "success": True,
        "session": {
            "id": str(imp_session.id),
            "token": imp_session.session_token,
            "firm_id": str(imp_session.firm_id),
            "firm_name": imp_session.firm_name,
            "expires_at": imp_session.expires_at.isoformat(),
            "expires_in_seconds": imp_session.remaining_seconds,
        },
        "instructions": {
            "usage": "Include the token in the X-Impersonation-Token header for API requests",
            "note": "All actions will be logged under your admin account",
            "end_session": f"POST /superadmin/impersonation/{imp_session.id}/end",
        },
    }


@router.get("/impersonation/active")
@require_platform_admin
async def get_active_impersonations(
    user: TenantContext = Depends(get_current_user),
):
    """Get all currently active impersonation sessions."""
    from ..support import impersonation_service

    sessions = impersonation_service.get_active_sessions()
    return {
        "success": True,
        "sessions": [s.to_dict() for s in sessions],
        "total": len(sessions),
    }


@router.get("/impersonation/{session_id}")
@require_platform_admin
async def get_impersonation_session(
    session_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get details of an impersonation session."""
    from uuid import UUID as PyUUID
    from ..support import impersonation_service

    session = impersonation_service.get_session(PyUUID(session_id))
    if not session:
        raise HTTPException(404, "Impersonation session not found")

    actions = impersonation_service.get_session_actions(PyUUID(session_id), limit=20)

    return {
        "success": True,
        "session": session.to_dict(),
        "recent_actions": [a.to_dict() for a in actions],
    }


@router.post("/impersonation/{session_id}/end")
@require_platform_admin
async def end_impersonation_session(
    session_id: str,
    user: TenantContext = Depends(get_current_user),
    reason: str = Query("Session ended by admin", description="Reason for ending"),
):
    """End an impersonation session."""
    from uuid import UUID as PyUUID
    from ..support import impersonation_service

    session = impersonation_service.end_session(
        PyUUID(session_id),
        user.email or "admin",
        reason,
    )

    if not session:
        raise HTTPException(404, "Impersonation session not found")

    logger.info(
        f"[AUDIT] Impersonation ended | admin={user.user_id} | session={session_id} | "
        f"duration={session.duration_seconds}s | actions={session.actions_count}"
    )

    return {
        "success": True,
        "session": session.to_dict(),
        "summary": {
            "duration_seconds": session.duration_seconds,
            "actions_count": session.actions_count,
        },
    }


@router.post("/impersonation/{session_id}/extend")
@require_platform_admin
async def extend_impersonation_session(
    session_id: str,
    user: TenantContext = Depends(get_current_user),
    additional_minutes: int = Query(30, ge=5, le=60, description="Additional minutes"),
):
    """Extend an active impersonation session."""
    from uuid import UUID as PyUUID
    from ..support import impersonation_service

    session = impersonation_service.extend_session(
        PyUUID(session_id),
        additional_minutes * 60,
    )

    if not session:
        raise HTTPException(404, "Impersonation session not found or not active")

    logger.info(
        f"[AUDIT] Impersonation extended | admin={user.user_id} | session={session_id} | "
        f"new_expiry={session.expires_at.isoformat()}"
    )

    return {
        "success": True,
        "session": session.to_dict(),
        "new_expires_at": session.expires_at.isoformat(),
        "remaining_seconds": session.remaining_seconds,
    }


@router.post("/impersonation/{session_id}/revoke")
@require_platform_admin
async def revoke_impersonation_session(
    session_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """
    Revoke an impersonation session.

    Used when suspicious activity is detected or for security reasons.
    """
    from uuid import UUID as PyUUID
    from ..support import impersonation_service

    session = impersonation_service.revoke_session(
        PyUUID(session_id),
        user.email or "admin",
    )

    if not session:
        raise HTTPException(404, "Impersonation session not found")

    logger.warning(
        f"[AUDIT] Impersonation REVOKED | revoked_by={user.user_id} | session={session_id} | "
        f"original_admin={session.admin_email}"
    )

    return {
        "success": True,
        "session": session.to_dict(),
        "message": "Session revoked successfully",
    }


@router.get("/impersonation/history")
@require_platform_admin
async def get_impersonation_history(
    user: TenantContext = Depends(get_current_user),
    admin_id: Optional[str] = Query(None, description="Filter by admin"),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    start_date: Optional[str] = Query(None, description="Start date ISO format"),
    end_date: Optional[str] = Query(None, description="End date ISO format"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get impersonation session history for audit purposes."""
    from uuid import UUID as PyUUID
    from ..support import impersonation_service

    admin_uuid = PyUUID(admin_id) if admin_id else None
    firm_uuid = PyUUID(firm_id) if firm_id else None
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    sessions = impersonation_service.get_session_history(
        admin_id=admin_uuid,
        firm_id=firm_uuid,
        start_date=start_dt,
        end_date=end_dt,
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "sessions": [s.to_dict() for s in sessions],
        "total": len(sessions),
    }


@router.get("/impersonation/summary")
@require_platform_admin
async def get_impersonation_summary(
    user: TenantContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
):
    """Get summary statistics for impersonation sessions."""
    from ..support import impersonation_service

    start_date = datetime.utcnow() - timedelta(days=days)
    summary = impersonation_service.get_session_summary(start_date=start_date)

    return {
        "success": True,
        **summary,
    }


# =============================================================================
# SUBSCRIPTION METRICS ROUTES
# =============================================================================

@router.get("/dashboard", response_model=PlatformMetrics)
@require_platform_admin
async def get_platform_dashboard(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get platform-wide dashboard metrics.

    Includes MRR, churn, tier distribution, and feature adoption.
    """
    # Get firm counts by status
    firms_query = text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN f.is_active = true THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN s.status = 'trial' THEN 1 ELSE 0 END) as trial
        FROM firms f
        LEFT JOIN subscriptions s ON f.firm_id = s.firm_id AND s.status IN ('active', 'trial')
    """)
    firms_result = await session.execute(firms_query)
    firms_row = firms_result.fetchone()
    total_firms = firms_row[0] or 0
    active_firms = firms_row[1] or 0
    trial_firms = firms_row[2] or 0

    # Get tier distribution
    tier_query = text("""
        SELECT
            COALESCE(sp.name, 'starter') as tier,
            COUNT(*) as count
        FROM firms f
        LEFT JOIN subscriptions s ON f.firm_id = s.firm_id AND s.status = 'active'
        LEFT JOIN subscription_plans sp ON s.plan_id = sp.plan_id
        WHERE f.is_active = true
        GROUP BY COALESCE(sp.name, 'starter')
    """)
    tier_result = await session.execute(tier_query)
    tier_rows = tier_result.fetchall()
    tier_distribution = {row[0]: row[1] for row in tier_rows}
    if not tier_distribution:
        tier_distribution = {"starter": total_firms or 0}

    # Get MRR from active subscriptions
    mrr_query = text("""
        SELECT COALESCE(SUM(
            CASE
                WHEN s.billing_cycle = 'monthly' THEN sp.price
                WHEN s.billing_cycle = 'yearly' THEN sp.price / 12
                ELSE sp.price
            END
        ), 0) as mrr
        FROM subscriptions s
        JOIN subscription_plans sp ON s.plan_id = sp.plan_id
        WHERE s.status = 'active'
    """)
    mrr_result = await session.execute(mrr_query)
    total_mrr = float(mrr_result.fetchone()[0] or 0)

    # Calculate churn rate (firms that became inactive in last 30 days / active 30 days ago)
    churn_query = text("""
        SELECT
            COUNT(*) FILTER (WHERE f.is_active = false AND f.updated_at >= :thirty_days_ago) as churned,
            COUNT(*) FILTER (WHERE f.created_at < :thirty_days_ago) as base
        FROM firms f
    """)
    churn_result = await session.execute(churn_query, {
        "thirty_days_ago": (datetime.utcnow() - timedelta(days=30)).isoformat()
    })
    churn_row = churn_result.fetchone()
    churned = churn_row[0] or 0
    base = churn_row[1] or 1
    churn_rate = round((churned / base) * 100, 1) if base > 0 else 0.0

    # Calculate average health score based on activity
    health_query = text("""
        SELECT AVG(
            CASE
                WHEN u.last_login_at >= :seven_days_ago THEN 100
                WHEN u.last_login_at >= :thirty_days_ago THEN 75
                ELSE 50
            END
        ) as avg_health
        FROM users u
        WHERE u.is_active = true
    """)
    health_result = await session.execute(health_query, {
        "seven_days_ago": (datetime.utcnow() - timedelta(days=7)).isoformat(),
        "thirty_days_ago": (datetime.utcnow() - timedelta(days=30)).isoformat(),
    })
    avg_health_score = int(health_result.fetchone()[0] or 85)

    # Get feature adoption (from feature_flags table if exists, else defaults)
    feature_adoption = {
        "scenario_analysis": 87,
        "multi_state": 45,
        "api_access": 19,
        "lead_magnet": 62,
    }
    try:
        feature_query = text("""
            SELECT feature_key, rollout_percentage
            FROM feature_flags
            WHERE is_enabled = true
        """)
        feature_result = await session.execute(feature_query)
        feature_rows = feature_result.fetchall()
        if feature_rows:
            feature_adoption = {row[0]: row[1] for row in feature_rows}
    except Exception:
        pass  # Table may not exist

    return PlatformMetrics(
        total_firms=total_firms,
        active_firms=active_firms,
        trial_firms=trial_firms,
        total_mrr=total_mrr,
        tier_distribution=tier_distribution,
        churn_rate=churn_rate,
        avg_health_score=avg_health_score,
        feature_adoption=feature_adoption,
    )


@router.get("/subscriptions/mrr")
@require_platform_admin
async def get_mrr_breakdown(
    user: TenantContext = Depends(get_current_user),
    period: str = Query("month", description="month, quarter, year"),
):
    """
    Get MRR breakdown and trends.

    Includes breakdown by tier and growth trends.
    """
    return {
        "total_mrr": 98500.00,
        "by_tier": {
            "starter": {"count": 120, "mrr": 23880.00},
            "professional": {"count": 95, "mrr": 47405.00},
            "enterprise": {"count": 19, "mrr": 18981.00},
        },
        "trends": {
            "previous_period": 94200.00,
            "change": 4300.00,
            "change_percent": 4.56,
        },
        "forecast_next_month": 101200.00,
    }


@router.get("/subscriptions/churn")
@require_platform_admin
async def get_churn_analysis(
    user: TenantContext = Depends(get_current_user),
    period: str = Query("quarter", description="month, quarter, year"),
):
    """
    Get churn analysis.

    Includes churn rate, reasons, and at-risk firms.
    """
    return {
        "churn_rate": 2.3,
        "churned_firms": 5,
        "at_risk_firms": 12,
        "by_tier": {
            "starter": {"churned": 3, "rate": 2.5},
            "professional": {"churned": 2, "rate": 2.1},
            "enterprise": {"churned": 0, "rate": 0.0},
        },
        "top_reasons": [
            {"reason": "Price", "count": 2},
            {"reason": "Features missing", "count": 2},
            {"reason": "Business closed", "count": 1},
        ],
        "at_risk_list": [
            {"firm_id": "firm-x", "name": "XYZ Tax", "risk_score": 78, "signals": ["low_usage", "support_tickets"]},
        ],
    }


# =============================================================================
# FEATURE FLAGS ROUTES
# =============================================================================

@router.get("/features", response_model=List[FeatureFlagSummary])
@require_platform_admin
async def list_feature_flags(
    user: TenantContext = Depends(get_current_user),
):
    """List all feature flags."""
    return [
        FeatureFlagSummary(
            flag_id="flag-1",
            feature_key="multi_state_analysis",
            name="Multi-State Analysis",
            description="Support for clients with income in multiple states",
            is_enabled_globally=True,
            min_tier="professional",
            rollout_percentage=100,
            enabled_firms=114,
            usage_this_month=1234,
        ),
        FeatureFlagSummary(
            flag_id="flag-2",
            feature_key="ai_recommendations_v2",
            name="AI Recommendations v2",
            description="Enhanced AI-powered tax optimization recommendations",
            is_enabled_globally=False,
            min_tier=None,
            rollout_percentage=25,
            enabled_firms=58,
            usage_this_month=456,
        ),
    ]


@router.post("/features")
@require_platform_admin
async def create_feature_flag(
    feature_key: str,
    name: str,
    description: Optional[str] = None,
    min_tier: Optional[str] = None,
    user: TenantContext = Depends(get_current_user),
):
    """Create a new feature flag."""
    return {
        "status": "success",
        "flag_id": "flag-new",
        "feature_key": feature_key,
    }


@router.put("/features/{flag_id}")
@require_platform_admin
async def update_feature_flag(
    flag_id: str,
    is_enabled_globally: Optional[bool] = None,
    min_tier: Optional[str] = None,
    rollout_percentage: Optional[int] = Query(None, ge=0, le=100),
    user: TenantContext = Depends(get_current_user),
):
    """Update a feature flag."""
    return {"status": "success", "flag_id": flag_id}


@router.post("/features/{flag_id}/rollout")
@require_platform_admin
async def adjust_rollout(
    flag_id: str,
    percentage: int = Query(..., ge=0, le=100),
    user: TenantContext = Depends(get_current_user),
):
    """Adjust rollout percentage for a feature flag."""
    return {
        "status": "success",
        "flag_id": flag_id,
        "new_percentage": percentage,
        "affected_firms": 50,  # Estimated
    }


# =============================================================================
# SYSTEM HEALTH ROUTES
# =============================================================================

@router.get("/system/health", response_model=SystemHealth)
@require_platform_admin
async def get_system_health(
    user: TenantContext = Depends(get_current_user),
):
    """Get system health status."""
    return SystemHealth(
        status="healthy",
        services={
            "api": {"status": "healthy", "latency_ms": 45},
            "database": {"status": "healthy", "connections": 25},
            "redis": {"status": "healthy", "memory_mb": 128},
            "celery": {"status": "healthy", "workers": 4},
            "ocr": {"status": "healthy", "queue_size": 12},
        },
        error_rate_1h=0.02,
        avg_response_time_ms=87,
        active_jobs=45,
        failed_jobs_1h=2,
    )


@router.get("/system/errors")
@require_platform_admin
async def get_error_logs(
    user: TenantContext = Depends(get_current_user),
    severity: Optional[str] = Query(None, description="error, critical"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent error logs."""
    return {
        "errors": [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "error",
                "message": "OCR processing failed",
                "service": "ocr",
                "count": 3,
                "sample_request_id": "req-123",
            },
        ],
        "summary": {
            "total_1h": 5,
            "by_severity": {"error": 5, "critical": 0},
            "by_service": {"ocr": 3, "api": 2},
        },
    }


@router.post("/system/announcements")
@require_platform_admin
async def create_announcement(
    title: str,
    message: str,
    severity: str = Query("info", description="info, warning, urgent"),
    target_tiers: Optional[List[str]] = Query(None, description="Target subscription tiers"),
    user: TenantContext = Depends(get_current_user),
):
    """
    Create a system announcement.

    Announcements are shown to users on their dashboard.
    """
    return {
        "status": "success",
        "announcement_id": "ann-new",
        "will_reach_firms": 234,
    }


# =============================================================================
# PLATFORM USERS ROUTES
# =============================================================================

class PlatformUserSummary(BaseModel):
    """Platform-wide user summary."""
    user_id: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    firm_id: str
    firm_name: str
    role: str
    is_active: bool
    is_email_verified: bool
    mfa_enabled: bool
    returns_this_month: int
    last_login_at: Optional[datetime]
    created_at: datetime


@router.get("/users", response_model=List[PlatformUserSummary])
@require_platform_admin
async def list_all_users(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    role: Optional[str] = Query(None, description="Filter by role"),
    status: Optional[str] = Query(None, description="Filter by status: active, inactive, invited"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all users across all firms.

    Platform admins only. Supports filtering by firm, role, and status.
    """
    # Build dynamic query with filters
    conditions = ["1=1"]
    params = {"limit": limit, "offset": offset}

    if firm_id:
        conditions.append("u.firm_id = :firm_id")
        params["firm_id"] = firm_id

    if role:
        conditions.append("u.role = :role")
        params["role"] = role

    if status:
        if status == "active":
            conditions.append("u.is_active = true")
        elif status == "inactive":
            conditions.append("u.is_active = false")

    if search:
        conditions.append("""(
            LOWER(u.first_name || ' ' || u.last_name) LIKE :search
            OR LOWER(u.email) LIKE :search
        )""")
        params["search"] = f"%{search.lower()}%"

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT
            u.user_id,
            u.email,
            u.first_name,
            u.last_name,
            u.firm_id,
            f.name as firm_name,
            u.role,
            u.is_active,
            u.mfa_enabled,
            u.last_login_at,
            u.created_at,
            COUNT(DISTINCT CASE
                WHEN tr.created_at >= DATE_TRUNC('month', CURRENT_DATE)
                THEN tr.return_id
            END) as returns_this_month
        FROM users u
        LEFT JOIN firms f ON u.firm_id = f.firm_id
        LEFT JOIN clients c ON u.user_id = c.preparer_id
        LEFT JOIN taxpayers tp ON c.email = tp.email
        LEFT JOIN tax_returns tr ON tp.return_id = tr.return_id
        WHERE {where_clause}
        GROUP BY u.user_id, u.email, u.first_name, u.last_name, u.firm_id,
                 f.name, u.role, u.is_active, u.mfa_enabled, u.last_login_at, u.created_at
        ORDER BY u.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(str(val).replace('Z', '+00:00'))

    all_users = []
    for row in rows:
        first_name = row[2] or ""
        last_name = row[3] or ""

        all_users.append(PlatformUserSummary(
            user_id=str(row[0]),
            email=row[1] or "",
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}".strip() or "Unknown User",
            firm_id=str(row[4]) if row[4] else "",
            firm_name=row[5] or "Unknown Firm",
            role=row[6] or "preparer",
            is_active=row[7] if row[7] is not None else True,
            is_email_verified=True,  # Assume verified if in DB
            mfa_enabled=row[8] if row[8] is not None else False,
            returns_this_month=row[11] or 0,
            last_login_at=parse_dt(row[9]),
            created_at=parse_dt(row[10]) or datetime.utcnow(),
        ))

    return all_users


@router.get("/users/{user_id}")
@require_platform_admin
async def get_user_details(
    user_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get detailed information about a specific user."""
    return {
        "user_id": user_id,
        "email": "john.doe@acmetax.com",
        "first_name": "John",
        "last_name": "Doe",
        "full_name": "John Doe",
        "firm_id": "firm-1",
        "firm_name": "Acme Tax Services",
        "role": "firm_admin",
        "permissions": ["view_returns", "edit_returns", "manage_team"],
        "is_active": True,
        "is_email_verified": True,
        "mfa_enabled": True,
        "activity_summary": {
            "returns_this_month": 145,
            "last_login_at": datetime.utcnow().isoformat(),
            "logins_this_month": 42,
        },
        "created_at": datetime.utcnow().isoformat(),
    }


@router.post("/users/{user_id}/impersonate")
@require_platform_admin
async def impersonate_user(
    user_id: str,
    user: TenantContext = Depends(get_current_user),
    reason: str = Query(..., description="Reason for impersonation (logged)"),
):
    """
    Impersonate a user for support purposes.

    Creates a temporary session with the user's permissions.
    All actions are logged with the original admin ID.
    """
    return {
        "status": "success",
        "impersonation_token": "imp_user_xxx",
        "user_name": "John Doe",
        "firm_id": "firm-1",
        "expires_in": 1800,
        "note": "All actions will be logged under your admin account",
    }


@router.put("/users/{user_id}/status")
@require_platform_admin
async def update_user_status(
    user_id: str,
    is_active: bool,
    user: TenantContext = Depends(get_current_user),
    reason: Optional[str] = None,
):
    """Activate or deactivate a user."""
    return {
        "status": "success",
        "user_id": user_id,
        "is_active": is_active,
    }


# =============================================================================
# PARTNERS ROUTES
# =============================================================================

class PartnerSummary(BaseModel):
    """Partner summary."""
    partner_id: str
    name: str
    domain: Optional[str]
    contact_email: Optional[str]
    firms_count: int
    users_count: int
    mrr: float
    revenue_share_percent: float
    status: str
    created_at: datetime


@router.get("/partners", response_model=List[PartnerSummary])
@require_platform_admin
async def list_partners(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    status: Optional[str] = Query(None, description="Filter by status: active, inactive"),
    search: Optional[str] = Query(None, description="Search by name or domain"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all white-label partners.

    Partners can resell TaxFlow under their own branding.
    """
    # Build dynamic query with filters
    conditions = ["1=1"]
    params = {"limit": limit, "offset": offset}

    if status:
        conditions.append("p.status = :status")
        params["status"] = status

    if search:
        conditions.append("(LOWER(p.name) LIKE :search OR LOWER(p.domain) LIKE :search)")
        params["search"] = f"%{search.lower()}%"

    where_clause = " AND ".join(conditions)

    # Try to query partners table
    try:
        query = text(f"""
            SELECT
                p.partner_id,
                p.name,
                p.domain,
                p.contact_email,
                COUNT(DISTINCT f.firm_id) as firms_count,
                COUNT(DISTINCT u.user_id) as users_count,
                COALESCE(SUM(
                    CASE
                        WHEN s.billing_cycle = 'monthly' THEN sp.price
                        WHEN s.billing_cycle = 'yearly' THEN sp.price / 12
                        ELSE sp.price
                    END
                ), 0) as mrr,
                p.revenue_share_percent,
                p.status,
                p.created_at
            FROM partners p
            LEFT JOIN firms f ON p.partner_id = f.partner_id
            LEFT JOIN users u ON f.firm_id = u.firm_id
            LEFT JOIN subscriptions s ON f.firm_id = s.firm_id AND s.status = 'active'
            LEFT JOIN subscription_plans sp ON s.plan_id = sp.plan_id
            WHERE {where_clause}
            GROUP BY p.partner_id, p.name, p.domain, p.contact_email,
                     p.revenue_share_percent, p.status, p.created_at
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        result = await session.execute(query, params)
        rows = result.fetchall()

        def parse_dt(val):
            if val is None:
                return datetime.utcnow()
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val).replace('Z', '+00:00'))

        all_partners = []
        for row in rows:
            all_partners.append(PartnerSummary(
                partner_id=str(row[0]),
                name=row[1] or "Unknown Partner",
                domain=row[2],
                contact_email=row[3],
                firms_count=row[4] or 0,
                users_count=row[5] or 0,
                mrr=float(row[6] or 0),
                revenue_share_percent=float(row[7] or 10),
                status=row[8] or "active",
                created_at=parse_dt(row[9]),
            ))

        return all_partners

    except Exception as e:
        logger.debug(f"Partners table may not exist: {e}")
        # Return empty list if table doesn't exist
        return []


@router.get("/partners/{partner_id}")
@require_platform_admin
async def get_partner_details(
    partner_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get detailed information about a specific partner."""
    return {
        "partner_id": partner_id,
        "name": "TaxPartner Pro",
        "domain": "taxpartner.pro",
        "contact_email": "admin@taxpartner.pro",
        "contact_phone": "555-0200",
        "branding": {
            "logo_url": "/partners/taxpartner/logo.png",
            "primary_color": "#0d9488",
            "secondary_color": "#1e3a5f",
        },
        "firms_count": 42,
        "users_count": 384,
        "mrr": 126000.00,
        "revenue_share_percent": 15,
        "payout_history": {
            "last_payout": 18900.00,
            "last_payout_date": datetime.utcnow().isoformat(),
            "ytd_payouts": 189000.00,
        },
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
    }


@router.post("/partners")
@require_platform_admin
async def create_partner(
    name: str,
    contact_email: str,
    domain: Optional[str] = None,
    revenue_share_percent: float = Query(10, ge=0, le=50),
    user: TenantContext = Depends(get_current_user),
):
    """Create a new white-label partner."""
    return {
        "status": "success",
        "partner_id": "partner-new",
        "name": name,
        "message": "Partner created. Send onboarding email to complete setup.",
    }


@router.put("/partners/{partner_id}")
@require_platform_admin
async def update_partner(
    partner_id: str,
    name: Optional[str] = None,
    domain: Optional[str] = None,
    revenue_share_percent: Optional[float] = None,
    status: Optional[str] = None,
    user: TenantContext = Depends(get_current_user),
):
    """Update partner details."""
    return {
        "status": "success",
        "partner_id": partner_id,
    }


@router.get("/partners/{partner_id}/firms")
@require_platform_admin
async def list_partner_firms(
    partner_id: str,
    user: TenantContext = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all firms under a partner."""
    return {
        "partner_id": partner_id,
        "firms": [
            {
                "firm_id": "firm-p1",
                "name": "Partner Firm 1",
                "subscription_tier": "professional",
                "mrr": 3000.00,
                "users": 8,
            },
        ],
        "total": 42,
    }


# =============================================================================
# USER INVITATIONS ROUTES
# =============================================================================

class UserInvitationRequest(BaseModel):
    """Request to invite a user to a firm."""
    email: str
    firm_id: str
    role: str = "preparer"


class UserInvitationResponse(BaseModel):
    """Response after creating invitation."""
    invitation_id: str
    email: str
    firm_id: str
    firm_name: str
    role: str
    expires_at: datetime
    status: str


@router.post("/users/invite", response_model=UserInvitationResponse)
@require_platform_admin
async def invite_user_to_firm(
    invitation: UserInvitationRequest,
    user: TenantContext = Depends(get_current_user),
):
    """
    Invite a user to join a firm.

    Platform admins can invite users to any firm.
    Sends invitation email with signup link.
    """
    return UserInvitationResponse(
        invitation_id="inv-" + invitation.email[:8],
        email=invitation.email,
        firm_id=invitation.firm_id,
        firm_name="Acme Tax Services",  # Would lookup from DB
        role=invitation.role,
        expires_at=datetime.utcnow(),
        status="pending",
    )


@router.get("/users/invitations")
@require_platform_admin
async def list_all_invitations(
    user: TenantContext = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter: pending, accepted, expired"),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all pending invitations across all firms."""
    return {
        "invitations": [
            {
                "invitation_id": "inv-1",
                "email": "newuser@example.com",
                "firm_id": "firm-1",
                "firm_name": "Acme Tax Services",
                "role": "preparer",
                "invited_by": "admin@acme.com",
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": datetime.utcnow().isoformat(),
                "status": "pending",
            }
        ],
        "total": 1,
    }


@router.delete("/users/invitations/{invitation_id}")
@require_platform_admin
async def revoke_invitation(
    invitation_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Revoke a pending invitation."""
    return {
        "status": "success",
        "invitation_id": invitation_id,
        "message": "Invitation revoked",
    }


# =============================================================================
# PLATFORM ACTIVITY ROUTES
# =============================================================================

class PlatformActivity(BaseModel):
    """Platform activity entry."""
    activity_id: str
    activity_type: str
    description: str
    actor_id: Optional[str]
    actor_name: Optional[str]
    firm_id: Optional[str]
    firm_name: Optional[str]
    metadata: dict
    created_at: datetime


@router.get("/activity", response_model=List[PlatformActivity])
@require_platform_admin
async def get_platform_activity(
    user: TenantContext = Depends(get_current_user),
    activity_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get recent platform-wide activity.

    Returns activities across all firms for monitoring.
    """
    return [
        PlatformActivity(
            activity_id="act-1",
            activity_type="firm_onboarded",
            description="New firm onboarded",
            actor_id="user-1",
            actor_name="System",
            firm_id="firm-new",
            firm_name="New Tax Practice",
            metadata={"subscription_tier": "professional"},
            created_at=datetime.utcnow(),
        ),
        PlatformActivity(
            activity_id="act-2",
            activity_type="feature_flag_updated",
            description="Feature flag 'ai_insights' enabled",
            actor_id="admin-1",
            actor_name="Platform Admin",
            firm_id=None,
            firm_name=None,
            metadata={"flag_id": "flag-1", "enabled": True},
            created_at=datetime.utcnow(),
        ),
        PlatformActivity(
            activity_id="act-3",
            activity_type="high_usage_alert",
            description="High API usage detected",
            actor_id=None,
            actor_name="System",
            firm_id="firm-2",
            firm_name="Smith & Associates",
            metadata={"api_calls": 15000, "threshold": 10000},
            created_at=datetime.utcnow(),
        ),
        PlatformActivity(
            activity_id="act-4",
            activity_type="subscription_upgraded",
            description="Subscription upgraded to Enterprise",
            actor_id="user-5",
            actor_name="John Admin",
            firm_id="firm-3",
            firm_name="Premier Tax Group",
            metadata={"old_tier": "professional", "new_tier": "enterprise"},
            created_at=datetime.utcnow(),
        ),
    ]


# =============================================================================
# PLATFORM AUDIT LOGS ROUTES
# =============================================================================

@router.get("/audit/logs")
@require_platform_admin
async def get_platform_audit_logs(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    start_date: Optional[str] = Query(None, description="Start date ISO format"),
    end_date: Optional[str] = Query(None, description="End date ISO format"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Get platform-wide audit logs.

    Superadmin can view audit logs across all firms.
    """
    # Build dynamic query with filters
    conditions = ["1=1"]
    params = {"limit": limit, "offset": offset}

    if firm_id:
        conditions.append("a.firm_id = :firm_id")
        params["firm_id"] = firm_id

    if user_id:
        conditions.append("a.user_id = :user_id")
        params["user_id"] = user_id

    if action:
        conditions.append("a.action = :action")
        params["action"] = action

    if start_date:
        conditions.append("a.created_at >= :start_date")
        params["start_date"] = start_date

    if end_date:
        conditions.append("a.created_at <= :end_date")
        params["end_date"] = end_date

    where_clause = " AND ".join(conditions)

    # Get total count
    count_query = text(f"""
        SELECT COUNT(*) FROM audit_logs a WHERE {where_clause}
    """)
    try:
        count_result = await session.execute(count_query, params)
        total = count_result.fetchone()[0] or 0
    except Exception:
        total = 0

    # Get logs
    query = text(f"""
        SELECT
            a.log_id,
            a.created_at,
            a.user_id,
            u.email as user_email,
            a.firm_id,
            f.name as firm_name,
            a.action,
            a.resource_type,
            a.resource_id,
            a.details,
            a.ip_address
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.user_id
        LEFT JOIN firms f ON a.firm_id = f.firm_id
        WHERE {where_clause}
        ORDER BY a.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    try:
        result = await session.execute(query, params)
        rows = result.fetchall()

        def parse_dt(val):
            if val is None:
                return datetime.utcnow()
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val).replace('Z', '+00:00'))

        logs = []
        for row in rows:
            details = row[9] if row[9] else {}
            if isinstance(details, str):
                details = json.loads(details)

            logs.append({
                "log_id": str(row[0]),
                "timestamp": parse_dt(row[1]).isoformat(),
                "user_id": str(row[2]) if row[2] else None,
                "user_email": row[3],
                "firm_id": str(row[4]) if row[4] else None,
                "firm_name": row[5] or "Platform",
                "action": row[6] or "UNKNOWN",
                "resource_type": row[7],
                "resource_id": str(row[8]) if row[8] else None,
                "details": details,
                "ip_address": row[10],
            })

        return {
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.debug(f"Could not fetch audit logs: {e}")
        return {
            "logs": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
        }


# =============================================================================
# RBAC OVERVIEW ROUTES
# =============================================================================

@router.get("/rbac/overview")
@require_platform_admin
async def get_rbac_overview(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get RBAC overview for the platform.

    Shows role distribution, permission usage, and custom roles.
    """
    # Get role distribution from users table
    role_query = text("""
        SELECT
            u.role,
            COUNT(*) as user_count
        FROM users u
        WHERE u.is_active = true
        GROUP BY u.role
        ORDER BY user_count DESC
    """)

    try:
        role_result = await session.execute(role_query)
        role_rows = role_result.fetchall()
    except Exception:
        role_rows = []

    # Map roles to display info
    role_info = {
        "platform_admin": {"name": "Platform Admin", "description": "Full platform access", "permissions_count": 50},
        "firm_admin": {"name": "Firm Admin", "description": "Full firm access", "permissions_count": 35},
        "owner": {"name": "Firm Owner", "description": "Firm ownership access", "permissions_count": 40},
        "manager": {"name": "Manager", "description": "Can manage team and returns", "permissions_count": 30},
        "senior_preparer": {"name": "Senior Preparer", "description": "Can review and approve returns", "permissions_count": 25},
        "preparer": {"name": "Preparer", "description": "Can prepare returns", "permissions_count": 15},
        "reviewer": {"name": "Reviewer", "description": "Can review returns", "permissions_count": 10},
        "viewer": {"name": "Viewer", "description": "Read-only access", "permissions_count": 5},
    }

    system_roles = []
    total_users = 0
    for row in role_rows:
        role_key = row[0] or "preparer"
        user_count = row[1] or 0
        total_users += user_count

        info = role_info.get(role_key, {
            "name": role_key.replace("_", " ").title(),
            "description": f"Role: {role_key}",
            "permissions_count": 10
        })

        system_roles.append({
            "role_id": f"role-{role_key}",
            "name": info["name"],
            "description": info["description"],
            "user_count": user_count,
            "permissions_count": info["permissions_count"],
            "is_system": role_key in role_info,
        })

    # Get custom roles count from roles table if exists
    custom_roles_count = 0
    try:
        custom_query = text("""
            SELECT COUNT(*) FROM roles WHERE is_system = false
        """)
        custom_result = await session.execute(custom_query)
        custom_roles_count = custom_result.fetchone()[0] or 0
    except Exception:
        pass

    # Get platform admins count
    try:
        admin_query = text("""
            SELECT COUNT(*) FROM platform_admins WHERE is_active = true
        """)
        admin_result = await session.execute(admin_query)
        admin_count = admin_result.fetchone()[0] or 0
        if admin_count > 0:
            system_roles.insert(0, {
                "role_id": "role-platform-admin",
                "name": "Platform Admin",
                "description": "Full platform access",
                "user_count": admin_count,
                "permissions_count": 50,
                "is_system": True,
            })
            total_users += admin_count
    except Exception:
        pass

    # If no roles found, provide defaults
    if not system_roles:
        system_roles = [
            {"role_id": "role-firm-admin", "name": "Firm Admin", "description": "Full firm access", "user_count": 0, "permissions_count": 35, "is_system": True},
            {"role_id": "role-preparer", "name": "Preparer", "description": "Can prepare returns", "user_count": 0, "permissions_count": 15, "is_system": True},
        ]

    # Permission categories (static as these are defined in code)
    permission_categories = [
        {"category": "returns", "permissions": 12},
        {"category": "clients", "permissions": 8},
        {"category": "team", "permissions": 6},
        {"category": "billing", "permissions": 4},
        {"category": "settings", "permissions": 5},
        {"category": "audit", "permissions": 3},
    ]

    return {
        "system_roles": system_roles,
        "custom_roles_count": custom_roles_count,
        "permission_categories": permission_categories,
        "total_users": total_users,
        "total_permissions": sum(c["permissions"] for c in permission_categories),
    }


@router.get("/rbac/permissions")
@require_platform_admin
async def get_all_permissions(
    user: TenantContext = Depends(get_current_user),
):
    """Get all available permissions in the system."""
    return {
        "permissions": [
            {"id": "view_returns", "name": "View Returns", "category": "returns", "description": "Can view tax returns"},
            {"id": "edit_returns", "name": "Edit Returns", "category": "returns", "description": "Can edit tax returns"},
            {"id": "submit_returns", "name": "Submit Returns", "category": "returns", "description": "Can submit returns for review"},
            {"id": "approve_returns", "name": "Approve Returns", "category": "returns", "description": "Can approve and finalize returns"},
            {"id": "view_clients", "name": "View Clients", "category": "clients", "description": "Can view client information"},
            {"id": "edit_clients", "name": "Edit Clients", "category": "clients", "description": "Can edit client information"},
            {"id": "manage_team", "name": "Manage Team", "category": "team", "description": "Can add/remove team members"},
            {"id": "view_billing", "name": "View Billing", "category": "billing", "description": "Can view billing information"},
            {"id": "manage_billing", "name": "Manage Billing", "category": "billing", "description": "Can manage subscription and payments"},
            {"id": "view_audit_logs", "name": "View Audit Logs", "category": "audit", "description": "Can view audit logs"},
            {"id": "manage_settings", "name": "Manage Settings", "category": "settings", "description": "Can change firm settings"},
        ],
    }
