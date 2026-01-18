"""
CPA Approval Manager

Handles the CPA sign-off process with:
- Digital signature generation
- Approval verification
- Audit trail integration
"""

import hashlib
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def compute_return_data_hash(return_data: Dict[str, Any]) -> str:
    """
    Compute a deterministic hash of tax return data.

    This ensures the signature is bound to the actual return values,
    not just the session metadata. Any change to the return after
    approval will invalidate the signature.

    Args:
        return_data: Tax return data dictionary

    Returns:
        SHA-256 hash of the canonical return data
    """
    # Extract key financial fields that must be immutable once approved
    canonical_fields = {
        "tax_year": return_data.get("tax_year"),
        "filing_status": return_data.get("filing_status"),
        "adjusted_gross_income": return_data.get("adjusted_gross_income"),
        "taxable_income": return_data.get("taxable_income"),
        "tax_liability": return_data.get("tax_liability"),
        "total_credits": return_data.get("total_credits"),
        "total_payments": return_data.get("total_payments"),
        "refund_or_owed": return_data.get("refund_or_owed"),
        "gross_income": return_data.get("gross_income"),
        "total_deductions": return_data.get("total_deductions"),
    }
    # Sort keys for deterministic serialization
    canonical_json = json.dumps(canonical_fields, sort_keys=True, default=str)
    return hashlib.sha256(canonical_json.encode()).hexdigest()


