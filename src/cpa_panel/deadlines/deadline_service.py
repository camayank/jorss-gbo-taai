"""
Deadline Service

Business logic for deadline management.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from collections import defaultdict

from .deadline_models import (
    Deadline,
    DeadlineType,
    DeadlineStatus,
    DeadlineReminder,
    DeadlineAlert,
    ReminderType,
    STANDARD_DEADLINES_2025,
    STANDARD_DEADLINES_2026,
)

logger = logging.getLogger(__name__)


class DeadlineService:
    """
    Service for managing tax deadlines.

    Provides:
    - Deadline creation and management
    - Standard deadline generation for tax years
    - Reminder scheduling
    - Alert generation
    - Calendar view support
    - Deadline analytics
    """

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._deadlines: Dict[UUID, Deadline] = {}
        self._alerts: Dict[UUID, DeadlineAlert] = {}
        self._reminders_sent: Dict[UUID, List[UUID]] = defaultdict(list)

    # =========================================================================
    # DEADLINE CRUD
    # =========================================================================

    def create_deadline(
        self,
        firm_id: UUID,
        deadline_type: DeadlineType,
        due_date: date,
        title: Optional[str] = None,
        description: Optional[str] = None,
        client_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        tax_year: int = 2025,
        assigned_to: Optional[UUID] = None,
        priority: str = "normal",
        created_by: Optional[UUID] = None,
        auto_reminders: bool = True,
    ) -> Deadline:
        """
        Create a new deadline.

        Args:
            firm_id: Tenant/firm ID
            deadline_type: Type of deadline
            due_date: Due date
            title: Optional custom title
            description: Optional description
            client_id: Optional client ID (None = firm-wide)
            session_id: Optional tax return session ID
            tax_year: Tax year
            assigned_to: Staff member responsible
            priority: Priority level
            created_by: User creating the deadline
            auto_reminders: Whether to add default reminders

        Returns:
            Created Deadline object
        """
        deadline = Deadline(
            firm_id=firm_id,
            client_id=client_id,
            session_id=session_id,
            deadline_type=deadline_type,
            title=title or "",
            description=description,
            due_date=due_date,
            tax_year=tax_year,
            assigned_to=assigned_to,
            priority=priority,
            created_by=created_by,
        )

        # Auto-generate title if not provided
        if not title:
            deadline.title = deadline._generate_title()

        # Add default reminders
        if auto_reminders:
            self._add_default_reminders(deadline)

        self._deadlines[deadline.id] = deadline
        logger.info(f"Created deadline: {deadline.id} - {deadline.title}")

        return deadline

    def _add_default_reminders(self, deadline: Deadline):
        """Add default reminders based on deadline type."""
        # Standard reminder schedule
        reminder_days = [30, 14, 7, 3, 1]

        # Urgent deadlines get more reminders
        if deadline.deadline_type in [DeadlineType.FILING, DeadlineType.EXTENSION]:
            for days in reminder_days:
                deadline.add_reminder(days, ReminderType.EMAIL, "both")
            # Add SMS for final reminders
            deadline.add_reminder(3, ReminderType.SMS, "cpa")
            deadline.add_reminder(1, ReminderType.SMS, "cpa")
        else:
            # Standard reminders
            for days in [7, 3, 1]:
                deadline.add_reminder(days, ReminderType.EMAIL, "cpa")

    def get_deadline(self, deadline_id: UUID) -> Optional[Deadline]:
        """Get a deadline by ID."""
        deadline = self._deadlines.get(deadline_id)
        if deadline:
            deadline.update_status()
        return deadline

    def update_deadline(
        self,
        deadline_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[date] = None,
        assigned_to: Optional[UUID] = None,
        priority: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Deadline]:
        """Update a deadline."""
        deadline = self._deadlines.get(deadline_id)
        if not deadline:
            return None

        if title is not None:
            deadline.title = title
        if description is not None:
            deadline.description = description
        if due_date is not None:
            deadline.due_date = due_date
        if assigned_to is not None:
            deadline.assigned_to = assigned_to
        if priority is not None:
            deadline.priority = priority
        if notes is not None:
            deadline.notes = notes

        deadline.updated_at = datetime.utcnow()
        deadline.update_status()

        logger.info(f"Updated deadline: {deadline_id}")
        return deadline

    def delete_deadline(self, deadline_id: UUID) -> bool:
        """Delete a deadline."""
        if deadline_id in self._deadlines:
            del self._deadlines[deadline_id]
            logger.info(f"Deleted deadline: {deadline_id}")
            return True
        return False

    def complete_deadline(
        self,
        deadline_id: UUID,
        completed_by: Optional[UUID] = None,
    ) -> Optional[Deadline]:
        """Mark a deadline as completed."""
        deadline = self._deadlines.get(deadline_id)
        if not deadline:
            return None

        deadline.mark_completed(completed_by)
        logger.info(f"Completed deadline: {deadline_id}")
        return deadline

    def file_extension(
        self,
        deadline_id: UUID,
        extended_date: date,
        filed_by: Optional[UUID] = None,
    ) -> Optional[Deadline]:
        """File an extension for a deadline."""
        deadline = self._deadlines.get(deadline_id)
        if not deadline:
            return None

        deadline.file_extension(extended_date, filed_by)

        # Add reminders for the new extended deadline
        self._add_default_reminders(deadline)

        logger.info(f"Filed extension for deadline: {deadline_id}, new date: {extended_date}")
        return deadline

    # =========================================================================
    # DEADLINE QUERIES
    # =========================================================================

    def get_deadlines_for_firm(
        self,
        firm_id: UUID,
        status: Optional[DeadlineStatus] = None,
        deadline_type: Optional[DeadlineType] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        client_id: Optional[UUID] = None,
        assigned_to: Optional[UUID] = None,
        include_completed: bool = False,
    ) -> List[Deadline]:
        """Get deadlines for a firm with optional filters."""
        deadlines = []

        for deadline in self._deadlines.values():
            if deadline.firm_id != firm_id:
                continue

            # Update status before filtering
            deadline.update_status()

            # Apply filters
            if status and deadline.status != status:
                continue
            if deadline_type and deadline.deadline_type != deadline_type:
                continue
            if client_id and deadline.client_id != client_id:
                continue
            if assigned_to and deadline.assigned_to != assigned_to:
                continue
            if not include_completed and deadline.status == DeadlineStatus.COMPLETED:
                continue

            # Date range filter
            effective_date = deadline.effective_due_date
            if from_date and effective_date < from_date:
                continue
            if to_date and effective_date > to_date:
                continue

            deadlines.append(deadline)

        # Sort by due date
        deadlines.sort(key=lambda d: d.effective_due_date or date.max)

        return deadlines

    def get_upcoming_deadlines(
        self,
        firm_id: UUID,
        days_ahead: int = 30,
    ) -> List[Deadline]:
        """Get deadlines due within the next N days."""
        today = date.today()
        to_date = today + timedelta(days=days_ahead)

        return self.get_deadlines_for_firm(
            firm_id=firm_id,
            from_date=today,
            to_date=to_date,
        )

    def get_overdue_deadlines(self, firm_id: UUID) -> List[Deadline]:
        """Get all overdue deadlines."""
        return self.get_deadlines_for_firm(
            firm_id=firm_id,
            status=DeadlineStatus.OVERDUE,
        )

    def get_deadlines_for_client(
        self,
        firm_id: UUID,
        client_id: UUID,
        include_completed: bool = False,
    ) -> List[Deadline]:
        """Get all deadlines for a specific client."""
        return self.get_deadlines_for_firm(
            firm_id=firm_id,
            client_id=client_id,
            include_completed=include_completed,
        )

    def get_deadlines_for_session(
        self,
        session_id: str,
    ) -> List[Deadline]:
        """Get all deadlines for a specific tax return session."""
        return [
            d for d in self._deadlines.values()
            if d.session_id == session_id
        ]

    # =========================================================================
    # STANDARD DEADLINE GENERATION
    # =========================================================================

    def generate_standard_deadlines(
        self,
        firm_id: UUID,
        tax_year: int = 2025,
        client_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        include_estimated: bool = True,
        created_by: Optional[UUID] = None,
    ) -> List[Deadline]:
        """
        Generate standard tax deadlines for a tax year.

        Creates:
        - Filing deadline (April 15)
        - Extension deadline (October 15)
        - Quarterly estimated payment deadlines (if requested)
        """
        deadlines = []

        # Get standard dates
        standard_dates = STANDARD_DEADLINES_2025 if tax_year == 2025 else STANDARD_DEADLINES_2026

        # Filing deadline
        filing = self.create_deadline(
            firm_id=firm_id,
            deadline_type=DeadlineType.FILING,
            due_date=standard_dates[DeadlineType.FILING],
            client_id=client_id,
            session_id=session_id,
            tax_year=tax_year,
            priority="high",
            created_by=created_by,
        )
        deadlines.append(filing)

        # Extension deadline (created but not active until extension filed)
        extension = self.create_deadline(
            firm_id=firm_id,
            deadline_type=DeadlineType.EXTENSION,
            due_date=standard_dates[DeadlineType.EXTENSION],
            client_id=client_id,
            session_id=session_id,
            tax_year=tax_year,
            priority="high",
            created_by=created_by,
        )
        extension.status = DeadlineStatus.WAIVED  # Not active until extension filed
        deadlines.append(extension)

        # Estimated tax deadlines
        if include_estimated:
            for q_type in [
                DeadlineType.ESTIMATED_Q1,
                DeadlineType.ESTIMATED_Q2,
                DeadlineType.ESTIMATED_Q3,
                DeadlineType.ESTIMATED_Q4,
            ]:
                if q_type in standard_dates:
                    est = self.create_deadline(
                        firm_id=firm_id,
                        deadline_type=q_type,
                        due_date=standard_dates[q_type],
                        client_id=client_id,
                        session_id=session_id,
                        tax_year=tax_year,
                        priority="normal",
                        created_by=created_by,
                    )
                    deadlines.append(est)

        logger.info(f"Generated {len(deadlines)} standard deadlines for tax year {tax_year}")
        return deadlines

    # =========================================================================
    # CALENDAR VIEW
    # =========================================================================

    def get_calendar_view(
        self,
        firm_id: UUID,
        year: int,
        month: int,
    ) -> Dict[str, Any]:
        """Get deadlines formatted for calendar display."""
        # Get first and last day of month
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        # Get deadlines for the month
        deadlines = self.get_deadlines_for_firm(
            firm_id=firm_id,
            from_date=first_day,
            to_date=last_day,
            include_completed=True,
        )

        # Group by date
        by_date: Dict[str, List[Dict]] = defaultdict(list)
        for deadline in deadlines:
            date_key = deadline.effective_due_date.isoformat()
            by_date[date_key].append(deadline.to_dict())

        return {
            "year": year,
            "month": month,
            "first_day": first_day.isoformat(),
            "last_day": last_day.isoformat(),
            "deadlines_by_date": dict(by_date),
            "total_deadlines": len(deadlines),
        }

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_deadline_summary(self, firm_id: UUID) -> Dict[str, Any]:
        """Get summary statistics for deadlines."""
        all_deadlines = self.get_deadlines_for_firm(firm_id, include_completed=True)

        # Count by status
        by_status = defaultdict(int)
        by_type = defaultdict(int)
        by_urgency = defaultdict(int)

        overdue_count = 0
        due_this_week = 0
        due_this_month = 0

        today = date.today()
        week_end = today + timedelta(days=7)
        month_end = today + timedelta(days=30)

        for deadline in all_deadlines:
            by_status[deadline.status.value] += 1
            by_type[deadline.deadline_type.value] += 1
            by_urgency[deadline.urgency_level] += 1

            if deadline.is_overdue:
                overdue_count += 1

            effective_date = deadline.effective_due_date
            if effective_date and deadline.status not in [DeadlineStatus.COMPLETED, DeadlineStatus.WAIVED]:
                if today <= effective_date <= week_end:
                    due_this_week += 1
                if today <= effective_date <= month_end:
                    due_this_month += 1

        return {
            "total": len(all_deadlines),
            "overdue": overdue_count,
            "due_this_week": due_this_week,
            "due_this_month": due_this_month,
            "by_status": dict(by_status),
            "by_type": dict(by_type),
            "by_urgency": dict(by_urgency),
            "completion_rate": (
                by_status.get("completed", 0) / len(all_deadlines) * 100
                if all_deadlines else 0
            ),
        }

    # =========================================================================
    # REMINDERS & ALERTS
    # =========================================================================

    def get_pending_reminders(
        self,
        firm_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get reminders that should be sent today."""
        today = date.today()
        pending = []

        for deadline in self._deadlines.values():
            if deadline.firm_id != firm_id:
                continue
            if deadline.status in [DeadlineStatus.COMPLETED, DeadlineStatus.WAIVED]:
                continue

            for reminder in deadline.reminders:
                if reminder.is_sent:
                    continue

                # Calculate when this reminder should fire
                reminder_date = deadline.effective_due_date - timedelta(days=reminder.days_before)

                if reminder_date <= today:
                    pending.append({
                        "deadline": deadline.to_dict(),
                        "reminder": reminder.to_dict(),
                        "should_send_on": reminder_date.isoformat(),
                    })

        return pending

    def mark_reminder_sent(
        self,
        deadline_id: UUID,
        reminder_id: UUID,
    ) -> bool:
        """Mark a reminder as sent."""
        deadline = self._deadlines.get(deadline_id)
        if not deadline:
            return False

        for reminder in deadline.reminders:
            if reminder.id == reminder_id:
                reminder.is_sent = True
                reminder.sent_at = datetime.utcnow()
                return True

        return False

    def generate_alerts(self, firm_id: UUID) -> List[DeadlineAlert]:
        """Generate alerts for deadlines needing attention."""
        alerts = []

        for deadline in self._deadlines.values():
            if deadline.firm_id != firm_id:
                continue
            if deadline.status in [DeadlineStatus.COMPLETED, DeadlineStatus.WAIVED]:
                continue

            # Check if we already have an active alert for this deadline
            existing_alert = any(
                a.deadline_id == deadline.id and not a.is_dismissed
                for a in self._alerts.values()
            )
            if existing_alert:
                continue

            # Generate alert based on urgency
            if deadline.is_overdue:
                alert = DeadlineAlert(
                    deadline_id=deadline.id,
                    alert_type="overdue",
                    title=f"OVERDUE: {deadline.title}",
                    message=f"This deadline was due on {deadline.effective_due_date}. Please take immediate action.",
                )
                alerts.append(alert)
                self._alerts[alert.id] = alert
            elif deadline.days_until_due <= 3:
                alert = DeadlineAlert(
                    deadline_id=deadline.id,
                    alert_type="urgent",
                    title=f"URGENT: {deadline.title}",
                    message=f"Due in {deadline.days_until_due} days on {deadline.effective_due_date}.",
                )
                alerts.append(alert)
                self._alerts[alert.id] = alert
            elif deadline.days_until_due <= 7:
                alert = DeadlineAlert(
                    deadline_id=deadline.id,
                    alert_type="warning",
                    title=f"Due Soon: {deadline.title}",
                    message=f"Due in {deadline.days_until_due} days on {deadline.effective_due_date}.",
                )
                alerts.append(alert)
                self._alerts[alert.id] = alert

        return alerts

    def get_alerts(
        self,
        firm_id: UUID,
        include_dismissed: bool = False,
    ) -> List[DeadlineAlert]:
        """Get alerts for a firm."""
        alerts = []

        for alert in self._alerts.values():
            deadline = self._deadlines.get(alert.deadline_id)
            if not deadline or deadline.firm_id != firm_id:
                continue
            if not include_dismissed and alert.is_dismissed:
                continue
            alerts.append(alert)

        # Sort by creation time (newest first)
        alerts.sort(key=lambda a: a.created_at, reverse=True)

        return alerts

    def dismiss_alert(self, alert_id: UUID) -> bool:
        """Dismiss an alert."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.is_dismissed = True
            return True
        return False

    def mark_alert_read(self, alert_id: UUID) -> bool:
        """Mark an alert as read."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.is_read = True
            alert.read_at = datetime.utcnow()
            return True
        return False


# Global service instance
deadline_service = DeadlineService()
