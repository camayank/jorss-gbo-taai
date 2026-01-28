"""
Appointment Scheduling Routes

API endpoints for appointment booking and management.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import date, datetime, time
from uuid import UUID
import logging

from ..appointments.appointment_service import (
    appointment_service,
    AppointmentType,
    AppointmentStatus,
)
from ..appointments.appointment_models import DayOfWeek

logger = logging.getLogger(__name__)

appointment_router = APIRouter(prefix="/appointments", tags=["Appointments"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AvailabilityWindowRequest(BaseModel):
    """Availability window configuration."""
    day_of_week: str = Field(..., description="monday, tuesday, etc.")
    start_time: str = Field(..., description="HH:MM format, e.g., 09:00")
    end_time: str = Field(..., description="HH:MM format, e.g., 17:00")
    is_active: bool = True


class SetAvailabilityRequest(BaseModel):
    """Request to set CPA availability."""
    availability_windows: Optional[List[AvailabilityWindowRequest]] = None
    blocked_dates: Optional[List[date]] = None
    buffer_time: int = Field(15, ge=0, le=60)
    min_advance_booking_hours: int = Field(24, ge=1, le=168)
    max_advance_booking_days: int = Field(60, ge=1, le=365)
    appointment_types: Optional[List[str]] = None
    custom_durations: Optional[Dict[str, int]] = None
    video_meeting_link: Optional[str] = None
    office_address: Optional[str] = None
    phone_number: Optional[str] = None
    timezone: str = "America/New_York"


class BookAppointmentRequest(BaseModel):
    """Request to book an appointment."""
    cpa_id: str = Field(..., description="CPA user ID")
    cpa_name: str = Field(..., description="CPA name")
    client_name: str = Field(..., min_length=1)
    client_email: EmailStr
    start_time: datetime = Field(..., description="Appointment start time")
    appointment_type: str = Field("general", description="Appointment type")
    client_id: Optional[str] = None
    client_phone: Optional[str] = None
    session_id: Optional[str] = None
    description: Optional[str] = None


class RescheduleRequest(BaseModel):
    """Request to reschedule an appointment."""
    new_start_time: datetime = Field(..., description="New start time")


class CancelRequest(BaseModel):
    """Request to cancel an appointment."""
    reason: Optional[str] = None


class CompleteRequest(BaseModel):
    """Request to complete an appointment."""
    notes: Optional[str] = None


class UpdateAppointmentRequest(BaseModel):
    """Request to update appointment details."""
    description: Optional[str] = None
    client_phone: Optional[str] = None


# =============================================================================
# AVAILABILITY MANAGEMENT
# =============================================================================

@appointment_router.post("/availability")
async def set_availability(
    request: SetAvailabilityRequest,
    cpa_id: str = Query(..., description="CPA user ID"),
    firm_id: str = Query(..., description="Firm ID"),
):
    """
    Set or update CPA availability configuration.

    Configure when the CPA is available for appointments.
    """
    # Parse appointment types
    appointment_types = None
    if request.appointment_types:
        try:
            appointment_types = [AppointmentType(t) for t in request.appointment_types]
        except ValueError as e:
            raise HTTPException(400, f"Invalid appointment type: {e}")

    # Parse availability windows
    windows = None
    if request.availability_windows:
        windows = []
        for w in request.availability_windows:
            windows.append({
                "day_of_week": w.day_of_week,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "is_active": w.is_active,
            })

    availability = appointment_service.set_cpa_availability(
        cpa_id=UUID(cpa_id),
        firm_id=UUID(firm_id),
        availability_windows=windows,
        blocked_dates=request.blocked_dates,
        buffer_time=request.buffer_time,
        min_advance_booking_hours=request.min_advance_booking_hours,
        max_advance_booking_days=request.max_advance_booking_days,
        appointment_types=appointment_types,
        custom_durations=request.custom_durations,
        video_meeting_link=request.video_meeting_link,
        office_address=request.office_address,
        phone_number=request.phone_number,
        timezone=request.timezone,
    )

    return {
        "success": True,
        "availability": availability.to_dict(),
    }


@appointment_router.get("/availability/{cpa_id}")
async def get_availability(cpa_id: str):
    """Get CPA availability configuration."""
    availability = appointment_service.get_cpa_availability(UUID(cpa_id))
    if not availability:
        raise HTTPException(404, "Availability not configured for this CPA")

    return {
        "success": True,
        "availability": availability.to_dict(),
    }


@appointment_router.post("/availability/{cpa_id}/block-date")
async def add_blocked_date(
    cpa_id: str,
    blocked_date: date = Query(..., description="Date to block"),
):
    """Add a blocked date (vacation, holiday, etc.)."""
    success = appointment_service.add_blocked_date(UUID(cpa_id), blocked_date)
    if not success:
        raise HTTPException(404, "CPA availability not found")

    return {
        "success": True,
        "message": f"Blocked date {blocked_date} added",
    }


@appointment_router.delete("/availability/{cpa_id}/block-date")
async def remove_blocked_date(
    cpa_id: str,
    blocked_date: date = Query(..., description="Date to unblock"),
):
    """Remove a blocked date."""
    success = appointment_service.remove_blocked_date(UUID(cpa_id), blocked_date)
    if not success:
        raise HTTPException(404, "CPA availability not found")

    return {
        "success": True,
        "message": f"Blocked date {blocked_date} removed",
    }


# =============================================================================
# AVAILABLE SLOTS
# =============================================================================

@appointment_router.get("/slots")
async def get_available_slots(
    cpa_id: str = Query(..., description="CPA user ID"),
    start_date: date = Query(..., description="Start of date range"),
    end_date: date = Query(..., description="End of date range"),
    appointment_type: str = Query("general", description="Appointment type"),
):
    """
    Get available time slots for booking.

    Returns slots based on CPA availability and existing appointments.
    """
    try:
        appt_type = AppointmentType(appointment_type)
    except ValueError:
        raise HTTPException(400, f"Invalid appointment type: {appointment_type}")

    slots = appointment_service.get_available_slots(
        cpa_id=UUID(cpa_id),
        start_date=start_date,
        end_date=end_date,
        appointment_type=appt_type,
    )

    return {
        "success": True,
        "slots": [s.to_dict() for s in slots],
        "total": len(slots),
    }


# =============================================================================
# APPOINTMENT CRUD
# =============================================================================

@appointment_router.post("")
async def book_appointment(
    request: BookAppointmentRequest,
    firm_id: str = Query(..., description="Firm ID"),
    created_by: str = Query("client", description="Who is booking: 'cpa' or 'client'"),
):
    """
    Book a new appointment.

    Creates an appointment with confirmation code.
    """
    try:
        appt_type = AppointmentType(request.appointment_type)
    except ValueError:
        raise HTTPException(400, f"Invalid appointment type: {request.appointment_type}")

    appointment = appointment_service.book_appointment(
        firm_id=UUID(firm_id),
        cpa_id=UUID(request.cpa_id),
        cpa_name=request.cpa_name,
        client_name=request.client_name,
        client_email=request.client_email,
        start_time=request.start_time,
        appointment_type=appt_type,
        client_id=UUID(request.client_id) if request.client_id else None,
        client_phone=request.client_phone,
        session_id=request.session_id,
        description=request.description,
        created_by=created_by,
    )

    return {
        "success": True,
        "appointment": appointment.to_dict(),
        "confirmation_code": appointment.confirmation_code,
    }


@appointment_router.get("/{appointment_id}")
async def get_appointment(appointment_id: str):
    """Get an appointment by ID."""
    try:
        appointment = appointment_service.get_appointment(UUID(appointment_id))
    except ValueError:
        # Try by confirmation code
        appointment = appointment_service.get_appointment_by_code(appointment_id)

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    return {
        "success": True,
        "appointment": appointment.to_dict(),
    }


@appointment_router.put("/{appointment_id}")
async def update_appointment(appointment_id: str, request: UpdateAppointmentRequest):
    """Update appointment details."""
    appointment = appointment_service.update_appointment(
        appointment_id=UUID(appointment_id),
        description=request.description,
        client_phone=request.client_phone,
    )

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    return {
        "success": True,
        "appointment": appointment.to_dict(),
    }


@appointment_router.post("/{appointment_id}/confirm")
async def confirm_appointment(appointment_id: str):
    """Confirm an appointment."""
    appointment = appointment_service.confirm_appointment(UUID(appointment_id))
    if not appointment:
        raise HTTPException(404, "Appointment not found")

    return {
        "success": True,
        "appointment": appointment.to_dict(),
    }


@appointment_router.post("/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: str,
    request: CancelRequest,
    cancelled_by: str = Query("client", description="Who is cancelling"),
):
    """Cancel an appointment."""
    appointment = appointment_service.cancel_appointment(
        appointment_id=UUID(appointment_id),
        cancelled_by=cancelled_by,
        reason=request.reason or "",
    )

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    return {
        "success": True,
        "appointment": appointment.to_dict(),
    }


@appointment_router.post("/{appointment_id}/reschedule")
async def reschedule_appointment(
    appointment_id: str,
    request: RescheduleRequest,
    rescheduled_by: str = Query("client", description="Who is rescheduling"),
):
    """Reschedule an appointment."""
    appointment = appointment_service.reschedule_appointment(
        appointment_id=UUID(appointment_id),
        new_start_time=request.new_start_time,
        rescheduled_by=rescheduled_by,
    )

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    return {
        "success": True,
        "appointment": appointment.to_dict(),
    }


@appointment_router.post("/{appointment_id}/complete")
async def complete_appointment(appointment_id: str, request: CompleteRequest):
    """Mark appointment as completed."""
    appointment = appointment_service.complete_appointment(
        appointment_id=UUID(appointment_id),
        notes=request.notes or "",
    )

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    return {
        "success": True,
        "appointment": appointment.to_dict(),
    }


@appointment_router.post("/{appointment_id}/no-show")
async def mark_no_show(appointment_id: str):
    """Mark appointment as no-show."""
    appointment = appointment_service.mark_no_show(UUID(appointment_id))
    if not appointment:
        raise HTTPException(404, "Appointment not found")

    return {
        "success": True,
        "appointment": appointment.to_dict(),
    }


# =============================================================================
# APPOINTMENT QUERIES
# =============================================================================

@appointment_router.get("")
async def list_appointments(
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    cpa_id: Optional[str] = Query(None, description="Filter by CPA"),
    client_id: Optional[str] = Query(None, description="Filter by client"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    include_cancelled: bool = Query(False),
):
    """List appointments with optional filters."""
    status_filter = AppointmentStatus(status) if status else None

    if cpa_id:
        appointments = appointment_service.get_appointments_for_cpa(
            cpa_id=UUID(cpa_id),
            start_date=start_date,
            end_date=end_date,
            status=status_filter,
            include_cancelled=include_cancelled,
        )
    elif client_id:
        appointments = appointment_service.get_appointments_for_client(
            client_id=UUID(client_id),
            include_cancelled=include_cancelled,
        )
    elif firm_id:
        appointments = appointment_service.get_appointments_for_firm(
            firm_id=UUID(firm_id),
            start_date=start_date,
            end_date=end_date,
            include_cancelled=include_cancelled,
        )
    else:
        raise HTTPException(400, "Must provide firm_id, cpa_id, or client_id")

    return {
        "success": True,
        "appointments": [a.to_dict() for a in appointments],
        "total": len(appointments),
    }


@appointment_router.get("/upcoming")
async def get_upcoming_appointments(
    cpa_id: Optional[str] = Query(None),
    firm_id: Optional[str] = Query(None),
    hours_ahead: int = Query(24, ge=1, le=168),
):
    """Get upcoming appointments within the next N hours."""
    appointments = appointment_service.get_upcoming_appointments(
        cpa_id=UUID(cpa_id) if cpa_id else None,
        firm_id=UUID(firm_id) if firm_id else None,
        hours_ahead=hours_ahead,
    )

    return {
        "success": True,
        "appointments": [a.to_dict() for a in appointments],
        "total": len(appointments),
    }


@appointment_router.get("/today")
async def get_todays_appointments(
    cpa_id: Optional[str] = Query(None),
    firm_id: Optional[str] = Query(None),
):
    """Get today's appointments."""
    appointments = appointment_service.get_todays_appointments(
        cpa_id=UUID(cpa_id) if cpa_id else None,
        firm_id=UUID(firm_id) if firm_id else None,
    )

    return {
        "success": True,
        "appointments": [a.to_dict() for a in appointments],
        "total": len(appointments),
    }


