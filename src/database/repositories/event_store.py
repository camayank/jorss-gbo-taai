"""Async Event Store Implementation.

Implements IEventStore using SQLAlchemy async sessions.
Provides event sourcing capabilities for domain events.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.repositories import IEventStore
from domain.events import DomainEvent

logger = logging.getLogger(__name__)


class EventStore(IEventStore):
    """
    Async implementation of IEventStore.

    Uses SQLAlchemy async sessions with an events table.
    Provides event sourcing capabilities for complete audit trails.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize event store with a session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def append(self, stream_id: str, event: DomainEvent) -> None:
        """
        Append an event to a stream.

        Args:
            stream_id: Stream identifier (typically aggregate_type:aggregate_id).
            event: The event to append.
        """
        # Get current version for this stream
        version = await self.get_stream_version(stream_id) + 1

        query = text("""
            INSERT INTO domain_events (
                event_id, stream_id, event_type, event_version,
                aggregate_type, aggregate_id, event_data,
                occurred_at, stored_at
            ) VALUES (
                :event_id, :stream_id, :event_type, :event_version,
                :aggregate_type, :aggregate_id, :event_data,
                :occurred_at, :stored_at
            )
        """)

        # Extract aggregate info from stream_id
        parts = stream_id.split(":")
        aggregate_type = parts[0] if len(parts) > 0 else "unknown"
        aggregate_id = parts[1] if len(parts) > 1 else stream_id

        params = {
            "event_id": str(event.event_id),
            "stream_id": stream_id,
            "event_type": event.event_type,
            "event_version": version,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "event_data": json.dumps(event.to_dict()),
            "occurred_at": event.occurred_at.isoformat(),
            "stored_at": datetime.utcnow().isoformat(),
        }

        await self._session.execute(query, params)
        logger.debug(f"Appended event {event.event_type} to stream {stream_id} (v{version})")

    async def append_batch(self, stream_id: str, events: List[DomainEvent]) -> None:
        """
        Append multiple events to a stream atomically.

        Args:
            stream_id: Stream identifier.
            events: Events to append.
        """
        if not events:
            return

        # Get current version for this stream
        base_version = await self.get_stream_version(stream_id)

        # Extract aggregate info from stream_id
        parts = stream_id.split(":")
        aggregate_type = parts[0] if len(parts) > 0 else "unknown"
        aggregate_id = parts[1] if len(parts) > 1 else stream_id

        query = text("""
            INSERT INTO domain_events (
                event_id, stream_id, event_type, event_version,
                aggregate_type, aggregate_id, event_data,
                occurred_at, stored_at
            ) VALUES (
                :event_id, :stream_id, :event_type, :event_version,
                :aggregate_type, :aggregate_id, :event_data,
                :occurred_at, :stored_at
            )
        """)

        stored_at = datetime.utcnow().isoformat()

        for i, event in enumerate(events):
            version = base_version + i + 1
            params = {
                "event_id": str(event.event_id),
                "stream_id": stream_id,
                "event_type": event.event_type,
                "event_version": version,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_data": json.dumps(event.to_dict()),
                "occurred_at": event.occurred_at.isoformat(),
                "stored_at": stored_at,
            }
            await self._session.execute(query, params)

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
            stream_id: Stream identifier.
            from_version: Start version (inclusive).
            to_version: End version (inclusive), None for all.

        Returns:
            List of events in order.
        """
        if to_version is not None:
            query = text("""
                SELECT event_id, stream_id, event_type, event_version,
                       aggregate_type, aggregate_id, event_data,
                       occurred_at, stored_at
                FROM domain_events
                WHERE stream_id = :stream_id
                  AND event_version >= :from_version
                  AND event_version <= :to_version
                ORDER BY event_version ASC
            """)
            params = {
                "stream_id": stream_id,
                "from_version": from_version,
                "to_version": to_version,
            }
        else:
            query = text("""
                SELECT event_id, stream_id, event_type, event_version,
                       aggregate_type, aggregate_id, event_data,
                       occurred_at, stored_at
                FROM domain_events
                WHERE stream_id = :stream_id
                  AND event_version >= :from_version
                ORDER BY event_version ASC
            """)
            params = {
                "stream_id": stream_id,
                "from_version": from_version,
            }

        result = await self._session.execute(query, params)
        return [self._row_to_event(row) for row in result.fetchall()]

    async def get_events_by_type(
        self,
        event_type: str,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[DomainEvent]:
        """
        Get events of a specific type.

        Args:
            event_type: Type of events to get.
            since: Only events after this time.
            limit: Maximum events to return.

        Returns:
            List of matching events.
        """
        if since is not None:
            query = text("""
                SELECT event_id, stream_id, event_type, event_version,
                       aggregate_type, aggregate_id, event_data,
                       occurred_at, stored_at
                FROM domain_events
                WHERE event_type = :event_type
                  AND occurred_at > :since
                ORDER BY occurred_at ASC
                LIMIT :limit
            """)
            params = {
                "event_type": event_type,
                "since": since.isoformat(),
                "limit": limit,
            }
        else:
            query = text("""
                SELECT event_id, stream_id, event_type, event_version,
                       aggregate_type, aggregate_id, event_data,
                       occurred_at, stored_at
                FROM domain_events
                WHERE event_type = :event_type
                ORDER BY occurred_at ASC
                LIMIT :limit
            """)
            params = {
                "event_type": event_type,
                "limit": limit,
            }

        result = await self._session.execute(query, params)
        return [self._row_to_event(row) for row in result.fetchall()]

    async def get_events_by_aggregate(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        since: Optional[datetime] = None
    ) -> List[DomainEvent]:
        """
        Get all events for an aggregate.

        Args:
            aggregate_type: Type of aggregate.
            aggregate_id: Aggregate identifier.
            since: Only events after this time.

        Returns:
            List of events for the aggregate.
        """
        if since is not None:
            query = text("""
                SELECT event_id, stream_id, event_type, event_version,
                       aggregate_type, aggregate_id, event_data,
                       occurred_at, stored_at
                FROM domain_events
                WHERE aggregate_type = :aggregate_type
                  AND aggregate_id = :aggregate_id
                  AND occurred_at > :since
                ORDER BY event_version ASC
            """)
            params = {
                "aggregate_type": aggregate_type,
                "aggregate_id": str(aggregate_id),
                "since": since.isoformat(),
            }
        else:
            query = text("""
                SELECT event_id, stream_id, event_type, event_version,
                       aggregate_type, aggregate_id, event_data,
                       occurred_at, stored_at
                FROM domain_events
                WHERE aggregate_type = :aggregate_type
                  AND aggregate_id = :aggregate_id
                ORDER BY event_version ASC
            """)
            params = {
                "aggregate_type": aggregate_type,
                "aggregate_id": str(aggregate_id),
            }

        result = await self._session.execute(query, params)
        return [self._row_to_event(row) for row in result.fetchall()]

    async def get_stream_version(self, stream_id: str) -> int:
        """
        Get the current version of a stream.

        Args:
            stream_id: Stream identifier.

        Returns:
            Current version number, 0 if stream doesn't exist.
        """
        query = text("""
            SELECT COALESCE(MAX(event_version), 0)
            FROM domain_events
            WHERE stream_id = :stream_id
        """)
        result = await self._session.execute(query, {"stream_id": stream_id})
        row = result.fetchone()
        return row[0] if row else 0

    async def get_all_streams(self) -> List[str]:
        """
        Get all stream IDs.

        Returns:
            List of stream identifiers.
        """
        query = text("""
            SELECT DISTINCT stream_id
            FROM domain_events
            ORDER BY stream_id
        """)
        result = await self._session.execute(query)
        return [row[0] for row in result.fetchall()]

    def _row_to_event(self, row) -> DomainEvent:
        """Convert a database row to a DomainEvent object."""
        if row is None:
            return None

        # Parse the JSON event data
        event_data = json.loads(row[6]) if row[6] else {}

        # Create a DomainEvent from the stored data
        return DomainEvent.from_dict(event_data)
