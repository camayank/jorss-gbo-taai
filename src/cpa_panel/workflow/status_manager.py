"""
Return Status Manager for CPA Workflow

Manages the lifecycle of tax returns through the CPA review process:
- DRAFT: Initial state, editable by taxpayer
- IN_REVIEW: Submitted for CPA review, read-only to taxpayer
- CPA_APPROVED: Signed off by CPA, full feature access

CPA Compliance:
- All status transitions are audit-trailed
- Enforces valid transition rules
- Tracks reviewer assignments
"""

from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ReturnStatus(str, Enum):
    """Valid return statuses for CPA workflow."""
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    CPA_APPROVED = "CPA_APPROVED"

    @classmethod
    def from_string(cls, value: str) -> "ReturnStatus":
        """Convert string to ReturnStatus enum."""
        try:
            return cls(value.upper())
        except ValueError:
            return cls.DRAFT


class WorkflowTransitionError(Exception):
    """Raised when an invalid workflow transition is attempted."""
    def __init__(self, message: str, current_status: str, target_status: str):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(message)


# Valid status transitions
VALID_TRANSITIONS: Dict[ReturnStatus, List[ReturnStatus]] = {
    ReturnStatus.DRAFT: [ReturnStatus.IN_REVIEW],
    ReturnStatus.IN_REVIEW: [ReturnStatus.CPA_APPROVED, ReturnStatus.DRAFT],
    ReturnStatus.CPA_APPROVED: [ReturnStatus.DRAFT],  # CPA can revert if needed
}


@dataclass
class StatusRecord:
    """Record of a return's status."""
    session_id: str
    status: ReturnStatus
    tenant_id: str = "default"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_status_change: datetime = field(default_factory=datetime.utcnow)
    cpa_reviewer_id: Optional[str] = None
    cpa_reviewer_name: Optional[str] = None
    review_notes: Optional[str] = None
    approval_timestamp: Optional[datetime] = None
    approval_signature_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_status_change": self.last_status_change.isoformat(),
            "cpa_reviewer_id": self.cpa_reviewer_id,
            "cpa_reviewer_name": self.cpa_reviewer_name,
            "review_notes": self.review_notes,
            "approval_timestamp": self.approval_timestamp.isoformat() if self.approval_timestamp else None,
            "approval_signature_hash": self.approval_signature_hash,
        }


