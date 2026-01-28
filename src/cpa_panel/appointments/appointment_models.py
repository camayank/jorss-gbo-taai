"""
Appointment Models

Data models for appointment scheduling system.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID, uuid4


class AppointmentType(str, Enum):
    """Types of appointments."""
    PHONE_CALL = "phone_call"
    VIDEO_CALL = "video_call"
    IN_PERSON = "in_person"
    TAX_CONSULTATION = "tax_consultation"
    DOCUMENT_REVIEW = "document_review"
    TAX_PLANNING = "tax_planning"
    RETURN_REVIEW = "return_review"
    GENERAL = "general"


class AppointmentStatus(str, Enum):
    """Status of an appointment."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class DayOfWeek(str, Enum):
    """Days of the week."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# Default appointment durations in minutes
APPOINTMENT_DURATIONS = {
    AppointmentType.PHONE_CALL: 30,
    AppointmentType.VIDEO_CALL: 45,
    AppointmentType.IN_PERSON: 60,
    AppointmentType.TAX_CONSULTATION: 60,
    AppointmentType.DOCUMENT_REVIEW: 30,
    AppointmentType.TAX_PLANNING: 90,
    AppointmentType.RETURN_REVIEW: 45,
    AppointmentType.GENERAL: 30,
}


@dataclass
class TimeSlot:
    """Available time slot for booking."""
    start_time: datetime
    end_time: datetime
    is_available: bool = True
    cpa_id: Optional[UUID] = None
    cpa_name: Optional[str] = None

    @property
    def duration_minutes(self) -> int:
        """Get duration in minutes."""
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": self.duration_minutes,
            "is_available": self.is_available,
            "cpa_id": str(self.cpa_id) if self.cpa_id else None,
            "cpa_name": self.cpa_name,
        }


@dataclass
class AvailabilityWindow:
    """Time window when CPA is available."""
    day_of_week: DayOfWeek
    start_time: time  # e.g., 09:00
    end_time: time    # e.g., 17:00
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day_of_week": self.day_of_week.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "is_active": self.is_active,
        }


@dataclass
class CPAAvailability:
    """CPA's availability configuration."""
    id: UUID = field(default_factory=uuid4)
    cpa_id: UUID = None
    firm_id: UUID = None

    # Regular availability windows
    availability_windows: List[AvailabilityWindow] = field(default_factory=list)

    # Blocked dates (holidays, vacations, etc.)
    blocked_dates: List[date] = field(default_factory=list)

    # Buffer time between appointments (in minutes)
    buffer_time: int = 15

    # Minimum advance booking (in hours)
    min_advance_booking_hours: int = 24

    # Maximum advance booking (in days)
    max_advance_booking_days: int = 60

    # Appointment types offered
    appointment_types: List[AppointmentType] = field(default_factory=list)

    # Custom durations (overrides defaults)
    custom_durations: Dict[str, int] = field(default_factory=dict)

    # Meeting links
    video_meeting_link: Optional[str] = None
    office_address: Optional[str] = None
    phone_number: Optional[str] = None

    # Timezone
    timezone: str = "America/New_York"

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Set default availability if not provided."""
        if not self.availability_windows:
            # Default: Mon-Fri 9 AM to 5 PM
            for day in [DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY,
                        DayOfWeek.THURSDAY, DayOfWeek.FRIDAY]:
                self.availability_windows.append(AvailabilityWindow(
                    day_of_week=day,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                ))

        if not self.appointment_types:
            # Default appointment types
            self.appointment_types = [
                AppointmentType.PHONE_CALL,
                AppointmentType.VIDEO_CALL,
                AppointmentType.TAX_CONSULTATION,
            ]

    def get_duration(self, appointment_type: AppointmentType) -> int:
        """Get duration for appointment type."""
        if appointment_type.value in self.custom_durations:
            return self.custom_durations[appointment_type.value]
        return APPOINTMENT_DURATIONS.get(appointment_type, 30)

    def is_date_blocked(self, check_date: date) -> bool:
        """Check if a date is blocked."""
        return check_date in self.blocked_dates

    def get_availability_for_day(self, day: DayOfWeek) -> Optional[AvailabilityWindow]:
        """Get availability window for a specific day."""
        for window in self.availability_windows:
            if window.day_of_week == day and window.is_active:
                return window
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "cpa_id": str(self.cpa_id) if self.cpa_id else None,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "availability_windows": [w.to_dict() for w in self.availability_windows],
            "blocked_dates": [d.isoformat() for d in self.blocked_dates],
            "buffer_time": self.buffer_time,
            "min_advance_booking_hours": self.min_advance_booking_hours,
            "max_advance_booking_days": self.max_advance_booking_days,
            "appointment_types": [t.value for t in self.appointment_types],
            "custom_durations": self.custom_durations,
            "video_meeting_link": self.video_meeting_link,
            "office_address": self.office_address,
            "phone_number": self.phone_number,
            "timezone": self.timezone,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Appointment:
    """
    Represents a scheduled appointment.

    Tracks appointments between CPAs and clients with
    full lifecycle management.
    """
    id: UUID = field(default_factory=uuid4)
    firm_id: UUID = None

    # Participants
    cpa_id: UUID = None
    cpa_name: str = ""
    client_id: Optional[UUID] = None
    client_name: str = ""
    client_email: str = ""
    client_phone: Optional[str] = None

    # Session context (if related to a tax return)
    session_id: Optional[str] = None

    # Appointment details
    appointment_type: AppointmentType = AppointmentType.GENERAL
    title: str = ""
    description: Optional[str] = None
    start_time: datetime = None
    end_time: datetime = None
    duration_minutes: int = 30

    # Location/meeting details
    location: Optional[str] = None  # Address for in-person
    meeting_link: Optional[str] = None  # Video call link
    phone_number: Optional[str] = None  # For phone calls

    # Status
    status: AppointmentStatus = AppointmentStatus.PENDING

    # Confirmation
    confirmed_at: Optional[datetime] = None
    confirmation_code: str = ""

    # Reminders
    reminder_sent_24h: bool = False
    reminder_sent_1h: bool = False

    # Rescheduling
    original_start_time: Optional[datetime] = None
    reschedule_count: int = 0
    rescheduled_by: Optional[str] = None  # "cpa" or "client"

    # Cancellation
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None

    # Completion
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None  # CPA notes after meeting

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None  # "cpa" or "client"

    def __post_init__(self):
        """Generate confirmation code if not provided."""
        if not self.confirmation_code:
            import random
            import string
            self.confirmation_code = ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )

        if not self.title:
            self.title = f"{self.appointment_type.value.replace('_', ' ').title()} with {self.cpa_name}"

        if self.start_time and not self.end_time:
            self.end_time = self.start_time + timedelta(minutes=self.duration_minutes)

    @property
    def is_upcoming(self) -> bool:
        """Check if appointment is in the future."""
        return self.start_time > datetime.utcnow() if self.start_time else False

    @property
    def is_past(self) -> bool:
        """Check if appointment is in the past."""
        return self.end_time < datetime.utcnow() if self.end_time else False

    @property
    def hours_until(self) -> Optional[float]:
        """Get hours until appointment."""
        if not self.start_time:
            return None
        delta = self.start_time - datetime.utcnow()
        return delta.total_seconds() / 3600

    @property
    def needs_24h_reminder(self) -> bool:
        """Check if 24-hour reminder should be sent."""
        if self.reminder_sent_24h:
            return False
        hours = self.hours_until
        return hours is not None and 23 <= hours <= 25

    @property
    def needs_1h_reminder(self) -> bool:
        """Check if 1-hour reminder should be sent."""
        if self.reminder_sent_1h:
            return False
        hours = self.hours_until
        return hours is not None and 0.5 <= hours <= 1.5

    def confirm(self):
        """Confirm the appointment."""
        self.status = AppointmentStatus.CONFIRMED
        self.confirmed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def cancel(self, cancelled_by: str = "client", reason: str = ""):
        """Cancel the appointment."""
        self.status = AppointmentStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.cancelled_by = cancelled_by
        self.cancellation_reason = reason
        self.updated_at = datetime.utcnow()

    def reschedule(self, new_start_time: datetime, new_end_time: datetime, rescheduled_by: str = "client"):
        """Reschedule the appointment."""
        if self.original_start_time is None:
            self.original_start_time = self.start_time

        self.start_time = new_start_time
        self.end_time = new_end_time
        self.status = AppointmentStatus.RESCHEDULED
        self.reschedule_count += 1
        self.rescheduled_by = rescheduled_by
        self.updated_at = datetime.utcnow()

    def complete(self, notes: str = ""):
        """Mark appointment as completed."""
        self.status = AppointmentStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.notes = notes
        self.updated_at = datetime.utcnow()

    def mark_no_show(self):
        """Mark as no-show."""
        self.status = AppointmentStatus.NO_SHOW
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "cpa_id": str(self.cpa_id) if self.cpa_id else None,
            "cpa_name": self.cpa_name,
            "client_id": str(self.client_id) if self.client_id else None,
            "client_name": self.client_name,
            "client_email": self.client_email,
            "client_phone": self.client_phone,
            "session_id": self.session_id,
            "appointment_type": self.appointment_type.value,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_minutes": self.duration_minutes,
            "location": self.location,
            "meeting_link": self.meeting_link,
            "phone_number": self.phone_number,
            "status": self.status.value,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "confirmation_code": self.confirmation_code,
            "is_upcoming": self.is_upcoming,
            "is_past": self.is_past,
            "hours_until": self.hours_until,
            "reschedule_count": self.reschedule_count,
            "rescheduled_by": self.rescheduled_by,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "cancelled_by": self.cancelled_by,
            "cancellation_reason": self.cancellation_reason,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
        }

    def to_dict_client(self) -> Dict[str, Any]:
        """Convert to dictionary for client-facing response (no internal notes)."""
        result = self.to_dict()
        del result["notes"]  # Don't expose CPA notes to client
        return result
