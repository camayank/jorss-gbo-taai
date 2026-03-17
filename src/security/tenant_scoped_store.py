"""
Tenant-Scoped In-Memory Store

Wraps a plain dict to enforce tenant isolation on all operations.
Prevents cross-tenant data access in in-memory caches.

Usage:
    store = TenantScopedStore(max_size=10000)
    store.set("report-123", report_data, tenant_id="firm-alpha")
    store.get("report-123", tenant_id="firm-alpha")   # -> report_data
    store.get("report-123", tenant_id="firm-beta")    # -> None (isolated)
"""

import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TenantScopedStore:
    """
    Thread-safe in-memory store with mandatory tenant isolation.

    Every key is internally prefixed with tenant_id to prevent cross-tenant
    access even if the raw key (e.g., report_id) is known.
    """

    def __init__(self, name: str = "store", max_size: int = 10000):
        self._name = name
        self._max_size = max_size
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def _scoped_key(self, key: str, tenant_id: str) -> str:
        """Create a tenant-scoped internal key."""
        if not tenant_id:
            logger.warning(
                f"[{self._name}] Access attempt with empty tenant_id for key '{key}'. "
                "Falling back to 'default' — this should not happen in production."
            )
            tenant_id = "default"
        return f"{tenant_id}::{key}"

    def get(self, key: str, tenant_id: str) -> Optional[Any]:
        """Get a value, scoped to tenant. Returns None if not found or wrong tenant."""
        scoped = self._scoped_key(key, tenant_id)
        with self._lock:
            return self._data.get(scoped)

    def set(self, key: str, value: Any, tenant_id: str) -> None:
        """Set a value, scoped to tenant."""
        scoped = self._scoped_key(key, tenant_id)
        with self._lock:
            if len(self._data) >= self._max_size and scoped not in self._data:
                self._evict_oldest()
            self._data[scoped] = value

    def delete(self, key: str, tenant_id: str) -> bool:
        """Delete a value, scoped to tenant. Returns True if existed."""
        scoped = self._scoped_key(key, tenant_id)
        with self._lock:
            return self._data.pop(scoped, None) is not None

    def list_keys(self, tenant_id: str) -> List[str]:
        """List all keys belonging to a specific tenant."""
        prefix = f"{tenant_id}::"
        with self._lock:
            return [
                k[len(prefix):]
                for k in self._data
                if k.startswith(prefix)
            ]

    def clear_tenant(self, tenant_id: str) -> int:
        """Remove all entries for a tenant. Returns count removed."""
        prefix = f"{tenant_id}::"
        with self._lock:
            keys_to_remove = [k for k in self._data if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._data[k]
            return len(keys_to_remove)

    def _evict_oldest(self) -> None:
        """Remove oldest 10% of entries when store is full."""
        evict_count = max(1, len(self._data) // 10)
        keys = list(self._data.keys())[:evict_count]
        for k in keys:
            del self._data[k]
        logger.info(
            f"[{self._name}] Evicted {evict_count} entries (max_size={self._max_size})"
        )

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
