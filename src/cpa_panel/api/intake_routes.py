"""
CPA Panel Intake Routes

API endpoints for client intake management, enabling CPAs to
initiate, track, and complete client onboarding.

Now with REAL database persistence - no mocks!
"""

from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging
import uuid
import json
import os
from datetime import datetime
from pathlib import Path

from .common import get_tenant_id, format_success_response, format_error_response, ErrorCode, log_and_raise_http_error
from ..security import (
    sanitize_filename,
    validate_session_id,
    validate_file_upload,
    get_safe_error_message,
    MAX_FILE_SIZE,
)

logger = logging.getLogger(__name__)

intake_router = APIRouter(tags=["Client Intake"])

# Document storage path
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_db_connection():
    """Get database connection."""
    import sqlite3
    db_path = Path(__file__).parent.parent.parent / "database" / "jorss_gbo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables_exist():
    """Ensure necessary tables exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clients table (if not exists)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT UNIQUE NOT NULL,
            session_id TEXT,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone TEXT,
            address_json TEXT,
            filing_status TEXT,
            tax_year INTEGER DEFAULT 2025,
            profile_type TEXT DEFAULT 'new_client',
            complexity TEXT DEFAULT 'simple',
            state_code TEXT,
            state_name TEXT,
            state_tax_rate REAL DEFAULT 0,
            spouse_json TEXT,
            dependents_json TEXT,
            base_income INTEGER DEFAULT 0,
            consent_given INTEGER DEFAULT 0,
            consent_timestamp TEXT,
            status TEXT DEFAULT 'DRAFT',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT UNIQUE NOT NULL,
            session_id TEXT NOT NULL,
            client_id TEXT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER,
            file_type TEXT,
            document_type TEXT,
            storage_path TEXT,
            status TEXT DEFAULT 'uploaded',
            ocr_status TEXT DEFAULT 'pending',
            ocr_result_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Intake sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intake_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            tenant_id TEXT DEFAULT 'default',
            status TEXT DEFAULT 'in_progress',
            current_stage TEXT DEFAULT 'welcome',
            stages_completed_json TEXT DEFAULT '[]',
            answers_json TEXT DEFAULT '{}',
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )
    """)

    # ==========================================================================
    # CPA PROFILES TABLE - Multi-tenant CPA branding
    # ==========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cpa_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpa_id TEXT UNIQUE NOT NULL,
            cpa_slug TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            credentials TEXT,
            firm_name TEXT,
            logo_url TEXT,
            email TEXT,
            phone TEXT,
            booking_link TEXT,
            address TEXT,
            bio TEXT,
            specialties_json TEXT DEFAULT '[]',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ==========================================================================
    # LEAD MAGNET SESSIONS TABLE - Tracks assessment sessions
    # ==========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lead_magnet_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            cpa_id TEXT,
            cpa_slug TEXT,
            assessment_mode TEXT DEFAULT 'quick',
            current_screen TEXT DEFAULT 'welcome',
            privacy_consent INTEGER DEFAULT 0,
            profile_data_json TEXT DEFAULT '{}',
            contact_captured INTEGER DEFAULT 0,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            time_spent_seconds INTEGER DEFAULT 0,
            referral_source TEXT,
            FOREIGN KEY (cpa_id) REFERENCES cpa_profiles(cpa_id)
        )
    """)

    # ==========================================================================
    # LEAD MAGNET LEADS TABLE - Captured leads with scoring
    # ==========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lead_magnet_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id TEXT UNIQUE NOT NULL,
            session_id TEXT NOT NULL,
            cpa_id TEXT,
            first_name TEXT,
            email TEXT NOT NULL,
            phone TEXT,
            filing_status TEXT,
            complexity TEXT DEFAULT 'simple',
            income_range TEXT,
            lead_score INTEGER DEFAULT 50,
            lead_temperature TEXT DEFAULT 'warm',
            estimated_engagement_value REAL DEFAULT 0,
            conversion_probability REAL DEFAULT 0.5,
            savings_range_low REAL DEFAULT 0,
            savings_range_high REAL DEFAULT 0,
            engaged INTEGER DEFAULT 0,
            engaged_at TEXT,
            engagement_letter_acknowledged INTEGER DEFAULT 0,
            engagement_letter_acknowledged_at TEXT,
            converted INTEGER DEFAULT 0,
            converted_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES lead_magnet_sessions(session_id),
            FOREIGN KEY (cpa_id) REFERENCES cpa_profiles(cpa_id)
        )
    """)

    # ==========================================================================
    # TIERED REPORTS TABLE - Stores generated reports
    # ==========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiered_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT UNIQUE NOT NULL,
            session_id TEXT NOT NULL,
            lead_id TEXT,
            cpa_id TEXT,
            report_tier INTEGER DEFAULT 1,
            report_html TEXT,
            report_data_json TEXT,
            insights_shown INTEGER DEFAULT 3,
            total_insights INTEGER DEFAULT 0,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES lead_magnet_sessions(session_id),
            FOREIGN KEY (lead_id) REFERENCES lead_magnet_leads(lead_id)
        )
    """)

    conn.commit()
    conn.close()


def get_intake_service():
    """Get the intake service singleton."""
    from cpa_panel.services.intake_service import get_intake_service
    return get_intake_service()


# Ensure tables exist on module load
ensure_tables_exist()


# =============================================================================
# INTAKE MANAGEMENT - REAL DATABASE PERSISTENCE
# =============================================================================

@intake_router.post("/clients/intake/start")
async def start_intake(request: Request):
    """
    Start a new client intake session with REAL database persistence.

    Request body:
        - first_name, last_name, email: Client information (optional)
        - filing_status: Filing status (optional)
        - tax_year: Tax year (default 2025)
        - consent: Whether consent was given

    Creates a new session and client record in the database.
    Returns session_id for tracking.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    tenant_id = get_tenant_id(request)
    now = datetime.utcnow().isoformat()

    # Generate unique IDs
    session_id = body.get("session_id") or f"session-{uuid.uuid4().hex[:12]}"
    client_id = f"client-{uuid.uuid4().hex[:12]}"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create intake session
        cursor.execute("""
            INSERT OR REPLACE INTO intake_sessions (
                session_id, tenant_id, status, current_stage,
                stages_completed_json, answers_json, started_at, last_activity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            tenant_id,
            "in_progress",
            "welcome",
            "[]",
            json.dumps(body),
            now,
            now
        ))

        # Create client record (only columns that exist in the schema)
        cursor.execute("""
            INSERT OR REPLACE INTO clients (
                client_id, session_id, first_name, last_name, email, phone,
                filing_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            session_id,
            body.get("first_name", ""),
            body.get("last_name", ""),
            body.get("email", ""),
            body.get("phone", ""),
            body.get("filing_status", ""),
            now,
            now
        ))

        conn.commit()
        conn.close()

        logger.info(f"Created intake session {session_id} for client {client_id}")

        return format_success_response({
            "session_id": session_id,
            "client_id": client_id,
            "status": "in_progress",
            "current_stage": "welcome",
            "created_at": now,
            "message": "Intake session created successfully",
        })

    except Exception as e:
        log_and_raise_http_error(e, category="db", context="starting intake")


