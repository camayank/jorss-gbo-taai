"""
Audit Trail API

REST API endpoints for accessing and managing audit logs.
Provides compliance-ready audit trail export for tax filing sessions.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import logging

# Import audit logger
try:
    from audit.audit_logger import (
        get_audit_logger,
        get_session_audit_trail,
        export_session_audit_report,
        AuditEventType,
        AuditSeverity
    )
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Trail"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class AuditEventResponse(BaseModel):
    """Single audit event response."""
    event_id: str
    event_type: str
    timestamp: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    user_id: Optional[str]
    details: Optional[dict]
    old_value: Optional[dict]
    new_value: Optional[dict]
    success: bool


class AuditSummaryResponse(BaseModel):
    """Audit summary response."""
    session_id: str
    total_events: int
    actions: dict
    sources: dict
    fields: dict
    first_event: Optional[str]
    last_event: Optional[str]


class AuditReportResponse(BaseModel):
    """Full audit report response."""
    report_type: str
    session_id: str
    generated_at: str
    summary: dict
    timeline: List[dict]
    taxpayer_info: Optional[dict]


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/session/{session_id}", response_model=List[dict])
async def get_session_audit(
    session_id: str,
    event_type: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """
    Get audit trail for a specific tax filing session.

    Returns a chronological list of all changes and actions during the session.
    """
    if not AUDIT_AVAILABLE:
        raise HTTPException(status_code=501, detail="Audit trail not available")

    audit_logger = get_audit_logger()

    try:
        events = audit_logger.query(
            resource_id=session_id,
            limit=limit,
            offset=offset
        )

        # Filter by event type if specified
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]

        return events

    except Exception as e:
        logger.error(f"Error retrieving audit trail for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/summary")
async def get_session_audit_summary(session_id: str):
    """
    Get summary of audit activity for a session.

    Returns aggregated counts by action type, source, and field.
    """
    if not AUDIT_AVAILABLE:
        raise HTTPException(status_code=501, detail="Audit trail not available")

    try:
        events = get_session_audit_trail(session_id)

        if not events:
            return {
                "session_id": session_id,
                "total_events": 0,
                "actions": {},
                "sources": {},
                "fields": {},
                "first_event": None,
                "last_event": None
            }

        actions = {}
        sources = {}
        fields = {}

        for event in events:
            # Count by action
            action = event.get("action", "unknown")
            actions[action] = actions.get(action, 0) + 1

            # Count by source
            details = event.get("details", {}) or {}
            source = details.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1

            # Count by field
            field_name = details.get("field_name", event.get("resource_type", "unknown"))
            fields[field_name] = fields.get(field_name, 0) + 1

        return {
            "session_id": session_id,
            "total_events": len(events),
            "actions": actions,
            "sources": sources,
            "fields": fields,
            "first_event": events[-1].get("timestamp") if events else None,
            "last_event": events[0].get("timestamp") if events else None
        }

    except Exception as e:
        logger.error(f"Error generating audit summary for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/report")
async def get_session_audit_report(session_id: str):
    """
    Export comprehensive audit report for compliance purposes.

    Returns a full report including timeline, summary, and taxpayer information.
    Suitable for CPA review and IRS compliance documentation.
    """
    if not AUDIT_AVAILABLE:
        raise HTTPException(status_code=501, detail="Audit trail not available")

    try:
        report = export_session_audit_report(session_id)
        return report

    except Exception as e:
        logger.error(f"Error generating audit report for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/field/{field_name}")
async def get_field_history(session_id: str, field_name: str):
    """
    Get complete history of changes to a specific field.

    Useful for understanding how a value changed over time.
    """
    if not AUDIT_AVAILABLE:
        raise HTTPException(status_code=501, detail="Audit trail not available")

    audit_logger = get_audit_logger()

    try:
        events = audit_logger.query(resource_id=session_id, limit=1000)

        # Filter for events related to this field
        field_events = []
        for event in events:
            details = event.get("details", {}) or {}
            if details.get("field_name") == field_name:
                field_events.append(event)
            elif field_name in event.get("action", ""):
                field_events.append(event)

        return {
            "session_id": session_id,
            "field_name": field_name,
            "total_changes": len(field_events),
            "history": field_events
        }

    except Exception as e:
        logger.error(f"Error retrieving field history for {field_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/calculations")
async def get_calculation_history(session_id: str):
    """
    Get history of all tax calculations for a session.

    Shows how the tax estimate evolved as data was entered.
    """
    if not AUDIT_AVAILABLE:
        raise HTTPException(status_code=501, detail="Audit trail not available")

    audit_logger = get_audit_logger()

    try:
        events = audit_logger.query(resource_id=session_id, limit=1000)

        # Filter for calculation events
        calculations = [
            e for e in events
            if "calculation" in e.get("event_type", "") or "calculate" in e.get("action", "")
        ]

        return {
            "session_id": session_id,
            "total_calculations": len(calculations),
            "calculations": calculations
        }

    except Exception as e:
        logger.error(f"Error retrieving calculation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    days: int = Query(default=30, le=365)
):
    """
    Get recent audit activity for a specific user.

    Returns all events associated with the user within the specified timeframe.
    """
    if not AUDIT_AVAILABLE:
        raise HTTPException(status_code=501, detail="Audit trail not available")

    audit_logger = get_audit_logger()

    try:
        events = audit_logger.get_user_activity(user_id, days=days)
        return {
            "user_id": user_id,
            "days_queried": days,
            "total_events": len(events),
            "events": events
        }

    except Exception as e:
        logger.error(f"Error retrieving user activity for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/security/events")
async def get_security_events(
    days: int = Query(default=7, le=90),
    severity: Optional[str] = None
):
    """
    Get security-related audit events.

    Returns events such as permission denials, failed logins, and suspicious activity.
    """
    if not AUDIT_AVAILABLE:
        raise HTTPException(status_code=501, detail="Audit trail not available")

    audit_logger = get_audit_logger()

    try:
        events = audit_logger.get_security_events(days=days)

        # Filter by severity if specified
        if severity:
            events = [e for e in events if e.get("severity") == severity]

        return {
            "days_queried": days,
            "severity_filter": severity,
            "total_events": len(events),
            "events": events
        }

    except Exception as e:
        logger.error(f"Error retrieving security events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def audit_health_check():
    """
    Check if audit trail system is operational.
    """
    return {
        "status": "operational" if AUDIT_AVAILABLE else "unavailable",
        "audit_available": AUDIT_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }
