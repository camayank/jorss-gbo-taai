"""
Real-Time Event Models

Defines event types and structures for WebSocket communication.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from uuid import UUID, uuid4
import json


class EventType(str, Enum):
    """Types of real-time events."""
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    HEARTBEAT = "heartbeat"

    # Notification events
    NOTIFICATION = "notification"
    NOTIFICATION_READ = "notification_read"

    # Return/Document events
    RETURN_STATUS_CHANGED = "return_status_changed"
    RETURN_UPDATED = "return_updated"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"

    # Appointment events
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_REMINDER = "appointment_reminder"

    # Task events
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_UPDATED = "task_updated"

    # Deadline events
    DEADLINE_APPROACHING = "deadline_approaching"
    DEADLINE_OVERDUE = "deadline_overdue"

    # Lead events
    LEAD_CAPTURED = "lead_captured"
    LEAD_CONVERTED = "lead_converted"

    # Client events
    CLIENT_MESSAGE = "client_message"
    CLIENT_ACTIVITY = "client_activity"

    # System events
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    MAINTENANCE_SCHEDULED = "maintenance_scheduled"

    # Collaboration events
    USER_JOINED_SESSION = "user_joined_session"
    USER_LEFT_SESSION = "user_left_session"
    RESOURCE_LOCKED = "resource_locked"
    RESOURCE_UNLOCKED = "resource_unlocked"


class EventPriority(str, Enum):
    """Priority levels for events."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class RealtimeEvent:
    """
    Base class for all real-time events.

    Events are broadcast to connected WebSocket clients
    based on their subscriptions and permissions.
    """
    id: UUID = field(default_factory=uuid4)
    event_type: EventType = EventType.NOTIFICATION
    priority: EventPriority = EventPriority.NORMAL

    # Payload
    data: Dict[str, Any] = field(default_factory=dict)

    # Targeting
    firm_id: Optional[UUID] = None  # Target specific firm
    user_id: Optional[UUID] = None  # Target specific user
    session_id: Optional[str] = None  # Target specific return session
    broadcast: bool = False  # Send to all connected clients

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    source: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "type": self.event_type.value,
            "priority": self.priority.value,
            "data": self.data,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "user_id": str(self.user_id) if self.user_id else None,
            "session_id": self.session_id,
            "timestamp": self.created_at.isoformat(),
            "source": self.source,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RealtimeEvent":
        """Create event from dictionary."""
        return cls(
            id=UUID(data.get("id", str(uuid4()))),
            event_type=EventType(data.get("type", "notification")),
            priority=EventPriority(data.get("priority", "normal")),
            data=data.get("data", {}),
            firm_id=UUID(data["firm_id"]) if data.get("firm_id") else None,
            user_id=UUID(data["user_id"]) if data.get("user_id") else None,
            session_id=data.get("session_id"),
            source=data.get("source", "system"),
        )


# Convenience functions for creating common events

def create_notification_event(
    user_id: UUID,
    firm_id: UUID,
    title: str,
    message: str,
    notification_type: str = "info",
    link: Optional[str] = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> RealtimeEvent:
    """Create a notification event."""
    return RealtimeEvent(
        event_type=EventType.NOTIFICATION,
        priority=priority,
        user_id=user_id,
        firm_id=firm_id,
        data={
            "title": title,
            "message": message,
            "type": notification_type,
            "link": link,
        },
    )


def create_return_status_event(
    session_id: str,
    firm_id: UUID,
    old_status: str,
    new_status: str,
    changed_by: str,
) -> RealtimeEvent:
    """Create a return status change event."""
    return RealtimeEvent(
        event_type=EventType.RETURN_STATUS_CHANGED,
        priority=EventPriority.HIGH,
        firm_id=firm_id,
        session_id=session_id,
        data={
            "session_id": session_id,
            "old_status": old_status,
            "new_status": new_status,
            "changed_by": changed_by,
        },
    )


def create_task_assigned_event(
    task_id: UUID,
    assignee_id: UUID,
    firm_id: UUID,
    task_title: str,
    assigned_by: str,
) -> RealtimeEvent:
    """Create a task assigned event."""
    return RealtimeEvent(
        event_type=EventType.TASK_ASSIGNED,
        priority=EventPriority.HIGH,
        user_id=assignee_id,
        firm_id=firm_id,
        data={
            "task_id": str(task_id),
            "title": task_title,
            "assigned_by": assigned_by,
        },
    )


def create_appointment_event(
    event_type: EventType,
    appointment_id: UUID,
    user_id: UUID,
    firm_id: UUID,
    appointment_data: Dict[str, Any],
) -> RealtimeEvent:
    """Create an appointment-related event."""
    return RealtimeEvent(
        event_type=event_type,
        priority=EventPriority.HIGH,
        user_id=user_id,
        firm_id=firm_id,
        data={
            "appointment_id": str(appointment_id),
            **appointment_data,
        },
    )


def create_lead_event(
    firm_id: UUID,
    lead_id: UUID,
    lead_name: str,
    event_type: EventType = EventType.LEAD_CAPTURED,
    additional_data: Optional[Dict[str, Any]] = None,
) -> RealtimeEvent:
    """Create a lead-related event."""
    return RealtimeEvent(
        event_type=event_type,
        priority=EventPriority.HIGH,
        firm_id=firm_id,
        data={
            "lead_id": str(lead_id),
            "lead_name": lead_name,
            **(additional_data or {}),
        },
    )


def create_deadline_alert_event(
    user_id: UUID,
    firm_id: UUID,
    deadline_id: UUID,
    deadline_type: str,
    due_date: str,
    is_overdue: bool = False,
) -> RealtimeEvent:
    """Create a deadline alert event."""
    return RealtimeEvent(
        event_type=EventType.DEADLINE_OVERDUE if is_overdue else EventType.DEADLINE_APPROACHING,
        priority=EventPriority.URGENT if is_overdue else EventPriority.HIGH,
        user_id=user_id,
        firm_id=firm_id,
        data={
            "deadline_id": str(deadline_id),
            "deadline_type": deadline_type,
            "due_date": due_date,
            "is_overdue": is_overdue,
        },
    )


def create_client_message_event(
    cpa_user_id: UUID,
    firm_id: UUID,
    client_name: str,
    message_preview: str,
    session_id: Optional[str] = None,
) -> RealtimeEvent:
    """Create a client message event."""
    return RealtimeEvent(
        event_type=EventType.CLIENT_MESSAGE,
        priority=EventPriority.HIGH,
        user_id=cpa_user_id,
        firm_id=firm_id,
        session_id=session_id,
        data={
            "client_name": client_name,
            "message_preview": message_preview[:100],
        },
    )


def create_system_announcement_event(
    title: str,
    message: str,
    severity: str = "info",
    target_firm_ids: Optional[List[UUID]] = None,
) -> RealtimeEvent:
    """Create a system announcement event."""
    return RealtimeEvent(
        event_type=EventType.SYSTEM_ANNOUNCEMENT,
        priority=EventPriority.HIGH if severity == "warning" else EventPriority.URGENT if severity == "critical" else EventPriority.NORMAL,
        broadcast=target_firm_ids is None,
        data={
            "title": title,
            "message": message,
            "severity": severity,
            "target_firm_ids": [str(f) for f in target_firm_ids] if target_firm_ids else None,
        },
    )
