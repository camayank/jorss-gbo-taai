"""
AI Services Package.

Provides unified AI capabilities across multiple providers:
- UnifiedAIService: Core abstraction for all AI providers (OpenAI, Anthropic, Google, Perplexity)
- IntelligentChatRouter: Smart routing based on query complexity
- TaxResearchService: Real-time tax research via Perplexity
- TaxReasoningService: Complex tax reasoning via Claude
- AIMetricsService: Usage monitoring and cost tracking
- AIDocumentProcessor: Multimodal document processing via Gemini
- AnomalyDetector: Tax return anomaly detection
- ComplianceReviewer: Compliance checking via Claude

Usage:
    from services.ai import get_ai_service, get_chat_router

    # Direct AI access
    ai = get_ai_service()
    response = await ai.complete("Explain tax deductions")

    # Intelligent routing
    router = get_chat_router()
    response = await router.route_query("Should I convert to Roth IRA?")

    # Document processing
    processor = get_document_processor()
    result = await processor.process_document(image_bytes, "W-2")

    # Anomaly detection
    detector = get_anomaly_detector()
    report = await detector.analyze_return(tax_return_data)
"""

# Core AI service
from services.ai.unified_ai_service import (
    UnifiedAIService,
    AIMessage,
    AIResponse,
    AIUsageStats,
    get_ai_service,
    CircuitBreaker,
    CircuitState,
)

# Intelligent chat routing
from services.ai.chat_router import (
    IntelligentChatRouter,
    QueryAnalyzer,
    QueryType,
    QueryAnalysis,
    get_chat_router,
)

# Tax-specific research
from services.ai.tax_research_service import (
    TaxResearchService,
    ResearchCategory,
    ResearchResult,
    get_tax_research_service,
)

# Complex tax reasoning
from services.ai.tax_reasoning_service import (
    TaxReasoningService,
    ReasoningType,
    ReasoningResult,
    get_tax_reasoning_service,
)

# Metrics and monitoring
from services.ai.metrics_service import (
    AIMetricsService,
    UsageRecord,
    UsageSummary,
    BudgetStatus,
    PerformanceMetrics,
    MetricPeriod,
    get_ai_metrics_service,
)

# Document processing (Phase 3)
from services.ai.document_processor import (
    AIDocumentProcessor,
    DocumentType,
    ExtractedField,
    DocumentAnalysis,
    get_document_processor,
)

# Anomaly detection (Phase 3)
from services.ai.anomaly_detector import (
    AnomalyDetector,
    Anomaly,
    AnomalyReport,
    AnomalySeverity,
    AnomalyCategory,
    AuditRiskAssessment,
    get_anomaly_detector,
)

# Compliance review (Phase 3)
from services.ai.compliance_reviewer import (
    ComplianceReviewer,
    ComplianceArea,
    ComplianceStatus,
    ComplianceIssue,
    ComplianceReport,
    DueDiligenceChecklist,
    get_compliance_reviewer,
)

__all__ = [
    # Core service
    "UnifiedAIService",
    "AIMessage",
    "AIResponse",
    "AIUsageStats",
    "get_ai_service",
    "CircuitBreaker",
    "CircuitState",
    # Chat router
    "IntelligentChatRouter",
    "QueryAnalyzer",
    "QueryType",
    "QueryAnalysis",
    "get_chat_router",
    # Tax research
    "TaxResearchService",
    "ResearchCategory",
    "ResearchResult",
    "get_tax_research_service",
    # Tax reasoning
    "TaxReasoningService",
    "ReasoningType",
    "ReasoningResult",
    "get_tax_reasoning_service",
    # Metrics
    "AIMetricsService",
    "UsageRecord",
    "UsageSummary",
    "BudgetStatus",
    "PerformanceMetrics",
    "MetricPeriod",
    "get_ai_metrics_service",
    # Document processing
    "AIDocumentProcessor",
    "DocumentType",
    "ExtractedField",
    "DocumentAnalysis",
    "get_document_processor",
    # Anomaly detection
    "AnomalyDetector",
    "Anomaly",
    "AnomalyReport",
    "AnomalySeverity",
    "AnomalyCategory",
    "AuditRiskAssessment",
    "get_anomaly_detector",
    # Compliance review
    "ComplianceReviewer",
    "ComplianceArea",
    "ComplianceStatus",
    "ComplianceIssue",
    "ComplianceReport",
    "DueDiligenceChecklist",
    "get_compliance_reviewer",
]
