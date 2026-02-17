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
from .unified_session import UnifiedFilingSession

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
        """Create tables if they don't exist.

        NOTE: These tables should be created via Alembic migration
        (20260205_0002_session_tables.py). This method is kept as a
        safety net for environments where migrations haven't been run.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if tables already exist (created by Alembic)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_states'")
            if cursor.fetchone():
                # Tables exist — skip runtime creation, just do ALTER TABLE safety checks
                for column, coldef in [
                    ("user_id", "TEXT"),
                    ("is_anonymous", "INTEGER DEFAULT 1"),
                    ("workflow_type", "TEXT"),
                    ("return_id", "TEXT")
                ]:
                    try:
                        cursor.execute(f"ALTER TABLE session_states ADD COLUMN {column} {coldef}")
                    except sqlite3.OperationalError:
                        pass  # Column already exists

                # Ensure optimistic locking support exists
                try:
                    cursor.execute("ALTER TABLE session_tax_returns ADD COLUMN version INTEGER NOT NULL DEFAULT 0")
                except sqlite3.OperationalError:
                    pass  # Column already exists or table missing (handled by migrations)

                # Ensure anonymous->authenticated transfer audit table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_transfers (
                        transfer_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        from_anonymous INTEGER NOT NULL DEFAULT 1,
                        to_user_id TEXT NOT NULL,
                        transferred_at TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES session_states(session_id)
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_transfers_session
                    ON session_transfers(session_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_transfers_user
                    ON session_transfers(to_user_id)
                """)
                conn.commit()
                return

            logger.warning(
                "Session tables not found — creating via runtime fallback. "
                "Run 'alembic upgrade head' to use the canonical migration path."
            )

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
                    agent_state_blob BLOB,
                    user_id TEXT,
                    is_anonymous INTEGER DEFAULT 1,
                    workflow_type TEXT,
                    return_id TEXT
                )
            """)

            # Add missing columns to existing tables (migration for existing DBs)
            for column, coldef in [
                ("user_id", "TEXT"),
                ("is_anonymous", "INTEGER DEFAULT 1"),
                ("workflow_type", "TEXT"),
                ("return_id", "TEXT")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE session_states ADD COLUMN {column} {coldef}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

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
                    version INTEGER NOT NULL DEFAULT 0,
                    calculated_results_json TEXT,
                    FOREIGN KEY (session_id) REFERENCES session_states(session_id)
                )
            """)

            # Session transfer audit table (anonymous -> authenticated)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_transfers (
                    transfer_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    from_anonymous INTEGER NOT NULL DEFAULT 1,
                    to_user_id TEXT NOT NULL,
                    transferred_at TEXT NOT NULL,
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_transfers_session
                ON session_transfers(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_transfers_user
                ON session_transfers(to_user_id)
            """)

            # =================================================================
            # AUDIT TRAILS TABLE - CPA COMPLIANCE REQUIREMENT
            # =================================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_trails (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    trail_json TEXT NOT NULL,
                    entry_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES session_states(session_id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_tenant
                ON audit_trails(tenant_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_updated
                ON audit_trails(updated_at)
            """)

            # =================================================================
            # RETURN STATUS TABLE - CPA APPROVAL WORKFLOW
            # =================================================================
            # Tracks: DRAFT → IN_REVIEW → CPA_APPROVED status per return
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS return_status (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    status TEXT NOT NULL DEFAULT 'DRAFT',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_status_change TEXT NOT NULL,
                    cpa_reviewer_id TEXT,
                    cpa_reviewer_name TEXT,
                    review_notes TEXT,
                    approval_timestamp TEXT,
                    approval_signature_hash TEXT,
                    FOREIGN KEY (session_id) REFERENCES session_states(session_id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_return_status_tenant
                ON return_status(tenant_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_return_status_status
                ON return_status(status)
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
        agent_state: Optional[bytes] = None,
        user_id: Optional[str] = None,
        is_anonymous: bool = True,
        workflow_type: Optional[str] = None,
        return_id: Optional[str] = None
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
            user_id: User ID for authenticated sessions (NEW)
            is_anonymous: Whether session is anonymous (NEW)
            workflow_type: Workflow type ('express', 'smart', 'chat', 'guided') (NEW)
            return_id: Link to TaxReturnRecord when filing complete (NEW)
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
                        agent_state_blob = ?,
                        user_id = ?,
                        is_anonymous = ?,
                        workflow_type = ?,
                        return_id = ?
                    WHERE session_id = ?
                """, (
                    tenant_id,
                    session_type,
                    now.isoformat(),
                    expires_at.isoformat(),
                    json.dumps(data, default=str),
                    json.dumps(metadata, default=str),
                    agent_state,
                    user_id,
                    1 if is_anonymous else 0,
                    workflow_type,
                    return_id,
                    session_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO session_states (
                        session_id, tenant_id, session_type,
                        created_at, last_activity, expires_at,
                        data_json, metadata_json, agent_state_blob,
                        user_id, is_anonymous, workflow_type, return_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    tenant_id,
                    session_type,
                    now.isoformat(),
                    now.isoformat(),
                    expires_at.isoformat(),
                    json.dumps(data, default=str),
                    json.dumps(metadata, default=str),
                    agent_state,
                    user_id,
                    1 if is_anonymous else 0,
                    workflow_type,
                    return_id
                ))

            conn.commit()

    def save_session_state(
        self,
        session_id: str,
        state_data: Dict[str, Any],
        tenant_id: str = "default",
        session_type: str = "agent",
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        is_anonymous: Optional[bool] = None,
        workflow_type: Optional[str] = None,
        return_id: Optional[str] = None,
    ) -> None:
        """
        Backward-compatible wrapper for legacy callers that expect save_session_state().
        """
        data = state_data or {}
        resolved_user_id = user_id if user_id is not None else data.get("user_id")

        resolved_is_anonymous = is_anonymous
        if resolved_is_anonymous is None:
            if "is_anonymous" in data:
                resolved_is_anonymous = bool(data.get("is_anonymous"))
            else:
                resolved_is_anonymous = resolved_user_id is None

        resolved_workflow_type = workflow_type or data.get("workflow_type")
        resolved_return_id = return_id or data.get("return_id")

        self.save_session(
            session_id=session_id,
            tenant_id=tenant_id,
            session_type=session_type,
            data=data,
            metadata=metadata or {},
            user_id=resolved_user_id,
            is_anonymous=resolved_is_anonymous,
            workflow_type=resolved_workflow_type,
            return_id=resolved_return_id,
        )

    def load_session_state(
        self,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Backward-compatible wrapper for legacy callers that expect load_session_state().
        """
        record = self.load_session(session_id, tenant_id=tenant_id)
        if not record:
            return None

        data = dict(record.data or {})
        data.setdefault("session_id", record.session_id)
        data.setdefault("created_at", record.created_at)
        data.setdefault("updated_at", record.last_activity)
        data.setdefault("last_updated", record.last_activity)
        data.setdefault("workflow_type", record.session_type)

        if "user_id" not in data and record.metadata.get("user_id"):
            data["user_id"] = record.metadata["user_id"]
        if "is_anonymous" not in data:
            data["is_anonymous"] = data.get("user_id") is None

        return data

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

    def cleanup_expired_sessions(self, batch_size: int = 500) -> int:
        """
        Remove all expired sessions in batches to prevent memory issues.

        PERFORMANCE: Uses batched deletion to avoid loading all expired
        session IDs into memory at once, which can cause OOM errors
        when many sessions have expired.

        Args:
            batch_size: Number of sessions to delete per batch (default: 500)

        Returns:
            Total number of sessions deleted
        """
        now = datetime.utcnow().isoformat()
        total_deleted = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            while True:
                # Get batch of expired session IDs (with LIMIT for pagination)
                cursor.execute(
                    "SELECT session_id FROM session_states WHERE expires_at < ? LIMIT ?",
                    (now, batch_size)
                )
                expired_ids = [row[0] for row in cursor.fetchall()]

                if not expired_ids:
                    break

                # Delete related data for this batch
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
                total_deleted += len(expired_ids)

                # Log progress for large cleanups
                if total_deleted % 1000 == 0:
                    logger.info(f"Cleanup progress: {total_deleted} sessions deleted")

        if total_deleted > 0:
            logger.info(f"Cleanup complete: {total_deleted} expired sessions deleted")

        return total_deleted

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

    def delete_session_tax_return(self, session_id: str, tenant_id: str = "default") -> bool:
        """Delete tax return data for a session."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM session_tax_returns WHERE session_id = ? AND tenant_id = ?",
                (session_id, tenant_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # AUDIT TRAIL METHODS - CPA COMPLIANCE REQUIREMENT
    # =========================================================================

    def save_audit_trail(
        self,
        session_id: str,
        trail_json: str,
        tenant_id: str = "default"
    ) -> None:
        """
        Save or update an audit trail for a session.

        CPA COMPLIANCE: All audit trails must be persisted for defensibility.

        Args:
            session_id: Session/return identifier
            trail_json: JSON-serialized audit trail
            tenant_id: Tenant identifier for isolation
        """
        now = datetime.utcnow().isoformat()

        # Count entries from JSON
        try:
            trail_data = json.loads(trail_json)
            entry_count = len(trail_data.get('entries', []))
        except (json.JSONDecodeError, KeyError):
            entry_count = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT session_id FROM audit_trails WHERE session_id = ?",
                (session_id,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE audit_trails SET
                        updated_at = ?,
                        trail_json = ?,
                        entry_count = ?
                    WHERE session_id = ?
                """, (now, trail_json, entry_count, session_id))
            else:
                cursor.execute("""
                    INSERT INTO audit_trails
                    (session_id, tenant_id, created_at, updated_at, trail_json, entry_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, tenant_id, now, now, trail_json, entry_count))

            conn.commit()

    def load_audit_trail(
        self,
        session_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Load audit trail JSON for a session.

        Args:
            session_id: Session/return identifier
            tenant_id: Optional tenant filter for isolation

        Returns:
            JSON string of audit trail, or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # SECURITY: Always require tenant_id for multi-tenant isolation
            cursor.execute("""
                SELECT trail_json FROM audit_trails
                WHERE session_id = ? AND tenant_id = ?
            """, (session_id, tenant_id))

            row = cursor.fetchone()
            return row[0] if row else None

    def get_audit_trail_summary(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get summary info about an audit trail without loading full JSON.

        Returns:
            Dict with created_at, updated_at, entry_count, or None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT created_at, updated_at, entry_count, tenant_id
                FROM audit_trails
                WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "session_id": session_id,
                "created_at": row[0],
                "updated_at": row[1],
                "entry_count": row[2],
                "tenant_id": row[3]
            }

    def list_audit_trails(
        self,
        tenant_id: str = "default",
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List audit trail summaries for a tenant.

        Returns:
            List of audit trail summary dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, created_at, updated_at, entry_count
                FROM audit_trails
                WHERE tenant_id = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """, (tenant_id, limit, offset))

            return [
                {
                    "session_id": row[0],
                    "created_at": row[1],
                    "updated_at": row[2],
                    "entry_count": row[3]
                }
                for row in cursor.fetchall()
            ]

    # =========================================================================
    # RETURN STATUS METHODS - CPA APPROVAL WORKFLOW
    # =========================================================================

    def get_return_status(
        self,
        session_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a return.

        CPA COMPLIANCE: Returns status controls feature access.

        Args:
            session_id: Session/return identifier
            tenant_id: Optional tenant filter

        Returns:
            Dict with status info, or None if no status exists
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if tenant_id:
                cursor.execute("""
                    SELECT status, created_at, updated_at, last_status_change,
                           cpa_reviewer_id, cpa_reviewer_name, review_notes,
                           approval_timestamp, approval_signature_hash
                    FROM return_status
                    WHERE session_id = ? AND tenant_id = ?
                """, (session_id, tenant_id))
            else:
                cursor.execute("""
                    SELECT status, created_at, updated_at, last_status_change,
                           cpa_reviewer_id, cpa_reviewer_name, review_notes,
                           approval_timestamp, approval_signature_hash
                    FROM return_status
                    WHERE session_id = ?
                """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "session_id": session_id,
                "status": row[0],
                "created_at": row[1],
                "updated_at": row[2],
                "last_status_change": row[3],
                "cpa_reviewer_id": row[4],
                "cpa_reviewer_name": row[5],
                "review_notes": row[6],
                "approval_timestamp": row[7],
                "approval_signature_hash": row[8],
            }

    def set_return_status(
        self,
        session_id: str,
        status: str,
        tenant_id: str = "default",
        cpa_reviewer_id: Optional[str] = None,
        cpa_reviewer_name: Optional[str] = None,
        review_notes: Optional[str] = None,
        approval_signature_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Set or update the status of a return.

        CPA COMPLIANCE: Status transitions are audited.

        Valid statuses:
        - DRAFT: Initial state, editable
        - IN_REVIEW: Submitted for CPA review, read-only to taxpayer
        - CPA_APPROVED: Signed off by CPA, full feature access

        Args:
            session_id: Session/return identifier
            status: New status (DRAFT, IN_REVIEW, CPA_APPROVED)
            tenant_id: Tenant identifier
            cpa_reviewer_id: ID of reviewing CPA (for IN_REVIEW/CPA_APPROVED)
            cpa_reviewer_name: Name of reviewing CPA
            review_notes: CPA notes/comments
            approval_signature_hash: Hash for CPA_APPROVED signature

        Returns:
            Updated status record
        """
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT session_id, status FROM return_status WHERE session_id = ?",
                (session_id,)
            )
            existing = cursor.fetchone()

            if existing:
                old_status = existing[1]
                # Build dynamic update
                updates = ["status = ?", "updated_at = ?", "last_status_change = ?"]
                params = [status, now, now]

                if cpa_reviewer_id is not None:
                    updates.append("cpa_reviewer_id = ?")
                    params.append(cpa_reviewer_id)
                if cpa_reviewer_name is not None:
                    updates.append("cpa_reviewer_name = ?")
                    params.append(cpa_reviewer_name)
                if review_notes is not None:
                    updates.append("review_notes = ?")
                    params.append(review_notes)
                if status == "CPA_APPROVED":
                    updates.append("approval_timestamp = ?")
                    params.append(now)
                    if approval_signature_hash:
                        updates.append("approval_signature_hash = ?")
                        params.append(approval_signature_hash)

                params.append(session_id)
                cursor.execute(
                    f"UPDATE return_status SET {', '.join(updates)} WHERE session_id = ?",
                    params
                )
            else:
                approval_ts = now if status == "CPA_APPROVED" else None
                cursor.execute("""
                    INSERT INTO return_status
                    (session_id, tenant_id, status, created_at, updated_at,
                     last_status_change, cpa_reviewer_id, cpa_reviewer_name,
                     review_notes, approval_timestamp, approval_signature_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, tenant_id, status, now, now, now,
                    cpa_reviewer_id, cpa_reviewer_name, review_notes,
                    approval_ts, approval_signature_hash
                ))

            conn.commit()

        return self.get_return_status(session_id, tenant_id)

    def list_returns_by_status(
        self,
        status: str,
        tenant_id: str = "default",
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List returns by status for CPA workflow.

        Args:
            status: Filter by status (DRAFT, IN_REVIEW, CPA_APPROVED)
            tenant_id: Tenant identifier
            limit: Max results
            offset: Pagination offset

        Returns:
            List of return status records
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, status, created_at, updated_at,
                       last_status_change, cpa_reviewer_name
                FROM return_status
                WHERE status = ? AND tenant_id = ?
                ORDER BY last_status_change DESC
                LIMIT ? OFFSET ?
            """, (status, tenant_id, limit, offset))

            return [
                {
                    "session_id": row[0],
                    "status": row[1],
                    "created_at": row[2],
                    "updated_at": row[3],
                    "last_status_change": row[4],
                    "cpa_reviewer_name": row[5]
                }
                for row in cursor.fetchall()
            ]

    # =========================================================================
    # UNIFIED SESSION METHODS - NEW UNIFIED FILING PLATFORM
    # =========================================================================

    def save_unified_session(
        self,
        session: UnifiedFilingSession,
        tenant_id: str = "default"
    ) -> None:
        """
        Save unified filing session to database.

        This replaces workflow-specific session saves.

        Args:
            session: UnifiedFilingSession instance
            tenant_id: Tenant identifier
        """
        # Convert session to dict for storage
        session_dict = session.to_dict()

        # Save to session_states with new fields
        self.save_session(
            session_id=session.session_id,
            tenant_id=tenant_id,
            session_type="unified_filing",
            data=session_dict,
            metadata=session.metadata,
            user_id=session.user_id,
            is_anonymous=session.is_anonymous,
            workflow_type=session.workflow_type.value,
            return_id=session.return_id
        )

        # Also save tax return data if present
        if session.user_confirmed_data or session.calculated_results:
            return_data = {**session.extracted_data, **session.user_confirmed_data}
            self.save_session_tax_return(
                session_id=session.session_id,
                tenant_id=tenant_id,
                tax_year=session.tax_year,
                return_data=return_data,
                calculated_results=session.calculated_results
            )

    def load_unified_session(
        self,
        session_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[UnifiedFilingSession]:
        """
        Load unified filing session from database.

        Args:
            session_id: Session identifier
            tenant_id: Optional tenant filter

        Returns:
            UnifiedFilingSession or None if not found/expired
        """
        # Load session record
        session_record = self.load_session(session_id, tenant_id)
        if not session_record:
            return None

        # Load session data
        try:
            session = UnifiedFilingSession.from_dict(session_record.data)
            return session
        except Exception as e:
            logger.error(f"Failed to deserialize unified session {session_id}: {e}")
            return None

    def get_user_sessions(
        self,
        user_id: str,
        workflow_type: Optional[str] = None,
        tax_year: Optional[int] = None
    ) -> List[UnifiedFilingSession]:
        """
        Get all active sessions for a user.

        Args:
            user_id: User identifier
            workflow_type: Optional filter by workflow type
            tax_year: Optional filter by tax year

        Returns:
            List of UnifiedFilingSession objects
        """
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = """
                SELECT session_id, data_json
                FROM session_states
                WHERE user_id = ? AND expires_at > ?
            """
            params = [user_id, now]

            if workflow_type:
                query += " AND workflow_type = ?"
                params.append(workflow_type)

            query += " ORDER BY last_activity DESC"

            cursor.execute(query, params)

            sessions = []
            for row in cursor.fetchall():
                try:
                    session_data = json.loads(row[1])
                    session = UnifiedFilingSession.from_dict(session_data)

                    # Filter by tax year if specified
                    if tax_year and session.tax_year != tax_year:
                        continue

                    sessions.append(session)
                except Exception as e:
                    logger.error(f"Failed to load session {row[0]}: {e}")
                    continue

            return sessions

    def transfer_session_to_user(
        self,
        session_id: str,
        user_id: str,
        tenant_id: str = "default"
    ) -> bool:
        """
        Transfer an anonymous session to an authenticated user.

        This is used when a user logs in after starting an anonymous filing session.

        Args:
            session_id: Session to transfer
            user_id: User to transfer to
            tenant_id: Tenant identifier

        Returns:
            True if successful, False otherwise
        """
        now = datetime.utcnow().isoformat()
        transfer_id = str(uuid.uuid4())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if session exists and is anonymous
            cursor.execute("""
                SELECT is_anonymous FROM session_states
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()

            if not row:
                logger.warning(f"Session {session_id} not found for transfer")
                return False

            if row[0] != 1:
                logger.warning(f"Session {session_id} is not anonymous")
                return False

            # Update session to authenticated
            cursor.execute("""
                UPDATE session_states SET
                    user_id = ?,
                    is_anonymous = 0
                WHERE session_id = ?
            """, (user_id, session_id))

            # Record transfer for audit
            cursor.execute("""
                INSERT INTO session_transfers
                (transfer_id, session_id, from_anonymous, to_user_id, transferred_at)
                VALUES (?, ?, 1, ?, ?)
            """, (transfer_id, session_id, user_id, now))

            conn.commit()
            return True

    def save_with_version(
        self,
        session: UnifiedFilingSession,
        expected_version: int,
        tenant_id: str = "default"
    ) -> bool:
        """
        Save session with optimistic locking.

        Args:
            session: UnifiedFilingSession to save
            expected_version: Expected current version
            tenant_id: Tenant identifier

        Returns:
            True if saved successfully, False if version conflict
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Load current tax return to check version
            cursor.execute("""
                SELECT version FROM session_tax_returns
                WHERE session_id = ?
            """, (session.session_id,))
            row = cursor.fetchone()

            if row:
                current_version = row[0]
                if current_version != expected_version:
                    logger.warning(
                        f"Version conflict for session {session.session_id}: "
                        f"expected {expected_version}, current {current_version}"
                    )
                    return False

                # Update with incremented version
                new_version = current_version + 1
                cursor.execute("""
                    UPDATE session_tax_returns SET
                        version = ?,
                        updated_at = ?,
                        return_data_json = ?
                    WHERE session_id = ? AND version = ?
                """, (
                    new_version,
                    datetime.utcnow().isoformat(),
                    json.dumps({**session.extracted_data, **session.user_confirmed_data}, default=str),
                    session.session_id,
                    expected_version
                ))

                if cursor.rowcount == 0:
                    return False

                session.version = new_version
            else:
                # No existing return, create with version 0
                session.version = 0

            # Save the session
            self.save_unified_session(session, tenant_id)
            conn.commit()
            return True

    def check_active_session(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if user has an active session.

        Used for the "resume banner" on landing page.

        Args:
            user_id: User to check (if authenticated)
            session_id: Session ID to check (if anonymous)

        Returns:
            Dict with session info if active, None otherwise
        """
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if user_id:
                # Check for authenticated user's sessions
                cursor.execute("""
                    SELECT session_id, workflow_type, data_json
                    FROM session_states
                    WHERE user_id = ? AND expires_at > ?
                    ORDER BY last_activity DESC
                    LIMIT 1
                """, (user_id, now))
            elif session_id:
                # Check specific session
                cursor.execute("""
                    SELECT session_id, workflow_type, data_json
                    FROM session_states
                    WHERE session_id = ? AND expires_at > ?
                """, (session_id, now))
            else:
                return None

            row = cursor.fetchone()
            if not row:
                return None

            try:
                session_data = json.loads(row[2])
                return {
                    "session_id": row[0],
                    "workflow_type": row[1],
                    "state": session_data.get("state"),
                    "tax_year": session_data.get("tax_year"),
                    "completeness_score": session_data.get("completeness_score", 0)
                }
            except Exception as e:
                logger.error(f"Failed to parse session data: {e}")
                return None


# Global instance
_session_persistence: Optional[SessionPersistence] = None

# Configuration for session storage backend
# Set SESSION_STORAGE_TYPE=redis to use Redis (requires Redis to be available)
# Default is 'sqlite' for backward compatibility
import os
_SESSION_STORAGE_TYPE = os.environ.get("SESSION_STORAGE_TYPE", "sqlite").lower()


def get_session_persistence() -> SessionPersistence:
    """
    Get the global session persistence instance.

    Uses Redis if SESSION_STORAGE_TYPE=redis and Redis is available,
    otherwise falls back to SQLite (default).

    Environment variables:
        SESSION_STORAGE_TYPE: 'redis' or 'sqlite' (default: 'sqlite')

    Returns:
        SessionPersistence instance (SQLite-based)

    Note:
        For async Redis operations, use get_redis_session_persistence()
        from database.redis_session_persistence instead.
    """
    global _session_persistence
    if _session_persistence is None:
        if _SESSION_STORAGE_TYPE == "redis":
            logger.info("SESSION_STORAGE_TYPE=redis, but sync persistence requires SQLite. "
                       "Use async get_redis_session_persistence() for Redis operations.")
        _session_persistence = SessionPersistence()
    return _session_persistence


async def get_async_session_persistence():
    """
    Get async session persistence - Redis if available, else SQLite wrapper.

    This is the preferred method for async code paths. Returns Redis
    persistence if available, otherwise wraps SQLite persistence.

    Returns:
        Redis or SQLite session persistence
    """
    if _SESSION_STORAGE_TYPE == "redis":
        try:
            from database.redis_session_persistence import get_redis_session_persistence
            redis_persistence = await get_redis_session_persistence()
            if redis_persistence:
                return redis_persistence
            logger.warning("Redis session persistence unavailable, falling back to SQLite")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis session persistence: {e}")

    # Fallback to SQLite
    return get_session_persistence()
