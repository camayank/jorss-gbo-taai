"""
Compliance & Audit Routes - Audit trail and compliance management.

Provides:
- Audit log viewing
- Activity monitoring
- Compliance reports
- Data retention management
"""

from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..auth.rbac import (
    get_current_user,
    TenantContext,
    require_permission,
    require_firm_admin,
)
from ..models.user import UserPermission
from ..services.audit_service import AuditService, AuditAction


router = APIRouter(tags=["Compliance & Audit"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class AuditLogEntry(BaseModel):
    """Single audit log entry."""
    log_id: str
    user_id: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: dict
    ip_address: Optional[str]
    timestamp: str


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""
    logs: List[AuditLogEntry]
    total: int
    limit: int
    offset: int


class ActivitySummary(BaseModel):
    """Activity summary for a user or firm."""
    period_days: int
    total_actions: int
    action_breakdown: dict
    last_login: Optional[str]


class ComplianceReport(BaseModel):
    """Compliance report structure."""
    firm_id: str
    report_period: dict
    generated_at: str
    summary: dict
    compliance_flags: List[dict]


class RetentionPolicy(BaseModel):
    """Data retention policy."""
    audit_logs: dict
    client_data: dict
    session_data: dict


# =============================================================================
# AUDIT LOG ROUTES
# =============================================================================

@router.get("/audit/logs", response_model=AuditLogResponse)
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_audit_logs(
    user: TenantContext = Depends(get_current_user),
    user_id_filter: Optional[str] = Query(None, alias="user_id", description="Filter by user ID"),
    action_filter: Optional[str] = Query(None, alias="action", description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Get audit logs for the firm.

    Supports filtering by user, action type, resource, and date range.
    Requires VIEW_AUDIT_LOGS permission.
    """
    # Parse dates
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    # Parse action filter to list
    actions = action_filter.split(",") if action_filter else None

    # Get logs from service (would inject actual DB session)
    audit_service = AuditService(None)  # Placeholder

    logs = await audit_service.get_audit_logs(
        firm_id=user.firm_id,
        user_id=user_id_filter,
        action_filter=actions,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_dt,
        end_date=end_dt,
        limit=limit,
        offset=offset,
    )

    return {
        "logs": logs,
        "total": len(logs),  # Would be actual count from DB
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit/logs/{log_id}")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_audit_log_detail(
    log_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get detailed information about a specific audit log entry."""
    audit_service = AuditService(None)

    log = await audit_service.get_audit_log(user.firm_id, log_id)

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found",
        )

    # Verify integrity
    is_valid = await audit_service.verify_log_integrity(log_id)

    return {
        **log,
        "integrity_verified": is_valid,
    }


@router.get("/audit/actions")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def list_audit_actions(
    user: TenantContext = Depends(get_current_user),
):
    """List all available audit action types."""
    return {
        "actions": [
            {"value": action.value, "name": action.name}
            for action in AuditAction
        ]
    }


# =============================================================================
# ACTIVITY MONITORING ROUTES
# =============================================================================

@router.get("/audit/activity/summary")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_firm_activity_summary(
    user: TenantContext = Depends(get_current_user),
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
):
    """
    Get activity summary for the entire firm.

    Shows action counts, daily breakdown, and most active users.
    """
    audit_service = AuditService(None)

    summary = await audit_service.get_firm_activity_summary(
        firm_id=user.firm_id,
        days=days,
    )

    return summary


@router.get("/audit/activity/user/{target_user_id}")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_user_activity(
    target_user_id: str,
    user: TenantContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
):
    """Get activity summary for a specific user."""
    audit_service = AuditService(None)

    activity = await audit_service.get_user_activity(
        firm_id=user.firm_id,
        user_id=target_user_id,
        days=days,
    )

    return activity


@router.get("/audit/activity/recent")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_recent_activity(
    user: TenantContext = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
):
    """Get recent activity feed for dashboard."""
    audit_service = AuditService(None)

    feed = await audit_service.get_recent_activity(
        firm_id=user.firm_id,
        limit=limit,
    )

    return {"activity": feed}


@router.get("/audit/activity/resource/{resource_type}/{resource_id}")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_resource_access_history(
    resource_type: str,
    resource_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get access history for a specific resource."""
    audit_service = AuditService(None)

    report = await audit_service.generate_access_report(
        firm_id=user.firm_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )

    return report


# =============================================================================
# COMPLIANCE REPORTING ROUTES
# =============================================================================

@router.get("/compliance/report")
@require_firm_admin
async def generate_compliance_report(
    user: TenantContext = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="Report start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Report end date (ISO format)"),
):
    """
    Generate compliance report for auditors.

    Includes security events, data access logs, user management changes,
    and any compliance flags.
    """
    # Default to last 90 days
    end_dt = datetime.fromisoformat(end_date) if end_date else datetime.utcnow()
    start_dt = datetime.fromisoformat(start_date) if start_date else end_dt - timedelta(days=90)

    audit_service = AuditService(None)

    report = await audit_service.generate_compliance_report(
        firm_id=user.firm_id,
        start_date=start_dt,
        end_date=end_dt,
    )

    return report


@router.get("/compliance/status")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_compliance_status(
    user: TenantContext = Depends(get_current_user),
):
    """Get current compliance status and any flags."""
    audit_service = AuditService(None)

    retention_check = await audit_service.check_retention_compliance(user.firm_id)

    return {
        "firm_id": user.firm_id,
        "checked_at": datetime.utcnow().isoformat(),
        "retention_compliance": retention_check,
        "overall_status": "compliant" if retention_check["is_compliant"] else "review_needed",
    }


@router.get("/compliance/retention-policy")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_retention_policy(
    user: TenantContext = Depends(get_current_user),
):
    """Get data retention policy for the firm."""
    audit_service = AuditService(None)

    policy = await audit_service.get_retention_policy(user.firm_id)

    return policy


# =============================================================================
# EXPORT ROUTES
# =============================================================================

@router.post("/audit/export")
@require_firm_admin
async def export_audit_logs(
    user: TenantContext = Depends(get_current_user),
    start_date: str = Query(..., description="Export start date (ISO format)"),
    end_date: str = Query(..., description="Export end date (ISO format)"),
    format: str = Query("json", description="Export format: json, csv"),
):
    """
    Export audit logs for external use.

    This action is itself logged for compliance.
    Requires firm admin permission.
    """
    audit_service = AuditService(None)

    # Log the export action
    await audit_service.log_action(
        firm_id=user.firm_id,
        user_id=user.user_id,
        action=AuditAction.DATA_EXPORTED.value,
        resource_type="audit_logs",
        details={
            "start_date": start_date,
            "end_date": end_date,
            "format": format,
        },
    )

    # Get logs
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)

    logs = await audit_service.get_audit_logs(
        firm_id=user.firm_id,
        start_date=start_dt,
        end_date=end_dt,
        limit=10000,
    )

    if format == "csv":
        # Would generate CSV
        return {
            "status": "success",
            "format": "csv",
            "record_count": len(logs),
            "download_url": f"/api/v1/admin/audit/export/download/export-{user.firm_id}.csv",
        }
    else:
        return {
            "status": "success",
            "format": "json",
            "record_count": len(logs),
            "data": logs,
        }


# =============================================================================
# SECURITY MONITORING ROUTES
# =============================================================================

@router.get("/security/failed-logins")
@require_permission(UserPermission.VIEW_AUDIT_LOGS)
async def get_failed_login_attempts(
    user: TenantContext = Depends(get_current_user),
    days: int = Query(7, ge=1, le=30),
):
    """Get failed login attempts for security monitoring."""
    audit_service = AuditService(None)

    cutoff = datetime.utcnow() - timedelta(days=days)

    logs = await audit_service.get_audit_logs(
        firm_id=user.firm_id,
        action_filter=[AuditAction.LOGIN_FAILED.value],
        start_date=cutoff,
        limit=500,
    )

    # Group by IP
    by_ip = {}
    for log in logs:
        ip = log.get("ip_address", "unknown")
        by_ip[ip] = by_ip.get(ip, 0) + 1

    # Group by user
    by_user = {}
    for log in logs:
        user_id = log.get("details", {}).get("attempted_email", "unknown")
        by_user[user_id] = by_user.get(user_id, 0) + 1

    return {
        "total_failures": len(logs),
        "period_days": days,
        "by_ip_address": by_ip,
        "by_attempted_user": by_user,
        "recent_attempts": logs[:20],
    }


@router.get("/security/sensitive-actions")
@require_firm_admin
async def get_sensitive_actions(
    user: TenantContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=90),
):
    """Get log of sensitive/privileged actions."""
    sensitive_actions = [
        AuditAction.USER_DEACTIVATED.value,
        AuditAction.ROLE_CHANGED.value,
        AuditAction.MFA_DISABLED.value,
        AuditAction.API_KEY_CREATED.value,
        AuditAction.API_KEY_REVOKED.value,
        AuditAction.SETTINGS_UPDATED.value,
        AuditAction.DATA_EXPORTED.value,
        AuditAction.CLIENT_DELETED.value,
    ]

    audit_service = AuditService(None)
    cutoff = datetime.utcnow() - timedelta(days=days)

    logs = await audit_service.get_audit_logs(
        firm_id=user.firm_id,
        action_filter=sensitive_actions,
        start_date=cutoff,
        limit=500,
    )

    return {
        "sensitive_actions": logs,
        "total": len(logs),
        "period_days": days,
    }
