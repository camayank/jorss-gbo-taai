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
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_status_change: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
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

    def _check_submission_readiness(self, session_id: str, tenant_id: str = "default") -> Tuple[bool, List[str]]:
        """
        Check if a return is ready to submit for CPA review.

        Guard condition for DRAFT→IN_REVIEW transition.

        Returns:
            Tuple of (is_ready, list_of_errors)
        """
        errors = []

        # Load session data and return information
        persistence = self._get_persistence()
        session = persistence.get_session(session_id, tenant_id)
        if not session:
            errors.append("Session not found")
            return (False, errors)

        # Extract return data
        return_data = session.get("data", {}).get("return_data", {})

        # Check required fields from form_1040_parser
        required_fields = [
            "taxpayer_name",
            "wages_salaries_tips",
            "total_income",
            "adjusted_gross_income",
            "taxable_income",
            "tax",
            "total_tax",
            "federal_withholding"
        ]

        for field in required_fields:
            if not return_data.get(field):
                errors.append(f"Missing required field: {field}")

        # Check for validation errors
        validation_errors = return_data.get("validation_errors", [])
        if validation_errors:
            errors.append(f"Return has {len(validation_errors)} validation error(s)")

        return (len(errors) == 0, errors)

    def _send_in_review_notification(self, session_id: str, tenant_id: str = "default"):
        """
        Entry action: Send CPA notification when return enters IN_REVIEW.

        Uses notification_integration for email delivery.
        """
        try:
            from notifications.notification_integration import get_delivery_service

            # Load session to get taxpayer and return info
            persistence = self._get_persistence()
            session = persistence.get_session(session_id, tenant_id)
            if not session:
                logger.warning(f"Cannot send IN_REVIEW notification: session {session_id} not found")
                return

            data = session.get("data", {})
            taxpayer_name = data.get("taxpayer_name", "Unknown Taxpayer")
            tax_year = data.get("tax_year", 2025)

            # Get CPAs in the firm to notify (placeholder - would need real CPA list)
            # For now, log that notification should be sent
            service = get_delivery_service()
            logger.info(
                f"IN_REVIEW notification triggered for session {session_id}: "
                f"{taxpayer_name} (tax year {tax_year}) submitted for CPA review. "
                f"Implementation requires CPA team email configuration."
            )

        except ImportError:
            logger.warning("Notification service not available for IN_REVIEW trigger")
        except Exception as e:
            logger.error(f"Error sending IN_REVIEW notification: {e}")

    def _trigger_cpa_approved_actions(self, session_id: str, tenant_id: str = "default"):
        """
        Entry action: Trigger export-ready flag and related actions when return is CPA_APPROVED.

        Sets internal state and triggers downstream processes.
        """
        try:
            persistence = self._get_persistence()
            session = persistence.get_session(session_id, tenant_id)
            if not session:
                logger.warning(f"Cannot trigger CPA_APPROVED actions: session {session_id} not found")
                return

            # Mark as export-ready by setting flag in session data
            if "data" not in session:
                session["data"] = {}
            session["data"]["export_ready"] = True
            session["data"]["export_ready_timestamp"] = datetime.now(timezone.utc).isoformat()

            # Persist the export-ready flag
            persistence.update_session(session_id, session, tenant_id)

            logger.info(f"CPA_APPROVED actions triggered for session {session_id}: export-ready flag set")

        except Exception as e:
            logger.error(f"Error triggering CPA_APPROVED actions: {e}")

    def check_and_escalate_stale_reviews(
        self,
        tenant_id: str = "default",
        timeout_hours: int = 48
    ) -> List[str]:
        """
        Check for returns in IN_REVIEW > timeout_hours and escalate them.

        Returns:
            List of escalated session IDs
        """
        escalated = []
        try:
            persistence = self._get_persistence()
            reviews = persistence.list_returns_by_status("IN_REVIEW", tenant_id, limit=1000)

            threshold = datetime.now(timezone.utc) - timedelta(hours=timeout_hours)

            for review in reviews:
                last_change = review.get("last_status_change")
                if isinstance(last_change, str):
                    last_change = datetime.fromisoformat(last_change.replace("Z", "+00:00"))

                if last_change and last_change < threshold:
                    # Log escalation event
                    session_id = review["session_id"]
                    logger.warning(
                        f"Return {session_id} in IN_REVIEW for > {timeout_hours} hours. "
                        f"Escalation: notify management team."
                    )

                    # Mark in audit trail if available
                    if self._audit_logger:
                        self._audit_logger(
                            session_id=session_id,
                            event_type="REVIEW_TIMEOUT",
                            description=f"Return exceeded {timeout_hours}hr review timeout",
                            metadata={"threshold_hours": timeout_hours}
                        )

                    escalated.append(session_id)

        except Exception as e:
            logger.error(f"Error checking review timeouts: {e}")

        return escalated

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
            created_at=datetime.fromisoformat(record["created_at"]) if record.get("created_at") else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(record["updated_at"]) if record.get("updated_at") else datetime.now(timezone.utc),
            last_status_change=datetime.fromisoformat(record["last_status_change"]) if record.get("last_status_change") else datetime.now(timezone.utc),
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

        Enforces guards and triggers side effects:
        - DRAFT→IN_REVIEW: Requires fields complete + no errors; sends CPA notification
        - Any→CPA_APPROVED: Triggers export-ready flag

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
            WorkflowTransitionError: If transition is invalid or guards fail
        """
        current = self.get_status(session_id, tenant_id)
        can_transition, error_msg = self.can_transition(session_id, target_status)

        if not can_transition:
            raise WorkflowTransitionError(
                error_msg,
                current.status.value,
                target_status.value
            )

        # Guard: DRAFT→IN_REVIEW requires submission readiness
        if current.status == ReturnStatus.DRAFT and target_status == ReturnStatus.IN_REVIEW:
            is_ready, errors = self._check_submission_readiness(session_id, tenant_id)
            if not is_ready:
                error_details = "; ".join(errors)
                raise WorkflowTransitionError(
                    f"Return not ready for review: {error_details}",
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

        # Entry actions: Trigger side effects based on target status
        if target_status == ReturnStatus.IN_REVIEW:
            self._send_in_review_notification(session_id, tenant_id)

        if target_status == ReturnStatus.CPA_APPROVED:
            self._trigger_cpa_approved_actions(session_id, tenant_id)

        # Emit webhook event for status change
        try:
            from webhooks.triggers import trigger_return_status_changed
            trigger_return_status_changed(
                firm_id=tenant_id,
                return_id=session_id,
                previous_status=current.status.value,
                new_status=target_status.value,
                changed_by=cpa_reviewer_id,
                notes=notes,
            )
        except ImportError:
            pass  # Webhooks module not available

        return self.get_status(session_id, tenant_id)

    def submit_for_review(self, session_id: str, tenant_id: str = "default") -> StatusRecord:
        """
        Submit a return for CPA review.

        Guards:
        - All required fields must be populated
        - No validation errors present
        - Return must be in DRAFT status

        Entry Actions:
        - Sends CPA notification of new submission
        - Marks return as read-only to taxpayer

        Args:
            session_id: Session/return identifier
            tenant_id: Tenant identifier

        Returns:
            Updated StatusRecord

        Raises:
            WorkflowTransitionError: If submission guards fail
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

        Entry Actions:
        - Sets export-ready flag
        - Enables full feature access (export, smart insights)
        - Records approval timestamp and signature

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
                created_at=datetime.fromisoformat(r["created_at"]) if r.get("created_at") else datetime.now(timezone.utc),
                updated_at=datetime.fromisoformat(r["updated_at"]) if r.get("updated_at") else datetime.now(timezone.utc),
                last_status_change=datetime.fromisoformat(r["last_status_change"]) if r.get("last_status_change") else datetime.now(timezone.utc),
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
