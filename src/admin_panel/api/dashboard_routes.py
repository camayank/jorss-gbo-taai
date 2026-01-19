"""
Dashboard Routes - Firm admin dashboard endpoints.

Provides:
- Dashboard overview with key metrics
- AI-powered alerts
- Recent activity feed
- Quick stats cards

All routes use database-backed queries.
"""

import json
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.rbac import get_current_user, get_current_firm, TenantContext
from ..models.user import UserPermission
from database.async_engine import get_async_session

router = APIRouter(tags=["Dashboard"])
logger = logging.getLogger(__name__)


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class MetricCard(BaseModel):
    """Single metric card for dashboard display."""
    label: str
    value: str
    change: Optional[float] = None  # Percent change from previous period
    change_label: Optional[str] = None
    trend: Optional[str] = None  # up, down, neutral
    icon: Optional[str] = None


class Alert(BaseModel):
    """AI-powered alert for dashboard."""
    alert_id: str
    severity: str = Field(..., description="info, warning, error, critical")
    title: str
    message: str
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    created_at: datetime
    is_read: bool = False


class ActivityItem(BaseModel):
    """Recent activity item."""
    activity_id: str
    event_type: str
    description: str
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    client_name: Optional[str] = None
    timestamp: datetime
    metadata: Optional[dict] = None


class DashboardOverview(BaseModel):
    """Complete dashboard overview response."""
    firm_name: str
    subscription_tier: str
    health_score: int = Field(..., ge=0, le=100)
    metrics: List[MetricCard]
    alerts: List[Alert]
    recent_activity: List[ActivityItem]
    quick_actions: List[dict]


class DashboardAlerts(BaseModel):
    """Dashboard alerts response."""
    alerts: List[Alert]
    unread_count: int
    total_count: int


class ActivityFeed(BaseModel):
    """Activity feed response."""
    activities: List[ActivityItem]
    has_more: bool
    next_cursor: Optional[str] = None


# =============================================================================
# ROUTES
# =============================================================================