@appointment_router.get("/client/{client_id}")
async def get_client_appointments(
    client_id: str,
    include_cancelled: bool = Query(False),
):
    """Get all appointments for a client."""
    appointments = appointment_service.get_appointments_for_client(
        client_id=UUID(client_id),
        include_cancelled=include_cancelled,
    )

    return {
        "success": True,
        "appointments": [a.to_dict_client() for a in appointments],
        "total": len(appointments),
    }


# =============================================================================
# REMINDERS
# =============================================================================

@appointment_router.get("/reminders/pending")
async def get_pending_reminders():
    """Get appointments needing reminder notifications."""
    reminders = appointment_service.get_appointments_needing_reminders()

    return {
        "success": True,
        "reminders_24h": [a.to_dict() for a in reminders["24h"]],
        "reminders_1h": [a.to_dict() for a in reminders["1h"]],
    }


@appointment_router.post("/{appointment_id}/reminders/{reminder_type}/sent")
async def mark_reminder_sent(appointment_id: str, reminder_type: str):
    """Mark a reminder as sent."""
    if reminder_type not in ["24h", "1h"]:
        raise HTTPException(400, "Invalid reminder type. Use '24h' or '1h'")

    success = appointment_service.mark_reminder_sent(UUID(appointment_id), reminder_type)
    if not success:
        raise HTTPException(404, "Appointment not found")

    return {
        "success": True,
        "message": f"{reminder_type} reminder marked as sent",
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@appointment_router.get("/summary")
async def get_appointment_summary(
    firm_id: Optional[str] = Query(None),
    cpa_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    """Get summary statistics for appointments."""
    summary = appointment_service.get_appointment_summary(
        firm_id=UUID(firm_id) if firm_id else None,
        cpa_id=UUID(cpa_id) if cpa_id else None,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "success": True,
        **summary,
    }


# =============================================================================
# REFERENCE DATA
# =============================================================================

@appointment_router.get("/types")
async def get_appointment_types():
    """Get list of appointment types."""
    return {
        "success": True,
        "types": [
            {"value": t.value, "label": t.value.replace("_", " ").title()}
            for t in AppointmentType
        ],
    }


@appointment_router.get("/statuses")
async def get_statuses():
    """Get list of appointment statuses."""
    return {
        "success": True,
        "statuses": [
            {"value": s.value, "label": s.value.replace("_", " ").title()}
            for s in AppointmentStatus
        ],
    }
