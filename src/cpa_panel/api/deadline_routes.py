"""
Deadline Management Routes

API endpoints for managing tax deadlines.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from uuid import UUID
import logging

from ..deadlines.deadline_service import deadline_service, DeadlineType, DeadlineStatus

logger = logging.getLogger(__name__)

deadline_router = APIRouter(prefix="/deadlines", tags=["Deadlines"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateDeadlineRequest(BaseModel):
    """Request to create a new deadline."""
    deadline_type: str = Field(..., description="Type of deadline")
    due_date: date = Field(..., description="Due date")
    title: Optional[str] = Field(None, description="Custom title")
    description: Optional[str] = Field(None, description="Description")
    client_id: Optional[str] = Field(None, description="Client ID (optional)")
    session_id: Optional[str] = Field(None, description="Tax return session ID")
    tax_year: int = Field(2025, description="Tax year")
    assigned_to: Optional[str] = Field(None, description="Staff member ID")
    priority: str = Field("normal", description="Priority: low, normal, high, urgent")
    auto_reminders: bool = Field(True, description="Add default reminders")


class UpdateDeadlineRequest(BaseModel):
    """Request to update a deadline."""
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None


class FileExtensionRequest(BaseModel):
    """Request to file an extension."""
    extended_date: date = Field(..., description="New extended due date")


class AddReminderRequest(BaseModel):
    """Request to add a reminder."""
    days_before: int = Field(..., ge=1, le=90, description="Days before deadline")
    reminder_type: str = Field("email", description="email, sms, in_app, push")
    recipient_type: str = Field("cpa", description="cpa, client, both")


class GenerateStandardDeadlinesRequest(BaseModel):
    """Request to generate standard deadlines."""
    tax_year: int = Field(2025, description="Tax year")
    client_id: Optional[str] = Field(None, description="Client ID (optional)")
    session_id: Optional[str] = Field(None, description="Session ID (optional)")
    include_estimated: bool = Field(True, description="Include estimated tax deadlines")


# =============================================================================
# DEADLINE CRUD
# =============================================================================

@deadline_router.post("")
async def create_deadline(
    request: CreateDeadlineRequest,
    firm_id: str = Query(..., description="Firm ID"),
    user_id: Optional[str] = Query(None, description="Creating user ID"),
):
    """
    Create a new deadline.

    Creates a deadline with optional automatic reminders.
    """
    try:
        deadline_type = DeadlineType(request.deadline_type)
    except ValueError:
        raise HTTPException(400, f"Invalid deadline type: {request.deadline_type}")

    deadline = deadline_service.create_deadline(
        firm_id=UUID(firm_id),
        deadline_type=deadline_type,
        due_date=request.due_date,
        title=request.title,
        description=request.description,
        client_id=UUID(request.client_id) if request.client_id else None,
        session_id=request.session_id,
        tax_year=request.tax_year,
        assigned_to=UUID(request.assigned_to) if request.assigned_to else None,
        priority=request.priority,
        created_by=UUID(user_id) if user_id else None,
        auto_reminders=request.auto_reminders,
    )

    return {
        "success": True,
        "deadline": deadline.to_dict(),
    }


@deadline_router.get("/{deadline_id}")
async def get_deadline(deadline_id: str):
    """Get a specific deadline by ID."""
    deadline = deadline_service.get_deadline(UUID(deadline_id))
    if not deadline:
        raise HTTPException(404, "Deadline not found")

    return {
        "success": True,
        "deadline": deadline.to_dict(),
    }


@deadline_router.put("/{deadline_id}")
async def update_deadline(
    deadline_id: str,
    request: UpdateDeadlineRequest,
):
    """Update a deadline."""
    deadline = deadline_service.update_deadline(
        deadline_id=UUID(deadline_id),
        title=request.title,
        description=request.description,
        due_date=request.due_date,
        assigned_to=UUID(request.assigned_to) if request.assigned_to else None,
        priority=request.priority,
        notes=request.notes,
    )

    if not deadline:
        raise HTTPException(404, "Deadline not found")

    return {
        "success": True,
        "deadline": deadline.to_dict(),
    }


@deadline_router.delete("/{deadline_id}")
async def delete_deadline(deadline_id: str):
    """Delete a deadline."""
    success = deadline_service.delete_deadline(UUID(deadline_id))
    if not success:
        raise HTTPException(404, "Deadline not found")

    return {
        "success": True,
        "message": "Deadline deleted",
    }


@deadline_router.post("/{deadline_id}/complete")
async def complete_deadline(
    deadline_id: str,
    user_id: Optional[str] = Query(None, description="User completing the deadline"),
):
    """Mark a deadline as completed."""
    deadline = deadline_service.complete_deadline(
        deadline_id=UUID(deadline_id),
        completed_by=UUID(user_id) if user_id else None,
    )

    if not deadline:
        raise HTTPException(404, "Deadline not found")

    return {
        "success": True,
        "deadline": deadline.to_dict(),
    }


@deadline_router.post("/{deadline_id}/extension")
async def file_extension(
    deadline_id: str,
    request: FileExtensionRequest,
    user_id: Optional[str] = Query(None, description="User filing the extension"),
):
    """File an extension for a deadline."""
    deadline = deadline_service.file_extension(
        deadline_id=UUID(deadline_id),
        extended_date=request.extended_date,
        filed_by=UUID(user_id) if user_id else None,
    )

    if not deadline:
        raise HTTPException(404, "Deadline not found")

    return {
        "success": True,
        "deadline": deadline.to_dict(),
        "message": f"Extension filed. New due date: {request.extended_date}",
    }


# =============================================================================
# DEADLINE QUERIES
# =============================================================================

@deadline_router.get("")
async def list_deadlines(
    firm_id: str = Query(..., description="Firm ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    deadline_type: Optional[str] = Query(None, description="Filter by type"),
    client_id: Optional[str] = Query(None, description="Filter by client"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    from_date: Optional[date] = Query(None, description="From date"),
    to_date: Optional[date] = Query(None, description="To date"),
    include_completed: bool = Query(False, description="Include completed deadlines"),
):
    """
    List deadlines with optional filters.

    Returns deadlines sorted by due date.
    """
    status_filter = DeadlineStatus(status) if status else None
    type_filter = DeadlineType(deadline_type) if deadline_type else None

    deadlines = deadline_service.get_deadlines_for_firm(
        firm_id=UUID(firm_id),
        status=status_filter,
        deadline_type=type_filter,
        client_id=UUID(client_id) if client_id else None,
        assigned_to=UUID(assigned_to) if assigned_to else None,
        from_date=from_date,
        to_date=to_date,
        include_completed=include_completed,
    )

    return {
        "success": True,
        "deadlines": [d.to_dict() for d in deadlines],
        "total": len(deadlines),
    }


@deadline_router.get("/upcoming")
async def get_upcoming_deadlines(
    firm_id: str = Query(..., description="Firm ID"),
    days_ahead: int = Query(30, ge=1, le=365, description="Days to look ahead"),
):
    """Get deadlines due within the next N days."""
    deadlines = deadline_service.get_upcoming_deadlines(
        firm_id=UUID(firm_id),
        days_ahead=days_ahead,
    )

    return {
        "success": True,
        "deadlines": [d.to_dict() for d in deadlines],
        "total": len(deadlines),
        "days_ahead": days_ahead,
    }


@deadline_router.get("/overdue")
async def get_overdue_deadlines(
    firm_id: str = Query(..., description="Firm ID"),
):
    """Get all overdue deadlines."""
    deadlines = deadline_service.get_overdue_deadlines(firm_id=UUID(firm_id))

    return {
        "success": True,
        "deadlines": [d.to_dict() for d in deadlines],
        "total": len(deadlines),
    }


@deadline_router.get("/client/{client_id}")
async def get_client_deadlines(
    client_id: str,
    firm_id: str = Query(..., description="Firm ID"),
    include_completed: bool = Query(False),
):
    """Get all deadlines for a specific client."""
    deadlines = deadline_service.get_deadlines_for_client(
        firm_id=UUID(firm_id),
        client_id=UUID(client_id),
        include_completed=include_completed,
    )

    return {
        "success": True,
        "deadlines": [d.to_dict() for d in deadlines],
        "total": len(deadlines),
    }


@deadline_router.get("/session/{session_id}")
async def get_session_deadlines(session_id: str):
    """Get all deadlines for a specific tax return session."""
    deadlines = deadline_service.get_deadlines_for_session(session_id)

    return {
        "success": True,
        "deadlines": [d.to_dict() for d in deadlines],
        "total": len(deadlines),
    }


# =============================================================================
# STANDARD DEADLINE GENERATION
# =============================================================================

@deadline_router.post("/generate-standard")
async def generate_standard_deadlines(
    request: GenerateStandardDeadlinesRequest,
    firm_id: str = Query(..., description="Firm ID"),
    user_id: Optional[str] = Query(None, description="Creating user ID"),
):
    """
    Generate standard tax deadlines for a tax year.

    Creates filing deadline, extension deadline, and optionally
    quarterly estimated tax payment deadlines.
    """
    deadlines = deadline_service.generate_standard_deadlines(
        firm_id=UUID(firm_id),
        tax_year=request.tax_year,
        client_id=UUID(request.client_id) if request.client_id else None,
        session_id=request.session_id,
        include_estimated=request.include_estimated,
        created_by=UUID(user_id) if user_id else None,
    )

    return {
        "success": True,
        "deadlines": [d.to_dict() for d in deadlines],
        "total": len(deadlines),
        "message": f"Generated {len(deadlines)} standard deadlines for tax year {request.tax_year}",
    }


# =============================================================================
# CALENDAR VIEW
# =============================================================================

@deadline_router.get("/calendar/{year}/{month}")
async def get_calendar_view(
    year: int,
    month: int,
    firm_id: str = Query(..., description="Firm ID"),
):
    """
    Get deadlines formatted for calendar display.

    Returns deadlines grouped by date for the specified month.
    """
    if month < 1 or month > 12:
        raise HTTPException(400, "Invalid month")

    calendar_data = deadline_service.get_calendar_view(
        firm_id=UUID(firm_id),
        year=year,
        month=month,
    )

    return {
        "success": True,
        **calendar_data,
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@deadline_router.get("/summary")
async def get_deadline_summary(
    firm_id: str = Query(..., description="Firm ID"),
):
    """
    Get summary statistics for deadlines.

    Returns counts by status, type, urgency, and completion rate.
    """
    summary = deadline_service.get_deadline_summary(firm_id=UUID(firm_id))

    return {
        "success": True,
        **summary,
    }


# =============================================================================
# REMINDERS
# =============================================================================

@deadline_router.post("/{deadline_id}/reminders")
async def add_reminder(
    deadline_id: str,
    request: AddReminderRequest,
):
    """Add a reminder to a deadline."""
    deadline = deadline_service.get_deadline(UUID(deadline_id))
    if not deadline:
        raise HTTPException(404, "Deadline not found")

    from ..deadlines.deadline_models import ReminderType
    try:
        reminder_type = ReminderType(request.reminder_type)
    except ValueError:
        raise HTTPException(400, f"Invalid reminder type: {request.reminder_type}")

    reminder = deadline.add_reminder(
        days_before=request.days_before,
        reminder_type=reminder_type,
        recipient_type=request.recipient_type,
    )

    return {
        "success": True,
        "reminder": reminder.to_dict(),
    }


@deadline_router.get("/reminders/pending")
async def get_pending_reminders(
    firm_id: str = Query(..., description="Firm ID"),
):
    """Get reminders that should be sent today."""
    reminders = deadline_service.get_pending_reminders(firm_id=UUID(firm_id))

    return {
        "success": True,
        "reminders": reminders,
        "total": len(reminders),
    }


@deadline_router.post("/{deadline_id}/reminders/{reminder_id}/sent")
async def mark_reminder_sent(
    deadline_id: str,
    reminder_id: str,
):
    """Mark a reminder as sent."""
    success = deadline_service.mark_reminder_sent(
        deadline_id=UUID(deadline_id),
        reminder_id=UUID(reminder_id),
    )

    if not success:
        raise HTTPException(404, "Deadline or reminder not found")

    return {
        "success": True,
        "message": "Reminder marked as sent",
    }


# =============================================================================
# ALERTS
# =============================================================================

@deadline_router.post("/alerts/generate")
async def generate_alerts(
    firm_id: str = Query(..., description="Firm ID"),
):
    """Generate alerts for deadlines needing attention."""
    alerts = deadline_service.generate_alerts(firm_id=UUID(firm_id))

    return {
        "success": True,
        "alerts": [a.to_dict() for a in alerts],
        "total": len(alerts),
    }


@deadline_router.get("/alerts")
async def get_alerts(
    firm_id: str = Query(..., description="Firm ID"),
    include_dismissed: bool = Query(False),
):
    """Get deadline alerts."""
    alerts = deadline_service.get_alerts(
        firm_id=UUID(firm_id),
        include_dismissed=include_dismissed,
    )

    return {
        "success": True,
        "alerts": [a.to_dict() for a in alerts],
        "total": len(alerts),
    }


@deadline_router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str):
    """Dismiss an alert."""
    success = deadline_service.dismiss_alert(UUID(alert_id))
    if not success:
        raise HTTPException(404, "Alert not found")

    return {
        "success": True,
        "message": "Alert dismissed",
    }


@deadline_router.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str):
    """Mark an alert as read."""
    success = deadline_service.mark_alert_read(UUID(alert_id))
    if not success:
        raise HTTPException(404, "Alert not found")

    return {
        "success": True,
        "message": "Alert marked as read",
    }


# =============================================================================
# DEADLINE TYPES INFO
# =============================================================================

@deadline_router.get("/types")
async def get_deadline_types():
    """Get list of available deadline types."""
    return {
        "success": True,
        "types": [
            {
                "value": t.value,
                "label": t.value.replace("_", " ").title(),
                "description": _get_type_description(t),
            }
            for t in DeadlineType
        ],
    }


def _get_type_description(t: DeadlineType) -> str:
    """Get description for deadline type."""
    descriptions = {
        DeadlineType.FILING: "Tax return filing deadline (typically April 15)",
        DeadlineType.EXTENSION: "Extended filing deadline (typically October 15)",
        DeadlineType.ESTIMATED_Q1: "Q1 estimated tax payment (typically April 15)",
        DeadlineType.ESTIMATED_Q2: "Q2 estimated tax payment (typically June 15)",
        DeadlineType.ESTIMATED_Q3: "Q3 estimated tax payment (typically September 15)",
        DeadlineType.ESTIMATED_Q4: "Q4 estimated tax payment (typically January 15 next year)",
        DeadlineType.DOCUMENT_REQUEST: "Client document submission deadline",
        DeadlineType.REVIEW: "Internal review deadline",
        DeadlineType.SIGNATURE: "Client signature deadline",
        DeadlineType.PAYMENT: "Payment due deadline",
        DeadlineType.CUSTOM: "Custom deadline",
    }
    return descriptions.get(t, "")