@router.get("/dashboard", response_model=DashboardOverview)
async def get_dashboard(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get firm admin dashboard overview.

    Returns key metrics, alerts, and recent activity for the firm.
    """
    now = datetime.utcnow()
    last_month = now - timedelta(days=30)

    # Get firm info and subscription
    firm_query = text("""
        SELECT f.name, sp.name as plan_name
        FROM firms f
        LEFT JOIN subscriptions s ON f.firm_id = s.firm_id AND s.status = 'active'
        LEFT JOIN subscription_plans sp ON s.plan_id = sp.plan_id
        WHERE f.firm_id = :firm_id
    """)
    firm_result = await session.execute(firm_query, {"firm_id": firm_id})
    firm_row = firm_result.fetchone()

    if not firm_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    firm_name = firm_row[0] or "Unknown Firm"
    subscription_tier = firm_row[1] or "starter"

    # Get active returns count
    returns_query = text("""
        SELECT COUNT(*) as active,
               SUM(CASE WHEN r.workflow_stage = 'review' THEN 1 ELSE 0 END) as pending_review
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id AND r.workflow_stage != 'complete'
    """)
    returns_result = await session.execute(returns_query, {"firm_id": firm_id})
    returns_row = returns_result.fetchone()
    active_returns = returns_row[0] or 0
    pending_review = returns_row[1] or 0

    # Get returns from last month for comparison
    last_month_query = text("""
        SELECT COUNT(*) FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id AND r.created_at < :last_month AND r.workflow_stage != 'complete'
    """)
    last_month_result = await session.execute(last_month_query, {"firm_id": firm_id, "last_month": last_month.isoformat()})
    last_month_active = last_month_result.fetchone()[0] or 0
    returns_change = ((active_returns - last_month_active) / max(last_month_active, 1)) * 100

    # Get estimated revenue from current returns
    revenue_query = text("""
        SELECT COALESCE(SUM(r.estimated_fee), 0) as total
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.tax_year = EXTRACT(YEAR FROM NOW())
    """)
    revenue_result = await session.execute(revenue_query, {"firm_id": firm_id})
    estimated_revenue = revenue_result.fetchone()[0] or 0

    # Get deadline alerts
    deadline_query = text("""
        SELECT r.return_id, c.first_name || ' ' || c.last_name as client_name, r.deadline
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        LEFT JOIN clients c ON r.client_id = c.client_id
        WHERE u.firm_id = :firm_id
        AND r.workflow_stage != 'complete'
        AND r.deadline IS NOT NULL
        AND r.deadline BETWEEN :now AND :deadline_limit
        ORDER BY r.deadline ASC
        LIMIT 5
    """)
    deadline_result = await session.execute(deadline_query, {
        "firm_id": firm_id,
        "now": now.isoformat(),
        "deadline_limit": (now + timedelta(days=7)).isoformat(),
    })
    deadline_rows = deadline_result.fetchall()

    # Build alerts
    alerts = []
    if deadline_rows:
        client_names = [row[1] or "Unknown" for row in deadline_rows[:3]]
        alerts.append(Alert(
            alert_id=f"alert-deadline-{firm_id}",
            severity="warning",
            title=f"{len(deadline_rows)} returns approaching deadline",
            message=f"Returns for {', '.join(client_names)} are due soon",
            action_url="/returns?filter=deadline",
            action_label="View Returns",
            created_at=now,
        ))

    # Get recent activity
    activity_query = text("""
        SELECT a.log_id, a.action, a.details, a.created_at,
               u.first_name || ' ' || u.last_name as user_name
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.user_id
        WHERE a.firm_id = :firm_id
        ORDER BY a.created_at DESC
        LIMIT 5
    """)
    activity_result = await session.execute(activity_query, {"firm_id": firm_id})
    activity_rows = activity_result.fetchall()

    def parse_dt(val):
        if val is None:
            return datetime.utcnow()
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    recent_activity = []
    for row in activity_rows:
        details = json.loads(row[2]) if row[2] else {}
        recent_activity.append(ActivityItem(
            activity_id=str(row[0]),
            event_type=row[1] or "action",
            description=details.get("description", row[1] or ""),
            user_name=row[4] or "System",
            client_name=details.get("client_name"),
            timestamp=parse_dt(row[3]),
        ))

    # Calculate health score (simple algorithm)
    health_score = 100
    if pending_review > 10:
        health_score -= 10
    if len(deadline_rows) > 3:
        health_score -= 5 * len(deadline_rows)
    health_score = max(0, min(100, health_score))

    return DashboardOverview(
        firm_name=firm_name,
        subscription_tier=subscription_tier,
        health_score=health_score,
        metrics=[
            MetricCard(
                label="Active Returns",
                value=str(active_returns),
                change=round(returns_change, 1),
                change_label="vs last month",
                trend="up" if returns_change > 0 else ("down" if returns_change < 0 else "neutral"),
                icon="document",
            ),
            MetricCard(
                label="Pending Review",
                value=str(pending_review),
                change=None,
                change_label=None,
                trend="neutral",
                icon="clock",
            ),
            MetricCard(
                label="Health Score",
                value=f"{health_score}%",
                change=None,
                change_label=None,
                trend="up" if health_score >= 80 else "down",
                icon="shield",
            ),
            MetricCard(
                label="Est. Revenue",
                value=f"${estimated_revenue:,.0f}",
                change=None,
                change_label=None,
                trend="up",
                icon="currency",
            ),
        ],
        alerts=alerts,
        recent_activity=recent_activity,
        quick_actions=[
            {"label": "Add Team Member", "url": "/admin/team/invite", "icon": "user-plus"},
            {"label": "View Review Queue", "url": "/returns?filter=pending_review", "icon": "clipboard"},
            {"label": "Export Compliance", "url": "/admin/compliance/export", "icon": "download"},
            {"label": "View Billing", "url": "/admin/billing", "icon": "credit-card"},
        ],
    )


@router.get("/dashboard/alerts", response_model=DashboardAlerts)
async def get_dashboard_alerts(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    unread_only: bool = Query(False, description="Show only unread alerts"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get AI-powered alerts for the firm.

    Alerts are generated based on:
    - Deadline proximity
    - Staff performance anomalies
    - Compliance score changes
    - Churn risk signals
    - Upgrade opportunities
    """
    now = datetime.utcnow()

    # Build conditions for stored alerts
    conditions = ["a.firm_id = :firm_id"]
    params = {"firm_id": firm_id, "limit": limit}

    if severity:
        conditions.append("a.severity = :severity")
        params["severity"] = severity

    if unread_only:
        conditions.append("a.is_read = false")

    where_clause = " AND ".join(conditions)

    # Get stored alerts
    query = text(f"""
        SELECT a.alert_id, a.severity, a.title, a.message, a.action_url,
               a.action_label, a.created_at, a.is_read
        FROM alerts a
        WHERE {where_clause}
        ORDER BY a.created_at DESC
        LIMIT :limit
    """)
    result = await session.execute(query, params)
    rows = result.fetchall()

    def parse_dt(val):
        if val is None:
            return datetime.utcnow()
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    alerts = []
    for row in rows:
        alerts.append(Alert(
            alert_id=str(row[0]),
            severity=row[1] or "info",
            title=row[2] or "",
            message=row[3] or "",
            action_url=row[4],
            action_label=row[5],
            created_at=parse_dt(row[6]),
            is_read=row[7] if row[7] is not None else False,
        ))

    # Also generate dynamic alerts based on current state
    # Check for deadline alerts
    deadline_query = text("""
        SELECT COUNT(*), MIN(r.deadline) FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.workflow_stage != 'complete'
        AND r.deadline IS NOT NULL
        AND r.deadline BETWEEN :now AND :deadline_limit
    """)
    deadline_result = await session.execute(deadline_query, {
        "firm_id": firm_id,
        "now": now.isoformat(),
        "deadline_limit": (now + timedelta(days=7)).isoformat(),
    })
    deadline_row = deadline_result.fetchone()
    if deadline_row and deadline_row[0] > 0:
        days_until = (parse_dt(deadline_row[1]) - now).days if deadline_row[1] else 7
        alerts.insert(0, Alert(
            alert_id=f"dynamic-deadline-{firm_id}",
            severity="warning" if days_until <= 3 else "info",
            title=f"{deadline_row[0]} returns approaching deadline",
            message=f"Earliest deadline in {days_until} days",
            action_url="/returns?filter=deadline",
            action_label="View Returns",
            created_at=now,
            is_read=False,
        ))

    # Get counts
    count_query = text("""
        SELECT COUNT(*) as total, SUM(CASE WHEN is_read = false THEN 1 ELSE 0 END) as unread
        FROM alerts WHERE firm_id = :firm_id
    """)
    count_result = await session.execute(count_query, {"firm_id": firm_id})
    count_row = count_result.fetchone()

    return DashboardAlerts(
        alerts=alerts[:limit],
        unread_count=(count_row[1] or 0) + (1 if deadline_row and deadline_row[0] > 0 else 0),
        total_count=(count_row[0] or 0) + (1 if deadline_row and deadline_row[0] > 0 else 0),
    )


@router.post("/dashboard/alerts/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Mark an alert as read."""
    # Skip dynamic alerts (they don't persist)
    if alert_id.startswith("dynamic-"):
        return {"status": "success", "alert_id": alert_id, "is_read": True}

    query = text("""
        UPDATE alerts SET is_read = true, read_at = :read_at
        WHERE alert_id = :alert_id AND firm_id = :firm_id
    """)
    result = await session.execute(query, {
        "alert_id": alert_id,
        "firm_id": firm_id,
        "read_at": datetime.utcnow().isoformat(),
    })

    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    await session.commit()

    return {"status": "success", "alert_id": alert_id, "is_read": True}


@router.get("/dashboard/activity", response_model=ActivityFeed)
async def get_activity_feed(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
):
    """
    Get recent activity feed for the firm.

    Activity types:
    - return_submitted, return_approved, return_rejected
    - client_added, client_archived
    - document_uploaded, document_processed
    - team_member_added, team_member_removed
    - setting_changed
    """
    # Build conditions
    conditions = ["a.firm_id = :firm_id"]
    params = {"firm_id": firm_id, "limit": limit + 1}  # +1 to check has_more

    if event_type:
        conditions.append("a.action = :event_type")
        params["event_type"] = event_type

    if user_id:
        conditions.append("a.user_id = :user_id")
        params["user_id"] = user_id

    if cursor:
        conditions.append("a.created_at < :cursor")
        params["cursor"] = cursor

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT a.log_id, a.action, a.details, a.created_at,
               u.first_name || ' ' || u.last_name as user_name
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.user_id
        WHERE {where_clause}
        ORDER BY a.created_at DESC
        LIMIT :limit
    """)
    result = await session.execute(query, params)
    rows = result.fetchall()

    def parse_dt(val):
        if val is None:
            return datetime.utcnow()
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    activities = []
    for row in rows[:limit]:
        details = json.loads(row[2]) if row[2] else {}
        activities.append(ActivityItem(
            activity_id=str(row[0]),
            event_type=row[1] or "action",
            description=details.get("description", row[1] or ""),
            user_name=row[4] or "System",
            client_name=details.get("client_name"),
            timestamp=parse_dt(row[3]),
            metadata=details,
        ))

    has_more = len(rows) > limit
    next_cursor = None
    if has_more and activities:
        next_cursor = activities[-1].timestamp.isoformat()

    return ActivityFeed(
        activities=activities,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@router.get("/dashboard/stats/summary")
async def get_stats_summary(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    period: str = Query("month", description="time period: day, week, month, quarter, year"),
):
    """
    Get summary statistics for the specified period.

    Used for dashboard hero metrics and trend analysis.
    """
    now = datetime.utcnow()

    # Calculate period start date
    period_map = {
        "day": timedelta(days=1),
        "week": timedelta(weeks=1),
        "month": timedelta(days=30),
        "quarter": timedelta(days=90),
        "year": timedelta(days=365),
    }
    period_delta = period_map.get(period, timedelta(days=30))
    period_start = now - period_delta

    # Get returns statistics
    returns_query = text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN r.workflow_stage = 'complete' THEN 1 ELSE 0 END) as filed,
            SUM(CASE WHEN r.workflow_stage NOT IN ('complete', 'review') THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN r.workflow_stage = 'review' THEN 1 ELSE 0 END) as pending_review,
            SUM(CASE WHEN r.complexity = 'simple' THEN 1 ELSE 0 END) as simple,
            SUM(CASE WHEN r.complexity = 'standard' THEN 1 ELSE 0 END) as standard,
            SUM(CASE WHEN r.complexity = 'complex' THEN 1 ELSE 0 END) as complex,
            SUM(CASE WHEN r.complexity = 'very_complex' THEN 1 ELSE 0 END) as very_complex
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.created_at >= :period_start
    """)
    returns_result = await session.execute(returns_query, {
        "firm_id": firm_id,
        "period_start": period_start.isoformat(),
    })
    returns_row = returns_result.fetchone()

    # Get client statistics
    clients_query = text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN c.is_active THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN c.created_at >= :period_start THEN 1 ELSE 0 END) as new_this_period
        FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
    """)
    clients_result = await session.execute(clients_query, {
        "firm_id": firm_id,
        "period_start": period_start.isoformat(),
    })
    clients_row = clients_result.fetchone()

    # Get team statistics
    team_query = text("""
        SELECT
            COUNT(*) as total_members,
            SUM(CASE WHEN u.last_login_at >= :period_start THEN 1 ELSE 0 END) as active_this_period
        FROM users u
        WHERE u.firm_id = :firm_id AND u.is_active = true
    """)
    team_result = await session.execute(team_query, {
        "firm_id": firm_id,
        "period_start": period_start.isoformat(),
    })
    team_row = team_result.fetchone()

    # Get revenue statistics
    revenue_query = text("""
        SELECT
            COALESCE(SUM(r.estimated_fee), 0) as total,
            COALESCE(SUM(CASE WHEN r.complexity = 'simple' THEN r.estimated_fee ELSE 0 END), 0) as simple,
            COALESCE(SUM(CASE WHEN r.complexity = 'standard' THEN r.estimated_fee ELSE 0 END), 0) as standard,
            COALESCE(SUM(CASE WHEN r.complexity = 'complex' THEN r.estimated_fee ELSE 0 END), 0) as complex,
            COALESCE(SUM(CASE WHEN r.complexity = 'very_complex' THEN r.estimated_fee ELSE 0 END), 0) as very_complex
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.created_at >= :period_start
    """)
    revenue_result = await session.execute(revenue_query, {
        "firm_id": firm_id,
        "period_start": period_start.isoformat(),
    })
    revenue_row = revenue_result.fetchone()

    # Calculate compliance score (simple algorithm)
    compliance_score = 100
    issues = 0
    warnings = 0

    # Check for overdue returns
    overdue_query = text("""
        SELECT COUNT(*) FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.workflow_stage != 'complete'
        AND r.deadline < :now
    """)
    overdue_result = await session.execute(overdue_query, {"firm_id": firm_id, "now": now.isoformat()})
    overdue_count = overdue_result.fetchone()[0] or 0
    if overdue_count > 0:
        issues = overdue_count
        compliance_score -= overdue_count * 5

    # Check for approaching deadlines
    warning_query = text("""
        SELECT COUNT(*) FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.workflow_stage != 'complete'
        AND r.deadline BETWEEN :now AND :warning_date
    """)
    warning_result = await session.execute(warning_query, {
        "firm_id": firm_id,
        "now": now.isoformat(),
        "warning_date": (now + timedelta(days=7)).isoformat(),
    })
    warning_count = warning_result.fetchone()[0] or 0
    warnings = warning_count
    compliance_score = max(0, compliance_score)

    return {
        "period": period,
        "returns": {
            "total": returns_row[0] or 0,
            "filed": returns_row[1] or 0,
            "in_progress": returns_row[2] or 0,
            "pending_review": returns_row[3] or 0,
            "by_complexity": {
                "simple": returns_row[4] or 0,
                "standard": returns_row[5] or 0,
                "complex": returns_row[6] or 0,
                "very_complex": returns_row[7] or 0,
            },
        },
        "clients": {
            "total": clients_row[0] or 0,
            "active": clients_row[1] or 0,
            "new_this_period": clients_row[2] or 0,
        },
        "team": {
            "total_members": team_row[0] or 0,
            "active_this_period": team_row[1] or 0,
        },
        "revenue": {
            "estimated_total": float(revenue_row[0] or 0),
            "by_complexity": {
                "simple": float(revenue_row[1] or 0),
                "standard": float(revenue_row[2] or 0),
                "complex": float(revenue_row[3] or 0),
                "very_complex": float(revenue_row[4] or 0),
            },
        },
        "compliance": {
            "score": compliance_score,
            "issues": issues,
            "warnings": warnings,
        },
    }
