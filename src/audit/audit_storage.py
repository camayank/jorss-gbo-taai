"""
Audit Trail Storage Backends

Provides storage implementations for audit log persistence.
Supports both in-memory (for testing) and SQLite (for production).
"""
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .audit_models import AuditEntry, AuditAction, AuditSource


class AuditStorageBackend(ABC):
    """Abstract base class for audit storage backends."""

    @abstractmethod
    def save(self, entry: AuditEntry) -> None:
        """Save an audit entry."""
        pass

    @abstractmethod
    def get_by_session(self, session_id: str, entity_type: Optional[str] = None) -> List[AuditEntry]:
        """Get all entries for a session, optionally filtered by entity type."""
        pass

    @abstractmethod
    def get_by_entity(self, entity_type: str, entity_id: str) -> List[AuditEntry]:
        """Get all entries for a specific entity."""
        pass

    @abstractmethod
    def get_timeline(self, session_id: str, start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None) -> List[AuditEntry]:
        """Get chronological timeline of all changes for a session."""
        pass


class InMemoryAuditStorage(AuditStorageBackend):
    """
    In-memory audit storage for testing and development.

    Thread-safe but not persistent - data lost on restart.
    """

    def __init__(self):
        self._entries: List[AuditEntry] = []
        self._lock = threading.Lock()

    def save(self, entry: AuditEntry) -> None:
        """Save an audit entry to memory."""
        with self._lock:
            self._entries.append(entry)

    def get_by_session(self, session_id: str, entity_type: Optional[str] = None) -> List[AuditEntry]:
        """Get all entries for a session."""
        with self._lock:
            entries = [e for e in self._entries if e.session_id == session_id]
            if entity_type:
                entries = [e for e in entries if e.entity_type == entity_type]
            return sorted(entries, key=lambda e: e.timestamp)

    def get_by_entity(self, entity_type: str, entity_id: str) -> List[AuditEntry]:
        """Get all entries for a specific entity."""
        with self._lock:
            entries = [e for e in self._entries
                      if e.entity_type == entity_type and e.entity_id == entity_id]
            return sorted(entries, key=lambda e: e.timestamp)

    def get_timeline(self, session_id: str, start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None) -> List[AuditEntry]:
        """Get chronological timeline for a session."""
        with self._lock:
            entries = [e for e in self._entries if e.session_id == session_id]

            if start_time:
                entries = [e for e in entries if e.timestamp >= start_time]
            if end_time:
                entries = [e for e in entries if e.timestamp <= end_time]

            return sorted(entries, key=lambda e: e.timestamp)

    def clear(self) -> None:
        """Clear all entries (for testing)."""
        with self._lock:
            self._entries.clear()

    def count(self) -> int:
        """Get total entry count."""
        with self._lock:
            return len(self._entries)


class SQLiteAuditStorage(AuditStorageBackend):
    """
    SQLite-based audit storage for production use.

    Provides persistent, thread-safe audit log storage with
    efficient querying by session, entity, and time range.
    """

    def __init__(self, db_path: str = "data/audit_trail.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                field_name TEXT,
                old_value TEXT,
                new_value TEXT,
                source TEXT NOT NULL,
                confidence REAL,
                reason TEXT,
                user_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                calculation_version TEXT,
                tax_year INTEGER,
                metadata TEXT
            )
        """)

        # Create indexes for efficient querying
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_session
            ON audit_log(session_id, timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_entity
            ON audit_log(entity_type, entity_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_log(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_user
            ON audit_log(user_id)
        """)

        conn.commit()

    def save(self, entry: AuditEntry) -> None:
        """Save an audit entry to SQLite."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO audit_log (
                id, session_id, timestamp, action, entity_type, entity_id,
                field_name, old_value, new_value, source, confidence, reason,
                user_id, ip_address, user_agent, calculation_version, tax_year, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id,
            entry.session_id,
            entry.timestamp.isoformat(),
            entry.action.value,
            entry.entity_type,
            entry.entity_id,
            entry.field_name,
            json.dumps(entry.old_value) if entry.old_value is not None else None,
            json.dumps(entry.new_value) if entry.new_value is not None else None,
            entry.source.value,
            entry.confidence,
            entry.reason,
            entry.user_id,
            entry.ip_address,
            entry.user_agent,
            entry.calculation_version,
            entry.tax_year,
            json.dumps(entry.metadata) if entry.metadata else None
        ))

        conn.commit()

    def _row_to_entry(self, row: sqlite3.Row) -> AuditEntry:
        """Convert database row to AuditEntry."""
        return AuditEntry(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            action=AuditAction(row["action"]),
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            field_name=row["field_name"],
            old_value=json.loads(row["old_value"]) if row["old_value"] else None,
            new_value=json.loads(row["new_value"]) if row["new_value"] else None,
            source=AuditSource(row["source"]),
            confidence=row["confidence"],
            reason=row["reason"],
            user_id=row["user_id"],
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            calculation_version=row["calculation_version"],
            tax_year=row["tax_year"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        )

    def get_by_session(self, session_id: str, entity_type: Optional[str] = None) -> List[AuditEntry]:
        """Get all entries for a session."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if entity_type:
            cursor.execute("""
                SELECT * FROM audit_log
                WHERE session_id = ? AND entity_type = ?
                ORDER BY timestamp ASC
            """, (session_id, entity_type))
        else:
            cursor.execute("""
                SELECT * FROM audit_log
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_by_entity(self, entity_type: str, entity_id: str) -> List[AuditEntry]:
        """Get all entries for a specific entity."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM audit_log
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY timestamp ASC
        """, (entity_type, entity_id))

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_timeline(self, session_id: str, start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None) -> List[AuditEntry]:
        """Get chronological timeline for a session."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM audit_log WHERE session_id = ?"
        params = [session_id]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY timestamp ASC"

        cursor.execute(query, params)
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_user_activity(self, user_id: str, limit: int = 100) -> List[AuditEntry]:
        """Get recent activity for a specific user."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM audit_log
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_recent_calculations(self, session_id: str, limit: int = 10) -> List[AuditEntry]:
        """Get recent tax calculations for a session."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM audit_log
            WHERE session_id = ? AND action = 'calculate'
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, limit))

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_field_history(self, session_id: str, entity_type: str,
                          field_name: str) -> List[AuditEntry]:
        """Get complete history of changes to a specific field."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM audit_log
            WHERE session_id = ? AND entity_type = ? AND field_name = ?
            ORDER BY timestamp ASC
        """, (session_id, entity_type, field_name))

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def count_by_session(self, session_id: str) -> int:
        """Get total entry count for a session."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM audit_log WHERE session_id = ?
        """, (session_id,))

        return cursor.fetchone()[0]

    def export_session_audit(self, session_id: str) -> List[dict]:
        """Export complete audit trail for a session as JSON-serializable list."""
        entries = self.get_by_session(session_id)
        return [entry.to_dict() for entry in entries]
