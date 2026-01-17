"""
Onboarding Persistence Layer.

Provides database-backed persistence for interview, questionnaire, and document
collection state. Replaces in-memory state with SQLite storage to prevent
data loss on restart.

Prompt 1: Persistence Safety - Replace in-memory state with database-backed models.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


# Use same database path as main persistence
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"


@dataclass
class InterviewStateRecord:
    """Persisted interview state."""
    session_id: str
    current_stage: str
    started_at: Optional[str]
    last_activity: Optional[str]
    is_complete: bool
    collected_data: Dict[str, Any]
    detected_forms: List[str]
    estimated_refund: Optional[float]
    progress_percentage: float
    questionnaire_state: Dict[str, Any]


@dataclass
class DocumentRecord:
    """Persisted document record."""
    document_id: str
    session_id: str
    document_type: str
    status: str
    filename: Optional[str]
    uploaded_at: Optional[str]
    processed_at: Optional[str]
    tax_year: Optional[int]
    issuer_name: Optional[str]
    issuer_ein: Optional[str]
    recipient_name: Optional[str]
    overall_confidence: float
    fields: Dict[str, Any]
    fields_needing_review: List[str]
    extraction_warnings: List[str]
    raw_text: Optional[str]


class OnboardingPersistence:
    """
    Database-backed persistence for onboarding state.

    Ensures interview progress, questionnaire answers, and uploaded documents
    are not lost on application restart.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize persistence layer.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Interview state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interview_states (
                    session_id TEXT PRIMARY KEY,
                    current_stage TEXT NOT NULL DEFAULT 'welcome',
                    started_at TEXT,
                    last_activity TEXT,
                    is_complete INTEGER NOT NULL DEFAULT 0,
                    collected_data JSON NOT NULL DEFAULT '{}',
                    detected_forms JSON NOT NULL DEFAULT '[]',
                    estimated_refund REAL,
                    progress_percentage REAL NOT NULL DEFAULT 0.0,
                    questionnaire_state JSON NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS onboarding_documents (
                    document_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    filename TEXT,
                    uploaded_at TEXT,
                    processed_at TEXT,
                    tax_year INTEGER,
                    issuer_name TEXT,
                    issuer_ein TEXT,
                    recipient_name TEXT,
                    overall_confidence REAL DEFAULT 0.0,
                    fields JSON NOT NULL DEFAULT '{}',
                    fields_needing_review JSON NOT NULL DEFAULT '[]',
                    extraction_warnings JSON NOT NULL DEFAULT '[]',
                    raw_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Index for session lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_onboarding_docs_session
                ON onboarding_documents(session_id)
            """)

            conn.commit()

    # =========================================================================
    # INTERVIEW STATE PERSISTENCE
    # =========================================================================

    def save_interview_state(
        self,
        session_id: str,
        current_stage: str,
        started_at: Optional[str],
        last_activity: Optional[str],
        is_complete: bool,
        collected_data: Dict[str, Any],
        detected_forms: List[str],
        estimated_refund: Optional[float],
        progress_percentage: float,
        questionnaire_state: Dict[str, Any]
    ) -> None:
        """
        Save interview state to database.

        Args:
            session_id: Unique session identifier
            current_stage: Current interview stage
            started_at: When interview started
            last_activity: Last activity timestamp
            is_complete: Whether interview is complete
            collected_data: All collected interview data
            detected_forms: List of detected form types
            estimated_refund: Estimated refund amount
            progress_percentage: Progress percentage (0-100)
            questionnaire_state: Internal questionnaire engine state
        """
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if exists
            cursor.execute(
                "SELECT session_id FROM interview_states WHERE session_id = ?",
                (session_id,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE interview_states SET
                        current_stage = ?,
                        started_at = ?,
                        last_activity = ?,
                        is_complete = ?,
                        collected_data = ?,
                        detected_forms = ?,
                        estimated_refund = ?,
                        progress_percentage = ?,
                        questionnaire_state = ?,
                        updated_at = ?
                    WHERE session_id = ?
                """, (
                    current_stage,
                    started_at,
                    last_activity,
                    1 if is_complete else 0,
                    json.dumps(collected_data, default=str),
                    json.dumps(detected_forms),
                    estimated_refund,
                    progress_percentage,
                    json.dumps(questionnaire_state, default=str),
                    now,
                    session_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO interview_states (
                        session_id, current_stage, started_at, last_activity,
                        is_complete, collected_data, detected_forms,
                        estimated_refund, progress_percentage, questionnaire_state,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    current_stage,
                    started_at,
                    last_activity,
                    1 if is_complete else 0,
                    json.dumps(collected_data, default=str),
                    json.dumps(detected_forms),
                    estimated_refund,
                    progress_percentage,
                    json.dumps(questionnaire_state, default=str),
                    now,
                    now
                ))

            conn.commit()

    def load_interview_state(self, session_id: str) -> Optional[InterviewStateRecord]:
        """
        Load interview state from database.

        Args:
            session_id: Session identifier

        Returns:
            InterviewStateRecord or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, current_stage, started_at, last_activity,
                       is_complete, collected_data, detected_forms,
                       estimated_refund, progress_percentage, questionnaire_state
                FROM interview_states
                WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if row:
                return InterviewStateRecord(
                    session_id=row[0],
                    current_stage=row[1],
                    started_at=row[2],
                    last_activity=row[3],
                    is_complete=bool(row[4]),
                    collected_data=json.loads(row[5]) if row[5] else {},
                    detected_forms=json.loads(row[6]) if row[6] else [],
                    estimated_refund=row[7],
                    progress_percentage=row[8] or 0.0,
                    questionnaire_state=json.loads(row[9]) if row[9] else {}
                )
            return None

    def delete_interview_state(self, session_id: str) -> bool:
        """
        Delete interview state.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM interview_states WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # DOCUMENT PERSISTENCE
    # =========================================================================

    def save_document(
        self,
        document_id: str,
        session_id: str,
        document_type: str,
        status: str,
        filename: Optional[str] = None,
        uploaded_at: Optional[str] = None,
        processed_at: Optional[str] = None,
        tax_year: Optional[int] = None,
        issuer_name: Optional[str] = None,
        issuer_ein: Optional[str] = None,
        recipient_name: Optional[str] = None,
        overall_confidence: float = 0.0,
        fields: Optional[Dict[str, Any]] = None,
        fields_needing_review: Optional[List[str]] = None,
        extraction_warnings: Optional[List[str]] = None,
        raw_text: Optional[str] = None
    ) -> None:
        """
        Save document to database.

        Args:
            document_id: Unique document identifier
            session_id: Session this document belongs to
            document_type: Type of tax document
            status: Processing status
            filename: Original filename
            uploaded_at: Upload timestamp
            processed_at: Processing completion timestamp
            tax_year: Tax year of document
            issuer_name: Document issuer name
            issuer_ein: Issuer EIN
            recipient_name: Recipient name
            overall_confidence: OCR confidence score
            fields: Extracted fields
            fields_needing_review: Fields requiring review
            extraction_warnings: Any extraction warnings
            raw_text: Raw OCR text
        """
        now = datetime.utcnow().isoformat()
        fields = fields or {}
        fields_needing_review = fields_needing_review or []
        extraction_warnings = extraction_warnings or []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if exists
            cursor.execute(
                "SELECT document_id FROM onboarding_documents WHERE document_id = ?",
                (document_id,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE onboarding_documents SET
                        session_id = ?,
                        document_type = ?,
                        status = ?,
                        filename = ?,
                        uploaded_at = ?,
                        processed_at = ?,
                        tax_year = ?,
                        issuer_name = ?,
                        issuer_ein = ?,
                        recipient_name = ?,
                        overall_confidence = ?,
                        fields = ?,
                        fields_needing_review = ?,
                        extraction_warnings = ?,
                        raw_text = ?,
                        updated_at = ?
                    WHERE document_id = ?
                """, (
                    session_id,
                    document_type,
                    status,
                    filename,
                    uploaded_at,
                    processed_at,
                    tax_year,
                    issuer_name,
                    issuer_ein,
                    recipient_name,
                    overall_confidence,
                    json.dumps(fields, default=str),
                    json.dumps(fields_needing_review),
                    json.dumps(extraction_warnings),
                    raw_text,
                    now,
                    document_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO onboarding_documents (
                        document_id, session_id, document_type, status,
                        filename, uploaded_at, processed_at, tax_year,
                        issuer_name, issuer_ein, recipient_name,
                        overall_confidence, fields, fields_needing_review,
                        extraction_warnings, raw_text, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document_id,
                    session_id,
                    document_type,
                    status,
                    filename,
                    uploaded_at,
                    processed_at,
                    tax_year,
                    issuer_name,
                    issuer_ein,
                    recipient_name,
                    overall_confidence,
                    json.dumps(fields, default=str),
                    json.dumps(fields_needing_review),
                    json.dumps(extraction_warnings),
                    raw_text,
                    now,
                    now
                ))

            conn.commit()

    def load_document(self, document_id: str) -> Optional[DocumentRecord]:
        """
        Load a document by ID.

        Args:
            document_id: Document identifier

        Returns:
            DocumentRecord or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT document_id, session_id, document_type, status,
                       filename, uploaded_at, processed_at, tax_year,
                       issuer_name, issuer_ein, recipient_name,
                       overall_confidence, fields, fields_needing_review,
                       extraction_warnings, raw_text
                FROM onboarding_documents
                WHERE document_id = ?
            """, (document_id,))

            row = cursor.fetchone()
            if row:
                return DocumentRecord(
                    document_id=row[0],
                    session_id=row[1],
                    document_type=row[2],
                    status=row[3],
                    filename=row[4],
                    uploaded_at=row[5],
                    processed_at=row[6],
                    tax_year=row[7],
                    issuer_name=row[8],
                    issuer_ein=row[9],
                    recipient_name=row[10],
                    overall_confidence=row[11] or 0.0,
                    fields=json.loads(row[12]) if row[12] else {},
                    fields_needing_review=json.loads(row[13]) if row[13] else [],
                    extraction_warnings=json.loads(row[14]) if row[14] else [],
                    raw_text=row[15]
                )
            return None

    def load_session_documents(self, session_id: str) -> List[DocumentRecord]:
        """
        Load all documents for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of DocumentRecord objects
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT document_id, session_id, document_type, status,
                       filename, uploaded_at, processed_at, tax_year,
                       issuer_name, issuer_ein, recipient_name,
                       overall_confidence, fields, fields_needing_review,
                       extraction_warnings, raw_text
                FROM onboarding_documents
                WHERE session_id = ?
                ORDER BY uploaded_at DESC
            """, (session_id,))

            documents = []
            for row in cursor.fetchall():
                documents.append(DocumentRecord(
                    document_id=row[0],
                    session_id=row[1],
                    document_type=row[2],
                    status=row[3],
                    filename=row[4],
                    uploaded_at=row[5],
                    processed_at=row[6],
                    tax_year=row[7],
                    issuer_name=row[8],
                    issuer_ein=row[9],
                    recipient_name=row[10],
                    overall_confidence=row[11] or 0.0,
                    fields=json.loads(row[12]) if row[12] else {},
                    fields_needing_review=json.loads(row[13]) if row[13] else [],
                    extraction_warnings=json.loads(row[14]) if row[14] else [],
                    raw_text=row[15]
                ))
            return documents

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document.

        Args:
            document_id: Document identifier

        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM onboarding_documents WHERE document_id = ?",
                (document_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_session_documents(self, session_id: str) -> int:
        """
        Delete all documents for a session.

        Args:
            session_id: Session identifier

        Returns:
            Number of documents deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM onboarding_documents WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
            return cursor.rowcount


# Global instance for convenience
_onboarding_persistence: Optional[OnboardingPersistence] = None


def get_onboarding_persistence() -> OnboardingPersistence:
    """Get the global onboarding persistence instance."""
    global _onboarding_persistence
    if _onboarding_persistence is None:
        _onboarding_persistence = OnboardingPersistence()
    return _onboarding_persistence
