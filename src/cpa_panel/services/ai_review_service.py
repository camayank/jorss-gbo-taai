"""
CPA Review Gate for AI-Generated Responses.

Flow:
1. Client asks question -> AI generates draft response
2. If firm has review mode enabled, draft is queued (status=PENDING)
3. CPA sees queue on their dashboard
4. CPA approves (one-click) or edits -> response released to client
5. Client sees response (attributed as "from [CPA Firm Name]")
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"


@dataclass
class AIResponseDraft:
    draft_id: str
    session_id: str
    firm_id: str
    client_question: str
    ai_response: str
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    edited_response: Optional[str] = None
    review_note: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: Optional[datetime] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    complexity: Optional[str] = None
    estimated_savings: Optional[float] = None


class AIReviewService:
    """Service for managing AI response review queue."""

    def __init__(self):
        self._drafts: Dict[str, AIResponseDraft] = {}

    def queue_for_review(
        self,
        session_id: str,
        firm_id: str,
        client_question: str,
        ai_response: str,
        client_name: Optional[str] = None,
        client_email: Optional[str] = None,
        complexity: Optional[str] = None,
        estimated_savings: Optional[float] = None,
    ) -> AIResponseDraft:
        """Queue an AI-generated response for CPA review."""
        draft = AIResponseDraft(
            draft_id=str(uuid4()),
            session_id=session_id,
            firm_id=firm_id,
            client_question=client_question,
            ai_response=ai_response,
            client_name=client_name,
            client_email=client_email,
            complexity=complexity,
            estimated_savings=estimated_savings,
        )
        self._drafts[draft.draft_id] = draft
        logger.info(f"Queued AI response {draft.draft_id} for review (firm={firm_id})")
        return draft

    def get_pending_reviews(self, firm_id: str) -> List[AIResponseDraft]:
        """Get all pending reviews for a firm."""
        return sorted(
            [d for d in self._drafts.values()
             if d.firm_id == firm_id and d.status == ReviewStatus.PENDING],
            key=lambda d: d.created_at,
            reverse=True,
        )

    def get_review_stats(self, firm_id: str) -> Dict[str, Any]:
        """Get review queue stats for a firm."""
        firm_drafts = [d for d in self._drafts.values() if d.firm_id == firm_id]
        return {
            "pending": sum(1 for d in firm_drafts if d.status == ReviewStatus.PENDING),
            "approved": sum(1 for d in firm_drafts if d.status == ReviewStatus.APPROVED),
            "edited": sum(1 for d in firm_drafts if d.status == ReviewStatus.EDITED),
            "rejected": sum(1 for d in firm_drafts if d.status == ReviewStatus.REJECTED),
            "total": len(firm_drafts),
        }

    def approve_draft(
        self,
        draft_id: str,
        reviewer_id: str,
        reviewer_name: str,
    ) -> Optional[AIResponseDraft]:
        """Approve an AI response as-is."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        draft.status = ReviewStatus.APPROVED
        draft.reviewer_id = reviewer_id
        draft.reviewer_name = reviewer_name
        draft.reviewed_at = datetime.now(timezone.utc)
        logger.info(f"Draft {draft_id} approved by {reviewer_name}")
        return draft

    def edit_and_approve(
        self,
        draft_id: str,
        reviewer_id: str,
        reviewer_name: str,
        edited_response: str,
        review_note: Optional[str] = None,
    ) -> Optional[AIResponseDraft]:
        """Edit and approve an AI response."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        draft.status = ReviewStatus.EDITED
        draft.reviewer_id = reviewer_id
        draft.reviewer_name = reviewer_name
        draft.edited_response = edited_response
        draft.review_note = review_note
        draft.reviewed_at = datetime.now(timezone.utc)
        logger.info(f"Draft {draft_id} edited and approved by {reviewer_name}")
        return draft

    def reject_draft(
        self,
        draft_id: str,
        reviewer_id: str,
        reviewer_name: str,
        review_note: str,
    ) -> Optional[AIResponseDraft]:
        """Reject an AI response."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        draft.status = ReviewStatus.REJECTED
        draft.reviewer_id = reviewer_id
        draft.reviewer_name = reviewer_name
        draft.review_note = review_note
        draft.reviewed_at = datetime.now(timezone.utc)
        logger.info(f"Draft {draft_id} rejected by {reviewer_name}")
        return draft

    def get_final_response(self, draft_id: str) -> Optional[str]:
        """Get the final response to send to the client."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        if draft.status == ReviewStatus.EDITED:
            return draft.edited_response
        if draft.status == ReviewStatus.APPROVED:
            return draft.ai_response
        return None


# Singleton
ai_review_service = AIReviewService()
