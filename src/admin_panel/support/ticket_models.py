"""
Support Ticket Models

Data models for support ticket system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID, uuid4


class TicketStatus(str, Enum):
    """Status of a support ticket."""
    NEW = "new"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    WAITING_INTERNAL = "waiting_internal"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Priority levels for tickets."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class TicketCategory(str, Enum):
    """Categories of support tickets."""
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    ONBOARDING = "onboarding"
    INTEGRATION = "integration"
    SECURITY = "security"
    OTHER = "other"


class MessageType(str, Enum):
    """Types of ticket messages."""
    CUSTOMER = "customer"
    AGENT = "agent"
    SYSTEM = "system"
    INTERNAL_NOTE = "internal_note"


# SLA definitions (in hours)
SLA_RESPONSE_TIMES = {
    TicketPriority.CRITICAL: 1,
    TicketPriority.URGENT: 4,
    TicketPriority.HIGH: 8,
    TicketPriority.NORMAL: 24,
    TicketPriority.LOW: 48,
}

SLA_RESOLUTION_TIMES = {
    TicketPriority.CRITICAL: 4,
    TicketPriority.URGENT: 24,
    TicketPriority.HIGH: 48,
    TicketPriority.NORMAL: 72,
    TicketPriority.LOW: 120,
}


@dataclass
class TicketAttachment:
    """Attachment on a ticket or message."""
    id: UUID = field(default_factory=uuid4)
    ticket_id: UUID = None
    message_id: Optional[UUID] = None
    filename: str = ""
    file_type: str = ""
    file_size: int = 0
    storage_path: str = ""
    uploaded_by: Optional[UUID] = None
    uploaded_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "ticket_id": str(self.ticket_id) if self.ticket_id else None,
            "message_id": str(self.message_id) if self.message_id else None,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "uploaded_by": str(self.uploaded_by) if self.uploaded_by else None,
            "uploaded_at": self.uploaded_at.isoformat(),
        }


@dataclass
class TicketMessage:
    """Message on a support ticket."""
    id: UUID = field(default_factory=uuid4)
    ticket_id: UUID = None
    message_type: MessageType = MessageType.CUSTOMER
    author_id: Optional[UUID] = None
    author_name: str = ""
    author_email: Optional[str] = None
    content: str = ""
    is_internal: bool = False  # Internal notes not visible to customer
    attachments: List[TicketAttachment] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "ticket_id": str(self.ticket_id) if self.ticket_id else None,
            "message_type": self.message_type.value,
            "author_id": str(self.author_id) if self.author_id else None,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "content": self.content,
            "is_internal": self.is_internal,
            "attachments": [a.to_dict() for a in self.attachments],
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Ticket:
    """
    Support ticket.

    Represents a customer support request with full lifecycle management.
    """
    id: UUID = field(default_factory=uuid4)
    ticket_number: str = ""  # Human-readable ticket ID (e.g., TKT-2025-0001)

    # Customer info
    firm_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    customer_name: str = ""
    customer_email: str = ""

    # Ticket details
    subject: str = ""
    description: str = ""
    category: TicketCategory = TicketCategory.OTHER
    priority: TicketPriority = TicketPriority.NORMAL
    status: TicketStatus = TicketStatus.NEW

    # Assignment
    assigned_to: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    assigned_at: Optional[datetime] = None

    # SLA tracking
    sla_response_due: Optional[datetime] = None
    sla_resolution_due: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    sla_response_breached: bool = False
    sla_resolution_breached: bool = False

    # Resolution
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    resolution_notes: Optional[str] = None
    satisfaction_rating: Optional[int] = None  # 1-5
    satisfaction_feedback: Optional[str] = None

    # Messages and attachments
    messages: List[TicketMessage] = field(default_factory=list)

    # Tags for filtering
    tags: List[str] = field(default_factory=list)

    # Metadata
    source: str = "web"  # web, email, api, phone
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None

    def __post_init__(self):
        """Generate ticket number if not provided."""
        if not self.ticket_number:
            self.ticket_number = self._generate_ticket_number()

        # Calculate SLA deadlines
        if not self.sla_response_due:
            self._calculate_sla()

    def _generate_ticket_number(self) -> str:
        """Generate a human-readable ticket number."""
        year = datetime.utcnow().year
        import secrets
        seq = secrets.randbelow(9000) + 1000  # 1000-9999, cryptographically random
        return f"TKT-{year}-{seq}"

    def _calculate_sla(self):
        """Calculate SLA deadlines based on priority."""
        response_hours = SLA_RESPONSE_TIMES.get(self.priority, 24)
        resolution_hours = SLA_RESOLUTION_TIMES.get(self.priority, 72)

        self.sla_response_due = self.created_at + timedelta(hours=response_hours)
        self.sla_resolution_due = self.created_at + timedelta(hours=resolution_hours)

    @property
    def is_sla_response_at_risk(self) -> bool:
        """Check if SLA response is at risk (within 1 hour of breach)."""
        if self.first_response_at or not self.sla_response_due:
            return False
        remaining = (self.sla_response_due - datetime.utcnow()).total_seconds()
        return 0 < remaining < 3600

    @property
    def is_sla_resolution_at_risk(self) -> bool:
        """Check if SLA resolution is at risk (within 4 hours of breach)."""
        if self.status == TicketStatus.RESOLVED or not self.sla_resolution_due:
            return False
        remaining = (self.sla_resolution_due - datetime.utcnow()).total_seconds()
        return 0 < remaining < 14400

    @property
    def time_to_first_response(self) -> Optional[float]:
        """Calculate time to first response in hours."""
        if not self.first_response_at:
            return None
        delta = self.first_response_at - self.created_at
        return delta.total_seconds() / 3600

    @property
    def resolution_time(self) -> Optional[float]:
        """Calculate resolution time in hours."""
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.created_at
        return delta.total_seconds() / 3600

    def add_message(
        self,
        content: str,
        message_type: MessageType = MessageType.CUSTOMER,
        author_id: Optional[UUID] = None,
        author_name: str = "",
        author_email: Optional[str] = None,
        is_internal: bool = False,
    ) -> TicketMessage:
        """Add a message to the ticket."""
        message = TicketMessage(
            ticket_id=self.id,
            message_type=message_type,
            author_id=author_id,
            author_name=author_name,
            author_email=author_email,
            content=content,
            is_internal=is_internal,
        )
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

        # Track first response
        if message_type == MessageType.AGENT and not self.first_response_at:
            self.first_response_at = datetime.utcnow()
            # Check if SLA was breached
            if self.sla_response_due and self.first_response_at > self.sla_response_due:
                self.sla_response_breached = True

        # Update status based on message type
        if message_type == MessageType.CUSTOMER:
            if self.status == TicketStatus.WAITING_CUSTOMER:
                self.status = TicketStatus.OPEN
        elif message_type == MessageType.AGENT and not is_internal:
            if self.status in [TicketStatus.NEW, TicketStatus.OPEN]:
                self.status = TicketStatus.WAITING_CUSTOMER

        return message

    def assign(self, agent_id: UUID, agent_name: str = ""):
        """Assign ticket to an agent."""
        self.assigned_to = agent_id
        self.assigned_to_name = agent_name
        self.assigned_at = datetime.utcnow()
        if self.status == TicketStatus.NEW:
            self.status = TicketStatus.OPEN
        self.updated_at = datetime.utcnow()

    def resolve(self, resolved_by: UUID = None, resolution_notes: str = ""):
        """Mark ticket as resolved."""
        self.status = TicketStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        self.resolved_by = resolved_by
        self.resolution_notes = resolution_notes
        self.updated_at = datetime.utcnow()

        # Check if resolution SLA was breached
        if self.sla_resolution_due and self.resolved_at > self.sla_resolution_due:
            self.sla_resolution_breached = True

    def close(self):
        """Close the ticket."""
        self.status = TicketStatus.CLOSED
        self.closed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def reopen(self):
        """Reopen a closed ticket."""
        self.status = TicketStatus.OPEN
        self.closed_at = None
        self.resolved_at = None
        self.updated_at = datetime.utcnow()

    def rate_satisfaction(self, rating: int, feedback: str = ""):
        """Rate customer satisfaction."""
        if 1 <= rating <= 5:
            self.satisfaction_rating = rating
            self.satisfaction_feedback = feedback
            self.updated_at = datetime.utcnow()

    def to_dict(self, include_messages: bool = True) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "id": str(self.id),
            "ticket_number": self.ticket_number,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "customer_id": str(self.customer_id) if self.customer_id else None,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "subject": self.subject,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "assigned_to": str(self.assigned_to) if self.assigned_to else None,
            "assigned_to_name": self.assigned_to_name,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "sla_response_due": self.sla_response_due.isoformat() if self.sla_response_due else None,
            "sla_resolution_due": self.sla_resolution_due.isoformat() if self.sla_resolution_due else None,
            "first_response_at": self.first_response_at.isoformat() if self.first_response_at else None,
            "sla_response_breached": self.sla_response_breached,
            "sla_resolution_breached": self.sla_resolution_breached,
            "is_sla_response_at_risk": self.is_sla_response_at_risk,
            "is_sla_resolution_at_risk": self.is_sla_resolution_at_risk,
            "time_to_first_response_hours": self.time_to_first_response,
            "resolution_time_hours": self.resolution_time,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": str(self.resolved_by) if self.resolved_by else None,
            "resolution_notes": self.resolution_notes,
            "satisfaction_rating": self.satisfaction_rating,
            "satisfaction_feedback": self.satisfaction_feedback,
            "message_count": len(self.messages),
            "tags": self.tags,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

        if include_messages:
            # Filter out internal notes for customer-facing responses
            result["messages"] = [m.to_dict() for m in self.messages]

        return result

    def to_dict_customer(self) -> Dict[str, Any]:
        """Convert to dictionary for customer-facing response (no internal notes)."""
        result = self.to_dict(include_messages=False)
        result["messages"] = [
            m.to_dict() for m in self.messages if not m.is_internal
        ]
        return result
