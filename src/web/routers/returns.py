"""
Tax Returns Routes - CRUD and Workflow

SPEC-005: Extracted from app.py for modularity.

Routes:
- POST /api/returns/save - Save tax return
- GET /api/returns/{return_id} - Get return by ID
- GET /api/returns - List returns
- DELETE /api/returns/{return_id} - Delete return
- GET /api/returns/{session_id}/status - Get return status
- POST /api/returns/{session_id}/submit-for-review - Submit for CPA review
- POST /api/returns/{session_id}/approve - CPA approval
- POST /api/returns/{session_id}/revert-to-draft - Revert to draft
- GET /api/returns/queue/{status} - Get returns by status
- POST /api/returns/{session_id}/delta - Calculate delta changes
- POST /api/returns/{session_id}/notes - Add notes
- GET /api/returns/{session_id}/notes - Get notes
"""

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import uuid
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/returns", tags=["Tax Returns"])

# Dependencies will be injected
_persistence = None
_session_persistence = None


def set_dependencies(persistence, session_persistence):
    """Set dependencies from the main app."""
    global _persistence, _session_persistence
    _persistence = persistence
    _session_persistence = session_persistence


def _get_persistence():
    """Get tax return persistence."""
    global _persistence
    if _persistence is None:
        from database.persistence import TaxReturnPersistence
        _persistence = TaxReturnPersistence()
    return _persistence


def _get_session_persistence():
    """Get session persistence."""
    global _session_persistence
    if _session_persistence is None:
        from database.session_persistence import get_session_persistence
        _session_persistence = get_session_persistence()
    return _session_persistence


# =============================================================================
# CRUD ROUTES
# =============================================================================

