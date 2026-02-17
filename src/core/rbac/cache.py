"""
Simple permission cache for RBAC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from uuid import UUID


@dataclass
class _CacheEntry:
    permissions: Set[str]
    expires_at: datetime

    def is_valid(self) -> bool:
        return datetime.utcnow() < self.expires_at


@dataclass
class PermissionCache:
    """In-memory permission cache."""

    ttl_seconds: int = 300
    _user_cache: Dict[str, _CacheEntry] = field(default_factory=dict)

    def get_user(self, user_id: UUID) -> Optional[Set[str]]:
        key = str(user_id)
        entry = self._user_cache.get(key)
        if not entry:
            return None
        if not entry.is_valid():
            self._user_cache.pop(key, None)
            return None
        return set(entry.permissions)

    def set_user(self, user_id: UUID, permissions: Set[str]) -> None:
        key = str(user_id)
        self._user_cache[key] = _CacheEntry(
            permissions=set(permissions),
            expires_at=datetime.utcnow() + timedelta(seconds=self.ttl_seconds),
        )

    def invalidate_user(self, user_id: UUID) -> None:
        self._user_cache.pop(str(user_id), None)

    def invalidate_firm(self, firm_id: UUID) -> None:
        # No firm index maintained yet; clear all as safe default.
        self._user_cache.clear()

    def clear(self) -> None:
        self._user_cache.clear()


_permission_cache = PermissionCache()


def get_permission_cache() -> PermissionCache:
    """Get singleton permission cache."""
    return _permission_cache

