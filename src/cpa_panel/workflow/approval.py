"""
CPA Approval Manager

Handles the CPA sign-off process with:
- Digital signature generation
- Approval verification
- Audit trail integration
"""

import hashlib
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ApprovalRecord:
    """Record of a CPA approval."""
    session_id: str
    cpa_reviewer_id: str
    cpa_reviewer_name: str
    approval_timestamp: datetime
    signature_hash: str
    review_notes: Optional[str] = None
    verification_status: str = "valid"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "cpa_reviewer_id": self.cpa_reviewer_id,
            "cpa_reviewer_name": self.cpa_reviewer_name,
            "approval_timestamp": self.approval_timestamp.isoformat(),
            "signature_hash": self.signature_hash,
            "review_notes": self.review_notes,
            "verification_status": self.verification_status,
        }


class ApprovalManager:
    """
    Manages CPA approval signatures and verification.

    CPA Compliance:
    - Generates cryptographic signature hashes
    - Provides verification for audit purposes
    - Integrates with audit trail
    """

    def __init__(self, workflow_manager=None, audit_logger=None):
        """
        Initialize approval manager.

        Args:
            workflow_manager: CPAWorkflowManager instance
            audit_logger: Audit trail logging function
        """
        self._workflow_manager = workflow_manager
        self._audit_logger = audit_logger

    def _get_workflow_manager(self):
        """Get or create workflow manager."""
        if self._workflow_manager is None:
            from .status_manager import CPAWorkflowManager
            self._workflow_manager = CPAWorkflowManager()
        return self._workflow_manager

    def generate_signature_hash(
        self,
        session_id: str,
        cpa_reviewer_id: str,
        timestamp: Optional[datetime] = None,
        pin: Optional[str] = None,
    ) -> str:
        """
        Generate a cryptographic signature hash for approval.

        Args:
            session_id: Session/return identifier
            cpa_reviewer_id: CPA identifier
            timestamp: Approval timestamp (default: now)
            pin: Optional CPA PIN for additional verification

        Returns:
            Signature hash string (first 16 characters)
        """
        timestamp = timestamp or datetime.utcnow()
        signature_data = f"{session_id}:{cpa_reviewer_id}:{timestamp.isoformat()}"

        if pin:
            signature_data += f":{pin}"

        full_hash = hashlib.sha256(signature_data.encode()).hexdigest()
        return full_hash[:16]  # Short hash for display

    def verify_signature(
        self,
        session_id: str,
        cpa_reviewer_id: str,
        timestamp: datetime,
        signature_hash: str,
        pin: Optional[str] = None,
    ) -> bool:
        """
        Verify an approval signature.

        Args:
            session_id: Session/return identifier
            cpa_reviewer_id: CPA identifier
            timestamp: Approval timestamp
            signature_hash: Signature to verify
            pin: Optional CPA PIN

        Returns:
            True if signature is valid
        """
        expected_hash = self.generate_signature_hash(
            session_id=session_id,
            cpa_reviewer_id=cpa_reviewer_id,
            timestamp=timestamp,
            pin=pin,
        )
        return expected_hash == signature_hash

    def approve_return(
        self,
        session_id: str,
        cpa_reviewer_id: str,
        cpa_reviewer_name: str,
        tenant_id: str = "default",
        review_notes: Optional[str] = None,
        pin: Optional[str] = None,
    ) -> ApprovalRecord:
        """
        Approve a tax return with CPA signature.

        Args:
            session_id: Session/return identifier
            cpa_reviewer_id: CPA identifier
            cpa_reviewer_name: CPA name for display
            tenant_id: Tenant identifier
            review_notes: Optional review notes
            pin: Optional CPA PIN for signature

        Returns:
            ApprovalRecord with approval details
        """
        timestamp = datetime.utcnow()
        signature_hash = self.generate_signature_hash(
            session_id=session_id,
            cpa_reviewer_id=cpa_reviewer_id,
            timestamp=timestamp,
            pin=pin,
        )

        # Update workflow status
        workflow = self._get_workflow_manager()
        workflow.approve(
            session_id=session_id,
            cpa_reviewer_id=cpa_reviewer_id,
            cpa_reviewer_name=cpa_reviewer_name,
            tenant_id=tenant_id,
            notes=review_notes,
            signature_hash=signature_hash,
        )

        # Log audit event
        if self._audit_logger:
            self._audit_logger(
                session_id=session_id,
                event_type="CPA_APPROVAL",
                description=f"Return approved by CPA: {cpa_reviewer_name}",
                metadata={
                    "cpa_reviewer_id": cpa_reviewer_id,
                    "cpa_reviewer_name": cpa_reviewer_name,
                    "signature_hash": signature_hash,
                    "review_notes": review_notes,
                }
            )

        return ApprovalRecord(
            session_id=session_id,
            cpa_reviewer_id=cpa_reviewer_id,
            cpa_reviewer_name=cpa_reviewer_name,
            approval_timestamp=timestamp,
            signature_hash=signature_hash,
            review_notes=review_notes,
        )

    def get_approval_record(self, session_id: str) -> Optional[ApprovalRecord]:
        """
        Get the approval record for a return.

        Args:
            session_id: Session/return identifier

        Returns:
            ApprovalRecord if approved, None otherwise
        """
        workflow = self._get_workflow_manager()
        status = workflow.get_status(session_id)

        if status.status.value != "CPA_APPROVED":
            return None

        if not status.approval_timestamp:
            return None

        return ApprovalRecord(
            session_id=session_id,
            cpa_reviewer_id=status.cpa_reviewer_id or "",
            cpa_reviewer_name=status.cpa_reviewer_name or "",
            approval_timestamp=status.approval_timestamp,
            signature_hash=status.approval_signature_hash or "",
            review_notes=status.review_notes,
        )

    def revoke_approval(
        self,
        session_id: str,
        cpa_reviewer_id: str,
        reason: str,
        tenant_id: str = "default",
    ) -> bool:
        """
        Revoke an approval and revert to DRAFT.

        Args:
            session_id: Session/return identifier
            cpa_reviewer_id: CPA identifier
            reason: Reason for revoking
            tenant_id: Tenant identifier

        Returns:
            True if successful
        """
        workflow = self._get_workflow_manager()

        try:
            workflow.revert_to_draft(
                session_id=session_id,
                cpa_reviewer_id=cpa_reviewer_id,
                reason=reason,
                tenant_id=tenant_id,
            )

            # Log audit event
            if self._audit_logger:
                self._audit_logger(
                    session_id=session_id,
                    event_type="APPROVAL_REVOKED",
                    description=f"Approval revoked: {reason}",
                    metadata={
                        "cpa_reviewer_id": cpa_reviewer_id,
                        "reason": reason,
                    }
                )

            return True
        except Exception as e:
            logger.error(f"Failed to revoke approval: {e}")
            return False


