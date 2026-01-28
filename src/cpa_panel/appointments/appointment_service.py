"""
Appointment Service

Business logic for appointment scheduling.
"""

import logging
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from collections import defaultdict

from .appointment_models import (
    Appointment,
    AppointmentType,
    AppointmentStatus,
    CPAAvailability,
    TimeSlot,
    AvailabilityWindow,
    DayOfWeek,
    APPOINTMENT_DURATIONS,
)

logger = logging.getLogger(__name__)


class AppointmentService:
    """
    Service for managing appointments.

    Provides:
    - Appointment booking and management
    - CPA availability configuration
    - Available time slot generation
    - Reminders and notifications
    - Calendar integration hooks
    """

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._appointments: Dict[UUID, Appointment] = {}
        self._availability: Dict[UUID, CPAAvailability] = {}  # Keyed by CPA ID

    # =========================================================================
    # AVAILABILITY MANAGEMENT
    # =========================================================================

    def set_cpa_availability(
        self,
        cpa_id: UUID,
        firm_id: UUID,
        availability_windows: Optional[List[Dict]] = None,
        blocked_dates: Optional[List[date]] = None,
        buffer_time: int = 15,
        min_advance_booking_hours: int = 24,
        max_advance_booking_days: int = 60,
        appointment_types: Optional[List[AppointmentType]] = None,
        custom_durations: Optional[Dict[str, int]] = None,
        video_meeting_link: Optional[str] = None,
        office_address: Optional[str] = None,
        phone_number: Optional[str] = None,
        timezone: str = "America/New_York",
    ) -> CPAAvailability:
        """
        Set or update CPA availability configuration.
        """
        # Parse availability windows
        windows = []
        if availability_windows:
            for w in availability_windows:
                windows.append(AvailabilityWindow(
                    day_of_week=DayOfWeek(w["day_of_week"]),
                    start_time=time.fromisoformat(w["start_time"]) if isinstance(w["start_time"], str) else w["start_time"],
                    end_time=time.fromisoformat(w["end_time"]) if isinstance(w["end_time"], str) else w["end_time"],
                    is_active=w.get("is_active", True),
                ))

        availability = CPAAvailability(
            cpa_id=cpa_id,
            firm_id=firm_id,
            availability_windows=windows if windows else None,
            blocked_dates=blocked_dates or [],
            buffer_time=buffer_time,
            min_advance_booking_hours=min_advance_booking_hours,
            max_advance_booking_days=max_advance_booking_days,
            appointment_types=appointment_types,
            custom_durations=custom_durations or {},
            video_meeting_link=video_meeting_link,
            office_address=office_address,
            phone_number=phone_number,
            timezone=timezone,
        )

        self._availability[cpa_id] = availability
        logger.info(f"Set availability for CPA: {cpa_id}")

        return availability

    def get_cpa_availability(self, cpa_id: UUID) -> Optional[CPAAvailability]:
        """Get CPA availability configuration."""
        return self._availability.get(cpa_id)

    def add_blocked_date(self, cpa_id: UUID, blocked_date: date) -> bool:
        """Add a blocked date for CPA."""
        availability = self._availability.get(cpa_id)
        if not availability:
            return False

        if blocked_date not in availability.blocked_dates:
            availability.blocked_dates.append(blocked_date)
            availability.updated_at = datetime.utcnow()

        return True

    def remove_blocked_date(self, cpa_id: UUID, blocked_date: date) -> bool:
        """Remove a blocked date for CPA."""
        availability = self._availability.get(cpa_id)
        if not availability:
            return False

        if blocked_date in availability.blocked_dates:
            availability.blocked_dates.remove(blocked_date)
            availability.updated_at = datetime.utcnow()

        return True

    # =========================================================================
    # AVAILABLE SLOTS
    # =========================================================================

    def get_available_slots(
        self,
        cpa_id: UUID,
        start_date: date,
        end_date: date,
        appointment_type: AppointmentType = AppointmentType.GENERAL,
    ) -> List[TimeSlot]:
        """
        Get available time slots for booking.

        Args:
            cpa_id: CPA to check availability for
            start_date: Start of date range
            end_date: End of date range
            appointment_type: Type of appointment (for duration)

        Returns:
            List of available TimeSlot objects
        """
        availability = self._availability.get(cpa_id)
        if not availability:
            # Create default availability
            availability = CPAAvailability(cpa_id=cpa_id)
            self._availability[cpa_id] = availability

        slots = []
        duration = availability.get_duration(appointment_type)
        buffer = availability.buffer_time

        # Get existing appointments for the date range
        existing = self._get_appointments_for_cpa(
            cpa_id,
            datetime.combine(start_date, time(0, 0)),
            datetime.combine(end_date, time(23, 59)),
        )

        # Minimum booking time
        min_booking_time = datetime.utcnow() + timedelta(hours=availability.min_advance_booking_hours)

        current_date = start_date
        while current_date <= end_date:
            # Skip blocked dates
            if availability.is_date_blocked(current_date):
                current_date += timedelta(days=1)
                continue

            # Get day of week
            day_name = current_date.strftime("%A").lower()
            try:
                day_of_week = DayOfWeek(day_name)
            except ValueError:
                current_date += timedelta(days=1)
                continue

            # Get availability window for this day
            window = availability.get_availability_for_day(day_of_week)
            if not window:
                current_date += timedelta(days=1)
                continue

            # Generate slots for this day
            slot_start = datetime.combine(current_date, window.start_time)
            day_end = datetime.combine(current_date, window.end_time)

            while slot_start + timedelta(minutes=duration) <= day_end:
                slot_end = slot_start + timedelta(minutes=duration)

                # Check if slot is in the future (with min advance booking)
                if slot_start >= min_booking_time:
                    # Check for conflicts with existing appointments
                    is_available = True
                    for appt in existing:
                        # Check for overlap (considering buffer)
                        appt_start_with_buffer = appt.start_time - timedelta(minutes=buffer)
                        appt_end_with_buffer = appt.end_time + timedelta(minutes=buffer)

                        if not (slot_end <= appt_start_with_buffer or slot_start >= appt_end_with_buffer):
                            is_available = False
                            break

                    if is_available:
                        slots.append(TimeSlot(
                            start_time=slot_start,
                            end_time=slot_end,
                            is_available=True,
                            cpa_id=cpa_id,
                        ))

                # Move to next slot (duration + buffer for spacing)
                slot_start += timedelta(minutes=duration + buffer)

            current_date += timedelta(days=1)

        return slots

    def _get_appointments_for_cpa(
        self,
        cpa_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Appointment]:
        """Get appointments for a CPA within a time range."""
        return [
            a for a in self._appointments.values()
            if a.cpa_id == cpa_id
            and a.status not in [AppointmentStatus.CANCELLED]
            and a.start_time
            and start_time <= a.start_time <= end_time
        ]

    # =========================================================================
    # APPOINTMENT CRUD
    # =========================================================================

    def book_appointment(
        self,
        firm_id: UUID,
        cpa_id: UUID,
        cpa_name: str,
        client_name: str,
        client_email: str,
        start_time: datetime,
        appointment_type: AppointmentType = AppointmentType.GENERAL,
        client_id: Optional[UUID] = None,
        client_phone: Optional[str] = None,
        session_id: Optional[str] = None,
        description: Optional[str] = None,
        created_by: str = "client",
    ) -> Appointment:
        """
        Book a new appointment.

        Args:
            firm_id: Firm ID
            cpa_id: CPA to book with
            cpa_name: CPA's name
            client_name: Client's name
            client_email: Client's email
            start_time: Appointment start time
            appointment_type: Type of appointment
            client_id: Client's user ID
            client_phone: Client's phone number
            session_id: Related tax return session
            description: Appointment description
            created_by: Who created ("cpa" or "client")

        Returns:
            Created Appointment object
        """
        # Get availability for duration and meeting details
        availability = self._availability.get(cpa_id)
        if availability:
            duration = availability.get_duration(appointment_type)
            meeting_link = availability.video_meeting_link
            location = availability.office_address
            phone = availability.phone_number
        else:
            duration = APPOINTMENT_DURATIONS.get(appointment_type, 30)
            meeting_link = None
            location = None
            phone = None

        end_time = start_time + timedelta(minutes=duration)

        appointment = Appointment(
            firm_id=firm_id,
            cpa_id=cpa_id,
            cpa_name=cpa_name,
            client_id=client_id,
            client_name=client_name,
            client_email=client_email,
            client_phone=client_phone,
            session_id=session_id,
            appointment_type=appointment_type,
            description=description,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            meeting_link=meeting_link if appointment_type == AppointmentType.VIDEO_CALL else None,
            location=location if appointment_type == AppointmentType.IN_PERSON else None,
            phone_number=phone if appointment_type == AppointmentType.PHONE_CALL else None,
            created_by=created_by,
        )

        self._appointments[appointment.id] = appointment
        logger.info(f"Booked appointment: {appointment.id} - {appointment.title}")

        return appointment

    def get_appointment(self, appointment_id: UUID) -> Optional[Appointment]:
        """Get an appointment by ID."""
        return self._appointments.get(appointment_id)

    def get_appointment_by_code(self, confirmation_code: str) -> Optional[Appointment]:
        """Get an appointment by confirmation code."""
        for appointment in self._appointments.values():
            if appointment.confirmation_code == confirmation_code:
                return appointment
        return None

    def update_appointment(
        self,
        appointment_id: UUID,
        description: Optional[str] = None,
        client_phone: Optional[str] = None,
    ) -> Optional[Appointment]:
        """Update appointment details."""
        appointment = self._appointments.get(appointment_id)
        if not appointment:
            return None

        if description is not None:
            appointment.description = description
        if client_phone is not None:
            appointment.client_phone = client_phone

        appointment.updated_at = datetime.utcnow()
        return appointment

    def cancel_appointment(
        self,
        appointment_id: UUID,
        cancelled_by: str = "client",
        reason: str = "",
    ) -> Optional[Appointment]:
        """Cancel an appointment."""
        appointment = self._appointments.get(appointment_id)
        if not appointment:
            return None

        appointment.cancel(cancelled_by, reason)
        logger.info(f"Cancelled appointment: {appointment_id} by {cancelled_by}")

        return appointment

    def confirm_appointment(self, appointment_id: UUID) -> Optional[Appointment]:
        """Confirm an appointment."""
        appointment = self._appointments.get(appointment_id)
        if not appointment:
            return None

        appointment.confirm()
        logger.info(f"Confirmed appointment: {appointment_id}")

        return appointment

    def reschedule_appointment(
        self,
        appointment_id: UUID,
        new_start_time: datetime,
        rescheduled_by: str = "client",
    ) -> Optional[Appointment]:
        """Reschedule an appointment."""
        appointment = self._appointments.get(appointment_id)
        if not appointment:
            return None

        # Get availability for duration
        availability = self._availability.get(appointment.cpa_id)
        if availability:
            duration = availability.get_duration(appointment.appointment_type)
        else:
            duration = appointment.duration_minutes

        new_end_time = new_start_time + timedelta(minutes=duration)

        appointment.reschedule(new_start_time, new_end_time, rescheduled_by)
        logger.info(f"Rescheduled appointment: {appointment_id} to {new_start_time}")

        return appointment

    def complete_appointment(
        self,
        appointment_id: UUID,
        notes: str = "",
    ) -> Optional[Appointment]:
        """Mark appointment as completed."""
        appointment = self._appointments.get(appointment_id)
        if not appointment:
            return None

        appointment.complete(notes)
        logger.info(f"Completed appointment: {appointment_id}")

        return appointment

    def mark_no_show(self, appointment_id: UUID) -> Optional[Appointment]:
        """Mark appointment as no-show."""
        appointment = self._appointments.get(appointment_id)
        if not appointment:
            return None

        appointment.mark_no_show()
        logger.info(f"Marked appointment as no-show: {appointment_id}")

        return appointment

    # =========================================================================
    # APPOINTMENT QUERIES
    # =========================================================================

    def get_appointments_for_cpa(
        self,
        cpa_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[AppointmentStatus] = None,
        include_cancelled: bool = False,
    ) -> List[Appointment]:
        """Get appointments for a CPA."""
        appointments = []

        for appointment in self._appointments.values():
            if appointment.cpa_id != cpa_id:
                continue
            if not include_cancelled and appointment.status == AppointmentStatus.CANCELLED:
                continue
            if status and appointment.status != status:
                continue
            if start_date and appointment.start_time:
                if appointment.start_time.date() < start_date:
                    continue
            if end_date and appointment.start_time:
                if appointment.start_time.date() > end_date:
                    continue

            appointments.append(appointment)

        # Sort by start time
        appointments.sort(key=lambda a: a.start_time or datetime.max)

        return appointments

    def get_appointments_for_client(
        self,
        client_id: UUID,
        include_cancelled: bool = False,
    ) -> List[Appointment]:
        """Get appointments for a client."""
        appointments = []

        for appointment in self._appointments.values():
            if appointment.client_id != client_id:
                continue
            if not include_cancelled and appointment.status == AppointmentStatus.CANCELLED:
                continue

            appointments.append(appointment)

        # Sort by start time (upcoming first)
        appointments.sort(key=lambda a: a.start_time or datetime.max)

        return appointments

    def get_appointments_for_firm(
        self,
        firm_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_cancelled: bool = False,
    ) -> List[Appointment]:
        """Get all appointments for a firm."""
        appointments = []

        for appointment in self._appointments.values():
            if appointment.firm_id != firm_id:
                continue
            if not include_cancelled and appointment.status == AppointmentStatus.CANCELLED:
                continue
            if start_date and appointment.start_time:
                if appointment.start_time.date() < start_date:
                    continue
            if end_date and appointment.start_time:
                if appointment.start_time.date() > end_date:
                    continue

            appointments.append(appointment)

        # Sort by start time
        appointments.sort(key=lambda a: a.start_time or datetime.max)

        return appointments

    def get_upcoming_appointments(
        self,
        cpa_id: Optional[UUID] = None,
        firm_id: Optional[UUID] = None,
        hours_ahead: int = 24,
    ) -> List[Appointment]:
        """Get upcoming appointments within the next N hours."""
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours_ahead)

        appointments = []

        for appointment in self._appointments.values():
            if cpa_id and appointment.cpa_id != cpa_id:
                continue
            if firm_id and appointment.firm_id != firm_id:
                continue
            if appointment.status in [AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED]:
                continue
            if not appointment.start_time:
                continue
            if now <= appointment.start_time <= cutoff:
                appointments.append(appointment)

        appointments.sort(key=lambda a: a.start_time)

        return appointments

    def get_todays_appointments(
        self,
        cpa_id: Optional[UUID] = None,
        firm_id: Optional[UUID] = None,
    ) -> List[Appointment]:
        """Get today's appointments."""
        today = date.today()
        return self.get_appointments_for_cpa(cpa_id, today, today) if cpa_id else \
               self.get_appointments_for_firm(firm_id, today, today) if firm_id else []

    # =========================================================================
    # REMINDERS
    # =========================================================================

    def get_appointments_needing_reminders(self) -> Dict[str, List[Appointment]]:
        """Get appointments that need reminder notifications."""
        result = {
            "24h": [],
            "1h": [],
        }

        for appointment in self._appointments.values():
            if appointment.status not in [AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]:
                continue

            if appointment.needs_24h_reminder:
                result["24h"].append(appointment)
            if appointment.needs_1h_reminder:
                result["1h"].append(appointment)

        return result

    def mark_reminder_sent(
        self,
        appointment_id: UUID,
        reminder_type: str,  # "24h" or "1h"
    ) -> bool:
        """Mark a reminder as sent."""
        appointment = self._appointments.get(appointment_id)
        if not appointment:
            return False

        if reminder_type == "24h":
            appointment.reminder_sent_24h = True
        elif reminder_type == "1h":
            appointment.reminder_sent_1h = True

        return True

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_appointment_summary(
        self,
        firm_id: Optional[UUID] = None,
        cpa_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get summary statistics for appointments."""
        appointments = []

        for appointment in self._appointments.values():
            if firm_id and appointment.firm_id != firm_id:
                continue
            if cpa_id and appointment.cpa_id != cpa_id:
                continue
            if start_date and appointment.start_time:
                if appointment.start_time.date() < start_date:
                    continue
            if end_date and appointment.start_time:
                if appointment.start_time.date() > end_date:
                    continue

            appointments.append(appointment)

        by_status = defaultdict(int)
        by_type = defaultdict(int)

        completed = 0
        no_shows = 0
        cancelled = 0

        for appt in appointments:
            by_status[appt.status.value] += 1
            by_type[appt.appointment_type.value] += 1

            if appt.status == AppointmentStatus.COMPLETED:
                completed += 1
            elif appt.status == AppointmentStatus.NO_SHOW:
                no_shows += 1
            elif appt.status == AppointmentStatus.CANCELLED:
                cancelled += 1

        total = len(appointments)
        show_rate = ((completed / (completed + no_shows)) * 100) if (completed + no_shows) > 0 else 0

        return {
            "total": total,
            "by_status": dict(by_status),
            "by_type": dict(by_type),
            "completed": completed,
            "no_shows": no_shows,
            "cancelled": cancelled,
            "show_rate": round(show_rate, 1),
        }


# Global service instance
appointment_service = AppointmentService()
