"""
Smart Tax Module

Intelligent tax preparation orchestration layer that provides:
- Document-first workflow with instant feedback
- Progressive data collection with adaptive questions
- Real-time estimates with confidence bands
- Complexity-based routing (SIMPLE/MODERATE/COMPLEX/PROFESSIONAL)
"""

from .orchestrator import (
    SmartTaxOrchestrator,
    SmartTaxSession,
    SessionState,
    ComplexityLevel,
)
from .complexity_router import (
    ComplexityRouter,
    ComplexityAssessment,
    RoutingDecision,
)
from .document_processor import (
    SmartDocumentProcessor,
    ProcessedDocument,
    DocumentSummary,
)
from .question_generator import (
    AdaptiveQuestionGenerator,
    AdaptiveQuestion,
    QuestionPriority,
    QuestionCategory,
)
from .deduction_detector import (
    SmartDeductionDetector,
    DetectedDeduction,
    DetectedCredit,
    DeductionType,
    CreditType,
    DeductionAnalysis,
)
from .planning_insights import (
    TaxPlanningEngine,
    TaxPlanningInsight,
    PlanningReport,
    QuarterlyEstimate,
    InsightCategory,
    InsightUrgency,
    InsightImpact,
)

__all__ = [
    # Orchestrator
    "SmartTaxOrchestrator",
    "SmartTaxSession",
    "SessionState",
    "ComplexityLevel",
    # Complexity routing
    "ComplexityRouter",
    "ComplexityAssessment",
    "RoutingDecision",
    # Document processing
    "SmartDocumentProcessor",
    "ProcessedDocument",
    "DocumentSummary",
    # Question generation
    "AdaptiveQuestionGenerator",
    "AdaptiveQuestion",
    "QuestionPriority",
    "QuestionCategory",
    # Deduction detection
    "SmartDeductionDetector",
    "DetectedDeduction",
    "DetectedCredit",
    "DeductionType",
    "CreditType",
    "DeductionAnalysis",
    # Planning insights
    "TaxPlanningEngine",
    "TaxPlanningInsight",
    "PlanningReport",
    "QuarterlyEstimate",
    "InsightCategory",
    "InsightUrgency",
    "InsightImpact",
]
