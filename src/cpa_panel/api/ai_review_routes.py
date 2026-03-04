"""
CPA AI Review Queue API routes.

Provides endpoints for CPAs to review, approve, edit, or reject
AI-generated responses before they are sent to clients.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cpa_panel.services.ai_review_service import ai_review_service

logger = logging.getLogger(__name__)

ai_review_router = APIRouter(prefix="/ai-review", tags=["AI Review"])


class ApproveRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str


class EditApproveRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str
    edited_response: str
    review_note: Optional[str] = None


class RejectRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str
    review_note: str


@ai_review_router.get("/pending/{firm_id}")
async def get_pending_reviews(firm_id: str):
    """Get all pending AI response drafts for a firm."""
    drafts = ai_review_service.get_pending_reviews(firm_id)
    return {
        "count": len(drafts),
        "drafts": [
            {
                "draft_id": d.draft_id,
                "session_id": d.session_id,
                "client_question": d.client_question,
                "ai_response": d.ai_response,
                "client_name": d.client_name,
                "client_email": d.client_email,
                "complexity": d.complexity,
                "estimated_savings": d.estimated_savings,
                "created_at": d.created_at.isoformat(),
            }
            for d in drafts
        ],
    }


@ai_review_router.get("/stats/{firm_id}")
async def get_review_stats(firm_id: str):
    """Get review queue stats for a firm."""
    return ai_review_service.get_review_stats(firm_id)


@ai_review_router.post("/{draft_id}/approve")
async def approve_draft(draft_id: str, req: ApproveRequest):
    """One-click approve an AI response."""
    draft = ai_review_service.approve_draft(
        draft_id, req.reviewer_id, req.reviewer_name
    )
    if not draft:
        raise HTTPException(404, "Draft not found")
    return {"status": "approved", "draft_id": draft_id}


@ai_review_router.post("/{draft_id}/edit-approve")
async def edit_and_approve(draft_id: str, req: EditApproveRequest):
    """Edit and approve an AI response."""
    draft = ai_review_service.edit_and_approve(
        draft_id, req.reviewer_id, req.reviewer_name,
        req.edited_response, req.review_note
    )
    if not draft:
        raise HTTPException(404, "Draft not found")
    return {"status": "edited", "draft_id": draft_id}


@ai_review_router.post("/{draft_id}/reject")
async def reject_draft(draft_id: str, req: RejectRequest):
    """Reject an AI response."""
    draft = ai_review_service.reject_draft(
        draft_id, req.reviewer_id, req.reviewer_name, req.review_note
    )
    if not draft:
        raise HTTPException(404, "Draft not found")
    return {"status": "rejected", "draft_id": draft_id}


@ai_review_router.get("/{draft_id}/response")
async def get_final_response(draft_id: str):
    """Get the final approved response to deliver to the client."""
    response = ai_review_service.get_final_response(draft_id)
    if response is None:
        raise HTTPException(404, "Draft not found or not yet approved")
    return {"draft_id": draft_id, "response": response}
