"""
Event Bus and Event Store implementations.

The event bus provides in-process event publication and subscription.
The event store provides persistent storage for domain events.
"""

import json
import sqlite3
import logging
from datetime import datetime
from typing import Callable, Dict, List, Type, Optional, Any
from uuid import UUID
from pathlib import Path
import asyncio

from .events import DomainEvent, EventType
from .repositories import IEventStore


# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# EVENT BUS
# =============================================================================

class EventBus:
    """
    Simple in-process event bus for publishing domain events.

    Supports both sync and async event handlers.
    Events are delivered to all registered handlers for their type.
    """

    def __init__(self):
        """Initialize event bus."""
        self._handlers: Dict[Type[DomainEvent], List[Callable]] = {}
        self._async_handlers: Dict[Type[DomainEvent], List[Callable]] = {}
        self._global_handlers: List[Callable] = []
        self._async_global_handlers: List[Callable] = []

    def subscribe(
        self,
        event_type: Type[DomainEvent],
        handler: Callable[[DomainEvent], None]
    ) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Type of event to subscribe to
            handler: Callback function to invoke
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type.__name__}")

    def subscribe_async(
        self,
        event_type: Type[DomainEvent],
        handler: Callable[[DomainEvent], Any]
    ) -> None:
        """
        Subscribe an async handler to events of a specific type.

        Args:
            event_type: Type of event to subscribe to
            handler: Async callback function to invoke
        """
        if event_type not in self._async_handlers:
            self._async_handlers[event_type] = []
        self._async_handlers[event_type].append(handler)
        logger.debug(f"Subscribed async handler to {event_type.__name__}")

    def subscribe_all(self, handler: Callable[[DomainEvent], None]) -> None:
        """
        Subscribe to all events.

        Args:
            handler: Callback function to invoke for all events
        """
        self._global_handlers.append(handler)
        logger.debug("Subscribed global handler")

    def subscribe_all_async(self, handler: Callable[[DomainEvent], Any]) -> None:
        """
        Subscribe an async handler to all events.

        Args:
            handler: Async callback function to invoke for all events
        """
        self._async_global_handlers.append(handler)
        logger.debug("Subscribed async global handler")

    def unsubscribe(
        self,
        event_type: Type[DomainEvent],
        handler: Callable
    ) -> bool:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: Type of event
            handler: Handler to remove

        Returns:
            True if handler was removed
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                return True
            except ValueError:
                pass

        if event_type in self._async_handlers:
            try:
                self._async_handlers[event_type].remove(handler)
                return True
            except ValueError:
                pass

        return False

    def publish(self, event: DomainEvent) -> None:
        """
        Publish an event synchronously.

        Args:
            event: Event to publish
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, []) + self._global_handlers

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}", exc_info=True)

    async def publish_async(self, event: DomainEvent) -> None:
        """
        Publish an event asynchronously.

        Args:
            event: Event to publish
        """
        event_type = type(event)

        # Run sync handlers
        sync_handlers = self._handlers.get(event_type, []) + self._global_handlers
        for handler in sync_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in sync event handler: {e}", exc_info=True)

        # Run async handlers
        async_handlers = self._async_handlers.get(event_type, []) + self._async_global_handlers
        if async_handlers:
            await asyncio.gather(
                *[self._safe_async_call(handler, event) for handler in async_handlers],
                return_exceptions=True
            )

    async def _safe_async_call(self, handler: Callable, event: DomainEvent) -> None:
        """Safely call an async handler."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Error in async event handler: {e}", exc_info=True)

    def clear(self) -> None:
        """Clear all subscriptions."""
        self._handlers.clear()
        self._async_handlers.clear()
        self._global_handlers.clear()
        self._async_global_handlers.clear()


# =============================================================================
# EVENT STORE IMPLEMENTATION
# =============================================================================

