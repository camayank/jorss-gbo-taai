"""
Alert Routes - AI-driven alerts and notifications.

Provides:
- Alert viewing and management
- Alert acknowledgment
- Notification preferences
- Alert generation triggers
"""

from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ..auth.rbac import (
    get_current_user,
    TenantContext,
    require_permission,
    require_firm_admin,
)
from ..models.user import UserPermission
from ..services.alert_service import AlertService, AlertType, AlertPriority, AlertStatus


router = APIRouter(tags=["Alerts & Notifications"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class AlertItem(BaseModel):
    """Alert item."""
    alert_id: str
    alert_type: str
    priority: str
    status: str
    title: str
    message: str
    client_id: Optional[str]
    action_url: Optional[str]
    created_at: str


class AlertSummary(BaseModel):
    """Alert summary for dashboard."""
    total_active: int
    by_priority: dict
    by_type: dict
    critical_count: int
    high_count: int


class NotificationPreferences(BaseModel):
    """User notification preferences."""
    email_enabled: bool
    email_digest: str
    push_enabled: bool
    sms_enabled: bool
    quiet_hours: dict
    alert_types: dict


# =============================================================================
# ALERT LISTING ROUTES
# =============================================================================

@router.get("/alerts", response_model=List[AlertItem])
async def list_alerts(
    user: TenantContext = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    type_filter: Optional[str] = Query(None, alias="type", description="Filter by alert type"),
    priority_filter: Optional[str] = Query(None, alias="priority", description="Filter by priority"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List alerts for the current user/firm.

    Supports filtering by status, type, and priority.
    """
    alert_service = AlertService(None)

    # Parse filters to lists
    statuses = status_filter.split(",") if status_filter else None
    types = type_filter.split(",") if type_filter else None
    priorities = priority_filter.split(",") if priority_filter else None

    alerts = await alert_service.get_alerts(
        firm_id=user.firm_id,
        status_filter=statuses,
        type_filter=types,
        priority_filter=priorities,
        user_id=user.user_id,
        limit=limit,
        offset=offset,
    )

    return alerts


@router.get("/alerts/summary", response_model=AlertSummary)
async def get_alert_summary(
    user: TenantContext = Depends(get_current_user),
):
    """Get alert summary for dashboard widget."""
    alert_service = AlertService(None)

    summary = await alert_service.get_alert_summary(user.firm_id)

    return summary


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get details for a specific alert."""
    alert_service = AlertService(None)

    alert = await alert_service.get_alert(user.firm_id, alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return alert


# =============================================================================
# ALERT ACTION ROUTES
# =============================================================================

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Acknowledge an alert."""
    alert_service = AlertService(None)

    success = await alert_service.acknowledge_alert(
        firm_id=user.firm_id,
        alert_id=alert_id,
        user_id=user.user_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return {"status": "acknowledged", "alert_id": alert_id}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    user: TenantContext = Depends(get_current_user),
    note: Optional[str] = Query(None, description="Resolution note"),
):
    """Resolve an alert."""
    alert_service = AlertService(None)

    success = await alert_service.resolve_alert(
        firm_id=user.firm_id,
        alert_id=alert_id,
        user_id=user.user_id,
        resolution_note=note,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return {"status": "resolved", "alert_id": alert_id}


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Dismiss an alert."""
    alert_service = AlertService(None)

    success = await alert_service.dismiss_alert(
        firm_id=user.firm_id,
        alert_id=alert_id,
        user_id=user.user_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return {"status": "dismissed", "alert_id": alert_id}


@router.post("/alerts/{alert_id}/snooze")
async def snooze_alert(
    alert_id: str,
    user: TenantContext = Depends(get_current_user),
    hours: int = Query(24, ge=1, le=168, description="Hours to snooze"),
):
    """Snooze an alert for a specified duration."""
    alert_service = AlertService(None)

    snooze_until = datetime.utcnow() + timedelta(hours=hours)

    success = await alert_service.snooze_alert(
        firm_id=user.firm_id,
        alert_id=alert_id,
        user_id=user.user_id,
        snooze_until=snooze_until,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return {
        "status": "snoozed",
        "alert_id": alert_id,
        "snooze_until": snooze_until.isoformat(),
    }


@router.post("/alerts/bulk-acknowledge")
async def bulk_acknowledge_alerts(
    alert_ids: List[str] = Query(..., description="Alert IDs to acknowledge"),
    user: TenantContext = Depends(get_current_user),
):
    """Acknowledge multiple alerts at once."""
    alert_service = AlertService(None)

    acknowledged = 0
    for alert_id in alert_ids:
        success = await alert_service.acknowledge_alert(
            firm_id=user.firm_id,
            alert_id=alert_id,
            user_id=user.user_id,
        )
        if success:
            acknowledged += 1

    return {
        "status": "success",
        "acknowledged_count": acknowledged,
        "total_requested": len(alert_ids),
    }


# =============================================================================
# ALERT GENERATION ROUTES (AI-DRIVEN)
# =============================================================================

@router.post("/alerts/generate/deadlines")
@require_firm_admin
async def generate_deadline_alerts(
    user: TenantContext = Depends(get_current_user),
):
    """
    Trigger deadline alert generation.

    Analyzes upcoming deadlines and creates alerts as needed.
    """
    alert_service = AlertService(None)

    alerts = await alert_service.generate_deadline_alerts(user.firm_id)

    return {
        "status": "success",
        "alerts_created": len(alerts),
        "alerts": alerts,
    }


@router.post("/alerts/generate/compliance")
@require_firm_admin
async def generate_compliance_alerts(
    user: TenantContext = Depends(get_current_user),
):
    """
    Trigger compliance alert generation.

    Analyzes client data for compliance issues.
    """
    alert_service = AlertService(None)

    alerts = await alert_service.generate_compliance_alerts(user.firm_id)

    return {
        "status": "success",
        "alerts_created": len(alerts),
        "alerts": alerts,
    }


@router.post("/alerts/generate/usage")
@require_firm_admin
async def generate_usage_alerts(
    user: TenantContext = Depends(get_current_user),
):
    """
    Trigger usage threshold alerts.

    Checks subscription limits and generates warnings.
    """
    alert_service = AlertService(None)

    alerts = await alert_service.generate_usage_alerts(user.firm_id)

    return {
        "status": "success",
        "alerts_created": len(alerts),
        "alerts": alerts,
    }


@router.post("/alerts/generate/opportunities")
@require_firm_admin
async def generate_opportunity_alerts(
    user: TenantContext = Depends(get_current_user),
):
    """
    Trigger AI opportunity identification.

    Analyzes client data to identify tax optimization opportunities.
    """
    alert_service = AlertService(None)

    alerts = await alert_service.generate_opportunity_alerts(user.firm_id)

    return {
        "status": "success",
        "alerts_created": len(alerts),
        "alerts": alerts,
    }


@router.post("/alerts/generate/all")
@require_firm_admin
async def generate_all_alerts(
    user: TenantContext = Depends(get_current_user),
):
    """
    Trigger all alert generation types.

    Useful for daily batch processing.
    """
    alert_service = AlertService(None)

    all_alerts = []

    # Generate each type
    deadline_alerts = await alert_service.generate_deadline_alerts(user.firm_id)
    all_alerts.extend(deadline_alerts)

    compliance_alerts = await alert_service.generate_compliance_alerts(user.firm_id)
    all_alerts.extend(compliance_alerts)

    usage_alerts = await alert_service.generate_usage_alerts(user.firm_id)
    all_alerts.extend(usage_alerts)

    opportunity_alerts = await alert_service.generate_opportunity_alerts(user.firm_id)
    all_alerts.extend(opportunity_alerts)

    return {
        "status": "success",
        "total_alerts_created": len(all_alerts),
        "by_type": {
            "deadlines": len(deadline_alerts),
            "compliance": len(compliance_alerts),
            "usage": len(usage_alerts),
            "opportunities": len(opportunity_alerts),
        },
    }


# =============================================================================
# ALERT ANALYTICS ROUTES
# =============================================================================

@router.get("/alerts/trends")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_alert_trends(
    user: TenantContext = Depends(get_current_user),
    days: int = Query(30, ge=7, le=90, description="Days to analyze"),
):
    """Get alert trends for analysis."""
    alert_service = AlertService(None)

    trends = await alert_service.get_alert_trends(user.firm_id, days)

    return trends


@router.get("/alerts/types")
async def list_alert_types(
    user: TenantContext = Depends(get_current_user),
):
    """List all available alert types."""
    return {
        "types": [
            {"value": t.value, "name": t.name, "description": _get_alert_type_description(t)}
            for t in AlertType
        ],
        "priorities": [
            {"value": p.value, "name": p.name}
            for p in AlertPriority
        ],
        "statuses": [
            {"value": s.value, "name": s.name}
            for s in AlertStatus
        ],
    }


# =============================================================================
# NOTIFICATION PREFERENCES ROUTES
# =============================================================================

@router.get("/notifications/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    user: TenantContext = Depends(get_current_user),
):
    """Get notification preferences for current user."""
    alert_service = AlertService(None)

    prefs = await alert_service.get_notification_preferences(
        firm_id=user.firm_id,
        user_id=user.user_id,
    )

    return prefs


@router.put("/notifications/preferences")
async def update_notification_preferences(
    request: Request,
    user: TenantContext = Depends(get_current_user),
    email_enabled: Optional[bool] = Query(None),
    email_digest: Optional[str] = Query(None, description="daily, weekly, realtime"),
    push_enabled: Optional[bool] = Query(None),
    sms_enabled: Optional[bool] = Query(None),
):
    """Update notification preferences for current user."""
    alert_service = AlertService(None)

    # Build update dict from query params and/or JSON body
    updates = {}
    if email_enabled is not None:
        updates["email_enabled"] = email_enabled
    if email_digest is not None:
        updates["email_digest"] = email_digest
    if push_enabled is not None:
        updates["push_enabled"] = push_enabled
    if sms_enabled is not None:
        updates["sms_enabled"] = sms_enabled

    # Also accept JSON body (from CPA settings page)
    try:
        body = await request.json()
        if isinstance(body, dict):
            for key in ("email_enabled", "email_digest", "push_enabled", "sms_enabled",
                        "digest_frequency", "quiet_hours", "notifications"):
                if key in body:
                    updates[key] = body[key]
    except Exception:
        pass

    # Store preferences
    await alert_service.update_notification_preferences(
        firm_id=user.firm_id,
        user_id=user.user_id,
        preferences=updates,
    )

    return {
        "status": "success",
        "updated_preferences": updates,
    }


@router.get("/notifications/digest")
async def get_notification_digest(
    user: TenantContext = Depends(get_current_user),
):
    """Get current notification digest (preview of what would be sent)."""
    alert_service = AlertService(None)

    digest = await alert_service.compile_daily_digest(user.firm_id)

    return digest


# =============================================================================
# HELPERS
# =============================================================================

def _get_alert_type_description(alert_type: AlertType) -> str:
    """Get description for alert type."""
    descriptions = {
        AlertType.DEADLINE: "Upcoming deadlines and due dates",
        AlertType.COMPLIANCE: "Compliance issues and requirements",
        AlertType.USAGE: "Usage limits and threshold warnings",
        AlertType.SECURITY: "Security-related notifications",
        AlertType.BILLING: "Billing and payment alerts",
        AlertType.PERFORMANCE: "Performance and efficiency insights",
        AlertType.SYSTEM: "System updates and maintenance",
        AlertType.CLIENT: "Client-related notifications",
        AlertType.OPPORTUNITY: "AI-identified tax optimization opportunities",
    }
    return descriptions.get(alert_type, "")
