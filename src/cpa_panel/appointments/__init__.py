"""
Appointment Scheduling Module

Provides appointment booking and management:
- CPA availability management
- Client self-service booking
- Appointment types (call, video, in-person)
- Calendar integration support
- Reminders and notifications
"""

from .appointment_service import (
    AppointmentService,
    AppointmentType,
    AppointmentStatus,
)
from .appointment_models import Appointment, TimeSlot, CPAAvailability

__all__ = [
    "AppointmentService",
    "AppointmentType",
    "AppointmentStatus",
    "Appointment",
    "TimeSlot",
    "CPAAvailability",
]