class SQLiteEventStore(IEventStore):
    """
    SQLite-based event store implementation.

    Provides persistent storage for domain events with:
    - Event streaming by aggregate
    - Event querying by type and time
    - Version tracking for optimistic concurrency
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize event store.

        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"
        self.db_path = db_path
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Ensure the events table exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    stream_id TEXT NOT NULL,
                    stream_type TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data JSON NOT NULL,
                    metadata JSON,
                    version INTEGER NOT NULL,
                    occurred_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_stream ON events(stream_id, version)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events(occurred_at)"
            )
            conn.commit()

    def _serialize_event(self, event: DomainEvent) -> Dict[str, Any]:
        """Serialize event to storable format."""
        # Convert to dict, handling special types
        data = event.model_dump()

        # Convert UUIDs to strings
        for key, value in data.items():
            if isinstance(value, UUID):
                data[key] = str(value)
            elif isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, list):
                data[key] = [
                    str(v) if isinstance(v, UUID) else v
                    for v in value
                ]

        return data

    def _deserialize_event(self, row: tuple) -> DomainEvent:
        """Deserialize event from stored format."""
        event_id, stream_id, stream_type, event_type, event_data, metadata, version, occurred_at, created_at = row

        data = json.loads(event_data)
        meta = json.loads(metadata) if metadata else {}

        # Import the specific event class
        from . import events as events_module

        # Find the event class by type
        event_type_enum = EventType(event_type)
        event_class = None

        for name, cls in vars(events_module).items():
            if isinstance(cls, type) and issubclass(cls, DomainEvent) and cls != DomainEvent:
                try:
                    if hasattr(cls, 'model_fields') and 'event_type' in cls.model_fields:
                        default = cls.model_fields['event_type'].default
                        if default == event_type_enum:
                            event_class = cls
                            break
                except (AttributeError, KeyError, TypeError):
                    pass

        if event_class is None:
            # Return base DomainEvent if specific class not found
            return DomainEvent(
                event_id=UUID(event_id),
                event_type=event_type_enum,
                occurred_at=datetime.fromisoformat(occurred_at),
                metadata=meta,
                aggregate_id=UUID(data.get('aggregate_id')) if data.get('aggregate_id') else None,
                aggregate_type=data.get('aggregate_type'),
            )

        return event_class(**data)

    async def append(self, stream_id: str, event: DomainEvent) -> None:
        """
        Append an event to a stream.

        Args:
            stream_id: Stream identifier
            event: Event to append
        """
        version = await self.get_stream_version(stream_id) + 1
        event_data = self._serialize_event(event)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (
                    event_id, stream_id, stream_type, event_type,
                    event_data, metadata, version, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(event.event_id),
                stream_id,
                event.aggregate_type or "unknown",
                event.event_type.value,
                json.dumps(event_data),
                json.dumps(event.metadata),
                version,
                event.occurred_at.isoformat()
            ))
            conn.commit()

        logger.debug(f"Appended event {event.event_type.value} to stream {stream_id}")

    async def append_batch(self, stream_id: str, events: List[DomainEvent]) -> None:
        """
        Append multiple events to a stream atomically.

        Args:
            stream_id: Stream identifier
            events: Events to append
        """
        if not events:
            return

        version = await self.get_stream_version(stream_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for event in events:
                version += 1
                event_data = self._serialize_event(event)

                cursor.execute("""
                    INSERT INTO events (
                        event_id, stream_id, stream_type, event_type,
                        event_data, metadata, version, occurred_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(event.event_id),
                    stream_id,
                    event.aggregate_type or "unknown",
                    event.event_type.value,
                    json.dumps(event_data),
                    json.dumps(event.metadata),
                    version,
                    event.occurred_at.isoformat()
                ))

            conn.commit()

        logger.debug(f"Appended {len(events)} events to stream {stream_id}")

    async def get_events(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: Optional[int] = None
    ) -> List[DomainEvent]:
        """
        Get events from a stream.

        Args:
            stream_id: Stream identifier
            from_version: Start version (inclusive)
            to_version: End version (inclusive)

        Returns:
            List of events in order
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if to_version is not None:
                cursor.execute("""
                    SELECT event_id, stream_id, stream_type, event_type,
                           event_data, metadata, version, occurred_at, created_at
                    FROM events
                    WHERE stream_id = ? AND version >= ? AND version <= ?
                    ORDER BY version
                """, (stream_id, from_version, to_version))
            else:
                cursor.execute("""
                    SELECT event_id, stream_id, stream_type, event_type,
                           event_data, metadata, version, occurred_at, created_at
                    FROM events
                    WHERE stream_id = ? AND version >= ?
                    ORDER BY version
                """, (stream_id, from_version))

            return [self._deserialize_event(row) for row in cursor.fetchall()]

    async def get_events_by_type(
        self,
        event_type: str,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[DomainEvent]:
        """
        Get events of a specific type.

        Args:
            event_type: Type of events to get
            since: Only events after this time
            limit: Maximum events to return

        Returns:
            List of matching events
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if since:
                cursor.execute("""
                    SELECT event_id, stream_id, stream_type, event_type,
                           event_data, metadata, version, occurred_at, created_at
                    FROM events
                    WHERE event_type = ? AND occurred_at > ?
                    ORDER BY occurred_at DESC
                    LIMIT ?
                """, (event_type, since.isoformat(), limit))
            else:
                cursor.execute("""
                    SELECT event_id, stream_id, stream_type, event_type,
                           event_data, metadata, version, occurred_at, created_at
                    FROM events
                    WHERE event_type = ?
                    ORDER BY occurred_at DESC
                    LIMIT ?
                """, (event_type, limit))

            return [self._deserialize_event(row) for row in cursor.fetchall()]

    async def get_events_by_aggregate(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        since: Optional[datetime] = None
    ) -> List[DomainEvent]:
        """
        Get all events for an aggregate.

        Args:
            aggregate_type: Type of aggregate
            aggregate_id: Aggregate identifier
            since: Only events after this time

        Returns:
            List of events for the aggregate
        """
        stream_id = f"{aggregate_type}:{aggregate_id}"
        events = await self.get_events(stream_id)

        if since:
            events = [e for e in events if e.occurred_at > since]

        return events

    async def get_stream_version(self, stream_id: str) -> int:
        """
        Get the current version of a stream.

        Args:
            stream_id: Stream identifier

        Returns:
            Current version number, 0 if stream doesn't exist
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MAX(version) FROM events WHERE stream_id = ?",
                (stream_id,)
            )
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0

    async def get_all_streams(self) -> List[str]:
        """
        Get all stream IDs.

        Returns:
            List of stream identifiers
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT stream_id FROM events ORDER BY stream_id")
            return [row[0] for row in cursor.fetchall()]


