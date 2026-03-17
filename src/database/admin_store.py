"""
Simple SQLite-backed key-value store for admin data.

Replaces in-memory dicts in admin APIs (refunds, API keys, compliance)
with persistent storage that survives restarts and works across workers.

Uses a single SQLite database with separate tables per data type.
Thread-safe via SQLite's built-in locking.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Database location
_DB_DIR = Path(__file__).parent.parent.parent / "data"
_DB_PATH = _DB_DIR / "admin_store.db"

# Module-level lock for initialization
_init_lock = threading.Lock()
_initialized = False


def _get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    _ensure_initialized()
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _ensure_initialized():
    """Create database and tables if they don't exist."""
    global _initialized
    if _initialized:
        return

    with _init_lock:
        if _initialized:
            return

        _DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH), timeout=10)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS admin_refunds (
                    refund_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_api_keys (
                    key_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_compliance_reports (
                    report_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_compliance_alerts (
                    alert_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_refunds_status
                    ON admin_refunds(json_extract(data, '$.status'));
                CREATE INDEX IF NOT EXISTS idx_api_keys_firm
                    ON admin_api_keys(json_extract(data, '$.firm_id'));
            """)
            conn.commit()
            _initialized = True
            logger.info(f"Admin store initialized at {_DB_PATH}")
        finally:
            conn.close()


class AdminStore:
    """
    Generic CRUD operations for admin data stored as JSON in SQLite.

    Usage:
        store = AdminStore("admin_refunds", "refund_id")
        store.put("ref-123", {"refund_id": "ref-123", "amount": 100, ...})
        item = store.get("ref-123")
        all_items = store.list_all()
    """

    def __init__(self, table_name: str, id_column: str):
        self._table = table_name
        self._id_col = id_column

    def put(self, item_id: str, data: dict) -> None:
        """Insert or update an item."""
        now = datetime.now(timezone.utc).isoformat()
        json_data = json.dumps(data, default=str)
        conn = _get_connection()
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO {self._table} ({self._id_col}, data, created_at, updated_at) "
                f"VALUES (?, ?, COALESCE((SELECT created_at FROM {self._table} WHERE {self._id_col} = ?), ?), ?)",
                (item_id, json_data, item_id, now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, item_id: str) -> Optional[dict]:
        """Get an item by ID."""
        conn = _get_connection()
        try:
            row = conn.execute(
                f"SELECT data FROM {self._table} WHERE {self._id_col} = ?",
                (item_id,),
            ).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            conn.close()

    def list_all(self) -> List[dict]:
        """List all items."""
        conn = _get_connection()
        try:
            rows = conn.execute(
                f"SELECT data FROM {self._table} ORDER BY updated_at DESC"
            ).fetchall()
            return [json.loads(row[0]) for row in rows]
        finally:
            conn.close()

    def delete(self, item_id: str) -> bool:
        """Delete an item by ID."""
        conn = _get_connection()
        try:
            result = conn.execute(
                f"DELETE FROM {self._table} WHERE {self._id_col} = ?",
                (item_id,),
            )
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def query(self, json_path: str, value: str) -> List[dict]:
        """Query items by a JSON field value."""
        conn = _get_connection()
        try:
            rows = conn.execute(
                f"SELECT data FROM {self._table} WHERE json_extract(data, ?) = ? ORDER BY updated_at DESC",
                (json_path, value),
            ).fetchall()
            return [json.loads(row[0]) for row in rows]
        finally:
            conn.close()

    def count(self) -> int:
        """Count all items."""
        conn = _get_connection()
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {self._table}").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()


# Pre-configured stores for each admin domain
refund_store = AdminStore("admin_refunds", "refund_id")
api_key_store = AdminStore("admin_api_keys", "key_id")
compliance_report_store = AdminStore("admin_compliance_reports", "report_id")
compliance_alert_store = AdminStore("admin_compliance_alerts", "alert_id")
