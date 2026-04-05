"""
Redis Pub/Sub for WebSocket cross-process broadcasting.

When the app runs across multiple worker processes (uvicorn with --workers > 1),
in-memory connection tracking means a message published in process A won't reach
WebSocket clients connected to process B.

This module bridges that gap:
- Publishers push events to a Redis channel.
- Each process runs a subscriber loop that receives events and forwards them
  to locally connected WebSocket clients via the ConnectionManager.

Channel naming:
  ws:firm:<firm_id>      — events targeted at a whole firm
  ws:user:<user_id>      — events targeted at a specific user
  ws:session:<session_id> — events targeted at a session subscription
  ws:broadcast           — events for all connected clients
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Channel prefix constants
_CHANNEL_BROADCAST = "ws:broadcast"
_CHANNEL_FIRM_PREFIX = "ws:firm:"
_CHANNEL_USER_PREFIX = "ws:user:"
_CHANNEL_SESSION_PREFIX = "ws:session:"


def _firm_channel(firm_id: str) -> str:
    return f"{_CHANNEL_FIRM_PREFIX}{firm_id}"


def _user_channel(user_id: str) -> str:
    return f"{_CHANNEL_USER_PREFIX}{user_id}"


def _session_channel(session_id: str) -> str:
    return f"{_CHANNEL_SESSION_PREFIX}{session_id}"


class RedisPubSubBroadcaster:
    """
    Manages Redis pub/sub for real-time cross-process WebSocket broadcasting.

    Usage:
        broadcaster = RedisPubSubBroadcaster(connection_manager)
        await broadcaster.start()    # begin subscriber loop (call once at startup)
        await broadcaster.publish_event(event)
        await broadcaster.stop()
    """

    def __init__(self, connection_manager: "ConnectionManager"):  # noqa: F821
        self._manager = connection_manager
        self._redis_client: Optional[object] = None
        self._pubsub: Optional[object] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the Redis pub/sub subscriber loop."""
        try:
            import redis.asyncio as aioredis
        except ImportError:
            logger.warning("[PubSub] redis package not available; cross-process broadcasting disabled")
            return

        try:
            from config.settings import get_settings
            settings = get_settings()
            redis_url = settings.redis.url
        except Exception:
            redis_url = "redis://localhost:6379/0"

        try:
            self._redis_client = aioredis.from_url(redis_url, decode_responses=True)
            self._pubsub = self._redis_client.pubsub()

            # Subscribe to all ws:* channels using pattern
            await self._pubsub.psubscribe("ws:*")
            self._running = True
            self._task = asyncio.create_task(self._subscriber_loop())
            logger.info("[PubSub] Redis pub/sub broadcaster started")
        except Exception as e:
            logger.warning(f"[PubSub] Failed to start Redis subscriber: {e}")

    async def stop(self) -> None:
        """Stop the subscriber loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            try:
                await self._pubsub.punsubscribe("ws:*")
                await self._pubsub.close()
            except Exception:
                pass
        if self._redis_client:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass
        logger.info("[PubSub] Redis pub/sub broadcaster stopped")

    async def _subscriber_loop(self) -> None:
        """Listen for published messages and deliver to local connections."""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message.get("type") == "pmessage":
                    await self._handle_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.warning(f"[PubSub] Subscriber loop error: {e}")
                    await asyncio.sleep(1.0)

    async def _handle_message(self, message: dict) -> None:
        """Dispatch a Redis pub/sub message to local WebSocket connections."""
        try:
            channel: str = message.get("channel", "")
            raw: str = message.get("data", "{}")
            payload = json.loads(raw)

            from .events import RealtimeEvent
            event = RealtimeEvent.from_dict(payload)

            if channel == _CHANNEL_BROADCAST:
                await self._manager._broadcast_to_all(event)
            elif channel.startswith(_CHANNEL_FIRM_PREFIX):
                await self._manager._broadcast_to_firm(event)
            elif channel.startswith(_CHANNEL_USER_PREFIX):
                await self._manager._send_to_user(event)
            elif channel.startswith(_CHANNEL_SESSION_PREFIX):
                await self._manager._broadcast_to_session(event)
        except Exception as e:
            logger.warning(f"[PubSub] Failed to handle message: {e}")

    async def publish_event(self, event: "RealtimeEvent") -> None:  # noqa: F821
        """
        Publish an event to the appropriate Redis channel.

        Falls back silently if Redis is not available (in-process delivery only).
        """
        if not self._redis_client:
            return

        try:
            payload = json.dumps(event.to_dict())

            if event.broadcast:
                await self._redis_client.publish(_CHANNEL_BROADCAST, payload)
            elif event.session_id:
                await self._redis_client.publish(_session_channel(event.session_id), payload)
            elif event.user_id:
                await self._redis_client.publish(_user_channel(str(event.user_id)), payload)
            elif event.firm_id:
                await self._redis_client.publish(_firm_channel(str(event.firm_id)), payload)
        except Exception as e:
            logger.warning(f"[PubSub] Publish failed: {e}")


# Lazy singleton — initialized at startup via start_redis_broadcaster()
redis_broadcaster: Optional[RedisPubSubBroadcaster] = None


async def start_redis_broadcaster(connection_manager: "RedisPubSubBroadcaster") -> None:  # noqa: F821
    """Create and start the global Redis broadcaster. Call once at app startup."""
    global redis_broadcaster
    if redis_broadcaster is None:
        from .connection_manager import connection_manager as _cm
        redis_broadcaster = RedisPubSubBroadcaster(_cm)
        await redis_broadcaster.start()


async def stop_redis_broadcaster() -> None:
    """Stop the global Redis broadcaster. Call at app shutdown."""
    global redis_broadcaster
    if redis_broadcaster is not None:
        await redis_broadcaster.stop()
        redis_broadcaster = None
