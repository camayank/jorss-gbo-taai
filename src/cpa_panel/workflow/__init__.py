"""
CPA Workflow Management Module

Handles the return approval workflow:
- Status transitions (DRAFT → IN_REVIEW → CPA_APPROVED)
- CPA assignment and review management
- Audit trail integration
"""

from .status_manager import (
    ReturnStatus,
    CPAWorkflowManager,
    WorkflowTransitionError,
    StatusRecord,
    FeatureAccess,
)
from .approval import (
    ApprovalManager,
    ApprovalRecord,
)
from .notes import (
    NotesManager,
    CPANote,
)

__all__ = [
    "ReturnStatus",
    "CPAWorkflowManager",
    "WorkflowTransitionError",
    "StatusRecord",
    "FeatureAccess",
    "ApprovalManager",
    "ApprovalRecord",
    "NotesManager",
    "CPANote",
]
