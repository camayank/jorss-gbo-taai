"""
WebSocket Connection Manager

Manages WebSocket connections and message broadcasting.
Handles subscriptions, authentication, and event routing.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional, Any
from uuid import UUID
from dataclasses import dataclass, field
from fastapi import WebSocket, WebSocketDisconnect
import json

from .events import RealtimeEvent, EventType, EventPriority

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    websocket: WebSocket
    user_id: UUID
    firm_id: UUID
    user_email: str
    user_role: str
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Subscriptions
    subscribed_sessions: Set[str] = field(default_factory=set)
    subscribed_events: Set[str] = field(default_factory=set)

    # Stats
    messages_sent: int = 0
    messages_received: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": str(self.user_id),
            "firm_id": str(self.firm_id),
            "user_email": self.user_email,
            "user_role": self.user_role,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "subscribed_sessions": list(self.subscribed_sessions),
            "subscribed_events": list(self.subscribed_events),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
        }


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.

    Features:
    - Connection lifecycle management
    - Event routing based on subscriptions
    - Firm-scoped broadcasting
    - User-specific targeting
    - Session-based subscriptions
    - Heartbeat/keepalive
    """

    def __init__(self):
        # Active connections by user_id
        self._connections: Dict[UUID, ConnectionInfo] = {}

        # Index by firm for efficient firm-wide broadcasts
        self._firm_connections: Dict[UUID, Set[UUID]] = {}

        # Index by session for session-specific updates
        self._session_subscriptions: Dict[str, Set[UUID]] = {}

        # Broadcast lock for thread safety (created lazily)
        self._lock = None

    def _get_lock(self):
        if self._lock is None:
            import asyncio as _asyncio
            self._lock = _asyncio.Lock()
        return self._lock

    async def connect(
        self,
        websocket: WebSocket,
        user_id: UUID,
        firm_id: UUID,
        user_email: str,
        user_role: str,
    ) -> ConnectionInfo:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            user_id: User's UUID
            firm_id: User's firm UUID
            user_email: User's email
            user_role: User's role

        Returns:
            ConnectionInfo for the new connection
        """
        await websocket.accept()

        # Create connection info
        connection = ConnectionInfo(
            websocket=websocket,
            user_id=user_id,
            firm_id=firm_id,
            user_email=user_email,
            user_role=user_role,
        )

        async with self._get_lock():
            # Remove any existing connection for this user
            if user_id in self._connections:
                old_conn = self._connections[user_id]
                await self._remove_connection(old_conn)

            # Store new connection
            self._connections[user_id] = connection

            # Add to firm index
            if firm_id not in self._firm_connections:
                self._firm_connections[firm_id] = set()
            self._firm_connections[firm_id].add(user_id)

        logger.info(f"[WS] Connected: user={user_email} firm={firm_id}")

        # Send welcome message
        await self._send_to_connection(connection, RealtimeEvent(
            event_type=EventType.CONNECTED,
            user_id=user_id,
            firm_id=firm_id,
            data={
                "message": "Connected to real-time updates",
                "user_id": str(user_id),
                "firm_id": str(firm_id),
            },
        ))

        return connection

    async def disconnect(self, user_id: UUID):
        """Disconnect a user's WebSocket connection and release any held field locks."""
        # Release field locks held by this user and notify session peers
        try:
            released = await field_lock_manager.release_all_for_user(user_id)
            for session_id, field_id in released:
                from .events import create_field_unlocked_event
                connection = self._connections.get(user_id)
                firm_id = connection.firm_id if connection else None
                if firm_id:
                    event = create_field_unlocked_event(
                        session_id=session_id,
                        firm_id=firm_id,
                        field_id=field_id,
                    )
                    await self.broadcast_event(event)
        except Exception as e:
            logger.warning(f"[WS] Error releasing field locks on disconnect: {e}")

        async with self._get_lock():
            if user_id in self._connections:
                connection = self._connections[user_id]
                await self._remove_connection(connection)
                logger.info(f"[WS] Disconnected: user={connection.user_email}")

    async def _remove_connection(self, connection: ConnectionInfo):
        """Remove a connection from all indexes."""
        user_id = connection.user_id
        firm_id = connection.firm_id

        # Remove from connections
        if user_id in self._connections:
            del self._connections[user_id]

        # Remove from firm index
        if firm_id in self._firm_connections:
            self._firm_connections[firm_id].discard(user_id)
            if not self._firm_connections[firm_id]:
                del self._firm_connections[firm_id]

        # Remove from session subscriptions
        for session_id in list(connection.subscribed_sessions):
            if session_id in self._session_subscriptions:
                self._session_subscriptions[session_id].discard(user_id)
                if not self._session_subscriptions[session_id]:
                    del self._session_subscriptions[session_id]

        # Try to close websocket gracefully
        try:
            await connection.websocket.close()
        except Exception:
            pass

    async def subscribe_session(self, user_id: UUID, session_id: str):
        """Subscribe a user to updates for a specific session."""
        async with self._get_lock():
            if user_id not in self._connections:
                return

            connection = self._connections[user_id]
            connection.subscribed_sessions.add(session_id)

            if session_id not in self._session_subscriptions:
                self._session_subscriptions[session_id] = set()
            self._session_subscriptions[session_id].add(user_id)

            logger.debug(f"[WS] User {user_id} subscribed to session {session_id}")

    async def unsubscribe_session(self, user_id: UUID, session_id: str):
        """Unsubscribe a user from session updates."""
        async with self._get_lock():
            if user_id not in self._connections:
                return

            connection = self._connections[user_id]
            connection.subscribed_sessions.discard(session_id)

            if session_id in self._session_subscriptions:
                self._session_subscriptions[session_id].discard(user_id)
                if not self._session_subscriptions[session_id]:
                    del self._session_subscriptions[session_id]

    async def broadcast_event(self, event: RealtimeEvent, _via_pubsub: bool = False):
        """
        Broadcast an event to relevant connections.

        Event targeting:
        - broadcast=True: Send to all connections
        - firm_id: Send to all users in that firm
        - user_id: Send to specific user
        - session_id: Send to users subscribed to that session

        When Redis pub/sub is enabled, also publishes the event to the Redis
        channel so other worker processes can deliver it to their local clients.
        The ``_via_pubsub`` flag prevents re-publishing events that already
        arrived from Redis (avoiding infinite loops).
        """
        if event.broadcast:
            await self._broadcast_to_all(event)
        elif event.session_id:
            await self._broadcast_to_session(event)
        elif event.user_id:
            await self._send_to_user(event)
        elif event.firm_id:
            await self._broadcast_to_firm(event)

        # Cross-process: publish to Redis so other workers can deliver locally
        if not _via_pubsub:
            try:
                from .redis_pubsub import redis_broadcaster
                await redis_broadcaster.publish_event(event)
            except Exception:
                pass  # Redis unavailable — in-process delivery only

    async def _broadcast_to_all(self, event: RealtimeEvent):
        """Broadcast to all connected clients."""
        async with self._get_lock():
            connections = list(self._connections.values())

        for connection in connections:
            await self._send_to_connection(connection, event)

        logger.debug(f"[WS] Broadcast to all: {event.event_type.value} ({len(connections)} clients)")

    async def _broadcast_to_firm(self, event: RealtimeEvent):
        """Broadcast to all users in a firm."""
        async with self._get_lock():
            user_ids = self._firm_connections.get(event.firm_id, set())
            connections = [
                self._connections[uid]
                for uid in user_ids
                if uid in self._connections
            ]

        for connection in connections:
            await self._send_to_connection(connection, event)

        logger.debug(f"[WS] Broadcast to firm {event.firm_id}: {event.event_type.value} ({len(connections)} clients)")

    async def _broadcast_to_session(self, event: RealtimeEvent):
        """Broadcast to users subscribed to a session."""
        async with self._get_lock():
            user_ids = self._session_subscriptions.get(event.session_id, set())
            connections = [
                self._connections[uid]
                for uid in user_ids
                if uid in self._connections
            ]

        for connection in connections:
            await self._send_to_connection(connection, event)

        logger.debug(f"[WS] Broadcast to session {event.session_id}: {event.event_type.value} ({len(connections)} clients)")

    async def _send_to_user(self, event: RealtimeEvent):
        """Send event to a specific user."""
        async with self._get_lock():
            connection = self._connections.get(event.user_id)

        if connection:
            await self._send_to_connection(connection, event)
            logger.debug(f"[WS] Sent to user {event.user_id}: {event.event_type.value}")

    async def _send_to_connection(self, connection: ConnectionInfo, event: RealtimeEvent):
        """Send event to a specific connection."""
        try:
            await connection.websocket.send_json(event.to_dict())
            connection.messages_sent += 1
            connection.last_activity = datetime.now(timezone.utc)
        except Exception as e:
            logger.warning(f"[WS] Failed to send to {connection.user_email}: {e}")
            # Don't remove here - let the disconnect handler clean up

    async def handle_message(self, user_id: UUID, message: Dict[str, Any]):
        """
        Handle an incoming message from a client.

        Supported message types:
        - subscribe: Subscribe to a session
        - unsubscribe: Unsubscribe from a session
        - heartbeat: Keepalive ping
        - field_lock: Acquire exclusive edit lock on a form field
        - field_unlock: Release edit lock on a form field
        - presence_update: Update cursor / active field position
        """
        msg_type = message.get("type", "")

        if msg_type == "subscribe":
            session_id = message.get("session_id")
            if session_id:
                await self.subscribe_session(user_id, session_id)

        elif msg_type == "unsubscribe":
            session_id = message.get("session_id")
            if session_id:
                await self.unsubscribe_session(user_id, session_id)

        elif msg_type == "heartbeat":
            # Update last activity and respond
            async with self._get_lock():
                if user_id in self._connections:
                    connection = self._connections[user_id]
                    connection.last_activity = datetime.now(timezone.utc)
                    connection.messages_received += 1

                    await self._send_to_connection(connection, RealtimeEvent(
                        event_type=EventType.HEARTBEAT,
                        user_id=user_id,
                        data={"timestamp": datetime.now(timezone.utc).isoformat()},
                    ))

        elif msg_type == "field_lock":
            await self._handle_field_lock(user_id, message)

        elif msg_type == "field_unlock":
            await self._handle_field_unlock(user_id, message)

        elif msg_type == "presence_update":
            await self._handle_presence_update(user_id, message)

    async def _handle_field_lock(self, user_id: UUID, message: Dict[str, Any]):
        """Handle a request to lock a form field for exclusive editing."""
        from .events import create_field_locked_event

        session_id = message.get("session_id", "")
        field_id = message.get("field_id", "")
        user_name = message.get("user_name", str(user_id))

        if not session_id or not field_id:
            return

        lock = await field_lock_manager.acquire(session_id, field_id, user_id, user_name)

        conn = self._connections.get(user_id)
        if conn is None:
            return

        if lock.user_id == user_id:
            # Lock granted — broadcast to session peers
            event = create_field_locked_event(
                session_id=session_id,
                firm_id=conn.firm_id,
                field_id=field_id,
                locked_by_user_id=str(user_id),
                locked_by_name=user_name,
            )
            await self.broadcast_event(event)
        else:
            # Lock denied — notify requesting user only
            await self._send_to_connection(conn, RealtimeEvent(
                event_type=EventType.FIELD_LOCKED,
                user_id=user_id,
                firm_id=conn.firm_id,
                session_id=session_id,
                data={
                    "field_id": field_id,
                    "locked_by_user_id": str(lock.user_id),
                    "locked_by_name": lock.user_name,
                    "denied": True,
                },
            ))

    async def _handle_field_unlock(self, user_id: UUID, message: Dict[str, Any]):
        """Handle a request to release a field lock."""
        from .events import create_field_unlocked_event

        session_id = message.get("session_id", "")
        field_id = message.get("field_id", "")

        if not session_id or not field_id:
            return

        released = await field_lock_manager.release(session_id, field_id, user_id)
        if not released:
            return

        conn = self._connections.get(user_id)
        if conn is None:
            return

        event = create_field_unlocked_event(
            session_id=session_id,
            firm_id=conn.firm_id,
            field_id=field_id,
        )
        await self.broadcast_event(event)

    async def _handle_presence_update(self, user_id: UUID, message: Dict[str, Any]):
        """Handle a presence/cursor update from a user."""
        from .events import create_presence_update_event

        session_id = message.get("session_id", "")
        active_field = message.get("active_field")
        user_name = message.get("user_name", str(user_id))
        color = message.get("color")

        if not session_id:
            return

        conn = self._connections.get(user_id)
        if conn is None:
            return

        event = create_presence_update_event(
            session_id=session_id,
            firm_id=conn.firm_id,
            user_id=user_id,
            user_name=user_name,
            user_role=conn.user_role,
            active_field=active_field,
            color=color,
        )
        await self.broadcast_event(event)

    def get_connection_info(self, user_id: UUID) -> Optional[ConnectionInfo]:
        """Get connection info for a user."""
        return self._connections.get(user_id)

    def get_firm_connections(self, firm_id: UUID) -> List[ConnectionInfo]:
        """Get all connections for a firm."""
        user_ids = self._firm_connections.get(firm_id, set())
        return [
            self._connections[uid]
            for uid in user_ids
            if uid in self._connections
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        total_connections = len(self._connections)
        firms_with_connections = len(self._firm_connections)
        active_sessions = len(self._session_subscriptions)

        return {
            "total_connections": total_connections,
            "firms_with_connections": firms_with_connections,
            "active_session_subscriptions": active_sessions,
            "connections_by_firm": {
                str(firm_id): len(users)
                for firm_id, users in self._firm_connections.items()
            },
        }

    async def cleanup_stale_connections(self, max_idle_seconds: int = 300):
        """
        Clean up stale connections.

        Connections with no activity for max_idle_seconds are closed.
        """
        now = datetime.now(timezone.utc)
        stale_user_ids = []

        async with self._get_lock():
            for user_id, connection in self._connections.items():
                idle_seconds = (now - connection.last_activity).total_seconds()
                if idle_seconds > max_idle_seconds:
                    stale_user_ids.append(user_id)

        for user_id in stale_user_ids:
            await self.disconnect(user_id)
            logger.info(f"[WS] Cleaned up stale connection for user {user_id}")

        return len(stale_user_ids)


# Singleton instance
connection_manager = ConnectionManager()


@dataclass
class FieldLock:
    """Tracks who currently holds a field lock for co-editing."""
    field_id: str
    session_id: str
    user_id: UUID
    user_name: str
    locked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FieldLockManager:
    """
    In-memory field lock tracker for co-editing.

    Tracks which user holds the edit lock for each (session, field) pair.
    For multi-process deployments, locks are also mirrored in Redis via the
    connection_manager's pub/sub broadcaster.
    """

    def __init__(self):
        # key: (session_id, field_id) -> FieldLock
        self._locks: Dict[tuple, FieldLock] = {}
        self._lock = None

    def _get_lock(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(
        self,
        session_id: str,
        field_id: str,
        user_id: UUID,
        user_name: str,
    ) -> Optional[FieldLock]:
        """
        Try to acquire a field lock.

        Returns the lock if acquired, or the existing lock held by another user.
        """
        key = (session_id, field_id)
        async with self._get_lock():
            existing = self._locks.get(key)
            if existing and existing.user_id != user_id:
                return existing  # locked by someone else
            lock = FieldLock(
                field_id=field_id,
                session_id=session_id,
                user_id=user_id,
                user_name=user_name,
            )
            self._locks[key] = lock
            return lock

    async def release(self, session_id: str, field_id: str, user_id: UUID) -> bool:
        """Release a field lock. Only the lock holder can release."""
        key = (session_id, field_id)
        async with self._get_lock():
            existing = self._locks.get(key)
            if existing and existing.user_id == user_id:
                del self._locks[key]
                return True
            return False

    async def release_all_for_user(self, user_id: UUID) -> List[tuple]:
        """Release all locks held by a user (on disconnect). Returns released keys."""
        released = []
        async with self._get_lock():
            keys_to_remove = [
                k for k, v in self._locks.items() if v.user_id == user_id
            ]
            for k in keys_to_remove:
                del self._locks[k]
                released.append(k)
        return released

    def get_session_locks(self, session_id: str) -> List[FieldLock]:
        """Get all active locks for a session."""
        return [v for k, v in self._locks.items() if k[0] == session_id]

    def is_locked_by(self, session_id: str, field_id: str, user_id: UUID) -> bool:
        """Check if the given user holds the lock."""
        lock = self._locks.get((session_id, field_id))
        return lock is not None and lock.user_id == user_id


# Singleton field lock manager
field_lock_manager = FieldLockManager()
