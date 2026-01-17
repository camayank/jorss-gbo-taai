"""
Session Persistence Layer.

Provides database-backed persistence for web application session state,
replacing in-memory dictionaries with durable storage.

This addresses the CRITICAL findings from the in-memory state audit:
- _SESSIONS: Active TaxAgent conversations
- _DOCUMENTS: Document processing results
- _TAX_RETURNS: Document-only workflow tax returns

Prompt 1: Persistence Safety - Replace in-memory state with database-backed models.
Prompt 7: Tenant Safety - All data is scoped by tenant_id.
"""

import sqlite3
import json
import uuid
import pickle
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# Use same database path as main persistence
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"

# Session expiry (24 hours by default)
DEFAULT_SESSION_TTL_HOURS = 24


@dataclass
class SessionRecord:
    """Persisted session record."""
    session_id: str
    tenant_id: str
    session_type: str  # 'agent', 'document_flow', 'tax_return'
    created_at: str
    last_activity: str
    expires_at: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentProcessingRecord:
    """Persisted document processing result."""
    document_id: str
    session_id: str
    tenant_id: str
    created_at: str
    document_type: Optional[str]
    status: str  # 'pending', 'processing', 'completed', 'failed'
    result: Dict[str, Any]
    error_message: Optional[str] = None


