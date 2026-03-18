"""
Intelligent Advisor API - World-Class Tax Chatbot Backend

This API integrates ALL backend capabilities to create a truly intelligent
tax advisory chatbot experience:

- Real AI-powered responses
- 30+ tax optimization strategies
- Real-time tax calculations
- Document OCR and extraction
- Multi-year projections
- Entity structure analysis
- Professional report generation

NO ONE IN USA HAS DONE THIS.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends, Request as FastAPIRequest
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
import asyncio
import logging
import os
import re
import time

_raw_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PII Redaction — prevent SSNs, EINs, emails leaking into logs
# ---------------------------------------------------------------------------
PII_PATTERNS = [
    (r'\b\d{3}-\d{2}-\d{4}\b', '***-**-****'),      # SSN
    (r'\b\d{9}\b', '*********'),                       # SSN without dashes
    (r'\b\d{2}-\d{7}\b', '**-*******'),                # EIN
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),
    (r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', '[CARD]'),
]


def _redact_pii(text: str) -> str:
    """Strip PII patterns from text before logging."""
    if not text:
        return text
    result = str(text)
    for pattern, replacement in PII_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


class _SecureLogger:
    """Logger wrapper that auto-redacts PII from all messages."""
    def __init__(self, inner):
        self._inner = inner

    def info(self, msg, *a, **kw):
        self._inner.info(_redact_pii(str(msg)), *a, **kw)

    def warning(self, msg, *a, **kw):
        self._inner.warning(_redact_pii(str(msg)), *a, **kw)

    def error(self, msg, *a, **kw):
        self._inner.error(_redact_pii(str(msg)), *a, **kw)

    def debug(self, msg, *a, **kw):
        self._inner.debug(_redact_pii(str(msg)), *a, **kw)

    def exception(self, msg, *a, **kw):
        self._inner.exception(_redact_pii(str(msg)), *a, **kw)


logger = _SecureLogger(_raw_logger)


# ---------------------------------------------------------------------------
# UUID Validation — prevent session fixation with arbitrary strings
# ---------------------------------------------------------------------------
def _validate_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# IP-based Rate Limiting — prevents session-rotation bypass
# ---------------------------------------------------------------------------
_ip_rate_limits: dict = {}  # ip -> list of timestamps
_IP_RATE_LIMIT = 100  # max requests per window per IP
_IP_RATE_WINDOW = 60  # seconds


def _get_client_ip(request) -> str:
    """Extract client IP from proxy headers."""
    if hasattr(request, 'headers'):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
    if hasattr(request, 'client') and request.client:
        return request.client.host
    return "unknown"

from security.session_token import verify_session_token, generate_session_token, SESSION_TOKEN_KEY

# Journey event bus integration
try:
    from events.event_bus import get_event_bus
    from events.journey_events import AdvisorMessageSent, AdvisorProfileComplete
    _JOURNEY_EVENTS_AVAILABLE = True
except ImportError:
    _JOURNEY_EVENTS_AVAILABLE = False

# RBAC admin dependency for privileged endpoints
try:
    from rbac.dependencies import require_platform_admin
    from rbac.context import AuthContext
except ImportError:
    require_platform_admin = verify_session_token
    AuthContext = None

# ---------------------------------------------------------------------------
# AI Feature Flags — each integration is independently toggleable
# ---------------------------------------------------------------------------
AI_CHAT_ENABLED = os.environ.get("AI_CHAT_ENABLED", "true").lower() == "true"
AI_REPORT_NARRATIVES_ENABLED = os.environ.get("AI_REPORT_NARRATIVES_ENABLED", "true").lower() == "true"
AI_SAFETY_CHECKS_ENABLED = os.environ.get("AI_SAFETY_CHECKS_ENABLED", "true").lower() == "true"
AI_OPPORTUNITIES_ENABLED = os.environ.get("AI_OPPORTUNITIES_ENABLED", "true").lower() == "true"
AI_RECOMMENDATIONS_ENABLED = os.environ.get("AI_RECOMMENDATIONS_ENABLED", "true").lower() == "true"
AI_ENTITY_EXTRACTION_ENABLED = os.environ.get("AI_ENTITY_EXTRACTION_ENABLED", "true").lower() == "true"
AI_ADAPTIVE_QUESTIONS_ENABLED = os.environ.get("AI_ADAPTIVE_QUESTIONS_ENABLED", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Re-export from decomposed sub-modules (backward compatibility)
# ---------------------------------------------------------------------------
from web.advisor.models import (  # noqa: F401
    FilingStatus, ChatMessage, TaxProfileInput, ChatRequest,
    StrategyRecommendation, TaxCalculationResult, ChatResponse,
    FullAnalysisRequest, FullAnalysisResponse,
)
from web.advisor.parsers import (  # noqa: F401
    parse_user_message, enhanced_parse_user_message,
    EnhancedParser, ConversationContext, detect_user_intent,
)

# --- Input Guard (prompt injection + PII sanitization) ---
try:
    from security.input_guard import InputGuard
    _input_guard = InputGuard()
    _INPUT_GUARD_AVAILABLE = True
except ImportError:
    _input_guard = None
    _INPUT_GUARD_AVAILABLE = False
    logger.warning("InputGuard not available - prompt injection protection disabled")

# --- AI/ML Integration (graceful fallback if dependencies missing) ---
try:
    from services.ai.unified_ai_service import get_ai_service
except ImportError:
    get_ai_service = None
    logger.warning("unified_ai_service not available - AI features disabled")

try:
    from services.ai.metrics_service import get_ai_metrics_service
except ImportError:
    get_ai_metrics_service = None
    logger.warning("metrics_service not available")

try:
    from services.tax_opportunity_detector import TaxOpportunityDetector, TaxpayerProfile
except ImportError:
    TaxOpportunityDetector = None
    TaxpayerProfile = None
    logger.warning("tax_opportunity_detector not available")

try:
    from web.recommendation.orchestrator import get_recommendations
except ImportError:
    get_recommendations = None
    logger.warning("recommendation orchestrator not available")

try:
    from agent.intelligent_tax_agent import IntelligentTaxAgent
except ImportError:
    IntelligentTaxAgent = None
    logger.warning("IntelligentTaxAgent not available")

try:
    from ml.document_classifier import DocumentClassifier
except ImportError:
    DocumentClassifier = None
    logger.warning("DocumentClassifier not available")

try:
    from recommendation.ai_enhancer import get_ai_enhancer
except ImportError:
    get_ai_enhancer = None
    logger.warning("AI enhancer not available")

# Liability disclaimer constant
STANDARD_DISCLAIMER = (
    "This is AI-generated information for educational purposes only, "
    "not professional tax advice. Consult a licensed CPA or EA for "
    "your specific situation."
)


def _session_profile_to_taxpayer_profile(profile: dict) -> TaxpayerProfile:
    """Convert session profile dict to TaxpayerProfile for opportunity detection."""
    from decimal import Decimal

    def dec(key, default=0):
        val = profile.get(key, default)
        try:
            return Decimal(str(val)) if val else Decimal(str(default))
        except Exception:
            return Decimal(str(default))

    return TaxpayerProfile(
        filing_status=profile.get("filing_status", "single"),
        age=int(profile.get("age", 30) or 30),
        w2_wages=dec("w2_income") + dec("total_income"),
        self_employment_income=dec("self_employment_income"),
        business_income=dec("business_income"),
        traditional_401k=dec("retirement_401k") + dec("retirement_contributions"),
        roth_401k=dec("roth_401k"),
        traditional_ira=dec("retirement_ira") + dec("traditional_ira"),
        roth_ira=dec("roth_ira"),
        hsa_contribution=dec("hsa_contributions") + dec("hsa_contribution"),
        mortgage_interest=dec("mortgage_interest"),
        property_taxes=dec("property_taxes"),
        charitable_contributions=dec("charitable_donations") + dec("charitable_giving"),
        state_local_taxes=dec("state_income_tax") + dec("state_local_taxes"),
        medical_expenses=dec("medical_expenses"),
        student_loan_interest=dec("student_loan_interest"),
        num_dependents=int(profile.get("dependents", 0) or 0),
        has_children_under_17=int(profile.get("dependents", 0) or 0) > 0,
        had_baby="dependents" in profile and int(profile.get("dependents", 0) or 0) > 0,
        started_business=profile.get("income_type") in ("self_employed", "business_owner")
        or profile.get("is_self_employed", False),
        has_business=profile.get("is_self_employed", False) or bool(profile.get("business_income")),
        business_net_income=dec("business_income"),
        owns_home=bool(profile.get("mortgage_interest")),
        capital_gains=dec("capital_gains_long") + dec("capital_gains_short"),
        dividend_income=dec("dividend_income") + dec("qualified_dividends"),
        interest_income=dec("interest_income"),
        rental_income=dec("rental_income"),
        education_expenses=dec("education_expenses"),
    )


def _session_profile_to_rec_dict(profile: dict) -> dict:
    """Convert session profile to recommendation orchestrator input format."""
    income = float(profile.get("total_income", 0) or 0)
    return {
        "filing_status": profile.get("filing_status", "single"),
        "agi": income,
        "total_income": income,
        "has_dependents": int(profile.get("dependents", 0) or 0) > 0,
        "is_self_employed": profile.get("income_type") in ("self_employed", "business_owner")
        or profile.get("is_self_employed", False),
        "w2_wages": float(profile.get("w2_income", 0) or 0),
        "self_employment_income": float(profile.get("self_employment_income", 0) or 0),
        "retirement_contributions": float(profile.get("retirement_401k", 0) or 0),
        "mortgage_interest": float(profile.get("mortgage_interest", 0) or 0),
        "charitable_contributions": float(profile.get("charitable_donations", 0) or 0),
        "state": profile.get("state", ""),
        "age": int(profile.get("age", 30) or 30),
        "dependents": int(profile.get("dependents", 0) or 0),
    }


def _income_range_label(income: float) -> str:
    """Return human-readable income range label."""
    if income < 50000:
        return "under $50k"
    if income < 100000:
        return "$50k-$100k"
    if income < 200000:
        return "$100k-$200k"
    if income < 500000:
        return "$200k-$500k"
    return "over $500k"


def _identify_quick_wins(strategies: list, max_wins: int = 2) -> list:
    """Identify strategies with simplest action steps the user can do today."""
    QUICK_KEYWORDS = ["increase", "contribute", "open", "enroll", "switch", "set up", "log into", "contact"]
    scored = []
    for s in strategies:
        s_dict = s.dict() if hasattr(s, 'dict') else s
        steps = s_dict.get("action_steps", [])
        if not steps:
            continue
        simplicity = sum(1 for step in steps if any(kw in step.lower() for kw in QUICK_KEYWORDS))
        complexity = s_dict.get("implementation_complexity", "simple")
        if complexity == "simple" or simplicity > 0:
            scored.append((simplicity + (2 if complexity == "simple" else 0), s_dict))
    scored.sort(key=lambda x: (-x[0], -x[1].get("estimated_savings", 0)))
    return [
        {
            "label": f"\u26a1 Do Today: {s['title'][:35]}",
            "value": f"strategy_detail_{s['id']}",
            "style": "quick_win",
            "estimated_savings": s.get("estimated_savings", 0),
        }
        for _, s in scored[:max_wins]
    ]


def _get_expected_fields_for_type(doc_type: str) -> list:
    """Return expected fields for a document type to guide extraction."""
    field_map = {
        "w2": ["wages", "federal_withheld", "state_withheld", "social_security_wages", "employer_ein"],
        "1099-nec": ["nonemployee_compensation", "payer_tin"],
        "1099-int": ["interest_income", "tax_exempt_interest"],
        "1099-div": ["ordinary_dividends", "qualified_dividends", "capital_gain_distributions"],
        "1099-b": ["proceeds", "cost_basis", "gain_loss"],
        "k1": ["ordinary_income", "rental_income", "interest_income", "dividends", "capital_gains"],
        "1098": ["mortgage_interest", "points_paid", "property_taxes"],
    }
    return field_map.get(doc_type.lower(), [])


def should_require_professional_review(profile: dict) -> bool:
    """
    Determine if a tax profile is complex enough to require professional review.

    Complex scenarios:
    - Income > $200,000
    - Multi-state income
    - Cryptocurrency transactions
    - Foreign income
    - Passive activity losses
    """
    # High income
    total_income = (
        profile.get("wages", 0) +
        profile.get("self_employment_income", 0) +
        profile.get("investment_income", 0) +
        profile.get("rental_income", 0)
    )
    if total_income > 200000:
        return True

    # Multi-state
    states = profile.get("states", [])
    if len(states) > 1:
        return True

    # Crypto
    if profile.get("has_crypto", False):
        return True

    # Foreign income
    if profile.get("foreign_income", 0) > 0:
        return True

    # Passive losses
    if profile.get("passive_losses", 0) < 0:
        return True

    return False


def calculate_response_confidence(
    profile_completeness: float,
    has_complex_scenario: bool = False
) -> tuple:
    """
    Calculate confidence level for a response based on data quality.

    Args:
        profile_completeness: 0.0 to 1.0 indicating how complete the profile is
        has_complex_scenario: True if complex tax situation detected

    Returns:
        tuple of (confidence_level, reason)
    """
    if profile_completeness >= 0.70 and not has_complex_scenario:
        return ("high", None)
    elif profile_completeness >= 0.40:
        if has_complex_scenario:
            return ("medium", "Complex tax situation - verify with professional")
        return ("medium", "Some profile data missing")
    else:
        return ("low", "Limited data available - estimates may vary significantly")


# Circular 230 Compliance - Professional Standards Acknowledgment
class ProfessionalAcknowledgment(BaseModel):
    """Track user acknowledgment of professional standards limitations."""
    session_id: str
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

# In-memory cache for acknowledgments (backed by DB)
_acknowledgments: dict = {}


def check_acknowledgment(session_id: str) -> bool:
    """Check if user has acknowledged professional standards."""
    ack = _acknowledgments.get(session_id)
    return ack is not None and ack.acknowledged


def store_acknowledgment(session_id: str, ip_address: str = None, user_agent: str = None, tenant_id: str = None):
    """Store user acknowledgment of professional standards (persisted to DB)."""
    ack = ProfessionalAcknowledgment(
        session_id=session_id,
        acknowledged=True,
        acknowledged_at=datetime.now(timezone.utc),
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Persist to consent_audit_log table
    try:
        from database.session_manager import get_db_session
        from sqlalchemy import text
        with get_db_session() as db:
            db.execute(text(
                "INSERT INTO consent_audit_log "
                "(session_id, tenant_id, ip_address, user_agent, consent_version, acknowledged_at) "
                "VALUES (:sid, :tid, :ip, :ua, :cv, :ack_at)"
            ), {
                "sid": session_id,
                "tid": tenant_id,
                "ip": ip_address,
                "ua": user_agent,
                "cv": "2026-03-18-v1",
                "ack_at": datetime.now(timezone.utc),
            })
            db.commit()
    except Exception as e:
        _raw_logger.warning(f"Failed to persist consent to DB (in-memory still valid): {e}")

    # Prevent unbounded in-memory growth
    if len(_acknowledgments) > 10000:
        oldest_keys = sorted(_acknowledgments, key=lambda k: str(getattr(_acknowledgments[k], 'acknowledged_at', '')))[:5000]
        for k in oldest_keys:
            del _acknowledgments[k]
    _acknowledgments[session_id] = ack
    return ack


def get_acknowledgment(session_id: str):
    """Get acknowledgment details for a session."""
    return _acknowledgments.get(session_id)


import uuid
import json
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

# Import rate limiter and logo handler
try:
    from utils.rate_limiter import pdf_rate_limiter, global_pdf_limiter, RateLimitExceeded
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    if os.environ.get("APP_ENVIRONMENT") in ("production", "prod"):
        logger.critical("Rate limiter unavailable in production!")
    else:
        logger.warning("Rate limiter not available")

try:
    from utils.logo_handler import LogoHandler, logo_handler
    LOGO_HANDLER_AVAILABLE = True
except ImportError:
    LOGO_HANDLER_AVAILABLE = False
    logger.warning("Logo handler not available")

try:
    from utils.cpa_branding_helper import (
        get_cpa_branding_for_report,
        create_pdf_brand_config,
        get_cpa_branding_for_html_report
    )
    CPA_BRANDING_HELPER_AVAILABLE = True
except ImportError:
    CPA_BRANDING_HELPER_AVAILABLE = False
    logger.warning("CPA branding helper not available")

# CPA AI Review Gate — queue AI responses for CPA approval before delivery
try:
    from cpa_panel.services.ai_review_service import ai_review_service
    AI_REVIEW_AVAILABLE = True
except ImportError:
    AI_REVIEW_AVAILABLE = False
    logger.warning("AI review service not available")


def _maybe_queue_for_review(
    session: dict,
    session_id: str,
    client_question: str,
    ai_response: str,
    complexity: str = "medium",
    estimated_savings: float = None,
) -> Optional[dict]:
    """Queue AI response for CPA review if the session's firm has review mode enabled.

    Returns a queued-notice dict if queued, or None if the response should go directly.
    """
    if not AI_REVIEW_AVAILABLE:
        return None

    firm_id = session.get("firm_id") or session.get("tenant_id")
    review_mode = session.get("review_mode", False)

    if not firm_id or not review_mode:
        return None

    draft = ai_review_service.queue_for_review(
        session_id=session_id,
        firm_id=firm_id,
        client_question=client_question,
        ai_response=ai_response,
        client_name=session.get("profile", {}).get("full_name"),
        client_email=session.get("profile", {}).get("email"),
        complexity=complexity,
        estimated_savings=estimated_savings,
    )
    return {
        "queued": True,
        "draft_id": draft.draft_id,
        "message": (
            "Your question has been received and is being reviewed by your "
            "tax advisor. You'll receive the response shortly."
        ),
    }


# Import session persistence for database-backed storage
try:
    from database.session_persistence import get_session_persistence, SessionPersistence
    SESSION_PERSISTENCE_AVAILABLE = True
except ImportError:
    SESSION_PERSISTENCE_AVAILABLE = False
    logger.warning("Session persistence not available - using in-memory only")

# Import Redis session persistence for shared cross-worker sessions
try:
    from database.redis_session_persistence import get_redis_session_persistence
    REDIS_PERSISTENCE_IMPORTABLE = True
except ImportError:
    REDIS_PERSISTENCE_IMPORTABLE = False
    logger.debug("Redis session persistence module not available")

# Import for PDF generation
try:
    from fastapi.responses import FileResponse
    from advisory.report_generator import AdvisoryReportGenerator, ReportType
    from models.tax_return import TaxReturn, TaxpayerInfo, Income, Deductions, TaxCredits
    from models.taxpayer import FilingStatus as TaxFilingStatus
    PDF_GENERATION_AVAILABLE = True
except ImportError as e:
    PDF_GENERATION_AVAILABLE = False
    logger.warning(f"PDF generation dependencies not available: {e}")

router = APIRouter(prefix="/api/advisor", tags=["Intelligent Advisor"])


# =============================================================================
# PROFILE TO TAX RETURN CONVERSION
# =============================================================================

def convert_profile_to_tax_return(profile: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
    """
    Convert intelligent advisor profile format to advisory API return_data format.

    Args:
        profile: Chatbot profile with flat structure
        session_id: Optional session ID for naming

    Returns:
        Dictionary in return_data format expected by advisory API
    """
    # Map filing status from chatbot format to tax return format
    # Uses enum names from models/taxpayer.py FilingStatus
    filing_status_map = {
        "single": "SINGLE",
        "married_joint": "MARRIED_JOINT",
        "married_separate": "MARRIED_SEPARATE",
        "head_of_household": "HEAD_OF_HOUSEHOLD",
        "qualifying_widow": "QUALIFYING_WIDOW"
    }

    filing_status = profile.get("filing_status", "single")
    tax_filing_status = filing_status_map.get(filing_status, "SINGLE")

    # Calculate income breakdown
    total_income = profile.get("total_income", 0) or 0
    w2_income = profile.get("w2_income", 0) or 0
    business_income = profile.get("business_income", 0) or 0
    investment_income = profile.get("investment_income", 0) or 0
    rental_income = profile.get("rental_income", 0) or 0

    # K-1 income fields (GAP #6)
    k1_ordinary = profile.get("k1_ordinary_income", 0) or 0
    k1_rental = profile.get("k1_rental_income", 0) or 0
    k1_interest = profile.get("k1_interest_income", 0) or 0
    k1_dividend = profile.get("k1_dividend_income", 0) or 0
    k1_royalty = profile.get("k1_royalty_income", 0) or 0
    k1_guaranteed = profile.get("k1_guaranteed_payments", 0) or 0
    k1_total = k1_ordinary + k1_rental + k1_interest + k1_dividend + k1_royalty + k1_guaranteed

    # If only total_income provided, assume it's W-2 (minus known other sources)
    if total_income > 0 and w2_income == 0 and business_income == 0:
        w2_income = total_income - investment_income - rental_income - k1_total

    # Age → is_over_65 (GAP #8)
    age = profile.get("age")
    is_over_65 = False
    if age is not None:
        try:
            is_over_65 = int(age) >= 65
        except (ValueError, TypeError):
            pass

    # Calculate deductions
    mortgage_interest = profile.get("mortgage_interest", 0) or 0
    property_taxes = profile.get("property_taxes", 0) or 0
    state_income_tax = profile.get("state_income_tax", 0) or 0
    charitable = profile.get("charitable_donations", 0) or 0
    student_loan_interest = profile.get("student_loan_interest", 0) or 0
    medical_expenses = profile.get("medical_expenses", 0) or 0

    # SALT cap at $10,000
    salt = min(property_taxes + state_income_tax, 10000)
    total_itemized = mortgage_interest + salt + charitable + medical_expenses

    # Determine if itemizing makes sense
    # 2025 Standard Deductions (IRS Rev. Proc. 2024-40) - matches main engine
    standard_deductions = {
        "SINGLE": 15750,
        "MARRIED_JOINT": 31500,
        "MARRIED_FILING_JOINTLY": 31500,
        "HEAD_OF_HOUSEHOLD": 23850,
        "MARRIED_SEPARATE": 15750,
        "MARRIED_FILING_SEPARATELY": 15750,
        "QUALIFYING_WIDOW": 31500
    }
    # Additional standard deduction for age 65+ (2025: $2,000 single/HOH, $1,600 married)
    standard_ded = standard_deductions.get(tax_filing_status, 15750)
    if is_over_65:
        if tax_filing_status in ("SINGLE", "HEAD_OF_HOUSEHOLD"):
            standard_ded += 2000
        else:
            standard_ded += 1600

    use_standard = total_itemized < standard_ded

    # Calculate credits
    dependents = profile.get("dependents", 0) or 0
    child_tax_credit = dependents * 2000  # $2000 per child

    # Estimated tax payments
    estimated_payments = profile.get("estimated_payments", 0) or 0

    # Estimate withholding (rough estimate: 20% of W-2)
    federal_withholding = profile.get("federal_withholding", 0) or (w2_income * 0.20)

    # Retirement / above-the-line deductions
    retirement_401k = profile.get("retirement_401k", 0) or 0
    retirement_ira = profile.get("retirement_ira", 0) or 0
    hsa_contributions = profile.get("hsa_contributions", 0) or 0

    return {
        "taxpayer": {
            "first_name": profile.get("first_name", "Tax"),
            "last_name": profile.get("last_name", "Client"),
            "ssn": profile.get("ssn", "000-00-0000"),
            "filing_status": tax_filing_status,
            "state": profile.get("state", ""),
            "dependents": dependents,
            "is_over_65": is_over_65,
            "age": age,
        },
        "income": {
            "w2_wages": float(w2_income),
            "federal_withholding": float(federal_withholding),
            "self_employment_income": float(business_income),
            "self_employment_expenses": float(profile.get("business_expenses", 0) or 0),
            "investment_income": float(investment_income),
            "capital_gains": float(profile.get("capital_gains_long", 0) or profile.get("capital_gains", 0) or 0),
            "rental_income": float(rental_income),
            "dividend_income": float(profile.get("dividend_income", 0) or 0),
            "interest_income": float(profile.get("interest_income", 0) or 0),
            # K-1 fields (GAP #6)
            "k1_ordinary_income": float(k1_ordinary),
            "k1_rental_income": float(k1_rental),
            "k1_interest_income": float(k1_interest),
            "k1_dividend_income": float(k1_dividend),
            "k1_royalty_income": float(k1_royalty),
            "k1_guaranteed_payments": float(k1_guaranteed),
        },
        "deductions": {
            "use_standard_deduction": use_standard,
            "itemized_deductions": float(total_itemized),
            "state_local_taxes": float(salt),
            "mortgage_interest": float(mortgage_interest),
            "charitable_contributions": float(charitable),
            "medical_expenses": float(medical_expenses),
            "student_loan_interest": float(student_loan_interest),
        },
        "credits": {
            "child_tax_credit": float(child_tax_credit),
            "education_credits": 0.0,
            "retirement_savers_credit": 0.0
        },
        "payments": {
            "estimated_payments": float(estimated_payments),
            "federal_withholding": float(federal_withholding),
        },
        "retirement": {
            "traditional_401k": float(retirement_401k),
            "traditional_ira": float(retirement_ira),
            "hsa_contributions": float(hsa_contributions),
        }
    }


def build_tax_return_from_profile(profile: Dict[str, Any]) -> "TaxReturn":
    """
    Build a TaxReturn object from chatbot profile for PDF generation.

    Args:
        profile: Chatbot profile dictionary

    Returns:
        TaxReturn object ready for report generation
    """
    if not PDF_GENERATION_AVAILABLE:
        raise ImportError("PDF generation dependencies not available")

    return_data = convert_profile_to_tax_return(profile)

    # Map filing status - uses enum names from models/taxpayer.py
    filing_status_map = {
        "SINGLE": TaxFilingStatus.SINGLE,
        "MARRIED_JOINT": TaxFilingStatus.MARRIED_JOINT,
        "MARRIED_SEPARATE": TaxFilingStatus.MARRIED_SEPARATE,
        "HEAD_OF_HOUSEHOLD": TaxFilingStatus.HEAD_OF_HOUSEHOLD,
        "QUALIFYING_WIDOW": TaxFilingStatus.QUALIFYING_WIDOW
    }

    taxpayer_data = return_data["taxpayer"]
    income_data = return_data["income"]
    deductions_data = return_data["deductions"]
    credits_data = return_data["credits"]

    filing_status = filing_status_map.get(
        taxpayer_data["filing_status"],
        TaxFilingStatus.SINGLE
    )

    # Calculate date_of_birth from age if available (GAP #8)
    # TaxpayerInfo.date_of_birth expects YYYY-MM-DD string
    date_of_birth = None
    age = taxpayer_data.get("age")
    if age is not None:
        try:
            from datetime import date as date_cls
            birth_year = date_cls.today().year - int(age)
            date_of_birth = f"{birth_year}-01-01"  # Approximate to Jan 1
        except (ValueError, TypeError):
            pass

    taxpayer_kwargs = {
        "first_name": taxpayer_data.get("first_name", "Tax"),
        "last_name": taxpayer_data.get("last_name", "Client"),
        "ssn": taxpayer_data.get("ssn", "000-00-0000"),
        "filing_status": filing_status,
        "is_over_65": taxpayer_data.get("is_over_65", False),
        "state": taxpayer_data.get("state"),
    }
    if date_of_birth:
        taxpayer_kwargs["date_of_birth"] = date_of_birth

    taxpayer = TaxpayerInfo(**taxpayer_kwargs)

    # Build income with K-1 aggregated into Form 1040 line items
    # Per IRS rules: K-1 income flows to the same lines as direct income
    # - K-1 Box 5 (interest) → Schedule B → Form 1040 Line 2b
    # - K-1 Box 6 (dividends) → Schedule B → Form 1040 Line 3b
    # - K-1 Box 2/3 (rental) → Schedule E Part II → Form 1040 Line 5
    # - K-1 Box 7 (royalties) → Schedule E Part II → Form 1040 Line 5
    # - K-1 Box 1 (ordinary) + Box 4 (guaranteed) → Schedule E / Schedule SE
    k1_ordinary = income_data.get("k1_ordinary_income", 0) or 0
    k1_guaranteed = income_data.get("k1_guaranteed_payments", 0) or 0
    k1_interest = income_data.get("k1_interest_income", 0) or 0
    k1_dividend = income_data.get("k1_dividend_income", 0) or 0
    k1_rental = income_data.get("k1_rental_income", 0) or 0
    k1_royalty = income_data.get("k1_royalty_income", 0) or 0

    income_kwargs = {
        "self_employment_income": (income_data.get("self_employment_income", 0) or 0) + k1_ordinary + k1_guaranteed,
        "self_employment_expenses": income_data.get("self_employment_expenses", 0),
        "interest_income": (income_data.get("interest_income", 0) or 0) + k1_interest,
        "dividend_income": (income_data.get("dividend_income", 0) or 0) + k1_dividend,
        "rental_income": (income_data.get("rental_income", 0) or 0) + k1_rental,
        "long_term_capital_gains": income_data.get("capital_gains", 0),
        "royalty_income": k1_royalty,
    }

    income = Income(**income_kwargs)

    # Add W-2 if present
    w2_wages = income_data.get("w2_wages", 0)
    if w2_wages > 0:
        from models.income import W2Info
        income.w2_forms.append(W2Info(
            employer_name="Primary Employer",
            wages=w2_wages,
            federal_tax_withheld=income_data.get("federal_withholding", 0) or 0,
        ))

    # Build ScheduleE with K-1 data if present (GAP #6)
    has_k1 = any(income_data.get(k, 0) for k in [
        "k1_ordinary_income", "k1_guaranteed_payments", "k1_interest_income",
        "k1_dividend_income", "k1_rental_income", "k1_royalty_income"
    ])
    if has_k1:
        try:
            from models.schedule_e import ScheduleE, PartnershipSCorpK1
            k1_entry = PartnershipSCorpK1(
                entity_name=income_data.get("k1_entity_name", "Partnership/S-Corp"),
                is_s_corp=income_data.get("k1_entity_type", "").lower() == "s_corp",
                ein=income_data.get("k1_ein", ""),
                ordinary_income_loss=k1_ordinary,
                guaranteed_payments=k1_guaranteed,
                interest_income=k1_interest,
                ordinary_dividends=k1_dividend,
                net_rental_income_loss=k1_rental,
                royalties=k1_royalty,
                self_employment_income=k1_guaranteed,
                qbi_income=k1_ordinary,
            )
            income.schedule_e = ScheduleE(partnership_scorp_k1s=[k1_entry])
        except (ImportError, Exception) as e:
            logger.warning(f"Could not build ScheduleE: {e}")

    deductions = Deductions(
        use_standard_deduction=deductions_data.get("use_standard_deduction", True),
        student_loan_interest=deductions_data.get("student_loan_interest", 0),
    )

    # Set itemized deduction details if itemizing
    if not deductions_data.get("use_standard_deduction", True):
        from models.deductions import ItemizedDeductions
        deductions.itemized = ItemizedDeductions(
            state_local_income_tax=deductions_data.get("state_local_taxes", 0),
            mortgage_interest=deductions_data.get("mortgage_interest", 0),
            charitable_cash=deductions_data.get("charitable_contributions", 0),
            medical_expenses=deductions_data.get("medical_expenses", 0),
        )

    credits = TaxCredits(
        child_tax_credit=credits_data.get("child_tax_credit", 0),
    )

    # Retirement data
    retirement_data = return_data.get("retirement", {})

    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=taxpayer,
        income=income,
        deductions=deductions,
        credits=credits,
        state_of_residence=taxpayer_data.get("state"),
    )

    return tax_return


# =============================================================================
# REQUEST/RESPONSE MODELS — moved to web/advisor/models.py
# Backward-compat imports at top of this file.
# =============================================================================



# =============================================================================
# INTELLIGENT CHAT ENGINE
# =============================================================================

class IntelligentChatEngine:
    """
    The brain of the chatbot - orchestrates all backend services.

    Session storage uses a two-tier architecture:
    L1: In-memory dict (per-process hot cache, ~0ms reads)
    L2: Redis (shared across workers, ~1ms) with SQLite fallback
    Sessions are automatically loaded from L2 if not in L1.
    """

    # Maximum in-memory sessions before cleanup triggers
    MAX_IN_MEMORY_SESSIONS = 500
    # Sessions idle longer than this (seconds) are evicted from memory
    # Configurable via SESSION_TIMEOUT_MINUTES env var (default: 30 min)
    SESSION_IDLE_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "30")) * 60
    # Maximum conversation history messages per session before pruning
    MAX_CONVERSATION_HISTORY = 100
    MAX_TOKEN_ESTIMATE = 100000  # ~100K tokens max (approx 4 chars/token)

    def __init__(self):
        # In-memory cache for fast access (L1 — per-process hot cache)
        self.sessions: Dict[str, Dict[str, Any]] = {}
        # Track last access time for memory eviction
        self._session_access_times: Dict[str, datetime] = {}
        # Lock for async-safe operations
        self._lock = asyncio.Lock()
        # L2 persistence layers
        self._redis_persistence = None  # Async Redis (preferred, shared across workers)
        self._sqlite_persistence: Optional[SessionPersistence] = None  # Sync SQLite (fallback)
        self._redis_init_attempted = False
        if SESSION_PERSISTENCE_AVAILABLE:
            try:
                self._sqlite_persistence = get_session_persistence()
                logger.info("Intelligent Advisor: SQLite persistence enabled (fallback)")
            except Exception as e:
                logger.warning(f"Could not initialize SQLite persistence: {e}")

    async def _ensure_redis(self):
        """Lazily initialize Redis persistence on first async call."""
        if self._redis_persistence is not None or self._redis_init_attempted:
            return
        self._redis_init_attempted = True
        if not REDIS_PERSISTENCE_IMPORTABLE:
            return
        try:
            self._redis_persistence = await get_redis_session_persistence()
            if self._redis_persistence:
                logger.info("Intelligent Advisor: Redis persistence enabled (primary)")
            else:
                logger.info("Intelligent Advisor: Redis not available, using SQLite fallback")
        except Exception as e:
            logger.warning(f"Could not initialize Redis persistence: {e}")

    async def _cleanup_stale_sessions(self) -> None:
        """Evict idle sessions from memory (they remain in database)."""
        if len(self.sessions) < self.MAX_IN_MEMORY_SESSIONS:
            return

        now = datetime.now()
        to_evict = []
        for sid, last_access in self._session_access_times.items():
            elapsed = (now - last_access).total_seconds()
            if elapsed > self.SESSION_IDLE_TIMEOUT:
                to_evict.append(sid)

        for sid in to_evict:
            if sid in self.sessions:
                await self._save_session_to_db(sid, self.sessions[sid])
                del self.sessions[sid]
            self._session_access_times.pop(sid, None)

        if to_evict:
            logger.info(f"Evicted {len(to_evict)} idle sessions from memory, {len(self.sessions)} remain")

    @staticmethod
    def _prune_conversation(conversation: list) -> list:
        """Prune conversation history based on message count AND token estimate.

        Keeps the first 2 messages (welcome + first user message for context)
        and the most recent messages up to the limit.
        Uses approximate token counting (~4 chars per token) as secondary guard.
        """
        limit = IntelligentChatEngine.MAX_CONVERSATION_HISTORY
        token_limit = IntelligentChatEngine.MAX_TOKEN_ESTIMATE

        # Check approximate token count
        total_chars = sum(len(m.get("content", "")) for m in conversation)
        approx_tokens = total_chars // 4

        if len(conversation) <= limit and approx_tokens <= token_limit:
            return conversation

        # If token limit exceeded, reduce more aggressively
        effective_limit = limit
        if approx_tokens > token_limit:
            effective_limit = min(limit, max(20, limit // 2))

        if len(conversation) <= effective_limit:
            return conversation

        return conversation[:2] + conversation[-(effective_limit - 2):]

    def _serialize_session_for_db(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize session data for database storage."""
        # Create a copy to avoid modifying the original
        data = {}
        for key, value in session.items():
            if key == "calculations" and value is not None:
                # Convert TaxCalculationResult to dict
                data[key] = value.dict() if hasattr(value, 'dict') else value
            elif key == "strategies" and value:
                # Convert StrategyRecommendation list to dicts
                data[key] = [s.dict() if hasattr(s, 'dict') else s for s in value]
            elif key == "created_at" and isinstance(value, datetime):
                data[key] = value.isoformat()
            else:
                data[key] = value
        return data

    def _deserialize_session_from_db(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize session data from database storage."""
        session = dict(data)
        # Convert datetime string back to datetime
        if "created_at" in session and isinstance(session["created_at"], str):
            try:
                session["created_at"] = datetime.fromisoformat(session["created_at"])
            except (ValueError, TypeError):
                session["created_at"] = datetime.now()
        return session

    @staticmethod
    def _get_session_tenant_id(session: Dict[str, Any]) -> str:
        """Extract tenant_id from session for multi-tenant persistence scoping."""
        return session.get("tenant_id") or session.get("firm_id") or session.get("cpa_id") or "default"

    async def _save_session_to_db(self, session_id: str, session: Dict[str, Any]) -> None:
        """Save session to Redis (primary) or SQLite (fallback)."""
        await self._ensure_redis()
        serialized = self._serialize_session_for_db(session)
        tenant_id = self._get_session_tenant_id(session)
        metadata = {
            "lead_score": session.get("lead_score", 0),
            "state": session.get("state", "greeting"),
            "has_calculation": session.get("calculations") is not None
        }

        # Try Redis first (shared across workers)
        if self._redis_persistence:
            try:
                await self._redis_persistence.save_session(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    session_type="intelligent_advisor",
                    data=serialized,
                    metadata=metadata,
                )
                logger.debug(f"Session {session_id} saved to Redis (tenant={tenant_id})")
                return
            except Exception as e:
                logger.warning(f"Redis save failed for {session_id}, falling back to SQLite: {e}")

        # Fallback to SQLite
        if self._sqlite_persistence:
            try:
                self._sqlite_persistence.save_session(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    session_type="intelligent_advisor",
                    data=serialized,
                    metadata=metadata,
                )
                logger.debug(f"Session {session_id} saved to SQLite (tenant={tenant_id})")
            except Exception as e:
                logger.warning(f"Failed to save session {session_id} to SQLite: {e}")

    async def _load_session_from_db(self, session_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Load session from Redis (primary) or SQLite (fallback)."""
        await self._ensure_redis()

        # Try Redis first — check tenant-scoped key, then "default" for backward compat
        if self._redis_persistence:
            try:
                tenant_ids_to_try = [tenant_id] if tenant_id else []
                tenant_ids_to_try.append("default")  # backward compat fallback
                for tid in tenant_ids_to_try:
                    data = await self._redis_persistence.load_session(
                        session_id=session_id,
                        tenant_id=tid,
                    )
                    if data:
                        session_data = data.get("data", data) if isinstance(data, dict) and "data" in data else data
                        session = self._deserialize_session_from_db(session_data)
                        logger.info(f"Session {session_id} loaded from Redis (tenant={tid})")
                        return session
            except Exception as e:
                logger.warning(f"Redis load failed for {session_id}, trying SQLite: {e}")

        # Fallback to SQLite
        if self._sqlite_persistence:
            try:
                record = self._sqlite_persistence.load_session(session_id)
                if record and record.data:
                    session = self._deserialize_session_from_db(record.data)
                    logger.info(f"Session {session_id} loaded from SQLite")
                    return session
            except Exception as e:
                logger.warning(f"Failed to load session {session_id} from SQLite: {e}")

        return None

    async def get_session(self, session_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get session without creating. Returns None if not found."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        loaded = await self._load_session_from_db(session_id, tenant_id=tenant_id)
        if loaded:
            self.sessions[session_id] = loaded
            return loaded
        return None

    async def get_or_create_session(self, session_id: str, tenant_id: str = None) -> Dict[str, Any]:
        """
        Get existing session or create new one.

        1. Check in-memory cache first (fast path)
        2. Try loading from database if not in memory
        3. Create new session if not found anywhere
        4. Save new sessions to database

        Args:
            tenant_id: Optional tenant hint for scoped DB lookups.
        """
        async with self._lock:
            # Periodically clean up stale in-memory sessions
            await self._cleanup_stale_sessions()

            # Fast path: check in-memory cache
            if session_id in self.sessions:
                self._session_access_times[session_id] = datetime.now()
                return self.sessions[session_id]

            # Try loading from database (Redis first, then SQLite)
            loaded_session = await self._load_session_from_db(session_id, tenant_id=tenant_id)
            if loaded_session:
                self.sessions[session_id] = loaded_session
                self._session_access_times[session_id] = datetime.now()
                return loaded_session

            # Create new session with FULL checkpoint support for multi-turn undo
            # This enables rolling back to ANY previous point in the conversation
            new_session = {
                "id": session_id,
                "created_at": datetime.now(),
                "profile": {},
                "conversation": [],  # [{role, content, timestamp}]
                "state": "greeting",
                "calculations": None,
                "strategies": [],
                "lead_score": 0,
                SESSION_TOKEN_KEY: generate_session_token(),
                # Firm/CPA context for multi-tenant isolation
                "firm_id": None,       # Set when CPA context is known
                "cpa_id": None,        # CPA slug or ID for branding
                "tenant_id": None,     # Resolved firm_id used for persistence
                "review_mode": False,  # Whether AI responses need CPA approval
                # Enhanced checkpoint system for multi-turn undo
                # Each checkpoint stores FULL state at that point
                "checkpoints": [],  # List of full checkpoint objects (see below)
                "current_turn": 0,
                "corrections_made": 0,
                # AI savings tracking
                "detected_savings": 0,  # Running total of AI-detected savings
                "opportunity_alerts": [],  # New opportunities to surface to user
                # Checkpoint structure:
                # {
                #   "turn": N,
                #   "timestamp": ISO string,
                #   "user_message": "what user said",
                #   "extracted_fields": ["filing_status", "total_income"],  # What was extracted this turn
                #   "profile_snapshot": {full profile at this point},
                #   "conversation_length": N,  # How many messages existed
                #   "summary": "Single, $75k"  # Human-readable summary
                # }
            }
            new_session["_renewed"] = True  # Flag: session was not found, created fresh
            self.sessions[session_id] = new_session
            self._session_access_times[session_id] = datetime.now()

            # Save to database (Redis or SQLite)
            await self._save_session_to_db(session_id, new_session)

            return new_session

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update session with new data and persist to database.

        Also saves tax return data in the format expected by the advisory API
        for PDF generation support.

        Args:
            session_id: Session identifier
            updates: Dictionary of updates to apply

        Returns:
            Updated session
        """
        session = await self.get_or_create_session(session_id)

        async with self._lock:
            # Apply updates
            for key, value in updates.items():
                if key == "profile" and isinstance(value, dict):
                    # Merge profile updates
                    session["profile"].update(value)
                else:
                    session[key] = value

            # Save to database (Redis or SQLite)
            await self._save_session_to_db(session_id, session)

            # Also save tax return data for PDF generation compatibility
            profile = session.get("profile", {})
            if profile.get("filing_status") and profile.get("total_income"):
                self._save_tax_return_for_advisory(session_id, profile, self._get_session_tenant_id(session))

        return session

    def _save_tax_return_for_advisory(self, session_id: str, profile: Dict[str, Any], tenant_id: str = "default") -> None:
        """
        Save tax return data in the format expected by the advisory API.

        This enables PDF generation from chatbot sessions.

        Args:
            session_id: Session identifier
            profile: Chatbot profile data
            tenant_id: Firm tenant identifier for scoping
        """
        if not self._sqlite_persistence:
            return

        try:
            # Convert profile to tax return format
            return_data = convert_profile_to_tax_return(profile, session_id)

            # Save to session_tax_returns table (SQLite — used by PDF generator)
            self._sqlite_persistence.save_session_tax_return(
                session_id=session_id,
                tenant_id=tenant_id,
                tax_year=2025,
                return_data=return_data,
                calculated_results=None  # Will be calculated when report is generated
            )
            logger.debug(f"Tax return data saved for session {session_id} (PDF generation enabled)")
        except Exception as e:
            logger.warning(f"Failed to save tax return data for {session_id}: {e}")

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from both memory and database.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted
        """
        async with self._lock:
            # Remove from memory — get tenant_id before popping
            old_session = self.sessions.pop(session_id, None)
            removed = old_session is not None
            tenant_id = self._get_session_tenant_id(old_session) if old_session else "default"

            # Remove from Redis
            if self._redis_persistence:
                try:
                    await self._redis_persistence.delete_session(session_id, tenant_id=tenant_id)
                except Exception as e:
                    logger.warning(f"Failed to delete session {session_id} from Redis: {e}")

            # Remove from SQLite
            if self._sqlite_persistence:
                try:
                    self._sqlite_persistence.delete_session(session_id)
                except Exception as e:
                    logger.warning(f"Failed to delete session {session_id} from SQLite: {e}")

            return removed

    def get_session_count(self) -> Dict[str, int]:
        """Get count of sessions in memory and database."""
        memory_count = len(self.sessions)
        db_count = 0

        if self._sqlite_persistence:
            try:
                # Count sessions by listing them
                sessions = self._sqlite_persistence.list_sessions("default")
                db_count = len([s for s in sessions if s.session_type == "intelligent_advisor"])
            except Exception:
                pass

        return {
            "in_memory": memory_count,
            "in_database": db_count,
            "redis_enabled": self._redis_persistence is not None,
        }

    def calculate_profile_completeness(self, profile: Dict[str, Any]) -> float:
        """
        Calculate how complete the user's profile is.

        Three tiers:
        - Core (40%): filing_status, total_income, state, dependents, income_type
        - Financial (40%): deductions, retirement, investments, age
        - Detail (20%): specific amounts, K-1, rental, HSA, student loans
        """
        # Core fields (must have for any calculation)
        core_fields = ["filing_status", "total_income", "state", "dependents"]
        core_count = sum(1 for f in core_fields if profile.get(f) is not None and profile.get(f) != "")
        has_income_type = bool(profile.get("income_type") or profile.get("is_self_employed"))
        core_score = ((core_count + (1 if has_income_type else 0)) / 5) * 0.40

        # Financial context (asked or answered — skips count as answered)
        financial_fields = [
            # Field or its "asked" flag
            ("age", "_asked_age"),
            ("retirement_401k", "_asked_retirement"),
            ("mortgage_interest", "_asked_deductions"),
            ("investment_income", "_asked_investments"),
            ("k1_ordinary_income", "_asked_k1"),
            ("rental_income", "_asked_rental"),
        ]
        financial_count = sum(
            1 for field, asked_flag in financial_fields
            if profile.get(field) is not None or profile.get(asked_flag)
        )
        financial_score = (financial_count / len(financial_fields)) * 0.40

        # Detail fields (nice to have for comprehensive report)
        detail_fields = [
            ("hsa_contributions", "_asked_hsa"),
            ("charitable_donations", "_asked_charitable_amount"),
            ("student_loan_interest", "_asked_student_loans"),
            ("estimated_payments", "_asked_estimated"),
            ("business_income", "_asked_business"),
        ]
        detail_count = sum(
            1 for field, asked_flag in detail_fields
            if profile.get(field) is not None or profile.get(asked_flag)
        )
        detail_score = (detail_count / len(detail_fields)) * 0.20

        return min(1.0, core_score + financial_score + detail_score)

    def estimate_partial_savings(self, profile: Dict[str, Any]) -> Optional[float]:
        """Estimate potential savings from partial profile. Returns None if insufficient data."""
        income = float(profile.get("total_income", 0) or 0)
        status = profile.get("filing_status")
        if not income or not status:
            return None

        # Estimate marginal rate from 2025 brackets
        if status == "married_joint":
            brackets = [(23200, .10), (94300, .12), (201050, .22), (383900, .24), (487450, .32), (731200, .35)]
        else:
            brackets = [(11600, .10), (47150, .12), (100525, .22), (191950, .24), (243725, .32), (609350, .35)]
        rate = 0.22  # default
        for top, r in brackets:
            if income <= top:
                rate = r
                break

        est = 0.0
        # Retirement gap
        current_401k = float(profile.get("retirement_401k", 0) or 0)
        max_401k = 23500 + (7500 if int(profile.get("age", 0) or 0) >= 50 else 0)
        gap = max(0, max_401k - current_401k)
        if gap > 0:
            est += gap * rate

        # HSA gap (if not provided)
        if not profile.get("hsa_contributions") and not profile.get("_asked_hsa"):
            hsa_max = 8300 if status == "married_joint" else 4150
            est += hsa_max * rate * 0.3  # Conservative 30% estimate

        return round(est) if est > 200 else None

    def calculate_lead_score(self, profile: Dict[str, Any]) -> int:
        """Calculate lead quality score for CPA handoff."""
        score = 0

        # Base score for engagement
        score += 20

        # Income indicates potential value
        income = profile.get("total_income", 0) or 0
        if income > 200000:
            score += 30
        elif income > 100000:
            score += 20
        elif income > 50000:
            score += 10

        # Complexity indicates need for CPA
        if profile.get("business_income"):
            score += 15
        if profile.get("rental_income"):
            score += 10
        if profile.get("investment_income"):
            score += 10
        if profile.get("is_self_employed"):
            score += 15

        # Contact info
        # (would add if email/phone collected)

        return min(100, score)

    def determine_complexity(self, profile: Dict[str, Any]) -> str:
        """Determine tax situation complexity."""
        if profile.get("business_income") or profile.get("rental_income"):
            if profile.get("is_self_employed") and (profile.get("total_income", 0) or 0) > 100000:
                return "professional"
            return "complex"
        if profile.get("investment_income"):
            return "moderate"
        return "simple"

    # =========================================================================
    # MULTI-TURN UNDO SYSTEM - Dynamic Checkpoint Management
    # =========================================================================

    async def create_checkpoint(self, session_id: str, user_message: str, extracted_fields: List[str]) -> Dict[str, Any]:
        """
        Create a full checkpoint capturing the COMPLETE state at this turn.

        This enables rolling back to ANY previous point in the conversation,
        not just the last turn. Essential for handling "I made a mistake 5 turns ago".

        Args:
            session_id: Session identifier
            user_message: What the user said this turn
            extracted_fields: List of field names that were extracted/changed this turn

        Returns:
            The created checkpoint object
        """
        session = await self.get_or_create_session(session_id)
        profile = session.get("profile", {})

        # Create human-readable summary
        summary = self._create_profile_summary(profile)

        checkpoint = {
            "turn": session.get("current_turn", 0),
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message[:200],  # Truncate long messages
            "extracted_fields": extracted_fields,
            "profile_snapshot": profile.copy(),
            "conversation_length": len(session.get("conversation", [])),
            "summary": summary,
            "had_calculation": session.get("calculations") is not None
        }

        # Store checkpoint
        checkpoints = session.get("checkpoints", [])
        checkpoints.append(checkpoint)

        # Keep last 20 checkpoints for comprehensive undo
        if len(checkpoints) > 20:
            checkpoints = checkpoints[-20:]

        session["checkpoints"] = checkpoints
        session["current_turn"] = session.get("current_turn", 0) + 1

        # Persist
        await self._save_session_to_db(session_id, session)

        return checkpoint

    def _create_profile_summary(self, profile: Dict[str, Any]) -> str:
        """Create a brief human-readable summary of the profile state."""
        parts = []

        if profile.get("filing_status"):
            status_map = {
                "single": "Single",
                "married_joint": "MFJ",
                "married_separate": "MFS",
                "head_of_household": "HoH",
                "qualifying_widow": "QW"
            }
            parts.append(status_map.get(profile["filing_status"], profile["filing_status"]))

        if profile.get("total_income"):
            income = profile["total_income"]
            if income >= 1000000:
                parts.append(f"${income/1000000:.1f}M")
            elif income >= 1000:
                parts.append(f"${income/1000:.0f}k")
            else:
                parts.append(f"${income:.0f}")

        if profile.get("state"):
            parts.append(profile["state"])

        if profile.get("dependents"):
            parts.append(f"{profile['dependents']} dep")

        return ", ".join(parts) if parts else "Empty"

    async def get_undo_options(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get list of checkpoints the user can undo to.

        Returns a list of options showing what was said/changed at each turn,
        so user can pick where to roll back to.

        Returns:
            List of undo options with turn number, message, and changes
        """
        session = await self.get_or_create_session(session_id)
        checkpoints = session.get("checkpoints", [])

        if not checkpoints:
            return []

        options = []
        for cp in reversed(checkpoints):  # Most recent first
            option = {
                "turn": cp["turn"],
                "message_preview": cp["user_message"][:50] + ("..." if len(cp["user_message"]) > 50 else ""),
                "fields_changed": cp["extracted_fields"],
                "profile_summary": cp["summary"],
                "timestamp": cp["timestamp"]
            }
            options.append(option)

        return options

    async def undo_to_turn(self, session_id: str, target_turn: int) -> Dict[str, Any]:
        """
        Undo to a specific turn, restoring the profile state from BEFORE that turn.

        This removes all checkpoints from target_turn onwards and restores
        the profile to what it was before target_turn was processed.

        Args:
            session_id: Session identifier
            target_turn: The turn number to undo to (will restore state BEFORE this turn)

        Returns:
            Dict with:
                - success: bool
                - restored_profile: The profile state after undo
                - removed_turns: How many turns were undone
                - message: Human-readable result
        """
        session = await self.get_or_create_session(session_id)
        checkpoints = session.get("checkpoints", [])

        if not checkpoints:
            return {
                "success": False,
                "message": "No history to undo.",
                "restored_profile": session.get("profile", {}),
                "removed_turns": 0
            }

        # Find the checkpoint BEFORE target_turn
        target_checkpoint = None
        checkpoints_to_keep = []

        for cp in checkpoints:
            if cp["turn"] < target_turn:
                checkpoints_to_keep.append(cp)
                target_checkpoint = cp

        if not target_checkpoint and target_turn > 0:
            # Undoing to turn 0 means reset to empty
            target_checkpoint = {
                "profile_snapshot": {},
                "summary": "Empty",
                "turn": 0
            }
            checkpoints_to_keep = []

        if target_checkpoint is None:
            return {
                "success": False,
                "message": f"Cannot find checkpoint before turn {target_turn}.",
                "restored_profile": session.get("profile", {}),
                "removed_turns": 0
            }

        # Calculate how many turns we're removing
        removed_turns = len(checkpoints) - len(checkpoints_to_keep)

        # Restore the profile
        restored_profile = target_checkpoint.get("profile_snapshot", {}).copy()

        # Update session
        session["profile"] = restored_profile
        session["checkpoints"] = checkpoints_to_keep
        session["current_turn"] = target_checkpoint.get("turn", 0)
        session["calculations"] = None  # Clear calculations - need recalculation
        session["strategies"] = []
        session["corrections_made"] = session.get("corrections_made", 0) + 1

        # Trim conversation history to match
        conv_length = target_checkpoint.get("conversation_length", 0)
        if conv_length > 0 and session.get("conversation"):
            session["conversation"] = session["conversation"][:conv_length]

        # Persist
        await self._save_session_to_db(session_id, session)

        return {
            "success": True,
            "restored_profile": restored_profile,
            "removed_turns": removed_turns,
            "restored_to_turn": target_checkpoint.get("turn", 0),
            "profile_summary": target_checkpoint.get("summary", ""),
            "message": f"Rolled back {removed_turns} turn(s). Profile restored to: {target_checkpoint.get('summary', 'Empty')}"
        }

    async def undo_last_turn(self, session_id: str) -> Dict[str, Any]:
        """Convenience method to undo just the last turn."""
        session = await self.get_or_create_session(session_id)
        current_turn = session.get("current_turn", 0)

        if current_turn <= 0:
            return {
                "success": False,
                "message": "Nothing to undo.",
                "restored_profile": session.get("profile", {}),
                "removed_turns": 0
            }

        return await self.undo_to_turn(session_id, current_turn)

    async def get_conversation_history_for_undo(self, session_id: str) -> str:
        """
        Generate a formatted view of conversation history with turn numbers.

        This helps users identify which turn they want to undo to.
        """
        session = await self.get_or_create_session(session_id)
        checkpoints = session.get("checkpoints", [])

        if not checkpoints:
            return "No conversation history yet."

        lines = ["**Your conversation history:**\n"]

        for cp in checkpoints:
            turn = cp["turn"]
            msg = cp["user_message"][:60] + ("..." if len(cp["user_message"]) > 60 else "")
            fields = ", ".join(cp["extracted_fields"]) if cp["extracted_fields"] else "no data"
            summary = cp["summary"]

            lines.append(f"**Turn {turn}**: \"{msg}\"")
            lines.append(f"   → Extracted: {fields}")
            lines.append(f"   → Profile: {summary}\n")

        lines.append("\n*Say \"undo to turn X\" to roll back to before that turn.*")

        return "\n".join(lines)

    async def get_tax_calculation(self, profile: Dict[str, Any]) -> TaxCalculationResult:
        """
        Get comprehensive tax calculation using validated, cached pipeline.

        Uses the centralized calculation_helper which provides:
        - 11 validation rules (IRS limits, format checks, consistency)
        - Calculation caching for repeat requests
        - Graceful fallback if pipeline unavailable
        """
        try:
            from web.calculation_helper import calculate_taxes

            # Use centralized calculation with validation and caching
            session_id = profile.get("session_id")
            result = await calculate_taxes(
                tax_data=profile,
                session_id=session_id,
                use_cache=True,
                validate=True,  # Enable validation
                is_profile_format=True
            )

            if result.success and result.breakdown:
                breakdown = result.breakdown
                income = profile.get("total_income", 0) or profile.get("w2_income", 0) or 0

                # Sanity check: if income > 20k but federal_tax is 0, use fallback
                federal_tax_raw = breakdown.get("total_federal_tax", breakdown.get("federal_tax", 0))
                if income > 20000 and federal_tax_raw == 0:
                    logger.warning(f"Pipeline returned 0 tax for ${income} income, using fallback")
                    return self._fallback_calculation(profile)

                # Log cache hit for monitoring
                if result.cache_hit:
                    logger.info(f"Tax calculation cache HIT for session {session_id}")

                # Log validation warnings
                for warning in result.warnings:
                    logger.info(f"Validation warning: {warning}")

                return TaxCalculationResult(
                    gross_income=income,
                    adjustments=breakdown.get("above_the_line_deductions", breakdown.get("adjustments_to_income", 0)),
                    agi=breakdown.get("adjusted_gross_income", breakdown.get("agi", income)),
                    deductions=breakdown.get("total_deductions", breakdown.get("deduction_amount", 15000)),
                    deduction_type=breakdown.get("deduction_type", "standard"),
                    taxable_income=breakdown.get("taxable_income", max(0, income - 15000)),
                    federal_tax=breakdown.get("total_federal_tax", breakdown.get("federal_tax", 0)),
                    state_tax=breakdown.get("total_state_tax", breakdown.get("state_tax", 0)),
                    self_employment_tax=breakdown.get("self_employment_tax", breakdown.get("se_tax", 0)),
                    total_tax=breakdown.get("total_tax", 0),
                    effective_rate=breakdown.get("effective_tax_rate", breakdown.get("effective_rate", 0)),
                    marginal_rate=breakdown.get("marginal_bracket", breakdown.get("marginal_tax_rate", 22)),
                    refund_or_owed=breakdown.get("refund_or_owed", 0),
                    is_refund=breakdown.get("refund_or_owed", 0) > 0,
                    # Capital gains breakdown
                    short_term_gains=breakdown.get("net_short_term_gain_loss", 0),
                    long_term_gains=breakdown.get("net_long_term_gain_loss", 0),
                    capital_gains_tax=breakdown.get("preferential_income_tax", 0),
                    capital_loss_deduction=breakdown.get("capital_loss_deduction", 0),
                    net_investment_income=breakdown.get("net_investment_income", 0),
                    niit_tax=breakdown.get("net_investment_income_tax", 0),
                    amt_tax=breakdown.get("alternative_minimum_tax", 0),
                    qbi_deduction=breakdown.get("qbi_deduction", 0),
                    # K-1 and pass-through breakdown
                    k1_ordinary_income_taxable=breakdown.get("k1_ordinary_income", 0),
                    k1_qbi_eligible=breakdown.get("schedule_e_qbi", 0),
                    guaranteed_payments=breakdown.get("guaranteed_payments", 0),
                    passive_loss_allowed=breakdown.get("form_8582_passive_loss_allowed", 0),
                    passive_loss_suspended=breakdown.get("form_8582_suspended_loss", 0),
                    # Rental breakdown
                    rental_net_income=breakdown.get("schedule_e_rental_income", 0),
                    rental_depreciation_claimed=breakdown.get("rental_depreciation", 0),
                    rental_loss_allowed=breakdown.get("form_8582_rental_allowance", 0),
                )
            else:
                # Pipeline failed or returned errors, use fallback
                logger.warning(f"Pipeline calculation failed: {result.errors}")
                return self._fallback_calculation(profile)

        except ImportError as e:
            logger.warning(f"calculation_helper not available: {e}")
            return self._fallback_calculation(profile)
        except Exception as e:
            logger.warning(f"Using fallback calculation: {e}")
            return self._fallback_calculation(profile)

    # =========================================================================
    # 2025 TAX CONSTANTS (IRS Rev. Proc. 2024-40)
    # =========================================================================

    # Standard Deductions 2025
    STANDARD_DEDUCTIONS_2025 = {
        "single": 15750,
        "married_joint": 31500,
        "head_of_household": 23850,
        "married_separate": 15750,
        "qualifying_widow": 31500
    }

    # Additional standard deduction for 65+ or blind
    ADDITIONAL_STD_DEDUCTION_2025 = {
        "single": 2000,
        "head_of_household": 2000,
        "married_joint": 1600,
        "married_separate": 1600,
        "qualifying_widow": 1600
    }

    # 2025 Federal Tax Brackets by filing status
    TAX_BRACKETS_2025 = {
        "single": [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250525, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37)
        ],
        "married_joint": [
            (23850, 0.10),
            (96950, 0.12),
            (206700, 0.22),
            (394600, 0.24),
            (501050, 0.32),
            (751600, 0.35),
            (float('inf'), 0.37)
        ],
        "married_separate": [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250525, 0.32),
            (375800, 0.35),
            (float('inf'), 0.37)
        ],
        "head_of_household": [
            (17050, 0.10),
            (64850, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250525, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37)
        ],
        "qualifying_widow": [  # Same as MFJ
            (23850, 0.10),
            (96950, 0.12),
            (206700, 0.22),
            (394600, 0.24),
            (501050, 0.32),
            (751600, 0.35),
            (float('inf'), 0.37)
        ]
    }

    # NIIT (Net Investment Income Tax) thresholds - IRC §1411
    NIIT_THRESHOLDS = {
        "single": 200000,
        "married_joint": 250000,
        "married_separate": 125000,
        "head_of_household": 200000,
        "qualifying_widow": 250000
    }

    # AMT Exemptions 2025
    AMT_EXEMPTIONS_2025 = {
        "single": 88100,
        "married_joint": 137000,
        "married_separate": 68500,
        "head_of_household": 88100,
        "qualifying_widow": 137000
    }

    # AMT Phase-out thresholds 2025
    AMT_PHASEOUT_2025 = {
        "single": 626350,
        "married_joint": 1252700,
        "married_separate": 626350,
        "head_of_household": 626350,
        "qualifying_widow": 1252700
    }

    # Child Tax Credit 2025
    CTC_AMOUNT = 2000  # Per qualifying child
    CTC_REFUNDABLE_MAX = 1700  # ACTC refundable portion
    CTC_PHASEOUT_START = {
        "single": 200000,
        "married_joint": 400000,
        "married_separate": 200000,
        "head_of_household": 200000,
        "qualifying_widow": 400000
    }

    # SALT Cap (State and Local Tax deduction limit) - IRC §164(b)(6)
    SALT_CAP = 10000  # $10,000 limit through 2025

    # QBI Deduction Thresholds 2025 (Section 199A) - IRC §199A
    # 20% deduction on qualified business income for pass-through entities
    QBI_DEDUCTION_RATE = 0.20
    QBI_TAXABLE_INCOME_THRESHOLD = {
        "single": 191950,
        "married_joint": 383900,
        "married_separate": 191950,
        "head_of_household": 191950,
        "qualifying_widow": 383900
    }
    QBI_PHASEOUT_RANGE = {
        "single": 50000,  # Phase-out over $50K
        "married_joint": 100000,  # Phase-out over $100K
        "married_separate": 50000,
        "head_of_household": 50000,
        "qualifying_widow": 100000
    }

    # State Tax Brackets 2025 (Progressive rates for major states)
    STATE_TAX_BRACKETS = {
        "CA": [  # California - highest state income tax
            (10412, 0.01), (24684, 0.02), (38959, 0.04), (54081, 0.06),
            (68350, 0.08), (349137, 0.093), (418961, 0.103), (698271, 0.113),
            (float('inf'), 0.133)
        ],
        "NY": [  # New York
            (8500, 0.04), (11700, 0.045), (13900, 0.0525), (80650, 0.055),
            (215400, 0.06), (1077550, 0.0685), (5000000, 0.0965),
            (25000000, 0.103), (float('inf'), 0.109)
        ],
        "NJ": [  # New Jersey
            (20000, 0.014), (35000, 0.0175), (40000, 0.035), (75000, 0.05525),
            (500000, 0.0637), (1000000, 0.0897), (float('inf'), 0.1075)
        ],
        "IL": [(float('inf'), 0.0495)],  # Flat rate
        "PA": [(float('inf'), 0.0307)],  # Flat rate
        "OH": [  # Ohio
            (26050, 0.00), (100000, 0.02765), (float('inf'), 0.0375)
        ],
        "GA": [  # Georgia
            (750, 0.01), (2250, 0.02), (3750, 0.03), (5250, 0.04),
            (7000, 0.05), (float('inf'), 0.055)
        ],
        "NC": [(float('inf'), 0.0475)],  # Flat rate
        "MI": [(float('inf'), 0.0425)],  # Flat rate
        "MA": [(float('inf'), 0.05)],  # Flat rate (plus 4% surtax on income >$1M)
        "AZ": [  # Arizona
            (28653, 0.0259), (57305, 0.0334), (171913, 0.0417),
            (float('inf'), 0.045)
        ],
        "CO": [(float('inf'), 0.044)],  # Flat rate
        "VA": [  # Virginia
            (3000, 0.02), (5000, 0.03), (17000, 0.05), (float('inf'), 0.0575)
        ],
        "MN": [  # Minnesota
            (31690, 0.0535), (104090, 0.068), (183340, 0.0785),
            (float('inf'), 0.0985)
        ],
        "OR": [  # Oregon
            (4050, 0.0475), (10200, 0.0675), (125000, 0.0875),
            (float('inf'), 0.099)
        ],
        "CT": [  # Connecticut
            (10000, 0.02), (50000, 0.045), (100000, 0.055), (200000, 0.06),
            (250000, 0.065), (500000, 0.069), (float('inf'), 0.0699)
        ],
        # No income tax states
        "TX": [], "FL": [], "WA": [], "NV": [], "WY": [], "SD": [], "AK": [],
        "TN": [], "NH": []  # NH only taxes interest/dividends
    }

    def _calculate_federal_tax(self, taxable_income: float, filing_status: str) -> tuple:
        """Calculate federal income tax using progressive brackets."""
        brackets = self.TAX_BRACKETS_2025.get(filing_status, self.TAX_BRACKETS_2025["single"])

        tax = 0.0
        marginal_rate = 10
        prev_limit = 0

        for limit, rate in brackets:
            if taxable_income <= 0:
                break
            bracket_income = min(taxable_income, limit - prev_limit)
            tax += bracket_income * rate
            taxable_income -= bracket_income
            if taxable_income > 0:
                marginal_rate = int(rate * 100)
            prev_limit = limit

        return tax, marginal_rate

    def _calculate_state_tax(self, income: float, state: str, filing_status: str) -> float:
        """Calculate state income tax using actual state brackets."""
        if not state or state.upper() not in self.STATE_TAX_BRACKETS:
            # Default to 5% for unknown states
            return income * 0.05

        state = state.upper()
        brackets = self.STATE_TAX_BRACKETS.get(state, [])

        if not brackets:  # No income tax state
            return 0.0

        # Adjust for married filing jointly (most states double brackets)
        multiplier = 2.0 if filing_status in ["married_joint", "qualifying_widow"] else 1.0

        tax = 0.0
        prev_limit = 0
        remaining_income = income

        for limit, rate in brackets:
            if remaining_income <= 0:
                break
            adjusted_limit = limit * multiplier if limit != float('inf') else float('inf')
            bracket_income = min(remaining_income, adjusted_limit - prev_limit)
            tax += bracket_income * rate
            remaining_income -= bracket_income
            prev_limit = adjusted_limit

        return tax

    def _calculate_niit(self, profile: Dict[str, Any], agi: float) -> float:
        """Calculate Net Investment Income Tax (3.8%) - IRC §1411."""
        filing_status = profile.get("filing_status", "single")
        threshold = self.NIIT_THRESHOLDS.get(filing_status, 200000)

        # Net investment income includes interest, dividends, capital gains, rental
        investment_income = (
            (profile.get("investment_income", 0) or 0) +
            (profile.get("rental_income", 0) or 0)
        )

        if agi <= threshold or investment_income <= 0:
            return 0.0

        # NIIT is 3.8% on the lesser of:
        # 1. Net investment income, or
        # 2. AGI over the threshold
        excess_agi = agi - threshold
        niit_base = min(investment_income, excess_agi)

        return niit_base * 0.038

    def _calculate_amt(self, profile: Dict[str, Any], regular_tax: float, agi: float) -> float:
        """Calculate Alternative Minimum Tax - IRC §55."""
        filing_status = profile.get("filing_status", "single")

        # AMT exemption
        exemption = self.AMT_EXEMPTIONS_2025.get(filing_status, 88100)
        phaseout_start = self.AMT_PHASEOUT_2025.get(filing_status, 626350)

        # AMT income starts with AGI and adds back certain deductions
        # Simplified: Add back SALT deduction and misc itemized
        salt_addback = min(
            (profile.get("property_taxes", 0) or 0) +
            (profile.get("state_income_tax", 0) or 0),
            self.SALT_CAP
        )

        amti = agi + salt_addback

        # Phase out exemption (25 cents per dollar over threshold)
        if amti > phaseout_start:
            exemption_reduction = (amti - phaseout_start) * 0.25
            exemption = max(0, exemption - exemption_reduction)

        amt_taxable = max(0, amti - exemption)

        if amt_taxable <= 0:
            return 0.0

        # AMT rates: 26% up to $232,600 (MFS $116,300), 28% above
        amt_bracket = 232600 if filing_status != "married_separate" else 116300

        if amt_taxable <= amt_bracket:
            amt = amt_taxable * 0.26
        else:
            amt = amt_bracket * 0.26 + (amt_taxable - amt_bracket) * 0.28

        # AMT only applies if it exceeds regular tax
        return max(0, amt - regular_tax)

    def _calculate_child_tax_credit(self, profile: Dict[str, Any], agi: float) -> float:
        """Calculate Child Tax Credit with phase-out - IRC §24."""
        dependents = profile.get("dependents", 0) or 0
        if dependents <= 0:
            return 0.0

        filing_status = profile.get("filing_status", "single")
        phaseout_start = self.CTC_PHASEOUT_START.get(filing_status, 200000)

        # Full credit amount
        full_credit = dependents * self.CTC_AMOUNT

        # Phase-out: $50 reduction per $1,000 (or fraction) over threshold
        if agi > phaseout_start:
            excess = agi - phaseout_start
            reduction = (int(excess / 1000) + (1 if excess % 1000 > 0 else 0)) * 50
            full_credit = max(0, full_credit - reduction)

        return full_credit

    def _calculate_qbi_deduction(self, profile: Dict[str, Any], taxable_income: float) -> float:
        """
        Calculate Qualified Business Income (QBI) deduction - IRC §199A.

        The QBI deduction is 20% of qualified business income from pass-through
        entities (sole proprietors, partnerships, S-corps).

        Limitations apply based on taxable income:
        - Below threshold: Full 20% deduction
        - In phase-out range: W-2 wage limitation and UBIA limitation apply
        - Above phase-out: Stricter limitations
        """
        business_income = profile.get("business_income", 0) or 0
        if business_income <= 0:
            return 0.0

        filing_status = profile.get("filing_status", "single")
        threshold = self.QBI_TAXABLE_INCOME_THRESHOLD.get(filing_status, 191950)
        phaseout_range = self.QBI_PHASEOUT_RANGE.get(filing_status, 50000)

        # QBI is generally net business income (simplified - using gross here)
        # In reality, QBI excludes reasonable compensation, capital gains, etc.
        qbi = business_income

        # Calculate tentative QBI deduction (20%)
        tentative_deduction = qbi * self.QBI_DEDUCTION_RATE

        # If taxable income is below threshold, get full deduction
        if taxable_income <= threshold:
            # Also limited to 20% of taxable income (minus capital gains)
            return min(tentative_deduction, taxable_income * 0.20)

        # If in phase-out range, apply partial limitation
        if taxable_income < threshold + phaseout_range:
            # Phase-out percentage
            excess = taxable_income - threshold
            phaseout_pct = excess / phaseout_range

            # For simplicity, reduce deduction proportionally
            # (Full calculation would involve W-2 wages and UBIA)
            reduced_deduction = tentative_deduction * (1 - phaseout_pct * 0.5)
            return min(reduced_deduction, taxable_income * 0.20)

        # Above phase-out: Apply stricter W-2 wage limitation
        # Simplified: Greater of 50% of W-2 wages OR 25% of W-2 wages + 2.5% of UBIA
        # For sole proprietors with no employees, this often means $0
        # We'll use a simplified 50% reduction for high earners
        w2_wages_paid = profile.get("w2_wages_paid", 0) or 0
        if w2_wages_paid > 0:
            wage_limitation = w2_wages_paid * 0.50
            return min(tentative_deduction, wage_limitation, taxable_income * 0.20)

        # High-income sole proprietor with no W-2 wages paid to employees
        # QBI deduction phases out completely
        return 0.0

    def _calculate_itemized_deductions(self, profile: Dict[str, Any], agi: float) -> tuple:
        """Calculate itemized deductions with SALT cap and AGI floors."""
        # Medical expenses (only amount exceeding 7.5% of AGI)
        medical = profile.get("medical_expenses", 0) or 0
        medical_floor = agi * 0.075
        medical_deduction = max(0, medical - medical_floor)

        # SALT (capped at $10,000)
        salt = min(
            (profile.get("property_taxes", 0) or 0) +
            (profile.get("state_income_tax", 0) or 0),
            self.SALT_CAP
        )

        # Mortgage interest (limited to $750K acquisition debt)
        mortgage_interest = profile.get("mortgage_interest", 0) or 0

        # Charitable contributions (limited to 60% of AGI for cash)
        charitable = profile.get("charitable_donations", 0) or 0
        charitable_limit = agi * 0.60
        charitable_deduction = min(charitable, charitable_limit)

        total_itemized = (
            medical_deduction +
            salt +
            mortgage_interest +
            charitable_deduction
        )

        return total_itemized, {
            "medical": medical_deduction,
            "salt": salt,
            "mortgage_interest": mortgage_interest,
            "charitable": charitable_deduction
        }

    def _fallback_calculation(self, profile: Dict[str, Any]) -> TaxCalculationResult:
        """
        Comprehensive tax calculation with:
        - Progressive federal brackets by filing status
        - Progressive state tax brackets for major states
        - SALT $10K cap on itemized deductions
        - NIIT (3.8% Net Investment Income Tax)
        - AMT (Alternative Minimum Tax)
        - Child Tax Credit with phase-out
        - Proper itemized vs standard deduction comparison
        """
        income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single")
        state = profile.get("state", "").upper()

        # Calculate AGI (income minus above-the-line deductions)
        adjustments = 0.0

        # SE tax deduction (1/2 of SE tax) - IRC §164(f)
        se_income = (profile.get("business_income", 0) or 0) * 0.9235
        se_tax = se_income * 0.153 if se_income > 0 else 0
        se_deduction = se_tax * 0.5
        adjustments += se_deduction

        # SE Health Insurance Deduction - IRC §162(l)
        # Self-employed can deduct 100% of health insurance premiums
        if profile.get("is_self_employed") and profile.get("business_income", 0) > 0:
            se_health_insurance = profile.get("health_insurance_premiums", 0) or 0
            # Limited to net SE income (after SE tax deduction)
            net_se_income = profile.get("business_income", 0) - se_deduction
            se_health_deduction = min(se_health_insurance, max(0, net_se_income))
            adjustments += se_health_deduction

        # HSA contributions
        adjustments += profile.get("hsa_contributions", 0) or 0

        # Traditional IRA (simplified - assume deductible)
        adjustments += profile.get("retirement_ira", 0) or 0

        # Student loan interest deduction (up to $2,500)
        student_loan_interest = profile.get("student_loan_interest", 0) or 0
        adjustments += min(student_loan_interest, 2500)

        agi = income - adjustments

        # Calculate deductions (standard vs itemized)
        standard_deduction = self.STANDARD_DEDUCTIONS_2025.get(filing_status, 15000)

        # Add additional deduction for 65+ (simplified - check age)
        age = profile.get("age", 0) or 0
        if age >= 65:
            standard_deduction += self.ADDITIONAL_STD_DEDUCTION_2025.get(filing_status, 1600)

        # Calculate itemized deductions
        itemized_total, itemized_breakdown = self._calculate_itemized_deductions(profile, agi)

        # Use the larger deduction
        if itemized_total > standard_deduction:
            deduction = itemized_total
            deduction_type = "itemized"
        else:
            deduction = standard_deduction
            deduction_type = "standard"

        taxable_income_before_qbi = max(0, agi - deduction)

        # Calculate QBI deduction (Section 199A) for business income
        qbi_deduction = self._calculate_qbi_deduction(profile, taxable_income_before_qbi)
        taxable_income = max(0, taxable_income_before_qbi - qbi_deduction)

        # Calculate federal income tax
        federal_tax, marginal_rate = self._calculate_federal_tax(taxable_income, filing_status)

        # Calculate Child Tax Credit
        ctc = self._calculate_child_tax_credit(profile, agi)
        federal_tax = max(0, federal_tax - ctc)

        # Calculate AMT
        amt = self._calculate_amt(profile, federal_tax, agi)
        federal_tax += amt

        # Calculate NIIT
        niit = self._calculate_niit(profile, agi)
        federal_tax += niit

        # Calculate state tax using progressive brackets
        state_tax = self._calculate_state_tax(agi, state, filing_status)

        # Total tax
        total_tax = federal_tax + se_tax + state_tax
        effective_rate = (total_tax / income * 100) if income > 0 else 0

        # Calculate withholding/payments vs tax owed
        withholding = profile.get("federal_withholding", 0) or 0
        estimated_payments = profile.get("estimated_payments", 0) or 0
        total_payments = withholding + estimated_payments
        refund_or_owed = total_payments - federal_tax

        # Build tax notices for transparency
        tax_notices = []
        if qbi_deduction > 0:
            tax_notices.append(f"QBI deduction (§199A): ${qbi_deduction:,.0f} saved")
        if amt > 0:
            tax_notices.append(f"AMT applies: ${amt:,.0f} additional tax")
        if niit > 0:
            tax_notices.append(f"NIIT (3.8%) applies: ${niit:,.0f} on investment income")
        if deduction_type == "itemized" and itemized_breakdown.get("salt", 0) >= self.SALT_CAP:
            tax_notices.append(f"SALT deduction capped at ${self.SALT_CAP:,}")
        if ctc > 0:
            tax_notices.append(f"Child Tax Credit applied: ${ctc:,.0f}")

        # Calculate capital gains info
        short_term_gains = profile.get("capital_gains_short", 0) or 0
        long_term_gains = profile.get("capital_gains_long", 0) or profile.get("capital_gains", 0) or 0
        # Preferential rate on LTCG (simplified 15% rate)
        capital_gains_tax = long_term_gains * 0.15 if long_term_gains > 0 else 0
        # Net investment income for NIIT
        net_investment_income = (
            (profile.get("interest_income", 0) or 0) +
            (profile.get("dividend_income", 0) or 0) +
            short_term_gains + long_term_gains +
            (profile.get("rental_income", 0) or 0)
        )

        # Calculate K-1 and rental info for fallback
        k1_ordinary = (profile.get("k1_ordinary_income", 0) or 0)
        k1_qbi = k1_ordinary if not profile.get("k1_is_sstb", False) else 0
        rental_net = (profile.get("rental_gross_income", 0) or 0) - (profile.get("rental_expenses", 0) or 0)
        if rental_net == 0:
            rental_net = profile.get("rental_income", 0) or 0

        return TaxCalculationResult(
            gross_income=float(money(income)),
            adjustments=float(money(adjustments)),
            agi=float(money(agi)),
            deductions=float(money(deduction)),
            deduction_type=deduction_type,
            taxable_income=float(money(taxable_income)),
            federal_tax=float(money(federal_tax)),
            state_tax=float(money(state_tax)),
            self_employment_tax=float(money(se_tax)),
            total_tax=float(money(total_tax)),
            effective_rate=float(money(effective_rate)),
            marginal_rate=marginal_rate,
            refund_or_owed=float(money(refund_or_owed)),
            is_refund=refund_or_owed > 0,
            # Enhanced breakdown
            amt_tax=float(money(amt)),
            niit_tax=float(money(niit)),
            child_tax_credit=float(money(ctc)),
            qbi_deduction=float(money(qbi_deduction)),
            itemized_breakdown=itemized_breakdown if deduction_type == "itemized" else None,
            tax_bracket_detail=f"{marginal_rate}% bracket",
            tax_notices=tax_notices,
            # Capital gains breakdown
            short_term_gains=float(money(short_term_gains)),
            long_term_gains=float(money(long_term_gains)),
            capital_gains_tax=float(money(capital_gains_tax)),
            capital_loss_deduction=0.0,
            net_investment_income=float(money(net_investment_income)),
            # K-1 and pass-through breakdown
            k1_ordinary_income_taxable=float(money(k1_ordinary)),
            k1_qbi_eligible=float(money(k1_qbi)),
            guaranteed_payments=float(money(profile.get("k1_guaranteed_payments", 0) or 0)),
            passive_loss_allowed=0.0,  # Would need full PAL calc
            passive_loss_suspended=0.0,
            # Rental breakdown
            rental_net_income=float(money(rental_net)),
            rental_depreciation_claimed=float(money(profile.get("rental_depreciation", 0) or 0)),
            rental_loss_allowed=0.0,  # Would need PAL calc
            used_fallback=True,
        )

    async def _ai_extract_profile_data(self, message: str, session: dict) -> dict:
        """Use IntelligentTaxAgent for NLP entity extraction from user message."""
        if not AI_ENTITY_EXTRACTION_ENABLED:
            return {}
        try:
            agent = IntelligentTaxAgent(use_ocr=False)
            existing_profile = session.get("profile", {})
            context_msg = f"Current profile: {existing_profile}. User says: {message}"
            # process_message is synchronous — run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, agent.process_message, context_msg)

            extracted = {}
            context = agent.context
            for entity in context.extraction_history:
                if entity.confidence.value in ("HIGH", "MEDIUM"):
                    key_map = {
                        "w2_wages": "w2_income",
                        "total_income": "total_income",
                        "filing_status": "filing_status",
                        "dependents": "dependents",
                        "state": "state",
                        "age": "age",
                        "mortgage_interest": "mortgage_interest",
                        "self_employment_income": "self_employment_income",
                        "business_income": "business_income",
                        "retirement_contributions": "retirement_401k",
                        "charitable_contributions": "charitable_donations",
                        "hsa_contribution": "hsa_contributions",
                        "student_loan_interest": "student_loan_interest",
                    }
                    profile_key = key_map.get(entity.entity_type, entity.entity_type)
                    extracted[profile_key] = entity.value

            if extracted:
                logger.info(f"AI extracted {len(extracted)} entities: {list(extracted.keys())}")
            return extracted
        except Exception as e:
            logger.warning(
                "AI fallback activated",
                extra={
                    "service": "advisor_entity_extraction",
                    "source": "fallback",
                    "reason": str(e),
                    "impact": "user message entities not extracted, relying on rule-based parsing",
                },
            )
            return {}

    async def _ai_reason_about_tax_question(self, question: str, session: dict) -> Optional[str]:
        """Use UnifiedAIService for deep tax reasoning when user asks complex questions."""
        try:
            ai = get_ai_service()
            profile = session.get("profile", {})
            profile_summary = _summarize_profile(profile)

            response = await ai.reason(
                problem=question,
                context=f"""You are a tax advisor assistant. The taxpayer's profile:
{profile_summary}

Answer their question with specific, actionable advice based on their situation.
Include IRS references where applicable. Keep response under 200 words.
Always note this is not official tax advice and they should consult a CPA.""",
            )
            return response.content
        except Exception as e:
            logger.warning(
                "AI fallback activated",
                extra={
                    "service": "advisor_reasoning",
                    "source": "fallback",
                    "reason": str(e),
                    "impact": "user receives template response instead of AI-reasoned answer",
                },
            )
            return None

    async def get_tax_strategies(self, profile: Dict[str, Any], calculation: TaxCalculationResult) -> List[StrategyRecommendation]:
        """Get personalized tax optimization strategies using AI + rule-based detection."""
        strategies = []
        ai_categories: set = set()

        # --- AI-POWERED OPPORTUNITY DETECTION ---
        if AI_OPPORTUNITIES_ENABLED:
            try:
                taxpayer_profile = _session_profile_to_taxpayer_profile(profile)
                detector = TaxOpportunityDetector()
                opportunities = detector.detect_opportunities(taxpayer_profile)

                for i, opp in enumerate(opportunities):
                    confidence_val = opp.confidence if isinstance(opp.confidence, float) else 0.8
                    confidence_str = "high" if confidence_val >= 0.8 else "medium" if confidence_val >= 0.5 else "low"
                    priority_str = opp.priority.value if hasattr(opp.priority, "value") else str(opp.priority)
                    category_str = opp.category.value if hasattr(opp.category, "value") else str(opp.category)
                    ai_categories.add(category_str.lower())

                    strategies.append(StrategyRecommendation(
                        id=opp.id or f"ai_opp_{i}",
                        category=category_str.replace("_", " ").title(),
                        title=opp.title,
                        summary=opp.description,
                        detailed_explanation=opp.description,
                        estimated_savings=float(opp.estimated_savings) if opp.estimated_savings else 0,
                        confidence=confidence_str,
                        priority=priority_str,
                        action_steps=[opp.action_required] if opp.action_required else [],
                        irs_reference=opp.irs_reference or "",
                        tier="free" if priority_str == "high" else "premium",
                        risk_level="low",
                        metadata={"_source": "ai"},
                    ))
                logger.info(f"AI detected {len(opportunities)} opportunities")
            except Exception as e:
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "advisor_strategy",
                        "source": "template",
                        "reason": str(e),
                        "impact": "user receives only hardcoded strategy templates, no AI-detected opportunities",
                    },
                )

        # --- EXISTING HARDCODED STRATEGIES (as fallback/supplement) ---
        marginal_rate = calculation.marginal_rate / 100

        # 1. Retirement Optimization
        current_401k = profile.get("retirement_401k", 0) or 0
        max_401k = 23500
        age = profile.get("age", 40) or 40
        if age >= 50:
            max_401k += 7500  # Catch-up

        remaining_401k = max(0, max_401k - current_401k)
        if remaining_401k > 0:
            savings = remaining_401k * marginal_rate
            strategies.append(StrategyRecommendation(
                id="retirement-401k",
                category="Retirement",
                title="Maximize 401(k) Contributions",
                summary=f"Contribute ${remaining_401k:,.0f} more to your 401(k) to save ${savings:,.0f} in taxes.",
                detailed_explanation=f"""Your 401(k) contributions reduce your taxable income dollar-for-dollar.
At your {calculation.marginal_rate}% marginal tax rate, every $1,000 you contribute saves you ${marginal_rate * 1000:,.0f} in taxes immediately,
while building your retirement wealth tax-deferred.""",
                estimated_savings=float(money(savings)),
                confidence="high",
                priority="high" if savings > 2000 else "medium",
                action_steps=[
                    "Log into your employer's benefits portal",
                    f"Increase your contribution rate to reach ${max_401k:,.0f} by December",
                    "Consider front-loading contributions if cash flow allows"
                ],
                irs_reference="IRS Publication 560"
            ))

        # 2. IRA Contributions - Check income limits for deductibility
        current_ira = profile.get("retirement_ira", 0) or 0
        max_ira = 7000
        if age >= 50:
            max_ira += 1000

        total_income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single")
        has_workplace_plan = (profile.get("retirement_401k", 0) or 0) > 0 or profile.get("has_401k", False)

        # IRS 2025 Traditional IRA deduction limits when covered by workplace plan
        # Single: Phase-out $77,000 - $87,000
        # MFJ: Phase-out $123,000 - $143,000
        if filing_status in ["married_filing_jointly", "married filing jointly"]:
            ira_deduction_limit = 143000
            ira_phaseout_start = 123000
        else:
            ira_deduction_limit = 87000
            ira_phaseout_start = 77000

        remaining_ira = max(0, max_ira - current_ira)

        # Determine if Traditional IRA is deductible for this user
        is_high_earner = total_income > ira_deduction_limit
        partially_deductible = total_income > ira_phaseout_start and total_income <= ira_deduction_limit

        if remaining_ira > 0:
            if is_high_earner and has_workplace_plan:
                # High earner with workplace plan - recommend Backdoor Roth IRA
                strategies.append(StrategyRecommendation(
                    id="retirement-backdoor-roth",
                    category="Retirement",
                    title="Backdoor Roth IRA",
                    summary=f"Use Backdoor Roth IRA strategy to contribute ${remaining_ira:,.0f} to tax-free retirement savings.",
                    detailed_explanation=f"""At ${total_income:,.0f} income with a workplace retirement plan, Traditional IRA
contributions are NOT tax-deductible. However, you can use the Backdoor Roth IRA strategy:

1. Contribute ${remaining_ira:,.0f} to a Traditional IRA (non-deductible)
2. Immediately convert to Roth IRA
3. Enjoy tax-free growth and tax-free withdrawals in retirement

This is a legal strategy used by high earners to access Roth benefits despite income limits.""",
                    estimated_savings=float(money(remaining_ira * marginal_rate * 0.5)),  # Future tax-free growth
                    confidence="high",
                    priority="high",
                    action_steps=[
                        "Ensure you have NO pre-tax Traditional IRA balances (to avoid pro-rata rule)",
                        f"Contribute ${remaining_ira:,.0f} to a Traditional IRA (non-deductible)",
                        "Immediately convert the entire balance to a Roth IRA",
                        "Report on Form 8606 with your tax return"
                    ],
                    irs_reference="IRS Publication 590-A, Form 8606"
                ))
            elif is_high_earner:
                # High earner without workplace plan - may still be able to deduct, but recommend Roth
                savings = remaining_ira * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="retirement-ira",
                    category="Retirement",
                    title="Traditional or Backdoor Roth IRA",
                    summary=f"Consider Traditional IRA (deductible) or Backdoor Roth IRA strategy.",
                    detailed_explanation=f"""At ${total_income:,.0f} income without a workplace retirement plan,
you may still be able to deduct Traditional IRA contributions. However, with your high income,
consider whether tax-free growth in a Roth IRA might benefit you more long-term.""",
                    estimated_savings=float(money(savings)),
                    confidence="medium",
                    priority="medium",
                    action_steps=[
                        f"Contribute up to ${max_ira:,.0f} before the April tax deadline",
                        "Evaluate Traditional vs Roth based on expected retirement tax rates",
                        "Consider Backdoor Roth if you want tax-free growth"
                    ],
                    irs_reference="IRS Publication 590-A"
                ))
            else:
                # Lower income - Traditional IRA is deductible
                savings = remaining_ira * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="retirement-ira",
                    category="Retirement",
                    title="Traditional IRA Contribution",
                    summary=f"Contribute ${remaining_ira:,.0f} to a Traditional IRA for ${savings:,.0f} tax savings.",
                    detailed_explanation=f"""Traditional IRA contributions are tax-deductible at your income level.
At your {calculation.marginal_rate}% marginal tax rate, every $1,000 you contribute saves you ${marginal_rate * 1000:,.0f} in taxes immediately.""",
                    estimated_savings=float(money(savings)),
                    confidence="high",
                    priority="medium",
                    action_steps=[
                        "Open a Traditional IRA if you don't have one",
                        f"Contribute up to ${max_ira:,.0f} before the April tax deadline",
                        "Consider Roth IRA if you expect higher taxes in retirement"
                    ],
                    irs_reference="IRS Publication 590-A"
                ))

        # 2b. Mega Backdoor Roth for high earners with 401(k)
        if is_high_earner and has_workplace_plan:
            mega_contribution = 46000  # 2025 limit: $69,000 total - $23,000 employee
            mega_future_value = mega_contribution * 0.07 * 20  # 7% for 20 years simplified
            strategies.append(StrategyRecommendation(
                id="retirement-mega-backdoor",
                category="Retirement",
                title="Mega Backdoor Roth",
                summary=f"Contribute up to ${mega_contribution:,.0f} extra to Roth via after-tax 401(k) contributions.",
                detailed_explanation=f"""The Mega Backdoor Roth allows high earners to contribute significantly more to Roth accounts:

1. Max out your regular 401(k) ($23,500 in 2025)
2. Make after-tax contributions to your 401(k) (if your plan allows)
3. Convert these after-tax contributions to Roth 401(k) or roll to Roth IRA
4. The 2025 total 401(k) limit is $69,000 (including employer match)

This could add ${mega_contribution:,.0f} more per year to tax-free retirement savings.""",
                estimated_savings=float(money(mega_future_value * 0.25)),  # Estimated future tax savings
                confidence="medium",
                priority="high",
                action_steps=[
                    "Check if your 401(k) plan allows after-tax contributions",
                    "Verify your plan allows in-plan Roth conversions or in-service distributions",
                    "Coordinate with HR/plan administrator",
                    "Consider timing - convert quickly to minimize taxable gains"
                ],
                irs_reference="IRS Notice 2014-54"
            ))

        # 3. HSA Contributions (if applicable)
        if profile.get("hsa_contributions") is not None or True:  # Assume eligible
            current_hsa = profile.get("hsa_contributions", 0) or 0
            max_hsa = 4300 if profile.get("filing_status") == "single" else 8550
            if age >= 55:
                max_hsa += 1000

            remaining_hsa = max(0, max_hsa - current_hsa)
            if remaining_hsa > 0:
                savings = remaining_hsa * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="healthcare-hsa",
                    category="Healthcare",
                    title="Health Savings Account (HSA)",
                    summary=f"Contribute ${remaining_hsa:,.0f} to HSA for triple tax advantage.",
                    detailed_explanation="""HSA offers the only triple tax benefit in the tax code:
1. Tax-deductible contributions
2. Tax-free growth
3. Tax-free withdrawals for medical expenses

After age 65, HSA funds can be used for any purpose (just taxed as ordinary income, like an IRA).""",
                    estimated_savings=float(money(savings)),
                    confidence="high",
                    priority="high",
                    action_steps=[
                        "Verify you have a high-deductible health plan (HDHP)",
                        f"Set up automatic HSA contributions to reach ${max_hsa:,.0f}",
                        "Keep receipts for medical expenses - reimburse yourself later"
                    ],
                    irs_reference="IRS Publication 969"
                ))

        # 4. Charitable Giving Strategy
        charitable = profile.get("charitable_donations", 0) or 0
        if charitable > 0 or profile.get("total_income", 0) > 100000:
            strategies.append(StrategyRecommendation(
                id="charitable-bunching",
                category="Charitable",
                title="Charitable Donation Bunching",
                summary="Bunch 2-3 years of donations into one year to itemize deductions.",
                detailed_explanation=f"""With the $15,000 standard deduction, many people can't itemize.
By 'bunching' multiple years of charitable donations into a single year, you can exceed the standard deduction
and get a larger tax benefit. Consider a Donor-Advised Fund (DAF) for flexibility.""",
                estimated_savings=float(money(charitable * 0.3 * marginal_rate)),
                confidence="medium",
                priority="medium" if charitable > 5000 else "low",
                action_steps=[
                    "Calculate your total itemized deductions",
                    "If close to standard deduction, consider bunching",
                    "Open a Donor-Advised Fund for flexibility",
                    "Donate appreciated stock instead of cash to avoid capital gains"
                ],
                irs_reference="IRS Publication 526"
            ))

        # 5. Business/Self-Employment Strategies
        if profile.get("is_self_employed") or profile.get("business_income"):
            business_income = profile.get("business_income", 0) or 0

            # S-Corp Election
            if business_income > 50000:
                se_savings = business_income * 0.5 * 0.153  # Save SE tax on distributions
                strategies.append(StrategyRecommendation(
                    id="entity-scorp",
                    category="Business Structure",
                    title="S-Corporation Election",
                    summary=f"S-Corp election could save you ${se_savings:,.0f} in self-employment taxes.",
                    detailed_explanation=f"""As a sole proprietor, you pay 15.3% self-employment tax on all net earnings.
With an S-Corp, you pay yourself a 'reasonable salary' (SE tax applies), but remaining profits
are distributions (no SE tax). At ${business_income:,.0f} income, this can mean significant savings.""",
                    estimated_savings=float(money(se_savings)),
                    confidence="high",
                    priority="high" if se_savings > 3000 else "medium",
                    action_steps=[
                        "Consult with a CPA about reasonable salary requirements",
                        "File Form 2553 to elect S-Corp status",
                        "Set up payroll for yourself",
                        "Consider timing - election typically takes effect next year"
                    ],
                    irs_reference="IRS Form 2553"
                ))

            # Home Office Deduction
            if profile.get("home_office_sqft"):
                sqft = profile.get("home_office_sqft", 200)
                home_office_deduction = min(sqft * 5, 1500)  # Simplified method
                savings = home_office_deduction * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="business-homeoffice",
                    category="Business Deductions",
                    title="Home Office Deduction",
                    summary=f"Claim ${home_office_deduction:,.0f} home office deduction.",
                    detailed_explanation="""If you use part of your home regularly and exclusively for business,
you can deduct home office expenses. The simplified method allows $5 per square foot (up to 300 sq ft = $1,500).
The regular method may yield higher deductions but requires more recordkeeping.""",
                    estimated_savings=float(money(savings)),
                    confidence="high",
                    priority="medium",
                    action_steps=[
                        "Measure your dedicated home office space",
                        "Choose simplified ($5/sqft) or regular method",
                        "Take photos of your home office for documentation",
                        "Keep utility bills and home expense records"
                    ],
                    irs_reference="IRS Publication 587"
                ))

            # QBI Deduction
            if business_income > 0:
                qbi_deduction = business_income * 0.20  # Simplified
                savings = qbi_deduction * marginal_rate
                strategies.append(StrategyRecommendation(
                    id="business-qbi",
                    category="Business Deductions",
                    title="Qualified Business Income (QBI) Deduction",
                    summary=f"Claim up to ${qbi_deduction:,.0f} QBI deduction (20% pass-through).",
                    detailed_explanation="""The QBI deduction allows you to deduct up to 20% of qualified business income
from pass-through entities (sole proprietorships, S-corps, partnerships). Income limits may apply.""",
                    estimated_savings=float(money(savings)),
                    confidence="high",
                    priority="high",
                    action_steps=[
                        "Verify your business qualifies (most do)",
                        "Ensure proper recordkeeping of business income",
                        "Be aware of W-2 wage and property limitations at higher incomes"
                    ],
                    irs_reference="IRS Form 8995"
                ))

        # 6. Education Credits
        if profile.get("dependents", 0) > 0:
            strategies.append(StrategyRecommendation(
                id="credits-education",
                category="Education",
                title="American Opportunity Tax Credit",
                summary="Up to $2,500 per student for college expenses.",
                detailed_explanation="""The AOTC provides up to $2,500 per eligible student for the first 4 years of college.
It's 100% of the first $2,000 and 25% of the next $2,000 in qualified expenses.
40% is refundable (up to $1,000), meaning you get it even if you owe no taxes.""",
                estimated_savings=2500,
                confidence="medium",
                priority="high",
                action_steps=[
                    "Gather Form 1098-T from the educational institution",
                    "Keep receipts for books, supplies, and equipment",
                    "Verify income limits ($90,000 single, $180,000 MFJ)"
                ],
                irs_reference="IRS Form 8863"
            ))

        # 7. Child Tax Credit
        dependents = profile.get("dependents", 0) or 0
        if dependents > 0:
            ctc_amount = dependents * 2000
            strategies.append(StrategyRecommendation(
                id="credits-ctc",
                category="Family",
                title="Child Tax Credit",
                summary=f"Claim ${ctc_amount:,.0f} in Child Tax Credit for {dependents} dependent(s).",
                detailed_explanation=f"""The Child Tax Credit provides $2,000 per qualifying child under 17.
Up to $1,700 per child is refundable as the Additional Child Tax Credit.
Phase-out begins at $200,000 (single) or $400,000 (MFJ).""",
                estimated_savings=ctc_amount,
                confidence="high",
                priority="high",
                action_steps=[
                    "Verify each child is under 17 at year-end",
                    "Ensure you have valid SSN for each child",
                    "Complete Schedule 8812 with your return"
                ],
                irs_reference="IRS Schedule 8812"
            ))

        # 8. Tax-Loss Harvesting - Show when user has capital gains or high income
        investment_income = profile.get("investment_income", 0) or 0
        short_term_gains = profile.get("capital_gains_short", 0) or calculation.short_term_gains or 0
        long_term_gains = profile.get("capital_gains_long", 0) or profile.get("capital_gains", 0) or calculation.long_term_gains or 0
        total_cap_gains = short_term_gains + long_term_gains

        if total_cap_gains > 0 or investment_income > 0 or total_income > 200000:
            # Calculate potential savings from harvesting
            if total_cap_gains > 0:
                # Can offset gains directly + $3k ordinary income
                potential_offset = total_cap_gains
                # ST gains save at ordinary rate, LT at preferential
                savings = (short_term_gains * marginal_rate) + (long_term_gains * 0.15)
                savings += min(3000, max(0, 10000 - total_cap_gains)) * marginal_rate  # Extra ordinary income offset
            else:
                # No gains yet - estimate based on income level
                estimated_harvesting_potential = min(10000, total_income * 0.02) if total_income > 200000 else 3000
                potential_offset = estimated_harvesting_potential
                savings = min(3000, estimated_harvesting_potential) * marginal_rate

            # Check for NIIT exposure (adds 3.8% value to harvesting)
            niit_threshold = 200000 if filing_status == "single" else 250000
            has_niit_exposure = calculation.niit_tax > 0 or total_income > niit_threshold
            if has_niit_exposure and total_cap_gains > 0:
                savings += total_cap_gains * 0.038  # NIIT savings

            gain_detail = f"You have ${total_cap_gains:,.0f} in capital gains " if total_cap_gains > 0 else "Even without current gains, "
            niit_note = f"\n\n**NIIT Alert**: With NIIT exposure, harvesting saves an additional 3.8% on investment income!" if has_niit_exposure else ""

            strategies.append(StrategyRecommendation(
                id="investment-tlh",
                category="Investment",
                title="Tax-Loss Harvesting",
                summary=f"Harvest losses to offset ${potential_offset:,.0f} in gains, saving ${savings:,.0f} in taxes.",
                detailed_explanation=f"""{gain_detail}making tax-loss harvesting valuable:

1. **Offset Capital Gains**: Sell investments at a loss to offset gains dollar-for-dollar
   - Short-term gains (taxed at {calculation.marginal_rate}%): ${short_term_gains:,.0f}
   - Long-term gains (taxed at 15-20%): ${long_term_gains:,.0f}
2. **Ordinary Income Deduction**: Deduct up to $3,000 of excess losses against your ordinary income
3. **Carry Forward**: Unused losses carry forward indefinitely{niit_note}

Estimated tax savings: **${savings:,.0f}**""",
                estimated_savings=float(money(savings)),
                confidence="high" if total_cap_gains > 0 else "medium",
                priority="high" if total_cap_gains > 10000 or has_niit_exposure else "medium",
                action_steps=[
                    "Review your brokerage accounts for unrealized losses",
                    "Identify positions down 10%+ that you can harvest",
                    f"Target losses of ${potential_offset:,.0f}+ to offset your gains",
                    "Sell losing positions before year-end (or anytime markets dip)",
                    "Wait 31+ days before repurchasing same security (wash sale rule)",
                    "Consider similar (not identical) replacement investments immediately"
                ],
                irs_reference="IRS Publication 550",
                deadline="December 31, 2025" if total_cap_gains > 0 else None
            ))

        # --- RECOMMENDATION ORCHESTRATOR ENRICHMENT ---
        if AI_RECOMMENDATIONS_ENABLED and len(strategies) < 10:
            try:
                rec_dict = _session_profile_to_rec_dict(profile)
                rec_result = await get_recommendations(
                    profile=rec_dict,
                    max_recommendations=10 - len(strategies),
                )
                existing_titles = {s.title.lower() for s in strategies}
                for rec in rec_result.recommendations:
                    if rec.title.lower() not in existing_titles:
                        strategies.append(StrategyRecommendation(
                            id=f"rec_{rec.source}_{len(strategies)}",
                            category=rec.category,
                            title=rec.title,
                            summary=rec.description,
                            detailed_explanation=rec.description,
                            estimated_savings=rec.potential_savings,
                            confidence=rec.confidence if isinstance(rec.confidence, str) else (
                                "high" if rec.confidence >= 0.8 else "medium" if rec.confidence >= 0.5 else "low"
                            ),
                            priority=rec.priority,
                            action_steps=rec.action_items,
                            irs_reference="",
                            tier="premium" if rec.complexity == "complex" else "free",
                            risk_level="medium" if rec.warnings else "low",
                        ))
                logger.info(f"Orchestrator added {len(rec_result.recommendations)} recommendations")
            except Exception as e:
                logger.warning(f"Recommendation orchestrator failed: {e}")

        # --- AI ENHANCEMENT: Personalized explanations ---
        if AI_RECOMMENDATIONS_ENABLED:
            try:
                enhancer = get_ai_enhancer()
                if enhancer.is_available:
                    from recommendation.recommendation_engine import TaxSavingOpportunity
                    for strategy in strategies[:5]:
                        try:
                            opp = TaxSavingOpportunity(
                                category=strategy.category,
                                title=strategy.title,
                                estimated_savings=strategy.estimated_savings,
                                priority=strategy.priority,
                                description=strategy.summary,
                                action_required=strategy.action_steps[0] if strategy.action_steps else "",
                                confidence=80.0 if strategy.confidence == "high" else 60.0 if strategy.confidence == "medium" else 40.0,
                                irs_reference=strategy.irs_reference or "",
                            )
                            explanation = enhancer.explain_in_plain_language(
                                opportunity=opp,
                                education_level="general",
                            )
                            if explanation:
                                strategy.personalized_explanation = explanation
                        except Exception:
                            pass  # Individual enhancement failure is non-critical
            except Exception as e:
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "advisor_strategy_enhancement",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "strategies returned without AI-personalized explanations",
                    },
                )

        # Tag any untagged strategies as templates and record quality
        metrics = get_ai_metrics_service()
        for s in strategies:
            if s.metadata is None:
                s.metadata = {"_source": "template"}
            populated = sum(1 for v in [s.summary, s.detailed_explanation, s.action_steps, s.irs_reference, s.estimated_savings, s.confidence] if v)
            source = s.metadata.get("_source", "template")
            metrics.record_response_quality(
                service="advisor_strategy", source=source,
                response_fields_populated=populated, total_fields=6,
            )

        # Sort by estimated savings (highest first)
        strategies.sort(key=lambda x: (-x.estimated_savings,))

        return strategies

    async def generate_executive_summary(self, profile: Dict, calculation: TaxCalculationResult, strategies: List[StrategyRecommendation]) -> str:
        """Generate an executive summary of the tax analysis (AI-powered with template fallback)."""
        total_savings = sum(s.estimated_savings for s in strategies)

        # --- AI narrative path ---
        if AI_REPORT_NARRATIVES_ENABLED:
            try:
                from advisory.ai_narrative_generator import (
                    get_narrative_generator, ClientProfile,
                    CommunicationStyle, TaxSophistication,
                )
                generator = get_narrative_generator()
                client_profile = ClientProfile(
                    name=profile.get("name", "Valued Client"),
                    communication_style=CommunicationStyle.CONVERSATIONAL,
                    tax_sophistication=TaxSophistication.INTERMEDIATE,
                    primary_concern="tax optimization",
                )
                analysis_data = {
                    "tax_year": 2025,
                    "filing_status": profile.get("filing_status", "single"),
                    "metrics": {
                        "current_tax_liability": calculation.total_tax,
                        "potential_savings": total_savings,
                        "effective_rate": calculation.effective_rate,
                        "federal_tax": calculation.federal_tax,
                        "state_tax": calculation.state_tax,
                    },
                    "recommendations": {
                        "total_count": len(strategies),
                        "immediate_actions": [
                            {"title": s.title, "savings": s.estimated_savings}
                            for s in strategies[:3]
                        ],
                    },
                }
                narrative = await generator.generate_executive_summary(
                    analysis=analysis_data, client_profile=client_profile
                )
                return narrative.content
            except Exception as e:
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "advisor_narrative",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "user receives template executive summary instead of AI narrative",
                    },
                )

        # --- Fallback: template summary ---
        top_strategies = strategies[:3]
        income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single").replace("_", " ").title()

        summary = f"""## Executive Tax Analysis Summary

**Client Profile:** {filing_status} filer with ${income:,.0f} annual income

**Current Tax Position:**
- Federal Tax: ${calculation.federal_tax:,.0f}
- State Tax: ${calculation.state_tax:,.0f}
- Total Tax Liability: ${calculation.total_tax:,.0f}
- Effective Tax Rate: {calculation.effective_rate:.1f}%
- Marginal Tax Rate: {calculation.marginal_rate}%

**Total Optimization Opportunity:** ${total_savings:,.0f}

**Top 3 Recommendations:**
"""
        for i, strategy in enumerate(top_strategies, 1):
            summary += f"\n{i}. **{strategy.title}** - Save ${strategy.estimated_savings:,.0f}\n   {strategy.summary}\n"

        summary += f"""
**Next Steps:**
1. Review the detailed recommendations below
2. Prioritize high-impact strategies ({len([s for s in strategies if s.priority == 'high'])} identified)
3. Consult with a CPA for implementation guidance
4. Take action before applicable deadlines
"""

        return summary


# Initialize the chat engine
chat_engine = IntelligentChatEngine()


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint with session persistence and AI provider status."""
    session_counts = chat_engine.get_session_count()

    # AI provider availability
    ai_status: Dict[str, Any] = {"available": False}
    try:
        from config.ai_providers import get_available_providers
        providers = get_available_providers()
        ai_status = {
            "available": len(providers) > 0,
            "providers": [p.value for p in providers],
        }
    except Exception:
        pass

    return {
        "status": "healthy",
        "service": "intelligent-advisor",
        "persistence_enabled": chat_engine._sqlite_persistence is not None or chat_engine._redis_persistence is not None,
        "sessions": session_counts,
        "ai": ai_status,
        "feature_flags": {
            "ai_chat": AI_CHAT_ENABLED,
            "ai_report_narratives": AI_REPORT_NARRATIVES_ENABLED,
            "ai_safety_checks": AI_SAFETY_CHECKS_ENABLED,
        },
    }


@router.get("/sessions/stats")
async def get_session_stats():
    """Get statistics about active sessions."""
    session_counts = chat_engine.get_session_count()
    return {
        "in_memory_sessions": session_counts["in_memory"],
        "database_sessions": session_counts["in_database"],
        "persistence_enabled": chat_engine._sqlite_persistence is not None,
        "persistence_type": "SQLite" if chat_engine._sqlite_persistence else "In-memory only"
    }


# =============================================================================
# PARSERS — moved to web/advisor/parsers.py
# Backward-compat imports at top of this file.
# =============================================================================



def _summarize_profile(profile: dict) -> str:
    """Create a human-readable summary of the current profile."""
    parts = []

    if profile.get("filing_status"):
        status_names = {
            "single": "Single",
            "married_joint": "Married Filing Jointly",
            "married_separate": "Married Filing Separately",
            "head_of_household": "Head of Household",
            "qualifying_widow": "Qualifying Surviving Spouse"
        }
        parts.append(status_names.get(profile["filing_status"], profile["filing_status"]))

    if profile.get("total_income"):
        parts.append(f"${profile['total_income']:,.0f} income")

    if profile.get("state"):
        parts.append(f"in {profile['state']}")

    if profile.get("dependents"):
        parts.append(f"{profile['dependents']} dependent(s)")

    if profile.get("is_self_employed"):
        parts.append("self-employed")

    return ", ".join(parts) if parts else "No information yet"


def _profile_to_return_data(profile: Dict, session_id: str = "") -> Dict[str, Any]:
    """Convert chatbot profile to the tax_return dict format expected by fraud/compliance/anomaly services."""
    income = profile.get("total_income", 0) or 0
    w2 = profile.get("w2_income", 0) or 0
    biz = profile.get("business_income", 0) or 0
    inv = profile.get("investment_income", 0) or 0
    rental = profile.get("rental_income", 0) or 0
    return {
        "return_id": session_id,
        "tax_year": 2025,
        "filing_status": (profile.get("filing_status") or "single").upper(),
        "taxpayer": {
            "name": profile.get("name", "Taxpayer"),
            "age": profile.get("age", 40),
            "state": profile.get("state", ""),
        },
        "income": {
            "total": income,
            "wages": w2 if w2 else max(0, income - biz - inv - rental),
            "business": biz,
            "investment": inv,
            "rental": rental,
            "capital_gains": profile.get("capital_gains", 0) or 0,
        },
        "deductions": {
            "mortgage_interest": profile.get("mortgage_interest", 0) or 0,
            "charitable": profile.get("charitable_donations", 0) or 0,
            "medical": profile.get("medical_expenses", 0) or 0,
            "state_local_taxes": profile.get("salt_deduction", 0) or 0,
        },
        "credits": {
            "child_tax_credit": profile.get("child_tax_credit", 0) or 0,
            "earned_income_credit": profile.get("eitc", 0) or 0,
        },
        "dependents": profile.get("dependents", 0) or 0,
        "retirement": {
            "contributions_401k": profile.get("retirement_401k", 0) or 0,
            "contributions_ira": profile.get("retirement_ira", 0) or 0,
            "hsa": profile.get("hsa_contributions", 0) or 0,
        },
        "withholding": {
            "federal": profile.get("federal_withholding", 0) or 0,
            "estimated_payments": profile.get("estimated_payments", 0) or 0,
        },
    }


# =============================================================================
# STRATEGY TIERING — Classify strategies as free or premium
# =============================================================================

PREMIUM_CATEGORIES = {
    "entity_restructuring", "roth_conversion", "estate_planning",
    "amt_optimization", "international_tax", "trust_planning",
    "cost_segregation", "opportunity_zones", "backdoor_roth",
    "mega_backdoor_roth", "charitable_remainder_trust",
}

SIMPLE_CATEGORIES = {
    "retirement_401k", "retirement_ira", "hsa", "charitable_giving",
    "standard_deduction", "education_credits", "child_tax_credit",
    "earned_income_credit", "student_loan_interest",
}

_tier_classification_semaphore = asyncio.Semaphore(3)


async def _classify_strategy_tier(
    strategy,
    profile: dict,
    safety_data: Optional[dict] = None,
) -> dict:
    """Classify a strategy as free or premium based on AI risk analysis.

    Returns dict with tier, risk_level, implementation_complexity.

    Classification rules (from design doc):
      FREE:  requires_professional_review=false AND audit_risk < 20 AND simple category
      PREMIUM: requires_professional_review=true OR audit_risk >= 20 OR complex category
    """
    tier = "free"
    risk_level = "low"
    complexity = "simple"

    # Rule 1: Category-based classification
    category = (strategy.category or "").lower().replace(" ", "_")
    if category in PREMIUM_CATEGORIES:
        tier = "premium"
        complexity = "complex"
    elif category not in SIMPLE_CATEGORIES:
        complexity = "moderate"

    # Rule 2: AI reasoning flag (only if not already premium from category)
    if AI_CHAT_ENABLED and tier != "premium":
        try:
            from services.ai.tax_reasoning_service import get_tax_reasoning_service
            reasoning = get_tax_reasoning_service()
            async with _tier_classification_semaphore:
                result = await reasoning.analyze(
                    problem=f"Does '{strategy.title}' require professional CPA review for this taxpayer?",
                    context=_summarize_profile(profile),
                )
            if result.requires_professional_review:
                tier = "premium"
            if result.confidence and result.confidence < 0.6:
                risk_level = "medium"
        except Exception:
            pass

    # Rule 3: Audit risk from safety data
    if safety_data:
        audit_risk = safety_data.get("audit_risk", {})
        risk_score = audit_risk.get("risk_score", 0)
        if risk_score >= 20:
            tier = "premium"
        if risk_score >= 50:
            risk_level = "high"
        elif risk_score >= 20:
            risk_level = "medium"

    # Rule 4: High savings = likely complex
    if strategy.estimated_savings > 5000 and complexity == "simple":
        complexity = "moderate"

    # Rule 5: Entity changes, conversions, timing-dependent
    title_lower = (strategy.title or "").lower()
    if any(kw in title_lower for kw in ["convert", "restructure", "entity", "roth conversion", "backdoor"]):
        tier = "premium"
        complexity = "complex"

    return {"tier": tier, "risk_level": risk_level, "implementation_complexity": complexity}


def _build_safety_summary(safety_checks: Optional[dict]) -> Optional[dict]:
    """Build user-facing compliance summary from safety check data."""
    if not safety_checks:
        return None

    checks = []
    total = 0
    passed = 0

    fraud = safety_checks.get("fraud")
    if fraud:
        total += 1
        is_clear = fraud.get("risk_level", "").upper() in ("MINIMAL", "LOW", "NONE")
        passed += 1 if is_clear else 0
        checks.append({"name": "Fraud Detection", "status": "pass" if is_clear else "review", "detail": "Clear" if is_clear else "Review recommended"})

    identity = safety_checks.get("identity_theft")
    if identity:
        total += 1
        is_clear = not identity.get("indicators_found", True)
        passed += 1 if is_clear else 0
        checks.append({"name": "Identity Verification", "status": "pass" if is_clear else "review", "detail": "Pass" if is_clear else "Review recommended"})

    compliance = safety_checks.get("compliance")
    if compliance:
        total += 1
        is_ok = compliance.get("risk_level", "").upper() in ("LOW", "NONE", "MINIMAL")
        passed += 1 if is_ok else 0
        checks.append({"name": "Tax Compliance", "status": "pass" if is_ok else "review", "detail": "Compliant" if is_ok else "Review recommended"})

    eitc = safety_checks.get("eitc_compliance")
    if eitc is not None:
        total += 1
        if isinstance(eitc, list):
            all_met = all(item.get("met", True) for item in eitc) if eitc else True
            is_ok = all_met
        elif isinstance(eitc, dict):
            is_ok = eitc.get("compliant", False)
        else:
            is_ok = False
        passed += 1 if is_ok else 0
        checks.append({"name": "EITC Due Diligence", "status": "pass" if is_ok else "review", "detail": "Compliant" if is_ok else "Review recommended"})

    c230 = safety_checks.get("circular_230")
    if c230:
        total += 1
        is_ok = c230.get("compliant", False)
        passed += 1 if is_ok else 0
        checks.append({"name": "Circular 230", "status": "pass" if is_ok else "review", "detail": "Compliant" if is_ok else "Review recommended"})

    audit = safety_checks.get("audit_risk")
    if audit:
        total += 1
        risk = (audit.get("overall_risk") or "low").lower()
        is_ok = risk == "low"
        passed += 1 if is_ok else 0
        checks.append({"name": "Audit Risk Assessment", "status": "pass" if is_ok else "review", "detail": f"{'Low' if is_ok else risk.title()} risk (score: {audit.get('risk_score', 0)})"})

    data_errors = safety_checks.get("data_errors")
    if data_errors is not None:
        total += 1
        if isinstance(data_errors, list):
            is_ok = len(data_errors) == 0
        elif isinstance(data_errors, dict):
            is_ok = not data_errors.get("errors_found", True)
        else:
            is_ok = False
        passed += 1 if is_ok else 0
        checks.append({"name": "Data Validation", "status": "pass" if is_ok else "review", "detail": "Pass" if is_ok else "Errors detected"})

    if total == 0:
        return None

    needs_review = total - passed
    return {
        "total_checks": total,
        "passed": passed,
        "needs_review": needs_review,
        "checks": checks,
        "overall_status": "clear" if needs_review == 0 else "review_recommended",
    }


async def _record_ai_usage(service_name: str, method_name: str, duration_ms: float = 0, success: bool = True):
    """Record AI service usage for metrics dashboard (non-blocking)."""
    if not AI_CHAT_ENABLED:
        return
    try:
        from services.ai.metrics_service import get_ai_metrics_service
        from config.ai_providers import AIProvider
        metrics = get_ai_metrics_service()
        metrics.record_usage(
            provider=AIProvider.ANTHROPIC,
            model=f"{service_name}.{method_name}",
            input_tokens=0,
            output_tokens=0,
            latency_ms=int(duration_ms),
            cost=0.0,
            success=success,
        )
    except Exception:
        pass  # Metrics recording is never critical


async def _run_safety_checks(session_id: str, profile: Dict, calculation) -> Dict[str, Any]:
    """Run fraud, compliance, and anomaly checks. Returns results dict and persists to session."""
    if not AI_SAFETY_CHECKS_ENABLED:
        return {}

    return_data = _profile_to_return_data(profile, session_id)
    results: Dict[str, Any] = {}

    # 1. Fraud detection (async via unified AI service)
    try:
        from security.fraud_detector import get_fraud_detector
        fraud = await get_fraud_detector().detect_fraud(return_data)
        results["fraud"] = {
            "risk_level": fraud.overall_risk_level.value,
            "risk_score": fraud.risk_score,
            "indicators": len(fraud.indicators),
            "irs_referral": fraud.irs_referral_recommended,
        }
    except Exception as e:
        logger.warning(f"Fraud check failed (non-blocking): {e}")

    # 1b. Identity theft screening (async via unified AI service)
    try:
        from security.fraud_detector import get_fraud_detector
        identity_result = await get_fraud_detector().check_identity_theft_indicators(return_data)
        results["identity_theft"] = identity_result
    except Exception as e:
        logger.warning(f"Identity theft check failed (non-blocking): {e}")

    # 1c. Refund fraud detection (async via unified AI service)
    try:
        from security.fraud_detector import get_fraud_detector
        refund_result = await get_fraud_detector().analyze_refund_risk(return_data)
        results["refund_risk"] = refund_result
    except Exception as e:
        logger.warning(f"Refund risk check failed (non-blocking): {e}")

    # 2. Compliance review (async via unified AI service)
    try:
        from security.ai_compliance_reviewer import get_compliance_reviewer as get_compliance
        compliance = await get_compliance().review_compliance(return_data)
        results["compliance"] = {
            "risk_level": compliance.overall_risk_level.value,
            "issues": len(compliance.issues),
            "circular_230": compliance.circular_230_compliant,
        }
    except Exception as e:
        logger.warning(f"Compliance check failed (non-blocking): {e}")

    # 2b. EITC due diligence (Form 8867) — if dependents present
    if (profile.get("dependents", 0) or 0) > 0:
        try:
            from security.ai_compliance_reviewer import get_compliance_reviewer as get_compliance
            eitc_result = await get_compliance().check_eitc_due_diligence(return_data)
            results["eitc_compliance"] = [
                {"requirement": r.requirement if hasattr(r, 'requirement') else str(r),
                 "met": r.met if hasattr(r, 'met') else True}
                for r in (eitc_result if isinstance(eitc_result, list) else [eitc_result])
            ]
        except Exception as e:
            logger.warning(f"EITC due diligence check failed (non-blocking): {e}")

    # 2c. Circular 230 compliance verification
    try:
        from security.ai_compliance_reviewer import get_compliance_reviewer as get_compliance
        circ230_result = await get_compliance().check_circular_230_compliance(
            {"ptin": "P00000000", "firm": "AI Advisory"},
        )
        results["circular_230"] = circ230_result
    except Exception as e:
        logger.warning(f"Circular 230 check failed (non-blocking): {e}")

    # 3. Anomaly detection (async service)
    try:
        from services.ai.anomaly_detector import get_anomaly_detector
        anomaly = await get_anomaly_detector().analyze_return(return_data)
        results["anomaly"] = {
            "risk_score": anomaly.overall_risk_score,
            "audit_risk": anomaly.audit_risk_level,
            "anomalies": anomaly.total_anomalies,
        }
    except Exception as e:
        logger.warning(f"Anomaly check failed (non-blocking): {e}")

    # 3b. Audit risk scoring
    try:
        from services.ai.anomaly_detector import get_anomaly_detector
        audit_assessment = await get_anomaly_detector().assess_audit_risk(return_data)
        results["audit_risk"] = {
            "overall_risk": audit_assessment.overall_risk,
            "risk_score": audit_assessment.risk_score,
            "primary_triggers": audit_assessment.primary_triggers,
            "recommendations": audit_assessment.recommendations,
        }
    except Exception as e:
        logger.warning(f"Audit risk scoring failed (non-blocking): {e}")

    # 3c. Data entry error validation
    try:
        from services.ai.anomaly_detector import get_anomaly_detector
        data_errors = await get_anomaly_detector().check_data_entry_errors(return_data)
        results["data_errors"] = [
            {
                "field": err.field,
                "severity": err.severity.value if hasattr(err.severity, 'value') else str(err.severity),
                "description": err.description,
                "recommendation": err.recommendation,
            }
            for err in data_errors
        ]
    except Exception as e:
        logger.warning(f"Data entry error check failed (non-blocking): {e}")

    # Persist results into the session
    try:
        session = await chat_engine.get_or_create_session(session_id)
        session["safety_checks"] = results
        await chat_engine.update_session(session_id, {"safety_checks": results})
        logger.info(f"Safety checks complete for {session_id}: {list(results.keys())}")
    except Exception:
        pass

    # Emit real-time event for CPA panel
    try:
        from realtime.event_publisher import event_publisher
        from realtime.events import RealtimeEvent, EventType
        await event_publisher.publish(RealtimeEvent(
            event_type=EventType.RETURN_UPDATED,
            session_id=session_id,
            data={"type": "safety_checks_complete", "results": results},
        ))
    except Exception:
        pass

    asyncio.create_task(_record_ai_usage("SafetyChecks", "background_full_suite"))

    return results


def _get_suggested_questions(profile: dict) -> List[str]:
    """
    Detect patterns in profile and suggest proactive questions (GAP #4).
    Similar to agent's _detect_patterns_and_suggest() but for rule-based chatbot.
    Returns up to 2 suggested questions.
    """
    suggestions = []

    # Has W-2 income but no withholding info
    if profile.get("w2_income") or profile.get("total_income"):
        if not profile.get("federal_withholding"):
            suggestions.append("Do you know your total federal tax withholding from your W-2 (Box 2)?")

    # Has business income but no expenses
    if profile.get("business_income") and not profile.get("business_expenses"):
        suggestions.append("What business expenses did you have? (Mileage, supplies, home office, etc.)")

    # Has children but no education expenses asked
    if profile.get("dependents") and not profile.get("_asked_education"):
        suggestions.append("Are any of your dependents in college? You may qualify for education credits worth up to $2,500.")

    # Has rental income but no rental expenses
    if profile.get("rental_income") and not profile.get("rental_expenses"):
        suggestions.append("Do you have rental property expenses (insurance, repairs, depreciation)?")

    # High income but no retirement contributions
    total_income = profile.get("total_income", 0) or 0
    if total_income > 100000 and not profile.get("retirement_401k") and not profile.get("_asked_retirement"):
        suggestions.append("Are you contributing to a 401(k) or IRA? This could save significant taxes at your income level.")

    # Self-employed but no HSA
    if profile.get("business_income") and not profile.get("hsa_contributions") and not profile.get("_asked_hsa"):
        suggestions.append("Do you have a High Deductible Health Plan? HSA contributions are triple tax-advantaged.")

    return suggestions[:2]


def _compute_missing_fields(profile: dict) -> tuple:
    """Return (missing_field_labels, savings_hint) for progress display."""
    FIELDS = [
        ("filing_status", "Filing status", None),
        ("total_income", "Income", None),
        ("state", "State", None),
        ("dependents", "Dependents", None),
        ("age", "Age", "_asked_age"),
        ("retirement_401k", "Retirement contributions", "_asked_retirement"),
        ("mortgage_interest", "Mortgage/deductions", "_asked_deductions"),
        ("investment_income", "Investment income", "_asked_investments"),
        ("hsa_contributions", "HSA contributions", "_asked_hsa"),
        ("charitable_donations", "Charitable giving", "_asked_charitable"),
    ]
    HINTS = {
        "retirement_401k": "Retirement info could unlock ~$2,000+ in savings",
        "mortgage_interest": "Deduction details could reveal itemization opportunities",
        "hsa_contributions": "HSA provides triple tax benefits \u2014 could save $1,000+",
        "investment_income": "Investment details help optimize capital gains strategy",
    }

    missing = []
    hint = None
    for field, label, asked_flag in FIELDS:
        if not profile.get(field) and (not asked_flag or not profile.get(asked_flag)):
            missing.append(label)
            if not hint and field in HINTS:
                hint = HINTS[field]

    return missing[:5], hint


def _score_next_questions(profile: dict, conversation: list = None) -> tuple:
    """Score Phase 2 questions by relevance to user's situation. Returns (question, actions) or (None, None)."""
    total_income = float(profile.get("total_income", 0) or 0)
    is_se = profile.get("is_self_employed") or profile.get("income_type") in ("self_employed", "business_owner")

    # Conversation context keywords for boosting
    context_text = ""
    if conversation:
        context_text = " ".join(m.get("content", "") for m in conversation[-5:] if m.get("role") == "user").lower()

    # Each candidate: (score, question_text, quick_actions)
    candidates = []

    # Business deep-dive (high priority if self-employed)
    if is_se and not profile.get("business_income") and not profile.get("_asked_business"):
        score = 80
        if any(kw in context_text for kw in ["freelance", "1099", "side", "business", "contractor", "gig"]):
            score += 30
        candidates.append((score,
            "What's your approximate net business income (after expenses)?",
            [
                {"label": "Under $50K", "value": "biz_under_50k"},
                {"label": "$50K - $100K", "value": "biz_50_100k"},
                {"label": "$100K - $200K", "value": "biz_100_200k"},
                {"label": "Over $200K", "value": "biz_over_200k"},
                {"label": "Skip", "value": "skip_business"}
            ]
        ))

    # Home office (if self-employed and business income known)
    if is_se and profile.get("business_income") and not profile.get("home_office_sqft") and not profile.get("_asked_home_office"):
        score = 70
        if any(kw in context_text for kw in ["home", "remote", "office", "wfh"]):
            score += 25
        candidates.append((score,
            "Do you use part of your home exclusively for business? If so, approximately how many square feet?",
            [
                {"label": "Yes, I have a home office", "value": "has_home_office"},
                {"label": "No home office", "value": "no_home_office"},
                {"label": "Skip", "value": "skip_home_office"}
            ]
        ))

    # Retirement (universally valuable)
    if not profile.get("retirement_401k") and not profile.get("retirement_ira") and not profile.get("_asked_retirement"):
        score = 60
        if total_income > 100000:
            score += 15
        if any(kw in context_text for kw in ["401k", "ira", "retire", "saving", "roth"]):
            score += 25
        candidates.append((score,
            "Are you contributing to any retirement accounts? This can significantly reduce your taxes.",
            [
                {"label": "401(k) / 403(b)", "value": "has_401k"},
                {"label": "IRA (Traditional or Roth)", "value": "has_ira"},
                {"label": "Both 401(k) and IRA", "value": "has_both_retirement"},
                {"label": "No retirement contributions", "value": "no_retirement"},
                {"label": "Skip", "value": "skip_retirement"}
            ]
        ))

    # Investments (high income = more relevant)
    if not profile.get("investment_income") and not profile.get("capital_gains_long") and not profile.get("_asked_investments"):
        score = 40
        if total_income > 200000:
            score += 25  # NIIT threshold
        if any(kw in context_text for kw in ["stock", "invest", "crypto", "dividend", "capital", "trading"]):
            score += 30
        candidates.append((score,
            "Do you have any investment income? This includes stock sales, dividends, interest, or cryptocurrency.",
            [
                {"label": "Yes, I have investments", "value": "has_investments"},
                {"label": "No investment income", "value": "no_investments"},
                {"label": "Skip", "value": "skip_investments"}
            ]
        ))

    # Deductions (mortgage, charitable)
    if not profile.get("mortgage_interest") and not profile.get("_asked_deductions"):
        score = 50
        if total_income > 100000:
            score += 10
        if any(kw in context_text for kw in ["mortgage", "house", "home", "bought", "deduct", "charit", "donat"]):
            score += 25
        candidates.append((score,
            "Let's check your deductions. Do you have any of these? Select all that apply.",
            [
                {"label": "Mortgage interest", "value": "has_mortgage"},
                {"label": "Charitable donations", "value": "has_charitable"},
                {"label": "High medical expenses", "value": "has_medical"},
                {"label": "None of these / Standard deduction", "value": "no_itemized_deductions"},
                {"label": "Skip", "value": "skip_deductions"}
            ]
        ))

    # HSA
    if not profile.get("hsa_contributions") and not profile.get("_asked_hsa"):
        if profile.get("retirement_401k") or profile.get("retirement_ira"):
            score = 45
            if any(kw in context_text for kw in ["hsa", "health", "medical", "insurance"]):
                score += 25
            candidates.append((score,
                "Do you have a Health Savings Account (HSA)? Contributions are triple tax-advantaged.",
                [
                    {"label": "Yes, I have an HSA", "value": "has_hsa"},
                    {"label": "No HSA", "value": "no_hsa"},
                    {"label": "Skip", "value": "skip_hsa"}
                ]
            ))

    # Age
    if not profile.get("age") and not profile.get("_asked_age"):
        score = 35
        if any(kw in context_text for kw in ["retire", "senior", "65", "older", "age"]):
            score += 25
        candidates.append((score,
            "What is your age? This helps determine your standard deduction and eligibility for certain credits.",
            [
                {"label": "Under 50", "value": "age_under_50"},
                {"label": "50-64", "value": "age_50_64"},
                {"label": "65 or older", "value": "age_65_plus"},
                {"label": "Skip", "value": "skip_age"}
            ]
        ))

    # K-1 income
    if not profile.get("k1_ordinary_income") and not profile.get("_asked_k1"):
        score = 25
        if any(kw in context_text for kw in ["k-1", "k1", "partner", "s-corp", "trust"]):
            score += 35
        candidates.append((score,
            "Do you receive any K-1 income from partnerships, S-corporations, or trusts?",
            [
                {"label": "Yes, I have K-1 income", "value": "has_k1_income"},
                {"label": "No K-1 income", "value": "no_k1_income"},
                {"label": "Skip", "value": "skip_k1"}
            ]
        ))

    # Rental income
    if not profile.get("rental_income") and not profile.get("_asked_rental"):
        score = 30
        if any(kw in context_text for kw in ["rent", "landlord", "property", "tenant"]):
            score += 30
        candidates.append((score,
            "Do you own any rental properties?",
            [
                {"label": "Yes, I have rental income", "value": "has_rental"},
                {"label": "No rental properties", "value": "no_rental"},
                {"label": "Skip", "value": "skip_rental"}
            ]
        ))

    # Student loans
    if not profile.get("student_loan_interest") and not profile.get("_asked_student_loans"):
        if total_income < 180000:
            score = 20
            if any(kw in context_text for kw in ["student", "loan", "college", "university"]):
                score += 30
            candidates.append((score,
                "Did you pay any student loan interest this year? (Up to $2,500 may be deductible)",
                [
                    {"label": "Yes", "value": "has_student_loans"},
                    {"label": "No student loans", "value": "no_student_loans"},
                    {"label": "Skip", "value": "skip_student_loans"}
                ]
            ))

    # Estimated payments
    if total_income > 100000 and not profile.get("estimated_payments") and not profile.get("_asked_estimated"):
        score = 30
        if any(kw in context_text for kw in ["estimated", "quarterly", "payment"]):
            score += 25
        candidates.append((score,
            "Have you made any estimated tax payments for this year?",
            [
                {"label": "Yes", "value": "has_estimated_payments"},
                {"label": "No", "value": "no_estimated_payments"},
                {"label": "Skip", "value": "skip_estimated"}
            ]
        ))

    if not candidates:
        return (None, None)
    candidates.sort(key=lambda x: -x[0])
    return (candidates[0][1], candidates[0][2])


def _get_dynamic_next_question(profile: dict, last_extracted: dict = None, session: dict = None) -> tuple:
    """
    Dynamically determine the next question based on what's missing.
    Returns (question_text, quick_actions)

    Three phases:
      Phase 1 - Basics: filing status, income, state, dependents, income type
      Phase 2 - Deep dive: deductions, retirement, investments, age, etc.
      Phase 3 - Done: return (None, None) to trigger calculation
    """
    # =========================================================================
    # PHASE 1: Core basics (must have before anything else)
    # =========================================================================
    if not profile.get("filing_status"):
        return (
            "What's your filing status for this tax year?",
            [
                {"label": "Single", "value": "single"},
                {"label": "Married Filing Jointly", "value": "married_joint"},
                {"label": "Head of Household", "value": "head_of_household"},
                {"label": "Married Filing Separately", "value": "married_separate"}
            ]
        )

    if not profile.get("total_income"):
        return (
            "What's your approximate total annual income? Include all sources - wages, business, investments.",
            [
                {"label": "Under $50K", "value": "income_under_50k"},
                {"label": "$50K - $100K", "value": "income_50_100k"},
                {"label": "$100K - $200K", "value": "income_100_200k"},
                {"label": "Over $200K", "value": "income_over_200k"}
            ]
        )

    if not profile.get("state"):
        return (
            "Which state do you live in? This affects your state tax calculation.",
            [
                {"label": "California", "value": "CA"},
                {"label": "Texas", "value": "TX"},
                {"label": "New York", "value": "NY"},
                {"label": "Florida", "value": "FL"}
            ]
        )

    if profile.get("dependents") is None:
        return (
            "Do you have any dependents (children under 17, qualifying relatives)?",
            [
                {"label": "No dependents", "value": "0_dependents"},
                {"label": "1 dependent", "value": "1_dependent"},
                {"label": "2 dependents", "value": "2_dependents"},
                {"label": "3+ dependents", "value": "3plus_dependents"}
            ]
        )

    if not profile.get("income_type") and not profile.get("is_self_employed"):
        return (
            "What's your primary source of income?",
            [
                {"label": "W-2 Employee", "value": "w2_employee"},
                {"label": "Self-Employed", "value": "self_employed"},
                {"label": "Business Owner", "value": "business_owner"},
                {"label": "Retired", "value": "retired"}
            ]
        )

    # =========================================================================
    # PHASE 2: Deep dive - context-aware follow-ups for a complete profile
    # User can skip any question with "Skip" button to move forward
    # =========================================================================

    # If user has already opted to skip deep dive, go straight to calculation
    if profile.get("_skip_deep_dive"):
        return (None, None)

    # AI-driven adaptive question ordering (scores all Phase 2 questions by relevance)
    if AI_ADAPTIVE_QUESTIONS_ENABLED:
        conversation = session.get("conversation", []) if isinstance(session, dict) else []
        scored_result = _score_next_questions(profile, conversation)
        if scored_result[0]:
            return scored_result
    # Fall through to existing rigid ordering as fallback

    total_income = profile.get("total_income", 0) or 0

    # --- Age (affects standard deduction for 65+) ---
    if not profile.get("age") and not profile.get("_asked_age"):
        return (
            "What is your age? This helps determine your standard deduction and eligibility for certain credits.",
            [
                {"label": "Under 50", "value": "age_under_50"},
                {"label": "50-64", "value": "age_50_64"},
                {"label": "65 or older", "value": "age_65_plus"},
                {"label": "Skip", "value": "skip_age"}
            ]
        )

    # --- Self-employment / Business deep dive ---
    if profile.get("is_self_employed") or profile.get("income_type") in ("self_employed", "business_owner"):
        if not profile.get("business_income") and not profile.get("_asked_business"):
            return (
                "What's your approximate net business income (after expenses)?",
                [
                    {"label": "Under $50K", "value": "biz_under_50k"},
                    {"label": "$50K - $100K", "value": "biz_50_100k"},
                    {"label": "$100K - $200K", "value": "biz_100_200k"},
                    {"label": "Over $200K", "value": "biz_over_200k"},
                    {"label": "Skip", "value": "skip_business"}
                ]
            )
        if not profile.get("home_office_sqft") and not profile.get("_asked_home_office"):
            return (
                "Do you use part of your home exclusively for business? If so, approximately how many square feet?",
                [
                    {"label": "Yes, I have a home office", "value": "has_home_office"},
                    {"label": "No home office", "value": "no_home_office"},
                    {"label": "Skip", "value": "skip_home_office"}
                ]
            )

    # --- K-1 / Partnership / S-Corp income ---
    if not profile.get("k1_ordinary_income") and not profile.get("_asked_k1"):
        return (
            "Do you receive any K-1 income from partnerships, S-corporations, or trusts?",
            [
                {"label": "Yes, I have K-1 income", "value": "has_k1_income"},
                {"label": "No K-1 income", "value": "no_k1_income"},
                {"label": "Skip", "value": "skip_k1"}
            ]
        )

    # --- Investment income (dividends, capital gains) ---
    if not profile.get("investment_income") and not profile.get("capital_gains_long") and not profile.get("_asked_investments"):
        return (
            "Do you have any investment income? This includes stock sales, dividends, interest, or cryptocurrency.",
            [
                {"label": "Yes, I have investments", "value": "has_investments"},
                {"label": "No investment income", "value": "no_investments"},
                {"label": "Skip", "value": "skip_investments"}
            ]
        )

    # --- Rental income ---
    if not profile.get("rental_income") and not profile.get("_asked_rental"):
        return (
            "Do you own any rental properties?",
            [
                {"label": "Yes, I have rental income", "value": "has_rental"},
                {"label": "No rental properties", "value": "no_rental"},
                {"label": "Skip", "value": "skip_rental"}
            ]
        )

    # --- Retirement contributions (401k, IRA, HSA) ---
    if not profile.get("retirement_401k") and not profile.get("retirement_ira") and not profile.get("_asked_retirement"):
        return (
            "Are you contributing to any retirement accounts? This can significantly reduce your taxes.",
            [
                {"label": "401(k) / 403(b)", "value": "has_401k"},
                {"label": "IRA (Traditional or Roth)", "value": "has_ira"},
                {"label": "Both 401(k) and IRA", "value": "has_both_retirement"},
                {"label": "No retirement contributions", "value": "no_retirement"},
                {"label": "Skip", "value": "skip_retirement"}
            ]
        )

    # --- HSA contributions ---
    if not profile.get("hsa_contributions") and not profile.get("_asked_hsa"):
        if profile.get("retirement_401k") or profile.get("retirement_ira"):
            # Already asked about retirement, now ask HSA separately
            return (
                "Do you have a Health Savings Account (HSA)? Contributions are triple tax-advantaged.",
                [
                    {"label": "Yes, I have an HSA", "value": "has_hsa"},
                    {"label": "No HSA", "value": "no_hsa"},
                    {"label": "Skip", "value": "skip_hsa"}
                ]
            )

    # --- Major deductions (mortgage, charitable, medical) ---
    if not profile.get("mortgage_interest") and not profile.get("_asked_deductions"):
        return (
            "Let's check your deductions. Do you have any of these? Select all that apply.",
            [
                {"label": "Mortgage interest", "value": "has_mortgage"},
                {"label": "Charitable donations", "value": "has_charitable"},
                {"label": "High medical expenses", "value": "has_medical"},
                {"label": "None of these / Standard deduction", "value": "no_itemized_deductions"},
                {"label": "Skip", "value": "skip_deductions"}
            ]
        )

    # --- Mortgage follow-up ---
    if profile.get("_has_mortgage") and not profile.get("mortgage_interest") and not profile.get("_asked_mortgage_amount"):
        return (
            "Approximately how much mortgage interest did you pay this year? (Check your Form 1098)",
            [
                {"label": "Under $5,000", "value": "mortgage_under_5k"},
                {"label": "$5,000 - $15,000", "value": "mortgage_5_15k"},
                {"label": "$15,000 - $30,000", "value": "mortgage_15_30k"},
                {"label": "Over $30,000", "value": "mortgage_over_30k"},
                {"label": "Skip", "value": "skip_mortgage_amount"}
            ]
        )

    # --- Charitable follow-up ---
    if profile.get("_has_charitable") and not profile.get("charitable_donations") and not profile.get("_asked_charitable_amount"):
        return (
            "Approximately how much did you donate to charity this year?",
            [
                {"label": "Under $1,000", "value": "charity_under_1k"},
                {"label": "$1,000 - $5,000", "value": "charity_1_5k"},
                {"label": "$5,000 - $20,000", "value": "charity_5_20k"},
                {"label": "Over $20,000", "value": "charity_over_20k"},
                {"label": "Skip", "value": "skip_charitable_amount"}
            ]
        )

    # --- Estimated tax payments ---
    if total_income > 100000 and not profile.get("estimated_payments") and not profile.get("_asked_estimated"):
        return (
            "Have you made any estimated tax payments for this year?",
            [
                {"label": "Yes", "value": "has_estimated_payments"},
                {"label": "No", "value": "no_estimated_payments"},
                {"label": "Skip", "value": "skip_estimated"}
            ]
        )

    # --- Student loan interest ---
    if not profile.get("student_loan_interest") and not profile.get("_asked_student_loans"):
        if total_income < 180000:  # Phase-out threshold
            return (
                "Did you pay any student loan interest this year? (Up to $2,500 may be deductible)",
                [
                    {"label": "Yes", "value": "has_student_loans"},
                    {"label": "No student loans", "value": "no_student_loans"},
                    {"label": "Skip", "value": "skip_student_loans"}
                ]
            )

    # =========================================================================
    # PHASE 3: All deep-dive questions answered or skipped - ready for analysis
    # =========================================================================
    return (None, None)


# In-memory rate limiter — session + IP based
_chat_rate_limits: dict = {}  # session_id -> list of timestamps
_CHAT_RATE_LIMIT = 30  # max requests per window per session
_CHAT_RATE_WINDOW = 60  # seconds


def _check_chat_rate_limit(session_id: str, client_ip: str = None) -> bool:
    """Return True if request is allowed, False if rate limited.

    Checks both per-session and per-IP limits to prevent
    session-rotation bypass attacks.
    """
    now = time.time()
    window_start = now - _CHAT_RATE_WINDOW

    # Session-based check
    if session_id not in _chat_rate_limits:
        _chat_rate_limits[session_id] = []
    _chat_rate_limits[session_id] = [
        t for t in _chat_rate_limits[session_id] if t > window_start
    ]
    if len(_chat_rate_limits[session_id]) >= _CHAT_RATE_LIMIT:
        return False

    # IP-based check (prevents session rotation)
    if client_ip:
        if client_ip not in _ip_rate_limits:
            _ip_rate_limits[client_ip] = []
        _ip_rate_limits[client_ip] = [
            t for t in _ip_rate_limits[client_ip] if t > window_start
        ]
        if len(_ip_rate_limits[client_ip]) >= _IP_RATE_LIMIT:
            return False
        _ip_rate_limits[client_ip].append(now)

    _chat_rate_limits[session_id].append(now)

    # Cleanup stale entries periodically
    if len(_chat_rate_limits) > 1000:
        stale = [k for k, v in _chat_rate_limits.items() if not v or v[-1] < window_start]
        for k in stale:
            del _chat_rate_limits[k]
    if len(_ip_rate_limits) > 1000:
        stale = [k for k, v in _ip_rate_limits.items() if not v or v[-1] < window_start]
        for k in stale:
            del _ip_rate_limits[k]

    return True


@router.post("/chat", response_model=ChatResponse)
async def intelligent_chat(request: ChatRequest, http_request: FastAPIRequest = None, _session: str = Depends(verify_session_token)):
    """
    Main intelligent chat endpoint with dynamic flow handling.

    Features:
    - Intelligent responses based on context
    - Real-time tax calculations
    - Personalized strategy recommendations
    - Dynamic follow-up questions
    - Checkpoint system for undo/corrections
    - Adaptive conversation flow
    - Comprehensive error handling and recovery
    """
    # Initialize session_id early for error handling
    session_id = request.session_id or f"auto-{datetime.now().timestamp()}"
    request.session_id = session_id

    # Rate limiting (session + IP)
    client_ip = _get_client_ip(http_request) if http_request else None
    if not _check_chat_rate_limit(session_id, client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please wait a moment before sending more messages."}
        )

    try:
        # Get or create session
        session = await chat_engine.get_or_create_session(session_id)
        _session_was_renewed = session.pop("_renewed", False)
        profile = session["profile"]

        # Populate CPA/firm context from request if not already set.
        # Only cpa_id/cpa_slug are trusted from client context (used for branding).
        # firm_id is derived server-side from the CPA profile, never from raw client input.
        ctx = request.context or {}
        if not session.get("cpa_id"):
            cpa_id_from_ctx = ctx.get("cpa_id") or ctx.get("cpa_slug")
            if cpa_id_from_ctx:
                # Validate the CPA exists by checking the lead magnet service
                try:
                    from cpa_panel.services.lead_magnet_service import get_lead_magnet_service
                    lm_svc = get_lead_magnet_service()
                    cpa_profile = lm_svc.get_cpa_profile(cpa_id_from_ctx)
                    if cpa_profile:
                        session["cpa_id"] = cpa_profile.cpa_id
                    else:
                        logger.warning(f"Unknown cpa_id in context: {cpa_id_from_ctx}")
                except Exception:
                    # If validation fails, still set it (graceful degradation)
                    session["cpa_id"] = cpa_id_from_ctx
        # Derive tenant_id from validated cpa_id (not from client-supplied firm_id)
        if not session.get("tenant_id") and session.get("cpa_id"):
            session["tenant_id"] = session.get("cpa_id")
        if ctx.get("review_mode") is not None:
            session["review_mode"] = bool(ctx["review_mode"])
    except Exception as e:
        logger.error(f"Session initialization error: {e}")
        return ChatResponse(
            session_id=session_id,
            response="I'm having trouble accessing your session. Let me start fresh for you.",
            response_type="session_error",
            quick_actions=[
                {"label": "Start Fresh", "value": "start_fresh"},
                {"label": "Try Again", "value": "retry"}
            ],
            metadata={"_source": "template"},
        )

    # Compute missing fields for progress transparency
    missing_fields, completion_hint = _compute_missing_fields(profile)

    # Sanitize and validate message
    msg_original = (request.message or "").strip()
    # Remove potential injection attempts (null bytes, carriage returns)
    msg_original = msg_original.replace('\x00', '').replace('\r', '')
    # Remove potential XSS attempts
    msg_original = msg_original.replace('<script', '').replace('javascript:', '')
    # Limit message length
    if len(msg_original) > 5000:
        msg_original = msg_original[:5000]

    # --- InputGuard: Block prompt injection + sanitize PII before AI ---
    if _INPUT_GUARD_AVAILABLE:
        guard_result, msg_original = _input_guard.check_and_sanitize(msg_original)
        if not guard_result.is_safe:
            logger.warning(
                f"[InputGuard] Blocked message in session {session_id}: "
                f"type={guard_result.violation_type}"
            )
            return ChatResponse(
                session_id=request.session_id,
                message="I can only help with tax-related questions. Could you please rephrase your question about your tax situation?",
                quick_actions=[
                    {"label": "What deductions can I claim?", "value": "ask_deductions"},
                    {"label": "Help me file my taxes", "value": "start_filing"},
                ],
                profile=profile,
            )

    msg_lower = msg_original.lower()

    # Journey event: notify that a message was sent (for input guard / orchestrator)
    if _JOURNEY_EVENTS_AVAILABLE and msg_original:
        try:
            bus = get_event_bus()
            if bus:
                bus.emit(AdvisorMessageSent(
                    session_id=session_id,
                    tenant_id=session.get("tenant_id", "default"),
                    user_id=session.get("user_id", session_id),
                    message_text=msg_original,
                ))
        except Exception:
            pass  # Never block chat on event emission failure

    # =========================================================================
    # GRACEFUL EDGE CASE HANDLING - Handle problematic inputs early
    # =========================================================================

    # Handle empty or very short messages
    if not msg_original or len(msg_original) < 2:
        next_q, next_actions = _get_dynamic_next_question(profile)
        return ChatResponse(
            session_id=request.session_id,
            response=next_q or "I'm here to help with your taxes! What would you like to know?",
            response_type="prompt",
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=next_actions or [
                {"label": "Start Tax Analysis", "value": "start_analysis"},
                {"label": "Upload Documents", "value": "upload_docs"}
            ],
            metadata={"_source": "template"},
        )

    # Handle greetings
    greeting_patterns = [
        r'^(hi|hello|hey|howdy|greetings|good\s*(morning|afternoon|evening))[\s!.]*$',
        r'^(what\'?s\s*up|sup|yo)[\s!.]*$'
    ]
    import re
    is_greeting = any(re.match(p, msg_lower) for p in greeting_patterns)
    if is_greeting:
        greeting_response = """Hello! I'm your AI tax advisor.

⚠️ **Important:** I provide general tax information only—not professional tax advice. For your specific situation, consult a licensed CPA or EA.

I can help you:
• **Estimate your taxes** for 2025
• **Find tax savings** opportunities
• **Generate professional reports**

To get started, what's your filing status?"""

        return ChatResponse(
            session_id=request.session_id,
            response=greeting_response,
            response_type="greeting",
            disclaimer=STANDARD_DISCLAIMER,
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=[
                {"label": "Single", "value": "filing_single"},
                {"label": "Married Filing Jointly", "value": "filing_married"},
                {"label": "Head of Household", "value": "filing_hoh"},
                {"label": "Other", "value": "filing_other"}
            ],
            metadata={"_source": "template"},
        )

    # Handle frustrated/confused user
    frustrated_patterns = [
        r'(this\s*(is\s*)?(not|doesn\'t)\s*work)',
        r'(i\'?m\s*(so\s*)?(confused|frustrated|lost))',
        r'(i\s*don\'?t\s*understand)',
        r'(help\s*me|i\s*need\s*help)[\s!]*$',
        r'(what|huh|wtf|wth)\?*$'
    ]
    is_frustrated = any(re.search(p, msg_lower) for p in frustrated_patterns)
    if is_frustrated:
        help_response = "I'm sorry for any confusion! Let me help you.\n\n"
        help_response += "**Here's what you can do:**\n"
        help_response += "• Tell me your filing status (single, married, etc.)\n"
        help_response += "• Share your approximate income\n"
        help_response += "• Say \"undo\" to go back\n"
        help_response += "• Say \"reset\" to start over\n"
        help_response += "• Say \"show history\" to see our conversation\n\n"

        if profile:
            help_response += f"**Your current info:** {_summarize_profile(profile)}\n\n"

        help_response += "What would you like to do?"

        return ChatResponse(
            session_id=request.session_id,
            response=help_response,
            response_type="help",
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=[
                {"label": "Start Over", "value": "reset"},
                {"label": "Show My History", "value": "show_history"},
                {"label": "Continue", "value": "continue"}
            ],
            metadata={"_source": "template"},
        )

    # Handle off-topic messages (detect if message has no tax-related content)
    tax_keywords = [
        'tax', 'income', 'salary', 'wage', 'earn', 'make', 'filing', 'single', 'married',
        'dependent', 'child', 'deduct', 'credit', 'refund', 'owe', 'irs', 'state',
        'business', 'self-employ', '1099', 'w-2', 'w2', 'mortgage', 'rent', 'invest',
        'retire', '401k', 'ira', 'hsa', 'charit', 'donat', 'medical', 'student',
        'capital', 'gain', 'loss', 'dividend', 'interest', 'property', 'home',
        'yes', 'no', 'correct', 'change', 'update', 'undo', 'reset', 'help',
        'k', 'thousand', 'million', 'hundred', '$', 'dollar', 'annual',
        # Common typos (to prevent false off-topic detection)
        'singl', 'maried', 'marred', 'seperately', 'houshold', 'dependant',
        'deductio', 'expens', 'refun', 'californi', 'texs', 'flordia', 'york',
        'hoh', 'mfj', 'mfs', 'jointly', 'separate', 'widow',
    ]

    # Also check if message contains numbers (likely tax-related)
    has_numbers = bool(re.search(r'\d', msg_original))
    has_tax_keyword = any(kw in msg_lower for kw in tax_keywords)

    # Also do a quick fuzzy check for filing status patterns
    fuzzy_status, _ = EnhancedParser.fuzzy_match_filing_status(msg_original)
    fuzzy_state, _ = EnhancedParser.fuzzy_match_state(msg_original)
    has_fuzzy_match = fuzzy_status is not None or fuzzy_state is not None

    if not has_numbers and not has_tax_keyword and not has_fuzzy_match and len(msg_original) > 20:
        # Likely off-topic - gently redirect
        redirect_response = "I'm specifically designed to help with tax questions and planning. "
        redirect_response += "I can help you with:\n\n"
        redirect_response += "• Estimating your tax liability\n"
        redirect_response += "• Finding deductions and credits\n"
        redirect_response += "• Retirement planning strategies\n"
        redirect_response += "• Business tax optimization\n\n"

        if not profile.get("filing_status"):
            redirect_response += "Let's start - what's your filing status?"
        elif not profile.get("total_income"):
            redirect_response += "What's your approximate annual income?"
        else:
            redirect_response += "What tax-related question can I help you with?"

        return ChatResponse(
            session_id=request.session_id,
            response=redirect_response,
            response_type="redirect",
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=[
                {"label": "Calculate My Taxes", "value": "calculate_taxes"},
                {"label": "Find Deductions", "value": "find_deductions"},
                {"label": "Upload Documents", "value": "upload_docs"}
            ],
            metadata={"_source": "rules"},
        )

    # =========================================================================
    # STRATEGY DRILL-DOWN — let users explore individual strategies
    # =========================================================================
    strategy_detail_match = re.match(r'strategy_detail_(\w+)', msg_lower)
    tell_more_match = re.search(
        r'(?:tell me more|explain|details|more info|drill down|deep dive).*(?:strategy\s*)?(\d+|401k|ira|hsa|deduction|retirement|business|roth|income|charitable)',
        msg_lower
    )

    if strategy_detail_match or tell_more_match:
        strategy_ref = (strategy_detail_match.group(1) if strategy_detail_match
                        else tell_more_match.group(1).strip())
        cached = session.get("strategies", [])
        target = None

        # Match by index (1-based) or by id/title substring
        if strategy_ref.isdigit():
            idx = int(strategy_ref) - 1
            if 0 <= idx < len(cached):
                target = cached[idx]
        else:
            for s in cached:
                s_dict = s.dict() if hasattr(s, 'dict') else s
                if strategy_ref in (s_dict.get("id", "") + " " + s_dict.get("title", "")).lower():
                    target = s
                    break

        if target:
            t = target.dict() if hasattr(target, 'dict') else target
            # Build rich detail response using AI reasoning if available
            full_detail = t.get("detailed_explanation", t.get("summary", ""))
            detail_source = "fallback_template"
            if AI_CHAT_ENABLED:
                try:
                    detail_prompt = (
                        f"Explain in detail for a taxpayer: {t['title']}. "
                        f"Summary: {t.get('summary', '')}. "
                        f"Steps: {t.get('action_steps', [])}."
                    )
                    ai_detail = await chat_engine._ai_reason_about_tax_question(detail_prompt, session)
                    if ai_detail:
                        full_detail = ai_detail
                        detail_source = "ai"
                except Exception as e:
                    logger.warning(
                        "AI fallback activated",
                        extra={
                            "service": "advisor_reasoning",
                            "source": "fallback_template",
                            "reason": str(e),
                            "impact": "user receives template explanation instead of AI-personalized detail",
                        },
                    )

            # Include ALL action steps (not truncated)
            steps_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(t.get("action_steps", [])))
            if steps_text:
                full_detail += f"\n\n**Action Steps:**\n{steps_text}"
            if t.get("irs_reference"):
                full_detail += f"\n\n**IRS Reference:** {t['irs_reference']}"
            if t.get("estimated_savings"):
                full_detail += f"\n\n**Estimated Savings:** ${t['estimated_savings']:,.0f}"
            full_detail += f"\n\n---\n*{STANDARD_DISCLAIMER}*"

            get_ai_metrics_service().record_response_quality(
                service="advisor_reasoning", source=detail_source,
                response_fields_populated=1 if detail_source == "ai" else 0,
                total_fields=1,
            )

            return ChatResponse(
                session_id=request.session_id,
                response=full_detail,
                response_type="strategy_detail",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile),
                quick_actions=[
                    {"label": "Show All Strategies", "value": "show_strategies"},
                    {"label": "Generate Report", "value": "generate_report"},
                    {"label": "Ask a Question", "value": "ask_question"},
                ],
                metadata={"_source": detail_source},
            )

    # Detect user intent
    user_intent = detect_user_intent(request.message or "", profile) if request.message else "provide_info"

    # =========================================================================
    # AI-POWERED RESPONSE for complex / research questions (cost-gated)
    # =========================================================================
    if AI_CHAT_ENABLED and user_intent in ("ask_question", "request_advice"):
        try:
            from services.ai.chat_router import QueryAnalyzer, QueryType
            _qa = QueryAnalyzer()
            _analysis = _qa.analyze(msg_original)

            if _analysis.query_type in (QueryType.COMPLEX_REASONING, QueryType.RESEARCH, QueryType.COMPARISON):
                context = _summarize_profile(profile) if profile else None

                # Research queries → cheaper Perplexity path with caching
                if _analysis.query_type == QueryType.RESEARCH:
                    from services.ai.tax_research_service import get_tax_research_service
                    research_svc = get_tax_research_service()
                    result = await research_svc.research(msg_original, context=context)
                    ai_text = result.summary
                    if result.sources:
                        ai_text += "\n\n**Sources:** " + ", ".join(result.sources[:3])
                    ai_text += f"\n\n---\n*{STANDARD_DISCLAIMER}*"
                    _resp_type = "ai_research"
                else:
                    # Complex reasoning / comparison → optimal model via ChatRouter
                    from services.ai.chat_router import get_chat_router
                    router_instance = get_chat_router()
                    ai_resp = await router_instance.route_query(
                        query=msg_original,
                        conversation_id=request.session_id,
                        additional_context=context,
                    )
                    ai_text = ai_resp.content
                    ai_text += f"\n\n---\n*{STANDARD_DISCLAIMER}*"
                    _resp_type = "ai_response"

                # Record in conversation history
                conversation = session.get("conversation", [])
                conversation.append({"role": "user", "content": msg_original, "timestamp": datetime.now().isoformat()})
                conversation.append({"role": "assistant", "content": ai_text, "timestamp": datetime.now().isoformat()})
                session["conversation"] = chat_engine._prune_conversation(conversation)

                # CPA Review Gate: queue for approval if firm has review mode
                review_result = _maybe_queue_for_review(
                    session, request.session_id, msg_original, ai_text,
                    complexity=chat_engine.determine_complexity(profile),
                )
                if review_result:
                    return ChatResponse(
                        session_id=request.session_id,
                        response=review_result["message"],
                        response_type="queued_for_review",
                        disclaimer=STANDARD_DISCLAIMER,
                        profile_completeness=chat_engine.calculate_profile_completeness(profile),
                        lead_score=chat_engine.calculate_lead_score(profile),
                        complexity=chat_engine.determine_complexity(profile),
                        quick_actions=[
                            {"label": "Ask Another Question", "value": "ask_question"},
                            {"label": "Continue Profile", "value": "continue_profile"},
                        ],
                        response_confidence="high",
                        metadata={"_source": "ai"},
                    )

                return ChatResponse(
                    session_id=request.session_id,
                    response=ai_text,
                    response_type=_resp_type,
                    disclaimer=STANDARD_DISCLAIMER,
                    profile_completeness=chat_engine.calculate_profile_completeness(profile),
                    lead_score=chat_engine.calculate_lead_score(profile),
                    complexity=chat_engine.determine_complexity(profile),
                    quick_actions=[
                        {"label": "Continue Profile", "value": "continue_profile"},
                        {"label": "Generate Report", "value": "generate_report"},
                    ],
                    response_confidence="high",
                    metadata={"_source": "ai"},
                )
        except Exception as e:
            logger.warning(
                "AI fallback activated",
                extra={
                    "service": "advisor_chat",
                    "source": "fallback",
                    "reason": str(e),
                    "impact": "user question falls through to rule-based or fallback reasoning",
                },
            )

    # --- FALLBACK: UnifiedAIService deep reasoning for unanswered questions ---
    if user_intent in ("ask_question", "request_advice"):
        try:
            ai_answer = await chat_engine._ai_reason_about_tax_question(msg_original, session)
            if ai_answer:
                ai_answer += f"\n\n---\n*{STANDARD_DISCLAIMER}*"
                conversation = session.get("conversation", [])
                conversation.append({"role": "user", "content": msg_original, "timestamp": datetime.now().isoformat()})
                conversation.append({"role": "assistant", "content": ai_answer, "timestamp": datetime.now().isoformat()})
                session["conversation"] = chat_engine._prune_conversation(conversation)

                # CPA Review Gate: queue for approval if firm has review mode
                review_result = _maybe_queue_for_review(
                    session, request.session_id, msg_original, ai_answer,
                    complexity=chat_engine.determine_complexity(profile),
                )
                if review_result:
                    return ChatResponse(
                        session_id=request.session_id,
                        response=review_result["message"],
                        response_type="queued_for_review",
                        disclaimer=STANDARD_DISCLAIMER,
                        profile_completeness=chat_engine.calculate_profile_completeness(profile),
                        lead_score=chat_engine.calculate_lead_score(profile),
                        complexity=chat_engine.determine_complexity(profile),
                        quick_actions=[
                            {"label": "Ask Another Question", "value": "ask_question"},
                            {"label": "Continue Profile", "value": "continue_profile"},
                        ],
                        response_confidence="medium",
                        metadata={"_source": "ai"},
                    )

                return ChatResponse(
                    session_id=request.session_id,
                    response=ai_answer,
                    response_type="ai_reasoning",
                    disclaimer=STANDARD_DISCLAIMER,
                    profile_completeness=chat_engine.calculate_profile_completeness(profile),
                    lead_score=chat_engine.calculate_lead_score(profile),
                    complexity=chat_engine.determine_complexity(profile),
                    quick_actions=[
                        {"label": "Continue Profile", "value": "continue_profile"},
                        {"label": "Ask Another Question", "value": "ask_question"},
                        {"label": "Generate Report", "value": "generate_report"},
                    ],
                    response_confidence="medium",
                    confidence_reason="AI-generated reasoning based on your profile",
                    metadata={"_source": "ai"},
                )
        except Exception as e:
            logger.warning(
                "AI fallback activated",
                extra={
                    "service": "advisor_reasoning",
                    "source": "fallback",
                    "reason": str(e),
                    "impact": "user question not answered by AI, falls through to profile extraction",
                },
            )

    # =========================================================================
    # MULTI-TURN UNDO SYSTEM - Handle various undo requests dynamically
    # =========================================================================

    # Check for "undo to turn X" pattern
    import re
    undo_to_turn_match = re.search(r'undo\s*(?:to\s*)?(?:turn\s*)?(\d+)', msg_lower)
    show_history = re.search(r'show\s*history|view\s*history|my\s*history|what\s*did\s*i\s*say', msg_lower)
    reset_all = re.search(r'reset\s*(?:all|everything)|start\s*(?:over|fresh)|clear\s*(?:all|everything)', msg_lower)

    # Handle "show history" - Display conversation history for user to pick undo point
    if show_history:
        history_text = await chat_engine.get_conversation_history_for_undo(request.session_id)
        return ChatResponse(
            session_id=request.session_id,
            response=history_text,
            response_type="history_display",
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            lead_score=chat_engine.calculate_lead_score(profile),
            complexity=chat_engine.determine_complexity(profile),
            quick_actions=[
                {"label": "Undo Last Turn", "value": "undo_last"},
                {"label": "Continue", "value": "continue_conversation"}
            ],
            metadata={"_source": "template"},
        )

    # Handle "reset all" - Complete reset to empty state
    if reset_all:
        # Full reset - clear everything including profile
        session["profile"] = {}
        session["checkpoints"] = []
        session["current_turn"] = 0
        session["calculations"] = None
        session["strategies"] = []
        session["conversation"] = []
        await chat_engine._save_session_to_db(request.session_id, session)
        profile = {}

        return ChatResponse(
            session_id=request.session_id,
            response="I've reset everything. Let's start fresh!\n\nWhat's your filing status?",
            response_type="reset_complete",
            profile_completeness=0.0,
            lead_score=0,
            complexity="simple",
            quick_actions=[
                {"label": "Single", "value": "filing_single"},
                {"label": "Married Filing Jointly", "value": "filing_married"},
                {"label": "Head of Household", "value": "filing_hoh"},
                {"label": "Married Filing Separately", "value": "filing_mfs"}
            ],
            metadata={"_source": "template"},
        )

    # Handle "undo to turn X" - Multi-turn undo to specific point
    if undo_to_turn_match:
        target_turn = int(undo_to_turn_match.group(1))
        result = await chat_engine.undo_to_turn(request.session_id, target_turn)

        if result["success"]:
            profile = result["restored_profile"]
            next_q, next_actions = _get_dynamic_next_question(profile)

            response_text = f"✓ {result['message']}\n\n"
            if next_q:
                response_text += next_q
            else:
                response_text += "What would you like to update?"

            return ChatResponse(
                session_id=request.session_id,
                response=response_text,
                response_type="undo_complete",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile),
                quick_actions=next_actions or [{"label": "Continue", "value": "continue"}],
                metadata={"_source": "rules"},
            )
        else:
            return ChatResponse(
                session_id=request.session_id,
                response=result["message"],
                response_type="error",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile),
                metadata={"_source": "rules"},
            )

    # Handle simple "undo" - Undo last turn
    if user_intent == "undo":
        result = await chat_engine.undo_last_turn(request.session_id)

        if result["success"]:
            profile = result["restored_profile"]
            next_q, next_actions = _get_dynamic_next_question(profile)

            response_text = f"✓ {result['message']}\n\n"
            if next_q:
                response_text += next_q
            else:
                response_text += "What would you like to change?"

            # Show undo options for further undo
            undo_options = await chat_engine.get_undo_options(request.session_id)
            if len(undo_options) > 1:
                response_text += f"\n\n*You can also say \"undo to turn X\" to go back further ({len(undo_options)} checkpoints available).*"

            return ChatResponse(
                session_id=request.session_id,
                response=response_text,
                response_type="undo_complete",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile),
                quick_actions=next_actions or [
                    {"label": "Show History", "value": "show_history"},
                    {"label": "Continue", "value": "continue"}
                ],
                metadata={"_source": "rules"},
            )
        else:
            return ChatResponse(
                session_id=request.session_id,
                response=result["message"],
                response_type="info",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile),
                metadata={"_source": "rules"},
            )

    # Update profile with any new data from request
    if request.profile:
        profile_dict = request.profile.dict(exclude_none=True)
        session = await chat_engine.update_session(request.session_id, {"profile": profile_dict})
        profile = session["profile"]

    # =========================================================================
    # QUICK ACTION VALUE HANDLER (Phase 2 deep-dive buttons)
    # Maps button clicks directly to profile updates before NLU parsing
    # =========================================================================
    _quick_action_handled = False
    _quick_action_map = {
        # Age quick actions
        "age_under_50": {"age": 35},
        "age_50_64": {"age": 57},
        "age_65_plus": {"age": 67},
        "skip_age": {"_asked_age": True},
        # Business deep dive
        "biz_under_50k": {"business_income": 25000},
        "biz_50_100k": {"business_income": 75000},
        "biz_100_200k": {"business_income": 150000},
        "biz_over_200k": {"business_income": 300000},
        "skip_business": {"_asked_business": True},
        "has_home_office": {"home_office_sqft": 200},  # Reasonable default, will ask to refine
        "no_home_office": {"home_office_sqft": 0, "_asked_home_office": True},
        "skip_home_office": {"_asked_home_office": True},
        # K-1 income
        "has_k1_income": {"_has_k1": True},
        "no_k1_income": {"_asked_k1": True, "k1_ordinary_income": 0},
        "skip_k1": {"_asked_k1": True},
        # Investment income
        "has_investments": {"_has_investments": True},
        "no_investments": {"_asked_investments": True, "investment_income": 0},
        "skip_investments": {"_asked_investments": True},
        # Rental income
        "has_rental": {"_has_rental": True},
        "no_rental": {"_asked_rental": True, "rental_income": 0},
        "skip_rental": {"_asked_rental": True},
        # Retirement
        "has_401k": {"_has_401k": True, "retirement_401k": 23000},  # Max contribution as default
        "has_ira": {"_has_ira": True, "retirement_ira": 7000},
        "has_both_retirement": {"retirement_401k": 23000, "retirement_ira": 7000},
        "no_retirement": {"_asked_retirement": True, "retirement_401k": 0, "retirement_ira": 0},
        "skip_retirement": {"_asked_retirement": True},
        # HSA
        "has_hsa": {"hsa_contributions": 4150},  # 2025 individual limit
        "no_hsa": {"_asked_hsa": True, "hsa_contributions": 0},
        "skip_hsa": {"_asked_hsa": True},
        # Deductions
        "has_mortgage": {"_has_mortgage": True, "_asked_deductions": True},
        "has_charitable": {"_has_charitable": True, "_asked_deductions": True},
        "has_medical": {"_has_medical": True, "_asked_deductions": True},
        "no_itemized_deductions": {"_asked_deductions": True, "mortgage_interest": 0, "charitable_donations": 0},
        "skip_deductions": {"_asked_deductions": True},
        # Mortgage amount follow-up
        "mortgage_under_5k": {"mortgage_interest": 3000},
        "mortgage_5_15k": {"mortgage_interest": 10000},
        "mortgage_15_30k": {"mortgage_interest": 22000},
        "mortgage_over_30k": {"mortgage_interest": 35000},
        "skip_mortgage_amount": {"_asked_mortgage_amount": True, "mortgage_interest": 10000},
        # Charitable amount follow-up
        "charity_under_1k": {"charitable_donations": 500},
        "charity_1_5k": {"charitable_donations": 3000},
        "charity_5_20k": {"charitable_donations": 12000},
        "charity_over_20k": {"charitable_donations": 25000},
        "skip_charitable_amount": {"_asked_charitable_amount": True, "charitable_donations": 2000},
        # Estimated payments
        "has_estimated_payments": {"_has_estimated_payments": True},
        "no_estimated_payments": {"_asked_estimated": True, "estimated_payments": 0},
        "skip_estimated": {"_asked_estimated": True},
        # Student loans
        "has_student_loans": {"student_loan_interest": 2500},  # Max deductible
        "no_student_loans": {"_asked_student_loans": True, "student_loan_interest": 0},
        "skip_student_loans": {"_asked_student_loans": True},
        # Skip deep dive entirely
        "skip_deep_dive": {"_skip_deep_dive": True},
        # Phase 1: Dependents quick actions
        "0_dependents": {"dependents": 0},
        "1_dependent": {"dependents": 1},
        "2_dependents": {"dependents": 2},
        "3plus_dependents": {"dependents": 3},
        # Phase 1: Income type quick actions
        "w2_employee": {"income_type": "w2", "is_self_employed": False},
        "self_employed": {"income_type": "self_employed", "is_self_employed": True},
        "business_owner": {"income_type": "business", "is_self_employed": True},
        "retired": {"income_type": "retired", "is_self_employed": False},
    }

    if msg_lower in _quick_action_map:
        updates = _quick_action_map[msg_lower]
        profile.update(updates)
        session = await chat_engine.update_session(request.session_id, {"profile": profile})
        _quick_action_handled = True

        # Create checkpoint for undo
        real_fields = [k for k in updates.keys() if not k.startswith("_")]
        if real_fields:
            await chat_engine.create_checkpoint(request.session_id, msg_original, real_fields)

        # Acknowledge and move to next question
        next_q, next_actions = _get_dynamic_next_question(profile, session=session)

        if next_q:
            # Build a brief acknowledgment based on what was just set
            ack = ""
            if "age" in updates:
                ack = f"Got it, age {updates['age']}. "
            elif "business_income" in updates:
                ack = f"Noted — ${updates['business_income']:,.0f} business income. "
            elif "retirement_401k" in updates or "retirement_ira" in updates:
                amounts = []
                if updates.get("retirement_401k"):
                    amounts.append(f"401(k): ${updates['retirement_401k']:,.0f}")
                if updates.get("retirement_ira"):
                    amounts.append(f"IRA: ${updates['retirement_ira']:,.0f}")
                ack = f"Great — {', '.join(amounts)}. " if amounts else "Noted. "
            elif "mortgage_interest" in updates and updates["mortgage_interest"] > 0:
                ack = f"Got it — ${updates['mortgage_interest']:,.0f} in mortgage interest. "
            elif "charitable_donations" in updates and updates["charitable_donations"] > 0:
                ack = f"Noted — ${updates['charitable_donations']:,.0f} in charitable donations. "
            elif "hsa_contributions" in updates and updates["hsa_contributions"] > 0:
                ack = f"Great — ${updates['hsa_contributions']:,.0f} HSA contribution. "
            elif any(k.startswith("_asked") or k.startswith("skip") for k in updates):
                ack = ""  # Silent skip
            elif any(updates.get(k) == 0 for k in ["k1_ordinary_income", "investment_income", "rental_income"]):
                ack = ""  # "No" answers don't need acknowledgment

            return ChatResponse(
                session_id=request.session_id,
                response=ack + next_q,
                response_type="question",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile),
                quick_actions=next_actions,
                metadata={"_source": "template"},
            )
        # else: fall through to calculation below

    # =========================================================================
    # ENHANCED PARSING with confidence scoring, fuzzy matching, validation
    # =========================================================================
    correction_made = False
    changed_fields = []
    extracted_fields = []
    pending_confirmations = []
    detected_conflicts = []
    validation_warnings = []

    if request.message and not _quick_action_handled:
        # Use enhanced parser for robustness
        parse_result = enhanced_parse_user_message(request.message, profile, session)

        # Check for field-specific update (e.g., "change my income to 90000")
        if parse_result.get("field_update"):
            field_update = parse_result["field_update"]
            extracted = {field_update["field"]: field_update["new_value"]}
            extracted_fields = [field_update["field"]]
            correction_made = True
            changed_fields = extracted_fields
            logger.info(f"Field-specific update: {field_update}")
        else:
            extracted = parse_result.get("extracted", {})
            extracted_fields = [k for k in extracted.keys() if not k.startswith("_")]

        # Handle needs_confirmation - store for asking user
        if parse_result.get("needs_confirmation"):
            pending_confirmations = parse_result["needs_confirmation"]
            # Store in session for follow-up handling
            session["pending_confirmations"] = pending_confirmations

        # Handle detected conflicts
        if parse_result.get("conflicts"):
            detected_conflicts = parse_result["conflicts"]

        # Handle validation warnings
        if parse_result.get("warnings"):
            validation_warnings = parse_result["warnings"]

        # Augment regex extraction with AI entity extraction (fills gaps only)
        try:
            ai_updates = await chat_engine._ai_extract_profile_data(msg_original, session)
            for key, value in ai_updates.items():
                if key not in extracted or not extracted[key]:
                    extracted[key] = value
                    if key not in extracted_fields:
                        extracted_fields.append(key)
        except Exception as e:
            logger.warning(
                "AI fallback activated",
                extra={
                    "service": "advisor_extraction_augmentation",
                    "source": "fallback",
                    "reason": str(e),
                    "impact": "AI extraction skipped, relying on rule-based extraction only",
                },
            )

        if extracted:
            # Check if this is a correction
            if extracted.get("_is_correction"):
                correction_made = True
                changed_fields = [extracted.get("_changed_field")] if extracted.get("_changed_field") else extracted_fields
                # Clear calculations when corrections are made
                session["calculations"] = None
                session["strategies"] = []

            # Remove internal flags before updating profile
            extracted.pop("_is_correction", None)
            extracted.pop("_changed_field", None)
            extracted.pop("_response_type", None)
            extracted.pop("_clarification_needed", None)

            # CREATE CHECKPOINT BEFORE applying changes (for undo capability)
            if extracted_fields:
                await chat_engine.create_checkpoint(
                    request.session_id,
                    request.message,
                    extracted_fields
                )

            # Now update the profile with extracted data
            profile.update(extracted)
            session = await chat_engine.update_session(request.session_id, {"profile": profile})

            # Log with confidence scores
            confidence_info = parse_result.get("confidence", {})
            logger.info(f"Enhanced extraction: {extracted} (confidence: {confidence_info})")

            # Wire contextual follow-ups: detect topics mentioned and use them
            # to drive the deep-dive question flow
            if request.message:
                detected_topics = ConversationContext.detect_topic(request.message)
                for topic in detected_topics:
                    # Map detected topics to profile flags that drive follow-up questions
                    topic_flag_map = {
                        "rental_income": "_has_rental",
                        "business_income": "is_self_employed",
                        "investment_income": "_has_investments",
                        "self_employed": "is_self_employed",
                        "retirement": "_has_retirement",
                        "mortgage": "_has_mortgage",
                        "charitable": "_has_charitable",
                        "medical": "_has_medical",
                        "education": "_has_education",
                    }
                    flag = topic_flag_map.get(topic)
                    if flag and not profile.get(flag):
                        profile[flag] = True
                        session = await chat_engine.update_session(
                            request.session_id, {"profile": profile}
                        )

                # Use contextual follow-up from ConversationContext (was dead code)
                contextual_followup = ConversationContext.get_contextual_follow_up(
                    extracted, profile, session
                )
                if contextual_followup:
                    # Store as a hint for response building
                    session["_contextual_followup"] = contextual_followup

    # Calculate metrics
    completeness = chat_engine.calculate_profile_completeness(profile)
    lead_score = chat_engine.calculate_lead_score(profile)
    complexity = chat_engine.determine_complexity(profile)

    # Journey event: emit profile complete when threshold crossed
    if _JOURNEY_EVENTS_AVAILABLE and completeness >= 0.6:
        try:
            bus = get_event_bus()
            if bus:
                bus.emit(AdvisorProfileComplete(
                    session_id=session_id,
                    tenant_id=session.get("tenant_id", "default"),
                    user_id=session.get("user_id", session_id),
                    profile_completeness=completeness,
                    extracted_forms=list(profile.get("_extracted_forms", [])),
                ))
        except Exception:
            pass  # Never block chat on event emission failure

    # Get urgency info from CPAIntelligenceService
    urgency_level = "PLANNING"
    urgency_message = "Perfect timing for tax planning!"
    days_to_deadline = 365
    try:
        from services.cpa_intelligence_service import calculate_urgency_level
        urgency_level, urgency_message, days_to_deadline = calculate_urgency_level()
    except Exception as e:
        logger.debug(f"Urgency calculation skipped: {e}")

    # Determine response type and content
    response_type = "question"
    response_text = ""
    tax_calculation = None
    strategies = []
    next_questions = []
    quick_actions = []
    key_insights = []
    warnings = []
    total_potential_savings = 0.0
    premium_unlocked = False
    safety_data = None

    # Build correction acknowledgment prefix if needed
    correction_prefix = ""
    if correction_made:
        if changed_fields:
            field_names = {"filing_status": "filing status", "total_income": "income",
                          "state": "state", "dependents": "dependents"}
            changed_names = [field_names.get(f, f) for f in changed_fields if f and not f.startswith("_")]
            if changed_names:
                correction_prefix = f"Got it! I've updated your {', '.join(changed_names)}. "
            else:
                correction_prefix = "Got it! I've updated your information. "
        else:
            correction_prefix = "Got it! I've noted that change. "

    # =========================================================================
    # Handle confirmations, conflicts, and validation warnings FIRST
    # =========================================================================

    # If there are pending confirmations, ask for confirmation before proceeding
    if pending_confirmations:
        confirmation = pending_confirmations[0]  # Handle one at a time
        response_text = confirmation.get("message", "Could you please confirm this?")

        # Build confirmation options
        if "options" in confirmation:
            quick_actions = [
                {"label": opt["meaning"], "value": f"confirm_{opt['amount']}"}
                for opt in confirmation["options"]
            ]
            quick_actions.append({"label": "Enter different amount", "value": "enter_custom"})
        else:
            quick_actions = [
                {"label": "Yes, that's correct", "value": "confirm_yes"},
                {"label": "No, let me clarify", "value": "confirm_no"}
            ]

        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            response_type="confirmation_needed",
            profile_completeness=completeness,
            lead_score=lead_score,
            complexity=complexity,
            quick_actions=quick_actions,
            warnings=[f"⚠️ Low confidence: {confirmation.get('field', 'value')}"],
            metadata={"_source": "rules"},
        )

    # If there are conflicts, ask user to resolve them
    if detected_conflicts:
        conflict = detected_conflicts[0]  # Handle one at a time
        response_text = f"🤔 {conflict.get('message', '')}\n\n{conflict.get('question', 'Which is correct?')}"

        quick_actions = conflict.get("options", [
            {"label": "Continue as is", "value": "conflict_ignore"}
        ])

        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            response_type="conflict_resolution",
            profile_completeness=completeness,
            lead_score=lead_score,
            complexity=complexity,
            quick_actions=quick_actions,
            metadata={"_source": "rules"},
        )

    # If there are validation warnings that need attention
    critical_warnings = [w for w in validation_warnings if not w.get("auto_corrected")]
    if critical_warnings:
        warning = critical_warnings[0]
        response_text = f"⚠️ {warning.get('message', 'Please check this value.')}"
        if warning.get("suggestion"):
            response_text += f"\n\n{warning['suggestion']}"

        quick_actions = []
        if warning.get("possible_correction"):
            quick_actions.append({
                "label": f"Yes, use ${warning['possible_correction']:,.0f}",
                "value": f"correct_{warning['field']}_{warning['possible_correction']}"
            })
        quick_actions.append({"label": "Keep my original value", "value": "keep_value"})
        quick_actions.append({"label": "Enter different value", "value": "enter_custom"})

        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            response_type="validation_warning",
            profile_completeness=completeness,
            lead_score=lead_score,
            complexity=complexity,
            quick_actions=quick_actions,
            warnings=[warning.get("message", "")],
            metadata={"_source": "rules"},
        )

    # Handle scenario comparison via ChatRouter (design doc: compare_scenarios wiring)
    comparison_result = None
    if AI_CHAT_ENABLED and any(kw in (request.message or "").lower() for kw in ["compare", "versus", " vs ", "should i do", "which is better"]):
        try:
            from services.ai.chat_router import get_chat_router
            chat_router = get_chat_router()
            msg_lower = (request.message or "").lower()
            parts = msg_lower.split(" or ") if " or " in msg_lower else [msg_lower, "alternative approach"]
            comparison_result = await chat_router.compare_scenarios(
                question=message,
                scenarios=[
                    {"name": "Option A", "description": parts[0].strip()},
                    {"name": "Option B", "description": parts[1].strip() if len(parts) > 1 else "alternative approach"},
                ],
            )
        except Exception:
            pass  # Non-blocking

    # Include comparison in response if available
    if comparison_result and hasattr(comparison_result, "content") and comparison_result.content:
        comp_text = comparison_result.content
        if comp_text and len(comp_text) > 10:
            response_text = comp_text[:1500]
            response_type = "ai_response"

    # Check if there are still deep-dive questions to ask before calculating
    has_basics = profile.get("total_income") and profile.get("filing_status") and profile.get("state")
    next_deep_q, next_deep_actions = _get_dynamic_next_question(profile, session=session)

    # If basics are done but deep-dive questions remain, ask them first
    if has_basics and next_deep_q:
        # Include a "Skip to Results" option so user isn't trapped
        if next_deep_actions and not any(a.get("value") == "skip_deep_dive" for a in next_deep_actions):
            next_deep_actions.append({"label": "Skip to Results", "value": "skip_deep_dive"})

        # Use contextual follow-up if available (from topic detection)
        contextual = session.get("_contextual_followup")
        if contextual:
            response_text = f"{correction_prefix}{contextual}"
            session.pop("_contextual_followup", None)
        else:
            response_text = f"{correction_prefix}{next_deep_q}"

        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            response_type="question",
            profile_completeness=completeness,
            lead_score=lead_score,
            complexity=complexity,
            quick_actions=next_deep_actions,
            metadata={"_source": "template"},
        )

    # If we have enough data, calculate taxes
    if has_basics:
        tax_calculation = await chat_engine.get_tax_calculation(profile)

        # Get strategies
        strategies = await chat_engine.get_tax_strategies(profile, tax_calculation)

        # Enrich top strategies with AI reasoning (non-simple profiles only)
        if AI_CHAT_ENABLED and complexity != "simple" and strategies:
            import time as _time
            _ai_start = _time.monotonic()
            # Parallel reasoning enrichment
            try:
                from services.ai.tax_reasoning_service import get_tax_reasoning_service
                reasoning_svc = get_tax_reasoning_service()
                reasoning_tasks = []
                for s in strategies[:2]:
                    reasoning_tasks.append(reasoning_svc.analyze(
                        problem=f"Evaluate strategy: {s.title} with savings of ${s.estimated_savings:,.0f}",
                        context=_summarize_profile(profile),
                    ))
                reasoning_results = await asyncio.gather(*reasoning_tasks, return_exceptions=True)
                for s, result in zip(strategies[:2], reasoning_results):
                    if isinstance(result, Exception):
                        continue
                    if result and result.confidence:
                        s.confidence = "high" if result.confidence > 0.8 else "medium" if result.confidence > 0.5 else "low"
                _ai_elapsed = (_time.monotonic() - _ai_start) * 1000
                asyncio.create_task(_record_ai_usage("TaxReasoningService", "analyze", _ai_elapsed))
            except Exception:
                _ai_elapsed = (_time.monotonic() - _ai_start) * 1000
                asyncio.create_task(_record_ai_usage("TaxReasoningService", "analyze", _ai_elapsed, success=False))

            # Parallel narrative enrichment
            try:
                from advisory.ai_narrative_generator import get_narrative_generator, ClientProfile as NarrClientProfile
                narrator = get_narrative_generator()
                client_profile = NarrClientProfile(
                    name=profile.get("name", "Client"),
                    occupation=profile.get("occupation", ""),
                    financial_goals=["Minimize tax liability"],
                    primary_concern="Tax optimization",
                )
                narr_tasks = []
                for s in strategies[:3]:
                    rec_data = {
                        "title": s.title,
                        "savings": s.estimated_savings,
                        "priority": s.priority,
                        "explanation": s.detailed_explanation or "",
                    }
                    narr_tasks.append(narrator.generate_recommendation_explanation(rec_data, client_profile))
                narr_results = await asyncio.gather(*narr_tasks, return_exceptions=True)
                for s, narrative in zip(strategies[:3], narr_results):
                    if isinstance(narrative, Exception):
                        continue
                    if narrative and narrative.content:
                        s.detailed_explanation = narrative.content[:800]
                asyncio.create_task(_record_ai_usage("AINarrativeGenerator", "generate_recommendation_explanation"))
            except Exception as e:
                logger.warning(f"Narrative enrichment failed (non-blocking): {e}")
                asyncio.create_task(_record_ai_usage("AINarrativeGenerator", "generate_recommendation_explanation", success=False))

        # Classify strategy tiers
        tier_session = await chat_engine.get_or_create_session(request.session_id)
        safety_data = tier_session.get("safety_checks")
        premium_unlocked = tier_session.get("premium_unlocked", False)

        # Classify tiers — deterministic rules first, AI only for ambiguous cases
        tier_tasks = [_classify_strategy_tier(s, profile, safety_data) for s in strategies]
        tier_results = await asyncio.gather(*tier_tasks, return_exceptions=True)
        for s, tier_info in zip(strategies, tier_results):
            if isinstance(tier_info, Exception):
                tier_info = {"tier": "free", "risk_level": "low", "implementation_complexity": "simple"}
            s.tier = tier_info["tier"]
            s.risk_level = tier_info["risk_level"]
            s.implementation_complexity = tier_info["implementation_complexity"]

        # Count tiers for response
        premium_count = sum(1 for s in strategies if s.tier == "premium")

        # Edge case: all free (simple W-2) — no tiering
        if premium_count == 0:
            premium_unlocked = True  # Nothing to unlock

        # Update running savings total
        total_detected_savings = sum(s.estimated_savings for s in strategies)

        # Update session with calculations, strategies, and savings tracking
        await chat_engine.update_session(request.session_id, {
            "calculations": tax_calculation,
            "strategies": strategies,
            "lead_score": chat_engine.calculate_lead_score(profile),
            "detected_savings": total_detected_savings,
        })

        # Run safety checks inline with timeout (results needed for this response)
        if tax_calculation:
            try:
                safety_data = await asyncio.wait_for(
                    _run_safety_checks(request.session_id, profile, tax_calculation),
                    timeout=8.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Safety checks timed out — will show on next response")
                safety_data = None

        # Bridge: Also save to session_tax_returns so advisory report API can find it
        try:
            return_data = convert_profile_to_tax_return(profile, request.session_id)
            calc_dict = tax_calculation.dict() if hasattr(tax_calculation, 'dict') else tax_calculation
            if SESSION_PERSISTENCE_AVAILABLE:
                persistence = get_session_persistence()
                persistence.save_session_tax_return(
                    session_id=request.session_id,
                    tenant_id=chat_engine._get_session_tenant_id(tier_session),
                    tax_year=2025,
                    return_data=return_data,
                    calculated_results=calc_dict,
                )
                logger.debug(f"Tax return data saved to session_tax_returns for {request.session_id}")
        except Exception as bridge_err:
            logger.warning(f"Failed to bridge tax return data (non-blocking): {bridge_err}")

        total_savings = sum(s.estimated_savings for s in strategies)
        total_potential_savings = total_savings

        # Emit real-time event for CPA dashboard
        try:
            from realtime.event_publisher import event_publisher
            from realtime.events import RealtimeEvent, EventType
            await event_publisher.publish(RealtimeEvent(
                event_type=EventType.RETURN_UPDATED,
                session_id=request.session_id,
                data={
                    "total_tax": tax_calculation.total_tax,
                    "savings": total_savings,
                    "strategies": len(strategies),
                },
            ))
        except Exception:
            pass

        response_type = "calculation"

        # Build context-aware response
        filing_display = profile.get('filing_status', 'single').replace('_', ' ').title()
        income_display = f"${profile.get('total_income', 0):,.0f}"
        state_display = f" in {profile.get('state')}" if profile.get('state') else ""
        dependents_display = f" with {profile.get('dependents')} dependent(s)" if profile.get('dependents') else ""

        # Show richer profile summary in calculation response
        extra_info = []
        if profile.get("retirement_401k"):
            extra_info.append(f"401(k): ${profile['retirement_401k']:,.0f}")
        if profile.get("mortgage_interest") and profile["mortgage_interest"] > 0:
            extra_info.append(f"Mortgage interest: ${profile['mortgage_interest']:,.0f}")
        if profile.get("charitable_donations") and profile["charitable_donations"] > 0:
            extra_info.append(f"Charitable: ${profile['charitable_donations']:,.0f}")
        if profile.get("business_income") and profile["business_income"] > 0:
            extra_info.append(f"Business income: ${profile['business_income']:,.0f}")
        extra_display = ""
        if extra_info:
            extra_display = "\n\n**Profile Details:** " + " | ".join(extra_info)

        response_text = f"""{correction_prefix}Based on your profile ({filing_display}, {income_display}{state_display}{dependents_display}):{extra_display}

**Your Tax Position:**
• Federal Tax: **${tax_calculation.federal_tax:,.0f}**
• State Tax: **${tax_calculation.state_tax:,.0f}**
• Total Tax: **${tax_calculation.total_tax:,.0f}**
• Effective Rate: **{tax_calculation.effective_rate:.1f}%**

**I found ${total_savings:,.0f} in potential savings across {len(strategies)} strategies!**"""

        if strategies:
            response_text += f"\n\nYour top opportunity: **{strategies[0].title}** could save you **${strategies[0].estimated_savings:,.0f}**."

        response_text += "\n\nWould you like me to explain your top strategies, generate your full advisory report, or update any information?"

        quick_actions = [
            {"label": "Show Top Strategies", "value": "show_strategies", "primary": True},
            {"label": "Generate Full Report", "value": "generate_report"},
            {"label": "Update My Info", "value": "update_info"},
            {"label": "Connect with CPA", "value": "connect_cpa"}
        ]

        # Prepend quick wins (immediately actionable strategies) before other actions
        if strategies:
            quick_wins = _identify_quick_wins(strategies)
            quick_actions = quick_wins + quick_actions

        # Add deep analysis buttons when AI is enabled (Round 10.4)
        if AI_CHAT_ENABLED:
            deep_actions = [
                {"label": "Deduction Optimization", "value": "deep_deduction_analysis"},
            ]
            if profile.get("is_self_employed") or profile.get("business_income"):
                deep_actions.insert(0, {"label": "Business Structure Analysis", "value": "deep_entity_analysis"})
            if profile.get("retirement_401k") or profile.get("retirement_ira") or (profile.get("total_income", 0) or 0) > 100000:
                deep_actions.append({"label": "Roth Conversion Analysis", "value": "deep_roth_analysis"})
            quick_actions.extend(deep_actions)

        # Add per-strategy drill-down quick actions
        if strategies:
            for i, strat in enumerate(strategies[:3]):
                quick_actions.append({
                    "label": f"Details: {strat.title[:35]}",
                    "value": f"strategy_detail_{strat.id}",
                })

        key_insights = [
            f"Your marginal tax rate is {tax_calculation.marginal_rate}%",
            f"Taking the {tax_calculation.deduction_type} deduction saves you most"
        ]
        if strategies:
            key_insights.append(f"Top opportunity: {strategies[0].title}")

    else:
        # Need more information - use dynamic question system
        next_q, next_actions = _get_dynamic_next_question(profile, session=session)

        if next_q:
            response_text = correction_prefix + next_q
            if next_actions:
                quick_actions = next_actions
        elif not profile.get("filing_status"):
            response_text = "To provide accurate tax strategies, I need to know your filing status. What's your current situation?"
            next_questions = [
                {"question": "What's your filing status?", "type": "select", "options": [
                    {"label": "Single", "value": "single"},
                    {"label": "Married Filing Jointly", "value": "married_joint"},
                    {"label": "Head of Household", "value": "head_of_household"},
                    {"label": "Married Filing Separately", "value": "married_separate"},
                    {"label": "Qualifying Surviving Spouse", "value": "qualifying_widow"}
                ]}
            ]
            quick_actions = [
                {"label": "Single", "value": "filing_single"},
                {"label": "Married Filing Jointly", "value": "filing_married"},
                {"label": "Head of Household", "value": "filing_hoh"},
                {"label": "Married Separately", "value": "filing_mfs"},
                {"label": "Qualifying Surviving Spouse", "value": "filing_qss"}
            ]
        elif not profile.get("total_income"):
            response_text = "What's your approximate total annual income for 2025? Include all sources - W-2 wages, self-employment, investments, etc."
            quick_actions = [
                {"label": "$0 - $50,000", "value": "income_0_50k"},
                {"label": "$50,000 - $100,000", "value": "income_50_100k"},
                {"label": "$100,000 - $200,000", "value": "income_100_200k"},
                {"label": "$200,000 - $500,000", "value": "income_200_500k"},
                {"label": "Over $500,000", "value": "income_500k_plus"}
            ]

    # Add urgency warning if critical
    if urgency_level == "CRITICAL":
        warnings.append(f"⚠️ {urgency_message}")
    elif urgency_level == "HIGH":
        key_insights.insert(0, f"📅 {urgency_message}")

    # Append proactive suggested questions to response (GAP #4)
    suggested_qs = _get_suggested_questions(profile)
    if suggested_qs and response_type in ("calculation", "question", "strategy"):
        response_text += "\n\n**You might also want to share:**\n"
        for sq in suggested_qs:
            response_text += f"- {sq}\n"

    # Record conversation messages and prune if needed
    conversation = session.get("conversation", [])
    conversation.append({"role": "user", "content": msg_original, "timestamp": datetime.now().isoformat()})
    conversation.append({"role": "assistant", "content": response_text, "timestamp": datetime.now().isoformat()})
    session["conversation"] = chat_engine._prune_conversation(conversation)

    # Calculate response confidence
    has_complex = should_require_professional_review(profile) if profile else False
    response_confidence, confidence_reason = calculate_response_confidence(completeness, has_complex)

    # Add tax law citations for calculation/strategy/report responses
    if response_type in ["calculation", "strategy", "report"]:
        try:
            from tax_references.citations import add_citations_to_response
            response_text = add_citations_to_response(response_text)
        except ImportError:
            pass  # Citations module not available

    # Determine primary source for main response
    _has_ai_strategies = strategies and any(
        getattr(s, "metadata", None) and s.metadata.get("_source") == "ai"
        for s in (strategies or [])
    )
    _main_source = "ai" if _has_ai_strategies else "rules"

    try:
        chat_response = ChatResponse(
            session_id=request.session_id,
            response=response_text,
            response_type=response_type,
            disclaimer=STANDARD_DISCLAIMER,
            tax_calculation=tax_calculation,
            strategies=[StrategyRecommendation(**s.dict()) for s in strategies[:5]] if strategies else [],
            next_questions=next_questions,
            quick_actions=quick_actions,
            profile_completeness=completeness,
            lead_score=lead_score,
            complexity=complexity,
            urgency_level=urgency_level,
            urgency_message=urgency_message,
            days_to_deadline=days_to_deadline,
            key_insights=key_insights,
            warnings=warnings,
            total_potential_savings=total_potential_savings,
            response_confidence=response_confidence,
            confidence_reason=confidence_reason,
            premium_unlocked=premium_unlocked,
            detected_savings=session.get("detected_savings", 0),
            new_opportunities=session.get("opportunity_alerts", []),
            missing_fields=missing_fields,
            completion_hint=completion_hint,
            estimated_savings_preview=chat_engine.estimate_partial_savings(profile) if response_type != "calculation" else None,
            safety_summary=_build_safety_summary(safety_data),
            safety_checks=safety_data,
            session_renewed=_session_was_renewed,
            metadata={"_source": _main_source},
        )
        # Clear alerts after sending
        session["opportunity_alerts"] = []

        # Log AI response for audit trail
        try:
            from audit.audit_models import AIResponseAuditEvent
            from audit.audit_logger import log_ai_response, get_prompt_hash

            audit_event = AIResponseAuditEvent(
                session_id=request.session_id,
                model_version="gpt-4-turbo-2024",
                prompt_hash=get_prompt_hash(),
                response_type=response_type,
                profile_completeness=completeness,
                response_confidence=response_confidence,
                confidence_reason=confidence_reason,
                user_message=request.message[:500] if request.message else "",
                response_summary=response_text[:200] if response_text else "",
                warnings_triggered=warnings or []
            )
            log_ai_response(audit_event)
        except Exception as audit_err:
            logger.warning(f"Audit logging failed: {audit_err}")

        return chat_response
    except Exception as e:
        # Catch any response building errors
        logger.error(f"Response building error in intelligent_chat: {e}")
        return ChatResponse(
            session_id=request.session_id,
            response="I encountered an issue processing your request. Let me try a simpler response.",
            response_type="error",
            profile_completeness=completeness if 'completeness' in dir() else 0.0,
            lead_score=lead_score if 'lead_score' in dir() else 0,
            complexity=complexity if 'complexity' in dir() else "simple",
            quick_actions=[
                {"label": "Try Again", "value": "retry"},
                {"label": "Start Over", "value": "reset"}
            ],
            metadata={"_source": "fallback_template"},
        )


@router.post("/analyze", response_model=FullAnalysisResponse)
async def full_analysis(request: FullAnalysisRequest, _session: str = Depends(verify_session_token)):
    """
    Comprehensive tax analysis with all strategies and insights.

    This is the full advisory engine - use this when you have
    complete profile data and want all recommendations.
    """
    try:
        profile = request.profile.dict(exclude_none=True)

        # Get tax calculation
        calculation = await chat_engine.get_tax_calculation(profile)

        # Get all strategies
        strategies = await chat_engine.get_tax_strategies(profile, calculation)

        total_savings = sum(s.estimated_savings for s in strategies)

        # Entity comparison if self-employed
        entity_comparison = None
        if profile.get("is_self_employed") or profile.get("business_income"):
            business_income = profile.get("business_income", 0) or 0
            if AI_CHAT_ENABLED and business_income > 0:
                try:
                    from services.ai.tax_reasoning_service import get_tax_reasoning_service
                    reasoning = get_tax_reasoning_service()
                    result = await reasoning.analyze_entity_structure(
                        gross_revenue=business_income,
                        business_expenses=profile.get("business_expenses", 0) or business_income * 0.3,
                        owner_salary=business_income * 0.6,
                        state=profile.get("state", "CA"),
                        filing_status=profile.get("filing_status", "single"),
                        other_income=(profile.get("total_income", 0) or 0) - business_income,
                        current_entity="sole_prop",
                    )
                    entity_comparison = {
                        "ai_analysis": result.analysis[:1000],
                        "recommendation": result.recommendation,
                        "key_factors": result.key_factors,
                        "action_items": result.action_items[:5],
                        "confidence": result.confidence,
                    }
                except Exception as e:
                    logger.warning(
                        "AI fallback activated",
                        extra={
                            "service": "advisor_entity_analysis",
                            "source": "fallback",
                            "reason": str(e),
                            "impact": "user receives hardcoded entity comparison instead of AI analysis",
                        },
                    )
            # Fallback: keep existing hardcoded comparison
            if not entity_comparison:
                entity_comparison = {
                    "sole_proprietorship": {
                        "tax": calculation.total_tax,
                        "se_tax": calculation.self_employment_tax
                    },
                    "s_corporation": {
                        "salary": business_income * 0.5,
                        "distribution": business_income * 0.5,
                        "se_tax_savings": business_income * 0.5 * 0.153,
                        "recommended": business_income > 50000
                    }
                }

        # 5-year projection
        five_year = {}
        if AI_CHAT_ENABLED:
            try:
                from services.ai.tax_reasoning_service import get_tax_reasoning_service
                reasoning = get_tax_reasoning_service()
                multi_year_result = await reasoning.analyze_multi_year_strategy(
                    current_situation=_summarize_profile(profile),
                    life_events="Standard planning scenario",
                    goals="Minimize tax liability and maximize savings",
                    years=5,
                )
                five_year = {
                    "ai_strategy": multi_year_result.analysis[:1000],
                    "recommendation": multi_year_result.recommendation,
                    "action_items": multi_year_result.action_items[:5],
                    "key_factors": multi_year_result.key_factors,
                }
            except Exception as e:
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "advisor_multi_year",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "user receives hardcoded 3% growth projection instead of AI strategy",
                    },
                )

        if not five_year:
            # Fallback: existing hardcoded 3% growth
            for year in range(2025, 2030):
                growth_factor = 1 + (0.03 * (year - 2025))  # 3% annual growth
                projected_income = (profile.get("total_income", 0) or 0) * growth_factor
                projected_tax = calculation.total_tax * growth_factor
                five_year[str(year)] = {
                    "income": float(money(projected_income)),
                    "tax": float(money(projected_tax)),
                    "savings_if_optimized": float(money(total_savings * growth_factor))
                }

        # Executive summary
        summary = await chat_engine.generate_executive_summary(profile, calculation, strategies)

        # Deduction analysis
        deduction_rec = "standard" if calculation.deduction_type == "standard" else "itemized"
        itemized_est = (
            (profile.get("mortgage_interest", 0) or 0) +
            (profile.get("property_taxes", 0) or 0) +
            min((profile.get("state_income_tax", 0) or 0), 10000) +
            (profile.get("charitable_donations", 0) or 0)
        )

        # Eligible credits
        credits = []
        if profile.get("dependents", 0) > 0:
            credits.append({
                "name": "Child Tax Credit",
                "amount": profile.get("dependents", 0) * 2000,
                "refundable": True
            })

        # Get urgency info
        urgency_level = "PLANNING"
        urgency_message = "Perfect timing for tax planning!"
        days_to_deadline = 365
        try:
            from services.cpa_intelligence_service import calculate_urgency_level
            urgency_level, urgency_message, days_to_deadline = calculate_urgency_level()
        except Exception:
            pass

        lead_score = chat_engine.calculate_lead_score(profile)

        return FullAnalysisResponse(
            session_id=request.session_id,
            current_tax=calculation,
            strategies=[StrategyRecommendation(**s.dict()) for s in strategies],
            total_potential_savings=total_savings,
            top_3_opportunities=[StrategyRecommendation(**s.dict()) for s in strategies[:3]],
            entity_comparison=entity_comparison,
            five_year_projection=five_year,
            executive_summary=summary,
            deduction_recommendation=f"Based on your situation, taking the **{deduction_rec} deduction** is optimal.",
            itemized_vs_standard={
                "standard": calculation.deductions,
                "itemized_estimate": itemized_est
            },
            eligible_credits=credits,
            confidence="high" if chat_engine.calculate_profile_completeness(profile) > 0.7 else "medium",
            complexity=chat_engine.determine_complexity(profile),
            urgency_level=urgency_level,
            urgency_message=urgency_message,
            days_to_deadline=days_to_deadline,
            lead_score=lead_score,
            report_ready=True
        )
    except Exception as e:
        logger.error(f"Full analysis error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to complete analysis. Please try again or contact support."
        )


_DOCUMENT_FIELD_MAP = {
    "wages": "total_income", "federal_wages": "total_income", "w2_wages": "w2_income",
    "federal_tax_withheld": "federal_withholding", "state_tax_withheld": "state_income_tax",
    "employer_state": "state",
    "nonemployee_compensation": "self_employment_income",
    "interest_income": "interest_income", "dividend_income": "dividend_income",
    "qualified_dividends": "qualified_dividends",
    "mortgage_interest_received": "mortgage_interest", "real_estate_taxes": "property_taxes",
    "ordinary_income": "k1_ordinary_income",
}


def _map_extracted_to_profile(extracted_fields: dict) -> dict:
    """Map OCR-extracted document fields to session profile keys."""
    updates = {}
    for key, value in extracted_fields.items():
        profile_key = _DOCUMENT_FIELD_MAP.get(key.lower())
        if profile_key and value is not None:
            try:
                updates[profile_key] = float(str(value).replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                updates[profile_key] = value
    return updates


@router.post("/upload-document")
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    document_type: str = Form(None),
    http_request: FastAPIRequest = None,
    _session: str = Depends(verify_session_token),
):
    """
    Upload and process a tax document with OCR.

    Supported documents: W-2, 1099, 1098, K-1, etc.
    """
    # SECURITY: Validate session_id (Form fields bypass Pydantic validators)
    if not _validate_uuid(session_id):
        raise HTTPException(400, "Invalid session ID format")

    try:
        # Try to use the unified tax advisor for OCR
        from services.unified_tax_advisor import UnifiedTaxAdvisor, DocumentType

        advisor = UnifiedTaxAdvisor()

        # Save uploaded file temporarily
        import tempfile
        import os

        _SAFE_DOC_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".gif", ".bmp", ".webp"}
        raw_ext = os.path.splitext(file.filename or "")[1].lower()
        safe_suffix = raw_ext if raw_ext in _SAFE_DOC_EXTENSIONS else ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=safe_suffix) as tmp:
            content = await file.read()

            # SECURITY: Magic-byte validation — reject spoofed files
            from web.utils.file_validation import validate_magic_bytes as _validate_magic
            detected_mime, _ = _validate_magic(content)
            if not detected_mime:
                raise HTTPException(400, "File content does not match a supported type (PDF, PNG, JPG, TIFF, GIF)")

            tmp.write(content)
            tmp_path = tmp.name

        try:
            # --- ML DOCUMENT CLASSIFICATION ---
            ml_classification = {}
            try:
                # Read text content for classification (if text-extractable)
                extracted_text = ""
                if safe_suffix == ".pdf":
                    try:
                        import fitz  # PyMuPDF
                        pdf_doc = fitz.open(tmp_path)
                        for page in pdf_doc:
                            extracted_text += page.get_text()
                        pdf_doc.close()
                    except Exception:
                        pass  # PDF text extraction optional
                elif safe_suffix in (".jpg", ".jpeg", ".png", ".tiff", ".tif"):
                    # Image — classifier can still work with OCR text from advisor
                    pass

                if extracted_text:
                    classifier = DocumentClassifier()
                    classification = classifier.classify(extracted_text)
                    ml_classification = {
                        "detected_type": classification.document_type,
                        "classification_confidence": classification.confidence,
                        "type_description": classification.document_type_description,
                        "expected_fields": _get_expected_fields_for_type(classification.document_type),
                    }
                    logger.info(
                        f"ML classified document as {classification.document_type} "
                        f"({classification.confidence:.0%} confidence)"
                    )

                    # Use ML classification if user didn't specify type and confidence is high
                    if not document_type and classification.confidence >= 0.7:
                        # Map ML doc types to DocumentType enum values
                        ml_type_map = {
                            "w2": "w2", "1099-nec": "1099_nec", "1099-int": "1099_int",
                            "1099-div": "1099_div", "1099-b": "1099_b", "1099-misc": "1099_misc",
                            "1098": "1098", "k1": "k1",
                        }
                        mapped_type = ml_type_map.get(classification.document_type)
                        if mapped_type:
                            try:
                                document_type = mapped_type
                            except Exception:
                                pass
            except Exception as e:
                logger.warning(f"ML classification failed (non-blocking): {e}")

            # Determine document type
            doc_type = DocumentType(document_type) if document_type else DocumentType.OTHER

            # Process document
            extracted = advisor.process_document(tmp_path, doc_type)

            # Auto-update session profile from extracted document data
            profile_updates = {}
            new_strategies_list = []
            updated_savings = 0
            try:
                profile_updates = _map_extracted_to_profile(extracted.extracted_fields)
                if profile_updates:
                    session = await chat_engine.get_or_create_session(session_id)
                    profile = session["profile"]
                    for k, v in profile_updates.items():
                        if v is not None and not profile.get(k):  # Don't overwrite existing
                            profile[k] = v
                    await chat_engine.update_session(session_id, {"profile": profile})

                    # Re-generate strategies if profile is now rich enough
                    if profile.get("total_income") and profile.get("filing_status"):
                        try:
                            calc = await chat_engine.get_tax_calculation(profile)
                            strats = await chat_engine.get_tax_strategies(profile, calc)
                            new_strategies_list = [s.dict() for s in strats[:5]]
                            updated_savings = sum(s.estimated_savings for s in strats)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Auto profile update from document failed: {e}")

            return {
                "success": True,
                "document_type": extracted.document_type.value,
                "extracted_fields": extracted.extracted_fields,
                "confidence": extracted.extraction_confidence,
                "needs_review": extracted.needs_review,
                "payer_name": extracted.payer_name,
                "ml_classification": ml_classification if ml_classification else None,
                "profile_updates": profile_updates,
                "new_strategies": new_strategies_list,
                "updated_savings": updated_savings,
                "message": f"Successfully extracted data from {file.filename}"
            }
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Document processing error: {e}")
        return {
            "success": False,
            "error": "Document processing failed",
            "message": "Unable to process document. Please try again or enter the information manually."
        }


