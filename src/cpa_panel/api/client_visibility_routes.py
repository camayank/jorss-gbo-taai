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

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import uuid

from ..client_visibility import ClientVisibilityService, ClientVisibilityData
from .common import format_success_response, format_error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client", tags=["client-visibility"])

_visibility_service = ClientVisibilityService()

# Mock data store (replace with actual DB queries in production)
_mock_sessions: Dict[str, Dict[str, Any]] = {}
_mock_documents: Dict[str, List[Dict[str, Any]]] = {}
_mock_cpa_info: Dict[str, Dict[str, Any]] = {}


def _get_session_data(session_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    """
    Get session data with access token verification.

    In production, this would:
    1. Verify the access token is valid for this session
    2. Load session data from database
    3. Return None if unauthorized
    """
    # For now, return mock data or None
    return _mock_sessions.get(session_id)


def _get_cpa_info(session_id: str) -> Dict[str, Any]:
    """Get CPA info for a session."""
    return _mock_cpa_info.get(session_id, {
        "firm_name": "Your CPA Firm",
        "cpa_name": "Your CPA",
        "email": "cpa@example.com",
        "phone": None,
        "office_hours": "Mon-Fri 9am-5pm",
    })


def _get_documents(session_id: str) -> List[Dict[str, Any]]:
    """Get document statuses for a session."""
    return _mock_documents.get(session_id, [])


@router.get("/status/{session_id}")
async def get_client_status(
    request: Request,
    session_id: str,
    access_token: Optional[str] = None,
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
    # In production, verify access_token grants access to this session
    # For now, we'll check if session exists

    session_data = _get_session_data(session_id, access_token or "")

    if not session_data:
        # Return a generic "not found" to avoid leaking session existence
        raise HTTPException(
            status_code=404,
            detail="Session not found or access denied"
        )

    cpa_info = _get_cpa_info(session_id)
    documents = _get_documents(session_id)

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
    session_data = _get_session_data(session_id, access_token or "")

    if not session_data:
        raise HTTPException(
            status_code=404,
            detail="Session not found or access denied"
        )

    # Check if uploads are allowed for this session
    status = session_data.get("status", "").lower()
    if status not in ["new", "in_progress", "gathering_info"]:
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

    # In production, this would:
    # 1. Save file to secure storage
    # 2. Create document record in database
    # 3. Trigger OCR processing if applicable
    # 4. Notify CPA of new document

    document_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"

    logger.info(f"Client uploaded document {document_id} for session {session_id}")

    return format_success_response({
        "document_id": document_id,
        "filename": file.filename,
        "document_type": document_type or "unknown",
        "size_bytes": len(contents),
        "uploaded_at": datetime.utcnow().isoformat(),
        "status": "received",
        "message": "Document received. Your CPA will review it shortly.",
    })


@router.get("/documents/{session_id}")
async def get_document_status(
    request: Request,
    session_id: str,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get document status for a session.

    Shows which documents have been requested, received, or are pending.
    """
    session_data = _get_session_data(session_id, access_token or "")

    if not session_data:
        raise HTTPException(
            status_code=404,
            detail="Session not found or access denied"
        )

    documents = _get_documents(session_id)

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
    session_data = {
        "client_name": body.get("client_name", ""),
        "tax_year": body.get("tax_year", 2025),
        "status": body.get("status", "new"),
        "status_updated_at": datetime.utcnow().isoformat(),
        "filing_deadline": body.get("filing_deadline"),
        "extension_deadline": body.get("extension_deadline"),
    }

    _mock_sessions[session_id] = session_data

    if body.get("cpa_info"):
        _mock_cpa_info[session_id] = body["cpa_info"]

    if body.get("requested_documents"):
        _mock_documents[session_id] = [
            {
                "document_type": doc.get("type", "Document"),
                "description": doc.get("description", ""),
                "is_required": doc.get("is_required", True),
                "is_received": False,
            }
            for doc in body["requested_documents"]
        ]

    return format_success_response({
        "session_id": session_id,
        "visibility_configured": True,
    })


@router.put("/internal/sessions/{session_id}/status")
async def update_client_status(
    request: Request,
    session_id: str,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update the client-visible status for a session.

    Called by the CPA system when return status changes.
    NOT a client-facing endpoint.
    """
    if session_id not in _mock_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    new_status = body.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="status is required")

    _mock_sessions[session_id]["status"] = new_status
    _mock_sessions[session_id]["status_updated_at"] = datetime.utcnow().isoformat()

    logger.info(f"Client visibility status updated for {session_id}: {new_status}")

    return format_success_response({
        "session_id": session_id,
        "status": new_status,
        "updated_at": _mock_sessions[session_id]["status_updated_at"],
    })
