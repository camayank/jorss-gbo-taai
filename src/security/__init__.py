"""
Security module for the tax platform.

Provides secure serialization, encryption, authentication, data protection,
AI-powered compliance review, and fraud detection.
"""

from .secure_serializer import SecureSerializer, get_serializer
from .encryption import DataEncryptor, get_encryptor
from .authentication import (
    AuthenticationManager,
    get_auth_manager,
    require_auth,
    JWTClaims,
)
from .data_sanitizer import DataSanitizer, sanitize_for_logging, sanitize_for_api

# AI-Powered Security Services (Phase 7)
from .ai_compliance_reviewer import (
    ClaudeComplianceReviewer,
    get_compliance_reviewer,
    ComplianceReviewResult,
    ComplianceIssue,
    DueDiligenceRequirement,
    ComplianceRiskLevel,
    ComplianceCategory,
)
from .fraud_detector import (
    OpenAIFraudDetector,
    get_fraud_detector,
    FraudDetectionResult,
    FraudIndicator,
    PatternMatch,
    FraudRiskLevel,
    FraudIndicatorType,
)

__all__ = [
    # Core Security
    "SecureSerializer",
    "get_serializer",
    "DataEncryptor",
    "get_encryptor",
    "AuthenticationManager",
    "get_auth_manager",
    "require_auth",
    "JWTClaims",
    "DataSanitizer",
    "sanitize_for_logging",
    "sanitize_for_api",
    # AI Compliance Review (Phase 7)
    "ClaudeComplianceReviewer",
    "get_compliance_reviewer",
    "ComplianceReviewResult",
    "ComplianceIssue",
    "DueDiligenceRequirement",
    "ComplianceRiskLevel",
    "ComplianceCategory",
    # AI Fraud Detection (Phase 7)
    "OpenAIFraudDetector",
    "get_fraud_detector",
    "FraudDetectionResult",
    "FraudIndicator",
    "PatternMatch",
    "FraudRiskLevel",
    "FraudIndicatorType",
]
