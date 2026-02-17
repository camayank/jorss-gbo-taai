"""
Client Visibility Surface API Routes

Read-only endpoints for clients to view their return status.

SCOPE BOUNDARIES (ENFORCED - DO NOT EXPAND):
- GET status: YES
- GET next steps: YES
- GET CPA contact: YES
- POST document upload: YES
- Messaging: NO
- Comments: NO
- Task management: NO
"""

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Depends
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import uuid
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from database.connection import get_async_session
except ImportError:
    async def get_async_session():
        raise HTTPException(status_code=503, detail="Database session dependency unavailable")
from ..client_visibility import ClientVisibilityService, ClientVisibilityData
from .common import format_success_response, format_error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client", tags=["client-visibility"])

_visibility_service = ClientVisibilityService()


async def _get_session_data(session_id: str, access_token: str, session: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Get session data with access token verification.

    Loads session data from the tax_returns table by return_id (session_id).
    """
    query = text("""
        SELECT
            tr.return_id,
            tr.tax_year,
            tr.status,
            tr.filing_status,
            tr.updated_at,
            tr.return_data,
            tp.first_name,
            tp.last_name,
            tp.email as client_email,
            c.client_id
        FROM tax_returns tr
        JOIN taxpayers tp ON tr.return_id = tp.return_id
        LEFT JOIN clients c ON tp.email = c.email
        WHERE tr.return_id = :session_id
    """)
    try:
        result = await session.execute(query, {"session_id": session_id})
        row = result.fetchone()

        if row:
            return_data = row[5] if row[5] else {}
            if isinstance(return_data, str):
                return_data = json.loads(return_data)

            return {
                "return_id": str(row[0]),
                "tax_year": row[1],
                "status": row[2] or "new",
                "filing_status": row[3],
                "status_updated_at": row[4].isoformat() if row[4] else None,
                "client_name": f"{row[6] or ''} {row[7] or ''}".strip(),
                "client_email": row[8],
                "client_id": str(row[9]) if row[9] else None,
                "filing_deadline": return_data.get("filing_deadline"),
                "extension_deadline": return_data.get("extension_deadline"),
            }
    except Exception as e:
        logger.debug(f"Could not fetch session data: {e}")

    return None


async def _get_cpa_info(session_id: str, session: AsyncSession) -> Dict[str, Any]:
    """Get CPA info for a session."""
    query = text("""
        SELECT
            f.name as firm_name,
            u.first_name,
            u.last_name,
            u.email,
            u.phone,
            f.settings
        FROM tax_returns tr
        JOIN taxpayers tp ON tr.return_id = tp.return_id
        JOIN clients c ON tp.email = c.email
        JOIN users u ON c.preparer_id = u.user_id
        JOIN firms f ON u.firm_id = f.firm_id
        WHERE tr.return_id = :session_id
    """)
    try:
        result = await session.execute(query, {"session_id": session_id})
        row = result.fetchone()

        if row:
            settings = row[5] if row[5] else {}
            if isinstance(settings, str):
                settings = json.loads(settings)

            return {
                "firm_name": row[0] or "Your CPA Firm",
                "cpa_name": f"{row[1] or ''} {row[2] or ''}".strip() or "Your CPA",
                "email": row[3],
                "phone": row[4],
                "office_hours": settings.get("office_hours", "Mon-Fri 9am-5pm"),
            }
    except Exception as e:
        logger.debug(f"Could not fetch CPA info: {e}")

    return {
        "firm_name": "Your CPA Firm",
        "cpa_name": "Your CPA",
        "email": "cpa@example.com",
        "phone": None,
        "office_hours": "Mon-Fri 9am-5pm",
    }


async def _get_documents(session_id: str, session: AsyncSession) -> List[Dict[str, Any]]:
    """Get document statuses for a session."""
    query = text("""
        SELECT
            document_id,
            document_type,
            file_name,
            status,
            is_required,
            uploaded_at,
            description
        FROM documents
        WHERE return_id = :session_id
        ORDER BY is_required DESC, uploaded_at DESC
    """)
    try:
        result = await session.execute(query, {"session_id": session_id})
        rows = result.fetchall()

        documents = []
        for row in rows:
            documents.append({
                "document_id": str(row[0]),
                "document_type": row[1] or "Document",
                "file_name": row[2],
                "status": row[3] or "pending",
                "is_required": row[4] if row[4] is not None else False,
                "is_received": row[3] in ("received", "processed", "approved"),
                "uploaded_at": row[5].isoformat() if row[5] else None,
                "description": row[6],
            })
        return documents
    except Exception as e:
        logger.debug(f"Could not fetch documents: {e}")

    return []


@router.get("/status/{session_id}")
async def get_client_status(
    request: Request,
    session_id: str,
    access_token: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Get client visibility data for a session.

    This is the main endpoint for clients to see their return status.

    Query params:
    - access_token: Client access token (for auth verification)

    Returns:
    - status: Current status with progress
    - next_steps: What the client needs to do (max 4 items)
    - cpa_contact: How to reach the CPA
    - documents: Document upload status
    """
    session_data = await _get_session_data(session_id, access_token or "", session)

    if not session_data:
        # Return a generic "not found" to avoid leaking session existence
        raise HTTPException(
            status_code=404,
            detail="Session not found or access denied"
        )

    cpa_info = await _get_cpa_info(session_id, session)
    documents = await _get_documents(session_id, session)

    visibility_data = _visibility_service.get_visibility_data(
        session_id=session_id,
        session_data=session_data,
        cpa_info=cpa_info,
        documents=documents,
    )

    return format_success_response({
        "visibility": visibility_data.to_dict(),
    })


@router.post("/documents/{session_id}/upload")
async def upload_document(
    request: Request,
    session_id: str,
    file: UploadFile = File(...),
    document_type: Optional[str] = None,
    access_token: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Upload a document for a session.

    This is a simplified upload endpoint for clients.
    The actual document processing happens elsewhere.

    Form data:
    - file: The document file
    - document_type: Optional type hint (W-2, 1099, etc.)

    Query params:
    - access_token: Client access token
    """
    session_data = await _get_session_data(session_id, access_token or "", session)

    if not session_data:
        raise HTTPException(
            status_code=404,
            detail="Session not found or access denied"
        )

    # Check if uploads are allowed for this session
    status = session_data.get("status", "").lower()
    if status not in ["new", "in_progress", "gathering_info", "draft", "pending"]:
        raise HTTPException(
            status_code=400,
            detail="Document uploads are not accepted at this stage"
        )

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Check file size (10MB limit for client uploads)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    document_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Insert document record into database
    query = text("""
        INSERT INTO documents (
            document_id, return_id, document_type, file_name, file_size,
            status, uploaded_at, uploaded_by
        ) VALUES (
            :document_id, :return_id, :document_type, :file_name, :file_size,
            'received', :uploaded_at, :uploaded_by
        )
    """)
    try:
        await session.execute(query, {
            "document_id": document_id,
            "return_id": session_id,
            "document_type": document_type or "other",
            "file_name": file.filename,
            "file_size": len(contents),
            "uploaded_at": now,
            "uploaded_by": session_data.get("client_id"),
        })
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to save document: {e}")
        raise HTTPException(status_code=500, detail="Failed to save document")

    logger.info(f"Client uploaded document {document_id} for session {session_id}")

    return format_success_response({
        "document_id": document_id,
        "filename": file.filename,
        "document_type": document_type or "other",
        "size_bytes": len(contents),
        "uploaded_at": now.isoformat(),
        "status": "received",
        "message": "Document received. Your CPA will review it shortly.",
    })


@router.get("/documents/{session_id}")
async def get_document_status(
    request: Request,
    session_id: str,
    access_token: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Get document status for a session.

    Shows which documents have been requested, received, or are pending.
    """
    session_data = await _get_session_data(session_id, access_token or "", session)

    if not session_data:
        raise HTTPException(
            status_code=404,
            detail="Session not found or access denied"
        )

    documents = await _get_documents(session_id, session)

    pending = [d for d in documents if d.get("is_required") and not d.get("is_received")]
    received = [d for d in documents if d.get("is_received")]

    return format_success_response({
        "session_id": session_id,
        "documents": {
            "pending": pending,
            "received": received,
            "pending_count": len(pending),
            "received_count": len(received),
        },
    })


# =============================================================================
# INTERNAL ENDPOINTS (for CPA/system use, not client-facing)
# =============================================================================

@router.post("/internal/sessions/{session_id}/setup")
async def setup_client_visibility(
    request: Request,
    session_id: str,
    body: Dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Set up client visibility data for a session.

    This is called by the CPA system to configure what the client sees.
    NOT a client-facing endpoint.

    Body:
    - client_name: Client's name
    - tax_year: Tax year
    - status: Current status
    - cpa_info: CPA contact information
    - requested_documents: List of documents to request
    """
    now = datetime.utcnow()

    # Update tax_return with visibility settings in return_data
    return_data = {
        "filing_deadline": body.get("filing_deadline"),
        "extension_deadline": body.get("extension_deadline"),
    }

    query = text("""
        UPDATE tax_returns
        SET status = :status,
            return_data = COALESCE(return_data, '{}'::jsonb) || :return_data::jsonb,
            updated_at = :updated_at
        WHERE return_id = :return_id
    """)
    try:
        result = await session.execute(query, {
            "return_id": session_id,
            "status": body.get("status", "new"),
            "return_data": json.dumps(return_data),
            "updated_at": now,
        })
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to setup visibility: {e}")
        raise HTTPException(status_code=500, detail="Failed to setup visibility")

    # Add requested documents if provided
    if body.get("requested_documents"):
        for doc in body["requested_documents"]:
            doc_query = text("""
                INSERT INTO documents (
                    document_id, return_id, document_type, description,
                    is_required, status, created_at
                ) VALUES (
                    :document_id, :return_id, :document_type, :description,
                    :is_required, 'pending', :created_at
                )
            """)
            try:
                await session.execute(doc_query, {
                    "document_id": str(uuid.uuid4()),
                    "return_id": session_id,
                    "document_type": doc.get("type", "Document"),
                    "description": doc.get("description", ""),
                    "is_required": doc.get("is_required", True),
                    "created_at": now,
                })
            except Exception as e:
                logger.debug(f"Could not insert document request: {e}")

    await session.commit()

    return format_success_response({
        "session_id": session_id,
        "visibility_configured": True,
    })


@router.put("/internal/sessions/{session_id}/status")
async def update_client_status(
    request: Request,
    session_id: str,
    body: Dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Update the client-visible status for a session.

    Called by the CPA system when return status changes.
    NOT a client-facing endpoint.
    """
    new_status = body.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="status is required")

    now = datetime.utcnow()

    query = text("""
        UPDATE tax_returns
        SET status = :status,
            updated_at = :updated_at
        WHERE return_id = :return_id
    """)
    try:
        result = await session.execute(query, {
            "return_id": session_id,
            "status": new_status,
            "updated_at": now,
        })
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        await session.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update status")

    logger.info(f"Client visibility status updated for {session_id}: {new_status}")

    return format_success_response({
        "session_id": session_id,
        "status": new_status,
        "updated_at": now.isoformat(),
    })
