"""
Unified Audit Storage

Consolidates storage backends from audit_storage.py and audit_logger.py
into a single implementation with comprehensive indexing.

Supports:
- In-memory storage for testing
- SQLite for production with efficient querying
"""

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .event_types import AuditEventType, AuditSeverity, AuditSource
from .entry import UnifiedAuditEntry, ChangeRecord


class AuditStorage(ABC):
    """Abstract base class for audit storage backends."""

    @abstractmethod
    def save(self, entry: UnifiedAuditEntry) -> str:
        """Save an audit entry. Returns entry_id."""
        pass

    @abstractmethod
    def get(self, entry_id: str) -> Optional[UnifiedAuditEntry]:
        """Get a specific entry by ID."""
        pass

    @abstractmethod
    def query(
        self,
        session_id: Optional[str] = None,
        return_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UnifiedAuditEntry]:
        """Query entries with filters."""
        pass

    @abstractmethod
    def get_last_hash(self, session_id: str) -> Optional[str]:
        """Get the last signature hash for chain verification."""
        pass


class InMemoryAuditStorage(AuditStorage):
    """
    In-memory audit storage for testing.

    Thread-safe but not persistent.
    """

    def __init__(self):
        self._entries: Dict[str, UnifiedAuditEntry] = {}
        self._lock = threading.Lock()

    def save(self, entry: UnifiedAuditEntry) -> str:
        """Save an audit entry to memory."""
        with self._lock:
            self._entries[entry.entry_id] = entry
        return entry.entry_id

    def get(self, entry_id: str) -> Optional[UnifiedAuditEntry]:
        """Get a specific entry by ID."""
        with self._lock:
            return self._entries.get(entry_id)

    def query(
        self,
        session_id: Optional[str] = None,
        return_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UnifiedAuditEntry]:
        """Query entries with filters."""
        with self._lock:
            results = list(self._entries.values())

        # Apply filters
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        if return_id:
            results = [e for e in results if e.return_id == return_id]
        if tenant_id:
            results = [e for e in results if e.tenant_id == tenant_id]
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if resource_type:
            results = [e for e in results if e.resource_type == resource_type]
        if resource_id:
            results = [e for e in results if e.resource_id == resource_id]
        if start_date:
            results = [e for e in results if e.timestamp >= start_date]
        if end_date:
            results = [e for e in results if e.timestamp <= end_date]
        if severity:
            results = [e for e in results if e.severity == severity]
        if success_only is not None:
            results = [e for e in results if e.success == success_only]

        # Sort by timestamp descending
        results.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply pagination
        return results[offset:offset + limit]

    def get_last_hash(self, session_id: str) -> Optional[str]:
        """Get the last signature hash for chain verification."""
        entries = self.query(session_id=session_id, limit=1)
        if entries:
            return entries[0].signature_hash
        return None

    def clear(self) -> None:
        """Clear all entries (for testing)."""
        with self._lock:
            self._entries.clear()

    def count(self) -> int:
        """Get total entry count."""
        with self._lock:
            return len(self._entries)