class SessionPersistence:
    """
    Database-backed persistence for web session state.

    Replaces the in-memory dictionaries in web/app.py:
    - _SESSIONS -> session_states table
    - _DOCUMENTS -> document_processing table
    - _TAX_RETURNS -> session_tax_returns table
    """

    def __init__(self, db_path: Optional[Path] = None, ttl_hours: int = DEFAULT_SESSION_TTL_HOURS):
        """
        Initialize session persistence.

        Args:
            db_path: Path to SQLite database file.
            ttl_hours: Session time-to-live in hours.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.ttl_hours = ttl_hours
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Session states table (replaces _SESSIONS)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_states (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    session_type TEXT NOT NULL DEFAULT 'agent',
                    created_at TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    data_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    agent_state_blob BLOB
                )
            """)

            # Document processing results table (replaces _DOCUMENTS)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_processing (
                    document_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    created_at TEXT NOT NULL,
                    document_type TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    error_message TEXT,
                    FOREIGN KEY (session_id) REFERENCES session_states(session_id)
                )
            """)

            # Session tax returns table (replaces _TAX_RETURNS)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_tax_returns (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tax_year INTEGER NOT NULL DEFAULT 2025,
                    return_data_json TEXT NOT NULL DEFAULT '{}',
                    calculated_results_json TEXT,
                    FOREIGN KEY (session_id) REFERENCES session_states(session_id)
                )
            """)

            # Indexes for efficient lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_tenant
                ON session_states(tenant_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_expires
                ON session_states(expires_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_session
                ON document_processing(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_tenant
                ON document_processing(tenant_id)
            """)

            conn.commit()

    # =========================================================================
    # SESSION STATE METHODS (replaces _SESSIONS)
    # =========================================================================

    def save_session(
        self,
        session_id: str,
        tenant_id: str = "default",
        session_type: str = "agent",
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agent_state: Optional[bytes] = None
    ) -> None:
        """
        Save or update a session.

        Args:
            session_id: Unique session identifier
            tenant_id: Tenant identifier for isolation
            session_type: Type of session ('agent', 'document_flow', etc.)
            data: Session data dictionary
            metadata: Additional metadata
            agent_state: Pickled TaxAgent state (optional)
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self.ttl_hours)
        data = data or {}
        metadata = metadata or {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT session_id FROM session_states WHERE session_id = ?",
                (session_id,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE session_states SET
                        tenant_id = ?,
                        session_type = ?,
                        last_activity = ?,
                        expires_at = ?,
                        data_json = ?,
                        metadata_json = ?,
                        agent_state_blob = ?
                    WHERE session_id = ?
                """, (
                    tenant_id,
                    session_type,
                    now.isoformat(),
                    expires_at.isoformat(),
                    json.dumps(data, default=str),
                    json.dumps(metadata, default=str),
                    agent_state,
                    session_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO session_states (
                        session_id, tenant_id, session_type,
                        created_at, last_activity, expires_at,
                        data_json, metadata_json, agent_state_blob
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    tenant_id,
                    session_type,
                    now.isoformat(),
                    now.isoformat(),
                    expires_at.isoformat(),
                    json.dumps(data, default=str),
                    json.dumps(metadata, default=str),
                    agent_state
                ))

            conn.commit()

    def load_session(self, session_id: str, tenant_id: Optional[str] = None) -> Optional[SessionRecord]:
        """
        Load a session by ID.

        Args:
            session_id: Session identifier
            tenant_id: Optional tenant filter (for security)

        Returns:
            SessionRecord or None if not found/expired
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if tenant_id:
                cursor.execute("""
                    SELECT session_id, tenant_id, session_type,
                           created_at, last_activity, expires_at,
                           data_json, metadata_json
                    FROM session_states
                    WHERE session_id = ? AND tenant_id = ?
                """, (session_id, tenant_id))
            else:
                cursor.execute("""
                    SELECT session_id, tenant_id, session_type,
                           created_at, last_activity, expires_at,
                           data_json, metadata_json
                    FROM session_states
                    WHERE session_id = ?
                """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Check if expired
            expires_at = datetime.fromisoformat(row[5])
            if datetime.utcnow() > expires_at:
                self.delete_session(session_id)
                return None

            return SessionRecord(
                session_id=row[0],
                tenant_id=row[1],
                session_type=row[2],
                created_at=row[3],
                last_activity=row[4],
                expires_at=row[5],
                data=json.loads(row[6]) if row[6] else {},
                metadata=json.loads(row[7]) if row[7] else {}
            )

    def load_agent_state(self, session_id: str) -> Optional[bytes]:
        """Load pickled TaxAgent state for a session."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT agent_state_blob FROM session_states WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] else None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all related data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Delete related documents
            cursor.execute(
                "DELETE FROM document_processing WHERE session_id = ?",
                (session_id,)
            )

            # Delete related tax returns
            cursor.execute(
                "DELETE FROM session_tax_returns WHERE session_id = ?",
                (session_id,)
            )

            # Delete session
            cursor.execute(
                "DELETE FROM session_states WHERE session_id = ?",
                (session_id,)
            )

            conn.commit()
            return cursor.rowcount > 0

    def touch_session(self, session_id: str) -> bool:
        """Update session last_activity and extend expiry."""
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self.ttl_hours)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE session_states SET
                    last_activity = ?,
                    expires_at = ?
                WHERE session_id = ?
            """, (now.isoformat(), expires_at.isoformat(), session_id))
            conn.commit()
            return cursor.rowcount > 0

    def list_sessions(self, tenant_id: str) -> List[SessionRecord]:
        """List all active sessions for a tenant."""
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, tenant_id, session_type,
                       created_at, last_activity, expires_at,
                       data_json, metadata_json
                FROM session_states
                WHERE tenant_id = ? AND expires_at > ?
                ORDER BY last_activity DESC
            """, (tenant_id, now))

            sessions = []
            for row in cursor.fetchall():
                sessions.append(SessionRecord(
                    session_id=row[0],
                    tenant_id=row[1],
                    session_type=row[2],
                    created_at=row[3],
                    last_activity=row[4],
                    expires_at=row[5],
                    data=json.loads(row[6]) if row[6] else {},
                    metadata=json.loads(row[7]) if row[7] else {}
                ))
            return sessions

    def cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions."""
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get expired session IDs
            cursor.execute(
                "SELECT session_id FROM session_states WHERE expires_at < ?",
                (now,)
            )
            expired_ids = [row[0] for row in cursor.fetchall()]

            if not expired_ids:
                return 0

            # Delete related data
            placeholders = ",".join("?" * len(expired_ids))
            cursor.execute(
                f"DELETE FROM document_processing WHERE session_id IN ({placeholders})",
                expired_ids
            )
            cursor.execute(
                f"DELETE FROM session_tax_returns WHERE session_id IN ({placeholders})",
                expired_ids
            )
            cursor.execute(
                f"DELETE FROM session_states WHERE session_id IN ({placeholders})",
                expired_ids
            )

            conn.commit()
            return len(expired_ids)

    # =========================================================================
    # DOCUMENT PROCESSING METHODS (replaces _DOCUMENTS)
    # =========================================================================

    def save_document_result(
        self,
        document_id: str,
        session_id: str,
        tenant_id: str = "default",
        document_type: Optional[str] = None,
        status: str = "completed",
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Save document processing result.

        Args:
            document_id: Unique document identifier
            session_id: Associated session
            tenant_id: Tenant identifier
            document_type: Type of document (W-2, 1099, etc.)
            status: Processing status
            result: Processing result data
            error_message: Error message if failed
        """
        now = datetime.utcnow().isoformat()
        result = result or {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT document_id FROM document_processing WHERE document_id = ?",
                (document_id,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE document_processing SET
                        session_id = ?,
                        tenant_id = ?,
                        document_type = ?,
                        status = ?,
                        result_json = ?,
                        error_message = ?
                    WHERE document_id = ?
                """, (
                    session_id,
                    tenant_id,
                    document_type,
                    status,
                    json.dumps(result, default=str),
                    error_message,
                    document_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO document_processing (
                        document_id, session_id, tenant_id,
                        created_at, document_type, status,
                        result_json, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document_id,
                    session_id,
                    tenant_id,
                    now,
                    document_type,
                    status,
                    json.dumps(result, default=str),
                    error_message
                ))

            conn.commit()

    def load_document_result(
        self,
        document_id: str,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Optional[DocumentProcessingRecord]:
        """
        Load document processing result.

        Args:
            document_id: Document identifier
            session_id: Optional session filter (for security)
            tenant_id: Optional tenant filter (for security)

        Returns:
            DocumentProcessingRecord or None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = """
                SELECT document_id, session_id, tenant_id,
                       created_at, document_type, status,
                       result_json, error_message
                FROM document_processing
                WHERE document_id = ?
            """
            params = [document_id]

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            cursor.execute(query, params)
            row = cursor.fetchone()

            if not row:
                return None

            return DocumentProcessingRecord(
                document_id=row[0],
                session_id=row[1],
                tenant_id=row[2],
                created_at=row[3],
                document_type=row[4],
                status=row[5],
                result=json.loads(row[6]) if row[6] else {},
                error_message=row[7]
            )

    def list_session_documents(
        self,
        session_id: str,
        tenant_id: Optional[str] = None
    ) -> List[DocumentProcessingRecord]:
        """List all documents for a session."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if tenant_id:
                cursor.execute("""
                    SELECT document_id, session_id, tenant_id,
                           created_at, document_type, status,
                           result_json, error_message
                    FROM document_processing
                    WHERE session_id = ? AND tenant_id = ?
                    ORDER BY created_at DESC
                """, (session_id, tenant_id))
            else:
                cursor.execute("""
                    SELECT document_id, session_id, tenant_id,
                           created_at, document_type, status,
                           result_json, error_message
                    FROM document_processing
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                """, (session_id,))

            documents = []
            for row in cursor.fetchall():
                documents.append(DocumentProcessingRecord(
                    document_id=row[0],
                    session_id=row[1],
                    tenant_id=row[2],
                    created_at=row[3],
                    document_type=row[4],
                    status=row[5],
                    result=json.loads(row[6]) if row[6] else {},
                    error_message=row[7]
                ))
            return documents

    def delete_document(self, document_id: str) -> bool:
        """Delete a document processing result."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM document_processing WHERE document_id = ?",
                (document_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # TAX RETURN METHODS (replaces _TAX_RETURNS)
    # =========================================================================

    def save_session_tax_return(
        self,
        session_id: str,
        tenant_id: str = "default",
        tax_year: int = 2025,
        return_data: Optional[Dict[str, Any]] = None,
        calculated_results: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save tax return data for a session.

        Args:
            session_id: Session identifier
            tenant_id: Tenant identifier
            tax_year: Tax year
            return_data: Tax return data dictionary
            calculated_results: Calculated results (optional)
        """
        now = datetime.utcnow().isoformat()
        return_data = return_data or {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT session_id FROM session_tax_returns WHERE session_id = ?",
                (session_id,)
            )
            existing = cursor.fetchone()

            calc_json = json.dumps(calculated_results, default=str) if calculated_results else None

            if existing:
                cursor.execute("""
                    UPDATE session_tax_returns SET
                        tenant_id = ?,
                        updated_at = ?,
                        tax_year = ?,
                        return_data_json = ?,
                        calculated_results_json = ?
                    WHERE session_id = ?
                """, (
                    tenant_id,
                    now,
                    tax_year,
                    json.dumps(return_data, default=str),
                    calc_json,
                    session_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO session_tax_returns (
                        session_id, tenant_id, created_at, updated_at,
                        tax_year, return_data_json, calculated_results_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    tenant_id,
                    now,
                    now,
                    tax_year,
                    json.dumps(return_data, default=str),
                    calc_json
                ))

            conn.commit()

    def load_session_tax_return(
        self,
        session_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Load tax return data for a session.

        Args:
            session_id: Session identifier
            tenant_id: Optional tenant filter

        Returns:
            Tax return data dictionary or None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if tenant_id:
                cursor.execute("""
                    SELECT return_data_json, calculated_results_json, tax_year
                    FROM session_tax_returns
                    WHERE session_id = ? AND tenant_id = ?
                """, (session_id, tenant_id))
            else:
                cursor.execute("""
                    SELECT return_data_json, calculated_results_json, tax_year
                    FROM session_tax_returns
                    WHERE session_id = ?
                """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "return_data": json.loads(row[0]) if row[0] else {},
                "calculated_results": json.loads(row[1]) if row[1] else None,
                "tax_year": row[2]
            }

    def delete_session_tax_return(self, session_id: str) -> bool:
        """Delete tax return data for a session."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM session_tax_returns WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0


# Global instance
_session_persistence: Optional[SessionPersistence] = None


def get_session_persistence() -> SessionPersistence:
    """Get the global session persistence instance."""
    global _session_persistence
    if _session_persistence is None:
        _session_persistence = SessionPersistence()
    return _session_persistence
