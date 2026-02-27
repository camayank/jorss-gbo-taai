"""
CPA Panel Notes Routes

Endpoints for CPA review notes management.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

from .common import get_notes_manager

logger = logging.getLogger(__name__)

notes_router = APIRouter(tags=["CPA Notes"])


@notes_router.post("/returns/{session_id}/notes")
async def add_note(session_id: str, request: Request):
    """
    Add a CPA review note.

    Request body:
        - text: Note content (required) - also accepts 'note_text'
        - category: Note category (general, review, question, etc.)
        - is_internal: Whether note is internal-only
        - cpa_id: CPA identifier
        - cpa_name: CPA name
    """
    from cpa_panel.workflow.notes import NoteCategory

    try:
        body = await request.json()
    except Exception as e:
        logger.debug(f"Failed to parse request body: {e}")
        body = {}

    note_text = body.get("text") or body.get("note_text", "")
    note_text = note_text.strip() if note_text else ""

    category_str = body.get("category", "general")
    is_internal = body.get("is_internal", False)
    cpa_id = body.get("cpa_id", "")
    cpa_name = body.get("cpa_name", "CPA")

    if not note_text:
        raise HTTPException(status_code=400, detail="Note text is required (use 'text' or 'note_text' field)")

    try:
        category = NoteCategory(category_str.lower())
    except ValueError:
        category = NoteCategory.GENERAL

    try:
        manager = get_notes_manager()
        note = manager.add_note(
            session_id=session_id,
            text=note_text,
            cpa_id=cpa_id,
            cpa_name=cpa_name,
            category=category,
            is_internal=is_internal,
        )

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "note": note.to_dict(),
            "message": "Note added successfully",
        })
    except Exception as e:
        logger.error(f"Error adding note: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred")


@notes_router.get("/returns/{session_id}/notes")
async def get_notes(session_id: str, request: Request, include_internal: bool = False):
    """
    Get all notes for a return.

    Args:
        include_internal: Include internal-only notes (for CPA view)
    """
    try:
        manager = get_notes_manager()
        notes = manager.get_notes(session_id, include_internal=include_internal)

        if hasattr(manager, 'get_note_summary'):
            summary = manager.get_note_summary(session_id)
        else:
            summary = {
                "total_notes": len(notes),
                "internal_notes": sum(1 for n in notes if n.is_internal),
                "client_visible_notes": sum(1 for n in notes if not n.is_internal),
                "by_category": {},
                "last_note": notes[-1].timestamp.isoformat() if notes else None,
            }

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "notes": [n.to_dict() for n in notes],
            "summary": summary,
        })
    except Exception as e:
        logger.error(f"Error getting notes: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@notes_router.delete("/returns/{session_id}/notes/{note_id}")
async def delete_note(session_id: str, note_id: str, request: Request):
    """Delete a note by ID."""
    try:
        manager = get_notes_manager()
        result = manager.delete_note(session_id, note_id)

        if not result:
            raise HTTPException(status_code=404, detail="Note not found")

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "note_id": note_id,
            "message": "Note deleted successfully",
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting note: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")