class SQLiteAuditStorage(AuditStorage):
    """
    SQLite-based audit storage for production.

    Features:
    - Persistent storage
    - Comprehensive indexing for efficient queries
    - Thread-safe with connection pooling
    - JSON storage for complex fields
    """

    def __init__(self, db_path: str = "./data/unified_audit.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self) -> None:
        """Initialize database schema with comprehensive indexes."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Main audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS unified_audit_log (
                entry_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,

                session_id TEXT,
                return_id TEXT,
                tenant_id TEXT,

                user_id TEXT,
                user_name TEXT,
                user_role TEXT,

                ip_address TEXT,
                user_agent TEXT,
                request_path TEXT,

                action TEXT,
                resource_type TEXT,
                resource_id TEXT,
                description TEXT,

                changes JSON,
                old_value JSON,
                new_value JSON,

                source TEXT,
                confidence REAL,
                calculation_version TEXT,
                tax_year INTEGER,

                pii_fields_accessed JSON,
                pii_access_reason TEXT,

                metadata JSON,

                success INTEGER NOT NULL DEFAULT 1,
                error_message TEXT,
                error_code TEXT,

                signature_hash TEXT,
                previous_hash TEXT
            )
        """)

        # Comprehensive indexes for efficient querying
        indexes = [
            ("idx_audit_timestamp", "timestamp"),
            ("idx_audit_session", "session_id, timestamp"),
            ("idx_audit_return", "return_id, timestamp"),
            ("idx_audit_tenant", "tenant_id, timestamp"),
            ("idx_audit_user", "user_id, timestamp"),
            ("idx_audit_event_type", "event_type, timestamp"),
            ("idx_audit_resource", "resource_type, resource_id"),
            ("idx_audit_severity", "severity, timestamp"),
            ("idx_audit_pii", "event_type, user_id, timestamp"),
        ]

        for index_name, columns in indexes:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON unified_audit_log({columns})
            """)

        conn.commit()

    def save(self, entry: UnifiedAuditEntry) -> str:
        """Save an audit entry to SQLite."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO unified_audit_log (
                entry_id, timestamp, event_type, severity,
                session_id, return_id, tenant_id,
                user_id, user_name, user_role,
                ip_address, user_agent, request_path,
                action, resource_type, resource_id, description,
                changes, old_value, new_value,
                source, confidence, calculation_version, tax_year,
                pii_fields_accessed, pii_access_reason,
                metadata,
                success, error_message, error_code,
                signature_hash, previous_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id,
            entry.timestamp.isoformat(),
            entry.event_type.value,
            entry.severity.value,
            entry.session_id,
            entry.return_id,
            entry.tenant_id,
            entry.user_id,
            entry.user_name,
            entry.user_role,
            entry.ip_address,
            entry.user_agent,
            entry.request_path,
            entry.action,
            entry.resource_type,
            entry.resource_id,
            entry.description,
            json.dumps([c.to_dict() for c in entry.changes]) if entry.changes else None,
            json.dumps(entry.old_value) if entry.old_value else None,
            json.dumps(entry.new_value) if entry.new_value else None,
            entry.source.value,
            entry.confidence,
            entry.calculation_version,
            entry.tax_year,
            json.dumps(entry.pii_fields_accessed) if entry.pii_fields_accessed else None,
            entry.pii_access_reason,
            json.dumps(entry.metadata) if entry.metadata else None,
            1 if entry.success else 0,
            entry.error_message,
            entry.error_code,
            entry.signature_hash,
            entry.previous_hash,
        ))

        conn.commit()
        return entry.entry_id

    def get(self, entry_id: str) -> Optional[UnifiedAuditEntry]:
        """Get a specific entry by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM unified_audit_log WHERE entry_id = ?",
            (entry_id,)
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_entry(row)
        return None

    def _row_to_entry(self, row: sqlite3.Row) -> UnifiedAuditEntry:
        """Convert database row to UnifiedAuditEntry."""
        changes = []
        if row["changes"]:
            changes_data = json.loads(row["changes"])
            changes = [ChangeRecord.from_dict(c) for c in changes_data]

        return UnifiedAuditEntry(
            entry_id=row["entry_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=AuditEventType(row["event_type"]),
            severity=AuditSeverity(row["severity"]),
            session_id=row["session_id"],
            return_id=row["return_id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            user_role=row["user_role"],
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            request_path=row["request_path"],
            action=row["action"] or "",
            resource_type=row["resource_type"] or "",
            resource_id=row["resource_id"],
            description=row["description"] or "",
            changes=changes,
            old_value=json.loads(row["old_value"]) if row["old_value"] else None,
            new_value=json.loads(row["new_value"]) if row["new_value"] else None,
            source=AuditSource(row["source"]) if row["source"] else AuditSource.USER_INPUT,
            confidence=row["confidence"],
            calculation_version=row["calculation_version"],
            tax_year=row["tax_year"],
            pii_fields_accessed=json.loads(row["pii_fields_accessed"]) if row["pii_fields_accessed"] else [],
            pii_access_reason=row["pii_access_reason"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            success=bool(row["success"]),
            error_message=row["error_message"],
            error_code=row["error_code"],
            signature_hash=row["signature_hash"],
            previous_hash=row["previous_hash"],
        )

    def query(
        self,
        session_id: Optional[str] = None,
        return_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UnifiedAuditEntry]:
        """Query entries with filters."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM unified_audit_log WHERE 1=1"
        params: List[Any] = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if return_id:
            query += " AND return_id = ?"
            params.append(return_id)
        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)
        if resource_type:
            query += " AND resource_type = ?"
            params.append(resource_type)
        if resource_id:
            query += " AND resource_id = ?"
            params.append(resource_id)
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        if severity:
            query += " AND severity = ?"
            params.append(severity.value)
        if success_only is not None:
            query += " AND success = ?"
            params.append(1 if success_only else 0)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_last_hash(self, session_id: str) -> Optional[str]:
        """Get the last signature hash for chain verification."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT signature_hash FROM unified_audit_log
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (session_id,))

        row = cursor.fetchone()
        if row:
            return row["signature_hash"]
        return None

    def count(self, **filters) -> int:
        """Get count of entries matching filters."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM unified_audit_log WHERE 1=1"
        params: List[Any] = []

        for key, value in filters.items():
            if value is not None:
                query += f" AND {key} = ?"
                params.append(value)

        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def verify_chain_integrity(self, session_id: str) -> tuple[bool, List[str]]:
        """
        Verify the integrity of the audit chain for a session.

        Returns:
            (is_valid, list_of_issues)
        """
        entries = self.query(session_id=session_id, limit=10000)
        entries.sort(key=lambda e: e.timestamp)  # Chronological order

        issues = []

        for i, entry in enumerate(entries):
            # Verify individual entry integrity
            if not entry.verify_integrity():
                issues.append(f"Entry {entry.entry_id}: Integrity check failed")

            # Verify chain linkage
            if i > 0:
                expected_previous = entries[i - 1].signature_hash
                if entry.previous_hash and entry.previous_hash != expected_previous:
                    issues.append(f"Entry {entry.entry_id}: Chain broken (previous_hash mismatch)")

        return len(issues) == 0, issues
