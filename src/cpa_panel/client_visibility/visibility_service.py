"""
Client Visibility Service

Provides read-only visibility data for clients.

SCOPE BOUNDARIES (ENFORCED):
- Status display: YES
- Next steps: YES
- CPA contact info: YES
- Document upload status: YES
- Messaging: NO (out of scope)
- Task management: NO (out of scope)
- Comments: NO (out of scope)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ReturnStatusDisplay(str, Enum):
    """Client-facing status display values."""
    GATHERING_INFO = "gathering_info"      # Initial data collection
    IN_PREPARATION = "in_preparation"      # CPA is preparing
    READY_FOR_REVIEW = "ready_for_review"  # CPA review in progress
    AWAITING_SIGNATURE = "awaiting_signature"  # Needs client signature
    APPROVED = "approved"                  # CPA approved, ready to file
    FILED = "filed"                        # Filed with IRS
    ACCEPTED = "accepted"                  # IRS accepted
    COMPLETED = "completed"                # Engagement complete

    @property
    def display_text(self) -> str:
        """Human-readable status text for clients."""
        texts = {
            ReturnStatusDisplay.GATHERING_INFO: "Gathering Information",
            ReturnStatusDisplay.IN_PREPARATION: "In Preparation",
            ReturnStatusDisplay.READY_FOR_REVIEW: "Under CPA Review",
            ReturnStatusDisplay.AWAITING_SIGNATURE: "Awaiting Your Signature",
            ReturnStatusDisplay.APPROVED: "Approved - Ready to File",
            ReturnStatusDisplay.FILED: "Filed with IRS",
            ReturnStatusDisplay.ACCEPTED: "Accepted by IRS",
            ReturnStatusDisplay.COMPLETED: "Completed",
        }
        return texts.get(self, self.value.replace("_", " ").title())

    @property
    def progress_percent(self) -> int:
        """Progress percentage for visual display."""
        progress = {
            ReturnStatusDisplay.GATHERING_INFO: 10,
            ReturnStatusDisplay.IN_PREPARATION: 30,
            ReturnStatusDisplay.READY_FOR_REVIEW: 50,
            ReturnStatusDisplay.AWAITING_SIGNATURE: 65,
            ReturnStatusDisplay.APPROVED: 80,
            ReturnStatusDisplay.FILED: 90,
            ReturnStatusDisplay.ACCEPTED: 95,
            ReturnStatusDisplay.COMPLETED: 100,
        }
        return progress.get(self, 0)


@dataclass
class NextStep:
    """A next step action for the client."""
    step_id: str
    title: str
    description: str
    action_type: str  # "upload", "sign", "review", "wait", "contact"
    is_client_action: bool  # True if client needs to do something
    is_complete: bool = False
    due_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "action_type": self.action_type,
            "is_client_action": self.is_client_action,
            "is_complete": self.is_complete,
            "due_date": self.due_date.isoformat() if self.due_date else None,
        }


@dataclass
class CPAContactInfo:
    """CPA contact information for client display."""
    firm_name: str
    cpa_name: str
    email: str
    phone: Optional[str] = None
    office_hours: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "firm_name": self.firm_name,
            "cpa_name": self.cpa_name,
            "email": self.email,
            "phone": self.phone,
            "office_hours": self.office_hours,
        }


@dataclass
class DocumentStatus:
    """Status of a requested/uploaded document."""
    document_type: str  # "W-2", "1099", "K-1", etc.
    description: str
    is_required: bool
    is_received: bool
    received_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_type": self.document_type,
            "description": self.description,
            "is_required": self.is_required,
            "is_received": self.is_received,
            "received_at": self.received_at.isoformat() if self.received_at else None,
        }


@dataclass
class ClientVisibilityData:
    """
    Complete visibility data for a client.

    This is what the client sees - nothing more.
    """
    session_id: str
    client_name: str
    tax_year: int

    # Status
    status: ReturnStatusDisplay
    status_updated_at: datetime

    # Next steps (max 3-4 items)
    next_steps: List[NextStep]

    # CPA contact
    cpa_contact: CPAContactInfo

    # Documents
    documents_requested: List[DocumentStatus]
    documents_pending_count: int

    # Key dates (no full calendar - just essential dates)
    filing_deadline: Optional[datetime] = None
    extension_deadline: Optional[datetime] = None

    # Simple flags
    has_pending_signature: bool = False
    can_upload_documents: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "client_name": self.client_name,
            "tax_year": self.tax_year,
            "status": {
                "code": self.status.value,
                "display": self.status.display_text,
                "progress_percent": self.status.progress_percent,
                "updated_at": self.status_updated_at.isoformat(),
            },
            "next_steps": [step.to_dict() for step in self.next_steps],
            "cpa_contact": self.cpa_contact.to_dict(),
            "documents": {
                "items": [doc.to_dict() for doc in self.documents_requested],
                "pending_count": self.documents_pending_count,
                "can_upload": self.can_upload_documents,
            },
            "key_dates": {
                "filing_deadline": self.filing_deadline.isoformat() if self.filing_deadline else None,
                "extension_deadline": self.extension_deadline.isoformat() if self.extension_deadline else None,
            },
            "has_pending_signature": self.has_pending_signature,
        }


class ClientVisibilityService:
    """
    Service for generating client visibility data.

    SCOPE: Read-only status, next steps, contact, documents.
    NOT IN SCOPE: Messaging, tasks, comments, account management.
    """

    # Map internal workflow status to client-facing status
    STATUS_MAP = {
        "new": ReturnStatusDisplay.GATHERING_INFO,
        "in_progress": ReturnStatusDisplay.IN_PREPARATION,
        "ready_for_review": ReturnStatusDisplay.READY_FOR_REVIEW,
        "in_review": ReturnStatusDisplay.READY_FOR_REVIEW,
        "reviewed": ReturnStatusDisplay.AWAITING_SIGNATURE,
        "cpa_approved": ReturnStatusDisplay.APPROVED,
        "draft": ReturnStatusDisplay.IN_PREPARATION,
        "filed": ReturnStatusDisplay.FILED,
        "accepted": ReturnStatusDisplay.ACCEPTED,
        "delivered": ReturnStatusDisplay.COMPLETED,
        "archived": ReturnStatusDisplay.COMPLETED,
    }

    def __init__(self):
        """Initialize visibility service."""
        pass

    def get_visibility_data(
        self,
        session_id: str,
        session_data: Dict[str, Any],
        cpa_info: Dict[str, Any],
        documents: Optional[List[Dict[str, Any]]] = None,
    ) -> ClientVisibilityData:
        """
        Generate visibility data for a client.

        Args:
            session_id: Tax return session ID
            session_data: Session/return data from database
            cpa_info: CPA/firm information
            documents: List of document statuses

        Returns:
            ClientVisibilityData for client display
        """
        # Map status
        internal_status = session_data.get("status", "new").lower()
        display_status = self.STATUS_MAP.get(internal_status, ReturnStatusDisplay.GATHERING_INFO)

        # Generate next steps based on status
        next_steps = self._generate_next_steps(display_status, session_data, documents)

        # Build CPA contact
        cpa_contact = CPAContactInfo(
            firm_name=cpa_info.get("firm_name", ""),
            cpa_name=cpa_info.get("cpa_name", ""),
            email=cpa_info.get("email", ""),
            phone=cpa_info.get("phone"),
            office_hours=cpa_info.get("office_hours"),
        )

        # Process documents
        doc_statuses = []
        pending_count = 0
        if documents:
            for doc in documents:
                is_received = doc.get("is_received", False)
                doc_status = DocumentStatus(
                    document_type=doc.get("document_type", "Document"),
                    description=doc.get("description", ""),
                    is_required=doc.get("is_required", True),
                    is_received=is_received,
                    received_at=datetime.fromisoformat(doc["received_at"]) if doc.get("received_at") else None,
                )
                doc_statuses.append(doc_status)
                if doc.get("is_required") and not is_received:
                    pending_count += 1

        # Determine if signature is pending
        has_pending_signature = display_status == ReturnStatusDisplay.AWAITING_SIGNATURE

        # Determine if uploads are allowed
        can_upload = display_status in [
            ReturnStatusDisplay.GATHERING_INFO,
            ReturnStatusDisplay.IN_PREPARATION,
        ]

        return ClientVisibilityData(
            session_id=session_id,
            client_name=session_data.get("client_name", ""),
            tax_year=session_data.get("tax_year", 2025),
            status=display_status,
            status_updated_at=datetime.fromisoformat(session_data["status_updated_at"])
                if session_data.get("status_updated_at") else datetime.utcnow(),
            next_steps=next_steps,
            cpa_contact=cpa_contact,
            documents_requested=doc_statuses,
            documents_pending_count=pending_count,
            filing_deadline=datetime.fromisoformat(session_data["filing_deadline"])
                if session_data.get("filing_deadline") else None,
            extension_deadline=datetime.fromisoformat(session_data["extension_deadline"])
                if session_data.get("extension_deadline") else None,
            has_pending_signature=has_pending_signature,
            can_upload_documents=can_upload,
        )

    def _generate_next_steps(
        self,
        status: ReturnStatusDisplay,
        session_data: Dict[str, Any],
        documents: Optional[List[Dict[str, Any]]],
    ) -> List[NextStep]:
        """Generate next steps based on current status."""
        steps = []

        # Check for pending documents first
        if documents:
            pending_docs = [d for d in documents if d.get("is_required") and not d.get("is_received")]
            if pending_docs:
                steps.append(NextStep(
                    step_id="upload_docs",
                    title="Upload Missing Documents",
                    description=f"Please upload {len(pending_docs)} required document(s)",
                    action_type="upload",
                    is_client_action=True,
                ))

        # Status-specific steps
        if status == ReturnStatusDisplay.GATHERING_INFO:
            if not any(s.step_id == "upload_docs" for s in steps):
                steps.append(NextStep(
                    step_id="provide_info",
                    title="Complete Tax Information",
                    description="Provide your tax documents and information",
                    action_type="upload",
                    is_client_action=True,
                ))

        elif status == ReturnStatusDisplay.IN_PREPARATION:
            steps.append(NextStep(
                step_id="cpa_preparing",
                title="CPA Is Preparing Your Return",
                description="Your CPA is preparing your tax return. No action needed.",
                action_type="wait",
                is_client_action=False,
            ))

        elif status == ReturnStatusDisplay.READY_FOR_REVIEW:
            steps.append(NextStep(
                step_id="cpa_review",
                title="Under CPA Review",
                description="Your return is being reviewed. You'll be notified when ready.",
                action_type="wait",
                is_client_action=False,
            ))

        elif status == ReturnStatusDisplay.AWAITING_SIGNATURE:
            steps.append(NextStep(
                step_id="sign_engagement",
                title="Sign Engagement Letter",
                description="Please review and sign the engagement letter",
                action_type="sign",
                is_client_action=True,
            ))

        elif status == ReturnStatusDisplay.APPROVED:
            steps.append(NextStep(
                step_id="ready_to_file",
                title="Ready to File",
                description="Your return has been approved and will be filed soon",
                action_type="wait",
                is_client_action=False,
            ))

        elif status == ReturnStatusDisplay.FILED:
            steps.append(NextStep(
                step_id="awaiting_irs",
                title="Awaiting IRS Response",
                description="Your return has been filed. Waiting for IRS acceptance.",
                action_type="wait",
                is_client_action=False,
            ))

        elif status == ReturnStatusDisplay.ACCEPTED:
            steps.append(NextStep(
                step_id="irs_accepted",
                title="IRS Accepted",
                description="Great news! The IRS has accepted your return.",
                action_type="wait",
                is_client_action=False,
                is_complete=True,
            ))

        elif status == ReturnStatusDisplay.COMPLETED:
            steps.append(NextStep(
                step_id="completed",
                title="Engagement Complete",
                description="Your tax return has been completed. Thank you!",
                action_type="wait",
                is_client_action=False,
                is_complete=True,
            ))

        # Always add contact CPA as last step
        steps.append(NextStep(
            step_id="contact_cpa",
            title="Questions? Contact Your CPA",
            description="Reach out if you have any questions about your return",
            action_type="contact",
            is_client_action=True,
        ))

        return steps[:4]  # Max 4 steps to keep it simple