class ApprovalCertificate:
    """
    Generates approval certificates for client presentation.

    Provides a professional summary of the CPA approval for
    client records and compliance documentation.
    """

    @staticmethod
    def generate(approval: ApprovalRecord, return_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate an approval certificate.

        Args:
            approval: ApprovalRecord
            return_summary: Summary of the tax return

        Returns:
            Certificate data dictionary
        """
        return {
            "certificate_type": "CPA_APPROVAL",
            "session_id": approval.session_id,
            "issued_at": datetime.utcnow().isoformat(),
            "approval_details": {
                "cpa_name": approval.cpa_reviewer_name,
                "cpa_id": approval.cpa_reviewer_id,
                "approval_date": approval.approval_timestamp.isoformat(),
                "signature_hash": approval.signature_hash,
            },
            "return_summary": {
                "tax_year": return_summary.get("tax_year", 2025),
                "taxpayer_name": return_summary.get("taxpayer_name", ""),
                "gross_income": return_summary.get("gross_income", 0),
                "tax_liability": return_summary.get("tax_liability", 0),
                "refund_or_owed": return_summary.get("refund_or_owed", 0),
            },
            "review_notes": approval.review_notes,
            "verification": {
                "status": "verified",
                "message": "This return has been reviewed and approved by a licensed CPA.",
            },
            "disclaimer": (
                "This certificate confirms that the associated tax return has been "
                "reviewed and approved by the named CPA. The approval signature hash "
                "can be used to verify the authenticity of this approval."
            ),
        }