@router.post("/save")
async def save_return(request: Request):
    """
    Save or update a tax return.

    Creates new return if no return_id provided, updates if exists.
    """
    try:
        body = await request.json()
        session_id = body.get("session_id") or request.cookies.get("tax_session_id")

        if not session_id:
            session_id = str(uuid.uuid4())

        return_id = body.get("return_id")
        tax_return_data = body.get("data", body)

        # Add metadata
        tax_return_data["session_id"] = session_id
        tax_return_data["updated_at"] = datetime.utcnow().isoformat()

        # Save to database
        persistence = _get_persistence()
        saved_id = persistence.save_return(
            session_id=session_id,
            tax_return_data=tax_return_data,
            return_id=return_id,
        )

        # Also save to session persistence
        session_persistence = _get_session_persistence()
        session_persistence.save_session_tax_return(
            session_id=session_id,
            return_data=tax_return_data,
            tax_year=tax_return_data.get("tax_year", 2025),
        )

        return JSONResponse({
            "status": "success",
            "return_id": saved_id,
            "session_id": session_id,
            "message": "Tax return saved successfully",
        })

    except Exception as e:
        logger.exception(f"Save return error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.get("/{return_id}")
async def get_return(return_id: str, request: Request):
    """Get a tax return by ID."""
    try:
        persistence = _get_persistence()
        tax_return = persistence.load_return(return_id)

        if not tax_return:
            raise HTTPException(status_code=404, detail="Return not found")

        return JSONResponse({
            "status": "success",
            "return": tax_return,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get return error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.get("")
async def list_returns(
    request: Request,
    tax_year: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """List tax returns with optional filters."""
    try:
        persistence = _get_persistence()
        returns = persistence.list_returns(
            tax_year=tax_year,
            status=status,
            limit=limit,
            offset=offset,
        )

        return JSONResponse({
            "status": "success",
            "returns": returns,
            "count": len(returns),
            "limit": limit,
            "offset": offset,
        })

    except Exception as e:
        logger.exception(f"List returns error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.delete("/{return_id}")
async def delete_return(return_id: str, request: Request):
    """Delete a tax return."""
    try:
        persistence = _get_persistence()

        # Verify return exists
        tax_return = persistence.load_return(return_id)
        if not tax_return:
            raise HTTPException(status_code=404, detail="Return not found")

        # Delete
        persistence.delete_return(return_id)

        return JSONResponse({
            "status": "success",
            "message": "Return deleted",
            "return_id": return_id,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Delete return error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


# =============================================================================
# WORKFLOW ROUTES
# =============================================================================

@router.get("/{session_id}/status")
async def get_return_status(session_id: str, request: Request):
    """Get the status of a return (DRAFT, IN_REVIEW, CPA_APPROVED)."""
    try:
        session_persistence = _get_session_persistence()
        status_info = session_persistence.get_return_status(session_id)

        if not status_info:
            # Return default status if no explicit status set
            return JSONResponse({
                "status": "success",
                "session_id": session_id,
                "return_status": "DRAFT",
                "message": "No status record found, defaulting to DRAFT",
            })

        return JSONResponse({
            "status": "success",
            "session_id": session_id,
            "return_status": status_info.get("status", "DRAFT"),
            "cpa_reviewer_name": status_info.get("cpa_reviewer_name"),
            "review_notes": status_info.get("review_notes"),
            "last_status_change": status_info.get("last_status_change"),
            "approval_timestamp": status_info.get("approval_timestamp"),
        })

    except Exception as e:
        logger.exception(f"Get status error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/{session_id}/submit-for-review")
async def submit_for_review(session_id: str, request: Request):
    """Submit a return for CPA review."""
    try:
        session_persistence = _get_session_persistence()

        # Check current status
        current_status = session_persistence.get_return_status(session_id)
        if current_status and current_status.get("status") == "CPA_APPROVED":
            raise HTTPException(
                status_code=400,
                detail="Cannot submit already approved return for review"
            )

        # Update status to IN_REVIEW
        new_status = session_persistence.set_return_status(
            session_id=session_id,
            status="IN_REVIEW",
        )

        return JSONResponse({
            "status": "success",
            "message": "Return submitted for CPA review",
            "session_id": session_id,
            "return_status": "IN_REVIEW",
            "submitted_at": new_status.get("last_status_change"),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Submit for review error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/{session_id}/approve")
async def approve_return(session_id: str, request: Request):
    """CPA approval of a return."""
    try:
        body = await request.json()
        cpa_reviewer_id = body.get("cpa_reviewer_id")
        cpa_reviewer_name = body.get("cpa_reviewer_name", "CPA Reviewer")
        review_notes = body.get("review_notes")

        session_persistence = _get_session_persistence()

        # Check current status
        current_status = session_persistence.get_return_status(session_id)
        if current_status and current_status.get("status") == "CPA_APPROVED":
            raise HTTPException(
                status_code=400,
                detail="Return already approved"
            )

        # Generate approval signature hash
        import hashlib
        approval_data = f"{session_id}:{cpa_reviewer_id}:{datetime.utcnow().isoformat()}"
        approval_hash = hashlib.sha256(approval_data.encode()).hexdigest()

        # Update status to CPA_APPROVED
        new_status = session_persistence.set_return_status(
            session_id=session_id,
            status="CPA_APPROVED",
            cpa_reviewer_id=cpa_reviewer_id,
            cpa_reviewer_name=cpa_reviewer_name,
            review_notes=review_notes,
            approval_signature_hash=approval_hash,
        )

        return JSONResponse({
            "status": "success",
            "message": "Return approved by CPA",
            "session_id": session_id,
            "return_status": "CPA_APPROVED",
            "cpa_reviewer_name": cpa_reviewer_name,
            "approval_timestamp": new_status.get("approval_timestamp"),
            "approval_signature": approval_hash[:16] + "...",
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Approve return error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/{session_id}/revert-to-draft")
async def revert_to_draft(session_id: str, request: Request):
    """Revert a return back to draft status."""
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        reason = body.get("reason", "Reverted to draft for edits")

        session_persistence = _get_session_persistence()

        # Update status to DRAFT
        new_status = session_persistence.set_return_status(
            session_id=session_id,
            status="DRAFT",
            review_notes=reason,
        )

        return JSONResponse({
            "status": "success",
            "message": "Return reverted to draft",
            "session_id": session_id,
            "return_status": "DRAFT",
            "reason": reason,
        })

    except Exception as e:
        logger.exception(f"Revert to draft error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.get("/queue/{status}")
async def get_returns_by_status(
    status: str,
    request: Request,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """Get returns by workflow status (for CPA queue)."""
    try:
        # Validate status
        valid_statuses = {"DRAFT", "IN_REVIEW", "CPA_APPROVED"}
        if status.upper() not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )

        session_persistence = _get_session_persistence()
        returns = session_persistence.list_returns_by_status(
            status=status.upper(),
            limit=limit,
            offset=offset,
        )

        return JSONResponse({
            "status": "success",
            "queue_status": status.upper(),
            "returns": returns,
            "count": len(returns),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get queue error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


# =============================================================================
# NOTES ROUTES
# =============================================================================

@router.post("/{session_id}/notes")
async def add_return_note(session_id: str, request: Request):
    """Add a note to a return."""
    try:
        body = await request.json()
        note_text = body.get("note", body.get("text", ""))
        note_type = body.get("type", "general")
        author = body.get("author", "User")

        if not note_text:
            raise HTTPException(status_code=400, detail="Note text is required")

        # Load existing notes
        session_persistence = _get_session_persistence()
        session_record = session_persistence.load_session(session_id)

        if not session_record:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get or create notes list
        session_data = session_record.data or {}
        notes = session_data.get("notes", [])

        # Add new note
        new_note = {
            "id": str(uuid.uuid4()),
            "text": note_text,
            "type": note_type,
            "author": author,
            "created_at": datetime.utcnow().isoformat(),
        }
        notes.append(new_note)
        session_data["notes"] = notes

        # Save session
        session_persistence.save_session(
            session_id=session_id,
            tenant_id=session_record.tenant_id,
            session_type=session_record.session_type,
            data=session_data,
            metadata=session_record.metadata,
        )

        return JSONResponse({
            "status": "success",
            "message": "Note added",
            "note": new_note,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Add note error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.get("/{session_id}/notes")
async def get_return_notes(session_id: str, request: Request):
    """Get all notes for a return."""
    try:
        session_persistence = _get_session_persistence()
        session_record = session_persistence.load_session(session_id)

        if not session_record:
            raise HTTPException(status_code=404, detail="Session not found")

        session_data = session_record.data or {}
        notes = session_data.get("notes", [])

        return JSONResponse({
            "status": "success",
            "session_id": session_id,
            "notes": notes,
            "count": len(notes),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get notes error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )
