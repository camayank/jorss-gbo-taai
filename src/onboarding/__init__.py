"""Smart User Onboarding Module.

This module provides a guided, intelligent onboarding experience for
tax return preparation, including:
- Guided questionnaire flow
- Smart question routing based on previous answers
- Document parsing and data extraction
- Profile-based interview paths
- Real-time benefit estimation during onboarding
"""

from onboarding.questionnaire_engine import QuestionnaireEngine, Question, QuestionGroup
from onboarding.interview_flow import (
    InterviewFlow,
    InterviewState,
    InterviewSection,
    InterviewProgress,
    NextAction,
)
from onboarding.taxpayer_profile import TaxpayerProfile, ProfileBuilder
from onboarding.document_collector import DocumentCollector, SupportedDocument
from onboarding.benefit_estimator import OnboardingBenefitEstimator

__all__ = [
    "QuestionnaireEngine",
    "Question",
    "QuestionGroup",
    "InterviewFlow",
    "InterviewState",
    "InterviewSection",
    "InterviewProgress",
    "NextAction",
    "TaxpayerProfile",
    "ProfileBuilder",
    "DocumentCollector",
    "SupportedDocument",
    "OnboardingBenefitEstimator",
    "get_interview_flow",
]


# Singleton instance for interview flow
_interview_flow_instance = None


def get_interview_flow() -> InterviewFlow:
    """
    Get the interview flow singleton instance.

    Returns:
        InterviewFlow: The global interview flow instance.
    """
    global _interview_flow_instance
    if _interview_flow_instance is None:
        _interview_flow_instance = InterviewFlow()
    return _interview_flow_instance
