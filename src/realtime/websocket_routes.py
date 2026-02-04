"""
WebSocket Routes

FastAPI WebSocket endpoints for real-time updates.
"""

import logging
import os
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from fastapi.responses import JSONResponse
import json

from .connection_manager import connection_manager
from .events import (
    RealtimeEvent,
    EventType,
    create_notification_event,
    create_system_announcement_event,
)

logger = logging.getLogger(__name__)

websocket_router = APIRouter(prefix="/ws", tags=["WebSocket"])


async def verify_websocket_token(token: str) -> Optional[dict]:
    """
    Verify a WebSocket authentication token via JWT.

    Uses the rbac.jwt module for proper JWT verification.
    Falls back to simple token format only in development.
    Returns user info if valid, None otherwise.
    """
    # Try JWT verification first (production path)
    try:
        from rbac.jwt import decode_token
        payload = decode_token(token)
        return {
            "user_id": UUID(str(payload.get("sub", payload.get("user_id", "")))),
            "firm_id": UUID(str(payload.get("firm_id", payload.get("tenant_id", "")))),
            "email": payload.get("email", ""),
            "role": payload.get("role", "user"),
        }
    except ImportError:
        logger.warning("rbac.jwt module not available, JWT verification disabled")
    except Exception as e:
        # Token failed JWT validation — in dev, fall through to simple format
        is_dev = os.environ.get("ENVIRONMENT", "").lower() in ("development", "dev", "test")
        if not is_dev:
            logger.warning(f"WebSocket JWT verification failed: {e}")
            return None
        logger.debug(f"JWT decode failed in dev mode, trying simple format: {e}")

    # Dev-only fallback: simple token format user_id:firm_id:email:role
    # SECURITY: Only enabled when ENVIRONMENT is explicitly set to a dev value
    is_dev = os.environ.get("ENVIRONMENT", "").lower() in ("development", "dev", "test")
    if not is_dev:
        return None

    try:
        parts = token.split(":")
        if len(parts) >= 4:
            return {
                "user_id": UUID(parts[0]),
                "firm_id": UUID(parts[1]),
                "email": parts[2],
                "role": parts[3],
            }
    except Exception as e:
        logger.warning(f"Invalid WebSocket token (dev fallback): {e}")

    return None


@websocket_router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token"),
):
    """
    Main WebSocket endpoint for real-time updates.

    Connect with: ws://host/ws?token=<auth_token>

    Message format (incoming):
    - {"type": "subscribe", "session_id": "..."}
    - {"type": "unsubscribe", "session_id": "..."}
    - {"type": "heartbeat"}

    Event format (outgoing):
    - {"id": "...", "type": "notification", "data": {...}, "timestamp": "..."}
    """
    # Verify token
    user_info = await verify_websocket_token(token)
    if not user_info:
        await websocket.close(code=4001, reason="Invalid authentication token")
        return

    user_id = user_info["user_id"]
    firm_id = user_info["firm_id"]
    email = user_info["email"]
    role = user_info["role"]

    # Connect
    try:
        connection = await connection_manager.connect(
            websocket=websocket,
            user_id=user_id,
            firm_id=firm_id,
            user_email=email,
            user_role=role,
        )

        # Listen for messages
        while True:
            try:
                data = await websocket.receive_json()
                await connection_manager.handle_message(user_id, data)
            except json.JSONDecodeError:
                # Ignore malformed messages
                continue

    except WebSocketDisconnect:
        await connection_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {email}: {e}")
        await connection_manager.disconnect(user_id)


# =============================================================================
# HTTP ENDPOINTS FOR SENDING EVENTS
# =============================================================================

@websocket_router.post("/broadcast")
async def broadcast_event(
    event_type: str = Query(..., description="Event type"),
    title: str = Query(..., description="Event title"),
    message: str = Query(..., description="Event message"),
    firm_id: Optional[str] = Query(None, description="Target firm (optional, broadcasts to all if not specified)"),
    user_id: Optional[str] = Query(None, description="Target user (optional)"),
    priority: str = Query("normal", description="Event priority: low, normal, high, urgent"),
):
    """
    Broadcast an event to connected clients.

    This endpoint can be called by internal services to push
    real-time updates to connected users.
    """
    from .events import EventPriority

    try:
        priority_enum = EventPriority(priority)
    except ValueError:
        priority_enum = EventPriority.NORMAL

    event = RealtimeEvent(
        event_type=EventType(event_type) if event_type in [e.value for e in EventType] else EventType.NOTIFICATION,
        priority=priority_enum,
        firm_id=UUID(firm_id) if firm_id else None,
        user_id=UUID(user_id) if user_id else None,
        broadcast=not firm_id and not user_id,
        data={
            "title": title,
            "message": message,
        },
    )

    await connection_manager.broadcast_event(event)

    return {
        "success": True,
        "event_id": str(event.id),
        "recipients": connection_manager.get_stats()["total_connections"],
    }


@websocket_router.post("/notify/{user_id}")
async def send_notification(
    user_id: str,
    title: str = Query(..., description="Notification title"),
    message: str = Query(..., description="Notification message"),
    notification_type: str = Query("info", description="Type: info, success, warning, error"),
    link: Optional[str] = Query(None, description="Optional link"),
):
    """Send a notification to a specific user."""
    # Get user's firm from connection (if connected)
    connection = connection_manager.get_connection_info(UUID(user_id))
    firm_id = connection.firm_id if connection else None

    event = create_notification_event(
        user_id=UUID(user_id),
        firm_id=firm_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
    )

    await connection_manager.broadcast_event(event)

    return {
        "success": True,
        "event_id": str(event.id),
        "delivered": connection is not None,
    }


@websocket_router.post("/announce")
async def system_announcement(
    title: str = Query(..., description="Announcement title"),
    message: str = Query(..., description="Announcement message"),
    severity: str = Query("info", description="Severity: info, warning, critical"),
):
    """
    Send a system-wide announcement.

    Broadcasts to all connected clients.
    """
    event = create_system_announcement_event(
        title=title,
        message=message,
        severity=severity,
    )

    await connection_manager.broadcast_event(event)

    stats = connection_manager.get_stats()

    return {
        "success": True,
        "event_id": str(event.id),
        "recipients": stats["total_connections"],
        "firms_reached": stats["firms_with_connections"],
    }


@websocket_router.get("/connections")
async def get_connections():
    """Get current WebSocket connection statistics."""
    stats = connection_manager.get_stats()
    return {
        "success": True,
        **stats,
    }


@websocket_router.get("/connections/{firm_id}")
async def get_firm_connections(firm_id: str):
    """Get connections for a specific firm."""
    connections = connection_manager.get_firm_connections(UUID(firm_id))
    return {
        "success": True,
        "firm_id": firm_id,
        "connections": [c.to_dict() for c in connections],
        "total": len(connections),
    }


@websocket_router.post("/cleanup")
async def cleanup_stale_connections(
    max_idle_seconds: int = Query(300, description="Max idle time in seconds"),
):
    """Clean up stale WebSocket connections."""
    cleaned = await connection_manager.cleanup_stale_connections(max_idle_seconds)
    return {
        "success": True,
        "cleaned_connections": cleaned,
    }
