"""
CPA Panel Services

Core business logic services for the CPA panel.
Includes AI-powered lead intelligence and client research (Phase 8).
"""

from .form_1040_parser import Form1040Parser, Parsed1040Data, FilingStatus
from .ai_question_generator import (
    AIQuestionGenerator,
    QuestionSet,
    SmartQuestion,
    QuestionCategory,
    QuestionPriority,
)
from .smart_onboarding_service import (
    SmartOnboardingService,
    OnboardingSession,
    OnboardingStatus,
    OptimizationOpportunity,
    InstantAnalysis,
    get_smart_onboarding_service,
)
from .lead_generation_service import (
    LeadGenerationService,
    ProspectLead,
    LeadTeaser,
    LeadSource,
    LeadStatus,
    LeadPriority,
    get_lead_generation_service,
)
# AI-Powered Services (Phase 8)
from .ai_lead_intelligence import (
    ClaudeLeadIntelligence,
    get_lead_intelligence,
    LeadIntelligenceResult,
    LeadData,
    LeadScoring,
    RevenueProjection,
    CrossSellOpportunity,
    OutreachStrategy,
    LeadQualityTier,
    ServiceTier,
    EngagementUrgency,
)
from .client_researcher import (
    PerplexityClientResearcher,
    get_client_researcher,
    ClientResearchResult,
    CompanyProfile,
    IndustryInsight,
    NewsItem,
    CompetitorInfo,
    FinancialIndicators,
    TaxConsiderations,
    ResearchDepth,
    IndustryTrendSignal,
    FinancialHealthIndicator,
)

__all__ = [
    # 1040 Parser
    "Form1040Parser",
    "Parsed1040Data",
    "FilingStatus",
    # Question Generator
    "AIQuestionGenerator",
    "QuestionSet",
    "SmartQuestion",
    "QuestionCategory",
    "QuestionPriority",
    # Smart Onboarding
    "SmartOnboardingService",
    "OnboardingSession",
    "OnboardingStatus",
    "OptimizationOpportunity",
    "InstantAnalysis",
    "get_smart_onboarding_service",
    # Lead Generation
    "LeadGenerationService",
    "ProspectLead",
    "LeadTeaser",
    "LeadSource",
    "LeadStatus",
    "LeadPriority",
    "get_lead_generation_service",
    # AI Lead Intelligence (Phase 8)
    "ClaudeLeadIntelligence",
    "get_lead_intelligence",
    "LeadIntelligenceResult",
    "LeadData",
    "LeadScoring",
    "RevenueProjection",
    "CrossSellOpportunity",
    "OutreachStrategy",
    "LeadQualityTier",
    "ServiceTier",
    "EngagementUrgency",
    # AI Client Research (Phase 8)
    "PerplexityClientResearcher",
    "get_client_researcher",
    "ClientResearchResult",
    "CompanyProfile",
    "IndustryInsight",
    "NewsItem",
    "CompetitorInfo",
    "FinancialIndicators",
    "TaxConsiderations",
    "ResearchDepth",
    "IndustryTrendSignal",
    "FinancialHealthIndicator",
]
