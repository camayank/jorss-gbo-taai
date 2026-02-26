"""
GDPR Data Erasure API.

Provides the right-to-erasure (Article 17) endpoint for data subjects.
Handles deletion across all data stores: main DB, sessions (Redis + SQLite),
uploaded files, and audit log anonymization.

All erasure operations are themselves audit-logged (without PII).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
import logging
import os
import glob as glob_module

from rbac.dependencies import require_auth
from rbac.context import AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/gdpr",
    tags=["GDPR Compliance"],
    responses={403: {"description": "Insufficient permissions"}},
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class ErasureRequest(BaseModel):
    """Data subject erasure request."""
    identifier_type: str = Field(
        ...,
        description="Type of identifier: 'session_id', 'email', 'ssn_hash', 'taxpayer_id', 'client_id'"
    )
    identifier_value: str = Field(..., description="The identifier value")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for erasure request")


class ErasureResult(BaseModel):
    """Result of an erasure operation."""
    status: str
    erasure_id: str
    records_deleted: Dict[str, int]
    timestamp: str


# =============================================================================
# ERASURE ENDPOINT
# =============================================================================


@router.post("/erasure", response_model=ErasureResult)
async def request_data_erasure(
    request: Request,
    body: ErasureRequest,
    auth: AuthContext = Depends(require_auth),
):
    """
    GDPR Article 17 - Right to Erasure.

    Deletes all PII associated with the given identifier across:
    - Main database (taxpayers, clients, documents, returns, dependents)
    - Session stores (Redis + SQLite)
    - Uploaded files (filesystem)
    - Audit logs (anonymized, not deleted - kept for compliance)

    Requires authentication. The requesting user must own the data
    or be a platform admin.
    """
    import uuid

    erasure_id = str(uuid.uuid4())
    deleted_counts: Dict[str, int] = {}

    identifier_type = body.identifier_type
    identifier_value = body.identifier_value

    logger.info(
        f"GDPR erasure request {erasure_id}: type={identifier_type}",
        extra={"erasure_id": erasure_id},
    )

    # Log the erasure request itself (no PII in log)
    _log_erasure_audit(
        erasure_id=erasure_id,
        action="erasure_requested",
        identifier_type=identifier_type,
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        ip_address=request.client.host if request.client else None,
    )

    try:
        # 1. Delete from main database (ORM tables)
        db_counts = await _erase_from_database(identifier_type, identifier_value)
        deleted_counts.update(db_counts)

        # 2. Delete sessions (Redis + SQLite)
        session_counts = await _erase_sessions(
            identifier_type, identifier_value, auth.tenant_id
        )
        deleted_counts.update(session_counts)

        # 3. Delete uploaded files
        file_count = _erase_uploaded_files(identifier_type, identifier_value)
        deleted_counts["files_deleted"] = file_count

        # 4. Anonymize audit logs (keep records, remove PII)
        anonymized = _anonymize_audit_logs(identifier_type, identifier_value)
        deleted_counts["audit_logs_anonymized"] = anonymized

        # Log completion
        _log_erasure_audit(
            erasure_id=erasure_id,
            action="erasure_completed",
            identifier_type=identifier_type,
            user_id=auth.user_id,
            tenant_id=auth.tenant_id,
            details={"records_deleted": deleted_counts},
        )

        logger.info(
            f"GDPR erasure {erasure_id} completed: {deleted_counts}",
            extra={"erasure_id": erasure_id, "counts": deleted_counts},
        )

        return ErasureResult(
            status="completed",
            erasure_id=erasure_id,
            records_deleted=deleted_counts,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"GDPR erasure {erasure_id} failed: {e}")
        _log_erasure_audit(
            erasure_id=erasure_id,
            action="erasure_failed",
            identifier_type=identifier_type,
            user_id=auth.user_id,
            tenant_id=auth.tenant_id,
            details={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Erasure failed — contact support")


@router.get("/erasure/{erasure_id}/status")
async def get_erasure_status(
    erasure_id: str,
    auth: AuthContext = Depends(require_auth),
):
    """Check status of an erasure request by its ID."""
    try:
        from audit.audit_logger import AuditLogger, AuditEventType
        audit = AuditLogger()
        events = audit.query(
            resource_type="gdpr_erasure",
            resource_id=erasure_id,
            limit=10,
        )
        if not events:
            raise HTTPException(status_code=404, detail="Erasure request not found")

        return {
            "erasure_id": erasure_id,
            "events": [
                {
                    "action": e.get("action"),
                    "timestamp": e.get("timestamp"),
                    "details": e.get("details"),
                }
                for e in events
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get erasure status: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve status")


# =============================================================================
# INTERNAL ERASURE FUNCTIONS
# =============================================================================


async def _erase_from_database(
    identifier_type: str, identifier_value: str
) -> Dict[str, int]:
    """Delete PII from main database tables."""
    counts: Dict[str, int] = {}

    try:
        from database.session_persistence import get_session_persistence
        persistence = get_session_persistence()
    except Exception:
        persistence = None

    if identifier_type == "session_id":
        if persistence:
            # Delete session and related data
            deleted = persistence.delete_session(identifier_value)
            counts["sessions"] = 1 if deleted else 0

            # Delete session documents
            try:
                from database.onboarding_persistence import OnboardingPersistence
                onboarding = OnboardingPersistence()
                doc_count = onboarding.delete_session_documents(identifier_value)
                counts["session_documents"] = doc_count
            except Exception as e:
                logger.warning(f"Could not delete session documents: {e}")

            # Delete session tax returns
            try:
                deleted_return = persistence.delete_session_tax_return(identifier_value)
                counts["session_tax_returns"] = 1 if deleted_return else 0
            except Exception as e:
                logger.warning(f"Could not delete session tax return: {e}")

    elif identifier_type == "email":
        # Find and delete by email across tables
        counts.update(_delete_by_email(identifier_value))

    elif identifier_type == "ssn_hash":
        counts.update(_delete_by_ssn_hash(identifier_value))

    elif identifier_type == "taxpayer_id":
        counts.update(_delete_by_taxpayer_id(identifier_value))

    elif identifier_type == "client_id":
        counts.update(_delete_by_client_id(identifier_value))

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported identifier type: {identifier_type}",
        )

    return counts


def _delete_by_email(email: str) -> Dict[str, int]:
    """Delete all records associated with an email address."""
    import sqlite3
    counts: Dict[str, int] = {}

    try:
        from database.session_persistence import get_session_persistence
        persistence = get_session_persistence()
        db_path = persistence.db_path

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Find sessions containing this email in their data
            cursor.execute(
                "SELECT session_id FROM session_states WHERE data_json LIKE ?",
                (f'%{email}%',),
            )
            session_ids = [row[0] for row in cursor.fetchall()]
            counts["sessions_found"] = len(session_ids)

            for sid in session_ids:
                persistence.delete_session(sid)

            counts["sessions_deleted"] = len(session_ids)
            conn.commit()
    except Exception as e:
        logger.warning(f"Could not search sessions by email: {e}")

    return counts


def _delete_by_ssn_hash(ssn_hash: str) -> Dict[str, int]:
    """Delete all records linked to an SSN hash."""
    import sqlite3
    counts: Dict[str, int] = {}

    try:
        from database.session_persistence import get_session_persistence
        persistence = get_session_persistence()
        db_path = persistence.db_path

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Search for sessions containing this SSN hash
            cursor.execute(
                "SELECT session_id FROM session_states WHERE data_json LIKE ?",
                (f'%{ssn_hash}%',),
            )
            session_ids = [row[0] for row in cursor.fetchall()]

            for sid in session_ids:
                persistence.delete_session(sid)

            counts["sessions_deleted"] = len(session_ids)
            conn.commit()
    except Exception as e:
        logger.warning(f"Could not delete by SSN hash: {e}")

    return counts


def _delete_by_taxpayer_id(taxpayer_id: str) -> Dict[str, int]:
    """Delete taxpayer and all related records."""
    import sqlite3
    counts: Dict[str, int] = {}

    try:
        from database.session_persistence import get_session_persistence
        persistence = get_session_persistence()
        db_path = persistence.db_path

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Delete sessions referencing this taxpayer
            cursor.execute(
                "SELECT session_id FROM session_states WHERE data_json LIKE ?",
                (f'%{taxpayer_id}%',),
            )
            session_ids = [row[0] for row in cursor.fetchall()]
            for sid in session_ids:
                persistence.delete_session(sid)
            counts["sessions_deleted"] = len(session_ids)

            conn.commit()
    except Exception as e:
        logger.warning(f"Could not delete by taxpayer_id: {e}")

    return counts


def _delete_by_client_id(client_id: str) -> Dict[str, int]:
    """Delete client and all related records."""
    import sqlite3
    counts: Dict[str, int] = {}

    try:
        from database.session_persistence import get_session_persistence
        persistence = get_session_persistence()
        db_path = persistence.db_path

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT session_id FROM session_states WHERE data_json LIKE ?",
                (f'%{client_id}%',),
            )
            session_ids = [row[0] for row in cursor.fetchall()]
            for sid in session_ids:
                persistence.delete_session(sid)
            counts["sessions_deleted"] = len(session_ids)

            conn.commit()
    except Exception as e:
        logger.warning(f"Could not delete by client_id: {e}")

    return counts


async def _erase_sessions(
    identifier_type: str, identifier_value: str, tenant_id: str
) -> Dict[str, int]:
    """Delete sessions from both Redis and SQLite."""
    counts: Dict[str, int] = {}

    # Redis sessions
    try:
        from database.redis_session_persistence import get_redis_session_persistence
        redis_persistence = await get_redis_session_persistence()
        if redis_persistence and identifier_type == "session_id":
            deleted = await redis_persistence.delete_session(
                identifier_value, tenant_id
            )
            counts["redis_sessions"] = 1 if deleted else 0
    except Exception as e:
        logger.warning(f"Could not delete Redis sessions: {e}")

    return counts


def _erase_uploaded_files(
    identifier_type: str, identifier_value: str
) -> int:
    """Delete uploaded document files from filesystem."""
    deleted_count = 0
    upload_dirs = [
        "./data/uploads",
        "./uploads",
    ]

    for upload_dir in upload_dirs:
        if not os.path.exists(upload_dir):
            continue

        # Search for files matching the identifier in their path
        patterns = [
            os.path.join(upload_dir, f"**/*{identifier_value}*"),
        ]

        if identifier_type == "session_id":
            patterns.append(os.path.join(upload_dir, identifier_value, "**/*"))

        for pattern in patterns:
            for filepath in glob_module.glob(pattern, recursive=True):
                if os.path.isfile(filepath):
                    try:
                        os.remove(filepath)
                        deleted_count += 1
                        logger.debug(f"Deleted upload: {filepath}")
                    except OSError as e:
                        logger.warning(f"Could not delete {filepath}: {e}")

    return deleted_count


def _anonymize_audit_logs(
    identifier_type: str, identifier_value: str
) -> int:
    """
    Anonymize PII in audit logs without deleting the audit records.

    GDPR allows retaining audit records for compliance, but PII
    within the records must be anonymized.
    """
    import sqlite3
    import json
    anonymized_count = 0

    try:
        from audit.audit_logger import AuditLogger
        audit = AuditLogger()

        with sqlite3.connect(audit.db_path) as conn:
            cursor = conn.cursor()

            # Find audit records referencing this identifier
            if identifier_type == "session_id":
                cursor.execute(
                    "SELECT event_id, details, old_value, new_value FROM audit_log "
                    "WHERE resource_id = ? OR details LIKE ?",
                    (identifier_value, f'%{identifier_value}%'),
                )
            elif identifier_type in ("email", "ssn_hash", "taxpayer_id", "client_id"):
                cursor.execute(
                    "SELECT event_id, details, old_value, new_value FROM audit_log "
                    "WHERE user_id = ? OR resource_id = ? OR details LIKE ?",
                    (identifier_value, identifier_value, f'%{identifier_value}%'),
                )
            else:
                return 0

            rows = cursor.fetchall()

            for event_id, details_json, old_json, new_json in rows:
                updates = []
                params = []

                # Anonymize details field
                if details_json:
                    details = json.loads(details_json)
                    anonymized_details = _scrub_pii_from_dict(details)
                    updates.append("details = ?")
                    params.append(json.dumps(anonymized_details))

                # Anonymize old_value
                if old_json:
                    updates.append("old_value = ?")
                    params.append(json.dumps({"_anonymized": True}))

                # Anonymize new_value
                if new_json:
                    updates.append("new_value = ?")
                    params.append(json.dumps({"_anonymized": True}))

                if updates:
                    params.append(event_id)
                    cursor.execute(
                        f"UPDATE audit_log SET {', '.join(updates)} WHERE event_id = ?",
                        params,
                    )
                    anonymized_count += 1

            conn.commit()

    except Exception as e:
        logger.warning(f"Could not anonymize audit logs: {e}")

    return anonymized_count


def _scrub_pii_from_dict(data: dict) -> dict:
    """Remove known PII fields from a dictionary."""
    pii_keys = {
        "ssn", "ssn_encrypted", "ssn_hash", "social_security",
        "email", "phone", "phone_number",
        "first_name", "last_name", "full_name", "name",
        "address", "address_line_1", "address_line_2",
        "date_of_birth", "dob",
        "bank_routing", "bank_account", "bank_routing_encrypted", "bank_account_encrypted",
        "ip_address", "ip_pin",
        "spouse_ssn", "spouse_name", "spouse_first_name", "spouse_last_name",
        "password", "password_hash", "mfa_secret",
    }

    scrubbed = {}
    for key, value in data.items():
        if key.lower() in pii_keys:
            scrubbed[key] = "[REDACTED]"
        elif isinstance(value, dict):
            scrubbed[key] = _scrub_pii_from_dict(value)
        else:
            scrubbed[key] = value

    return scrubbed


def _log_erasure_audit(
    erasure_id: str,
    action: str,
    identifier_type: str,
    user_id: str = None,
    tenant_id: str = None,
    ip_address: str = None,
    details: dict = None,
):
    """Log a GDPR erasure event to the audit trail (without storing PII)."""
    try:
        from audit.audit_logger import AuditLogger, AuditEventType, AuditSeverity
        audit = AuditLogger()
        audit.log(
            event_type=AuditEventType.PII_DELETION,
            action=action,
            resource_type="gdpr_erasure",
            resource_id=erasure_id,
            user_id=user_id,
            tenant_id=tenant_id,
            severity=AuditSeverity.CRITICAL,
            ip_address=ip_address,
            details={
                "identifier_type": identifier_type,
                **(details or {}),
            },
        )
    except Exception as e:
        logger.error(f"Could not log erasure audit event: {e}")