@intake_router.post("/clients/{session_id}/info")
async def save_client_info(session_id: str, request: Request):
    """
    Save or update client information.

    Persists client data to the database.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    now = datetime.utcnow().isoformat()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if client exists for this session
        cursor.execute("SELECT client_id FROM clients WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()

        if row:
            # Update existing client
            client_id = row["client_id"]
            cursor.execute("""
                UPDATE clients SET
                    first_name = COALESCE(?, first_name),
                    last_name = COALESCE(?, last_name),
                    email = COALESCE(?, email),
                    phone = COALESCE(?, phone),
                    filing_status = COALESCE(?, filing_status),
                    updated_at = ?
                WHERE session_id = ?
            """, (
                body.get("first_name"),
                body.get("last_name"),
                body.get("email"),
                body.get("phone"),
                body.get("filing_status"),
                now,
                session_id
            ))
        else:
            # Create new client
            client_id = f"client-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO clients (
                    client_id, session_id, first_name, last_name, email, phone,
                    filing_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                client_id,
                session_id,
                body.get("first_name", ""),
                body.get("last_name", ""),
                body.get("email", ""),
                body.get("phone", ""),
                body.get("filing_status", ""),
                now,
                now
            ))

        # Update intake session
        cursor.execute("""
            UPDATE intake_sessions SET
                last_activity = ?,
                answers_json = ?
            WHERE session_id = ?
        """, (now, json.dumps(body), session_id))

        conn.commit()
        conn.close()

        return format_success_response({
            "session_id": session_id,
            "client_id": client_id,
            "message": "Client information saved successfully",
            "updated_at": now
        })

    except Exception as e:
        log_and_raise_http_error(e, category="db", context="saving client info")


@intake_router.post("/clients/{session_id}/documents")
async def upload_document(
    session_id: str,
    request: Request,
    file: UploadFile = File(...)
):
    """
    Upload a document for a client session.

    Saves the file to disk and records metadata in the database.
    Security: Validates session ID, file size, type, and content.
    """
    # Validate session ID to prevent path traversal
    is_valid, error_msg = validate_session_id(session_id)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    now = datetime.utcnow().isoformat()
    document_id = f"doc-{uuid.uuid4().hex[:12]}"

    try:
        # Read file content
        content = await file.read()

        # Validate file upload (size, type, magic bytes)
        is_valid, error_msg, metadata = validate_file_upload(
            content=content,
            filename=file.filename,
            content_type=file.content_type,
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        safe_filename = metadata["safe_filename"]
        file_size = metadata["file_size"]
        detected_mime = metadata["detected_mime_type"]

        # Create session-specific directory
        session_dir = UPLOAD_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename using document_id (prevents collisions)
        ext = os.path.splitext(safe_filename)[1].lower() or ".pdf"
        stored_filename = f"{document_id}{ext}"
        storage_path = session_dir / stored_filename

        # Save file to disk
        with open(storage_path, "wb") as f:
            f.write(content)

        # Determine document type from sanitized filename
        filename_lower = safe_filename.lower()
        document_type = "unknown"
        if "w2" in filename_lower or "w-2" in filename_lower:
            document_type = "W-2"
        elif "1099" in filename_lower:
            document_type = "1099"
        elif "1098" in filename_lower:
            document_type = "1098"
        elif "k1" in filename_lower or "k-1" in filename_lower:
            document_type = "K-1"

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get client_id if exists
        cursor.execute("SELECT client_id FROM clients WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        client_id = row["client_id"] if row else None

        # Save document metadata
        cursor.execute("""
            INSERT INTO client_documents (
                document_id, session_id, client_id, filename, original_filename,
                file_size, file_type, document_type, storage_path, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            session_id,
            client_id,
            stored_filename,
            safe_filename,  # Store sanitized filename
            file_size,
            detected_mime or "application/octet-stream",
            document_type,
            str(storage_path),
            "uploaded",
            now
        ))

        conn.commit()
        conn.close()

        logger.info(f"Uploaded document {document_id} for session {session_id}")

        return format_success_response({
            "document_id": document_id,
            "session_id": session_id,
            "filename": safe_filename,
            "file_size": file_size,
            "document_type": document_type,
            "status": "uploaded",
            "created_at": now
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload document error: {e}")
        raise HTTPException(status_code=500, detail=get_safe_error_message(e))


@intake_router.get("/clients/{session_id}/documents")
async def list_documents(session_id: str, request: Request):
    """
    List all documents for a session.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT document_id, filename, original_filename, file_size,
                   file_type, document_type, status, ocr_status, created_at
            FROM client_documents
            WHERE session_id = ?
            ORDER BY created_at DESC
        """, (session_id,))

        documents = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return format_success_response({
            "session_id": session_id,
            "documents": documents,
            "count": len(documents)
        })

    except Exception as e:
        log_and_raise_http_error(e, category="db", context="listing documents")


@intake_router.post("/clients/{session_id}/submit")
async def submit_for_review(session_id: str, request: Request):
    """
    Submit the client intake for CPA review.

    Changes status from DRAFT to IN_REVIEW.
    """
    now = datetime.utcnow().isoformat()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Update client status
        cursor.execute("""
            UPDATE clients SET
                status = 'IN_REVIEW',
                updated_at = ?
            WHERE session_id = ?
        """, (now, session_id))

        # Update intake session
        cursor.execute("""
            UPDATE intake_sessions SET
                status = 'submitted',
                current_stage = 'review',
                completed_at = ?,
                last_activity = ?
            WHERE session_id = ?
        """, (now, now, session_id))

        conn.commit()

        # Get updated client info
        cursor.execute("SELECT * FROM clients WHERE session_id = ?", (session_id,))
        client = dict(cursor.fetchone()) if cursor.fetchone() else {}

        conn.close()

        return format_success_response({
            "session_id": session_id,
            "status": "IN_REVIEW",
            "submitted_at": now,
            "message": "Successfully submitted for CPA review"
        })

    except Exception as e:
        log_and_raise_http_error(e, category="db", context="submitting for review")


@intake_router.get("/clients/{session_id}/intake/status")
async def get_intake_status(session_id: str, request: Request):
    """
    Get current intake status for a session from database.

    Returns:
        - Current status (in_progress, completed, etc.)
        - Percent complete
        - Current stage
        - Client info
        - Document count
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get intake session
        cursor.execute("""
            SELECT session_id, status, current_stage, stages_completed_json,
                   started_at, last_activity, completed_at
            FROM intake_sessions
            WHERE session_id = ?
        """, (session_id,))
        session_row = cursor.fetchone()

        # Get client info
        cursor.execute("""
            SELECT client_id, first_name, last_name, email, filing_status,
                   tax_year, status, consent_given
            FROM clients
            WHERE session_id = ?
        """, (session_id,))
        client_row = cursor.fetchone()

        # Get document count
        cursor.execute("""
            SELECT COUNT(*) as count FROM client_documents WHERE session_id = ?
        """, (session_id,))
        doc_count = cursor.fetchone()["count"]

        conn.close()

        if not session_row and not client_row:
            raise HTTPException(status_code=404, detail="Session not found")

        # Calculate progress
        stages = ["welcome", "personal_info", "documents", "review", "complete"]
        completed = json.loads(session_row["stages_completed_json"]) if session_row else []
        current_stage = session_row["current_stage"] if session_row else "welcome"
        percent = (len(completed) / len(stages) * 100) if stages else 0

        return format_success_response({
            "session_id": session_id,
            "status": session_row["status"] if session_row else "not_started",
            "current_stage": current_stage,
            "stages_completed": completed,
            "percent_complete": round(percent, 1),
            "started_at": session_row["started_at"] if session_row else None,
            "last_activity": session_row["last_activity"] if session_row else None,
            "client": dict(client_row) if client_row else None,
            "documents_uploaded": doc_count,
        })

    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_http_error(e, category="db", context=f"getting intake status for {session_id}")


@intake_router.get("/clients/{session_id}/intake/progress")
async def get_intake_progress(session_id: str, request: Request):
    """
    Get detailed progress for intake session from database.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, current_stage, stages_completed_json
            FROM intake_sessions
            WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        completed = json.loads(row["stages_completed_json"]) if row["stages_completed_json"] else []
        current = row["current_stage"]

        stages = [
            {"stage_id": "welcome", "display_name": "Welcome & Consent"},
            {"stage_id": "personal_info", "display_name": "Personal Information"},
            {"stage_id": "documents", "display_name": "Document Upload"},
            {"stage_id": "review", "display_name": "Review & Submit"},
            {"stage_id": "complete", "display_name": "Dashboard"},
        ]

        for stage in stages:
            if stage["stage_id"] in completed:
                stage["status"] = "complete"
            elif stage["stage_id"] == current:
                stage["status"] = "in_progress"
            else:
                stage["status"] = "pending"

        return format_success_response({
            "session_id": session_id,
            "stages": stages,
            "overall_status": row["status"]
        })

    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_http_error(e, category="db", context=f"getting intake progress for {session_id}")


@intake_router.get("/clients/{session_id}/intake/estimate")
async def get_intake_estimate(session_id: str, request: Request):
    """
    Get current benefit estimate based on intake answers.
    Reads from tax_returns table if available.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Try to get from tax returns
        cursor.execute("""
            SELECT tr.*, c.first_name, c.last_name
            FROM tax_returns tr
            JOIN clients c ON tr.client_id = c.client_id
            WHERE tr.session_id = ? OR c.session_id = ?
        """, (session_id, session_id))
        tr_row = cursor.fetchone()

        if tr_row:
            tr = dict(tr_row)
            refund = tr.get("refund_amount", 0)
            balance = tr.get("balance_due", 0)

            # Get recommendations
            cursor.execute("""
                SELECT SUM(estimated_savings) as total_savings
                FROM recommendations WHERE session_id = ?
            """, (session_id,))
            rec_row = cursor.fetchone()
            potential_savings = rec_row["total_savings"] if rec_row and rec_row["total_savings"] else 0

            conn.close()

            return format_success_response({
                "session_id": session_id,
                "estimate_type": "refund" if refund > 0 else "owed",
                "estimated_amount": refund if refund > 0 else balance,
                "confidence": "high",
                "source": "tax_return",
                "total_income": tr.get("gross_income", 0),
                "total_tax": tr.get("total_tax", 0),
                "potential_savings": potential_savings,
            })

        # Fallback: just return session exists
        cursor.execute("SELECT * FROM clients WHERE session_id = ?", (session_id,))
        client = cursor.fetchone()
        conn.close()

        if not client:
            raise HTTPException(status_code=404, detail="Session not found")

        return format_success_response({
            "session_id": session_id,
            "estimate_type": "pending",
            "estimated_amount": 0,
            "confidence": "low",
            "source": "intake",
            "message": "Submit more information for a detailed estimate"
        })

    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_http_error(e, category="db", context=f"getting intake estimate for {session_id}")


@intake_router.post("/clients/{session_id}/intake/answers")
async def submit_intake_answers(session_id: str, request: Request):
    """
    Submit answers for an intake session.
    Persists to database.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    answers = body.get("answers", {})
    now = datetime.utcnow().isoformat()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get current session
        cursor.execute("""
            SELECT answers_json, stages_completed_json, current_stage
            FROM intake_sessions WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        # Merge answers
        existing_answers = json.loads(row["answers_json"]) if row["answers_json"] else {}
        existing_answers.update(answers)

        # Update session
        cursor.execute("""
            UPDATE intake_sessions SET
                answers_json = ?,
                last_activity = ?
            WHERE session_id = ?
        """, (json.dumps(existing_answers), now, session_id))

        conn.commit()
        conn.close()

        return format_success_response({
            "session_id": session_id,
            "answers_count": len(existing_answers),
            "updated_at": now
        })

    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_http_error(e, category="db", context=f"submitting intake answers for {session_id}")


# =============================================================================
# ADDITIONAL CLIENT ENDPOINTS
# =============================================================================

@intake_router.get("/clients/{session_id}/full")
async def get_client_full(session_id: str, request: Request):
    """
    Get full client details including tax return, recommendations, and documents.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get client
        cursor.execute("SELECT * FROM clients WHERE session_id = ?", (session_id,))
        client_row = cursor.fetchone()

        if not client_row:
            raise HTTPException(status_code=404, detail="Client not found")

        client = dict(client_row)
        client_id = client.get("client_id")

        # Get tax return
        cursor.execute("SELECT * FROM tax_returns WHERE session_id = ? OR client_id = ?", (session_id, client_id))
        tr_row = cursor.fetchone()
        if tr_row:
            client["tax_return"] = dict(tr_row)

        # Get recommendations
        cursor.execute("""
            SELECT * FROM recommendations
            WHERE session_id = ? OR client_id = ?
            ORDER BY estimated_savings DESC
        """, (session_id, client_id))
        client["recommendations"] = [dict(r) for r in cursor.fetchall()]

        # Get documents
        cursor.execute("""
            SELECT document_id, original_filename, file_size, document_type, status, created_at
            FROM client_documents WHERE session_id = ?
            ORDER BY created_at DESC
        """, (session_id,))
        client["documents"] = [dict(d) for d in cursor.fetchall()]

        # Get intake session
        cursor.execute("SELECT * FROM intake_sessions WHERE session_id = ?", (session_id,))
        intake_row = cursor.fetchone()
        if intake_row:
            client["intake_session"] = dict(intake_row)

        conn.close()

        return format_success_response({"client": client})

    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_http_error(e, category="db", context=f"getting full client data for {session_id}")
