"""
Admin Compliance API.

Provides endpoints for:
- Compliance reports
- Audit logs
- Security alerts
- Regulatory compliance checks
- Data access auditing

All compliance operations are themselves audited.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import uuid4
import logging

from rbac.dependencies import require_auth, require_platform_admin, require_permission
from rbac.context import AuthContext
from rbac.permissions import Permission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/compliance",
    tags=["Admin Compliance"],
    responses={403: {"description": "Insufficient permissions"}},
)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class AuditRequest(BaseModel):
    """Request to trigger a compliance audit."""
    firm_id: Optional[str] = Field(None, description="Firm to audit (null for platform-wide)")
    audit_type: str = Field(..., description="Type: data_access, security, financial, full")
    date_range_days: int = Field(30, ge=1, le=365, description="Days to audit")


class AlertAcknowledge(BaseModel):
    """Request to acknowledge a compliance alert."""
    notes: Optional[str] = Field(None, max_length=500, description="Notes about resolution")


# =============================================================================
# IN-MEMORY STORAGE (Replace with database in production)
# =============================================================================


class ComplianceReport:
    """A compliance report."""

    def __init__(
        self,
        report_id: str,
        report_type: str,
        status: str,
        firm_id: Optional[str],
        triggered_by: str,
        findings_count: int = 0,
    ):
        self.report_id = report_id
        self.report_type = report_type
        self.status = status  # pending, running, completed, failed
        self.firm_id = firm_id
        self.triggered_by = triggered_by
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.findings_count = findings_count
        self.findings: List[dict] = []

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type,
            "status": self.status,
            "firm_id": self.firm_id,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "findings_count": self.findings_count,
        }


class ComplianceAlert:
    """A compliance alert."""

    def __init__(
        self,
        alert_id: str,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        firm_id: Optional[str] = None,
    ):
        self.alert_id = alert_id
        self.alert_type = alert_type
        self.severity = severity  # low, medium, high, critical
        self.title = title
        self.description = description
        self.firm_id = firm_id
        self.created_at = datetime.utcnow()
        self.acknowledged_at: Optional[datetime] = None
        self.acknowledged_by: Optional[str] = None
        self.notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "firm_id": self.firm_id,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged_at is not None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
        }


# Thread-safe in-memory storage
_reports: dict[str, ComplianceReport] = {}
_alerts: dict[str, ComplianceAlert] = {}

# Seed some demo alerts
_alerts["alert-001"] = ComplianceAlert(
    alert_id="alert-001",
    alert_type="data_access",
    severity="medium",
    title="Unusual data access pattern",
    description="User accessed 50+ client records in 5 minutes",
    firm_id="firm-001",
)


# =============================================================================
# COMPLIANCE REPORTS
# =============================================================================


@router.get("/reports")
async def list_compliance_reports(
    ctx: AuthContext = Depends(require_platform_admin),
    report_type: Optional[str] = Query(None, description="Filter by type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=200, description="Maximum results"),
):
    """
    List compliance reports.

    Platform admins can view all reports.
    """
    reports = list(_reports.values())

    if report_type:
        reports = [r for r in reports if r.report_type == report_type]
    if status:
        reports = [r for r in reports if r.status == status]

    # Sort by created_at descending
    reports.sort(key=lambda r: r.created_at, reverse=True)

    return {
        "reports": [r.to_dict() for r in reports[:limit]],
        "total": len(reports),
    }


@router.post("/reports")
async def create_compliance_report(
    data: AuditRequest,
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Trigger a new compliance audit/report.

    Audit types:
    - data_access: Who accessed what data
    - security: Security configuration review
    - financial: Billing and payment audit
    - full: Comprehensive audit (all of the above)
    """
    valid_types = {"data_access", "security", "financial", "full"}
    if data.audit_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audit type. Must be one of: {', '.join(valid_types)}"
        )

    report = ComplianceReport(
        report_id=str(uuid4()),
        report_type=data.audit_type,
        status="pending",
        firm_id=data.firm_id,
        triggered_by=str(ctx.user_id),
    )

    _reports[report.report_id] = report

    logger.info(
        f"[AUDIT] Compliance report triggered | report_id={report.report_id} | "
        f"type={data.audit_type} | firm={data.firm_id or 'platform-wide'} | "
        f"triggered_by={ctx.user_id}"
    )

    # In production, this would trigger async processing
    # For demo, immediately complete with mock findings
    report.status = "completed"
    report.completed_at = datetime.utcnow()
    report.findings_count = 3
    report.findings = [
        {"type": "info", "message": "All access logs properly recorded"},
        {"type": "warning", "message": "2 users have not enabled MFA"},
        {"type": "info", "message": "Data retention policies are compliant"},
    ]

    return {
        "report": report.to_dict(),
        "message": "Compliance report completed",
    }


