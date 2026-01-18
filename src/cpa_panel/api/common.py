"""
Common utilities for CPA Panel API routes.

Shared helpers, dependency injection, and error formatting.
"""

from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ERROR FORMATTING
# =============================================================================

def format_error_response(message: str, code: str = "CPA_ERROR") -> Dict[str, Any]:
    """Format a standard error response."""
    return {
        "success": False,
        "error": True,
        "code": code,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format a standard success response."""
    return {
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
        **data,
    }


# =============================================================================
# DEPENDENCY INJECTION HELPERS
# =============================================================================

def get_tax_return_adapter():
    """Get the tax return adapter instance."""
    from cpa_panel.adapters import TaxReturnAdapter
    return TaxReturnAdapter()


def get_session_adapter():
    """Get the session adapter instance."""
    from cpa_panel.adapters import SessionAdapter
    return SessionAdapter()


def get_workflow_manager():
    """Get the workflow manager instance."""
    from cpa_panel.workflow import CPAWorkflowManager
    return CPAWorkflowManager()


def get_approval_manager():
    """Get the approval manager instance."""
    from cpa_panel.workflow import ApprovalManager
    return ApprovalManager()


def get_notes_manager():
    """Get the notes manager instance."""
    from cpa_panel.workflow import NotesManager
    return NotesManager()


_lead_state_engine = None


def get_lead_state_engine():
    """
    Get the lead state engine instance with persistence.

    Returns a singleton engine with database-backed persistence.
    """
    global _lead_state_engine
    if _lead_state_engine is None:
        from cpa_panel.lead_state import LeadStateEngine
        from database.lead_state_persistence import get_lead_state_persistence

        persistence = get_lead_state_persistence()
        _lead_state_engine = LeadStateEngine(persistence=persistence)

    return _lead_state_engine


# =============================================================================
# TENANT EXTRACTION
# =============================================================================

def get_tenant_id(request) -> str:
    """
    Extract tenant ID from request.

    Checks headers, query params, or defaults to 'default'.
    """
    # Check header first
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        return tenant_id

    # Check query params
    tenant_id = request.query_params.get("tenant_id")
    if tenant_id:
        return tenant_id

    return "default"
