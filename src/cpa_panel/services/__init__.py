"""
CPA Panel Services

Core business logic services for the CPA panel.
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
]