# =============================================================================
# AUDIT EVENT HANDLER
# =============================================================================

class AuditEventHandler:
    """
    Event handler that persists all events to the event store.

    Provides automatic audit trail for all domain events.
    """

    def __init__(self, event_store: IEventStore):
        """
        Initialize audit handler.

        Args:
            event_store: Event store to persist to
        """
        self._store = event_store

    async def handle(self, event: DomainEvent) -> None:
        """
        Handle an event by persisting it.

        Args:
            event: Event to persist
        """
        if event.aggregate_type and event.aggregate_id:
            stream_id = f"{event.aggregate_type}:{event.aggregate_id}"
        else:
            stream_id = f"global:{event.event_type.value}"

        await self._store.append(stream_id, event)


class LoggingEventHandler:
    """
    Event handler that logs all events.

    Provides observability for domain events.
    """

    def __init__(self, logger_name: str = "domain.events"):
        """
        Initialize logging handler.

        Args:
            logger_name: Name for the logger
        """
        self._logger = logging.getLogger(logger_name)

    def handle(self, event: DomainEvent) -> None:
        """
        Handle an event by logging it.

        Args:
            event: Event to log
        """
        self._logger.info(
            f"Event: {event.event_type.value}",
            extra={
                "event_id": str(event.event_id),
                "event_type": event.event_type.value,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": str(event.aggregate_id) if event.aggregate_id else None,
                "occurred_at": event.occurred_at.isoformat(),
            }
        )


# =============================================================================
# GLOBAL EVENT BUS INSTANCE
# =============================================================================

# Global event bus for convenience
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def publish_event(event: DomainEvent) -> None:
    """Publish an event to the global event bus."""
    get_event_bus().publish(event)


async def publish_event_async(event: DomainEvent) -> None:
    """Publish an event to the global event bus asynchronously."""
    await get_event_bus().publish_async(event)
