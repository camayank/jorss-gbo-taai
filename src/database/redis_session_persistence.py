"""
Redis-based Session Persistence for Tax Platform.

Provides high-performance session storage using Redis with:
- Automatic TTL-based expiration (no cleanup required)
- Tenant isolation via key naming conventions
- JSON serialization for all session data
- Index sets for efficient user/tenant queries

Key naming conventions:
- session:{tenant_id}:{session_id} - Main session data
- sessions:tenant:{tenant_id} - Set of session IDs per tenant
- sessions:user:{user_id} - Set of session IDs per user
- return_status:{session_id} - Return approval workflow status
"""

from __future__ import annotations

import base64
import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Default session TTL (24 hours)
DEFAULT_SESSION_TTL_SECONDS = 86400


@dataclass
class RedisSessionRecord:
    """Session record structure for Redis storage."""
    session_id: str
    tenant_id: str
    session_type: str
    created_at: str
    last_activity: str
    expires_at: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    user_id: Optional[str] = None
    is_anonymous: bool = True
    workflow_type: Optional[str] = None
    return_id: Optional[str] = None
    agent_state_base64: Optional[str] = None  # Pickled state as base64

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedisSessionRecord":
        return cls(**data)


class RedisSessionPersistence:
    """
    Redis-based session persistence implementation.

    Uses Redis for fast session storage with automatic expiration.
    Maintains index sets for efficient queries by tenant/user.

    Usage:
        persistence = RedisSessionPersistence(redis_client)
        await persistence.save_session(session_id, tenant_id, data)
        data = await persistence.load_session(session_id, tenant_id)
    """

    def __init__(self, redis_client, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS):
        """
        Initialize Redis session persistence.

        Args:
            redis_client: Async Redis client instance
            ttl_seconds: Default session TTL in seconds
        """
        self._redis = redis_client
        self._ttl = ttl_seconds

    def _session_key(self, tenant_id: str, session_id: str) -> str:
        """Generate session key with tenant isolation."""
        return f"session:{tenant_id}:{session_id}"

    def _tenant_sessions_key(self, tenant_id: str) -> str:
        """Generate tenant sessions index key."""
        return f"sessions:tenant:{tenant_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        """Generate user sessions index key."""
        return f"sessions:user:{user_id}"

    def _status_key(self, session_id: str) -> str:
        """Generate return status key."""
        return f"return_status:{session_id}"

    async def save_session(
        self,
        session_id: str,
        tenant_id: str,
        data: Dict[str, Any],
        session_type: str = "unified_filing",
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Save or update a session.

        Args:
            session_id: Unique session identifier
            tenant_id: Tenant ID for isolation
            data: Session data to store
            session_type: Type of session
            user_id: Optional user ID
            metadata: Optional metadata
            ttl_seconds: Override default TTL

        Returns:
            True if saved successfully
        """
        try:
            now = datetime.utcnow()
            ttl = ttl_seconds or self._ttl

            # Check if session exists to preserve created_at
            existing = await self.load_session(session_id, tenant_id)
            created_at = existing.get("created_at", now.isoformat()) if existing else now.isoformat()

            record = RedisSessionRecord(
                session_id=session_id,
                tenant_id=tenant_id,
                session_type=session_type,
                created_at=created_at,
                last_activity=now.isoformat(),
                expires_at=(now + timedelta(seconds=ttl)).isoformat(),
                data=data,
                metadata=metadata or {},
                user_id=user_id,
                is_anonymous=user_id is None,
            )

            # Store session data
            key = self._session_key(tenant_id, session_id)
            success = await self._redis.set(key, record.to_dict(), ttl=ttl)

            if success:
                # Add to tenant sessions index
                tenant_key = self._tenant_sessions_key(tenant_id)
                await self._redis._client.sadd(tenant_key, session_id)
                await self._redis._client.expire(tenant_key, ttl * 2)  # Keep index longer

                # Add to user sessions index if user is authenticated
                if user_id:
                    user_key = self._user_sessions_key(user_id)
                    await self._redis._client.sadd(user_key, session_id)
                    await self._redis._client.expire(user_key, ttl * 2)

                logger.debug(f"Saved session {session_id} for tenant {tenant_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
            return False

    async def load_session(
        self,
        session_id: str,
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Load a session by ID.

        Args:
            session_id: Session identifier
            tenant_id: Tenant ID for isolation

        Returns:
            Session data dict or None if not found/expired
        """
        try:
            key = self._session_key(tenant_id, session_id)
            data = await self._redis.get(key)

            if not data:
                return None

            # Touch session to extend TTL
            await self._redis.expire(key, self._ttl)

            # Update last activity
            if isinstance(data, dict):
                data["last_activity"] = datetime.utcnow().isoformat()

            return data

        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    async def delete_session(
        self,
        session_id: str,
        tenant_id: str,
    ) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session identifier
            tenant_id: Tenant ID

        Returns:
            True if deleted successfully
        """
        try:
            # Get session to find user_id for index cleanup
            session = await self.load_session(session_id, tenant_id)
            user_id = session.get("user_id") if session else None

            # Delete session data
            key = self._session_key(tenant_id, session_id)
            await self._redis.delete(key)

            # Remove from tenant sessions index
            tenant_key = self._tenant_sessions_key(tenant_id)
            await self._redis._client.srem(tenant_key, session_id)

            # Remove from user sessions index
            if user_id:
                user_key = self._user_sessions_key(user_id)
                await self._redis._client.srem(user_key, session_id)

            # Delete associated return status
            status_key = self._status_key(session_id)
            await self._redis.delete(status_key)

            logger.debug(f"Deleted session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    async def touch_session(
        self,
        session_id: str,
        tenant_id: str,
    ) -> bool:
        """
        Extend session TTL without loading full data.

        Args:
            session_id: Session identifier
            tenant_id: Tenant ID

        Returns:
            True if session exists and was touched
        """
        try:
            key = self._session_key(tenant_id, session_id)
            return await self._redis.expire(key, self._ttl)
        except Exception as e:
            logger.error(f"Failed to touch session {session_id}: {e}")
            return False

    async def list_sessions(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List sessions for a tenant.

        Args:
            tenant_id: Tenant ID
            limit: Maximum number to return
            offset: Pagination offset

        Returns:
            List of session summaries
        """
        try:
            # Get session IDs from tenant index
            tenant_key = self._tenant_sessions_key(tenant_id)
            session_ids = await self._redis._client.smembers(tenant_key)

            if not session_ids:
                return []

            # Apply pagination
            session_ids = sorted(session_ids)[offset:offset + limit]

            # Load each session
            sessions = []
            for sid in session_ids:
                session = await self.load_session(sid, tenant_id)
                if session:
                    sessions.append({
                        "session_id": session.get("session_id"),
                        "session_type": session.get("session_type"),
                        "created_at": session.get("created_at"),
                        "last_activity": session.get("last_activity"),
                        "user_id": session.get("user_id"),
                        "is_anonymous": session.get("is_anonymous", True),
                    })

            return sessions

        except Exception as e:
            logger.error(f"Failed to list sessions for tenant {tenant_id}: {e}")
            return []

    async def get_user_sessions(
        self,
        user_id: str,
        tenant_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get all sessions for a user.

        Args:
            user_id: User ID
            tenant_id: Tenant ID for isolation
            limit: Maximum sessions to return

        Returns:
            List of session data dicts
        """
        try:
            user_key = self._user_sessions_key(user_id)
            session_ids = await self._redis._client.smembers(user_key)

            if not session_ids:
                return []

            # Load sessions, filtering by tenant
            sessions = []
            for sid in list(session_ids)[:limit]:
                session = await self.load_session(sid, tenant_id)
                if session and session.get("tenant_id") == tenant_id:
                    sessions.append(session)

            return sessions

        except Exception as e:
            logger.error(f"Failed to get sessions for user {user_id}: {e}")
            return []

    async def transfer_session_to_user(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        """
        Transfer an anonymous session to an authenticated user.

        Args:
            session_id: Session identifier
            tenant_id: Tenant ID
            user_id: User ID to transfer to

        Returns:
            True if transferred successfully
        """
        try:
            session = await self.load_session(session_id, tenant_id)
            if not session:
                return False

            # Update user association
            session["user_id"] = user_id
            session["is_anonymous"] = False

            # Save updated session
            await self.save_session(
                session_id=session_id,
                tenant_id=tenant_id,
                data=session.get("data", {}),
                session_type=session.get("session_type", "unified_filing"),
                user_id=user_id,
                metadata=session.get("metadata", {}),
            )

            # Add to user sessions index
            user_key = self._user_sessions_key(user_id)
            await self._redis._client.sadd(user_key, session_id)

            logger.info(f"Transferred session {session_id} to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to transfer session {session_id}: {e}")
            return False

    # Return status operations (for CPA workflow)

    async def save_return_status(
        self,
        session_id: str,
        status: str,
        cpa_reviewer_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Save return approval status.

        Args:
            session_id: Session/return identifier
            status: Status value
            cpa_reviewer_id: Optional CPA reviewer
            notes: Optional status notes

        Returns:
            True if saved successfully
        """
        try:
            now = datetime.utcnow().isoformat()
            key = self._status_key(session_id)

            status_data = {
                "session_id": session_id,
                "status": status,
                "cpa_reviewer_id": cpa_reviewer_id,
                "notes": notes,
                "updated_at": now,
            }

            # Check if exists to preserve created_at
            existing = await self._redis.get(key)
            if existing:
                status_data["created_at"] = existing.get("created_at", now)
            else:
                status_data["created_at"] = now

            return await self._redis.set(key, status_data, ttl=self._ttl * 7)  # Keep status longer

        except Exception as e:
            logger.error(f"Failed to save return status for {session_id}: {e}")
            return False

    async def get_return_status(
        self,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get return approval status.

        Args:
            session_id: Session/return identifier

        Returns:
            Status dict or None
        """
        try:
            key = self._status_key(session_id)
            return await self._redis.get(key)
        except Exception as e:
            logger.error(f"Failed to get return status for {session_id}: {e}")
            return None

    # Agent state persistence (pickled objects)

    async def save_agent_state(
        self,
        session_id: str,
        tenant_id: str,
        agent_state: Any,
    ) -> bool:
        """
        Save pickled agent state.

        Args:
            session_id: Session identifier
            tenant_id: Tenant ID
            agent_state: Agent state object to pickle

        Returns:
            True if saved successfully
        """
        try:
            # Pickle and base64 encode
            pickled = pickle.dumps(agent_state)
            encoded = base64.b64encode(pickled).decode("ascii")

            # Load existing session
            session = await self.load_session(session_id, tenant_id)
            if not session:
                logger.warning(f"Session {session_id} not found for agent state save")
                return False

            # Update agent state
            session["agent_state_base64"] = encoded

            # Re-save session
            return await self.save_session(
                session_id=session_id,
                tenant_id=tenant_id,
                data=session.get("data", {}),
                session_type=session.get("session_type", "unified_filing"),
                user_id=session.get("user_id"),
                metadata=session.get("metadata", {}),
            )

        except Exception as e:
            logger.error(f"Failed to save agent state for {session_id}: {e}")
            return False

    async def load_agent_state(
        self,
        session_id: str,
        tenant_id: str,
    ) -> Optional[Any]:
        """
        Load pickled agent state.

        Args:
            session_id: Session identifier
            tenant_id: Tenant ID

        Returns:
            Unpickled agent state or None
        """
        try:
            session = await self.load_session(session_id, tenant_id)
            if not session:
                return None

            encoded = session.get("agent_state_base64")
            if not encoded:
                return None

            # Decode and unpickle
            pickled = base64.b64decode(encoded.encode("ascii"))
            return pickle.loads(pickled)

        except Exception as e:
            logger.error(f"Failed to load agent state for {session_id}: {e}")
            return None

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        return await self._redis.ping()


# Factory function for Redis session persistence
_redis_session_persistence: Optional[RedisSessionPersistence] = None


async def get_redis_session_persistence() -> Optional[RedisSessionPersistence]:
    """
    Get Redis session persistence singleton.

    Returns:
        RedisSessionPersistence instance or None if Redis unavailable
    """
    global _redis_session_persistence

    if _redis_session_persistence is not None:
        return _redis_session_persistence

    try:
        from cache.redis_client import get_redis_client

        redis_client = await get_redis_client()
        if redis_client and await redis_client.ping():
            _redis_session_persistence = RedisSessionPersistence(redis_client)
            logger.info("Redis session persistence initialized")
            return _redis_session_persistence
    except Exception as e:
        logger.warning(f"Redis session persistence not available: {e}")

    return None