@dataclass
class FeatureAccess:
    """Feature access based on return status."""
    editable: bool = True
    export_enabled: bool = False
    smart_insights_enabled: bool = False
    cpa_approved: bool = False
    can_submit_for_review: bool = True
    can_approve: bool = False
    can_revert: bool = False

    @classmethod
    def for_status(cls, status: ReturnStatus, is_cpa: bool = False) -> "FeatureAccess":
        """Get feature access for a given status."""
        if status == ReturnStatus.DRAFT:
            return cls(
                editable=True,
                export_enabled=False,
                smart_insights_enabled=False,
                cpa_approved=False,
                can_submit_for_review=True,
                can_approve=False,
                can_revert=False,
            )
        elif status == ReturnStatus.IN_REVIEW:
            return cls(
                editable=is_cpa,  # CPA can edit during review
                export_enabled=False,
                smart_insights_enabled=False,
                cpa_approved=False,
                can_submit_for_review=False,
                can_approve=is_cpa,
                can_revert=is_cpa,
            )
        elif status == ReturnStatus.CPA_APPROVED:
            return cls(
                editable=False,
                export_enabled=True,
                smart_insights_enabled=True,
                cpa_approved=True,
                can_submit_for_review=False,
                can_approve=False,
                can_revert=is_cpa,
            )
        return cls()

    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary."""
        return {
            "editable": self.editable,
            "export_enabled": self.export_enabled,
            "smart_insights_enabled": self.smart_insights_enabled,
            "cpa_approved": self.cpa_approved,
            "can_submit_for_review": self.can_submit_for_review,
            "can_approve": self.can_approve,
            "can_revert": self.can_revert,
        }


class CPAWorkflowManager:
    """
    Manages the CPA review workflow for tax returns.

    CPA Compliance:
    - Enforces valid status transitions
    - Integrates with audit trail
    - Tracks reviewer assignments
    """

    def __init__(self, persistence=None, audit_logger=None):
        """
        Initialize workflow manager.

        Args:
            persistence: Database persistence layer (SessionPersistence)
            audit_logger: Audit trail logging function
        """
        self._persistence = persistence
        self._audit_logger = audit_logger

    def _get_persistence(self):
        """Get or create persistence layer."""
        if self._persistence is None:
            from database.session_persistence import get_session_persistence
            self._persistence = get_session_persistence()
        return self._persistence

    def get_status(self, session_id: str, tenant_id: Optional[str] = None) -> StatusRecord:
        """
        Get the current status of a return.

        Args:
            session_id: Session/return identifier
            tenant_id: Optional tenant filter

        Returns:
            StatusRecord with current status
        """
        persistence = self._get_persistence()
        record = persistence.get_return_status(session_id, tenant_id)

        if not record:
            # Default to DRAFT for new returns
            return StatusRecord(
                session_id=session_id,
                status=ReturnStatus.DRAFT,
                tenant_id=tenant_id or "default"
            )

        return StatusRecord(
            session_id=session_id,
            status=ReturnStatus.from_string(record["status"]),
            tenant_id=record.get("tenant_id", "default"),
            created_at=datetime.fromisoformat(record["created_at"]) if record.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(record["updated_at"]) if record.get("updated_at") else datetime.utcnow(),
            last_status_change=datetime.fromisoformat(record["last_status_change"]) if record.get("last_status_change") else datetime.utcnow(),
            cpa_reviewer_id=record.get("cpa_reviewer_id"),
            cpa_reviewer_name=record.get("cpa_reviewer_name"),
            review_notes=record.get("review_notes"),
            approval_timestamp=datetime.fromisoformat(record["approval_timestamp"]) if record.get("approval_timestamp") else None,
            approval_signature_hash=record.get("approval_signature_hash"),
        )

    def get_feature_access(self, session_id: str, is_cpa: bool = False) -> FeatureAccess:
        """
        Get feature access for a return based on its status.

        Args:
            session_id: Session/return identifier
            is_cpa: Whether the user is a CPA

        Returns:
            FeatureAccess with allowed features
        """
        status_record = self.get_status(session_id)
        return FeatureAccess.for_status(status_record.status, is_cpa)

    def can_transition(self, session_id: str, target_status: ReturnStatus) -> Tuple[bool, str]:
        """
        Check if a status transition is valid.

        Args:
            session_id: Session/return identifier
            target_status: Target status

        Returns:
            Tuple of (is_valid, error_message)
        """
        current = self.get_status(session_id)
        valid_targets = VALID_TRANSITIONS.get(current.status, [])

        if target_status in valid_targets:
            return (True, "")

        return (
            False,
            f"Cannot transition from {current.status.value} to {target_status.value}. "
            f"Valid transitions: {[s.value for s in valid_targets]}"
        )

    def transition(
        self,
        session_id: str,
        target_status: ReturnStatus,
        tenant_id: str = "default",
        cpa_reviewer_id: Optional[str] = None,
        cpa_reviewer_name: Optional[str] = None,
        notes: Optional[str] = None,
        signature_hash: Optional[str] = None,
    ) -> StatusRecord:
        """
        Transition a return to a new status.

        Args:
            session_id: Session/return identifier
            target_status: Target status
            tenant_id: Tenant identifier
            cpa_reviewer_id: CPA identifier (for review/approval)
            cpa_reviewer_name: CPA name
            notes: Review notes
            signature_hash: Approval signature hash

        Returns:
            Updated StatusRecord

        Raises:
            WorkflowTransitionError: If transition is invalid
        """
        current = self.get_status(session_id, tenant_id)
        can_transition, error_msg = self.can_transition(session_id, target_status)

        if not can_transition:
            raise WorkflowTransitionError(
                error_msg,
                current.status.value,
                target_status.value
            )

        persistence = self._get_persistence()
        persistence.set_return_status(
            session_id=session_id,
            status=target_status.value,
            tenant_id=tenant_id,
            cpa_reviewer_id=cpa_reviewer_id,
            cpa_reviewer_name=cpa_reviewer_name,
            review_notes=notes,
            approval_signature_hash=signature_hash,
        )

        # Log audit event if logger provided
        if self._audit_logger:
            self._audit_logger(
                session_id=session_id,
                event_type="STATUS_CHANGE",
                description=f"Status changed from {current.status.value} to {target_status.value}",
                metadata={
                    "previous_status": current.status.value,
                    "new_status": target_status.value,
                    "cpa_reviewer_id": cpa_reviewer_id,
                    "cpa_reviewer_name": cpa_reviewer_name,
                }
            )

        return self.get_status(session_id, tenant_id)

    def submit_for_review(self, session_id: str, tenant_id: str = "default") -> StatusRecord:
        """
        Submit a return for CPA review.

        Args:
            session_id: Session/return identifier
            tenant_id: Tenant identifier

        Returns:
            Updated StatusRecord
        """
        return self.transition(
            session_id=session_id,
            target_status=ReturnStatus.IN_REVIEW,
            tenant_id=tenant_id,
        )

    def approve(
        self,
        session_id: str,
        cpa_reviewer_id: str,
        cpa_reviewer_name: str,
        tenant_id: str = "default",
        notes: Optional[str] = None,
        signature_hash: Optional[str] = None,
    ) -> StatusRecord:
        """
        CPA approval of a return.

        Args:
            session_id: Session/return identifier
            cpa_reviewer_id: CPA identifier
            cpa_reviewer_name: CPA name
            tenant_id: Tenant identifier
            notes: Review notes
            signature_hash: Approval signature hash

        Returns:
            Updated StatusRecord
        """
        return self.transition(
            session_id=session_id,
            target_status=ReturnStatus.CPA_APPROVED,
            tenant_id=tenant_id,
            cpa_reviewer_id=cpa_reviewer_id,
            cpa_reviewer_name=cpa_reviewer_name,
            notes=notes,
            signature_hash=signature_hash,
        )

    def revert_to_draft(
        self,
        session_id: str,
        cpa_reviewer_id: str,
        reason: str,
        tenant_id: str = "default",
    ) -> StatusRecord:
        """
        Revert a return to DRAFT status.

        Args:
            session_id: Session/return identifier
            cpa_reviewer_id: CPA identifier
            reason: Reason for reverting
            tenant_id: Tenant identifier

        Returns:
            Updated StatusRecord
        """
        return self.transition(
            session_id=session_id,
            target_status=ReturnStatus.DRAFT,
            tenant_id=tenant_id,
            cpa_reviewer_id=cpa_reviewer_id,
            notes=f"Reverted: {reason}",
        )

    def list_by_status(
        self,
        status: ReturnStatus,
        tenant_id: str = "default",
        limit: int = 100,
        offset: int = 0,
    ) -> List[StatusRecord]:
        """
        List returns by status for CPA queue.

        Args:
            status: Filter by status
            tenant_id: Tenant identifier
            limit: Max results
            offset: Pagination offset

        Returns:
            List of StatusRecord
        """
        persistence = self._get_persistence()
        records = persistence.list_returns_by_status(
            status=status.value,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )

        return [
            StatusRecord(
                session_id=r["session_id"],
                status=ReturnStatus.from_string(r["status"]),
                created_at=datetime.fromisoformat(r["created_at"]) if r.get("created_at") else datetime.utcnow(),
                updated_at=datetime.fromisoformat(r["updated_at"]) if r.get("updated_at") else datetime.utcnow(),
                last_status_change=datetime.fromisoformat(r["last_status_change"]) if r.get("last_status_change") else datetime.utcnow(),
                cpa_reviewer_name=r.get("cpa_reviewer_name"),
            )
            for r in records
        ]

    def get_queue_counts(self, tenant_id: str = "default") -> Dict[str, int]:
        """
        Get counts of returns in each status.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dict mapping status to count
        """
        counts = {}
        for status in ReturnStatus:
            records = self.list_by_status(status, tenant_id, limit=1000)
            counts[status.value] = len(records)
        return counts
