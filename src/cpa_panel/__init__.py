"""
CPA Decision Intelligence & Advisory Panel

A comprehensive module for CPA workflow management, tax analysis,
and client advisory features. Designed for the $20K/yr CPA white-label
subscription tier.

PLATFORM IDENTITY: CPA Intelligence & Advisory Amplifier
- NOT a Practice Management System (PMS)
- NOT an e-filing platform

Key Features:
- Return approval workflow (DRAFT → IN_REVIEW → CPA_APPROVED)
- Instant delta visualization (before/after impact analysis)
- "What Drives Your Tax Outcome" breakdown
- Scenario comparison with delta display
- CPA notes and review documentation
- Audit trail integration for defensibility
- Engagement letter generation with e-sign hooks
- Client visibility surface (read-only)
- State-based email notifications (3 triggers)
- Staff assignment (lightweight)
- Practice Intelligence (3 metrics only - BOUNDARY LOCKED)

CPA Compliance:
- All actions are audit-trailed
- Feature gating by approval status
- Calculation engine version tracking
- Hash-verified audit entries

SCOPE BOUNDARIES (LOCKED):
- Practice Intelligence: Advisory mix, complexity distribution, YoY surface ONLY
- NO time tracking, NO staff productivity, NO revenue per staff
- For PMS features, integrate with Karbon, Canopy, or Jetpack

Usage:
    from cpa_panel import CPAWorkflowManager, TaxAnalyzer, CPAInsightsEngine
    from cpa_panel.api import cpa_router

    # Include router in FastAPI app
    app.include_router(cpa_router, prefix="/api/cpa")
"""

from .workflow.status_manager import (
    ReturnStatus,
    CPAWorkflowManager,
    WorkflowTransitionError,
)
from .workflow.approval import (
    ApprovalManager,
    ApprovalRecord,
)
from .analysis.delta_analyzer import (
    DeltaAnalyzer,
    DeltaResult,
)
from .analysis.tax_drivers import (
    TaxDriversAnalyzer,
    TaxDriver,
)
from .analysis.scenario_comparison import (
    ScenarioComparator,
    Scenario,
    ScenarioResult,
)
from .insights.cpa_insights import (
    CPAInsightsEngine,
    CPAInsight,
)
from .practice_intelligence import (
    PracticeIntelligenceService,
    PortfolioMetrics,
    get_intelligence_service,
)

__all__ = [
    # Workflow
    "ReturnStatus",
    "CPAWorkflowManager",
    "WorkflowTransitionError",
    "ApprovalManager",
    "ApprovalRecord",
    # Analysis
    "DeltaAnalyzer",
    "DeltaResult",
    "TaxDriversAnalyzer",
    "TaxDriver",
    "ScenarioComparator",
    "Scenario",
    "ScenarioResult",
    # Insights
    "CPAInsightsEngine",
    "CPAInsight",
    # Practice Intelligence (BOUNDARY LOCKED - 3 metrics only)
    "PracticeIntelligenceService",
    "PortfolioMetrics",
    "get_intelligence_service",
]

__version__ = "1.0.0"
__author__ = "TaxFlow CPA Platform"
