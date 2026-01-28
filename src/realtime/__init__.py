"""
Real-Time Updates Module

Provides WebSocket-based real-time updates for the platform.

Features:
- WebSocket connection management
- Event broadcasting to firms, users, and sessions
- Typed event system for consistent messaging
- Event publisher for easy integration

Usage:
    from realtime import event_publisher

    # Send notification to user
    await event_publisher.notify_user(
        user_id=user_id,
        firm_id=firm_id,
        title="New task assigned",
        message="You have been assigned a new task",
    )

    # Broadcast to firm
    await event_publisher.broadcast_to_firm(
        firm_id=firm_id,
        event_type=EventType.RETURN_STATUS_CHANGED,
        data={"session_id": "...", "new_status": "approved"},
    )

WebSocket Connection:
    Connect to: ws://host/ws?token=<auth_token>

    Messages (client -> server):
    - {"type": "subscribe", "session_id": "..."}
    - {"type": "unsubscribe", "session_id": "..."}
    - {"type": "heartbeat"}

    Events (server -> client):
    - {"id": "...", "type": "notification", "data": {...}, "timestamp": "..."}
"""

from .events import (
    EventType,
    EventPriority,
    RealtimeEvent,
    create_notification_event,
    create_return_status_event,
    create_task_assigned_event,
    create_appointment_event,
    create_lead_event,
    create_deadline_alert_event,
    create_client_message_event,
    create_system_announcement_event,
)
from .connection_manager import (
    ConnectionManager,
    ConnectionInfo,
    connection_manager,
)
from .event_publisher import (
    EventPublisher,
    event_publisher,
)
from .websocket_routes import websocket_router

__all__ = [
    # Events
    "EventType",
    "EventPriority",
    "RealtimeEvent",
    "create_notification_event",
    "create_return_status_event",
    "create_task_assigned_event",
    "create_appointment_event",
    "create_lead_event",
    "create_deadline_alert_event",
    "create_client_message_event",
    "create_system_announcement_event",
    # Connection manager
    "ConnectionManager",
    "ConnectionInfo",
    "connection_manager",
    # Event publisher
    "EventPublisher",
    "event_publisher",
    # Router
    "websocket_router",
]