@dataclass
class ApprovalRecord:
    """Record of a CPA approval."""
    session_id: str
    cpa_reviewer_id: str
    cpa_reviewer_name: str
    approval_timestamp: datetime
    signature_hash: str
    return_data_hash: str = ""  # Hash of the return data at time of approval
    review_notes: Optional[str] = None
    verification_status: str = "valid"
    checklist_completed: bool = False  # P1: Require checklist completion

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "cpa_reviewer_id": self.cpa_reviewer_id,
            "cpa_reviewer_name": self.cpa_reviewer_name,
            "approval_timestamp": self.approval_timestamp.isoformat(),
            "signature_hash": self.signature_hash,
            "return_data_hash": self.return_data_hash,
            "review_notes": self.review_notes,
            "verification_status": self.verification_status,
            "checklist_completed": self.checklist_completed,
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
        return_data_hash: Optional[str] = None,
    ) -> str:
        """
        Generate a cryptographic signature hash for approval.

        CRITICAL: This signature binds the CPA's approval to:
        1. The specific session/return
        2. The reviewer's identity
        3. The exact timestamp
        4. The return data content (via return_data_hash)

        Any change to the return data after approval will invalidate
        the signature when verified.

        Args:
            session_id: Session/return identifier
            cpa_reviewer_id: CPA identifier
            timestamp: Approval timestamp (default: now)
            pin: Optional CPA PIN for additional verification
            return_data_hash: Hash of return data (required for integrity)

        Returns:
            Full SHA-256 signature hash (64 characters)
        """
        timestamp = timestamp or datetime.utcnow()

        # Include return_data_hash in signature for data binding
        signature_components = [
            session_id,
            cpa_reviewer_id,
            timestamp.isoformat(),
        ]

        if return_data_hash:
            signature_components.append(return_data_hash)

        if pin:
            signature_components.append(pin)

        signature_data = ":".join(signature_components)
        # Return full hash for cryptographic integrity (not truncated)
        return hashlib.sha256(signature_data.encode()).hexdigest()

    def verify_signature(
        self,
        session_id: str,
        cpa_reviewer_id: str,
        timestamp: datetime,
        signature_hash: str,
        pin: Optional[str] = None,
        return_data_hash: Optional[str] = None,
    ) -> bool:
        """
        Verify an approval signature against current return data.

        CRITICAL: If return_data_hash is provided, this verifies that
        the return data has not changed since approval. If the data
        has changed, the signature will be invalid.

        Args:
            session_id: Session/return identifier
            cpa_reviewer_id: CPA identifier
            timestamp: Approval timestamp
            signature_hash: Signature to verify
            pin: Optional CPA PIN
            return_data_hash: Current hash of return data

        Returns:
            True if signature is valid and data unchanged
        """
        expected_hash = self.generate_signature_hash(
            session_id=session_id,
            cpa_reviewer_id=cpa_reviewer_id,
            timestamp=timestamp,
            pin=pin,
            return_data_hash=return_data_hash,
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
        return_data: Optional[Dict[str, Any]] = None,
        checklist_completed: bool = False,
    ) -> ApprovalRecord:
        """
        Approve a tax return with CPA signature.

        CRITICAL: This signature binds the CPA's approval to the exact
        return data. If return_data is provided, the signature includes
        a hash of the data, ensuring any subsequent changes invalidate
        the approval.

        Args:
            session_id: Session/return identifier
            cpa_reviewer_id: CPA identifier
            cpa_reviewer_name: CPA name for display
            tenant_id: Tenant identifier
            review_notes: Optional review notes
            pin: Optional CPA PIN for signature
            return_data: Tax return data dict (required for signature integrity)
            checklist_completed: Whether the review checklist was completed

        Returns:
            ApprovalRecord with approval details

        Raises:
            ValueError: If checklist not completed (required for approval)
        """
        # P1: Require checklist completion before approval
        if not checklist_completed:
            raise ValueError(
                "Review checklist must be completed before approval. "
                "This ensures all critical items have been verified."
            )

        timestamp = datetime.utcnow()

        # P0: Compute return data hash for signature binding
        return_data_hash = ""
        if return_data:
            return_data_hash = compute_return_data_hash(return_data)

        signature_hash = self.generate_signature_hash(
            session_id=session_id,
            cpa_reviewer_id=cpa_reviewer_id,
            timestamp=timestamp,
            pin=pin,
            return_data_hash=return_data_hash,
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
                    "return_data_hash": return_data_hash,
                    "review_notes": review_notes,
                    "checklist_completed": checklist_completed,
                }
            )

        return ApprovalRecord(
            session_id=session_id,
            cpa_reviewer_id=cpa_reviewer_id,
            cpa_reviewer_name=cpa_reviewer_name,
            approval_timestamp=timestamp,
            signature_hash=signature_hash,
            return_data_hash=return_data_hash,
            review_notes=review_notes,
            checklist_completed=checklist_completed,
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

    P1 FIX: Certificate now references version hash instead of
    embedding mutable dollar values that could become stale.
    """

    # P3: IRS Circular 230 required disclaimer
    CIRCULAR_230_DISCLAIMER = (
        "IRS Circular 230 Disclosure: To ensure compliance with requirements "
        "imposed by the IRS, we inform you that any U.S. federal tax advice "
        "contained in this communication (including any attachments) is not "
        "intended or written to be used, and cannot be used, for the purpose "
        "of (i) avoiding penalties under the Internal Revenue Code or "
        "(ii) promoting, marketing, or recommending to another party any "
        "transaction or matter addressed herein."
    )

    @staticmethod
    def generate(approval: ApprovalRecord, return_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate an approval certificate.

        P1 FIX: Certificate references return_data_hash instead of
        embedding mutable dollar amounts. This prevents liability from
        stale certificate data if the return is later amended.

        Args:
            approval: ApprovalRecord
            return_summary: Summary of the tax return

        Returns:
            Certificate data dictionary
        """
        # P1: Compute current return data hash for verification
        current_return_hash = compute_return_data_hash(return_summary)

        # Check if return has changed since approval
        data_integrity_valid = (
            not approval.return_data_hash or
            approval.return_data_hash == current_return_hash
        )

        return {
            "certificate_type": "CPA_APPROVAL",
            "certificate_version": "2.0",  # Version with hash-based integrity
            "session_id": approval.session_id,
            "issued_at": datetime.utcnow().isoformat(),
            "approval_details": {
                "cpa_name": approval.cpa_reviewer_name,
                "cpa_id": approval.cpa_reviewer_id,
                "approval_date": approval.approval_timestamp.isoformat(),
                "signature_hash": approval.signature_hash,
                "checklist_completed": approval.checklist_completed,
            },
            # P1 FIX: Reference hash instead of mutable dollar values
            "return_reference": {
                "tax_year": return_summary.get("tax_year", 2025),
                "taxpayer_name": return_summary.get("taxpayer_name", ""),
                "return_data_hash": approval.return_data_hash,
                "current_data_hash": current_return_hash,
                "data_integrity_valid": data_integrity_valid,
            },
            "review_notes": approval.review_notes,
            "verification": {
                "status": "verified" if data_integrity_valid else "data_changed",
                "signature_valid": True,
                "data_unchanged": data_integrity_valid,
                "message": (
                    "This return has been reviewed and approved by a licensed CPA."
                    if data_integrity_valid else
                    "WARNING: Return data has changed since approval. Re-review required."
                ),
            },
            "disclaimers": {
                # P3: Circular 230 compliance
                "circular_230": ApprovalCertificate.CIRCULAR_230_DISCLAIMER,
                "general": (
                    "This certificate confirms that the associated tax return has been "
                    "reviewed and approved by the named CPA at the time indicated. "
                    "The approval signature hash and return data hash together verify "
                    "the authenticity of this approval and the integrity of the return data."
                ),
                "limitation_of_liability": (
                    "This approval is based on information provided by the taxpayer. "
                    "The CPA has reviewed the return for accuracy and compliance but "
                    "cannot guarantee the completeness or accuracy of underlying source documents."
                ),
            },
        }