# =============================================================================
# EXTRACTED ROUTES — now provided by sub-routers included below:
#   web/advisor/report_generation.py  (/report, /generate-report, /branding/*, /rate-limit/status, /report/email)
#   web/advisor/scenario_analysis.py  (/roth-analysis, /entity-analysis, /deduction-analysis, /audit-risk, /amt-analysis)
#   web/advisor/recommendations.py    (/acknowledge-standards, /strategies, /calculate, /unlock-strategies, /ai-metrics, /ai-routing-stats)
# =============================================================================





# Include report sub-router (safety check, PDF generation, universal reports)
try:
    from web.advisor.report_routes import _report_router
    router.include_router(_report_router)
except ImportError:
    logger.warning("advisor report_routes sub-module not available; report endpoints disabled")

# Include extracted sub-routers (decomposed from this monolith)
try:
    from web.advisor.scenario_analysis import router as _scenario_router
    router.include_router(_scenario_router)
    logger.info("Included scenario_analysis sub-router")
except ImportError as e:
    logger.warning(f"scenario_analysis sub-router not available: {e}")

try:
    from web.advisor.recommendations import router as _rec_router
    router.include_router(_rec_router)
    logger.info("Included recommendations sub-router")
except ImportError as e:
    logger.warning(f"recommendations sub-router not available: {e}")

try:
    from web.advisor.report_generation import router as _report_gen_router
    router.include_router(_report_gen_router)
    logger.info("Included report_generation sub-router")
except ImportError as e:
    logger.warning(f"report_generation sub-router not available: {e}")


# Register the router
def register_intelligent_advisor_routes(app):
    """Register the intelligent advisor routes with the main app."""
    app.include_router(router)
    logger.info("Intelligent Advisor API routes registered at /api/advisor")
