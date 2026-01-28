"""
Event Publisher

Provides a simple interface for publishing real-time events
from anywhere in the application.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID

from .connection_manager import connection_manager
from .events import (
    RealtimeEvent,
    EventType,
    EventPriority,
    create_notification_event,
    create_return_status_event,
    create_task_assigned_event,
    create_appointment_event,
    create_lead_event,
    create_deadline_alert_event,
    create_client_message_event,
    create_system_announcement_event,
)

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Simplified interface for publishing real-time events.

    Usage:
        from realtime import event_publisher

        # Send notification to user
        await event_publisher.notify_user(
            user_id=user_id,
            firm_id=firm_id,
            title="New message",
            message="You have a new client message",
        )

        # Broadcast to firm
        await event_publisher.broadcast_to_firm(
            firm_id=firm_id,
            event_type="return_updated",
            data={"session_id": "..."},
        )
    """

    async def publish(self, event: RealtimeEvent):
        """Publish a raw event."""
        await connection_manager.broadcast_event(event)
        logger.debug(f"Published event: {event.event_type.value}")

    async def notify_user(
        self,
        user_id: UUID,
        firm_id: UUID,
        title: str,
        message: str,
        notification_type: str = "info",
        link: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
    ):
        """Send a notification to a specific user."""
        event = create_notification_event(
            user_id=user_id,
            firm_id=firm_id,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
            priority=priority,
        )
        await self.publish(event)

    async def broadcast_to_firm(
        self,
        firm_id: UUID,
        event_type: EventType,
        data: Dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL,
    ):
        """Broadcast an event to all users in a firm."""
        event = RealtimeEvent(
            event_type=event_type,
            priority=priority,
            firm_id=firm_id,
            data=data,
        )
        await self.publish(event)

    async def notify_return_status_change(
        self,
        session_id: str,
        firm_id: UUID,
        old_status: str,
        new_status: str,
        changed_by: str,
    ):
        """Notify about a return status change."""
        event = create_return_status_event(
            session_id=session_id,
            firm_id=firm_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
        )
        await self.publish(event)

    async def notify_task_assigned(
        self,
        task_id: UUID,
        assignee_id: UUID,
        firm_id: UUID,
        task_title: str,
        assigned_by: str,
    ):
        """Notify a user about a task assignment."""
        event = create_task_assigned_event(
            task_id=task_id,
            assignee_id=assignee_id,
            firm_id=firm_id,
            task_title=task_title,
            assigned_by=assigned_by,
        )
        await self.publish(event)

    async def notify_appointment_booked(
        self,
        appointment_id: UUID,
        cpa_user_id: UUID,
        firm_id: UUID,
        client_name: str,
        appointment_time: str,
        appointment_type: str,
    ):
        """Notify CPA about a new appointment booking."""
        event = create_appointment_event(
            event_type=EventType.APPOINTMENT_BOOKED,
            appointment_id=appointment_id,
            user_id=cpa_user_id,
            firm_id=firm_id,
            appointment_data={
                "client_name": client_name,
                "time": appointment_time,
                "type": appointment_type,
            },
        )
        await self.publish(event)

    async def notify_appointment_cancelled(
        self,
        appointment_id: UUID,
        cpa_user_id: UUID,
        firm_id: UUID,
        client_name: str,
        cancelled_by: str,
        reason: Optional[str] = None,
    ):
        """Notify about an appointment cancellation."""
        event = create_appointment_event(
            event_type=EventType.APPOINTMENT_CANCELLED,
            appointment_id=appointment_id,
            user_id=cpa_user_id,
            firm_id=firm_id,
            appointment_data={
                "client_name": client_name,
                "cancelled_by": cancelled_by,
                "reason": reason,
            },
        )
        await self.publish(event)

    async def notify_appointment_reminder(
        self,
        appointment_id: UUID,
        user_id: UUID,
        firm_id: UUID,
        appointment_time: str,
        reminder_type: str,  # "24h" or "1h"
    ):
        """Send an appointment reminder notification."""
        event = create_appointment_event(
            event_type=EventType.APPOINTMENT_REMINDER,
            appointment_id=appointment_id,
            user_id=user_id,
            firm_id=firm_id,
            appointment_data={
                "time": appointment_time,
                "reminder_type": reminder_type,
            },
        )
        await self.publish(event)

    async def notify_new_lead(
        self,
        firm_id: UUID,
        lead_id: UUID,
        lead_name: str,
        lead_source: Optional[str] = None,
        estimated_value: Optional[float] = None,
    ):
        """Notify firm about a new lead."""
        event = create_lead_event(
            firm_id=firm_id,
            lead_id=lead_id,
            lead_name=lead_name,
            event_type=EventType.LEAD_CAPTURED,
            additional_data={
                "source": lead_source,
                "estimated_value": estimated_value,
            },
        )
        await self.publish(event)

    async def notify_lead_converted(
        self,
        firm_id: UUID,
        lead_id: UUID,
        lead_name: str,
        converted_by: str,
    ):
        """Notify firm about a lead conversion."""
        event = create_lead_event(
            firm_id=firm_id,
            lead_id=lead_id,
            lead_name=lead_name,
            event_type=EventType.LEAD_CONVERTED,
            additional_data={
                "converted_by": converted_by,
            },
        )
        await self.publish(event)

    async def notify_deadline_approaching(
        self,
        user_id: UUID,
        firm_id: UUID,
        deadline_id: UUID,
        deadline_type: str,
        due_date: str,
        days_remaining: int,
    ):
        """Notify about an approaching deadline."""
        event = create_deadline_alert_event(
            user_id=user_id,
            firm_id=firm_id,
            deadline_id=deadline_id,
            deadline_type=deadline_type,
            due_date=due_date,
            is_overdue=False,
        )
        event.data["days_remaining"] = days_remaining
        await self.publish(event)

    async def notify_deadline_overdue(
        self,
        user_id: UUID,
        firm_id: UUID,
        deadline_id: UUID,
        deadline_type: str,
        due_date: str,
        days_overdue: int,
    ):
        """Notify about an overdue deadline."""
        event = create_deadline_alert_event(
            user_id=user_id,
            firm_id=firm_id,
            deadline_id=deadline_id,
            deadline_type=deadline_type,
            due_date=due_date,
            is_overdue=True,
        )
        event.data["days_overdue"] = days_overdue
        await self.publish(event)

    async def notify_client_message(
        self,
        cpa_user_id: UUID,
        firm_id: UUID,
        client_name: str,
        message_preview: str,
        session_id: Optional[str] = None,
    ):
        """Notify CPA about a new client message."""
        event = create_client_message_event(
            cpa_user_id=cpa_user_id,
            firm_id=firm_id,
            client_name=client_name,
            message_preview=message_preview,
            session_id=session_id,
        )
        await self.publish(event)

    async def notify_document_uploaded(
        self,
        firm_id: UUID,
        session_id: str,
        document_name: str,
        uploaded_by: str,
    ):
        """Notify about a document upload."""
        event = RealtimeEvent(
            event_type=EventType.DOCUMENT_UPLOADED,
            priority=EventPriority.NORMAL,
            firm_id=firm_id,
            session_id=session_id,
            data={
                "document_name": document_name,
                "uploaded_by": uploaded_by,
            },
        )
        await self.publish(event)

    async def notify_document_processed(
        self,
        firm_id: UUID,
        session_id: str,
        document_name: str,
        document_type: str,
        extracted_data_summary: Optional[str] = None,
    ):
        """Notify about completed document processing."""
        event = RealtimeEvent(
            event_type=EventType.DOCUMENT_PROCESSED,
            priority=EventPriority.HIGH,
            firm_id=firm_id,
            session_id=session_id,
            data={
                "document_name": document_name,
                "document_type": document_type,
                "summary": extracted_data_summary,
            },
        )
        await self.publish(event)

    async def broadcast_system_announcement(
        self,
        title: str,
        message: str,
        severity: str = "info",
        target_firm_ids: Optional[List[UUID]] = None,
    ):
        """Broadcast a system announcement."""
        event = create_system_announcement_event(
            title=title,
            message=message,
            severity=severity,
            target_firm_ids=target_firm_ids,
        )
        await self.publish(event)

    async def notify_resource_locked(
        self,
        firm_id: UUID,
        session_id: str,
        resource_type: str,
        resource_id: str,
        locked_by: str,
        lock_reason: Optional[str] = None,
    ):
        """Notify that a resource has been locked for editing."""
        event = RealtimeEvent(
            event_type=EventType.RESOURCE_LOCKED,
            priority=EventPriority.HIGH,
            firm_id=firm_id,
            session_id=session_id,
            data={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "locked_by": locked_by,
                "reason": lock_reason,
            },
        )
        await self.publish(event)

    async def notify_resource_unlocked(
        self,
        firm_id: UUID,
        session_id: str,
        resource_type: str,
        resource_id: str,
    ):
        """Notify that a resource has been unlocked."""
        event = RealtimeEvent(
            event_type=EventType.RESOURCE_UNLOCKED,
            priority=EventPriority.NORMAL,
            firm_id=firm_id,
            session_id=session_id,
            data={
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )
        await self.publish(event)

    async def notify_user_joined_session(
        self,
        firm_id: UUID,
        session_id: str,
        user_name: str,
        user_role: str,
    ):
        """Notify that a user has joined a session."""
        event = RealtimeEvent(
            event_type=EventType.USER_JOINED_SESSION,
            priority=EventPriority.LOW,
            firm_id=firm_id,
            session_id=session_id,
            data={
                "user_name": user_name,
                "user_role": user_role,
            },
        )
        await self.publish(event)

    async def notify_user_left_session(
        self,
        firm_id: UUID,
        session_id: str,
        user_name: str,
    ):
        """Notify that a user has left a session."""
        event = RealtimeEvent(
            event_type=EventType.USER_LEFT_SESSION,
            priority=EventPriority.LOW,
            firm_id=firm_id,
            session_id=session_id,
            data={
                "user_name": user_name,
            },
        )
        await self.publish(event)


# Singleton instance
event_publisher = EventPublisher()