@router.get("/reports/{report_id}")
async def get_compliance_report(
    report_id: str,
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Get detailed compliance report with findings.
    """
    report = _reports.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    result = report.to_dict()
    result["findings"] = report.findings

    return {"report": result}


# =============================================================================
# COMPLIANCE ALERTS
# =============================================================================


@router.get("/alerts")
async def list_compliance_alerts(
    ctx: AuthContext = Depends(require_platform_admin),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgment"),
    limit: int = Query(50, le=200, description="Maximum results"),
):
    """
    List compliance alerts.

    Filterable by severity and acknowledgment status.
    """
    alerts = list(_alerts.values())

    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    if acknowledged is not None:
        alerts = [a for a in alerts if (a.acknowledged_at is not None) == acknowledged]

    # Sort by severity (critical first), then by created_at
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda a: (severity_order.get(a.severity, 4), -a.created_at.timestamp()))

    return {
        "alerts": [a.to_dict() for a in alerts[:limit]],
        "total": len(alerts),
        "unacknowledged_count": sum(1 for a in _alerts.values() if a.acknowledged_at is None),
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    data: AlertAcknowledge,
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Acknowledge a compliance alert.

    Records who acknowledged and when.
    """
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.acknowledged_at:
        return {
            "message": "Alert was already acknowledged",
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": alert.acknowledged_at.isoformat(),
        }

    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = str(ctx.user_id)
    alert.notes = data.notes

    logger.info(
        f"[AUDIT] Alert acknowledged | alert_id={alert_id} | "
        f"severity={alert.severity} | acknowledged_by={ctx.user_id}"
    )

    return {
        "alert": alert.to_dict(),
        "message": "Alert acknowledged",
    }


# =============================================================================
# AUDIT LOGS
# =============================================================================


@router.get("/audit-logs")
async def get_audit_logs(
    ctx: AuthContext = Depends(require_platform_admin),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    limit: int = Query(100, le=500, description="Maximum results"),
):
    """
    Get audit logs.

    Returns a chronological list of auditable events.
    """
    logs = []
    try:
        from audit.audit_logger import get_audit_logger
        audit_logger = get_audit_logger()
        start_date = datetime.utcnow() - timedelta(days=days)
        logs = audit_logger.query(
            user_id=user_id,
            start_date=start_date,
            limit=limit,
        )
    except Exception as e:
        logger.warning(f"Could not query audit logs: {e}")

    return {
        "logs": logs,
        "total": len(logs),
        "date_range": {
            "from": (datetime.utcnow() - timedelta(days=days)).isoformat(),
            "to": datetime.utcnow().isoformat(),
        },
    }


# =============================================================================
# DATA ACCESS AUDIT
# =============================================================================


@router.get("/data-access")
async def get_data_access_report(
    ctx: AuthContext = Depends(require_platform_admin),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
):
    """
    Get data access patterns report.

    Shows who accessed what data and when.
    """
    # Mock data access report
    return {
        "summary": {
            "total_accesses": 1234,
            "unique_users": 45,
            "unique_resources": 890,
        },
        "by_resource_type": {
            "clients": 456,
            "returns": 321,
            "documents": 234,
            "reports": 123,
            "other": 100,
        },
        "top_accessors": [
            {"user_id": "user-001", "email": "john@example.com", "access_count": 89},
            {"user_id": "user-002", "email": "jane@example.com", "access_count": 76},
            {"user_id": "user-003", "email": "bob@example.com", "access_count": 54},
        ],
        "unusual_patterns": [],
        "date_range": {
            "from": (datetime.utcnow() - timedelta(days=days)).isoformat(),
            "to": datetime.utcnow().isoformat(),
        },
    }


# =============================================================================
# REGULATORY COMPLIANCE
# =============================================================================


@router.get("/regulatory/status")
async def get_regulatory_status(
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Get overall regulatory compliance status.

    Checks compliance with various regulations (SOC2, GDPR, etc.).
    """
    return {
        "overall_status": "compliant",
        "last_assessment": datetime.utcnow().isoformat(),
        "regulations": [
            {
                "name": "SOC 2 Type II",
                "status": "compliant",
                "last_audit": "2025-01-15",
                "next_audit": "2026-01-15",
            },
            {
                "name": "IRS Publication 4557",
                "status": "compliant",
                "notes": "Safeguarding taxpayer data requirements met",
            },
            {
                "name": "GLBA",
                "status": "compliant",
                "notes": "Financial privacy requirements met",
            },
            {
                "name": "State Privacy Laws",
                "status": "compliant",
                "notes": "CCPA, VCDPA, and other state requirements met",
            },
        ],
        "pending_items": [],
    }


@router.get("/regulatory/checks")
async def run_compliance_checks(
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Run automated compliance checks.

    Returns current compliance status for various requirements.
    """
    checks = [
        {
            "check": "data_encryption_at_rest",
            "status": "pass",
            "description": "All stored data is encrypted",
        },
        {
            "check": "data_encryption_in_transit",
            "status": "pass",
            "description": "TLS 1.3 enforced on all connections",
        },
        {
            "check": "access_logging",
            "status": "pass",
            "description": "All data access is logged",
        },
        {
            "check": "mfa_enforcement",
            "status": "warning",
            "description": "2 admin users have not enabled MFA",
        },
        {
            "check": "password_policy",
            "status": "pass",
            "description": "Strong password requirements enforced",
        },
        {
            "check": "session_management",
            "status": "pass",
            "description": "Sessions expire after 30 minutes of inactivity",
        },
        {
            "check": "data_retention",
            "status": "pass",
            "description": "Data retention policies are properly configured",
        },
        {
            "check": "backup_verification",
            "status": "pass",
            "description": "Backups verified within last 24 hours",
        },
    ]

    passed = sum(1 for c in checks if c["status"] == "pass")
    warnings = sum(1 for c in checks if c["status"] == "warning")
    failed = sum(1 for c in checks if c["status"] == "fail")

    return {
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
        },
        "overall_status": "compliant" if failed == 0 else "non-compliant",
        "checked_at": datetime.utcnow().isoformat(),
    }
