"""
AI Services Package.

Provides unified AI capabilities across multiple providers:
- UnifiedAIService: Core abstraction for all AI providers
- IntelligentChatRouter: Smart routing based on query complexity
- TaxResearchService: Real-time tax research via Perplexity
- TaxReasoningService: Complex tax reasoning via Claude
- AIMetricsService: Usage monitoring and cost tracking

Usage:
    from services.ai import get_ai_service, get_chat_router

    # Direct AI access
    ai = get_ai_service()
    response = await ai.complete("Explain tax deductions")

    # Intelligent routing
    router = get_chat_router()
    response = await router.route_query("Should I convert to Roth IRA?")
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
]
