"""
CPA Panel API Router

Aggregates all domain-specific routers into a single CPA panel API.

Domain Routers:
- workflow_routes: Status, approval, queue management
- analysis_routes: Delta analysis, tax drivers, scenarios
- notes_routes: CPA review notes
- insights_routes: CPA insights and checklists
- lead_routes: Lead state management and signals
- exposure_routes: Prospect-safe discovery exposure

All endpoints are prefixed with /api/cpa when included in the main app.
"""

from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

# Create main CPA router
cpa_router = APIRouter(prefix="/cpa", tags=["CPA Panel"])

# Import domain-specific routers
from .workflow_routes import workflow_router
from .analysis_routes import analysis_router
from .notes_routes import notes_router
from .insights_routes import insights_router
from .lead_routes import lead_router
from .exposure_routes import exposure_router

# Include all domain routers
cpa_router.include_router(workflow_router)
cpa_router.include_router(analysis_router)
cpa_router.include_router(notes_router)
cpa_router.include_router(insights_router)
cpa_router.include_router(lead_router)
cpa_router.include_router(exposure_router)


# =============================================================================
# HEALTH CHECK
# =============================================================================

@cpa_router.get("/health")
async def cpa_health_check():
    """CPA Panel health check endpoint."""
    return {
        "status": "healthy",
        "module": "cpa_panel",
        "routes": {
            "workflow": "active",
            "analysis": "active",
            "notes": "active",
            "insights": "active",
            "leads": "active",
            "exposure": "active",
        },
    }


# =============================================================================
# API DOCUMENTATION
# =============================================================================

@cpa_router.get("/docs/routes")
async def get_route_documentation():
    """Get documentation of all CPA panel routes."""
    return {
        "prefix": "/api/cpa",
        "domains": {
            "workflow": {
                "description": "Return status management, approval workflow, review queue",
                "endpoints": [
                    "GET /returns/{session_id}/status",
                    "POST /returns/{session_id}/submit-for-review",
                    "POST /returns/{session_id}/approve",
                    "POST /returns/{session_id}/revert",
                    "GET /returns/{session_id}/approval-certificate",
                    "GET /returns/{session_id}/summary",
                    "GET /queue/counts",
                    "GET /queue/{status}",
                ],
            },
            "analysis": {
                "description": "Delta analysis, tax drivers, scenario comparison",
                "endpoints": [
                    "POST /returns/{session_id}/delta",
                    "GET /returns/{session_id}/tax-drivers",
                    "POST /returns/{session_id}/compare-scenarios",
                    "GET /returns/{session_id}/suggested-scenarios",
                ],
            },
            "notes": {
                "description": "CPA review notes management",
                "endpoints": [
                    "POST /returns/{session_id}/notes",
                    "GET /returns/{session_id}/notes",
                    "DELETE /returns/{session_id}/notes/{note_id}",
                ],
            },
            "insights": {
                "description": "CPA-specific insights and review checklists",
                "endpoints": [
                    "GET /returns/{session_id}/insights",
                    "GET /returns/{session_id}/review-checklist",
                ],
            },
            "leads": {
                "description": "Lead state management and signal processing",
                "endpoints": [
                    "GET /leads/{lead_id}",
                    "POST /leads",
                    "POST /leads/{lead_id}/signals",
                    "POST /leads/{lead_id}/signals/batch",
                    "GET /leads/queue/summary",
                    "GET /leads/queue/visible",
                    "GET /leads/queue/monetizable",
                    "GET /leads/queue/priority",
                    "GET /leads/queue/state/{state}",
                    "GET /signals/catalog",
                    "GET /states/info",
                ],
            },
            "exposure": {
                "description": "Prospect-safe discovery exposure (Red Line compliant)",
                "endpoints": [
                    "GET /prospect/{session_id}/discovery",
                    "GET /prospect/{session_id}/outcome",
                    "GET /prospect/{session_id}/complexity",
                    "GET /prospect/{session_id}/drivers",
                    "GET /exposure/contracts",
                ],
            },
        },
    }
