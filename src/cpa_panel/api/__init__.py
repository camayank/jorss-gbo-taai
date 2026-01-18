"""
CPA Panel API

Exports the main CPA router and all domain-specific routers.
"""

from .router import cpa_router
from .workflow_routes import workflow_router
from .analysis_routes import analysis_router
from .notes_routes import notes_router
from .insights_routes import insights_router
from .lead_routes import lead_router
from .exposure_routes import exposure_router

__all__ = [
    "cpa_router",
    "workflow_router",
    "analysis_router",
    "notes_routes",
    "insights_router",
    "lead_router",
    "exposure_router",
]
