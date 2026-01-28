"""
Deadline Models

Data models for deadline management system.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID, uuid4


class DeadlineType(str, Enum):
    """Types of tax deadlines."""
    FILING = "filing"                          # Tax return filing deadline
    EXTENSION = "extension"                    # Extension deadline (Oct 15)
    ESTIMATED_Q1 = "estimated_q1"              # Q1 estimated tax (Apr 15)
    ESTIMATED_Q2 = "estimated_q2"              # Q2 estimated tax (Jun 15)
    ESTIMATED_Q3 = "estimated_q3"              # Q3 estimated tax (Sep 15)
    ESTIMATED_Q4 = "estimated_q4"              # Q4 estimated tax (Jan 15 next year)
    DOCUMENT_REQUEST = "document_request"      # Document due from client
    REVIEW = "review"                          # Internal review deadline
    SIGNATURE = "signature"                    # Client signature deadline
    PAYMENT = "payment"                        # Payment due deadline
    CUSTOM = "custom"                          # Custom deadline


class DeadlineStatus(str, Enum):
    """Status of a deadline."""
    UPCOMING = "upcoming"                      # Not yet due
    DUE_SOON = "due_soon"                      # Due within 7 days
    OVERDUE = "overdue"                        # Past due date
    COMPLETED = "completed"                    # Met the deadline
    EXTENDED = "extended"                      # Extension filed
    WAIVED = "waived"                          # Deadline waived/not applicable


class ReminderType(str, Enum):
    """Types of reminders."""
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"
    PUSH = "push"


@dataclass
class DeadlineReminder:
    """Reminder configuration for a deadline."""
    id: UUID = field(default_factory=uuid4)
    deadline_id: UUID = None
    days_before: int = 7                       # Days before deadline to send
    reminder_type: ReminderType = ReminderType.EMAIL
    recipient_type: str = "cpa"                # "cpa", "client", "both"
    message_template: Optional[str] = None
    is_sent: bool = False
    sent_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "deadline_id": str(self.deadline_id) if self.deadline_id else None,
            "days_before": self.days_before,
            "reminder_type": self.reminder_type.value,
            "recipient_type": self.recipient_type,
            "message_template": self.message_template,
            "is_sent": self.is_sent,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DeadlineAlert:
    """Alert generated for a deadline."""
    id: UUID = field(default_factory=uuid4)
    deadline_id: UUID = None
    alert_type: str = "warning"                # "warning", "urgent", "overdue"
    title: str = ""
    message: str = ""
    is_read: bool = False
    is_dismissed: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "deadline_id": str(self.deadline_id) if self.deadline_id else None,
            "alert_type": self.alert_type,
            "title": self.title,
            "message": self.message,
            "is_read": self.is_read,
            "is_dismissed": self.is_dismissed,
            "created_at": self.created_at.isoformat(),
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }


@dataclass
class Deadline:
    """
    Represents a tax deadline.

    Tracks filing deadlines, extensions, estimated payments,
    and custom deadlines with reminder support.
    """
    id: UUID = field(default_factory=uuid4)
    firm_id: UUID = None                       # Tenant/firm ID
    client_id: Optional[UUID] = None           # Specific client (None = all clients)
    session_id: Optional[str] = None           # Specific tax return session

    # Deadline details
    deadline_type: DeadlineType = DeadlineType.FILING
    title: str = ""
    description: Optional[str] = None
    due_date: date = None
    tax_year: int = 2025

    # Status tracking
    status: DeadlineStatus = DeadlineStatus.UPCOMING
    completed_at: Optional[datetime] = None
    completed_by: Optional[UUID] = None        # User who completed it

    # Extension tracking
    extension_filed: bool = False
    extension_filed_at: Optional[datetime] = None
    extended_due_date: Optional[date] = None

    # Assignment
    assigned_to: Optional[UUID] = None         # Staff member responsible

    # Priority
    priority: str = "normal"                   # "low", "normal", "high", "urgent"

    # Reminders
    reminders: List[DeadlineReminder] = field(default_factory=list)

    # Notes
    notes: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[UUID] = None

    def __post_init__(self):
        """Auto-generate title if not provided."""
        if not self.title and self.deadline_type:
            self.title = self._generate_title()

    def _generate_title(self) -> str:
        """Generate default title based on deadline type."""
        titles = {
            DeadlineType.FILING: f"Tax Return Filing - {self.tax_year}",
            DeadlineType.EXTENSION: f"Extension Deadline - {self.tax_year}",
            DeadlineType.ESTIMATED_Q1: f"Q1 Estimated Tax Payment - {self.tax_year}",
            DeadlineType.ESTIMATED_Q2: f"Q2 Estimated Tax Payment - {self.tax_year}",
            DeadlineType.ESTIMATED_Q3: f"Q3 Estimated Tax Payment - {self.tax_year}",
            DeadlineType.ESTIMATED_Q4: f"Q4 Estimated Tax Payment - {self.tax_year + 1}",
            DeadlineType.DOCUMENT_REQUEST: "Document Due",
            DeadlineType.REVIEW: "Internal Review",
            DeadlineType.SIGNATURE: "Signature Required",
            DeadlineType.PAYMENT: "Payment Due",
            DeadlineType.CUSTOM: "Custom Deadline",
        }
        return titles.get(self.deadline_type, "Deadline")

    @property
    def effective_due_date(self) -> date:
        """Get the effective due date (considering extensions)."""
        if self.extension_filed and self.extended_due_date:
            return self.extended_due_date
        return self.due_date

    @property
    def days_until_due(self) -> int:
        """Calculate days until deadline."""
        if not self.effective_due_date:
            return 0
        today = date.today()
        delta = self.effective_due_date - today
        return delta.days

    @property
    def is_overdue(self) -> bool:
        """Check if deadline is overdue."""
        return self.days_until_due < 0 and self.status not in [
            DeadlineStatus.COMPLETED,
            DeadlineStatus.WAIVED,
        ]

    @property
    def is_due_soon(self) -> bool:
        """Check if deadline is due within 7 days."""
        return 0 <= self.days_until_due <= 7

    @property
    def urgency_level(self) -> str:
        """Determine urgency level based on days until due."""
        if self.status == DeadlineStatus.COMPLETED:
            return "completed"
        if self.is_overdue:
            return "overdue"
        days = self.days_until_due
        if days <= 3:
            return "critical"
        if days <= 7:
            return "urgent"
        if days <= 14:
            return "warning"
        return "normal"

    def update_status(self):
        """Update status based on current date."""
        if self.status in [DeadlineStatus.COMPLETED, DeadlineStatus.WAIVED]:
            return

        if self.extension_filed:
            self.status = DeadlineStatus.EXTENDED
        elif self.is_overdue:
            self.status = DeadlineStatus.OVERDUE
        elif self.is_due_soon:
            self.status = DeadlineStatus.DUE_SOON
        else:
            self.status = DeadlineStatus.UPCOMING

    def mark_completed(self, completed_by: UUID = None):
        """Mark deadline as completed."""
        self.status = DeadlineStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.completed_by = completed_by
        self.updated_at = datetime.utcnow()

    def file_extension(self, extended_date: date, filed_by: UUID = None):
        """File an extension for this deadline."""
        self.extension_filed = True
        self.extension_filed_at = datetime.utcnow()
        self.extended_due_date = extended_date
        self.status = DeadlineStatus.EXTENDED
        self.updated_at = datetime.utcnow()

    def add_reminder(self, days_before: int, reminder_type: ReminderType = ReminderType.EMAIL,
                     recipient_type: str = "cpa") -> DeadlineReminder:
        """Add a reminder for this deadline."""
        reminder = DeadlineReminder(
            deadline_id=self.id,
            days_before=days_before,
            reminder_type=reminder_type,
            recipient_type=recipient_type,
        )
        self.reminders.append(reminder)
        return reminder

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        self.update_status()
        return {
            "id": str(self.id),
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "client_id": str(self.client_id) if self.client_id else None,
            "session_id": self.session_id,
            "deadline_type": self.deadline_type.value,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "effective_due_date": self.effective_due_date.isoformat() if self.effective_due_date else None,
            "tax_year": self.tax_year,
            "status": self.status.value,
            "days_until_due": self.days_until_due,
            "is_overdue": self.is_overdue,
            "is_due_soon": self.is_due_soon,
            "urgency_level": self.urgency_level,
            "extension_filed": self.extension_filed,
            "extension_filed_at": self.extension_filed_at.isoformat() if self.extension_filed_at else None,
            "extended_due_date": self.extended_due_date.isoformat() if self.extended_due_date else None,
            "assigned_to": str(self.assigned_to) if self.assigned_to else None,
            "priority": self.priority,
            "reminders": [r.to_dict() for r in self.reminders],
            "notes": self.notes,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "completed_by": str(self.completed_by) if self.completed_by else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# Standard tax deadlines for reference
STANDARD_DEADLINES_2025 = {
    DeadlineType.FILING: date(2025, 4, 15),
    DeadlineType.EXTENSION: date(2025, 10, 15),
    DeadlineType.ESTIMATED_Q1: date(2025, 4, 15),
    DeadlineType.ESTIMATED_Q2: date(2025, 6, 16),  # June 15 falls on Sunday
    DeadlineType.ESTIMATED_Q3: date(2025, 9, 15),
    DeadlineType.ESTIMATED_Q4: date(2026, 1, 15),
}

STANDARD_DEADLINES_2026 = {
    DeadlineType.FILING: date(2026, 4, 15),
    DeadlineType.EXTENSION: date(2026, 10, 15),
    DeadlineType.ESTIMATED_Q1: date(2026, 4, 15),
    DeadlineType.ESTIMATED_Q2: date(2026, 6, 15),
    DeadlineType.ESTIMATED_Q3: date(2026, 9, 15),
    DeadlineType.ESTIMATED_Q4: date(2027, 1, 15),
}
