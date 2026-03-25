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
# Check if any AI provider is actually configured (not placeholder values)
def _is_real_key(key_name):
    val = os.environ.get(key_name, "")
    return val and not val.startswith("REPLACE") and not val.startswith("your_") and len(val) > 20

_HAS_AI_PROVIDER = any(_is_real_key(k) for k in [
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "PERPLEXITY_API_KEY"
])

AI_CHAT_ENABLED = _HAS_AI_PROVIDER and os.environ.get("AI_CHAT_ENABLED", "true").lower() == "true"
AI_REPORT_NARRATIVES_ENABLED = _HAS_AI_PROVIDER and os.environ.get("AI_REPORT_NARRATIVES_ENABLED", "true").lower() == "true"
AI_SAFETY_CHECKS_ENABLED = _HAS_AI_PROVIDER and os.environ.get("AI_SAFETY_CHECKS_ENABLED", "true").lower() == "true"
AI_OPPORTUNITIES_ENABLED = _HAS_AI_PROVIDER and os.environ.get("AI_OPPORTUNITIES_ENABLED", "true").lower() == "true"
AI_RECOMMENDATIONS_ENABLED = _HAS_AI_PROVIDER and os.environ.get("AI_RECOMMENDATIONS_ENABLED", "true").lower() == "true"
AI_ENTITY_EXTRACTION_ENABLED = _HAS_AI_PROVIDER and os.environ.get("AI_ENTITY_EXTRACTION_ENABLED", "true").lower() == "true"
# AI_ADAPTIVE_QUESTIONS removed — replaced by hybrid flow (sequential + freeform + confirmation)

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
        started_business=profile.get("income_type") in ("self_employed", "business_owner", "gig_worker", "farmer", "clergy")
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
        "is_self_employed": profile.get("income_type") in ("self_employed", "business_owner", "gig_worker", "farmer", "clergy")
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

            # Try to recover token from sessions_api persistence
            existing_token = None
            if self._sqlite_persistence:
                try:
                    existing_record = self._sqlite_persistence.load_session(session_id)
                    if existing_record and existing_record.data:
                        data = existing_record.data if isinstance(existing_record.data, dict) else {}
                        existing_token = data.get(SESSION_TOKEN_KEY)
                except Exception:
                    pass

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
                SESSION_TOKEN_KEY: existing_token or generate_session_token(),
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

        # Estimate marginal rate from 2025 brackets (Rev. Proc. 2024-40)
        if status == "married_joint":
            brackets = [(23850, .10), (96950, .12), (206700, .22), (394600, .24), (501050, .32), (751600, .35)]
        else:
            brackets = [(11925, .10), (48475, .12), (103350, .22), (197300, .24), (250525, .32), (626350, .35)]
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
        "single": 197300,
        "married_joint": 394600,
        "married_separate": 197300,
        "head_of_household": 197300,
        "qualifying_widow": 394600
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

    def _calculate_ltcg_tax(self, ltcg, filing_status, taxable_ordinary_income):
        """Calculate long-term capital gains tax at preferential rates (0/15/20%)."""
        thresholds = {
            "single": (48350, 533400),
            "married_joint": (96700, 600050),
            "head_of_household": (64750, 566700),
            "married_separate": (48350, 300025),
            "qualifying_widow": (96700, 600050),
        }
        zero_thresh, fifteen_thresh = thresholds.get(filing_status, (48350, 533400))

        # Stack LTCG on top of ordinary income
        stacked_start = taxable_ordinary_income

        tax = 0
        # 0% bracket
        if stacked_start < zero_thresh:
            zero_amount = min(ltcg, zero_thresh - stacked_start)
            tax += zero_amount * 0  # 0%
            ltcg -= zero_amount
            stacked_start += zero_amount
        # 15% bracket
        if ltcg > 0 and stacked_start < fifteen_thresh:
            fifteen_amount = min(ltcg, fifteen_thresh - stacked_start)
            tax += fifteen_amount * 0.15
            ltcg -= fifteen_amount
            stacked_start += fifteen_amount
        # 20% bracket
        if ltcg > 0:
            tax += ltcg * 0.20

        return tax

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
        multiplier = 1.5 if filing_status in ["married_joint", "qualifying_widow"] else 1.0

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
        """Calculate Child Tax Credit + Other Dependent Credit with phase-out - IRC §24."""
        dependents = profile.get("dependents", 0) or 0
        if dependents <= 0:
            return 0.0

        under_17 = profile.get("dependents_under_17")
        if under_17 is None or under_17 == -1:
            under_17 = dependents  # backward compat: assume all are CTC-eligible
        under_17 = min(under_17, dependents)
        over_17 = dependents - under_17

        ctc_per_child = 2000
        odc_per_dependent = 500
        filing_status = profile.get("filing_status", "single")

        # Phase-out thresholds (2025)
        threshold = 400000 if filing_status in ("married_joint", "qualifying_widow") else 200000

        total_credit = (under_17 * ctc_per_child) + (over_17 * odc_per_dependent)

        if agi > threshold:
            reduction = ((agi - threshold) // 1000) * 50
            total_credit = max(0, total_credit - reduction)

        return total_credit

    def _calculate_eitc(self, profile, agi):
        """Calculate Earned Income Tax Credit (2025 parameters)."""
        filing_status = profile.get("filing_status", "single")
        dependents = profile.get("dependents", 0) or 0
        earned_income = (profile.get("w2_income", 0) or 0) + (profile.get("business_income", 0) or 0)
        investment_income = (profile.get("investment_income", 0) or 0) + (profile.get("interest_income", 0) or 0) + (profile.get("dividend_income", 0) or 0)

        # Investment income disqualification ($11,950 for 2025)
        if investment_income > 11950:
            return 0

        # Cannot use MFS
        if filing_status == "married_separate":
            return 0

        # 2025 EITC parameters by number of qualifying children
        # (max_credit, phase_in_rate, phase_out_rate, phase_out_start_single, phase_out_start_mfj, income_limit_single, income_limit_mfj)
        eitc_params = {
            0: (649, 0.0765, 0.0765, 10620, 17640, 19104, 26214),
            1: (3733, 0.34, 0.1598, 12730, 19750, 46560, 53610),
            2: (6164, 0.40, 0.2106, 12730, 19750, 52918, 59968),
            3: (7830, 0.45, 0.2106, 12730, 19750, 56838, 63888),
        }

        children = min(dependents, 3)  # EITC maxes at 3 children
        params = eitc_params[children]
        max_credit, phase_in_rate, phase_out_rate, po_start_single, po_start_mfj, limit_single, limit_mfj = params

        is_joint = filing_status in ("married_joint", "qualifying_widow")
        po_start = po_start_mfj if is_joint else po_start_single
        income_limit = limit_mfj if is_joint else limit_single

        # Check income limit
        compare_income = max(agi, earned_income)
        if compare_income > income_limit:
            return 0

        # Phase-in: credit builds as earned income increases
        credit = min(earned_income * phase_in_rate, max_credit)

        # Phase-out: credit reduces as income exceeds threshold
        if compare_income > po_start:
            reduction = (compare_income - po_start) * phase_out_rate
            credit = max(0, credit - reduction)

        return round(min(credit, max_credit), 2)

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

        # Separate LTCG from ordinary income for preferential rate treatment
        ltcg_in_taxable = min(
            profile.get("capital_gains_long", 0) or profile.get("capital_gains", 0) or 0,
            taxable_income,
        )
        taxable_ordinary_income = max(0, taxable_income - ltcg_in_taxable)

        # Calculate federal income tax on ordinary income only
        federal_tax, marginal_rate = self._calculate_federal_tax(taxable_ordinary_income, filing_status)

        # Calculate LTCG tax at preferential rates (0/15/20%)
        if ltcg_in_taxable > 0:
            federal_tax += self._calculate_ltcg_tax(ltcg_in_taxable, filing_status, taxable_ordinary_income)

        # Calculate Child Tax Credit
        ctc = self._calculate_child_tax_credit(profile, agi)
        federal_tax = max(0, federal_tax - ctc)

        # Calculate AMT
        amt = self._calculate_amt(profile, federal_tax, agi)
        federal_tax += amt

        # Calculate NIIT
        niit = self._calculate_niit(profile, agi)
        federal_tax += niit

        # Calculate EITC (refundable credit — reduces total tax, can create refund)
        eitc = self._calculate_eitc(profile, agi)

        # Calculate state tax using progressive brackets
        state_tax = self._calculate_state_tax(agi, state, filing_status)

        # Total tax
        total_tax = federal_tax + se_tax + state_tax - eitc
        effective_rate = (total_tax / income * 100) if income > 0 else 0

        # Calculate withholding/payments vs tax owed
        withholding = profile.get("federal_withholding", 0) or 0
        # Auto-estimate withholding if user chose "estimate for me" or never answered
        if withholding == 0 and not profile.get("is_self_employed"):
            w2_income = profile.get("w2_income", 0) or profile.get("total_income", 0) or 0
            if w2_income > 0:
                # Average effective withholding rate approximation by income bracket
                if w2_income < 40000:
                    withholding = w2_income * 0.10
                elif w2_income < 90000:
                    withholding = w2_income * 0.15
                elif w2_income < 200000:
                    withholding = w2_income * 0.18
                else:
                    withholding = w2_income * 0.22
        estimated_payments = profile.get("estimated_payments", 0) or 0
        total_payments = withholding + estimated_payments
        refund_or_owed = total_payments - total_tax

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
        if eitc > 0:
            tax_notices.append(f"Earned Income Credit: ${eitc:,.0f} (refundable)")

        # Calculate capital gains info
        short_term_gains = profile.get("capital_gains_short", 0) or 0
        long_term_gains = profile.get("capital_gains_long", 0) or profile.get("capital_gains", 0) or 0
        # Preferential rate on LTCG (0/15/20% stacked on ordinary income)
        capital_gains_tax = self._calculate_ltcg_tax(long_term_gains, filing_status, taxable_ordinary_income) if long_term_gains > 0 else 0
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
        if filing_status in ["married_joint", "married_filing_jointly", "married filing jointly"]:
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
            mega_contribution = 46500  # 2025 limit: $70,000 total - $23,500 employee
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
        if profile.get("hsa_contributions") is not None or profile.get("has_hsa") or profile.get("income_type") in ("w2_employee", "multiple_w2", "w2_plus_side", "self_employed", "business_owner", "gig_worker", "farmer", "clergy", "military"):
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
                savings += 3000 * marginal_rate  # $3k ordinary income offset (Section 1211)
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
        metrics = get_ai_metrics_service() if get_ai_metrics_service else None
        for s in strategies:
            if s.metadata is None:
                s.metadata = {"_source": "template"}
            populated = sum(1 for v in [s.summary, s.detailed_explanation, s.action_steps, s.irs_reference, s.estimated_savings, s.confidence] if v)
            source = s.metadata.get("_source", "template")
            if metrics:
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



def _quick_tax_estimate(profile: dict) -> dict:
    """Fast partial tax estimate from available profile data.

    Returns: {"amount": int (+ = refund, - = owed), "confidence": str, "label": str}
    Called after every answer that affects tax numbers to power the live refund counter.
    """
    income = float(profile.get("total_income", 0) or 0)
    status = profile.get("filing_status", "single")
    if not income or not status:
        return {"amount": 0, "confidence": "none", "label": ""}

    # 1. Standard deduction (2025)
    std_ded = {"single": 15000, "married_joint": 30000, "head_of_household": 22500,
               "married_separate": 15000, "qualifying_widow": 30000}.get(status, 15000)

    # Bonus standard deduction for 65+
    age = profile.get("age")
    if age and (age == "age_65_plus" or (isinstance(age, (int, float)) and age >= 65)):
        std_ded += 1950 if status in ("single", "head_of_household") else 1550
    if profile.get("legally_blind") in ("taxpayer", "both"):
        std_ded += 1950 if status in ("single", "head_of_household") else 1550

    # 2. Itemized deductions
    mortgage = float(profile.get("mortgage_interest", 0) or 0)
    prop_tax = float(profile.get("property_taxes", 0) or 0)
    charity = float(profile.get("charitable_donations", 0) or 0)
    medical = float(profile.get("medical_expenses", 0) or 0)
    salt_other = float(profile.get("state_withholding", 0) or 0)
    salt_total = min(prop_tax + salt_other, 10000)  # SALT cap
    medical_ded = max(0, medical - income * 0.075)  # 7.5% AGI threshold
    itemized = mortgage + salt_total + charity + medical_ded

    deduction = max(std_ded, itemized)

    # 3. Above-the-line adjustments
    above_line = 0
    ret_401k = float(profile.get("retirement_401k", 0) or 0)
    ret_ira = float(profile.get("retirement_ira", 0) or 0)
    hsa = float(profile.get("hsa_contributions", 0) or 0)
    student_loan = float(profile.get("student_loan_amount", 0) or 0) or float(profile.get("student_loan_interest", 0) or 0)
    if isinstance(student_loan, str):
        student_loan = 0
    above_line += ret_401k + ret_ira + hsa + min(student_loan, 2500)

    # SE tax deduction (50% of SE tax)
    biz_income = float(profile.get("business_income", 0) or 0)
    if profile.get("is_self_employed") and biz_income > 0:
        se_tax = biz_income * 0.9235 * 0.153
        above_line += se_tax * 0.5

    # 4. Taxable income
    taxable = max(0, income - deduction - above_line)

    # 5. Progressive tax calculation (2025 brackets — Rev. Proc. 2024-40)
    if status == "married_joint" or status == "qualifying_widow":
        brackets = [(23850, 0.10), (96950, 0.12), (206700, 0.22), (394600, 0.24),
                    (501050, 0.32), (751600, 0.35), (float("inf"), 0.37)]
    elif status == "head_of_household":
        brackets = [(17000, 0.10), (64850, 0.12), (103350, 0.22), (197300, 0.24),
                    (250500, 0.32), (626350, 0.35), (float("inf"), 0.37)]
    else:  # single or MFS
        brackets = [(11925, 0.10), (48475, 0.12), (103350, 0.22), (197300, 0.24),
                    (250525, 0.32), (626350, 0.35), (float("inf"), 0.37)]

    tax = 0
    prev = 0
    for top, rate in brackets:
        bracket_income = min(taxable, top) - prev
        if bracket_income <= 0:
            break
        tax += bracket_income * rate
        prev = top

    # 6. Self-employment tax
    se_tax_total = 0
    if profile.get("is_self_employed") and biz_income > 0:
        se_tax_total = biz_income * 0.9235 * 0.153

    # 7. NIIT (3.8% on investment income over threshold)
    niit = 0
    inv_income = float(profile.get("investment_income", 0) or 0)
    niit_threshold = 250000 if status == "married_joint" else 200000
    if income > niit_threshold and inv_income > 0:
        niit = min(inv_income, income - niit_threshold) * 0.038

    # 8. Credits
    credits = 0
    under_17 = int(profile.get("dependents_under_17", 0) or 0)
    credits += under_17 * 2000  # CTC

    childcare = float(profile.get("childcare_costs", 0) or 0)
    if isinstance(childcare, str):
        childcare = 0
    if childcare > 0:
        max_expense = 3000 if under_17 <= 1 else 6000
        credits += min(childcare, max_expense) * 0.20

    # Solar credit
    solar = float(profile.get("solar_cost", 0) or 0)
    if solar > 0:
        credits += solar * 0.30

    # EV credit
    ev = profile.get("ev_detail")
    if ev == "ev_new_qualified":
        credits += 7500
    elif ev == "ev_used_qualified":
        credits += 4000

    # Education credits
    if profile.get("education_credit_type") == "aotc":
        credits += 2500
    elif profile.get("education_credit_type") in ("llc", "vocational"):
        credits += 2000

    # 9. Total tax
    total_tax = max(0, tax + se_tax_total + niit - credits)

    # 10. Payments
    withholding = float(profile.get("federal_withholding", 0) or 0)
    estimated = float(profile.get("estimated_payments", 0) or 0)
    total_payments = withholding + estimated

    # 11. Refund or owed
    result = total_payments - total_tax  # Positive = refund

    # 12. Confidence
    confidence = "none"
    if withholding > 0 or estimated > 0:
        confidence = "medium"
        if profile.get("_asked_deductions") or profile.get("_deduction_check"):
            confidence = "high"
    elif income > 0:
        confidence = "low"

    # 13. Label
    if confidence == "none":
        label = ""
    elif result >= 0:
        label = f"Estimated refund: ~${abs(result):,.0f}"
    else:
        label = f"Estimated owed: ~${abs(result):,.0f}"

    return {"amount": round(result), "confidence": confidence, "label": label}


def _get_proactive_advice(profile: dict, updates: dict) -> str:
    """Generate proactive tax advice based on what was just answered.

    Returns advice text to prepend to the next question, or empty string.
    """
    advice_parts = []
    income = float(profile.get("total_income", 0) or 0)

    # Mortgage + property tax → itemization recommendation
    mortgage = float(profile.get("mortgage_interest", 0) or 0)
    prop_tax = float(profile.get("property_taxes", 0) or 0)
    if "mortgage_interest" in updates or "property_taxes" in updates:
        total_item = mortgage + prop_tax + float(profile.get("charitable_donations", 0) or 0)
        std_ded = {"single": 15000, "married_joint": 30000, "head_of_household": 22500}.get(
            profile.get("filing_status", "single"), 15000)
        if total_item > std_ded:
            advice_parts.append(f"💡 With ${total_item:,.0f} in deductions, you'll save more by itemizing (standard deduction is ${std_ded:,.0f}).")

    # SALT cap hit
    if "property_taxes" in updates and prop_tax >= 10000:
        advice_parts.append("⚠️ Your property taxes alone hit the $10,000 SALT cap.")

    # SE no estimated payments
    if "business_income" in updates and float(updates.get("business_income", 0) or 0) > 30000:
        if not profile.get("estimated_payments") and not profile.get("_asked_estimated"):
            advice_parts.append("⚠️ With this business income, make sure you've made quarterly estimated payments to avoid penalties.")

    # CTC notification
    if "dependents_under_17" in updates:
        n = int(updates.get("dependents_under_17", 0) or 0)
        if n > 0:
            advice_parts.append(f"💰 With {n} child(ren) under 17, you qualify for ${n * 2000:,.0f} in Child Tax Credits!")

    # Retirement gap
    if "retirement_401k" in updates:
        current = float(updates.get("retirement_401k", 0) or 0)
        max_401k = 23500
        age = profile.get("age")
        if age and (age == "age_50_64" or age == "age_65_plus" or (isinstance(age, (int, float)) and age >= 50)):
            max_401k = 31000
        if 0 < current < max_401k and income > 75000:
            gap = max_401k - current
            rate = 0.22 if income < 200000 else 0.32
            savings = round(gap * rate)
            advice_parts.append(f"💡 You're contributing ${current:,.0f} to your 401(k) — the max is ${max_401k:,.0f}. Increasing could save ~${savings:,.0f} in taxes.")

    # Solar credit
    if "solar_cost" in updates:
        cost = float(updates.get("solar_cost", 0) or 0)
        if cost > 0:
            credit = round(cost * 0.30)
            advice_parts.append(f"🎉 Your solar installation qualifies for a 30% credit — that's ${credit:,.0f} off your tax bill!")

    # ── Multi-Year Awareness (Feature 10) ───────────────────────────────
    # Prior year context
    if "prior_year_return" in updates:
        prior = updates.get("prior_year_return")
        if prior == "owed":
            advice_parts.append("⚠️ Since you owed last year, let's make sure your withholding and estimated payments are adequate this year to avoid underpayment penalties.")
        elif prior == "refund":
            advice_parts.append("💡 You got a refund last year — that means you may be over-withholding. We can check if adjusting your W-4 would give you more money in each paycheck.")

    # Capital loss carryforward context
    if "loss_carryforward" in updates and updates.get("loss_carryforward") not in (False, "no_loss_carryforward"):
        advice_parts.append("💡 Your capital loss carryforward from prior years reduces your taxable income — up to $3,000 per year against ordinary income, with the rest carrying forward.")

    # NOL carryforward context
    if "nol_carryforward" in updates and updates.get("nol_carryforward") not in (False, "no_nol"):
        advice_parts.append("💡 Your Net Operating Loss carryforward can offset up to 80% of current year taxable income — a significant tax reduction.")

    # Inherited IRA context (SECURE Act)
    if "inherited_ira" in updates:
        val = updates.get("inherited_ira")
        if val == "post_2020":
            advice_parts.append("⚠️ Under the SECURE Act's 10-year rule, you must withdraw the entire inherited IRA by the end of year 10. Planning distributions strategically can minimize the tax hit.")
        elif val == "pre_2020":
            advice_parts.append("💡 Your inherited IRA uses the older 'stretch' rules — you take distributions based on your life expectancy, which can be very tax-efficient.")
        elif val == "spouse":
            advice_parts.append("💡 As a spouse beneficiary, you have the most flexible options — you can treat the IRA as your own, roll it over, or use the beneficiary rules.")

    return "\n".join(advice_parts)


def _estimate_smart_default(field: str, profile: dict) -> dict:
    """Estimate reasonable default values based on profile data.
    Returns dict with {value, text, actions, smart_value} or None."""
    income = float(profile.get("total_income", 0) or 0)
    status = profile.get("filing_status", "single")
    if not income or not status:
        return None

    if field == "federal_withholding":
        if status == "married_joint":
            if income <= 30000: rate = 0.04
            elif income <= 90000: rate = 0.08
            elif income <= 200000: rate = 0.12
            elif income <= 400000: rate = 0.17
            else: rate = 0.22
        else:
            if income <= 15000: rate = 0.04
            elif income <= 50000: rate = 0.09
            elif income <= 100000: rate = 0.13
            elif income <= 200000: rate = 0.17
            else: rate = 0.24
        est = round(income * rate / 100) * 100
        return {
            "smart_value": est,
            "text": f"Based on your ${income:,.0f} income filing as {status.replace('_', ' ')}, your federal withholding is probably around ${est:,.0f}. Does that sound right?",
            "actions": [
                {"label": f"Yes, ~${est:,.0f} sounds right", "value": "withholding_smart_default"},
                {"label": "It's different — let me enter it", "value": "withholding_manual_entry"},
                {"label": "Not sure — estimate for me", "value": "withholding_estimate"},
            ],
        }

    if field == "state_withholding":
        state = profile.get("state", "")
        _NO_TAX = {"TX", "FL", "WA", "NV", "WY", "SD", "AK", "NH", "TN"}
        if state in _NO_TAX:
            return None
        rates = {"CA": 0.055, "NY": 0.055, "NJ": 0.05, "OR": 0.07, "HI": 0.06,
                 "MN": 0.055, "CT": 0.05, "MA": 0.05, "IL": 0.0495, "PA": 0.0307,
                 "VA": 0.04, "GA": 0.045, "NC": 0.0475, "CO": 0.044, "MD": 0.05}
        rate = rates.get(state, 0.04)
        est = round(income * rate / 100) * 100
        return {
            "smart_value": est,
            "text": f"Your {state} state withholding is probably around ${est:,.0f}. Does that sound right?",
            "actions": [
                {"label": f"Yes, ~${est:,.0f}", "value": "state_wh_smart_default"},
                {"label": "Let me enter exact amount", "value": "state_wh_manual"},
                {"label": "Skip", "value": "skip_state_withholding"},
            ],
        }
    return None


def _get_simple_explanation(message: str, profile: dict) -> str:
    """Plain-English tax term explanations for confused users (Feature 7)."""
    explanations = {
        "filing status": "Your filing status determines your tax brackets. Most people are Single (unmarried) or Married Filing Jointly (married, one return).",
        "head of household": "For unmarried people who pay >50% of household costs for a dependent. Better brackets than Single.",
        "standard deduction": "An amount you subtract from income before calculating tax. 2025: $15,000 Single, $30,000 MFJ.",
        "itemize": "Listing actual deductions (mortgage, charity, etc.) instead of the standard deduction. Do it if your deductions exceed the standard.",
        "salt": "State And Local Taxes — income tax + property taxes. Capped at $10,000 deduction.",
        "amt": "Alternative Minimum Tax — ensures high earners pay at least a minimum. Mainly affects people with stock options or large state tax deductions.",
        "niit": "3.8% surtax on investment income if income exceeds $200K (single) / $250K (married).",
        "qbi": "Qualified Business Income deduction — self-employed may deduct 20% of business income.",
        "eitc": "Earned Income Tax Credit — refundable credit worth up to $7,430 for lower-income working families.",
        "hsa": "Health Savings Account — triple tax benefit: deductible contributions, tax-free growth, tax-free medical withdrawals.",
        "401k": "Employer retirement account. Contributions reduce taxable income. 2025 limit: $23,500 ($31,000 if 50+).",
        "ira": "Individual Retirement Account. Traditional = tax-deductible contributions. Roth = tax-free withdrawals in retirement.",
        "k-1": "Tax form from partnerships, S-Corps, or trusts showing your share of income.",
        "estimated payment": "Quarterly tax payments to IRS (Apr/Jun/Sep/Jan). Required for self-employed or income without withholding.",
        "withholding": "Tax your employer takes from each paycheck and sends to IRS. It's a prepayment of your annual tax.",
        "capital gain": "Profit from selling investments. Long-term (held >1 year) = lower tax rates. Short-term = regular income rates.",
        "backdoor roth": "Strategy for high earners: contribute to Traditional IRA (non-deductible), then convert to Roth. Gets around income limits.",
        "se tax": "Self-employment tax = 15.3% for Social Security + Medicare. You can deduct half of it.",
        "roth": "Roth accounts use after-tax money but all future growth and withdrawals are completely tax-free.",
    }
    msg = message.lower()
    for term, explanation in explanations.items():
        if term in msg:
            return explanation
    return "Tax terms can be confusing — ask about any term and I'll explain it simply."


_MULTI_SELECT_KEYWORDS = frozenset([
    "check your deductions",
    "major life changes",
    "energy-efficient",
])


def _is_multi_select_question(question_text: str) -> bool:
    """Return True if this question allows multiple selections."""
    t = question_text.lower()
    return any(kw in t for kw in _MULTI_SELECT_KEYWORDS)


def _get_topic_for_question(question_text: str) -> tuple:
    """Return (topic_name, topic_number) based on question content."""
    t = question_text.lower()
    if any(k in t for k in ["withholding", "withheld", "w-2", "side income", "side hustle", "entity", "business income", "salary", "spouse", "gig", "farm", "clergy", "1099", "tip", "statutory", "unemployment", "disability", "royalty", "interest income", "canceled debt", "hobby", "director", "barter", "jury", "annuity", "hsa distribut"]):
        return ("Income Details", 1)
    if any(k in t for k in ["dependent", "child", "custody", "education", "529", "college", "hoh", "qualifying surviving", "disabled dep", "ssn", "itin", "adoption"]):
        return ("Your Family", 2)
    if any(k in t for k in ["life change", "married", "divorce", "baby", "sold", "bought", "moved", "inherit", "job change", "job loss", "started a business", "spouse pass"]):
        return ("Life Events", 3)
    if any(k in t for k in ["investment", "crypto", "stock", "capital gain", "wash sale", "niit", "installment", "1031", "qsbs", "opportunity zone", "collectible", "margin", "passive", "mlp", "espp", "iso", "section 1256", "retirement", "401", "ira", "hsa", "rmd", "distribution", "backdoor", "catch-up", "mega", "eitc", "saver", "elderly"]):
        return ("Investments & Retirement", 4)
    if any(k in t for k in ["deduction", "mortgage", "charit", "medical", "student loan", "educator", "casualty", "home office", "meals", "travel", "insurance", "nol", "inventory", "accounting", "listed property", "qbi", "property tax", "salt"]):
        return ("Deductions & Credits", 5)
    if any(k in t for k in ["estimated", "energy", "solar", "electric vehicle", "foreign", "fbar", "fatca", "treaty", "pfic", "gambling", "amt", "alimony", "household employee", "state refund", "prize", "community property", "excess social", "ip pin", "local tax", "state withhold", "multi-state", "remote work", "extension", "refund", "prior year", "amended", "bankruptcy", "underpayment", "state credit"]):
        return ("Final Checks", 6)
    return ("Additional Details", 6)


def _build_profile_summary(profile: dict) -> dict:
    """Build organized profile summary for the confirmation screen."""
    return {
        "basics": {
            "filing_status": profile.get("filing_status"),
            "state": profile.get("state"),
            "dependents": profile.get("dependents", 0),
            "age": profile.get("age"),
            "income_type": profile.get("income_type"),
        },
        "income": {k: v for k, v in {
            "total_income": profile.get("total_income"),
            "business_income": profile.get("business_income"),
            "investment_income": profile.get("investment_income"),
            "rental_income": profile.get("rental_income"),
            "k1_ordinary_income": profile.get("k1_ordinary_income"),
            "ss_benefits": profile.get("ss_benefits"),
            "spouse_income": profile.get("spouse_income"),
            "side_income": profile.get("side_income"),
            "farm_income": profile.get("farm_income"),
        }.items() if v},
        "deductions": {k: v for k, v in {
            "mortgage_interest": profile.get("mortgage_interest"),
            "property_taxes": profile.get("property_taxes"),
            "charitable_donations": profile.get("charitable_donations"),
            "medical_expenses": profile.get("medical_expenses"),
            "student_loan_interest": profile.get("student_loan_interest"),
            "student_loan_amount": profile.get("student_loan_amount"),
        }.items() if v},
        "credits": {k: v for k, v in {
            "dependents_under_17": profile.get("dependents_under_17"),
            "childcare_costs": profile.get("childcare_costs"),
            "education_status": profile.get("education_status"),
            "energy_credits": profile.get("energy_credits"),
            "solar_cost": profile.get("solar_cost"),
            "ev_detail": profile.get("ev_detail"),
        }.items() if v},
        "retirement": {k: v for k, v in {
            "retirement_401k": profile.get("retirement_401k"),
            "retirement_ira": profile.get("retirement_ira"),
            "hsa_contributions": profile.get("hsa_contributions"),
            "backdoor_roth": profile.get("backdoor_roth"),
        }.items() if v},
        "payments": {k: v for k, v in {
            "federal_withholding": profile.get("federal_withholding"),
            "estimated_payments": profile.get("estimated_payments"),
            "state_withholding": profile.get("state_withholding"),
        }.items() if v},
    }


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
                {"label": "Married Filing Separately", "value": "married_separate"},
                {"label": "Qualifying Surviving Spouse", "value": "qualifying_widow"}
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
            "What best describes your income situation?",
            [
                {"label": "W-2 Employee (single job)", "value": "w2_employee"},
                {"label": "Multiple W-2 Jobs", "value": "multiple_w2"},
                {"label": "W-2 + Side Hustle / Freelance", "value": "w2_plus_side"},
                {"label": "Self-Employed / Freelancer (full-time)", "value": "self_employed"},
                {"label": "Business Owner (LLC / S-Corp / Partnership)", "value": "business_owner"},
                {"label": "Retired / Pension", "value": "retired"},
                {"label": "Primarily Investment Income", "value": "investor"},
                {"label": "Military", "value": "military"},
                {"label": "Full-time Gig Worker (Uber, DoorDash, Instacart)", "value": "gig_worker"},
                {"label": "Farmer / Agricultural", "value": "farmer"},
                {"label": "Clergy / Minister", "value": "clergy"},
                {"label": "Not currently working / No income", "value": "no_income"}
            ]
        )

    # =========================================================================
    # PHASE 2: Deep dive — sequential, profile-aware follow-ups
    #
    # The order below mirrors how a real tax preparer interviews a client:
    #   A. Income-type-specific details (W-2 → withholding, SE → business, etc.)
    #   B. Age
    #   C. Spouse details (MFJ only)
    #   D. Dependent details (if has dependents)
    #   E. Life events
    #   F. Investments
    #   G. Retirement & savings (non-retired)
    #   H. Deductions
    #   I. Rental property
    #   J. K-1 income (gated — not for low-income W-2)
    #   K. Healthcare
    #   L. Estimated tax payments
    #   M. Special situations
    #   N. State-specific
    #
    # User can skip any question with the "Skip" button.
    # =========================================================================

    if profile.get("_skip_deep_dive"):
        return (None, None)

    _NO_INCOME_TAX_STATES = {"TX", "FL", "WA", "NV", "WY", "SD", "AK", "NH", "TN"}
    total_income = float(profile.get("total_income", 0) or 0)
    income_type = profile.get("income_type", "")
    filing_status = profile.get("filing_status", "")
    dependents = profile.get("dependents", 0) or 0
    is_se = income_type in ("self_employed", "business_owner", "w2_plus_side", "gig_worker", "farmer", "clergy") or profile.get("is_self_employed")
    is_w2 = income_type in ("w2_employee", "multiple_w2", "w2_plus_side", "military")
    is_retired = income_type == "retired"
    is_military = income_type == "military"
    is_investor = income_type == "investor"

    # =========================================================================
    # ADAPTIVE INTELLIGENCE LAYER
    #
    # Sits between profile setup and the sequential blocks. Analyzes:
    #   1. Conversation context (last 5 user messages) for topic keywords
    #   2. Profile signals (income level, complexity indicators)
    #   3. Urgency signals (mentioned penalties, deadlines, audit)
    #
    # When it detects a strong signal, it PULLS FORWARD the most relevant
    # unanswered question — jumping ahead of the normal sequential order.
    # This means a user who says "I sold some Bitcoin" will get the crypto
    # question IMMEDIATELY, not after 20 other questions.
    #
    # If no strong signal is detected, falls through to normal sequential flow.
    # =========================================================================

    # Build conversation context from last 5 user messages
    _conv_context = ""
    if isinstance(session, dict):
        _conv_msgs = session.get("conversation", [])
        if _conv_msgs:
            _conv_context = " ".join(
                m.get("content", "") for m in _conv_msgs[-5:]
                if m.get("role") == "user"
            ).lower()

    # Only activate if we have conversation context to analyze
    if _conv_context:

        # ── Priority signal detection ────────────────────────────────────
        # Each signal: (keywords_to_detect, profile_field_to_check, question_to_ask)
        # If keywords found in context AND question not yet answered → jump to it

        _context_signals = [
            # ── CRYPTO (most commonly volunteered, most commonly missed) ──
            (
                ["bitcoin", "crypto", "ethereum", "nft", "defi", "mining", "staking", "coinbase", "binance"],
                "crypto_activity", "_asked_crypto",
                "Did you have any cryptocurrency activity? (Trading, mining, staking, DeFi, NFTs)",
                [
                    {"label": "Yes — trading / selling crypto", "value": "crypto_trading"},
                    {"label": "Yes — mining or staking", "value": "crypto_mining"},
                    {"label": "Yes — multiple activities", "value": "crypto_multiple"},
                    {"label": "No crypto activity", "value": "no_crypto"},
                    {"label": "Skip", "value": "skip_crypto"},
                ]
            ),
            # ── RENTAL PROPERTY ──
            (
                ["rental", "landlord", "tenant", "airbnb", "vrbo", "property manager", "rental income"],
                "_has_rental", "_asked_rental",
                "Do you own any rental properties?",
                [
                    {"label": "Yes — 1 property", "value": "rental_1"},
                    {"label": "Yes — 2-4 properties", "value": "rental_2_4"},
                    {"label": "Yes — 5+ properties", "value": "rental_5plus"},
                    {"label": "No rental properties", "value": "no_rental"},
                    {"label": "Skip", "value": "skip_rental"},
                ]
            ),
            # ── STOCK OPTIONS / RSU ──
            (
                ["rsu", "stock option", "vesting", "espp", "equity", "ipo", "restricted stock"],
                "stock_compensation", "_asked_stock_comp",
                "Do you have any employer stock compensation? (Stock options, RSUs, or ESPP)",
                [
                    {"label": "Incentive Stock Options (ISO)", "value": "has_iso"},
                    {"label": "Non-Qualified Options (NSO)", "value": "has_nso"},
                    {"label": "Restricted Stock Units (RSU)", "value": "has_rsu"},
                    {"label": "Employee Stock Purchase Plan (ESPP)", "value": "has_espp"},
                    {"label": "Multiple types", "value": "multiple_stock_comp"},
                    {"label": "None", "value": "no_stock_comp"},
                    {"label": "Skip", "value": "skip_stock_comp"},
                ]
            ),
            # ── HOME SALE ──
            (
                ["sold my house", "sold our home", "home sale", "selling the house", "sold the property"],
                "life_events", "_asked_life_events",
                "Did any major life changes happen this year? These can significantly affect your taxes.",
                [
                    {"label": "Sold a home", "value": "event_sold_home"},
                    {"label": "Other life events too", "value": "event_sold_home"},
                    {"label": "Skip", "value": "skip_life_events"},
                ]
            ),
            # ── DIVORCE ──
            (
                ["divorce", "separated", "ex-spouse", "alimony", "child support", "custody"],
                "life_events", "_asked_life_events",
                "Did any major life changes happen this year? These can significantly affect your taxes.",
                [
                    {"label": "Got divorced / separated", "value": "event_divorced"},
                    {"label": "Other life events too", "value": "event_divorced"},
                    {"label": "Skip", "value": "skip_life_events"},
                ]
            ),
            # ── FOREIGN INCOME / EXPAT ──
            (
                ["foreign", "abroad", "overseas", "expat", "fbar", "international", "treaty", "outside the us"],
                "foreign_income", "_asked_foreign",
                "Did you earn any income from outside the United States or pay foreign taxes?",
                [
                    {"label": "Yes — worked abroad", "value": "worked_abroad"},
                    {"label": "Yes — foreign investment income / taxes paid", "value": "foreign_investments"},
                    {"label": "No foreign income", "value": "no_foreign"},
                    {"label": "Skip", "value": "skip_foreign"},
                ]
            ),
            # ── STUDENT LOANS ──
            (
                ["student loan", "student debt", "pslf", "income-driven repayment", "idr", "1098-e"],
                "student_loan_interest", "_asked_student_loans",
                "Did you pay any student loan interest this year? (Up to $2,500 may be deductible)",
                [
                    {"label": "Yes", "value": "has_student_loans"},
                    {"label": "No student loans", "value": "no_student_loans"},
                    {"label": "Skip", "value": "skip_student_loans"},
                ]
            ),
            # ── K-1 INCOME ──
            (
                ["k-1", "k1", "partnership", "s-corp distribution", "limited partner", "trust distribution"],
                "_has_k1", "_asked_k1",
                "Do you receive any K-1 income from partnerships, S-corporations, or trusts?",
                [
                    {"label": "Yes, I have K-1 income", "value": "has_k1_income"},
                    {"label": "No K-1 income", "value": "no_k1_income"},
                    {"label": "Skip", "value": "skip_k1"},
                ]
            ),
            # ── SOLAR / EV / ENERGY ──
            (
                ["solar", "ev", "electric vehicle", "tesla", "heat pump", "energy credit", "panels"],
                "energy_credits", "_asked_energy",
                "Did you make any energy-efficient home improvements or purchase an electric vehicle?",
                [
                    {"label": "Installed solar panels", "value": "has_solar"},
                    {"label": "Bought an electric vehicle", "value": "has_ev"},
                    {"label": "Home energy improvements (insulation, windows, heat pump)", "value": "has_energy_improvements"},
                    {"label": "Multiple", "value": "multiple_energy"},
                    {"label": "None", "value": "no_energy"},
                    {"label": "Skip", "value": "skip_energy"},
                ]
            ),
            # ── MORTGAGE / HOME PURCHASE ──
            (
                ["mortgage", "bought a house", "new home", "first time buyer", "home purchase", "closing costs"],
                "life_events", "_asked_life_events",
                "Did any major life changes happen this year? These can significantly affect your taxes.",
                [
                    {"label": "Bought a home", "value": "event_bought_home"},
                    {"label": "Other life events too", "value": "event_bought_home"},
                    {"label": "Skip", "value": "skip_life_events"},
                ]
            ),
            # ── BABY / NEW CHILD ──
            (
                ["baby", "newborn", "new child", "adopted", "pregnant", "expecting"],
                "life_events", "_asked_life_events",
                "Did any major life changes happen this year? These can significantly affect your taxes.",
                [
                    {"label": "Had a baby / adopted", "value": "event_baby"},
                    {"label": "Other life events too", "value": "event_baby"},
                    {"label": "Skip", "value": "skip_life_events"},
                ]
            ),
            # ── JOB CHANGE / UNEMPLOYMENT ──
            (
                ["new job", "changed jobs", "laid off", "fired", "unemployed", "severance", "unemployment"],
                "unemployment_comp", "_asked_unemployment",
                "Did you receive any unemployment compensation this year? (1099-G — all unemployment benefits are taxable income)",
                [
                    {"label": "Yes", "value": "has_unemployment_comp"},
                    {"label": "No", "value": "no_unemployment_comp"},
                    {"label": "Skip", "value": "skip_unemployment"},
                ]
            ),
            # ── INHERITANCE ──
            (
                ["inherited", "inheritance", "passed away", "estate", "stepped up basis", "beneficiary"],
                "life_events", "_asked_life_events",
                "Did any major life changes happen this year? These can significantly affect your taxes.",
                [
                    {"label": "Received an inheritance", "value": "event_inheritance"},
                    {"label": "Other life events too", "value": "event_inheritance"},
                    {"label": "Skip", "value": "skip_life_events"},
                ]
            ),
            # ── ESTIMATED TAX PAYMENTS ──
            (
                ["estimated payment", "quarterly payment", "1040-es", "underpayment", "penalty"],
                "_has_estimated_payments", "_asked_estimated",
                "Have you made any estimated tax payments this year? (Quarterly payments to the IRS)",
                [
                    {"label": "Yes", "value": "has_estimated_payments"},
                    {"label": "No", "value": "no_estimated_payments"},
                    {"label": "Skip", "value": "skip_estimated"},
                ]
            ),
            # ── 401K / IRA / RETIREMENT ──
            (
                ["401k", "roth", "ira", "tsp", "sep", "retirement", "pension", "rmd", "required minimum"],
                "retirement_401k", "_asked_retirement",
                "Are you contributing to any retirement accounts? This can significantly reduce your taxes.",
                [
                    {"label": "401(k) / 403(b) / TSP", "value": "has_401k"},
                    {"label": "Traditional IRA", "value": "has_trad_ira"},
                    {"label": "Roth IRA", "value": "has_roth_ira"},
                    {"label": "Both employer plan and IRA", "value": "has_both_retirement"},
                    {"label": "No retirement contributions", "value": "no_retirement"},
                    {"label": "Skip", "value": "skip_retirement"},
                ]
            ),
            # ── CHILDCARE / DAYCARE ──
            (
                ["daycare", "childcare", "nanny", "babysitter", "preschool", "after school"],
                "childcare_costs", "_asked_childcare",
                "Did you pay for childcare or daycare so you (and your spouse) could work? This may qualify for the Child and Dependent Care Credit.",
                [
                    {"label": "Yes — under $3,000 total", "value": "childcare_under_3k"},
                    {"label": "Yes — $3,000 - $6,000", "value": "childcare_3_6k"},
                    {"label": "Yes — over $6,000", "value": "childcare_over_6k"},
                    {"label": "No childcare costs", "value": "no_childcare"},
                    {"label": "Skip", "value": "skip_childcare"},
                ]
            ),
            # ── MEDICAL EXPENSES ──
            (
                ["medical", "surgery", "hospital", "doctor bill", "health expenses", "out of pocket"],
                "_has_medical", "_asked_deductions",
                "Let's check your deductions. Do you have any of these?",
                [
                    {"label": "High medical expenses", "value": "has_medical"},
                    {"label": "Mortgage interest", "value": "has_mortgage"},
                    {"label": "Charitable donations", "value": "has_charitable"},
                    {"label": "None — standard deduction", "value": "no_itemized_deductions"},
                    {"label": "Skip", "value": "skip_deductions"},
                ]
            ),
            # ── CHARITABLE GIVING ──
            (
                ["donate", "charity", "charitable", "church", "tithe", "nonprofit", "donor advised"],
                "_has_charitable", "_asked_deductions",
                "Let's check your deductions. Do you have any of these?",
                [
                    {"label": "Charitable donations", "value": "has_charitable"},
                    {"label": "Mortgage interest", "value": "has_mortgage"},
                    {"label": "High medical expenses", "value": "has_medical"},
                    {"label": "None — standard deduction", "value": "no_itemized_deductions"},
                    {"label": "Skip", "value": "skip_deductions"},
                ]
            ),
            # ── HSA ──
            (
                ["hsa", "health savings", "hdhp", "high deductible"],
                "hsa_contributions", "_asked_hsa",
                "Do you have a Health Savings Account (HSA)? Contributions are triple tax-advantaged — deductible, grow tax-free, and withdraw tax-free for medical expenses.",
                [
                    {"label": "Yes, I contribute to an HSA", "value": "has_hsa"},
                    {"label": "I have an HDHP but no HSA yet", "value": "has_hdhp_no_hsa"},
                    {"label": "No HSA / not eligible", "value": "no_hsa"},
                    {"label": "Skip", "value": "skip_hsa"},
                ]
            ),
            # ── GAMBLING ──
            (
                ["gambling", "casino", "lottery", "sports bet", "draftkings", "fanduel", "poker"],
                "gambling_income", "_asked_gambling",
                "Did you have any gambling winnings or losses? (Casino, lottery, sports betting — all taxable)",
                [
                    {"label": "Yes — net winnings", "value": "gambling_winnings"},
                    {"label": "Yes — but net losses", "value": "gambling_losses"},
                    {"label": "No gambling", "value": "no_gambling"},
                    {"label": "Skip", "value": "skip_gambling"},
                ]
            ),
        ]

        # Check each signal — first match wins (highest priority signals first)
        for keywords, field, asked_flag, question_text, actions in _context_signals:
            if profile.get(field) is not None or profile.get(asked_flag):
                continue  # Already answered or asked
            for kw in keywords:
                if kw in _conv_context:
                    # MATCH — pull this question forward
                    logger.info(f"Context boost: '{kw}' detected → jumping to '{question_text[:50]}...'")
                    return (question_text, actions)

        # ── Profile-based urgency pulls ──────────────────────────────────
        # These activate based on profile data, not conversation keywords

        # High income + no investment questions yet → pull investments forward
        if total_income > 200000 and not profile.get("_has_investments") and not profile.get("_asked_investments"):
            if not profile.get("investment_income") and not profile.get("capital_gains_long"):
                return (
                    "With your income level, investment income is important for accurate planning. Do you have any investment income? (Stocks, bonds, crypto, dividends, interest)",
                    [
                        {"label": "Yes, I have investments", "value": "has_investments"},
                        {"label": "No investment income", "value": "no_investments"},
                        {"label": "Skip", "value": "skip_investments"},
                    ]
                )

        # Self-employed + no estimated payments asked → pull forward (penalty risk)
        if is_se and total_income > 50000 and not profile.get("_has_estimated_payments") and not profile.get("_asked_estimated"):
            if profile.get("business_income") and not profile.get("estimated_payments"):
                return (
                    "As self-employed with business income, have you made estimated tax payments? (Missing quarterly payments can trigger penalties)",
                    [
                        {"label": "Yes", "value": "has_estimated_payments"},
                        {"label": "No", "value": "no_estimated_payments"},
                        {"label": "Skip", "value": "skip_estimated"},
                    ]
                )

        # Has dependents + childcare not asked + income suggests working parent
        if dependents > 0 and total_income > 30000:
            under_17 = profile.get("dependents_under_17")
            if under_17 and under_17 > 0 and not profile.get("childcare_costs") and not profile.get("_asked_childcare"):
                if not profile.get("_asked_dependents_age"):
                    pass  # Let age split happen first
                else:
                    return (
                        "Did you pay for childcare or daycare so you (and your spouse) could work? This may qualify for the Child and Dependent Care Credit.",
                        [
                            {"label": "Yes — under $3,000 total", "value": "childcare_under_3k"},
                            {"label": "Yes — $3,000 - $6,000", "value": "childcare_3_6k"},
                            {"label": "Yes — over $6,000", "value": "childcare_over_6k"},
                            {"label": "No childcare costs", "value": "no_childcare"},
                            {"label": "Skip", "value": "skip_childcare"},
                        ]
                    )

    # =========================================================================
    # SEQUENTIAL FLOW (when no context signal detected, or no conversation yet)
    # Blocks A → B → C → D → E → F → G → H → I → J → K → L → M → N → O
    # =========================================================================

    # ── BLOCK A: Income-type-specific questions ──────────────────────────

    # --- A1. Multiple W-2 job count ---
    if income_type == "multiple_w2" and not profile.get("w2_job_count") and not profile.get("_asked_w2_count"):
        return (
            "How many W-2 jobs did you have this year?",
            [
                {"label": "2 jobs", "value": "2_jobs"},
                {"label": "3 or more jobs", "value": "3plus_jobs"},
            ]
        )

    # --- A2. W-2+Side hustle type ---
    if income_type == "w2_plus_side" and not profile.get("side_hustle_type") and not profile.get("_asked_side_type"):
        return (
            "What type of side income do you have?",
            [
                {"label": "Freelance / Consulting (1099-NEC)", "value": "freelance"},
                {"label": "Gig Work (Uber, DoorDash, etc.)", "value": "gig_work"},
                {"label": "Online Sales (Etsy, eBay, Shopify)", "value": "online_sales"},
                {"label": "Rental Income", "value": "side_rental"},
                {"label": "Multiple types", "value": "multiple_side"},
            ]
        )

    # --- A3. Side hustle income amount ---
    if income_type == "w2_plus_side" and profile.get("side_hustle_type") and not profile.get("side_income") and not profile.get("_asked_side_income"):
        return (
            "What's your approximate net side income (after expenses)?",
            [
                {"label": "Under $5,000", "value": "side_under_5k"},
                {"label": "$5,000 - $20,000", "value": "side_5_20k"},
                {"label": "$20,000 - $50,000", "value": "side_20_50k"},
                {"label": "Over $50,000", "value": "side_over_50k"},
                {"label": "Skip", "value": "skip_side_income"},
            ]
        )

    # --- A4. Federal withholding (W-2 / military only) — SMART DEFAULT first ---
    if is_w2 and not profile.get("federal_withholding") and not profile.get("_asked_withholding"):
        _smart = _estimate_smart_default("federal_withholding", profile)
        if _smart and not profile.get("_smart_default_rejected"):
            return (_smart["text"], _smart["actions"])
        return (
            "Approximately how much federal tax was withheld from your paychecks this year? Check your last pay stub for the YTD Federal Tax amount.",
            [
                {"label": "Under $5,000", "value": "withholding_under_5k"},
                {"label": "$5,000 - $10,000", "value": "withholding_5_10k"},
                {"label": "$10,000 - $20,000", "value": "withholding_10_20k"},
                {"label": "$20,000 - $40,000", "value": "withholding_20_40k"},
                {"label": "Over $40,000", "value": "withholding_over_40k"},
                {"label": "Not sure — estimate for me", "value": "withholding_estimate"},
            ]
        )

    # --- A5. Military: Combat zone ---
    if is_military and not profile.get("combat_zone") and not profile.get("_asked_military_combat"):
        return (
            "Were you deployed to a combat zone? Combat pay may be tax-exempt.",
            [
                {"label": "Yes — combat zone deployment", "value": "combat_zone"},
                {"label": "No deployment", "value": "no_combat"},
                {"label": "Skip", "value": "skip_military_combat"},
            ]
        )

    # --- A6. Military: PCS move ---
    if is_military and not profile.get("pcs_move") and not profile.get("_asked_pcs"):
        return (
            "Did you have a Permanent Change of Station (PCS) move? Military moving expenses are still deductible.",
            [
                {"label": "Yes — PCS move", "value": "pcs_move"},
                {"label": "No PCS this year", "value": "no_pcs"},
                {"label": "Skip", "value": "skip_pcs"},
            ]
        )

    # --- A7. Self-employment / Business: Entity type ---
    if is_se and not profile.get("entity_type") and not profile.get("_asked_entity_type"):
        return (
            "What type of business entity do you have?",
            [
                {"label": "Sole Proprietorship (no entity)", "value": "sole_prop"},
                {"label": "Single-Member LLC", "value": "single_llc"},
                {"label": "Multi-Member LLC", "value": "multi_llc"},
                {"label": "S-Corporation", "value": "s_corp"},
                {"label": "C-Corporation", "value": "c_corp"},
                {"label": "Partnership", "value": "partnership"},
                {"label": "Not sure", "value": "entity_unsure"},
            ]
        )

    # --- A8. Business income ---
    if is_se and not profile.get("business_income") and not profile.get("_asked_business"):
        return (
            "What's your approximate net business income (revenue minus expenses)?",
            [
                {"label": "Under $25K", "value": "biz_under_25k"},
                {"label": "$25K - $50K", "value": "biz_25_50k"},
                {"label": "$50K - $100K", "value": "biz_50_100k"},
                {"label": "$100K - $200K", "value": "biz_100_200k"},
                {"label": "Over $200K", "value": "biz_over_200k"},
                {"label": "Net loss", "value": "biz_net_loss"},
                {"label": "Skip", "value": "skip_business"},
            ]
        )

    # --- A9. S-Corp: Reasonable salary ---
    if profile.get("entity_type") == "s_corp" and not profile.get("reasonable_salary") and not profile.get("_asked_salary"):
        return (
            "As an S-Corp owner, what salary do you pay yourself? (This affects your self-employment tax savings)",
            [
                {"label": "Under $50K", "value": "salary_under_50k"},
                {"label": "$50K - $100K", "value": "salary_50_100k"},
                {"label": "$100K - $150K", "value": "salary_100_150k"},
                {"label": "Over $150K", "value": "salary_over_150k"},
                {"label": "Skip", "value": "skip_salary"},
            ]
        )

    # --- A10. SE: Home office ---
    if is_se and profile.get("business_income") and not profile.get("home_office_sqft") and not profile.get("_asked_home_office"):
        return (
            "Do you use part of your home exclusively and regularly for business?",
            [
                {"label": "Yes, I have a dedicated home office", "value": "has_home_office"},
                {"label": "No home office", "value": "no_home_office"},
                {"label": "Skip", "value": "skip_home_office"},
            ]
        )

    # --- A11. SE: Vehicle / mileage ---
    if is_se and profile.get("business_income") and not profile.get("business_miles") and not profile.get("_asked_vehicle"):
        return (
            "Do you use a vehicle for business? (Commuting doesn't count — business travel, client visits, deliveries)",
            [
                {"label": "Yes, I drive for business", "value": "has_biz_vehicle"},
                {"label": "No business vehicle use", "value": "no_biz_vehicle"},
                {"label": "Skip", "value": "skip_vehicle"},
            ]
        )

    # --- A12. SE: Equipment / Section 179 ---
    biz_income = float(profile.get("business_income", 0) or 0)
    if is_se and biz_income > 25000 and not profile.get("equipment_cost") and not profile.get("_asked_equipment"):
        return (
            "Did you purchase any major equipment or assets for your business this year? (Computers, machinery, furniture, vehicles)",
            [
                {"label": "Yes, I bought equipment", "value": "has_equipment"},
                {"label": "No major purchases", "value": "no_equipment"},
                {"label": "Skip", "value": "skip_equipment"},
            ]
        )

    # --- A13. SE: Employees / contractors ---
    if is_se and biz_income > 50000 and not profile.get("has_employees_status") and not profile.get("_asked_employees"):
        return (
            "Do you have any employees or pay independent contractors?",
            [
                {"label": "Yes, I have employees", "value": "has_employees"},
                {"label": "Yes, I pay contractors (1099)", "value": "has_contractors"},
                {"label": "Both employees and contractors", "value": "has_both_workers"},
                {"label": "No — solo operation", "value": "solo_operation"},
                {"label": "Skip", "value": "skip_employees"},
            ]
        )

    # --- A14. SE: Health insurance deduction ---
    if income_type in ("self_employed", "business_owner", "gig_worker", "farmer", "clergy") and not profile.get("se_health_insurance") and not profile.get("_asked_se_health"):
        return (
            "Do you pay for your own health insurance? Self-employed individuals can deduct 100% of premiums.",
            [
                {"label": "Yes, I pay my own premiums", "value": "has_se_health"},
                {"label": "Covered by spouse's employer", "value": "spouse_coverage"},
                {"label": "ACA Marketplace plan", "value": "aca_plan"},
                {"label": "No health insurance", "value": "no_health_insurance"},
                {"label": "Skip", "value": "skip_se_health"},
            ]
        )

    # --- A15. SE high income: QBI / SSTB classification ---
    if is_se and total_income > 182100 and not profile.get("is_sstb") and not profile.get("_asked_sstb"):
        return (
            "Is your business in a 'specified service' field? (Law, medicine, accounting, consulting, financial services, performing arts, athletics)",
            [
                {"label": "Yes — service-based profession", "value": "is_sstb"},
                {"label": "No — product / trade / other", "value": "not_sstb"},
                {"label": "Not sure", "value": "sstb_unsure"},
                {"label": "Skip", "value": "skip_sstb"},
            ]
        )

    # --- A16. Retired: Social Security benefits ---
    if is_retired and not profile.get("ss_benefits") and not profile.get("_asked_ss"):
        return (
            "Did you receive Social Security benefits this year? If so, approximately how much?",
            [
                {"label": "Under $15,000", "value": "ss_under_15k"},
                {"label": "$15,000 - $30,000", "value": "ss_15_30k"},
                {"label": "Over $30,000", "value": "ss_over_30k"},
                {"label": "Not receiving SS yet", "value": "no_ss"},
                {"label": "Skip", "value": "skip_ss"},
            ]
        )

    # --- A17. Retired: Pension income ---
    if is_retired and not profile.get("pension_income") and not profile.get("_asked_pension"):
        return (
            "Do you receive pension income?",
            [
                {"label": "Yes — fully taxable", "value": "pension_taxable"},
                {"label": "Yes — partially taxable (after-tax contributions)", "value": "pension_partial"},
                {"label": "No pension", "value": "no_pension"},
                {"label": "Skip", "value": "skip_pension"},
            ]
        )

    # --- A18. Retired 65+: Required Minimum Distributions ---
    if is_retired and profile.get("age") in ("age_65_plus",) and not profile.get("rmd_status") and not profile.get("_asked_rmd"):
        return (
            "Are you 73 or older? You're required to take minimum distributions (RMDs). Have you taken yours?",
            [
                {"label": "Yes — I've taken my RMD", "value": "rmd_taken"},
                {"label": "Not yet — need to before year-end", "value": "rmd_pending"},
                {"label": "Under 73 — RMD not required", "value": "under_73"},
                {"label": "Skip", "value": "skip_rmd"},
            ]
        )

    # --- A19. Gig worker: platform count ---
    if income_type == "gig_worker" and not profile.get("gig_platforms") and not profile.get("_asked_gig_platforms"):
        return (
            "How many gig platforms do you work for? (Each may send a 1099-K or 1099-NEC)",
            [
                {"label": "1 platform", "value": "gig_1_platform"},
                {"label": "2-3 platforms", "value": "gig_2_3_platforms"},
                {"label": "4+ platforms", "value": "gig_4plus_platforms"},
                {"label": "Skip", "value": "skip_gig_platforms"},
            ]
        )

    # --- A20. Gig worker: mileage tracking ---
    if income_type == "gig_worker" and not profile.get("gig_mileage") and not profile.get("_asked_gig_mileage"):
        return (
            "Do you track your business miles? (Standard rate is $0.70/mile for 2025 — this is usually the biggest gig deduction)",
            [
                {"label": "Yes — I track mileage", "value": "gig_tracks_mileage"},
                {"label": "No — I don't track", "value": "gig_no_mileage"},
                {"label": "I use actual vehicle expenses instead", "value": "gig_actual_expenses"},
                {"label": "Skip", "value": "skip_gig_mileage"},
            ]
        )

    # --- A21. Farmer: farm income ---
    if income_type == "farmer" and not profile.get("farm_income") and not profile.get("_asked_farm_income"):
        return (
            "What's your approximate net farm income? (Include crop sales, livestock, CRP payments, crop insurance proceeds)",
            [
                {"label": "Under $50K", "value": "farm_under_50k"},
                {"label": "$50K - $150K", "value": "farm_50_150k"},
                {"label": "Over $150K", "value": "farm_over_150k"},
                {"label": "Net loss", "value": "farm_net_loss"},
                {"label": "Skip", "value": "skip_farm_income"},
            ]
        )

    # --- A22. Farmer: crop insurance ---
    if income_type == "farmer" and profile.get("farm_income") and not profile.get("crop_insurance") and not profile.get("_asked_crop_insurance"):
        return (
            "Did you receive crop insurance or disaster payments?",
            [
                {"label": "Yes", "value": "has_crop_insurance"},
                {"label": "No", "value": "no_crop_insurance"},
                {"label": "Skip", "value": "skip_crop_insurance"},
            ]
        )

    # --- A23. Clergy: housing allowance ---
    if income_type == "clergy" and not profile.get("clergy_housing") and not profile.get("_asked_clergy_housing"):
        return (
            "Do you receive a parsonage/housing allowance? (This amount is excluded from income tax but subject to self-employment tax)",
            [
                {"label": "Yes — parsonage/housing allowance", "value": "has_clergy_housing"},
                {"label": "No", "value": "no_clergy_housing"},
                {"label": "Skip", "value": "skip_clergy_housing"},
            ]
        )

    # --- A24. 1099-K received (gig, side hustle, anyone with platform payments) ---
    if is_se and not profile.get("has_1099k") and not profile.get("_asked_1099k"):
        return (
            "Did you receive a Form 1099-K from any payment platform? (PayPal, Venmo, Square, Stripe, Etsy, eBay — $600 threshold for 2025)",
            [
                {"label": "Yes — for my business income", "value": "1099k_business"},
                {"label": "Yes — but it includes personal reimbursements (not income)", "value": "1099k_personal"},
                {"label": "No 1099-K received", "value": "no_1099k"},
                {"label": "Skip", "value": "skip_1099k"},
            ]
        )

    # --- A25. Unreported tip income — MOVED to Block M (only relevant for service workers) ---
    # Gated behind low income OR context keywords to avoid asking software engineers about tips

    # --- A26. Statutory employee — MOVED to context-only (adaptive intelligence handles it) ---
    # Most W-2 employees don't know what this is. Only ask if context mentions "commission" or "statutory"
    if False and is_w2 and not profile.get("statutory_employee") and not profile.get("_asked_statutory"):
        return (
            "Does your W-2 have 'Statutory Employee' checked in Box 13? (Commission salespeople, certain drivers, home workers — file Schedule C instead of reporting as wages)",
            [
                {"label": "Yes — Statutory Employee", "value": "is_statutory_employee"},
                {"label": "No", "value": "not_statutory"},
                {"label": "Not sure", "value": "statutory_unsure"},
                {"label": "Skip", "value": "skip_statutory"},
            ]
        )

    # --- A27. Unemployment benefits (anyone, not just life event) ---
    if not profile.get("unemployment_comp") and not profile.get("_asked_unemployment") and not profile.get("unemployment_income"):
        return (
            "Did you receive any unemployment compensation this year? (1099-G — all unemployment benefits are taxable income)",
            [
                {"label": "Yes", "value": "has_unemployment_comp"},
                {"label": "No", "value": "no_unemployment_comp"},
                {"label": "Skip", "value": "skip_unemployment"},
            ]
        )

    # --- A28. Disability income ---
    if not profile.get("disability_income_type") and not profile.get("_asked_disability"):
        return (
            "Do you receive any disability income?",
            [
                {"label": "Social Security Disability (SSDI)", "value": "has_ssdi"},
                {"label": "VA Disability (tax-free)", "value": "has_va_disability"},
                {"label": "Employer disability plan", "value": "has_employer_disability"},
                {"label": "Workers' compensation (tax-free)", "value": "has_workers_comp"},
                {"label": "No disability income", "value": "no_disability"},
                {"label": "Skip", "value": "skip_disability"},
            ]
        )

    # --- A29. Royalty income ---
    if not profile.get("royalty_income") and not profile.get("_asked_royalty"):
        return (
            "Do you receive any royalty income? (Oil/gas mineral rights, book/music royalties, patent licensing)",
            [
                {"label": "Oil/gas/mineral royalties", "value": "royalty_oil_gas"},
                {"label": "Book/music/art royalties", "value": "royalty_creative"},
                {"label": "Patent or licensing royalties", "value": "royalty_patent"},
                {"label": "No royalties", "value": "no_royalty"},
                {"label": "Skip", "value": "skip_royalty"},
            ]
        )

    # --- A30. Interest income detail (Schedule B threshold) ---
    if not profile.get("interest_income_detail") and not profile.get("_asked_interest_detail"):
        return (
            "Did you receive more than $1,500 in interest income this year? (Bank accounts, CDs, bonds, Treasury securities — Schedule B required if over $1,500)",
            [
                {"label": "Under $1,500", "value": "interest_under_1500"},
                {"label": "$1,500 - $10,000", "value": "interest_1500_10k"},
                {"label": "Over $10,000", "value": "interest_over_10k"},
                {"label": "I have tax-exempt interest (muni bonds)", "value": "has_tax_exempt_interest"},
                {"label": "No interest income", "value": "no_interest_income"},
                {"label": "Skip", "value": "skip_interest_detail"},
            ]
        )

    # --- A31. Canceled/forgiven debt (1099-C) ---
    if not profile.get("canceled_debt") and not profile.get("_asked_canceled_debt"):
        return (
            "Did you have any debt forgiven or canceled this year? (Credit card debt, mortgage modification, student loan forgiveness, personal loan)",
            [
                {"label": "Yes — credit card or personal debt", "value": "canceled_debt_personal"},
                {"label": "Yes — mortgage debt (foreclosure/short sale)", "value": "canceled_debt_mortgage"},
                {"label": "Yes — student loan forgiveness", "value": "canceled_debt_student"},
                {"label": "No canceled debt", "value": "no_canceled_debt"},
                {"label": "Skip", "value": "skip_canceled_debt"},
            ]
        )

    # --- A32. Hobby income (not for profit) ---
    if not profile.get("hobby_income") and not profile.get("_asked_hobby"):
        return (
            "Do you have income from a hobby or activity not engaged in for profit? (Crafts, collectibles, occasional sales — expenses are NOT deductible post-TCJA)",
            [
                {"label": "Yes", "value": "has_hobby_income"},
                {"label": "No", "value": "no_hobby_income"},
                {"label": "Skip", "value": "skip_hobby"},
            ]
        )

    # --- A33. 1099-R breakdown (annuity, life insurance, 457, disability pension) ---
    if not is_retired and not profile.get("other_1099r") and not profile.get("_asked_other_1099r"):
        return (
            "Did you receive distributions from any of these: annuity, life insurance (cash value), 457 plan, or disability pension?",
            [
                {"label": "Annuity payments", "value": "1099r_annuity"},
                {"label": "Life insurance cash surrender", "value": "1099r_life_insurance"},
                {"label": "457(b) plan", "value": "1099r_457b"},
                {"label": "Disability pension", "value": "1099r_disability_pension"},
                {"label": "None of these", "value": "no_other_1099r"},
                {"label": "Skip", "value": "skip_other_1099r"},
            ]
        )

    # --- A34. HSA distributions (1099-SA) ---
    if profile.get("hsa_contributions") and profile.get("hsa_contributions") not in (0, "no_hsa") and not profile.get("hsa_distributions") and not profile.get("_asked_hsa_dist"):
        return (
            "Did you take any distributions from your HSA this year? Were they for qualified medical expenses?",
            [
                {"label": "Yes — all for qualified medical", "value": "hsa_dist_qualified"},
                {"label": "Yes — some non-qualified (20% penalty applies)", "value": "hsa_dist_nonqualified"},
                {"label": "No distributions", "value": "hsa_no_dist"},
                {"label": "Skip", "value": "skip_hsa_dist"},
            ]
        )

    # --- A35. Director fees / board compensation ---
    if total_income > 100000 and not profile.get("director_fees") and not profile.get("_asked_director_fees"):
        return (
            "Did you receive fees for serving on a board of directors? (Reported on 1099-NEC, subject to SE tax)",
            [
                {"label": "Yes", "value": "has_director_fees"},
                {"label": "No", "value": "no_director_fees"},
                {"label": "Skip", "value": "skip_director_fees"},
            ]
        )

    # --- A36. Bartering income ---
    if is_se and not profile.get("bartering_income") and not profile.get("_asked_bartering"):
        return (
            "Did you exchange goods or services through bartering? (Bartering income is taxable)",
            [
                {"label": "Yes", "value": "has_bartering"},
                {"label": "No", "value": "no_bartering"},
                {"label": "Skip", "value": "skip_bartering"},
            ]
        )

    # --- A37. Jury duty pay ---
    if not profile.get("jury_duty_pay") and not profile.get("_asked_jury_duty"):
        return (
            "Did you receive jury duty pay this year?",
            [
                {"label": "Yes — kept it", "value": "jury_duty_kept"},
                {"label": "Yes — turned it over to employer", "value": "jury_duty_employer"},
                {"label": "No", "value": "no_jury_duty"},
                {"label": "Skip", "value": "skip_jury_duty"},
            ]
        )

    # --- A38. 1099-OID (Original Issue Discount) ---
    if profile.get("_has_investments") and not profile.get("oid_income") and not profile.get("_asked_oid"):
        return (
            "Did you receive a 1099-OID for bonds purchased at a discount? (Original Issue Discount)",
            [
                {"label": "Yes", "value": "has_oid"},
                {"label": "No", "value": "no_oid"},
                {"label": "Skip", "value": "skip_oid"},
            ]
        )

    # --- A39. Long-term care benefits (1099-LTC) ---
    if (profile.get("age") in ("age_50_64", "age_65_plus") or profile.get("disability_income_type")) and not profile.get("ltc_benefits") and not profile.get("_asked_ltc"):
        return (
            "Did you receive long-term care insurance benefits or accelerated death benefits?",
            [
                {"label": "Yes", "value": "has_ltc_benefits"},
                {"label": "No", "value": "no_ltc_benefits"},
                {"label": "Skip", "value": "skip_ltc"},
            ]
        )

    # ── BLOCK B: Age ─────────────────────────────────────────────────────

    if not profile.get("age") and not profile.get("_asked_age"):
        return (
            "What is your age? This helps determine your standard deduction and eligibility for certain credits.",
            [
                {"label": "Under 26", "value": "age_under_26"},
                {"label": "26 - 49", "value": "age_26_49"},
                {"label": "50 - 64", "value": "age_50_64"},
                {"label": "65 or older", "value": "age_65_plus"},
                {"label": "Skip", "value": "skip_age"},
            ]
        )

    # --- B2. Legally blind check ---
    if not profile.get("legally_blind") and not profile.get("_asked_blind"):
        return (
            "Are you or your spouse legally blind? (Additional standard deduction: $1,850 single / $1,500 MFJ per blind person)",
            [
                {"label": "Yes — taxpayer", "value": "blind_taxpayer"},
                {"label": "Yes — spouse", "value": "blind_spouse"},
                {"label": "Both", "value": "blind_both"},
                {"label": "No", "value": "not_blind"},
                {"label": "Skip", "value": "skip_blind"},
            ]
        )

    # --- B3. Student status ---
    if not profile.get("student_status") and not profile.get("_asked_student_status"):
        return (
            "Were you a full-time or part-time student during the tax year? (Affects EITC eligibility, education credits, and dependent filing rules)",
            [
                {"label": "Full-time student", "value": "fulltime_student"},
                {"label": "Part-time student", "value": "parttime_student"},
                {"label": "Not a student", "value": "not_student"},
                {"label": "Skip", "value": "skip_student_status"},
            ]
        )

    # --- B4. Filing as someone's dependent ---
    if not profile.get("claimed_as_dependent") and not profile.get("_asked_dependent_self"):
        return (
            "Can someone else claim you as a dependent on their tax return? (This affects your standard deduction and credit eligibility)",
            [
                {"label": "Yes — I'm claimed as a dependent", "value": "is_dependent"},
                {"label": "No — I file independently", "value": "not_dependent"},
                {"label": "Not sure", "value": "dependent_unsure"},
                {"label": "Skip", "value": "skip_dependent_self"},
            ]
        )

    # ── BLOCK C: Spouse details (MFJ only) ───────────────────────────────

    if filing_status == "married_joint":
        if not profile.get("spouse_income_type") and not profile.get("_asked_spouse_income_type"):
            return (
                "Does your spouse also earn income? If so, what type?",
                [
                    {"label": "W-2 Employee", "value": "spouse_w2"},
                    {"label": "Self-Employed", "value": "spouse_se"},
                    {"label": "Not working / Homemaker", "value": "spouse_none"},
                    {"label": "Retired", "value": "spouse_retired"},
                    {"label": "Skip", "value": "skip_spouse_income"},
                ]
            )
        if profile.get("spouse_income_type") in ("spouse_w2", "spouse_se") and not profile.get("spouse_income") and not profile.get("_asked_spouse_income"):
            return (
                "What's your spouse's approximate annual income?",
                [
                    {"label": "Under $25K", "value": "spouse_under_25k"},
                    {"label": "$25K - $50K", "value": "spouse_25_50k"},
                    {"label": "$50K - $100K", "value": "spouse_50_100k"},
                    {"label": "Over $100K", "value": "spouse_over_100k"},
                    {"label": "Skip", "value": "skip_spouse_amount"},
                ]
            )

    # --- C3. NRA spouse election ---
    if filing_status == "married_joint" and not profile.get("nra_spouse_election") and not profile.get("_asked_nra_spouse"):
        return (
            "Is your spouse a nonresident alien? Would you like to elect to treat them as a US resident? (Allows MFJ but subjects worldwide income to US tax)",
            [
                {"label": "Yes — elect US resident treatment", "value": "nra_spouse_elect"},
                {"label": "No — spouse is US citizen/resident", "value": "nra_spouse_na"},
                {"label": "Skip", "value": "skip_nra_spouse"},
            ]
        )

    # --- C4. Educator spouse (MFJ — each can deduct $300) ---
    if filing_status == "married_joint" and profile.get("educator_expenses") and not profile.get("spouse_educator") and not profile.get("_asked_spouse_educator"):
        return (
            "Is your spouse also a K-12 educator? Each spouse can deduct up to $300 in classroom supplies (combined $600).",
            [
                {"label": "Yes — spouse is also an educator", "value": "spouse_is_educator"},
                {"label": "No", "value": "spouse_not_educator"},
                {"label": "Skip", "value": "skip_spouse_educator"},
            ]
        )

    # --- C5. Dependent care benefits from employer (W-2 Box 10) ---
    if is_w2 and dependents > 0 and not profile.get("employer_dc_benefits") and not profile.get("_asked_employer_dc"):
        return (
            "Did your employer provide dependent care benefits shown in W-2 Box 10? (Up to $5,000 may be excluded from income)",
            [
                {"label": "Yes", "value": "has_employer_dc"},
                {"label": "No", "value": "no_employer_dc"},
                {"label": "Skip", "value": "skip_employer_dc"},
            ]
        )

    # ── BLOCK D: Dependent details ───────────────────────────────────────

    if dependents > 0:
        # D1. Age split for CTC
        if profile.get("dependents_under_17") is None and not profile.get("_asked_dependents_age"):
            return (
                f"Of your {dependents} dependent(s), how many are under age 17? (Important for the Child Tax Credit — $2,000 per child under 17)",
                [
                    {"label": f"All {dependents}", "value": "all_under_17"},
                    {"label": "None — all 17 or older", "value": "none_under_17"},
                    *([{"label": f"{i}", "value": f"{i}_under_17"} for i in range(1, dependents)] if dependents > 1 else []),
                    {"label": "Skip", "value": "skip_dependents_age"},
                ]
            )

        # D2. Childcare costs (if has young children)
        under_17 = profile.get("dependents_under_17", 0) or 0
        if under_17 > 0 and not profile.get("childcare_costs") and not profile.get("_asked_childcare"):
            return (
                "Did you pay for childcare or daycare so you (and your spouse) could work? This may qualify for the Child and Dependent Care Credit.",
                [
                    {"label": "Yes — under $3,000 total", "value": "childcare_under_3k"},
                    {"label": "Yes — $3,000 - $6,000", "value": "childcare_3_6k"},
                    {"label": "Yes — over $6,000", "value": "childcare_over_6k"},
                    {"label": "No childcare costs", "value": "no_childcare"},
                    {"label": "Skip", "value": "skip_childcare"},
                ]
            )

        # D3. Dependent care FSA (follow-up if has childcare)
        if profile.get("childcare_costs") and profile.get("childcare_costs") != "no_childcare" and not profile.get("dependent_care_fsa") and not profile.get("_asked_dcfsa"):
            return (
                "Did you or your employer contribute to a Dependent Care FSA? (Up to $5,000 pre-tax for childcare)",
                [
                    {"label": "Yes", "value": "has_dcfsa"},
                    {"label": "No", "value": "no_dcfsa"},
                    {"label": "Skip", "value": "skip_dcfsa"},
                ]
            )

        # D4. Education credits
        if not profile.get("education_status") and not profile.get("_asked_education") and total_income < 180000:
            return (
                "Did you or a dependent attend college or vocational school? Tuition may qualify for education credits (up to $2,500).",
                [
                    {"label": "Yes — I'm a student", "value": "self_student"},
                    {"label": "Yes — my dependent is a student", "value": "dependent_student"},
                    {"label": "Yes — both", "value": "both_students"},
                    {"label": "No", "value": "no_education"},
                    {"label": "Skip", "value": "skip_education"},
                ]
            )

        # D5. 529 plan (if state has income tax)
        if profile.get("state") not in _NO_INCOME_TAX_STATES and not profile.get("has_529") and not profile.get("_asked_529"):
            return (
                "Did you contribute to a 529 college savings plan? (Many states offer a tax deduction for contributions)",
                [
                    {"label": "Yes", "value": "has_529"},
                    {"label": "No", "value": "no_529"},
                    {"label": "Skip", "value": "skip_529"},
                ]
            )

        # D6. Custody (single/HOH with dependents — possible divorced parent)
        if filing_status in ("single", "head_of_household") and not profile.get("custody_status") and not profile.get("_asked_custody"):
            return (
                "Are you a divorced or separated parent? If so, who claims the children on their tax return?",
                [
                    {"label": "I claim all children", "value": "custody_self"},
                    {"label": "Ex-spouse claims them", "value": "custody_ex"},
                    {"label": "We split (Form 8332)", "value": "custody_split"},
                    {"label": "Not applicable", "value": "custody_na"},
                    {"label": "Skip", "value": "skip_custody"},
                ]
            )

    # D7a. HOH eligibility verification (most commonly audited filing status)
    if filing_status == "head_of_household" and not profile.get("hoh_verified") and not profile.get("_asked_hoh_verify"):
        return (
            "To confirm Head of Household: Did you pay more than half the cost of maintaining your home, AND did a qualifying person live with you for more than half the year?",
            [
                {"label": "Yes — I meet both requirements", "value": "hoh_confirmed"},
                {"label": "I'm not sure", "value": "hoh_unsure"},
                {"label": "I should probably file as Single", "value": "hoh_change_to_single"},
                {"label": "Skip", "value": "skip_hoh_verify"},
            ]
        )

    # D7b. Qualifying relative dependent (non-child — elderly parent, sibling)
    if dependents > 0 and not profile.get("qualifying_relative") and not profile.get("_asked_qualifying_relative"):
        return (
            "Besides children, do you support any other dependents? (Elderly parent, sibling, other relative earning less than $5,050)",
            [
                {"label": "Elderly parent", "value": "qr_elderly_parent"},
                {"label": "Other relative (sibling, grandparent, etc.)", "value": "qr_other_relative"},
                {"label": "Non-relative who lives with me", "value": "qr_non_relative"},
                {"label": "No — only children", "value": "qr_children_only"},
                {"label": "Skip", "value": "skip_qualifying_relative"},
            ]
        )

    # D7c. Disabled dependent
    if dependents > 0 and not profile.get("disabled_dependent") and not profile.get("_asked_disabled_dep"):
        return (
            "Is any of your dependents permanently and totally disabled? (No age limit for qualifying child status, affects credit eligibility)",
            [
                {"label": "Yes", "value": "has_disabled_dependent"},
                {"label": "No", "value": "no_disabled_dependent"},
                {"label": "Skip", "value": "skip_disabled_dep"},
            ]
        )

    # D7d. Dependent SSN vs ITIN
    if dependents > 0 and not profile.get("dependent_ssn_status") and not profile.get("_asked_dep_ssn"):
        return (
            "Do all your dependents have Social Security Numbers? (Required for CTC — ITIN dependents qualify for $500 Other Dependent Credit instead)",
            [
                {"label": "All have SSNs", "value": "dep_all_ssn"},
                {"label": "Some have ITINs", "value": "dep_some_itin"},
                {"label": "Skip", "value": "skip_dep_ssn"},
            ]
        )

    # D7d2. Multiple support agreement (Form 2120)
    if dependents > 0 and profile.get("qualifying_relative") in ("elderly_parent", "other", "non_relative") and not profile.get("multiple_support") and not profile.get("_asked_multiple_support"):
        return (
            "Do you share the financial support of this dependent with other family members? (Multiple Support Agreement — Form 2120)",
            [
                {"label": "Yes", "value": "has_multiple_support"},
                {"label": "No — I provide over half", "value": "no_multiple_support"},
                {"label": "Skip", "value": "skip_multiple_support"},
            ]
        )

    # D7d3. Student dependent 19-23
    under_17 = profile.get("dependents_under_17", 0) or 0
    _older_deps = dependents - under_17
    if _older_deps > 0 and not profile.get("student_dependent_status") and not profile.get("_asked_student_dep"):
        return (
            "Is your dependent age 19-23 a full-time student? (Full-time students under 24 qualify as qualifying children)",
            [
                {"label": "Yes — full-time student", "value": "student_dep_fulltime"},
                {"label": "No — not a full-time student", "value": "student_dep_no"},
                {"label": "Skip", "value": "skip_student_dep"},
            ]
        )

    # D7d4. QSS verification
    if filing_status == "qualifying_widow" and not profile.get("qss_verified") and not profile.get("_asked_qss_verify"):
        return (
            "To confirm Qualifying Surviving Spouse: Did your spouse die within the last 2 tax years, and do you have a dependent child living with you?",
            [
                {"label": "Yes — both conditions met", "value": "qss_confirmed"},
                {"label": "I should file differently", "value": "qss_change"},
                {"label": "Skip", "value": "skip_qss_verify"},
            ]
        )

    # D7e. Education credits follow-up: AOTC vs LLC
    if profile.get("education_status") in ("self_student", "dependent_student", "both_students") and not profile.get("education_credit_type") and not profile.get("_asked_edu_credit_type"):
        return (
            "Is the student within their first 4 years of college? (American Opportunity Credit = up to $2,500, partially refundable) Or beyond year 4? (Lifetime Learning Credit = up to $2,000)",
            [
                {"label": "First 4 years — AOTC", "value": "edu_aotc"},
                {"label": "Beyond year 4 or grad school — LLC", "value": "edu_llc"},
                {"label": "Vocational / continuing education — LLC", "value": "edu_vocational"},
                {"label": "Not sure", "value": "edu_unsure"},
                {"label": "Skip", "value": "skip_edu_credit_type"},
            ]
        )

    # D7e2. Education — felony drug conviction (AOTC compliance requirement)
    if profile.get("education_credit_type") == "aotc" and not profile.get("felony_drug") and not profile.get("_asked_felony_drug"):
        return (
            "Has the student been convicted of a felony drug offense? (This disqualifies the American Opportunity Credit only — required IRS question)",
            [
                {"label": "No", "value": "no_felony_drug"},
                {"label": "Yes", "value": "has_felony_drug"},
                {"label": "Skip", "value": "skip_felony_drug"},
            ]
        )

    # D7f. 529 distribution (if has 529)
    if profile.get("has_529") and not profile.get("_529_distribution") and not profile.get("_asked_529_dist"):
        return (
            "Did you take any distributions from a 529 plan? (Qualified education expenses = tax-free; non-qualified = taxable + 10% penalty)",
            [
                {"label": "Yes — for qualified education expenses", "value": "529_qualified"},
                {"label": "Yes — some non-qualified", "value": "529_nonqualified"},
                {"label": "No distributions", "value": "529_no_dist"},
                {"label": "Skip", "value": "skip_529_dist"},
            ]
        )

    # D7. Education credits (no dependents — self might be a student)
    if dependents == 0 and not profile.get("education_status") and not profile.get("_asked_education") and total_income < 180000:
        return (
            "Did you attend college or vocational school? Tuition may qualify for education credits (up to $2,500).",
            [
                {"label": "Yes — I'm a student", "value": "self_student"},
                {"label": "No", "value": "no_education"},
                {"label": "Skip", "value": "skip_education"},
            ]
        )

    # ── BLOCK E: Life events ─────────────────────────────────────────────

    if not profile.get("life_events") and not profile.get("_asked_life_events"):
        return (
            "Did any major life changes happen this year? These can significantly affect your taxes.",
            [
                {"label": "Got married", "value": "event_married"},
                {"label": "Got divorced / separated", "value": "event_divorced"},
                {"label": "Had a baby / adopted", "value": "event_baby"},
                {"label": "Bought a home", "value": "event_bought_home"},
                {"label": "Sold a home", "value": "event_sold_home"},
                {"label": "Changed jobs", "value": "event_job_change"},
                {"label": "Lost a job", "value": "event_job_loss"},
                {"label": "Started a business", "value": "event_started_biz"},
                {"label": "Moved to a different state", "value": "event_moved_states"},
                {"label": "Retired this year", "value": "event_retired"},
                {"label": "Received an inheritance", "value": "event_inheritance"},
                {"label": "None of these", "value": "no_life_events"},
                {"label": "Skip", "value": "skip_life_events"},
            ]
        )

    # E1. Home sale follow-up
    if profile.get("life_events") == "event_sold_home" and not profile.get("home_sale_exclusion") and not profile.get("_asked_home_sale"):
        return (
            "For the home you sold — did you live in it for at least 2 of the last 5 years? (Up to $250K/$500K gain may be tax-free)",
            [
                {"label": "Yes — primary residence 2+ years", "value": "home_sale_excluded"},
                {"label": "No — investment property or < 2 years", "value": "home_sale_taxable"},
                {"label": "Skip", "value": "skip_home_sale"},
            ]
        )

    # E2. State move follow-up
    if profile.get("life_events") == "event_moved_states" and not profile.get("move_date") and not profile.get("_asked_state_move"):
        return (
            "When did you move, and which state did you move from? (You may need to file part-year returns in both states)",
            [
                {"label": "Moved in first half of year", "value": "moved_h1"},
                {"label": "Moved in second half of year", "value": "moved_h2"},
                {"label": "Skip", "value": "skip_state_move"},
            ]
        )

    # E3. Job loss follow-up
    if profile.get("life_events") == "event_job_loss" and not profile.get("unemployment_income") and not profile.get("_asked_job_loss"):
        return (
            "Did you receive unemployment benefits or severance pay?",
            [
                {"label": "Unemployment benefits", "value": "had_unemployment"},
                {"label": "Severance pay", "value": "had_severance"},
                {"label": "Both", "value": "had_both_unemployment_severance"},
                {"label": "Neither", "value": "no_unemployment"},
                {"label": "Skip", "value": "skip_job_loss"},
            ]
        )

    # E4. New business follow-up
    if profile.get("life_events") == "event_started_biz" and not profile.get("startup_costs") and not profile.get("_asked_startup"):
        return (
            "Congratulations on starting a business! Did you have startup costs? (Up to $5,000 may be deductible in year one)",
            [
                {"label": "Yes — under $5,000", "value": "startup_under_5k"},
                {"label": "Yes — $5,000 - $50,000", "value": "startup_5_50k"},
                {"label": "Yes — over $50,000", "value": "startup_over_50k"},
                {"label": "No significant startup costs", "value": "no_startup_costs"},
                {"label": "Skip", "value": "skip_startup"},
            ]
        )

    # E5. Home purchase: mortgage points follow-up
    if profile.get("life_events") == "event_bought_home" and not profile.get("mortgage_points") and not profile.get("_asked_mortgage_points"):
        return (
            "Did you pay mortgage points (origination fees) at closing? Points may be fully deductible in the year of purchase.",
            [
                {"label": "Yes — paid points", "value": "has_mortgage_points"},
                {"label": "No points", "value": "no_mortgage_points"},
                {"label": "Not sure (check closing statement)", "value": "mortgage_points_unsure"},
                {"label": "Skip", "value": "skip_mortgage_points"},
            ]
        )

    # E6. Home purchase: first-time buyer IRA withdrawal
    if profile.get("life_events") == "event_bought_home" and not profile.get("first_home_ira") and not profile.get("_asked_first_home_ira"):
        return (
            "Did you withdraw from an IRA to help buy your first home? (Up to $10,000 is penalty-free for first-time homebuyers)",
            [
                {"label": "Yes", "value": "has_first_home_ira"},
                {"label": "No", "value": "no_first_home_ira"},
                {"label": "Skip", "value": "skip_first_home_ira"},
            ]
        )

    # E7. Home sale: gain amount
    if profile.get("life_events") == "event_sold_home" and not profile.get("home_sale_gain") and not profile.get("_asked_home_gain"):
        return (
            "Approximately how much profit (gain) did you make on the home sale? (Sale price minus original price minus improvements)",
            [
                {"label": "Under $100,000", "value": "home_gain_under_100k"},
                {"label": "$100,000 - $250,000", "value": "home_gain_100_250k"},
                {"label": "$250,000 - $500,000", "value": "home_gain_250_500k"},
                {"label": "Over $500,000", "value": "home_gain_over_500k"},
                {"label": "Loss", "value": "home_gain_loss"},
                {"label": "Skip", "value": "skip_home_gain"},
            ]
        )

    # E7b. Home sale — partial exclusion (lived < 2 years)
    if profile.get("home_sale_exclusion") == "home_sale_taxable" and not profile.get("partial_exclusion") and not profile.get("_asked_partial_exclusion"):
        return (
            "Did you live there less than 2 years but have a qualifying reason for a partial exclusion? (Job change, health, unforeseen circumstances)",
            [
                {"label": "Job-related move", "value": "partial_excl_job"},
                {"label": "Health reasons", "value": "partial_excl_health"},
                {"label": "Unforeseen circumstances", "value": "partial_excl_unforeseen"},
                {"label": "None of these", "value": "no_partial_exclusion"},
                {"label": "Skip", "value": "skip_partial_exclusion"},
            ]
        )

    # E8. Marriage: MFJ vs MFS comparison
    if profile.get("life_events") == "event_married" and not profile.get("mfj_mfs_preference") and not profile.get("_asked_mfj_mfs"):
        return (
            "You got married this year. Would you like us to compare Married Filing Jointly vs Separately to see which saves more?",
            [
                {"label": "Yes — compare both", "value": "compare_mfj_mfs"},
                {"label": "We'll file jointly", "value": "prefer_mfj"},
                {"label": "We'll file separately", "value": "prefer_mfs"},
                {"label": "Skip", "value": "skip_mfj_mfs"},
            ]
        )

    # E9. Divorce: decree year and property transfers
    if profile.get("life_events") == "event_divorced" and not profile.get("divorce_year") and not profile.get("_asked_divorce_year"):
        return (
            "When was your divorce finalized? (Pre-2019 vs post-2019 determines alimony tax treatment. Property transfers in divorce are generally tax-free.)",
            [
                {"label": "Finalized this year", "value": "divorce_this_year"},
                {"label": "Finalized before 2019", "value": "divorce_pre_2019"},
                {"label": "Finalized 2019 or later", "value": "divorce_post_2019"},
                {"label": "Still pending (separated)", "value": "divorce_pending"},
                {"label": "Skip", "value": "skip_divorce_year"},
            ]
        )

    # E9b. Divorce: QDRO distribution
    if profile.get("life_events") in ("event_divorced",) and not profile.get("qdro_distribution") and not profile.get("_asked_qdro"):
        return (
            "Did you receive a distribution from your ex-spouse's retirement plan via a QDRO (Qualified Domestic Relations Order)?",
            [
                {"label": "Yes", "value": "has_qdro"},
                {"label": "No", "value": "no_qdro"},
                {"label": "Skip", "value": "skip_qdro"},
            ]
        )

    # E10. Inheritance: type and details
    if profile.get("life_events") == "event_inheritance" and not profile.get("inheritance_type") and not profile.get("_asked_inheritance_type"):
        return (
            "What did you inherit? (Inherited assets generally get a stepped-up basis — no tax on appreciation during the deceased's lifetime)",
            [
                {"label": "Cash", "value": "inherited_cash"},
                {"label": "Real estate", "value": "inherited_real_estate"},
                {"label": "Investment accounts (stocks/bonds)", "value": "inherited_investments"},
                {"label": "Retirement account (IRA/401k)", "value": "inherited_retirement"},
                {"label": "Business interest", "value": "inherited_business"},
                {"label": "Multiple types", "value": "inherited_multiple"},
                {"label": "Skip", "value": "skip_inheritance_type"},
            ]
        )

    # E11. Job change: 401k rollover
    if profile.get("life_events") == "event_job_change" and not profile.get("job_change_401k") and not profile.get("_asked_job_401k"):
        return (
            "When you changed jobs, what did you do with your old employer's retirement plan?",
            [
                {"label": "Rolled over to new employer plan", "value": "rollover_new_employer"},
                {"label": "Rolled over to IRA", "value": "rollover_ira"},
                {"label": "Cashed out (took a distribution)", "value": "rollover_cashout"},
                {"label": "Left it with old employer", "value": "rollover_left"},
                {"label": "Skip", "value": "skip_job_401k"},
            ]
        )

    # E12. Spouse death (add to life events if not already there)
    if profile.get("life_events") == "event_retired" and not profile.get("spouse_death_year") and filing_status in ("married_joint", "qualifying_widow") and not profile.get("_asked_spouse_death"):
        return (
            "Did your spouse pass away during the tax year? (This affects filing status, final return requirements, and estate considerations)",
            [
                {"label": "Yes — filing final joint return", "value": "spouse_died_this_year"},
                {"label": "No", "value": "spouse_alive"},
                {"label": "Skip", "value": "skip_spouse_death"},
            ]
        )

    # ── BLOCK F: Investments ─────────────────────────────────────────────

    if not profile.get("_has_investments") and not profile.get("investment_income") and not profile.get("capital_gains_long") and not profile.get("_asked_investments"):
        return (
            "Do you have any investment income? This includes stock sales, dividends, interest, or cryptocurrency.",
            [
                {"label": "Yes, I have investments", "value": "has_investments"},
                {"label": "No investment income", "value": "no_investments"},
                {"label": "Skip", "value": "skip_investments"},
            ]
        )

    if profile.get("_has_investments") and not profile.get("investment_income") and not profile.get("_asked_invest_amount"):
        return (
            "Approximately how much total investment income do you have? (dividends, interest, capital gains)",
            [
                {"label": "Under $5,000", "value": "invest_under_5k"},
                {"label": "$5,000 - $25,000", "value": "invest_5_25k"},
                {"label": "$25,000 - $100,000", "value": "invest_25_100k"},
                {"label": "Over $100,000", "value": "invest_over_100k"},
                {"label": "Skip", "value": "skip_invest_amount"},
            ]
        )

    if profile.get("_has_investments") and profile.get("investment_income") and not profile.get("_asked_cap_gains"):
        return (
            "Did you sell any investments this year? Were the gains mostly long-term (held > 1 year) or short-term?",
            [
                {"label": "Mostly long-term gains", "value": "lt_gains"},
                {"label": "Mostly short-term gains", "value": "st_gains"},
                {"label": "Mix of both", "value": "mixed_gains"},
                {"label": "Had losses (not gains)", "value": "had_losses"},
                {"label": "No sales this year", "value": "no_sales"},
                {"label": "Skip", "value": "skip_cap_gains"},
            ]
        )

    # F4. Crypto (if has investments)
    if profile.get("_has_investments") and not profile.get("crypto_activity") and not profile.get("_asked_crypto"):
        return (
            "Did you have any cryptocurrency activity? (Trading, mining, staking, DeFi, NFTs)",
            [
                {"label": "Yes — trading / selling crypto", "value": "crypto_trading"},
                {"label": "Yes — mining or staking", "value": "crypto_mining"},
                {"label": "Yes — multiple activities", "value": "crypto_multiple"},
                {"label": "No crypto activity", "value": "no_crypto"},
                {"label": "Skip", "value": "skip_crypto"},
            ]
        )

    # F5. Stock options / RSU / ESPP (W-2 high earners)
    if is_w2 and total_income > 100000 and not profile.get("stock_compensation") and not profile.get("_asked_stock_comp"):
        return (
            "Do you have any employer stock compensation? (Stock options, RSUs, or ESPP)",
            [
                {"label": "Incentive Stock Options (ISO)", "value": "has_iso"},
                {"label": "Non-Qualified Options (NSO)", "value": "has_nso"},
                {"label": "Restricted Stock Units (RSU)", "value": "has_rsu"},
                {"label": "Employee Stock Purchase Plan (ESPP)", "value": "has_espp"},
                {"label": "Multiple types", "value": "multiple_stock_comp"},
                {"label": "None", "value": "no_stock_comp"},
                {"label": "Skip", "value": "skip_stock_comp"},
            ]
        )

    # --- F6. Wash sale awareness ---
    if profile.get("capital_gains_type") in ("had_losses", "mixed_gains") and not profile.get("wash_sale") and not profile.get("_asked_wash_sale"):
        return (
            "Did you sell any investments at a loss and buy the same or similar securities within 30 days? (This is a 'wash sale' — the loss is disallowed)",
            [
                {"label": "Yes / Possibly", "value": "has_wash_sale"},
                {"label": "No", "value": "no_wash_sale"},
                {"label": "Not sure", "value": "wash_sale_unsure"},
                {"label": "Skip", "value": "skip_wash_sale"},
            ]
        )

    # --- F7. NIIT check (3.8% surtax) ---
    _niit_threshold = 200000 if filing_status != "married_joint" else 250000
    if total_income > _niit_threshold and profile.get("_has_investments") and not profile.get("niit_status") and not profile.get("_asked_niit"):
        return (
            f"Your income exceeds the Net Investment Income Tax threshold (${_niit_threshold:,.0f}). You may owe an additional 3.8% tax on investment income.",
            [
                {"label": "I understand — include in calculation", "value": "niit_applies"},
                {"label": "Skip", "value": "skip_niit"},
            ]
        )

    # --- F8. Installment sale ---
    if profile.get("_has_investments") and not profile.get("installment_sale") and not profile.get("_asked_installment"):
        return (
            "Did you sell property and receive payments over multiple years? (Installment sale — report gain as payments are received)",
            [
                {"label": "Yes", "value": "has_installment_sale"},
                {"label": "No", "value": "no_installment_sale"},
                {"label": "Skip", "value": "skip_installment"},
            ]
        )

    # --- F9. Like-kind exchange (1031) ---
    if (profile.get("_has_investments") or profile.get("_has_rental")) and not profile.get("like_kind_exchange") and not profile.get("_asked_1031"):
        return (
            "Did you exchange any investment or business real property for similar property? (1031 like-kind exchange — defers capital gains)",
            [
                {"label": "Yes — completed exchange", "value": "has_1031_exchange"},
                {"label": "Yes — currently in exchange period", "value": "in_1031_exchange"},
                {"label": "No", "value": "no_1031_exchange"},
                {"label": "Skip", "value": "skip_1031"},
            ]
        )

    # --- F10. QSBS (Section 1202 — up to $10M gain exclusion) ---
    if profile.get("_has_investments") and total_income > 100000 and not profile.get("qsbs_sale") and not profile.get("_asked_qsbs"):
        return (
            "Did you sell stock in a qualified small business (Section 1202 QSBS)? You may exclude up to $10M or 10x basis in gain if held 5+ years.",
            [
                {"label": "Yes — held 5+ years", "value": "qsbs_qualified"},
                {"label": "Yes — held less than 5 years", "value": "qsbs_not_qualified"},
                {"label": "No / Not sure", "value": "no_qsbs"},
                {"label": "Skip", "value": "skip_qsbs"},
            ]
        )

    # --- F11. QOZ (Qualified Opportunity Zone) investment ---
    if profile.get("capital_gains_type") in ("lt_gains", "st_gains", "mixed_gains") and not profile.get("qoz_investment") and not profile.get("_asked_qoz"):
        return (
            "Did you invest capital gains into a Qualified Opportunity Zone fund? (Significant tax deferral/exclusion benefits)",
            [
                {"label": "Yes", "value": "has_qoz"},
                {"label": "No", "value": "no_qoz"},
                {"label": "Skip", "value": "skip_qoz"},
            ]
        )

    # --- F12. Collectibles (28% rate) ---
    if profile.get("_has_investments") and not profile.get("collectibles_sold") and not profile.get("_asked_collectibles"):
        return (
            "Did you sell any collectibles? (Art, antiques, coins, stamps, precious metals, gems — taxed at 28% max rate instead of 20%)",
            [
                {"label": "Yes", "value": "has_collectibles"},
                {"label": "No", "value": "no_collectibles"},
                {"label": "Skip", "value": "skip_collectibles"},
            ]
        )

    # --- F13. Investment interest expense (margin interest) ---
    if profile.get("_has_investments") and float(profile.get("investment_income", 0) or 0) > 25000 and not profile.get("investment_interest_expense") and not profile.get("_asked_inv_interest"):
        return (
            "Did you borrow money to buy investments? (Margin interest, investment-related interest expense — deductible against investment income)",
            [
                {"label": "Yes", "value": "has_inv_interest_expense"},
                {"label": "No", "value": "no_inv_interest_expense"},
                {"label": "Skip", "value": "skip_inv_interest"},
            ]
        )

    # --- F14. Passive activity loss carryforward ---
    if (profile.get("_has_rental") or profile.get("_has_k1")) and not profile.get("passive_loss_carryforward") and not profile.get("_asked_passive_carryforward"):
        return (
            "Do you have passive activity losses from prior years that were disallowed? (Rental losses, limited partnership losses carried forward)",
            [
                {"label": "Yes — prior year suspended losses", "value": "has_passive_carryforward"},
                {"label": "No", "value": "no_passive_carryforward"},
                {"label": "Not sure", "value": "passive_carryforward_unsure"},
                {"label": "Skip", "value": "skip_passive_carryforward"},
            ]
        )

    # --- F15. Additional Medicare Tax (0.9% on earned income over threshold) ---
    _amt_threshold = 200000 if filing_status != "married_joint" else 250000
    if total_income > _amt_threshold and not profile.get("addl_medicare_tax") and not profile.get("_asked_addl_medicare"):
        return (
            f"Your earned income exceeds ${_amt_threshold:,.0f}. You may owe the 0.9% Additional Medicare Tax on earnings above that threshold.",
            [
                {"label": "I understand — include in calculation", "value": "addl_medicare_applies"},
                {"label": "Skip", "value": "skip_addl_medicare"},
            ]
        )

    # --- F16. Section 1256 contracts (futures/forex — 60/40 rule) ---
    if profile.get("_has_investments") and not profile.get("section_1256") and not profile.get("_asked_section_1256"):
        return (
            "Did you trade futures, options on futures, or foreign currency contracts? (Section 1256 — special 60/40 long-term/short-term treatment)",
            [
                {"label": "Yes — regulated futures/options", "value": "has_section_1256"},
                {"label": "Yes — forex (Section 988)", "value": "has_forex"},
                {"label": "No", "value": "no_section_1256"},
                {"label": "Skip", "value": "skip_section_1256"},
            ]
        )

    # --- F17. MLP (Master Limited Partnership) ---
    if profile.get("_has_investments") and not profile.get("mlp_income") and not profile.get("_asked_mlp"):
        return (
            "Do you own any Master Limited Partnerships (MLPs)? (Common in energy/pipeline — K-1 with unique tax treatment)",
            [
                {"label": "Yes", "value": "has_mlp"},
                {"label": "No", "value": "no_mlp"},
                {"label": "Skip", "value": "skip_mlp"},
            ]
        )

    # --- F18. ESPP disposition type ---
    if profile.get("stock_compensation") in ("has_espp", "multiple") and not profile.get("espp_disposition") and not profile.get("_asked_espp_disp"):
        return (
            "For ESPP shares you sold: did you hold them 2+ years from grant date AND 1+ year from purchase? (Qualifying vs disqualifying disposition)",
            [
                {"label": "Qualifying (met holding periods)", "value": "espp_qualifying"},
                {"label": "Disqualifying (sold early)", "value": "espp_disqualifying"},
                {"label": "Haven't sold any shares", "value": "espp_not_sold"},
                {"label": "Skip", "value": "skip_espp_disp"},
            ]
        )

    # --- F19. ISO AMT adjustment detail ---
    if profile.get("stock_compensation") in ("has_iso", "multiple") and not profile.get("iso_amt_detail") and not profile.get("_asked_iso_amt"):
        return (
            "Did you exercise ISOs and HOLD (not sell same year)? The spread is an AMT preference item.",
            [
                {"label": "Exercised and held (AMT applies)", "value": "iso_exercised_held"},
                {"label": "Exercised and sold same year (no AMT)", "value": "iso_same_day"},
                {"label": "Skip", "value": "skip_iso_amt"},
            ]
        )

    # ── BLOCK G: Retirement & savings (non-retired) ──────────────────────

    if not is_retired:
        if not profile.get("retirement_401k") and not profile.get("retirement_ira") and not profile.get("_asked_retirement"):
            retirement_options = [
                {"label": "401(k) / 403(b) / TSP", "value": "has_401k"},
                {"label": "Traditional IRA", "value": "has_trad_ira"},
                {"label": "Roth IRA", "value": "has_roth_ira"},
                {"label": "Both employer plan and IRA", "value": "has_both_retirement"},
            ]
            if is_se:
                retirement_options.extend([
                    {"label": "SEP-IRA (self-employed)", "value": "has_sep"},
                    {"label": "Solo 401(k) (self-employed)", "value": "has_solo_401k"},
                ])
            retirement_options.extend([
                {"label": "No retirement contributions", "value": "no_retirement"},
                {"label": "Skip", "value": "skip_retirement"},
            ])
            return (
                "Are you contributing to any retirement accounts? This can significantly reduce your taxes.",
                retirement_options
            )

    # G2. HSA (everyone)
    if not profile.get("hsa_contributions") and not profile.get("_asked_hsa"):
        return (
            "Do you have a Health Savings Account (HSA)? Contributions are triple tax-advantaged — deductible, grow tax-free, and withdraw tax-free for medical expenses.",
            [
                {"label": "Yes, I contribute to an HSA", "value": "has_hsa"},
                {"label": "I have an HDHP but no HSA yet", "value": "has_hdhp_no_hsa"},
                {"label": "No HSA / not eligible", "value": "no_hsa"},
                {"label": "Skip", "value": "skip_hsa"},
            ]
        )

    # G3. Retirement distributions (anyone can have these)
    if not profile.get("retirement_distributions") and not profile.get("_asked_distributions"):
        return (
            "Did you take any distributions (withdrawals) from retirement accounts this year?",
            [
                {"label": "Yes — IRA withdrawal", "value": "ira_distribution"},
                {"label": "Yes — 401(k) withdrawal", "value": "401k_distribution"},
                {"label": "Yes — Roth conversion", "value": "roth_conversion"},
                {"label": "No distributions", "value": "no_distributions"},
                {"label": "Skip", "value": "skip_distributions"},
            ]
        )

    # G4. Early withdrawal penalty (follow-up)
    if profile.get("retirement_distributions") in ("ira_distribution", "401k_distribution") and not profile.get("early_withdrawal_status") and not profile.get("_asked_early_withdrawal"):
        return (
            "Are you under age 59½? Early withdrawals may incur a 10% penalty unless an exception applies.",
            [
                {"label": "Under 59½ — no exception", "value": "early_no_exception"},
                {"label": "Under 59½ — exception applies (disability, first home, SEPP)", "value": "early_with_exception"},
                {"label": "59½ or older", "value": "over_59_half"},
                {"label": "Skip", "value": "skip_early"},
            ]
        )

    # --- G5. Backdoor Roth IRA ---
    if (profile.get("retirement_401k") or profile.get("retirement_ira")) and total_income > 150000 and not profile.get("backdoor_roth") and not profile.get("_asked_backdoor_roth"):
        return (
            "Did you make a non-deductible Traditional IRA contribution and convert it to a Roth? (Backdoor Roth strategy — requires Form 8606)",
            [
                {"label": "Yes — backdoor Roth", "value": "has_backdoor_roth"},
                {"label": "No", "value": "no_backdoor_roth"},
                {"label": "Skip", "value": "skip_backdoor_roth"},
            ]
        )

    # --- G6. IRA basis (Form 8606 — pro-rata rule) ---
    if profile.get("retirement_distributions") in ("ira_distribution", "roth_conversion") and not profile.get("ira_basis") and not profile.get("_asked_ira_basis"):
        return (
            "Do you have non-deductible (after-tax) contributions in your Traditional IRA? (This affects tax on distributions — pro-rata rule)",
            [
                {"label": "Yes — I have basis in my IRA", "value": "has_ira_basis"},
                {"label": "No — all contributions were deductible", "value": "no_ira_basis"},
                {"label": "Not sure", "value": "ira_basis_unsure"},
                {"label": "Skip", "value": "skip_ira_basis"},
            ]
        )

    # --- G7. Inherited IRA (SECURE Act rules) ---
    if not profile.get("inherited_ira") and not profile.get("_asked_inherited_ira"):
        return (
            "Did you inherit a retirement account (IRA or 401k)? The rules for required distributions depend on when the original owner died.",
            [
                {"label": "Yes — inherited before 2020 (stretch IRA)", "value": "inherited_ira_pre_2020"},
                {"label": "Yes — inherited 2020+ (10-year rule)", "value": "inherited_ira_post_2020"},
                {"label": "Yes — I'm a spouse beneficiary", "value": "inherited_ira_spouse"},
                {"label": "No", "value": "no_inherited_ira"},
                {"label": "Skip", "value": "skip_inherited_ira"},
            ]
        )

    # --- G8. QCD — Qualified Charitable Distribution (70.5+) ---
    if is_retired and profile.get("age") in ("age_65_plus",) and not profile.get("qcd") and not profile.get("_asked_qcd"):
        return (
            "Are you 70½ or older? Did you make a Qualified Charitable Distribution (QCD) directly from your IRA to charity? (Up to $105,000 excluded from income — counts toward RMD)",
            [
                {"label": "Yes — made QCD", "value": "has_qcd"},
                {"label": "Under 70½", "value": "under_70_half"},
                {"label": "No QCD", "value": "no_qcd"},
                {"label": "Skip", "value": "skip_qcd"},
            ]
        )

    # --- G9. EITC eligibility check (Tier 1 — most common refundable credit) ---
    _eitc_thresholds = {0: 18591, 1: 49084, 2: 55768, 3: 59899}
    _eitc_limit = _eitc_thresholds.get(min(dependents, 3), 59899)
    if filing_status == "married_joint":
        _eitc_limit += 7430
    if total_income <= _eitc_limit and filing_status != "married_separate" and not profile.get("eitc_status") and not profile.get("_asked_eitc"):
        return (
            "Based on your income and filing status, you may qualify for the Earned Income Tax Credit (EITC) — one of the largest refundable credits. Do you have earned income (wages or self-employment)?",
            [
                {"label": "Yes — I think I qualify", "value": "eitc_likely"},
                {"label": "I have investment income over $11,600 (disqualifies)", "value": "eitc_inv_too_high"},
                {"label": "Not sure", "value": "eitc_unsure"},
                {"label": "Skip", "value": "skip_eitc"},
            ]
        )

    # --- G10. Saver's Credit (massively underclaimed) ---
    _savers_limit = 38250 if filing_status == "single" else 76500 if filing_status == "married_joint" else 57375
    if total_income <= _savers_limit and (profile.get("retirement_401k") or profile.get("retirement_ira")) and not profile.get("savers_credit") and not profile.get("_asked_savers_credit"):
        return (
            "You may qualify for the Retirement Savings Credit (Saver's Credit) — up to $1,000/$2,000. This is separate from your IRA/401k deduction.",
            [
                {"label": "Great — include it!", "value": "savers_credit_yes"},
                {"label": "I'm a full-time student (disqualifies)", "value": "savers_student"},
                {"label": "Skip", "value": "skip_savers_credit"},
            ]
        )

    # --- G11. Credit for Elderly or Disabled (Schedule R) ---
    if (profile.get("age") in ("age_65_plus",) or profile.get("disability_income_type")) and total_income < 25000 and not profile.get("elderly_disabled_credit") and not profile.get("_asked_elderly_credit"):
        return (
            "You may qualify for the Credit for the Elderly or Disabled (Schedule R). Are you 65+ or permanently disabled with limited income?",
            [
                {"label": "Yes — I think I qualify", "value": "elderly_credit_yes"},
                {"label": "Income too high", "value": "elderly_credit_no"},
                {"label": "Skip", "value": "skip_elderly_credit"},
            ]
        )

    # --- G12. Catch-up contributions (50+) ---
    if profile.get("age") in ("age_50_64", "age_65_plus") and (profile.get("retirement_401k") or profile.get("retirement_ira")) and not profile.get("catch_up_contributions") and not profile.get("_asked_catch_up"):
        return (
            "Are you making catch-up contributions? (50+: extra $7,500 for 401k, extra $1,000 for IRA)",
            [
                {"label": "Yes — catch-up contributions", "value": "has_catch_up"},
                {"label": "No", "value": "no_catch_up"},
                {"label": "Skip", "value": "skip_catch_up"},
            ]
        )

    # --- G13. Mega Backdoor Roth ---
    if is_w2 and total_income > 150000 and profile.get("retirement_401k") and not profile.get("mega_backdoor_roth") and not profile.get("_asked_mega_backdoor"):
        return (
            "Does your 401(k) plan allow after-tax contributions beyond the $23,500 limit? (Mega Backdoor Roth strategy — up to $69,000 total)",
            [
                {"label": "Yes — my plan allows it", "value": "has_mega_backdoor"},
                {"label": "No / Not sure", "value": "no_mega_backdoor"},
                {"label": "Skip", "value": "skip_mega_backdoor"},
            ]
        )

    # --- G14. IRA deductibility check ---
    if profile.get("retirement_ira") and not profile.get("ira_deductibility") and not profile.get("_asked_ira_deduct"):
        return (
            "You contribute to a Traditional IRA. Do you or your spouse have a retirement plan at work? (Affects whether IRA contribution is deductible)",
            [
                {"label": "Yes — I have plan at work", "value": "ira_has_workplace_plan"},
                {"label": "Yes — spouse has plan at work", "value": "ira_spouse_workplace_plan"},
                {"label": "Neither of us", "value": "ira_no_workplace_plan"},
                {"label": "Skip", "value": "skip_ira_deduct"},
            ]
        )

    # --- G15. CTC phaseout awareness ---
    _ctc_phase = 200000 if filing_status != "married_joint" else 400000
    if dependents > 0 and (profile.get("dependents_under_17") or 0) > 0 and total_income > _ctc_phase * 0.8 and not profile.get("ctc_phaseout_aware") and not profile.get("_asked_ctc_phaseout"):
        return (
            f"Your income may affect your Child Tax Credit. Is your AGI over ${_ctc_phase:,.0f}? (Credit phases out at $50 per $1,000 over the threshold)",
            [
                {"label": "Under the threshold", "value": "ctc_under_threshold"},
                {"label": "Over the threshold", "value": "ctc_over_threshold"},
                {"label": "Not sure", "value": "ctc_threshold_unsure"},
                {"label": "Skip", "value": "skip_ctc_phaseout"},
            ]
        )

    # --- G16. Foreign Tax Credit detail ---
    if profile.get("foreign_income") and profile.get("foreign_income") not in ("none", "no_foreign") and not profile.get("foreign_tax_credit_detail") and not profile.get("_asked_ftc_detail"):
        return (
            "How much in foreign taxes did you pay? (If under $300 single/$600 MFJ from qualified passive income, you can claim directly without Form 1116)",
            [
                {"label": "Under $300 (single) / $600 (MFJ)", "value": "ftc_simple"},
                {"label": "$300 - $5,000", "value": "ftc_moderate"},
                {"label": "Over $5,000", "value": "ftc_complex"},
                {"label": "Skip", "value": "skip_ftc_detail"},
            ]
        )

    # --- G17. ACA reconciliation ---
    if profile.get("aca_marketplace") == "with_subsidy" and not profile.get("aca_reconciliation") and not profile.get("_asked_aca_recon"):
        return (
            "Did your income end up higher or lower than estimated when you enrolled in the ACA Marketplace? (Affects whether you owe money back or get a bigger credit)",
            [
                {"label": "Income was higher than estimated", "value": "aca_income_higher"},
                {"label": "Income was lower", "value": "aca_income_lower"},
                {"label": "About what I estimated", "value": "aca_income_same"},
                {"label": "Skip", "value": "skip_aca_recon"},
            ]
        )

    # ── BLOCK H: Deductions ──────────────────────────────────────────────

    if not profile.get("mortgage_interest") and not profile.get("_asked_deductions") and not profile.get("_deduction_check"):
        return (
            "Let's check your deductions. Do you have any of these?",
            [
                {"label": "Mortgage interest", "value": "has_mortgage"},
                {"label": "Charitable donations", "value": "has_charitable"},
                {"label": "Property taxes", "value": "has_property_taxes"},
                {"label": "High medical expenses", "value": "has_medical"},
                {"label": "State/local income taxes paid", "value": "has_salt"},
                {"label": "None — I'll take the standard deduction", "value": "no_itemized_deductions"},
                {"label": "Skip", "value": "skip_deductions"},
            ]
        )

    # H follow-ups (mortgage, property tax, charitable, medical)
    if profile.get("_has_mortgage") and not profile.get("mortgage_interest") and not profile.get("_asked_mortgage_amount"):
        return (
            "How much mortgage interest did you pay this year? (Check Form 1098)",
            [
                {"label": "Under $5,000", "value": "mortgage_under_5k"},
                {"label": "$5,000 - $15,000", "value": "mortgage_5_15k"},
                {"label": "$15,000 - $30,000", "value": "mortgage_15_30k"},
                {"label": "Over $30,000", "value": "mortgage_over_30k"},
                {"label": "Skip", "value": "skip_mortgage_amount"},
            ]
        )

    if profile.get("_has_property_taxes") and not profile.get("property_taxes") and not profile.get("_asked_prop_tax_amount"):
        return (
            "How much did you pay in property taxes?",
            [
                {"label": "Under $5,000", "value": "prop_tax_under_5k"},
                {"label": "$5,000 - $10,000", "value": "prop_tax_5_10k"},
                {"label": "Over $10,000 (SALT cap applies)", "value": "prop_tax_over_10k"},
                {"label": "Skip", "value": "skip_prop_tax_amount"},
            ]
        )

    if profile.get("_has_charitable") and not profile.get("charitable_donations") and not profile.get("_asked_charitable_amount"):
        return (
            "How much did you donate to charity this year?",
            [
                {"label": "Under $1,000", "value": "charity_under_1k"},
                {"label": "$1,000 - $5,000", "value": "charity_1_5k"},
                {"label": "$5,000 - $20,000", "value": "charity_5_20k"},
                {"label": "Over $20,000", "value": "charity_over_20k"},
                {"label": "Skip", "value": "skip_charitable_amount"},
            ]
        )

    if profile.get("_has_medical") and not profile.get("medical_expenses") and not profile.get("_asked_medical_amount"):
        return (
            "Approximately how much in unreimbursed medical expenses? (Only deductible if over 7.5% of your income)",
            [
                {"label": "Under $5,000", "value": "medical_under_5k"},
                {"label": "$5,000 - $15,000", "value": "medical_5_15k"},
                {"label": "$15,000 - $30,000", "value": "medical_15_30k"},
                {"label": "Over $30,000", "value": "medical_over_30k"},
                {"label": "Skip", "value": "skip_medical_amount"},
            ]
        )

    # H6. Student loans
    if not profile.get("student_loan_interest") and not profile.get("_asked_student_loans") and total_income < 180000:
        return (
            "Did you pay any student loan interest this year? (Up to $2,500 may be deductible)",
            [
                {"label": "Yes", "value": "has_student_loans"},
                {"label": "No student loans", "value": "no_student_loans"},
                {"label": "Skip", "value": "skip_student_loans"},
            ]
        )

    # H7. Educator expenses (W-2 teachers)
    if is_w2 and not profile.get("educator_expenses") and not profile.get("_asked_educator"):
        return (
            "Are you a K-12 teacher or educator? You may deduct up to $300 in classroom supplies.",
            [
                {"label": "Yes — I'm an educator", "value": "is_educator"},
                {"label": "No", "value": "not_educator"},
            ]
        )

    # --- H8. Non-cash charitable donations (Form 8283) ---
    if profile.get("_has_charitable") and not profile.get("noncash_charitable") and not profile.get("_asked_noncash_charitable"):
        return (
            "Did any of your charitable donations include non-cash items worth more than $500? (Clothing, furniture, vehicles, stock, artwork)",
            [
                {"label": "Yes — donated property/goods over $500", "value": "noncash_goods"},
                {"label": "Yes — donated appreciated stock/securities", "value": "noncash_stock"},
                {"label": "Yes — donated vehicle worth over $500", "value": "noncash_vehicle"},
                {"label": "No — all cash/check donations", "value": "noncash_none"},
                {"label": "Skip", "value": "skip_noncash_charitable"},
            ]
        )

    # --- H9. Casualty/disaster loss ---
    if not profile.get("casualty_loss") and not profile.get("_asked_casualty"):
        return (
            "Did you suffer losses from a federally declared disaster? (Flood, hurricane, wildfire, tornado — only disaster losses are deductible post-TCJA)",
            [
                {"label": "Yes — federally declared disaster", "value": "has_casualty_loss"},
                {"label": "No disaster losses", "value": "no_casualty_loss"},
                {"label": "Skip", "value": "skip_casualty"},
            ]
        )

    # --- H10. Home office method (simplified vs regular) ---
    if profile.get("home_office_sqft") and profile.get("home_office_sqft") not in (0, "no_home_office") and not profile.get("home_office_method") and not profile.get("_asked_ho_method"):
        return (
            "For your home office, would you like the simplified method ($5/sq ft, max $1,500) or the regular method (actual expenses)?",
            [
                {"label": "Simplified ($5/sq ft)", "value": "ho_simplified"},
                {"label": "Regular (actual expenses)", "value": "ho_regular"},
                {"label": "Not sure — help me decide", "value": "ho_unsure"},
                {"label": "Skip", "value": "skip_ho_method"},
            ]
        )

    # --- H11. Business meals & travel ---
    if is_se and profile.get("business_income") and not profile.get("biz_meals_travel") and not profile.get("_asked_biz_meals"):
        return (
            "Did you have business travel or client meal expenses this year?",
            [
                {"label": "Yes — significant travel", "value": "biz_travel"},
                {"label": "Yes — mainly meals", "value": "biz_meals"},
                {"label": "Both", "value": "biz_meals_and_travel"},
                {"label": "No travel or meal expenses", "value": "no_biz_meals"},
                {"label": "Skip", "value": "skip_biz_meals"},
            ]
        )

    # --- H12. Business insurance ---
    if is_se and profile.get("business_income") and not profile.get("biz_insurance") and not profile.get("_asked_biz_insurance"):
        return (
            "Do you pay for business insurance? (Liability, E&O, professional, cyber, business property)",
            [
                {"label": "Yes", "value": "has_biz_insurance"},
                {"label": "No", "value": "no_biz_insurance"},
                {"label": "Skip", "value": "skip_biz_insurance"},
            ]
        )

    # --- H13. NOL carryforward ---
    if is_se and not profile.get("nol_carryforward") and not profile.get("_asked_nol"):
        return (
            "Do you have a net operating loss (NOL) from prior years to carry forward?",
            [
                {"label": "Yes", "value": "has_nol"},
                {"label": "No", "value": "no_nol"},
                {"label": "Not sure", "value": "nol_unsure"},
                {"label": "Skip", "value": "skip_nol"},
            ]
        )

    # --- H13b. Archer MSA (rare, being phased out) ---
    if is_se and not profile.get("archer_msa") and not profile.get("_asked_archer_msa"):
        return (
            "Do you have an Archer Medical Savings Account (MSA)? (Rare — for self-employed or small employer workers, being phased out)",
            [
                {"label": "Yes", "value": "has_archer_msa"},
                {"label": "No", "value": "no_archer_msa"},
                {"label": "Skip", "value": "skip_archer_msa"},
            ]
        )

    # --- H14. Early CD/savings withdrawal penalty ---
    if not profile.get("early_savings_penalty") and not profile.get("_asked_early_savings"):
        return (
            "Were you charged an early withdrawal penalty by your bank for breaking a CD or time deposit? (Above-the-line deduction)",
            [
                {"label": "Yes", "value": "has_early_savings_penalty"},
                {"label": "No", "value": "no_early_savings_penalty"},
                {"label": "Skip", "value": "skip_early_savings"},
            ]
        )

    # --- H15. Student loan interest amount (follow-up) ---
    if profile.get("student_loan_interest") and profile.get("student_loan_interest") not in (0, "no", "no_student_loans") and not profile.get("student_loan_amount") and not profile.get("_asked_sl_amount"):
        return (
            "How much student loan interest did you pay? (Deductible up to $2,500 — check Form 1098-E)",
            [
                {"label": "Under $1,000", "value": "sl_under_1k"},
                {"label": "$1,000 - $2,500", "value": "sl_1_2500"},
                {"label": "Over $2,500 (capped at $2,500)", "value": "sl_over_2500"},
                {"label": "Skip", "value": "skip_sl_amount"},
            ]
        )

    # --- H16. Gambling loss follow-up ---
    if profile.get("gambling_income") in ("gambling_winnings", "gambling_losses") and not profile.get("gambling_loss_detail") and not profile.get("_asked_gambling_loss"):
        return (
            "Were your gambling losses at least equal to your winnings? (You can deduct losses up to winnings if you itemize)",
            [
                {"label": "Losses exceed winnings", "value": "gambling_losses_exceed"},
                {"label": "Losses less than winnings", "value": "gambling_losses_less"},
                {"label": "Skip", "value": "skip_gambling_loss"},
            ]
        )

    # --- H17. Business: accounting method ---
    if is_se and profile.get("business_income") and not profile.get("accounting_method") and not profile.get("_asked_accounting"):
        return (
            "What accounting method does your business use?",
            [
                {"label": "Cash basis", "value": "accounting_cash"},
                {"label": "Accrual basis", "value": "accounting_accrual"},
                {"label": "Not sure", "value": "accounting_unsure"},
                {"label": "Skip", "value": "skip_accounting"},
            ]
        )

    # --- H18. Business: inventory ---
    if is_se and profile.get("business_income") and not profile.get("has_inventory") and not profile.get("_asked_inventory"):
        return (
            "Does your business carry inventory? (Products for sale, raw materials — affects Cost of Goods Sold)",
            [
                {"label": "Yes", "value": "has_inventory"},
                {"label": "No — service-based business", "value": "no_inventory"},
                {"label": "Skip", "value": "skip_inventory"},
            ]
        )

    # --- H19. Business: sale of business property (Form 4797) ---
    if is_se and profile.get("business_income") and not profile.get("sold_biz_property") and not profile.get("_asked_sold_biz_prop"):
        return (
            "Did you sell or dispose of any business property or equipment this year? (Form 4797)",
            [
                {"label": "Yes — sold at a gain", "value": "biz_prop_gain"},
                {"label": "Yes — sold at a loss", "value": "biz_prop_loss"},
                {"label": "No", "value": "no_sold_biz_prop"},
                {"label": "Skip", "value": "skip_sold_biz_prop"},
            ]
        )

    # --- H20. Business: listed property use % ---
    if is_se and not profile.get("listed_property") and not profile.get("_asked_listed_prop"):
        return (
            "Do you use any of these for both business and personal: vehicle, computer, camera, phone? What's the business-use %?",
            [
                {"label": "Over 50% business use", "value": "listed_prop_over_50"},
                {"label": "Under 50% business use", "value": "listed_prop_under_50"},
                {"label": "100% business use", "value": "listed_prop_100"},
                {"label": "No listed property", "value": "no_listed_prop"},
                {"label": "Skip", "value": "skip_listed_prop"},
            ]
        )

    # --- H21. Business: excess business loss limitation ---
    _ebl_limit = 305000 if filing_status != "married_joint" else 610000
    if is_se and profile.get("business_income") and float(profile.get("business_income", 0) or 0) < -100000 and not profile.get("excess_biz_loss") and not profile.get("_asked_excess_biz_loss"):
        return (
            f"Are your total business losses exceeding ${_ebl_limit:,.0f}? The excess converts to an NOL carryforward.",
            [
                {"label": "Yes", "value": "has_excess_biz_loss"},
                {"label": "No", "value": "no_excess_biz_loss"},
                {"label": "Not sure", "value": "excess_biz_loss_unsure"},
                {"label": "Skip", "value": "skip_excess_biz_loss"},
            ]
        )

    # --- H22. Business: retirement plan for employees ---
    if profile.get("has_employees_status") in ("employees", "both") and not profile.get("employer_retirement_plan") and not profile.get("_asked_employer_ret_plan"):
        return (
            "Do you offer a retirement plan for your employees? (SIMPLE IRA, SEP-IRA, 401k — employer contributions are deductible)",
            [
                {"label": "Yes", "value": "has_employer_ret_plan"},
                {"label": "No — interested in learning more", "value": "employer_ret_interested"},
                {"label": "No", "value": "no_employer_ret_plan"},
                {"label": "Skip", "value": "skip_employer_ret_plan"},
            ]
        )

    # --- H23. QBI W-2 wage limitation (high income) ---
    if is_se and total_income > 191950 and profile.get("has_employees_status") and not profile.get("qbi_w2_wages") and not profile.get("_asked_qbi_wages"):
        return (
            "For QBI deduction purposes: how much did your business pay in total W-2 wages? (Affects deduction at your income level)",
            [
                {"label": "Under $100,000", "value": "qbi_wages_under_100k"},
                {"label": "$100,000 - $250,000", "value": "qbi_wages_100_250k"},
                {"label": "Over $250,000", "value": "qbi_wages_over_250k"},
                {"label": "No W-2 employees", "value": "qbi_no_w2_wages"},
                {"label": "Skip", "value": "skip_qbi_wages"},
            ]
        )

    # ── BLOCK I: Rental property ─────────────────────────────────────────

    # Skip for low-income W-2 only (unlikely to have rentals)
    _is_low_income_w2 = income_type == "w2_employee" and total_income < 75000 and not profile.get("_has_investments")
    if not _is_low_income_w2:
        if not profile.get("rental_income") and not profile.get("_has_rental") and not profile.get("_asked_rental"):
            return (
                "Do you own any rental properties?",
                [
                    {"label": "Yes — 1 property", "value": "rental_1"},
                    {"label": "Yes — 2-4 properties", "value": "rental_2_4"},
                    {"label": "Yes — 5+ properties", "value": "rental_5plus"},
                    {"label": "No rental properties", "value": "no_rental"},
                    {"label": "Skip", "value": "skip_rental"},
                ]
            )

        if profile.get("_has_rental") and profile.get("_has_rental") not in ("no_rental",) and not profile.get("rental_income") and not profile.get("_asked_rental_amount"):
            return (
                "What's your approximate annual net rental income (after expenses)?",
                [
                    {"label": "Under $10,000 profit", "value": "rental_under_10k"},
                    {"label": "$10,000 - $25,000", "value": "rental_10_25k"},
                    {"label": "$25,000 - $50,000", "value": "rental_25_50k"},
                    {"label": "Over $50,000", "value": "rental_over_50k"},
                    {"label": "Net loss", "value": "rental_net_loss"},
                    {"label": "Skip", "value": "skip_rental_amount"},
                ]
            )

        if profile.get("rental_income") and not profile.get("rental_participation") and not profile.get("_asked_participation"):
            return (
                "Do you actively participate in managing your rentals? (Make decisions, approve tenants, authorize repairs)",
                [
                    {"label": "Yes — I actively manage them", "value": "active_participation"},
                    {"label": "I use a property manager for everything", "value": "passive_participation"},
                    {"label": "I'm a real estate professional (750+ hrs)", "value": "re_professional"},
                    {"label": "Skip", "value": "skip_participation"},
                ]
            )

    # --- I4. Short-term rental (Airbnb/VRBO) ---
    if profile.get("rental_income") and not profile.get("short_term_rental") and not profile.get("_asked_short_term"):
        return (
            "Is your rental a short-term rental (average stay under 7 days)? Short-term rentals have different SE tax and passive rules.",
            [
                {"label": "Yes — short-term (Airbnb/VRBO)", "value": "is_short_term_rental"},
                {"label": "Yes — with hotel-like services", "value": "short_term_hotel_services"},
                {"label": "No — long-term rental", "value": "long_term_rental"},
                {"label": "Skip", "value": "skip_short_term"},
            ]
        )

    # --- I5. Personal use days ---
    if profile.get("rental_income") and not profile.get("personal_use_days") and not profile.get("_asked_personal_use"):
        return (
            "Did you or family use the rental property personally for more than 14 days (or 10% of rental days)? This limits deductions.",
            [
                {"label": "Yes — personal use exceeds limit", "value": "personal_use_excess"},
                {"label": "No — minimal personal use", "value": "personal_use_minimal"},
                {"label": "Not sure", "value": "personal_use_unsure"},
                {"label": "Skip", "value": "skip_personal_use"},
            ]
        )

    # --- I6. Below FMV rental (family) ---
    if profile.get("rental_income") and not profile.get("below_fmv_rental") and not profile.get("_asked_below_fmv"):
        return (
            "Do you rent to a family member or anyone below fair market value? (Below-FMV rentals have limited deductions)",
            [
                {"label": "Yes — below market rent", "value": "rental_below_fmv"},
                {"label": "No — fair market rent", "value": "rental_fair_market"},
                {"label": "Skip", "value": "skip_below_fmv"},
            ]
        )

    # --- I7. Cost segregation study ---
    if profile.get("rental_income") and total_income > 100000 and not profile.get("cost_segregation") and not profile.get("_asked_cost_seg"):
        return (
            "Have you done or considered a cost segregation study? (Accelerates depreciation deductions significantly for properties worth $500K+)",
            [
                {"label": "Yes — already completed", "value": "has_cost_seg"},
                {"label": "Interested in learning more", "value": "cost_seg_interested"},
                {"label": "No", "value": "no_cost_seg"},
                {"label": "Skip", "value": "skip_cost_seg"},
            ]
        )

    # --- I8. Rental property conversion ---
    if profile.get("rental_income") and not profile.get("rental_conversion") and not profile.get("_asked_rental_convert"):
        return (
            "Did you convert a personal residence to rental (or vice versa) this year? (Affects depreciation basis)",
            [
                {"label": "Personal to rental", "value": "converted_to_rental"},
                {"label": "Rental to personal", "value": "converted_to_personal"},
                {"label": "No conversion", "value": "no_rental_conversion"},
                {"label": "Skip", "value": "skip_rental_convert"},
            ]
        )

    # --- I9. $25K rental loss allowance AGI phase-out ---
    if profile.get("rental_income") and float(profile.get("rental_income", 0) or 0) < 0 and not profile.get("rental_loss_allowance") and not profile.get("_asked_rental_loss_allow"):
        return (
            "Is your modified AGI over $100,000? (The $25,000 rental loss allowance phases out between $100K-$150K)",
            [
                {"label": "Under $100K (full $25K allowance)", "value": "rental_loss_full"},
                {"label": "$100K - $150K (partial)", "value": "rental_loss_partial"},
                {"label": "Over $150K (no allowance unless RE professional)", "value": "rental_loss_none"},
                {"label": "Skip", "value": "skip_rental_loss_allow"},
            ]
        )

    # ── BLOCK J: K-1 income (gated — not for low-income W-2) ────────────

    if not _is_low_income_w2:
        if not profile.get("k1_ordinary_income") and not profile.get("_has_k1") and not profile.get("_asked_k1"):
            return (
                "Do you receive any K-1 income from partnerships, S-corporations, or trusts?",
                [
                    {"label": "Yes, I have K-1 income", "value": "has_k1_income"},
                    {"label": "No K-1 income", "value": "no_k1_income"},
                    {"label": "Skip", "value": "skip_k1"},
                ]
            )

        if profile.get("_has_k1") and profile.get("_has_k1") not in ("no_k1_income",) and not profile.get("k1_ordinary_income") and not profile.get("_asked_k1_amount"):
            return (
                "What's your approximate K-1 ordinary income?",
                [
                    {"label": "Under $25,000", "value": "k1_under_25k"},
                    {"label": "$25,000 - $100,000", "value": "k1_25_100k"},
                    {"label": "$100,000 - $250,000", "value": "k1_100_250k"},
                    {"label": "Over $250,000", "value": "k1_over_250k"},
                    {"label": "Skip", "value": "skip_k1_amount"},
                ]
            )

    # ── BLOCK K: Healthcare ──────────────────────────────────────────────

    # K1. ACA Marketplace (non-retired, non-SE who already answered)
    if not is_retired and not profile.get("aca_marketplace") and not profile.get("se_health_insurance") and not profile.get("_asked_aca"):
        return (
            "Do you get health insurance through the ACA Marketplace (Healthcare.gov)? You may qualify for the Premium Tax Credit.",
            [
                {"label": "Yes — with subsidy", "value": "aca_with_subsidy"},
                {"label": "Yes — no subsidy", "value": "aca_no_subsidy"},
                {"label": "No — employer or other coverage", "value": "no_aca"},
                {"label": "Skip", "value": "skip_aca"},
            ]
        )

    # K2. Medicare premiums (retired 65+)
    if is_retired and profile.get("age") in ("age_65_plus",) and not profile.get("medicare_premiums") and not profile.get("_asked_medicare"):
        return (
            "How much do you pay in Medicare premiums? (Part B / Part D — may be deductible or trigger IRMAA surcharge)",
            [
                {"label": "Standard Part B only (~$185/mo)", "value": "medicare_standard"},
                {"label": "Part B + Part D", "value": "medicare_b_and_d"},
                {"label": "IRMAA surcharge (higher premiums)", "value": "medicare_irmaa"},
                {"label": "Skip", "value": "skip_medicare"},
            ]
        )

    # ── BLOCK L: Estimated tax payments ──────────────────────────────────

    if (is_se or total_income > 100000 or is_investor) and not profile.get("_has_estimated_payments") and not profile.get("_asked_estimated"):
        return (
            "Have you made any estimated tax payments this year? (Quarterly payments to the IRS)",
            [
                {"label": "Yes", "value": "has_estimated_payments"},
                {"label": "No", "value": "no_estimated_payments"},
                {"label": "Skip", "value": "skip_estimated"},
            ]
        )

    if profile.get("_has_estimated_payments") == "has_estimated_payments" and not profile.get("estimated_payments") and not profile.get("_asked_est_amount"):
        return (
            "How much total in estimated tax payments this year?",
            [
                {"label": "Under $5,000", "value": "est_under_5k"},
                {"label": "$5,000 - $15,000", "value": "est_5_15k"},
                {"label": "$15,000 - $30,000", "value": "est_15_30k"},
                {"label": "Over $30,000", "value": "est_over_30k"},
                {"label": "Skip", "value": "skip_est_amount"},
            ]
        )

    # ── BLOCK M: Special situations ──────────────────────────────────────

    # M1. Energy credits (popular — solar, EV)
    if not profile.get("energy_credits") and not profile.get("_asked_energy"):
        return (
            "Did you make any energy-efficient home improvements or purchase an electric vehicle?",
            [
                {"label": "Installed solar panels", "value": "has_solar"},
                {"label": "Bought an electric vehicle", "value": "has_ev"},
                {"label": "Home energy improvements (insulation, windows, heat pump)", "value": "has_energy_improvements"},
                {"label": "Multiple", "value": "multiple_energy"},
                {"label": "None", "value": "no_energy"},
                {"label": "Skip", "value": "skip_energy"},
            ]
        )

    # M2. Foreign income (if income > $50k)
    if total_income > 50000 and not profile.get("foreign_income") and not profile.get("_asked_foreign"):
        return (
            "Did you earn any income from outside the United States or pay foreign taxes?",
            [
                {"label": "Yes — worked abroad", "value": "worked_abroad"},
                {"label": "Yes — foreign investment income / taxes paid", "value": "foreign_investments"},
                {"label": "No foreign income", "value": "no_foreign"},
                {"label": "Skip", "value": "skip_foreign"},
            ]
        )

    # M3. Foreign accounts follow-up (FBAR)
    if profile.get("foreign_income") and profile.get("foreign_income") not in ("no_foreign",) and not profile.get("foreign_accounts") and not profile.get("_asked_foreign_accounts"):
        return (
            "Did you have foreign bank or financial accounts with a combined value over $10,000 at any point? (FBAR / FATCA reporting)",
            [
                {"label": "Yes", "value": "has_foreign_accounts"},
                {"label": "No", "value": "no_foreign_accounts"},
                {"label": "Skip", "value": "skip_foreign_accounts"},
            ]
        )

    # M4. AMT check (high income)
    if total_income > 150000 and not profile.get("amt_status") and not profile.get("_asked_amt"):
        return (
            "Do any of these apply? They can trigger the Alternative Minimum Tax (AMT): exercised Incentive Stock Options (ISOs), large state/local tax deductions (>$10K), or private activity bond interest.",
            [
                {"label": "Yes — exercised ISOs", "value": "amt_iso"},
                {"label": "Yes — large SALT deductions", "value": "amt_salt"},
                {"label": "Yes — multiple triggers", "value": "amt_multiple"},
                {"label": "None of these", "value": "no_amt_triggers"},
                {"label": "Skip", "value": "skip_amt"},
            ]
        )

    # M5. Alimony (single/HOH only)
    if filing_status in ("single", "head_of_household") and not profile.get("alimony_status") and not profile.get("_asked_alimony"):
        return (
            "Do you pay or receive alimony under a divorce agreement finalized before 2019? (Post-2018: not deductible/taxable)",
            [
                {"label": "I pay alimony (pre-2019)", "value": "pays_alimony"},
                {"label": "I receive alimony (pre-2019)", "value": "receives_alimony"},
                {"label": "Post-2018 agreement / N/A", "value": "no_alimony"},
                {"label": "Skip", "value": "skip_alimony"},
            ]
        )

    # M6. Gambling
    if not profile.get("gambling_income") and not profile.get("_asked_gambling"):
        return (
            "Did you have any gambling winnings or losses? (Casino, lottery, sports betting — all taxable)",
            [
                {"label": "Yes — net winnings", "value": "gambling_winnings"},
                {"label": "Yes — but net losses", "value": "gambling_losses"},
                {"label": "No gambling", "value": "no_gambling"},
                {"label": "Skip", "value": "skip_gambling"},
            ]
        )

    # M7. Household employee / nanny tax (high income with dependents)
    if total_income > 100000 and dependents > 0 and not profile.get("household_employee") and not profile.get("_asked_household"):
        return (
            "Did you pay a household employee (nanny, housekeeper, caregiver) more than $2,700? You may owe 'nanny tax' (Schedule H).",
            [
                {"label": "Yes", "value": "has_household_employee"},
                {"label": "No", "value": "no_household_employee"},
                {"label": "Skip", "value": "skip_household"},
            ]
        )

    # --- M8. 1099-G (state tax refund taxability) ---
    if not profile.get("state_refund_taxable") and not profile.get("_asked_state_refund"):
        return (
            "Did you receive a state or local tax refund last year? If you itemized last year, it may be taxable this year.",
            [
                {"label": "Yes — I itemized last year", "value": "state_refund_taxable"},
                {"label": "Yes — but I took standard deduction", "value": "state_refund_not_taxable"},
                {"label": "No state refund", "value": "no_state_refund"},
                {"label": "Skip", "value": "skip_state_refund"},
            ]
        )

    # --- M9. Prizes/awards/contest winnings ---
    if not profile.get("prize_income") and not profile.get("_asked_prizes"):
        return (
            "Did you win any prizes, awards, or contest winnings? (TV shows, raffles, employer awards — all taxable)",
            [
                {"label": "Yes", "value": "has_prize_income"},
                {"label": "No", "value": "no_prize_income"},
                {"label": "Skip", "value": "skip_prizes"},
            ]
        )

    # --- M10. Community property state + MFS ---
    _community_prop_states = {"AZ", "CA", "ID", "LA", "NV", "NM", "TX", "WA", "WI"}
    if filing_status == "married_separate" and profile.get("state") in _community_prop_states and not profile.get("community_property") and not profile.get("_asked_community_prop"):
        return (
            "You're filing MFS in a community property state. Community property rules require splitting community income 50/50 with your spouse (Form 8958).",
            [
                {"label": "I understand — I need Form 8958", "value": "community_prop_aware"},
                {"label": "I need more information", "value": "community_prop_help"},
                {"label": "Skip", "value": "skip_community_prop"},
            ]
        )

    # --- M11. Excess Social Security withholding (multiple employers) ---
    if income_type in ("multiple_w2",) and total_income > 176100 and not profile.get("excess_ss") and not profile.get("_asked_excess_ss"):
        return (
            "With multiple employers and combined wages over $176,100, you may have excess Social Security tax withheld. This is refundable!",
            [
                {"label": "Yes — combined wages exceed SS limit", "value": "has_excess_ss"},
                {"label": "No", "value": "no_excess_ss"},
                {"label": "Skip", "value": "skip_excess_ss"},
            ]
        )

    # --- M12. Identity theft / IP PIN ---
    if not profile.get("identity_pin") and not profile.get("_asked_ip_pin"):
        return (
            "Do you have an IRS Identity Protection PIN (IP PIN)? (If you've been a victim of tax-related identity theft or opted into the IP PIN program)",
            [
                {"label": "Yes — I have an IP PIN", "value": "has_ip_pin"},
                {"label": "No", "value": "no_ip_pin"},
                {"label": "Skip", "value": "skip_ip_pin"},
            ]
        )

    # ── BLOCK N: State-specific ──────────────────────────────────────────

    if profile.get("state") not in _NO_INCOME_TAX_STATES:
        if not profile.get("multi_state_income") and not profile.get("_asked_multi_state"):
            return (
                "Did you earn income in a state other than your home state? (Out-of-state employer, business travel, remote work)",
                [
                    {"label": "Yes — income in another state", "value": "multi_state_income"},
                    {"label": "No — all in my home state", "value": "single_state"},
                    {"label": "Skip", "value": "skip_multi_state"},
                ]
            )

    # N2. Local income tax
    if not profile.get("local_income_tax") and not profile.get("_asked_local_tax"):
        return (
            "Do you live or work in a city/county with local income tax? (Common in OH, PA, MD, IN, KY, NYC, Philadelphia)",
            [
                {"label": "Yes", "value": "has_local_tax"},
                {"label": "No", "value": "no_local_tax"},
                {"label": "Not sure", "value": "local_tax_unsure"},
                {"label": "Skip", "value": "skip_local_tax"},
            ]
        )

    # N3. State withholding amount
    if is_w2 and profile.get("state") not in _NO_INCOME_TAX_STATES and not profile.get("state_withholding") and not profile.get("_asked_state_withholding"):
        return (
            "How much state income tax was withheld from your paychecks? (Check W-2 Box 17)",
            [
                {"label": "Under $2,000", "value": "state_wh_under_2k"},
                {"label": "$2,000 - $5,000", "value": "state_wh_2_5k"},
                {"label": "$5,000 - $10,000", "value": "state_wh_5_10k"},
                {"label": "Over $10,000", "value": "state_wh_over_10k"},
                {"label": "Not sure", "value": "state_wh_unsure"},
                {"label": "Skip", "value": "skip_state_withholding"},
            ]
        )

    # --- M13. FEIE (Foreign Earned Income Exclusion) ---
    if profile.get("foreign_income") == "worked_abroad" and not profile.get("feie_status") and not profile.get("_asked_feie"):
        return (
            "Did you live and work outside the US for a full tax year (or 330 days)? You may exclude up to $130,000 of foreign earned income.",
            [
                {"label": "Yes — bona fide residence test", "value": "feie_bona_fide"},
                {"label": "Yes — physical presence test (330 days)", "value": "feie_physical_presence"},
                {"label": "No — short-term assignment", "value": "feie_short_term"},
                {"label": "Skip", "value": "skip_feie"},
            ]
        )

    # --- M14. Foreign Housing Exclusion ---
    if profile.get("feie_status") in ("feie_bona_fide", "feie_physical_presence") and not profile.get("foreign_housing") and not profile.get("_asked_foreign_housing"):
        return (
            "Did your overseas housing costs exceed $19,600? You may qualify for the Foreign Housing Exclusion.",
            [
                {"label": "Yes", "value": "has_foreign_housing"},
                {"label": "No", "value": "no_foreign_housing"},
                {"label": "Skip", "value": "skip_foreign_housing"},
            ]
        )

    # --- M15. FBAR detail ---
    if profile.get("foreign_accounts") and not profile.get("fbar_detail") and not profile.get("_asked_fbar_detail"):
        return (
            "How many foreign accounts do you have, and in which countries? (FBAR due April 15 with auto extension to October 15)",
            [
                {"label": "1-2 accounts", "value": "fbar_1_2"},
                {"label": "3-5 accounts", "value": "fbar_3_5"},
                {"label": "More than 5", "value": "fbar_5plus"},
                {"label": "Skip", "value": "skip_fbar_detail"},
            ]
        )

    # --- M16. FATCA (Form 8938) — separate from FBAR ---
    if profile.get("foreign_accounts") and not profile.get("fatca_status") and not profile.get("_asked_fatca"):
        return (
            "Is the total value of your foreign financial assets over $50,000 at year-end (or $75,000 at any time)? (Form 8938 — separate from FBAR)",
            [
                {"label": "Yes", "value": "fatca_yes"},
                {"label": "No", "value": "fatca_no"},
                {"label": "Not sure", "value": "fatca_unsure"},
                {"label": "Skip", "value": "skip_fatca"},
            ]
        )

    # --- M17. Foreign corporation ownership (Form 5471) ---
    if profile.get("foreign_income") and profile.get("foreign_income") not in ("none", "no_foreign") and not profile.get("foreign_corp") and not profile.get("_asked_foreign_corp"):
        return (
            "Do you own 10% or more of a foreign corporation or partnership? (Reporting required — $10,000+ penalty per form for non-filing)",
            [
                {"label": "Yes — foreign corporation", "value": "has_foreign_corp"},
                {"label": "Yes — foreign partnership", "value": "has_foreign_partnership"},
                {"label": "No", "value": "no_foreign_corp"},
                {"label": "Skip", "value": "skip_foreign_corp"},
            ]
        )

    # --- M18. Foreign trust (Form 3520) ---
    if profile.get("foreign_income") and profile.get("foreign_income") not in ("none", "no_foreign") and not profile.get("foreign_trust") and not profile.get("_asked_foreign_trust"):
        return (
            "Are you a beneficiary of or did you transfer funds to a foreign trust? (35% penalty on distributions for non-reporting)",
            [
                {"label": "Yes", "value": "has_foreign_trust"},
                {"label": "No", "value": "no_foreign_trust"},
                {"label": "Skip", "value": "skip_foreign_trust"},
            ]
        )

    # --- M19. Tax treaty positions (Form 8833) ---
    if profile.get("foreign_income") and profile.get("foreign_income") not in ("none", "no_foreign") and not profile.get("treaty_position") and not profile.get("_asked_treaty"):
        return (
            "Are you claiming any tax treaty benefits? (Common for foreign nationals on visas or US residents with income from treaty countries)",
            [
                {"label": "Yes", "value": "has_treaty"},
                {"label": "No", "value": "no_treaty"},
                {"label": "Skip", "value": "skip_treaty"},
            ]
        )

    # --- M20. PFIC (foreign mutual funds) ---
    if profile.get("foreign_income") in ("foreign_investments",) and not profile.get("pfic_status") and not profile.get("_asked_pfic"):
        return (
            "Do you own shares in foreign mutual funds or ETFs? (Most are PFICs with harsh tax treatment — Form 8621)",
            [
                {"label": "Yes", "value": "has_pfic"},
                {"label": "No", "value": "no_pfic"},
                {"label": "Not sure", "value": "pfic_unsure"},
                {"label": "Skip", "value": "skip_pfic"},
            ]
        )

    # --- M21. NRA spouse election ---
    if filing_status == "married_joint" and profile.get("foreign_income") and not profile.get("nra_spouse_election") and not profile.get("_asked_nra_spouse"):
        pass  # Already asked in Block C

    # --- M22. Solar credit detail ---
    if profile.get("energy_credits") in ("has_solar", "multiple_energy") and not profile.get("solar_cost") and not profile.get("_asked_solar_cost"):
        return (
            "What was the total cost of your solar installation? (30% credit applies)",
            [
                {"label": "Under $15,000", "value": "solar_under_15k"},
                {"label": "$15,000 - $30,000", "value": "solar_15_30k"},
                {"label": "$30,000 - $50,000", "value": "solar_30_50k"},
                {"label": "Over $50,000", "value": "solar_over_50k"},
                {"label": "Skip", "value": "skip_solar_cost"},
            ]
        )

    # --- M23. EV credit detail ---
    if profile.get("energy_credits") in ("has_ev", "multiple_energy") and not profile.get("ev_detail") and not profile.get("_asked_ev_detail"):
        return (
            "Was your EV new or used? (New: up to $7,500 credit, MSRP limits apply. Used: up to $4,000, price under $25K)",
            [
                {"label": "New EV — under MSRP limit", "value": "ev_new_qualified"},
                {"label": "New EV — over MSRP limit", "value": "ev_new_over_msrp"},
                {"label": "Used EV — under $25K", "value": "ev_used_qualified"},
                {"label": "Skip", "value": "skip_ev_detail"},
            ]
        )

    # --- M24. Energy improvement detail ---
    if profile.get("energy_credits") in ("has_energy_improvements", "multiple_energy") and not profile.get("energy_improvement_detail") and not profile.get("_asked_energy_detail"):
        return (
            "What energy improvements did you make? (Annual limit $3,200: $1,200 general + $2,000 heat pump)",
            [
                {"label": "Heat pump / heat pump water heater ($2,000 max)", "value": "energy_heat_pump"},
                {"label": "Insulation / windows / doors ($1,200 max)", "value": "energy_insulation"},
                {"label": "Electrical panel upgrade ($600 max)", "value": "energy_panel"},
                {"label": "Multiple improvements", "value": "energy_multiple_detail"},
                {"label": "Skip", "value": "skip_energy_detail"},
            ]
        )

    # --- M25. WOTC (Work Opportunity Tax Credit) ---
    if profile.get("has_employees_status") in ("employees", "both") and not profile.get("wotc") and not profile.get("_asked_wotc"):
        return (
            "Did you hire employees from targeted groups? (Veterans, ex-felons, long-term unemployed, SNAP recipients — Work Opportunity Tax Credit)",
            [
                {"label": "Yes", "value": "has_wotc"},
                {"label": "No", "value": "no_wotc"},
                {"label": "Skip", "value": "skip_wotc"},
            ]
        )

    # --- M26. Bankruptcy ---
    if not profile.get("bankruptcy_status") and not profile.get("_asked_bankruptcy"):
        return (
            "Did you file for bankruptcy during the tax year?",
            [
                {"label": "Chapter 7", "value": "bankruptcy_ch7"},
                {"label": "Chapter 13", "value": "bankruptcy_ch13"},
                {"label": "No bankruptcy", "value": "no_bankruptcy"},
                {"label": "Skip", "value": "skip_bankruptcy"},
            ]
        )

    # --- M27. Underpayment penalty exposure ---
    if not profile.get("underpayment_exposure") and not profile.get("_asked_underpayment"):
        return (
            "Did you owe more than $1,000 on last year's return? If so, did you adjust withholding or make estimated payments to avoid an underpayment penalty?",
            [
                {"label": "May be exposed to penalty", "value": "underpayment_exposed"},
                {"label": "I've adjusted", "value": "underpayment_adjusted"},
                {"label": "Not applicable", "value": "underpayment_na"},
                {"label": "Skip", "value": "skip_underpayment"},
            ]
        )

    # --- M27b. Unreported tip income (service workers only — low income W-2) ---
    if is_w2 and total_income < 60000 and not profile.get("unreported_tips") and not profile.get("_asked_tips"):
        return (
            "Did you receive tips that were NOT reported to your employer? (Cash tips — common in restaurant, hotel, salon jobs)",
            [
                {"label": "Yes — I have unreported tips", "value": "has_unreported_tips"},
                {"label": "No / Not a tipped employee", "value": "not_tipped"},
                {"label": "Skip", "value": "skip_tips"},
            ]
        )

    # --- M28. Amended return needed ---
    if not profile.get("amended_return") and not profile.get("_asked_amended"):
        return (
            "Do you need to amend a prior year return? (Received corrected W-2/1099, forgot income/deduction, filing status change)",
            [
                {"label": "Yes", "value": "has_amended"},
                {"label": "No", "value": "no_amended"},
                {"label": "Skip", "value": "skip_amended"},
            ]
        )

    # --- M29. State-specific credits ---
    if not profile.get("state_credits") and not profile.get("_asked_state_credits"):
        return (
            "Does your state offer credits you may qualify for? (Property tax relief, renter's credit, historic preservation, angel investor, etc.)",
            [
                {"label": "I may have state credits", "value": "has_state_credits"},
                {"label": "Not sure", "value": "state_credits_unsure"},
                {"label": "No", "value": "no_state_credits"},
                {"label": "Skip", "value": "skip_state_credits"},
            ]
        )

    # ── BLOCK O: Filing logistics ────────────────────────────────────────

    # O1. Prior year return status
    if not profile.get("prior_year_return") and not profile.get("_asked_prior_year"):
        return (
            "Did you file a tax return last year? If so, did you get a refund or owe money?",
            [
                {"label": "Filed — got a refund", "value": "prior_refund"},
                {"label": "Filed — owed money", "value": "prior_owed"},
                {"label": "Filed — broke even", "value": "prior_even"},
                {"label": "Didn't file last year", "value": "prior_not_filed"},
                {"label": "Skip", "value": "skip_prior_year"},
            ]
        )

    # O2. Extension filed
    if not profile.get("extension_filed") and not profile.get("_asked_extension"):
        return (
            "Have you already filed an extension for this tax year? (Form 4868)",
            [
                {"label": "Yes", "value": "has_extension"},
                {"label": "No", "value": "no_extension"},
                {"label": "Skip", "value": "skip_extension"},
            ]
        )

    # O3. Refund preference
    if not profile.get("refund_preference") and not profile.get("_asked_refund_pref"):
        return (
            "If you're due a refund, how would you like to receive it?",
            [
                {"label": "Direct deposit", "value": "refund_direct_deposit"},
                {"label": "Paper check", "value": "refund_check"},
                {"label": "Apply to next year's estimated tax", "value": "refund_apply_next"},
                {"label": "Split between accounts", "value": "refund_split"},
                {"label": "Skip", "value": "skip_refund_pref"},
            ]
        )

    # =========================================================================
    # PHASE 3: All questions answered or skipped — ready for analysis
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
        # Ensure profile exists (sessions_api creates sessions without it)
        if "profile" not in session:
            session["profile"] = {}
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
        logger.error(f"Session initialization error: {type(e).__name__}: {e}", exc_info=True)
        # Silently recover — create a fresh session instead of showing an error
        session = {"profile": {}, "conversation": [], "state": "greeting", "id": session_id}
        chat_engine.sessions[session_id] = session
        profile = session["profile"]

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
                response="I can only help with tax-related questions. Could you please rephrase your question about your tax situation?",
                response_type="redirect",
                quick_actions=[
                    {"label": "What deductions can I claim?", "value": "ask_deductions"},
                    {"label": "Help me file my taxes", "value": "start_filing"},
                ],
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

    # Handle "start" / "continue" — frontend sends this to get the next question from backend
    if msg_lower in ("start", "continue", "start_estimate", "no_manual", "continue_assessment"):
        next_q, next_actions = _get_dynamic_next_question(profile, session=session)
        if next_q:
            return ChatResponse(
                session_id=request.session_id,
                response=next_q,
                response_type="question",
                profile_completeness=chat_engine.calculate_profile_completeness(profile),
                quick_actions=next_actions or [],
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
        # Return the first Phase 1 question directly
        next_q, next_actions = _get_dynamic_next_question(profile, session=session)
        if next_q:
            return ChatResponse(
                session_id=request.session_id,
                response="Hello! I'm your AI tax advisor. Let's get started.\n\n" + next_q,
                response_type="question",
                disclaimer=STANDARD_DISCLAIMER,
                profile_completeness=0.0,
                quick_actions=next_actions or [],
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

    # ── EMOTIONAL INTELLIGENCE (Feature 7) — confusion/explanation detection ──
    _confusion_patterns = [
        r'(what does that mean)', r'(i don\'t understand)', r'(this is (too |so )?complicated)',
        r'(can you explain)', r'(what is .{2,30}\?)', r'(help me understand)',
        r'(i\'m (not sure|confused) (what|about))', r'(too many questions)',
        r'(just (do|calculate|figure) it)',
    ]
    _is_confused = any(re.search(p, msg_lower) for p in _confusion_patterns) and not is_frustrated
    if _is_confused:
        _explanation = _get_simple_explanation(msg_lower, profile)
        return ChatResponse(
            session_id=request.session_id,
            response=f"No worries — let me explain.\n\n{_explanation}\n\nShall we continue?",
            response_type="help",
            conversation_mode=profile.get("_conversation_mode", "guided"),
            profile_completeness=chat_engine.calculate_profile_completeness(profile),
            quick_actions=[
                {"label": "Yes, continue", "value": "continue_normal"},
                {"label": "Use simpler questions", "value": "simplify_mode"},
                {"label": "Skip ahead to calculation", "value": "skip_deep_dive"},
            ],
            metadata={"_source": "emotional_intelligence"},
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

            if get_ai_metrics_service:
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
        "no_k1_income": {"_asked_k1": True, "_has_k1": "no_k1_income", "k1_ordinary_income": 0,
            "_asked_k1_amount": True},
        "skip_k1": {"_asked_k1": True},
        # Investment income
        "has_investments": {"_has_investments": True},
        "no_investments": {"_asked_investments": True, "investment_income": 0,
            "_asked_invest_amount": True, "_asked_cap_gains": True, "_asked_crypto": True,
            "_asked_stock_comp": True, "_asked_wash_sale": True, "_asked_niit": True,
            "_asked_installment": True, "_asked_1031": True, "_asked_qsbs": True,
            "_asked_qoz": True, "_asked_collectibles": True, "_asked_inv_interest": True,
            "_asked_passive_carryforward": True, "_asked_section_1256": True,
            "_asked_mlp": True, "_asked_espp_disp": True, "_asked_iso_amt": True, "_asked_oid": True},
        "skip_investments": {"_asked_investments": True},
        # Rental income
        "has_rental": {"_has_rental": True},
        "no_rental": {"_asked_rental": True, "_has_rental": "no_rental", "rental_income": 0,
            "_asked_rental_amount": True, "_asked_participation": True,
            "_asked_short_term": True, "_asked_personal_use": True, "_asked_below_fmv": True,
            "_asked_cost_seg": True, "_asked_rental_convert": True, "_asked_rental_loss_allow": True},
        "skip_rental": {"_asked_rental": True},
        # Retirement
        "has_401k": {"_has_401k": True, "retirement_401k": 23500},  # 2025 employee limit
        "has_ira": {"_has_ira": True, "retirement_ira": 7000},
        "has_both_retirement": {"retirement_401k": 23500, "retirement_ira": 7000},
        "no_retirement": {"_asked_retirement": True, "retirement_401k": 0, "retirement_ira": 0,
            "_asked_backdoor_roth": True, "_asked_ira_basis": True, "_asked_catch_up": True,
            "_asked_mega_backdoor": True, "_asked_ira_deduct": True, "_asked_savers_credit": True},
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
        # ─── Hybrid flow: mode selection ─────────────────────────────────
        "mode_freeform": {"_conversation_mode": "freeform"},
        "mode_guided": {"_conversation_mode": "guided"},
        "confirm_summary": {"_freeform_confirmed": True, "_conversation_mode": "followup"},
        "fix_summary": {"_conversation_mode": "freeform", "_freeform_submitted": False},
        "confirm_and_calculate": {"_confirmed_profile": True},
        "edit_profile": {"_confirmed_profile": False},
        # ─── Smart defaults (Feature 2) ──────────────────────────────────
        "withholding_smart_default": {"_smart_default_accepted": True, "_asked_withholding": True},
        "withholding_manual_entry": {"_smart_default_rejected": True},
        "state_wh_smart_default": {"_smart_default_accepted": True, "_asked_state_withholding": True},
        "state_wh_manual": {"_smart_default_rejected": True},
        # ─── Document upload (Feature 5) ─────────────────────────────────
        "upload_w2": {"_doc_upload_requested": "w2", "_doc_offer_shown": True},
        "upload_1099": {"_doc_upload_requested": "1099", "_doc_offer_shown": True},
        "skip_upload": {"_doc_offer_shown": True},
        # ─── Emotional intelligence (Feature 7) ─────────────────────────
        "continue_normal": {"_complexity_level": "normal"},
        "simplify_mode": {"_complexity_level": "simple"},
        # Phase 1: Dependents quick actions
        "0_dependents": {"dependents": 0,
            "_asked_dependents_age": True, "_asked_childcare": True, "_asked_dcfsa": True,
            "_asked_529": True, "_asked_custody": True, "_asked_qualifying_relative": True,
            "_asked_disabled_dep": True, "_asked_dep_ssn": True, "_asked_multiple_support": True,
            "_asked_student_dep": True, "_asked_employer_dc": True, "_asked_household": True},
        "1_dependent": {"dependents": 1},
        "2_dependents": {"dependents": 2},
        "3plus_dependents": {"dependents": 3},
        # Phase 1: Income type quick actions (8 options)
        "w2_employee": {"income_type": "w2_employee", "is_self_employed": False},
        "multiple_w2": {"income_type": "multiple_w2", "is_self_employed": False},
        "w2_plus_side": {"income_type": "w2_plus_side", "is_self_employed": True},
        "self_employed": {"income_type": "self_employed", "is_self_employed": True},
        "business_owner": {"income_type": "business_owner", "is_self_employed": True},
        "retired": {"income_type": "retired", "is_self_employed": False},
        "investor": {"income_type": "investor", "is_self_employed": False},
        "military": {"income_type": "military", "is_self_employed": False},
        # Federal withholding
        "withholding_under_5k": {"federal_withholding": 3500, "_asked_withholding": True},
        "withholding_5_10k": {"federal_withholding": 7500, "_asked_withholding": True},
        "withholding_10_20k": {"federal_withholding": 15000, "_asked_withholding": True},
        "withholding_20_40k": {"federal_withholding": 30000, "_asked_withholding": True},
        "withholding_over_40k": {"federal_withholding": 50000, "_asked_withholding": True},
        "withholding_estimate": {"_withholding_auto_estimate": True, "_asked_withholding": True},
        # Dependent age split
        "all_under_17": {"dependents_under_17": -1, "_asked_dependents_age": True},  # -1 = use full dependents count
        "none_under_17": {"dependents_under_17": 0, "_asked_dependents_age": True},
        "1_under_17": {"dependents_under_17": 1, "_asked_dependents_age": True},
        "2_under_17": {"dependents_under_17": 2, "_asked_dependents_age": True},
        "skip_dependents_age": {"_asked_dependents_age": True},
        # Investment income amounts (follow-up after has_investments)
        "invest_under_5k": {"investment_income": 3000, "_asked_invest_amount": True},
        "invest_5_25k": {"investment_income": 15000, "_asked_invest_amount": True},
        "invest_25_100k": {"investment_income": 60000, "_asked_invest_amount": True},
        "invest_over_100k": {"investment_income": 150000, "_asked_invest_amount": True},
        "skip_invest_amount": {"_asked_invest_amount": True},
        # Capital gains follow-up
        "no_cap_gains": {"capital_gains_long": 0, "_asked_cap_gains": True},
        "capgains_under_10k": {"capital_gains_long": 5000, "_asked_cap_gains": True},
        "capgains_10_50k": {"capital_gains_long": 30000, "_asked_cap_gains": True},
        "capgains_over_50k": {"capital_gains_long": 75000, "_asked_cap_gains": True},
        "skip_cap_gains": {"_asked_cap_gains": True},
        # Rental income amounts
        "rental_under_10k": {"rental_income": 5000, "_asked_rental_amount": True},
        "rental_10_25k": {"rental_income": 17500, "_asked_rental_amount": True},
        "rental_25_50k": {"rental_income": 37500, "_asked_rental_amount": True},
        "rental_over_50k": {"rental_income": 75000, "_asked_rental_amount": True},
        "rental_net_loss": {"rental_income": -5000, "_asked_rental_amount": True},
        "skip_rental_amount": {"_asked_rental_amount": True},
        # K-1 income amounts
        "k1_under_25k": {"k1_ordinary_income": 15000, "_asked_k1_amount": True},
        "k1_25_100k": {"k1_ordinary_income": 60000, "_asked_k1_amount": True},
        "k1_100_250k": {"k1_ordinary_income": 175000, "_asked_k1_amount": True},
        "k1_over_250k": {"k1_ordinary_income": 375000, "_asked_k1_amount": True},
        "skip_k1_amount": {"_asked_k1_amount": True},
        # Estimated payments amounts
        "est_under_5k": {"estimated_payments": 3000, "_asked_est_amount": True},
        "est_5_15k": {"estimated_payments": 10000, "_asked_est_amount": True},
        "est_15_30k": {"estimated_payments": 22000, "_asked_est_amount": True},
        "est_over_30k": {"estimated_payments": 40000, "_asked_est_amount": True},
        "skip_est_amount": {"_asked_est_amount": True},
        # Property taxes
        "has_property_taxes": {"_has_property_taxes": True, "_asked_deductions": True},
        "prop_tax_under_5k": {"property_taxes": 3000, "_asked_prop_tax_amount": True},
        "prop_tax_5_10k": {"property_taxes": 7500, "_asked_prop_tax_amount": True},
        "prop_tax_over_10k": {"property_taxes": 10000, "_asked_prop_tax_amount": True},
        "skip_prop_tax_amount": {"_asked_prop_tax_amount": True},
        # ─── NEW: Phase 1 expanded dependents ────────────────────────────
        "3_dependents": {"dependents": 3},
        "4plus_dependents": {"dependents": 4},
        # ─── NEW: Phase 1 expanded income ranges ─────────────────────────
        "income_under_25k": {"total_income": 15000},
        "income_25_50k": {"total_income": 37500},
        "income_200_500k": {"total_income": 350000},
        "income_over_500k": {"total_income": 750000},
        # ─── NEW: Multiple W-2 jobs ──────────────────────────────────────
        "2_jobs": {"w2_job_count": 2, "_asked_w2_count": True},
        "3plus_jobs": {"w2_job_count": 3, "_asked_w2_count": True},
        # ─── NEW: Side hustle type & income ──────────────────────────────
        "freelance": {"side_hustle_type": "freelance", "_asked_side_type": True},
        "gig_work": {"side_hustle_type": "gig_work", "_asked_side_type": True},
        "online_sales": {"side_hustle_type": "online_sales", "_asked_side_type": True},
        "side_rental": {"side_hustle_type": "side_rental", "_asked_side_type": True},
        "multiple_side": {"side_hustle_type": "multiple_side", "_asked_side_type": True},
        "side_under_5k": {"side_income": 3000, "_asked_side_income": True},
        "side_5_20k": {"side_income": 12000, "_asked_side_income": True},
        "side_20_50k": {"side_income": 35000, "_asked_side_income": True},
        "side_over_50k": {"side_income": 75000, "_asked_side_income": True},
        "skip_side_income": {"_asked_side_income": True},
        # ─── NEW: Military ───────────────────────────────────────────────
        "combat_zone": {"combat_zone": "combat_zone", "_asked_military_combat": True},
        "no_combat": {"combat_zone": "no_combat", "_asked_military_combat": True},
        "skip_military_combat": {"_asked_military_combat": True},
        "pcs_move": {"pcs_move": "pcs_move", "_asked_pcs": True},
        "no_pcs": {"pcs_move": "no_pcs", "_asked_pcs": True},
        "skip_pcs": {"_asked_pcs": True},
        # ─── NEW: Entity type ────────────────────────────────────────────
        "sole_prop": {"entity_type": "sole_prop", "_asked_entity_type": True},
        "single_llc": {"entity_type": "single_llc", "_asked_entity_type": True},
        "multi_llc": {"entity_type": "multi_llc", "_asked_entity_type": True},
        "s_corp": {"entity_type": "s_corp", "_asked_entity_type": True},
        "c_corp": {"entity_type": "c_corp", "_asked_entity_type": True},
        "partnership": {"entity_type": "partnership", "_asked_entity_type": True},
        "entity_unsure": {"entity_type": "entity_unsure", "_asked_entity_type": True},
        # ─── NEW: Business income expanded ranges ────────────────────────
        "biz_under_25k": {"business_income": 15000},
        "biz_25_50k": {"business_income": 37500},
        "biz_net_loss": {"business_income": -5000, "_asked_business": True},
        # ─── NEW: S-Corp reasonable salary ───────────────────────────────
        "salary_under_50k": {"reasonable_salary": 35000, "_asked_salary": True},
        "salary_50_100k": {"reasonable_salary": 75000, "_asked_salary": True},
        "salary_100_150k": {"reasonable_salary": 125000, "_asked_salary": True},
        "salary_over_150k": {"reasonable_salary": 175000, "_asked_salary": True},
        "skip_salary": {"_asked_salary": True},
        # ─── NEW: Vehicle / mileage ──────────────────────────────────────
        "has_biz_vehicle": {"business_miles": 10000, "_asked_vehicle": True},
        "no_biz_vehicle": {"business_miles": 0, "_asked_vehicle": True},
        "skip_vehicle": {"_asked_vehicle": True},
        # ─── NEW: Equipment / Section 179 ────────────────────────────────
        "has_equipment": {"equipment_cost": 10000, "_asked_equipment": True},
        "no_equipment": {"equipment_cost": 0, "_asked_equipment": True},
        "skip_equipment": {"_asked_equipment": True},
        # ─── NEW: Employees / contractors ────────────────────────────────
        "has_employees": {"has_employees_status": "employees", "_asked_employees": True},
        "has_contractors": {"has_employees_status": "contractors", "_asked_employees": True},
        "has_both_workers": {"has_employees_status": "both", "_asked_employees": True},
        "solo_operation": {"has_employees_status": "solo", "_asked_employees": True},
        "skip_employees": {"_asked_employees": True},
        # ─── NEW: SE health insurance ────────────────────────────────────
        "has_se_health": {"se_health_insurance": "has_se_health", "_asked_se_health": True},
        "spouse_coverage": {"se_health_insurance": "spouse_coverage", "_asked_se_health": True},
        "aca_plan": {"se_health_insurance": "aca_plan", "_asked_se_health": True},
        "no_health_insurance": {"se_health_insurance": "none", "_asked_se_health": True},
        "skip_se_health": {"_asked_se_health": True},
        # ─── NEW: QBI / SSTB ────────────────────────────────────────────
        "is_sstb": {"is_sstb": True, "_asked_sstb": True},
        "not_sstb": {"is_sstb": False, "_asked_sstb": True},
        "sstb_unsure": {"is_sstb": "unsure", "_asked_sstb": True},
        "skip_sstb": {"_asked_sstb": True},
        # ─── NEW: Social Security benefits (retired) ─────────────────────
        "ss_under_15k": {"ss_benefits": 10000, "_asked_ss": True},
        "ss_15_30k": {"ss_benefits": 22000, "_asked_ss": True},
        "ss_over_30k": {"ss_benefits": 36000, "_asked_ss": True},
        "no_ss": {"ss_benefits": 0, "_asked_ss": True},
        "skip_ss": {"_asked_ss": True},
        # ─── NEW: Pension ────────────────────────────────────────────────
        "pension_taxable": {"pension_income": "taxable", "_asked_pension": True},
        "pension_partial": {"pension_income": "partial", "_asked_pension": True},
        "no_pension": {"pension_income": 0, "_asked_pension": True},
        "skip_pension": {"_asked_pension": True},
        # ─── NEW: RMD ───────────────────────────────────────────────────
        "rmd_taken": {"rmd_status": "taken", "_asked_rmd": True},
        "rmd_pending": {"rmd_status": "pending", "_asked_rmd": True},
        "under_73": {"rmd_status": "under_73", "_asked_rmd": True},
        "skip_rmd": {"_asked_rmd": True},
        # ─── NEW: Age expanded ───────────────────────────────────────────
        "age_under_26": {"age": 23},
        "age_26_49": {"age": 37},
        # ─── NEW: Spouse income (MFJ) ────────────────────────────────────
        "spouse_w2": {"spouse_income_type": "spouse_w2", "_asked_spouse_income_type": True},
        "spouse_se": {"spouse_income_type": "spouse_se", "_asked_spouse_income_type": True},
        "spouse_none": {"spouse_income_type": "spouse_none", "_asked_spouse_income_type": True},
        "spouse_retired": {"spouse_income_type": "spouse_retired", "_asked_spouse_income_type": True},
        "skip_spouse_income": {"_asked_spouse_income_type": True},
        "spouse_under_25k": {"spouse_income": 15000, "_asked_spouse_income": True},
        "spouse_25_50k": {"spouse_income": 37500, "_asked_spouse_income": True},
        "spouse_50_100k": {"spouse_income": 75000, "_asked_spouse_income": True},
        "spouse_over_100k": {"spouse_income": 150000, "_asked_spouse_income": True},
        "skip_spouse_amount": {"_asked_spouse_income": True},
        # ─── NEW: Childcare ──────────────────────────────────────────────
        "childcare_under_3k": {"childcare_costs": 2000, "_asked_childcare": True},
        "childcare_3_6k": {"childcare_costs": 4500, "_asked_childcare": True},
        "childcare_over_6k": {"childcare_costs": 8000, "_asked_childcare": True},
        "no_childcare": {"childcare_costs": 0, "_asked_childcare": True},
        "skip_childcare": {"_asked_childcare": True},
        # ─── NEW: Dependent care FSA ─────────────────────────────────────
        "has_dcfsa": {"dependent_care_fsa": 5000, "_asked_dcfsa": True},
        "no_dcfsa": {"dependent_care_fsa": 0, "_asked_dcfsa": True},
        "skip_dcfsa": {"_asked_dcfsa": True},
        # ─── NEW: Education ──────────────────────────────────────────────
        "self_student": {"education_status": "self_student", "_asked_education": True},
        "dependent_student": {"education_status": "dependent_student", "_asked_education": True},
        "both_students": {"education_status": "both_students", "_asked_education": True},
        "no_education": {"education_status": "no_education", "_asked_education": True},
        "skip_education": {"_asked_education": True},
        # ─── NEW: 529 plan ───────────────────────────────────────────────
        "has_529": {"has_529": True, "_asked_529": True},
        "no_529": {"has_529": False, "_asked_529": True},
        "skip_529": {"_asked_529": True},
        # ─── NEW: Custody ────────────────────────────────────────────────
        "custody_self": {"custody_status": "self", "_asked_custody": True},
        "custody_ex": {"custody_status": "ex", "_asked_custody": True},
        "custody_split": {"custody_status": "split", "_asked_custody": True},
        "custody_na": {"custody_status": "na", "_asked_custody": True},
        "skip_custody": {"_asked_custody": True},
        # ─── NEW: Life events ────────────────────────────────────────────
        "event_married": {"life_events": "event_married", "_asked_life_events": True},
        "event_divorced": {"life_events": "event_divorced", "_asked_life_events": True},
        "event_baby": {"life_events": "event_baby", "_asked_life_events": True},
        "event_bought_home": {"life_events": "event_bought_home", "_asked_life_events": True, "_has_mortgage": True},
        "event_sold_home": {"life_events": "event_sold_home", "_asked_life_events": True},
        "event_job_change": {"life_events": "event_job_change", "_asked_life_events": True},
        "event_job_loss": {"life_events": "event_job_loss", "_asked_life_events": True},
        "event_started_biz": {"life_events": "event_started_biz", "_asked_life_events": True},
        "event_moved_states": {"life_events": "event_moved_states", "_asked_life_events": True},
        "event_retired": {"life_events": "event_retired", "_asked_life_events": True},
        "event_inheritance": {"life_events": "event_inheritance", "_asked_life_events": True},
        "no_life_events": {"life_events": "no_life_events", "_asked_life_events": True,
            "_asked_home_sale": True, "_asked_home_gain": True, "_asked_partial_exclusion": True,
            "_asked_state_move": True, "_asked_job_loss": True, "_asked_startup": True,
            "_asked_mfj_mfs": True, "_asked_divorce_year": True, "_asked_qdro": True,
            "_asked_inheritance_type": True, "_asked_job_401k": True, "_asked_spouse_death": True,
            "_asked_mortgage_points": True, "_asked_first_home_ira": True},
        "skip_life_events": {"_asked_life_events": True},
        # Life event follow-ups
        "home_sale_excluded": {"home_sale_exclusion": "excluded", "_asked_home_sale": True},
        "home_sale_taxable": {"home_sale_exclusion": "taxable", "_asked_home_sale": True},
        "skip_home_sale": {"_asked_home_sale": True},
        "moved_h1": {"move_date": "h1", "_asked_state_move": True},
        "moved_h2": {"move_date": "h2", "_asked_state_move": True},
        "skip_state_move": {"_asked_state_move": True},
        "had_unemployment": {"unemployment_income": "unemployment", "_asked_job_loss": True},
        "had_severance": {"unemployment_income": "severance", "_asked_job_loss": True},
        "had_both_unemployment_severance": {"unemployment_income": "both", "_asked_job_loss": True},
        "no_unemployment": {"unemployment_income": "none", "_asked_job_loss": True},
        "skip_job_loss": {"_asked_job_loss": True},
        "startup_under_5k": {"startup_costs": 3000, "_asked_startup": True},
        "startup_5_50k": {"startup_costs": 25000, "_asked_startup": True},
        "startup_over_50k": {"startup_costs": 75000, "_asked_startup": True},
        "no_startup_costs": {"startup_costs": 0, "_asked_startup": True},
        "skip_startup": {"_asked_startup": True},
        # ─── NEW: Capital gains expanded ─────────────────────────────────
        "lt_gains": {"capital_gains_type": "lt_gains", "_asked_cap_gains": True},
        "st_gains": {"capital_gains_type": "st_gains", "_asked_cap_gains": True},
        "mixed_gains": {"capital_gains_type": "mixed_gains", "_asked_cap_gains": True},
        "had_losses": {"capital_gains_type": "had_losses", "_asked_cap_gains": True},
        "no_sales": {"capital_gains_type": "no_sales", "_asked_cap_gains": True},
        # ─── NEW: Crypto ─────────────────────────────────────────────────
        "crypto_trading": {"crypto_activity": "trading", "_asked_crypto": True},
        "crypto_mining": {"crypto_activity": "mining", "_asked_crypto": True},
        "crypto_multiple": {"crypto_activity": "multiple", "_asked_crypto": True},
        "no_crypto": {"crypto_activity": "none", "_asked_crypto": True},
        "skip_crypto": {"_asked_crypto": True},
        # ─── NEW: Stock options / RSU / ESPP ─────────────────────────────
        "has_iso": {"stock_compensation": "iso", "_asked_stock_comp": True},
        "has_nso": {"stock_compensation": "nso", "_asked_stock_comp": True},
        "has_rsu": {"stock_compensation": "rsu", "_asked_stock_comp": True},
        "has_espp": {"stock_compensation": "espp", "_asked_stock_comp": True},
        "multiple_stock_comp": {"stock_compensation": "multiple", "_asked_stock_comp": True},
        "no_stock_comp": {"stock_compensation": "none", "_asked_stock_comp": True},
        "skip_stock_comp": {"_asked_stock_comp": True},
        # ─── NEW: Retirement expanded ────────────────────────────────────
        "has_trad_ira": {"retirement_ira": 7000, "_asked_retirement": True},
        "has_roth_ira": {"retirement_ira": 7000, "_has_roth_ira": True, "_asked_retirement": True},
        "has_sep": {"retirement_401k": 70000, "_asked_retirement": True},  # 2025 SEP limit
        "has_solo_401k": {"retirement_401k": 70000, "_asked_retirement": True},
        # ─── NEW: HSA expanded ───────────────────────────────────────────
        "has_hdhp_no_hsa": {"hsa_contributions": 0, "_has_hdhp": True, "_asked_hsa": True},
        # ─── NEW: Distributions ──────────────────────────────────────────
        "ira_distribution": {"retirement_distributions": "ira_distribution", "_asked_distributions": True},
        "401k_distribution": {"retirement_distributions": "401k_distribution", "_asked_distributions": True},
        "roth_conversion": {"retirement_distributions": "roth_conversion", "_asked_distributions": True},
        "no_distributions": {"retirement_distributions": "none", "_asked_distributions": True},
        "skip_distributions": {"_asked_distributions": True},
        # ─── NEW: Early withdrawal ───────────────────────────────────────
        "early_no_exception": {"early_withdrawal_status": "penalty", "_asked_early_withdrawal": True},
        "early_with_exception": {"early_withdrawal_status": "exception", "_asked_early_withdrawal": True},
        "over_59_half": {"early_withdrawal_status": "no_penalty", "_asked_early_withdrawal": True},
        "skip_early": {"_asked_early_withdrawal": True},
        # ─── NEW: Medical expenses ───────────────────────────────────────
        "medical_under_5k": {"medical_expenses": 3000, "_asked_medical_amount": True},
        "medical_5_15k": {"medical_expenses": 10000, "_asked_medical_amount": True},
        "medical_15_30k": {"medical_expenses": 22000, "_asked_medical_amount": True},
        "medical_over_30k": {"medical_expenses": 35000, "_asked_medical_amount": True},
        "skip_medical_amount": {"_asked_medical_amount": True},
        # ─── NEW: SALT ───────────────────────────────────────────────────
        "has_salt": {"_has_salt": True, "_asked_deductions": True},
        # ─── NEW: Educator ───────────────────────────────────────────────
        "is_educator": {"educator_expenses": 300, "_asked_educator": True},
        "not_educator": {"educator_expenses": 0, "_asked_educator": True},
        # ─── NEW: Rental expanded ────────────────────────────────────────
        "rental_1": {"_has_rental": "rental_1", "_asked_rental": True},
        "rental_2_4": {"_has_rental": "rental_2_4", "_asked_rental": True},
        "rental_5plus": {"_has_rental": "rental_5plus", "_asked_rental": True},
        "active_participation": {"rental_participation": "active", "_asked_participation": True},
        "passive_participation": {"rental_participation": "passive", "_asked_participation": True},
        "re_professional": {"rental_participation": "re_professional", "_asked_participation": True},
        "skip_participation": {"_asked_participation": True},
        # ─── NEW: ACA Marketplace ────────────────────────────────────────
        "aca_with_subsidy": {"aca_marketplace": "with_subsidy", "_asked_aca": True},
        "aca_no_subsidy": {"aca_marketplace": "no_subsidy", "_asked_aca": True},
        "no_aca": {"aca_marketplace": "none", "_asked_aca": True},
        "skip_aca": {"_asked_aca": True},
        # ─── NEW: Medicare ───────────────────────────────────────────────
        "medicare_standard": {"medicare_premiums": "standard", "_asked_medicare": True},
        "medicare_b_and_d": {"medicare_premiums": "b_and_d", "_asked_medicare": True},
        "medicare_irmaa": {"medicare_premiums": "irmaa", "_asked_medicare": True},
        "skip_medicare": {"_asked_medicare": True},
        # ─── NEW: Energy credits ─────────────────────────────────────────
        "has_solar": {"energy_credits": "solar", "_asked_energy": True},
        "has_ev": {"energy_credits": "ev", "_asked_energy": True},
        "has_energy_improvements": {"energy_credits": "improvements", "_asked_energy": True},
        "multiple_energy": {"energy_credits": "multiple", "_asked_energy": True},
        "no_energy": {"energy_credits": "none", "_asked_energy": True},
        "skip_energy": {"_asked_energy": True},
        # ─── NEW: Foreign income ─────────────────────────────────────────
        "worked_abroad": {"foreign_income": "worked_abroad", "_asked_foreign": True},
        "foreign_investments": {"foreign_income": "foreign_investments", "_asked_foreign": True},
        "no_foreign": {"foreign_income": "none", "_asked_foreign": True},
        "skip_foreign": {"_asked_foreign": True},
        "has_foreign_accounts": {"foreign_accounts": True, "_asked_foreign_accounts": True},
        "no_foreign_accounts": {"foreign_accounts": False, "_asked_foreign_accounts": True},
        "skip_foreign_accounts": {"_asked_foreign_accounts": True},
        # ─── NEW: AMT ────────────────────────────────────────────────────
        "amt_iso": {"amt_status": "iso", "_asked_amt": True},
        "amt_salt": {"amt_status": "salt", "_asked_amt": True},
        "amt_multiple": {"amt_status": "multiple", "_asked_amt": True},
        "no_amt_triggers": {"amt_status": "none", "_asked_amt": True},
        "skip_amt": {"_asked_amt": True},
        # ─── NEW: Alimony ────────────────────────────────────────────────
        "pays_alimony": {"alimony_status": "pays", "_asked_alimony": True},
        "receives_alimony": {"alimony_status": "receives", "_asked_alimony": True},
        "no_alimony": {"alimony_status": "none", "_asked_alimony": True},
        "skip_alimony": {"_asked_alimony": True},
        # ─── NEW: Gambling ───────────────────────────────────────────────
        "gambling_winnings": {"gambling_income": "winnings", "_asked_gambling": True},
        "gambling_losses": {"gambling_income": "losses", "_asked_gambling": True},
        "no_gambling": {"gambling_income": "none", "_asked_gambling": True},
        "skip_gambling": {"_asked_gambling": True},
        # ─── NEW: Household employee ─────────────────────────────────────
        "has_household_employee": {"household_employee": True, "_asked_household": True},
        "no_household_employee": {"household_employee": False, "_asked_household": True},
        "skip_household": {"_asked_household": True},
        # ─── NEW: Multi-state ────────────────────────────────────────────
        "multi_state_income": {"multi_state_income": True, "_asked_multi_state": True},
        "single_state": {"multi_state_income": False, "_asked_multi_state": True},
        "skip_multi_state": {"_asked_multi_state": True},
        # ─── NEW PHASE 1: Expanded income types ─────────────────────────
        "gig_worker": {"income_type": "gig_worker", "is_self_employed": True},
        "farmer": {"income_type": "farmer", "is_self_employed": True},
        "clergy": {"income_type": "clergy", "is_self_employed": True},
        "no_income": {"income_type": "no_income", "is_self_employed": False},
        # ─── Gig worker questions ────────────────────────────────────────
        "gig_1_platform": {"gig_platforms": 1, "_asked_gig_platforms": True},
        "gig_2_3_platforms": {"gig_platforms": 3, "_asked_gig_platforms": True},
        "gig_4plus_platforms": {"gig_platforms": 5, "_asked_gig_platforms": True},
        "skip_gig_platforms": {"_asked_gig_platforms": True},
        "gig_tracks_mileage": {"gig_mileage": "tracked", "_asked_gig_mileage": True},
        "gig_no_mileage": {"gig_mileage": "not_tracked", "_asked_gig_mileage": True},
        "gig_actual_expenses": {"gig_mileage": "actual", "_asked_gig_mileage": True},
        "skip_gig_mileage": {"_asked_gig_mileage": True},
        # ─── Farm income ─────────────────────────────────────────────────
        "farm_under_50k": {"farm_income": 30000, "_asked_farm_income": True},
        "farm_50_150k": {"farm_income": 100000, "_asked_farm_income": True},
        "farm_over_150k": {"farm_income": 200000, "_asked_farm_income": True},
        "farm_net_loss": {"farm_income": -10000, "_asked_farm_income": True},
        "skip_farm_income": {"_asked_farm_income": True},
        "has_crop_insurance": {"crop_insurance": True, "_asked_crop_insurance": True},
        "no_crop_insurance": {"crop_insurance": False, "_asked_crop_insurance": True},
        "skip_crop_insurance": {"_asked_crop_insurance": True},
        # ─── Clergy ──────────────────────────────────────────────────────
        "has_clergy_housing": {"clergy_housing": True, "_asked_clergy_housing": True},
        "no_clergy_housing": {"clergy_housing": False, "_asked_clergy_housing": True},
        "skip_clergy_housing": {"_asked_clergy_housing": True},
        # ─── 1099-K ──────────────────────────────────────────────────────
        "1099k_business": {"has_1099k": "business", "_asked_1099k": True},
        "1099k_personal": {"has_1099k": "personal", "_asked_1099k": True},
        "no_1099k": {"has_1099k": "none", "_asked_1099k": True},
        "skip_1099k": {"_asked_1099k": True},
        # ─── Tips ────────────────────────────────────────────────────────
        "has_unreported_tips": {"unreported_tips": True, "_asked_tips": True},
        "no_unreported_tips": {"unreported_tips": False, "_asked_tips": True},
        "not_tipped": {"unreported_tips": False, "_asked_tips": True},
        "skip_tips": {"_asked_tips": True},
        # ─── Statutory employee ──────────────────────────────────────────
        "is_statutory_employee": {"statutory_employee": True, "_asked_statutory": True},
        "not_statutory": {"statutory_employee": False, "_asked_statutory": True},
        "statutory_unsure": {"statutory_employee": "unsure", "_asked_statutory": True},
        "skip_statutory": {"_asked_statutory": True},
        # ─── Unemployment ────────────────────────────────────────────────
        "has_unemployment_comp": {"unemployment_comp": True, "_asked_unemployment": True},
        "no_unemployment_comp": {"unemployment_comp": False, "_asked_unemployment": True},
        "skip_unemployment": {"_asked_unemployment": True},
        # ─── Disability income ───────────────────────────────────────────
        "has_ssdi": {"disability_income_type": "ssdi", "_asked_disability": True},
        "has_va_disability": {"disability_income_type": "va_disability", "_asked_disability": True},
        "has_employer_disability": {"disability_income_type": "employer", "_asked_disability": True},
        "has_workers_comp": {"disability_income_type": "workers_comp", "_asked_disability": True},
        "no_disability": {"disability_income_type": "none", "_asked_disability": True},
        "skip_disability": {"_asked_disability": True},
        # ─── Royalties ───────────────────────────────────────────────────
        "royalty_oil_gas": {"royalty_income": "oil_gas", "_asked_royalty": True},
        "royalty_creative": {"royalty_income": "creative", "_asked_royalty": True},
        "royalty_patent": {"royalty_income": "patent", "_asked_royalty": True},
        "no_royalty": {"royalty_income": "none", "_asked_royalty": True},
        "skip_royalty": {"_asked_royalty": True},
        # ─── Interest income detail ──────────────────────────────────────
        "interest_under_1500": {"interest_income_detail": 750, "_asked_interest_detail": True},
        "interest_1500_10k": {"interest_income_detail": 5000, "_asked_interest_detail": True},
        "interest_over_10k": {"interest_income_detail": 15000, "_asked_interest_detail": True},
        "has_tax_exempt_interest": {"interest_income_detail": "tax_exempt", "_asked_interest_detail": True},
        "no_interest_income": {"interest_income_detail": 0, "_asked_interest_detail": True},
        "skip_interest_detail": {"_asked_interest_detail": True},
        # ─── Canceled debt ───────────────────────────────────────────────
        "canceled_debt_personal": {"canceled_debt": "personal", "_asked_canceled_debt": True},
        "canceled_debt_mortgage": {"canceled_debt": "mortgage", "_asked_canceled_debt": True},
        "canceled_debt_student": {"canceled_debt": "student", "_asked_canceled_debt": True},
        "no_canceled_debt": {"canceled_debt": "none", "_asked_canceled_debt": True},
        "skip_canceled_debt": {"_asked_canceled_debt": True},
        # ─── Hobby income ────────────────────────────────────────────────
        "has_hobby_income": {"hobby_income": True, "_asked_hobby": True},
        "no_hobby_income": {"hobby_income": False, "_asked_hobby": True},
        "skip_hobby": {"_asked_hobby": True},
        # ─── Blind / disabled ────────────────────────────────────────────
        "blind_taxpayer": {"legally_blind": "taxpayer", "_asked_blind": True},
        "blind_spouse": {"legally_blind": "spouse", "_asked_blind": True},
        "blind_both": {"legally_blind": "both", "_asked_blind": True},
        "not_blind": {"legally_blind": "none", "_asked_blind": True},
        "skip_blind": {"_asked_blind": True},
        # ─── Student status ──────────────────────────────────────────────
        "fulltime_student": {"student_status": "fulltime", "_asked_student_status": True},
        "parttime_student": {"student_status": "parttime", "_asked_student_status": True},
        "not_student": {"student_status": "none", "_asked_student_status": True},
        "skip_student_status": {"_asked_student_status": True},
        # ─── Filed as dependent ──────────────────────────────────────────
        "is_dependent": {"claimed_as_dependent": True, "_asked_dependent_self": True},
        "not_dependent": {"claimed_as_dependent": False, "_asked_dependent_self": True},
        "dependent_unsure": {"claimed_as_dependent": "unsure", "_asked_dependent_self": True},
        "skip_dependent_self": {"_asked_dependent_self": True},
        # ─── HOH verification ────────────────────────────────────────────
        "hoh_confirmed": {"hoh_verified": True, "_asked_hoh_verify": True},
        "hoh_unsure": {"hoh_verified": "unsure", "_asked_hoh_verify": True},
        "hoh_change_to_single": {"hoh_verified": False, "filing_status": "single", "_asked_hoh_verify": True},
        "skip_hoh_verify": {"_asked_hoh_verify": True},
        # ─── Qualifying relative ─────────────────────────────────────────
        "qr_elderly_parent": {"qualifying_relative": "elderly_parent", "_asked_qualifying_relative": True},
        "qr_other_relative": {"qualifying_relative": "other", "_asked_qualifying_relative": True},
        "qr_non_relative": {"qualifying_relative": "non_relative", "_asked_qualifying_relative": True},
        "qr_children_only": {"qualifying_relative": "children_only", "_asked_qualifying_relative": True},
        "skip_qualifying_relative": {"_asked_qualifying_relative": True},
        # ─── Disabled dependent ──────────────────────────────────────────
        "has_disabled_dependent": {"disabled_dependent": True, "_asked_disabled_dep": True},
        "no_disabled_dependent": {"disabled_dependent": False, "_asked_disabled_dep": True},
        "skip_disabled_dep": {"_asked_disabled_dep": True},
        # ─── Dependent SSN/ITIN ──────────────────────────────────────────
        "dep_all_ssn": {"dependent_ssn_status": "all_ssn", "_asked_dep_ssn": True},
        "dep_some_itin": {"dependent_ssn_status": "some_itin", "_asked_dep_ssn": True},
        "skip_dep_ssn": {"_asked_dep_ssn": True},
        # ─── Education credit type ───────────────────────────────────────
        "edu_aotc": {"education_credit_type": "aotc", "_asked_edu_credit_type": True},
        "edu_llc": {"education_credit_type": "llc", "_asked_edu_credit_type": True},
        "edu_vocational": {"education_credit_type": "vocational", "_asked_edu_credit_type": True},
        "edu_unsure": {"education_credit_type": "unsure", "_asked_edu_credit_type": True},
        "skip_edu_credit_type": {"_asked_edu_credit_type": True},
        # ─── 529 distributions ───────────────────────────────────────────
        "529_qualified": {"_529_distribution": "qualified", "_asked_529_dist": True},
        "529_nonqualified": {"_529_distribution": "nonqualified", "_asked_529_dist": True},
        "529_no_dist": {"_529_distribution": "none", "_asked_529_dist": True},
        "skip_529_dist": {"_asked_529_dist": True},
        # ─── Life event follow-ups ───────────────────────────────────────
        "has_mortgage_points": {"mortgage_points": True, "_asked_mortgage_points": True},
        "no_mortgage_points": {"mortgage_points": False, "_asked_mortgage_points": True},
        "mortgage_points_unsure": {"mortgage_points": "unsure", "_asked_mortgage_points": True},
        "skip_mortgage_points": {"_asked_mortgage_points": True},
        "has_first_home_ira": {"first_home_ira": True, "_asked_first_home_ira": True},
        "no_first_home_ira": {"first_home_ira": False, "_asked_first_home_ira": True},
        "skip_first_home_ira": {"_asked_first_home_ira": True},
        "home_gain_under_100k": {"home_sale_gain": 50000, "_asked_home_gain": True},
        "home_gain_100_250k": {"home_sale_gain": 175000, "_asked_home_gain": True},
        "home_gain_250_500k": {"home_sale_gain": 375000, "_asked_home_gain": True},
        "home_gain_over_500k": {"home_sale_gain": 600000, "_asked_home_gain": True},
        "home_gain_loss": {"home_sale_gain": -20000, "_asked_home_gain": True},
        "skip_home_gain": {"_asked_home_gain": True},
        "compare_mfj_mfs": {"mfj_mfs_preference": "compare", "_asked_mfj_mfs": True},
        "prefer_mfj": {"mfj_mfs_preference": "mfj", "_asked_mfj_mfs": True},
        "prefer_mfs": {"mfj_mfs_preference": "mfs", "_asked_mfj_mfs": True},
        "skip_mfj_mfs": {"_asked_mfj_mfs": True},
        "divorce_this_year": {"divorce_year": "this_year", "_asked_divorce_year": True},
        "divorce_pre_2019": {"divorce_year": "pre_2019", "_asked_divorce_year": True},
        "divorce_post_2019": {"divorce_year": "post_2019", "_asked_divorce_year": True},
        "divorce_pending": {"divorce_year": "pending", "_asked_divorce_year": True},
        "skip_divorce_year": {"_asked_divorce_year": True},
        "has_qdro": {"qdro_distribution": True, "_asked_qdro": True},
        "no_qdro": {"qdro_distribution": False, "_asked_qdro": True},
        "skip_qdro": {"_asked_qdro": True},
        "inherited_cash": {"inheritance_type": "cash", "_asked_inheritance_type": True},
        "inherited_real_estate": {"inheritance_type": "real_estate", "_asked_inheritance_type": True},
        "inherited_investments": {"inheritance_type": "investments", "_asked_inheritance_type": True},
        "inherited_retirement": {"inheritance_type": "retirement", "_asked_inheritance_type": True},
        "inherited_business": {"inheritance_type": "business", "_asked_inheritance_type": True},
        "inherited_multiple": {"inheritance_type": "multiple", "_asked_inheritance_type": True},
        "skip_inheritance_type": {"_asked_inheritance_type": True},
        "rollover_new_employer": {"job_change_401k": "new_employer", "_asked_job_401k": True},
        "rollover_ira": {"job_change_401k": "ira", "_asked_job_401k": True},
        "rollover_cashout": {"job_change_401k": "cashout", "_asked_job_401k": True},
        "rollover_left": {"job_change_401k": "left", "_asked_job_401k": True},
        "skip_job_401k": {"_asked_job_401k": True},
        "spouse_died_this_year": {"spouse_death_year": "this_year", "_asked_spouse_death": True},
        "spouse_alive": {"spouse_death_year": "alive", "_asked_spouse_death": True},
        "skip_spouse_death": {"_asked_spouse_death": True},
        # ─── Investment follow-ups ───────────────────────────────────────
        "has_wash_sale": {"wash_sale": True, "_asked_wash_sale": True},
        "no_wash_sale": {"wash_sale": False, "_asked_wash_sale": True},
        "wash_sale_unsure": {"wash_sale": "unsure", "_asked_wash_sale": True},
        "skip_wash_sale": {"_asked_wash_sale": True},
        "niit_applies": {"niit_status": "applies", "_asked_niit": True},
        "skip_niit": {"_asked_niit": True},
        "has_installment_sale": {"installment_sale": True, "_asked_installment": True},
        "no_installment_sale": {"installment_sale": False, "_asked_installment": True},
        "skip_installment": {"_asked_installment": True},
        "has_1031_exchange": {"like_kind_exchange": "completed", "_asked_1031": True},
        "in_1031_exchange": {"like_kind_exchange": "in_progress", "_asked_1031": True},
        "no_1031_exchange": {"like_kind_exchange": "none", "_asked_1031": True},
        "skip_1031": {"_asked_1031": True},
        "qsbs_qualified": {"qsbs_sale": "qualified", "_asked_qsbs": True},
        "qsbs_not_qualified": {"qsbs_sale": "not_qualified", "_asked_qsbs": True},
        "no_qsbs": {"qsbs_sale": "none", "_asked_qsbs": True},
        "skip_qsbs": {"_asked_qsbs": True},
        "has_qoz": {"qoz_investment": True, "_asked_qoz": True},
        "no_qoz": {"qoz_investment": False, "_asked_qoz": True},
        "skip_qoz": {"_asked_qoz": True},
        "has_collectibles": {"collectibles_sold": True, "_asked_collectibles": True},
        "no_collectibles": {"collectibles_sold": False, "_asked_collectibles": True},
        "skip_collectibles": {"_asked_collectibles": True},
        "has_inv_interest_expense": {"investment_interest_expense": True, "_asked_inv_interest": True},
        "no_inv_interest_expense": {"investment_interest_expense": False, "_asked_inv_interest": True},
        "skip_inv_interest": {"_asked_inv_interest": True},
        "has_passive_carryforward": {"passive_loss_carryforward": True, "_asked_passive_carryforward": True},
        "no_passive_carryforward": {"passive_loss_carryforward": False, "_asked_passive_carryforward": True},
        "passive_carryforward_unsure": {"passive_loss_carryforward": "unsure", "_asked_passive_carryforward": True},
        "skip_passive_carryforward": {"_asked_passive_carryforward": True},
        "addl_medicare_applies": {"addl_medicare_tax": True, "_asked_addl_medicare": True},
        "skip_addl_medicare": {"_asked_addl_medicare": True},
        # ─── Retirement follow-ups ───────────────────────────────────────
        "has_backdoor_roth": {"backdoor_roth": True, "_asked_backdoor_roth": True},
        "no_backdoor_roth": {"backdoor_roth": False, "_asked_backdoor_roth": True},
        "skip_backdoor_roth": {"_asked_backdoor_roth": True},
        "has_ira_basis": {"ira_basis": True, "_asked_ira_basis": True},
        "no_ira_basis": {"ira_basis": False, "_asked_ira_basis": True},
        "ira_basis_unsure": {"ira_basis": "unsure", "_asked_ira_basis": True},
        "skip_ira_basis": {"_asked_ira_basis": True},
        "inherited_ira_pre_2020": {"inherited_ira": "pre_2020", "_asked_inherited_ira": True},
        "inherited_ira_post_2020": {"inherited_ira": "post_2020", "_asked_inherited_ira": True},
        "inherited_ira_spouse": {"inherited_ira": "spouse", "_asked_inherited_ira": True},
        "no_inherited_ira": {"inherited_ira": "none", "_asked_inherited_ira": True},
        "skip_inherited_ira": {"_asked_inherited_ira": True},
        "has_qcd": {"qcd": True, "_asked_qcd": True},
        "under_70_half": {"qcd": "under_age", "_asked_qcd": True},
        "no_qcd": {"qcd": False, "_asked_qcd": True},
        "skip_qcd": {"_asked_qcd": True},
        "eitc_likely": {"eitc_status": "likely", "_asked_eitc": True},
        "eitc_inv_too_high": {"eitc_status": "inv_disqualified", "_asked_eitc": True},
        "eitc_unsure": {"eitc_status": "unsure", "_asked_eitc": True},
        "skip_eitc": {"_asked_eitc": True},
        "savers_credit_yes": {"savers_credit": True, "_asked_savers_credit": True},
        "savers_student": {"savers_credit": "student_disqualified", "_asked_savers_credit": True},
        "skip_savers_credit": {"_asked_savers_credit": True},
        "elderly_credit_yes": {"elderly_disabled_credit": True, "_asked_elderly_credit": True},
        "elderly_credit_no": {"elderly_disabled_credit": False, "_asked_elderly_credit": True},
        "skip_elderly_credit": {"_asked_elderly_credit": True},
        # ─── Deduction follow-ups ────────────────────────────────────────
        "noncash_goods": {"noncash_charitable": "goods", "_asked_noncash_charitable": True},
        "noncash_stock": {"noncash_charitable": "stock", "_asked_noncash_charitable": True},
        "noncash_vehicle": {"noncash_charitable": "vehicle", "_asked_noncash_charitable": True},
        "noncash_none": {"noncash_charitable": "none", "_asked_noncash_charitable": True},
        "skip_noncash_charitable": {"_asked_noncash_charitable": True},
        "has_casualty_loss": {"casualty_loss": True, "_asked_casualty": True},
        "no_casualty_loss": {"casualty_loss": False, "_asked_casualty": True},
        "skip_casualty": {"_asked_casualty": True},
        "ho_simplified": {"home_office_method": "simplified", "_asked_ho_method": True},
        "ho_regular": {"home_office_method": "regular", "_asked_ho_method": True},
        "ho_unsure": {"home_office_method": "unsure", "_asked_ho_method": True},
        "skip_ho_method": {"_asked_ho_method": True},
        "biz_travel": {"biz_meals_travel": "travel", "_asked_biz_meals": True},
        "biz_meals": {"biz_meals_travel": "meals", "_asked_biz_meals": True},
        "biz_meals_and_travel": {"biz_meals_travel": "both", "_asked_biz_meals": True},
        "no_biz_meals": {"biz_meals_travel": "none", "_asked_biz_meals": True},
        "skip_biz_meals": {"_asked_biz_meals": True},
        "has_biz_insurance": {"biz_insurance": True, "_asked_biz_insurance": True},
        "no_biz_insurance": {"biz_insurance": False, "_asked_biz_insurance": True},
        "skip_biz_insurance": {"_asked_biz_insurance": True},
        "has_nol": {"nol_carryforward": True, "_asked_nol": True},
        "no_nol": {"nol_carryforward": False, "_asked_nol": True},
        "nol_unsure": {"nol_carryforward": "unsure", "_asked_nol": True},
        "skip_nol": {"_asked_nol": True},
        # ─── State/special follow-ups ────────────────────────────────────
        "state_refund_taxable": {"state_refund_taxable": True, "_asked_state_refund": True},
        "state_refund_not_taxable": {"state_refund_taxable": False, "_asked_state_refund": True},
        "no_state_refund": {"state_refund_taxable": "none", "_asked_state_refund": True},
        "skip_state_refund": {"_asked_state_refund": True},
        "has_prize_income": {"prize_income": True, "_asked_prizes": True},
        "no_prize_income": {"prize_income": False, "_asked_prizes": True},
        "skip_prizes": {"_asked_prizes": True},
        "community_prop_aware": {"community_property": "aware", "_asked_community_prop": True},
        "community_prop_help": {"community_property": "help", "_asked_community_prop": True},
        "skip_community_prop": {"_asked_community_prop": True},
        "has_excess_ss": {"excess_ss": True, "_asked_excess_ss": True},
        "no_excess_ss": {"excess_ss": False, "_asked_excess_ss": True},
        "skip_excess_ss": {"_asked_excess_ss": True},
        "has_ip_pin": {"identity_pin": True, "_asked_ip_pin": True},
        "no_ip_pin": {"identity_pin": False, "_asked_ip_pin": True},
        "skip_ip_pin": {"_asked_ip_pin": True},
        "has_local_tax": {"local_income_tax": True, "_asked_local_tax": True},
        "no_local_tax": {"local_income_tax": False, "_asked_local_tax": True},
        "local_tax_unsure": {"local_income_tax": "unsure", "_asked_local_tax": True},
        "skip_local_tax": {"_asked_local_tax": True},
        "state_wh_under_2k": {"state_withholding": 1000, "_asked_state_withholding": True},
        "state_wh_2_5k": {"state_withholding": 3500, "_asked_state_withholding": True},
        "state_wh_5_10k": {"state_withholding": 7500, "_asked_state_withholding": True},
        "state_wh_over_10k": {"state_withholding": 12000, "_asked_state_withholding": True},
        "state_wh_unsure": {"_asked_state_withholding": True},
        "skip_state_withholding": {"_asked_state_withholding": True},
        # ─── Filing logistics ────────────────────────────────────────────
        "prior_refund": {"prior_year_return": "refund", "_asked_prior_year": True},
        "prior_owed": {"prior_year_return": "owed", "_asked_prior_year": True},
        "prior_even": {"prior_year_return": "even", "_asked_prior_year": True},
        "prior_not_filed": {"prior_year_return": "not_filed", "_asked_prior_year": True},
        "skip_prior_year": {"_asked_prior_year": True},
        "has_extension": {"extension_filed": True, "_asked_extension": True},
        "no_extension": {"extension_filed": False, "_asked_extension": True},
        "skip_extension": {"_asked_extension": True},
        "refund_direct_deposit": {"refund_preference": "direct_deposit", "_asked_refund_pref": True},
        "refund_check": {"refund_preference": "check", "_asked_refund_pref": True},
        "refund_apply_next": {"refund_preference": "apply_next", "_asked_refund_pref": True},
        "refund_split": {"refund_preference": "split", "_asked_refund_pref": True},
        "skip_refund_pref": {"_asked_refund_pref": True},
        # ─── Remaining gap fixes: 1099-R, HSA dist, director, barter, jury ───
        "1099r_annuity": {"other_1099r": "annuity", "_asked_other_1099r": True},
        "1099r_life_insurance": {"other_1099r": "life_insurance", "_asked_other_1099r": True},
        "1099r_457b": {"other_1099r": "457b", "_asked_other_1099r": True},
        "1099r_disability_pension": {"other_1099r": "disability_pension", "_asked_other_1099r": True},
        "no_other_1099r": {"other_1099r": "none", "_asked_other_1099r": True},
        "skip_other_1099r": {"_asked_other_1099r": True},
        "hsa_dist_qualified": {"hsa_distributions": "qualified", "_asked_hsa_dist": True},
        "hsa_dist_nonqualified": {"hsa_distributions": "nonqualified", "_asked_hsa_dist": True},
        "hsa_no_dist": {"hsa_distributions": "none", "_asked_hsa_dist": True},
        "skip_hsa_dist": {"_asked_hsa_dist": True},
        "has_director_fees": {"director_fees": True, "_asked_director_fees": True},
        "no_director_fees": {"director_fees": False, "_asked_director_fees": True},
        "skip_director_fees": {"_asked_director_fees": True},
        "has_bartering": {"bartering_income": True, "_asked_bartering": True},
        "no_bartering": {"bartering_income": False, "_asked_bartering": True},
        "skip_bartering": {"_asked_bartering": True},
        "jury_duty_kept": {"jury_duty_pay": "kept", "_asked_jury_duty": True},
        "jury_duty_employer": {"jury_duty_pay": "employer", "_asked_jury_duty": True},
        "no_jury_duty": {"jury_duty_pay": "none", "_asked_jury_duty": True},
        "skip_jury_duty": {"_asked_jury_duty": True},
        "has_oid": {"oid_income": True, "_asked_oid": True},
        "no_oid": {"oid_income": False, "_asked_oid": True},
        "skip_oid": {"_asked_oid": True},
        "has_ltc_benefits": {"ltc_benefits": True, "_asked_ltc": True},
        "no_ltc_benefits": {"ltc_benefits": False, "_asked_ltc": True},
        "skip_ltc": {"_asked_ltc": True},
        # ─── Spouse/dependent gap fixes ──────────────────────────────────
        "nra_spouse_elect": {"nra_spouse_election": "elect", "_asked_nra_spouse": True},
        "nra_spouse_na": {"nra_spouse_election": "na", "_asked_nra_spouse": True},
        "skip_nra_spouse": {"_asked_nra_spouse": True},
        "spouse_is_educator": {"spouse_educator": True, "_asked_spouse_educator": True},
        "spouse_not_educator": {"spouse_educator": False, "_asked_spouse_educator": True},
        "skip_spouse_educator": {"_asked_spouse_educator": True},
        "has_employer_dc": {"employer_dc_benefits": True, "_asked_employer_dc": True},
        "no_employer_dc": {"employer_dc_benefits": False, "_asked_employer_dc": True},
        "skip_employer_dc": {"_asked_employer_dc": True},
        "has_multiple_support": {"multiple_support": True, "_asked_multiple_support": True},
        "no_multiple_support": {"multiple_support": False, "_asked_multiple_support": True},
        "skip_multiple_support": {"_asked_multiple_support": True},
        "student_dep_fulltime": {"student_dependent_status": "fulltime", "_asked_student_dep": True},
        "student_dep_no": {"student_dependent_status": "no", "_asked_student_dep": True},
        "skip_student_dep": {"_asked_student_dep": True},
        "qss_confirmed": {"qss_verified": True, "_asked_qss_verify": True},
        "qss_change": {"qss_verified": False, "_asked_qss_verify": True},
        "skip_qss_verify": {"_asked_qss_verify": True},
        # ─── Investment gap fixes ────────────────────────────────────────
        "has_section_1256": {"section_1256": "futures", "_asked_section_1256": True},
        "has_forex": {"section_1256": "forex", "_asked_section_1256": True},
        "no_section_1256": {"section_1256": "none", "_asked_section_1256": True},
        "skip_section_1256": {"_asked_section_1256": True},
        "has_mlp": {"mlp_income": True, "_asked_mlp": True},
        "no_mlp": {"mlp_income": False, "_asked_mlp": True},
        "skip_mlp": {"_asked_mlp": True},
        "espp_qualifying": {"espp_disposition": "qualifying", "_asked_espp_disp": True},
        "espp_disqualifying": {"espp_disposition": "disqualifying", "_asked_espp_disp": True},
        "espp_not_sold": {"espp_disposition": "not_sold", "_asked_espp_disp": True},
        "skip_espp_disp": {"_asked_espp_disp": True},
        "iso_exercised_held": {"iso_amt_detail": "exercised_held", "_asked_iso_amt": True},
        "iso_same_day": {"iso_amt_detail": "same_day", "_asked_iso_amt": True},
        "skip_iso_amt": {"_asked_iso_amt": True},
        # ─── Retirement gap fixes ────────────────────────────────────────
        "has_catch_up": {"catch_up_contributions": True, "_asked_catch_up": True},
        "no_catch_up": {"catch_up_contributions": False, "_asked_catch_up": True},
        "skip_catch_up": {"_asked_catch_up": True},
        "has_mega_backdoor": {"mega_backdoor_roth": True, "_asked_mega_backdoor": True},
        "no_mega_backdoor": {"mega_backdoor_roth": False, "_asked_mega_backdoor": True},
        "skip_mega_backdoor": {"_asked_mega_backdoor": True},
        "ira_has_workplace_plan": {"ira_deductibility": "has_plan", "_asked_ira_deduct": True},
        "ira_spouse_workplace_plan": {"ira_deductibility": "spouse_plan", "_asked_ira_deduct": True},
        "ira_no_workplace_plan": {"ira_deductibility": "no_plan", "_asked_ira_deduct": True},
        "skip_ira_deduct": {"_asked_ira_deduct": True},
        "ctc_under_threshold": {"ctc_phaseout_aware": "under", "_asked_ctc_phaseout": True},
        "ctc_over_threshold": {"ctc_phaseout_aware": "over", "_asked_ctc_phaseout": True},
        "ctc_threshold_unsure": {"ctc_phaseout_aware": "unsure", "_asked_ctc_phaseout": True},
        "skip_ctc_phaseout": {"_asked_ctc_phaseout": True},
        "ftc_simple": {"foreign_tax_credit_detail": "simple", "_asked_ftc_detail": True},
        "ftc_moderate": {"foreign_tax_credit_detail": "moderate", "_asked_ftc_detail": True},
        "ftc_complex": {"foreign_tax_credit_detail": "complex", "_asked_ftc_detail": True},
        "skip_ftc_detail": {"_asked_ftc_detail": True},
        "aca_income_higher": {"aca_reconciliation": "higher", "_asked_aca_recon": True},
        "aca_income_lower": {"aca_reconciliation": "lower", "_asked_aca_recon": True},
        "aca_income_same": {"aca_reconciliation": "same", "_asked_aca_recon": True},
        "skip_aca_recon": {"_asked_aca_recon": True},
        # ─── Deduction/business gap fixes ────────────────────────────────
        "has_early_savings_penalty": {"early_savings_penalty": True, "_asked_early_savings": True},
        "no_early_savings_penalty": {"early_savings_penalty": False, "_asked_early_savings": True},
        "skip_early_savings": {"_asked_early_savings": True},
        "sl_under_1k": {"student_loan_amount": 750, "_asked_sl_amount": True},
        "sl_1_2500": {"student_loan_amount": 1750, "_asked_sl_amount": True},
        "sl_over_2500": {"student_loan_amount": 2500, "_asked_sl_amount": True},
        "skip_sl_amount": {"_asked_sl_amount": True},
        "gambling_losses_exceed": {"gambling_loss_detail": "exceed", "_asked_gambling_loss": True},
        "gambling_losses_less": {"gambling_loss_detail": "less", "_asked_gambling_loss": True},
        "skip_gambling_loss": {"_asked_gambling_loss": True},
        "accounting_cash": {"accounting_method": "cash", "_asked_accounting": True},
        "accounting_accrual": {"accounting_method": "accrual", "_asked_accounting": True},
        "accounting_unsure": {"accounting_method": "unsure", "_asked_accounting": True},
        "skip_accounting": {"_asked_accounting": True},
        "has_inventory": {"has_inventory": True, "_asked_inventory": True},
        "no_inventory": {"has_inventory": False, "_asked_inventory": True},
        "skip_inventory": {"_asked_inventory": True},
        "biz_prop_gain": {"sold_biz_property": "gain", "_asked_sold_biz_prop": True},
        "biz_prop_loss": {"sold_biz_property": "loss", "_asked_sold_biz_prop": True},
        "no_sold_biz_prop": {"sold_biz_property": "none", "_asked_sold_biz_prop": True},
        "skip_sold_biz_prop": {"_asked_sold_biz_prop": True},
        "listed_prop_over_50": {"listed_property": "over_50", "_asked_listed_prop": True},
        "listed_prop_under_50": {"listed_property": "under_50", "_asked_listed_prop": True},
        "listed_prop_100": {"listed_property": "100", "_asked_listed_prop": True},
        "no_listed_prop": {"listed_property": "none", "_asked_listed_prop": True},
        "skip_listed_prop": {"_asked_listed_prop": True},
        "has_excess_biz_loss": {"excess_biz_loss": True, "_asked_excess_biz_loss": True},
        "no_excess_biz_loss": {"excess_biz_loss": False, "_asked_excess_biz_loss": True},
        "excess_biz_loss_unsure": {"excess_biz_loss": "unsure", "_asked_excess_biz_loss": True},
        "skip_excess_biz_loss": {"_asked_excess_biz_loss": True},
        "has_employer_ret_plan": {"employer_retirement_plan": True, "_asked_employer_ret_plan": True},
        "employer_ret_interested": {"employer_retirement_plan": "interested", "_asked_employer_ret_plan": True},
        "no_employer_ret_plan": {"employer_retirement_plan": False, "_asked_employer_ret_plan": True},
        "skip_employer_ret_plan": {"_asked_employer_ret_plan": True},
        "qbi_wages_under_100k": {"qbi_w2_wages": 60000, "_asked_qbi_wages": True},
        "qbi_wages_100_250k": {"qbi_w2_wages": 175000, "_asked_qbi_wages": True},
        "qbi_wages_over_250k": {"qbi_w2_wages": 300000, "_asked_qbi_wages": True},
        "qbi_no_w2_wages": {"qbi_w2_wages": 0, "_asked_qbi_wages": True},
        "skip_qbi_wages": {"_asked_qbi_wages": True},
        # ─── Rental gap fixes ────────────────────────────────────────────
        "is_short_term_rental": {"short_term_rental": "short_term", "_asked_short_term": True},
        "short_term_hotel_services": {"short_term_rental": "hotel_services", "_asked_short_term": True},
        "long_term_rental": {"short_term_rental": "long_term", "_asked_short_term": True},
        "skip_short_term": {"_asked_short_term": True},
        "personal_use_excess": {"personal_use_days": "excess", "_asked_personal_use": True},
        "personal_use_minimal": {"personal_use_days": "minimal", "_asked_personal_use": True},
        "personal_use_unsure": {"personal_use_days": "unsure", "_asked_personal_use": True},
        "skip_personal_use": {"_asked_personal_use": True},
        "rental_below_fmv": {"below_fmv_rental": True, "_asked_below_fmv": True},
        "rental_fair_market": {"below_fmv_rental": False, "_asked_below_fmv": True},
        "skip_below_fmv": {"_asked_below_fmv": True},
        "has_cost_seg": {"cost_segregation": True, "_asked_cost_seg": True},
        "cost_seg_interested": {"cost_segregation": "interested", "_asked_cost_seg": True},
        "no_cost_seg": {"cost_segregation": False, "_asked_cost_seg": True},
        "skip_cost_seg": {"_asked_cost_seg": True},
        "converted_to_rental": {"rental_conversion": "to_rental", "_asked_rental_convert": True},
        "converted_to_personal": {"rental_conversion": "to_personal", "_asked_rental_convert": True},
        "no_rental_conversion": {"rental_conversion": "none", "_asked_rental_convert": True},
        "skip_rental_convert": {"_asked_rental_convert": True},
        "rental_loss_full": {"rental_loss_allowance": "full", "_asked_rental_loss_allow": True},
        "rental_loss_partial": {"rental_loss_allowance": "partial", "_asked_rental_loss_allow": True},
        "rental_loss_none": {"rental_loss_allowance": "none", "_asked_rental_loss_allow": True},
        "skip_rental_loss_allow": {"_asked_rental_loss_allow": True},
        # ─── International gap fixes ─────────────────────────────────────
        "feie_bona_fide": {"feie_status": "bona_fide", "_asked_feie": True},
        "feie_physical_presence": {"feie_status": "physical_presence", "_asked_feie": True},
        "feie_short_term": {"feie_status": "short_term", "_asked_feie": True},
        "skip_feie": {"_asked_feie": True},
        "has_foreign_housing": {"foreign_housing": True, "_asked_foreign_housing": True},
        "no_foreign_housing": {"foreign_housing": False, "_asked_foreign_housing": True},
        "skip_foreign_housing": {"_asked_foreign_housing": True},
        "fbar_1_2": {"fbar_detail": "1_2", "_asked_fbar_detail": True},
        "fbar_3_5": {"fbar_detail": "3_5", "_asked_fbar_detail": True},
        "fbar_5plus": {"fbar_detail": "5plus", "_asked_fbar_detail": True},
        "skip_fbar_detail": {"_asked_fbar_detail": True},
        "fatca_yes": {"fatca_status": True, "_asked_fatca": True},
        "fatca_no": {"fatca_status": False, "_asked_fatca": True},
        "fatca_unsure": {"fatca_status": "unsure", "_asked_fatca": True},
        "skip_fatca": {"_asked_fatca": True},
        "has_foreign_corp": {"foreign_corp": "corp", "_asked_foreign_corp": True},
        "has_foreign_partnership": {"foreign_corp": "partnership", "_asked_foreign_corp": True},
        "no_foreign_corp": {"foreign_corp": "none", "_asked_foreign_corp": True},
        "skip_foreign_corp": {"_asked_foreign_corp": True},
        "has_foreign_trust": {"foreign_trust": True, "_asked_foreign_trust": True},
        "no_foreign_trust": {"foreign_trust": False, "_asked_foreign_trust": True},
        "skip_foreign_trust": {"_asked_foreign_trust": True},
        "has_treaty": {"treaty_position": True, "_asked_treaty": True},
        "no_treaty": {"treaty_position": False, "_asked_treaty": True},
        "skip_treaty": {"_asked_treaty": True},
        "has_pfic": {"pfic_status": True, "_asked_pfic": True},
        "no_pfic": {"pfic_status": False, "_asked_pfic": True},
        "pfic_unsure": {"pfic_status": "unsure", "_asked_pfic": True},
        "skip_pfic": {"_asked_pfic": True},
        # ─── Energy/credit detail gap fixes ──────────────────────────────
        "solar_under_15k": {"solar_cost": 10000, "_asked_solar_cost": True},
        "solar_15_30k": {"solar_cost": 22000, "_asked_solar_cost": True},
        "solar_30_50k": {"solar_cost": 40000, "_asked_solar_cost": True},
        "solar_over_50k": {"solar_cost": 60000, "_asked_solar_cost": True},
        "skip_solar_cost": {"_asked_solar_cost": True},
        "ev_new_qualified": {"ev_detail": "new_qualified", "_asked_ev_detail": True},
        "ev_new_over_msrp": {"ev_detail": "new_over_msrp", "_asked_ev_detail": True},
        "ev_used_qualified": {"ev_detail": "used_qualified", "_asked_ev_detail": True},
        "skip_ev_detail": {"_asked_ev_detail": True},
        "energy_heat_pump": {"energy_improvement_detail": "heat_pump", "_asked_energy_detail": True},
        "energy_insulation": {"energy_improvement_detail": "insulation", "_asked_energy_detail": True},
        "energy_panel": {"energy_improvement_detail": "panel", "_asked_energy_detail": True},
        "energy_multiple_detail": {"energy_improvement_detail": "multiple", "_asked_energy_detail": True},
        "skip_energy_detail": {"_asked_energy_detail": True},
        "has_wotc": {"wotc": True, "_asked_wotc": True},
        "no_wotc": {"wotc": False, "_asked_wotc": True},
        "skip_wotc": {"_asked_wotc": True},
        # ─── Special situation gap fixes ─────────────────────────────────
        "bankruptcy_ch7": {"bankruptcy_status": "ch7", "_asked_bankruptcy": True},
        "bankruptcy_ch13": {"bankruptcy_status": "ch13", "_asked_bankruptcy": True},
        "no_bankruptcy": {"bankruptcy_status": "none", "_asked_bankruptcy": True},
        "skip_bankruptcy": {"_asked_bankruptcy": True},
        "underpayment_exposed": {"underpayment_exposure": "exposed", "_asked_underpayment": True},
        "underpayment_adjusted": {"underpayment_exposure": "adjusted", "_asked_underpayment": True},
        "underpayment_na": {"underpayment_exposure": "na", "_asked_underpayment": True},
        "skip_underpayment": {"_asked_underpayment": True},
        "has_amended": {"amended_return": True, "_asked_amended": True},
        "no_amended": {"amended_return": False, "_asked_amended": True},
        "skip_amended": {"_asked_amended": True},
        "has_state_credits": {"state_credits": True, "_asked_state_credits": True},
        "state_credits_unsure": {"state_credits": "unsure", "_asked_state_credits": True},
        "no_state_credits": {"state_credits": False, "_asked_state_credits": True},
        "skip_state_credits": {"_asked_state_credits": True},
        # ─── Final gap fixes ─────────────────────────────────────────────
        "partial_excl_job": {"partial_exclusion": "job", "_asked_partial_exclusion": True},
        "partial_excl_health": {"partial_exclusion": "health", "_asked_partial_exclusion": True},
        "partial_excl_unforeseen": {"partial_exclusion": "unforeseen", "_asked_partial_exclusion": True},
        "no_partial_exclusion": {"partial_exclusion": "none", "_asked_partial_exclusion": True},
        "skip_partial_exclusion": {"_asked_partial_exclusion": True},
        "no_felony_drug": {"felony_drug": False, "_asked_felony_drug": True},
        "has_felony_drug": {"felony_drug": True, "_asked_felony_drug": True},
        "skip_felony_drug": {"_asked_felony_drug": True},
        "has_archer_msa": {"archer_msa": True, "_asked_archer_msa": True},
        "no_archer_msa": {"archer_msa": False, "_asked_archer_msa": True},
        "skip_archer_msa": {"_asked_archer_msa": True},
        # ─── Phase 1: Filing status values ───────────────────────────────
        "single": {"filing_status": "single"},
        "married_joint": {"filing_status": "married_joint"},
        "married_separate": {"filing_status": "married_separate"},
        "head_of_household": {"filing_status": "head_of_household"},
        "qualifying_widow": {"filing_status": "qualifying_widow"},
        # ─── Phase 1: Old income range values (backward compat) ──────────
        "income_under_50k": {"total_income": 30000},
        "income_50_100k": {"total_income": 75000},
        "income_100_200k": {"total_income": 150000},
        "income_over_200k": {"total_income": 350000},
        # ─── Phase 1: All 50 states + DC ─────────────────────────────────
        "AL": {"state": "AL"}, "AK": {"state": "AK"}, "AZ": {"state": "AZ"},
        "AR": {"state": "AR"}, "CA": {"state": "CA"}, "CO": {"state": "CO"},
        "CT": {"state": "CT"}, "DE": {"state": "DE"}, "FL": {"state": "FL"},
        "GA": {"state": "GA"}, "HI": {"state": "HI"}, "ID": {"state": "ID"},
        "IL": {"state": "IL"}, "IN": {"state": "IN"}, "IA": {"state": "IA"},
        "KS": {"state": "KS"}, "KY": {"state": "KY"}, "LA": {"state": "LA"},
        "ME": {"state": "ME"}, "MD": {"state": "MD"}, "MA": {"state": "MA"},
        "MI": {"state": "MI"}, "MN": {"state": "MN"}, "MS": {"state": "MS"},
        "MO": {"state": "MO"}, "MT": {"state": "MT"}, "NE": {"state": "NE"},
        "NV": {"state": "NV"}, "NH": {"state": "NH"}, "NJ": {"state": "NJ"},
        "NM": {"state": "NM"}, "NY": {"state": "NY"}, "NC": {"state": "NC"},
        "ND": {"state": "ND"}, "OH": {"state": "OH"}, "OK": {"state": "OK"},
        "OR": {"state": "OR"}, "PA": {"state": "PA"}, "RI": {"state": "RI"},
        "SC": {"state": "SC"}, "SD": {"state": "SD"}, "TN": {"state": "TN"},
        "TX": {"state": "TX"}, "UT": {"state": "UT"}, "VT": {"state": "VT"},
        "VA": {"state": "VA"}, "WA": {"state": "WA"}, "WV": {"state": "WV"},
        "WI": {"state": "WI"}, "WY": {"state": "WY"}, "DC": {"state": "DC"},
    }

    # Handle multi-select (comma-separated values from frontend checkboxes)
    if ',' in msg_lower and msg_lower not in _quick_action_map:
        _multi_values = [v.strip() for v in msg_lower.split(',')]
        _multi_updates = {}
        for _mv in _multi_values:
            if _mv in _quick_action_map:
                _multi_updates.update(_quick_action_map[_mv])
        if _multi_updates:
            msg_lower = _multi_values[0]  # Use first value for smart default check
            updates = _multi_updates
            profile.update(updates)
            session = await chat_engine.update_session(request.session_id, {"profile": profile})
            _quick_action_handled = True

    if not _quick_action_handled and msg_lower in _quick_action_map:
        updates = _quick_action_map[msg_lower]
        # Smart default: apply estimated value when user accepts (Feature 2)
        if msg_lower == "withholding_smart_default":
            _sd = _estimate_smart_default("federal_withholding", profile)
            if _sd:
                updates["federal_withholding"] = _sd["smart_value"]
        elif msg_lower == "state_wh_smart_default":
            _sd = _estimate_smart_default("state_withholding", profile)
            if _sd:
                updates["state_withholding"] = _sd["smart_value"]

        profile.update(updates)
        session = await chat_engine.update_session(request.session_id, {"profile": profile})
        _quick_action_handled = True

        # Create checkpoint for undo
        real_fields = [k for k in updates.keys() if not k.startswith("_")]
        if real_fields:
            await chat_engine.create_checkpoint(request.session_id, msg_original, real_fields)

        # ── COMPARISON SCENARIOS (Feature 8) — MFJ vs MFS ─────────────────
        if profile.get("mfj_mfs_preference") == "compare" and not profile.get("_comparison_shown"):
            profile["_comparison_shown"] = True
            _mfj_p = {**profile, "filing_status": "married_joint"}
            _mfs_p = {**profile, "filing_status": "married_separate"}
            _mfj_est = _quick_tax_estimate(_mfj_p)
            _mfs_est = _quick_tax_estimate(_mfs_p)
            _better = "Married Filing Jointly" if _mfj_est["amount"] >= _mfs_est["amount"] else "Married Filing Separately"
            _diff = abs(_mfj_est["amount"] - _mfs_est["amount"])
            session = await chat_engine.update_session(request.session_id, {"profile": profile})
            return ChatResponse(
                session_id=request.session_id,
                response=(
                    f"Here's how your filing options compare:\n\n"
                    f"**Married Filing Jointly:** {_mfj_est['label']}\n"
                    f"**Married Filing Separately:** {_mfs_est['label']}\n\n"
                    f"💡 **Recommendation: {_better}** saves you ~${_diff:,.0f}"
                ),
                response_type="comparison",
                conversation_mode=profile.get("_conversation_mode", "guided"),
                quick_actions=[
                    {"label": f"File as {_better}", "value": "prefer_mfj" if "Jointly" in _better else "prefer_mfs"},
                    {"label": "I'll decide later", "value": "skip_mfj_mfs"},
                ],
                metadata={"_source": "comparison", "mfj": _mfj_est["amount"], "mfs": _mfs_est["amount"], "savings": _diff},
            )

        # ── DOCUMENT UPLOAD OFFER (Feature 5) ────────────────────────────
        _phase1_complete = all([
            profile.get("filing_status"), profile.get("total_income"),
            profile.get("state"), profile.get("dependents") is not None,
            profile.get("income_type"),
        ])
        if _phase1_complete and not profile.get("_doc_offer_shown") and not profile.get("_transition_shown"):
            _it = profile.get("income_type", "")
            if _it in ("w2_employee", "multiple_w2", "w2_plus_side"):
                profile["_doc_offer_shown"] = True
                session = await chat_engine.update_session(request.session_id, {"profile": profile})
                return ChatResponse(
                    session_id=request.session_id,
                    response="Want to speed things up? Upload your W-2 and I'll extract your income, withholding, and other details automatically.",
                    response_type="document_offer",
                    conversation_mode="guided",
                    profile_completeness=0.12,
                    quick_actions=[
                        {"label": "Upload my W-2", "value": "upload_w2"},
                        {"label": "Upload 1099", "value": "upload_1099"},
                        {"label": "I'll enter manually", "value": "skip_upload"},
                    ],
                    metadata={"_source": "document_offer"},
                )
            elif _it in ("self_employed", "business_owner", "gig_worker"):
                profile["_doc_offer_shown"] = True
                session = await chat_engine.update_session(request.session_id, {"profile": profile})
                return ChatResponse(
                    session_id=request.session_id,
                    response="Want to upload your 1099-NEC, 1099-K, or other tax documents? I can extract the details automatically.",
                    response_type="document_offer",
                    conversation_mode="guided",
                    profile_completeness=0.12,
                    quick_actions=[
                        {"label": "Upload documents", "value": "upload_1099"},
                        {"label": "I'll enter manually", "value": "skip_upload"},
                    ],
                    metadata={"_source": "document_offer"},
                )
            else:
                profile["_doc_offer_shown"] = True  # Skip offer for retired/investor/military

        # ── HYBRID FLOW: Check if Phase 1 just completed → show transition ──
        _phase1_complete = all([
            profile.get("filing_status"),
            profile.get("total_income"),
            profile.get("state"),
            profile.get("dependents") is not None,
            profile.get("income_type"),
        ])
        if _phase1_complete and not profile.get("_transition_shown"):
            profile["_transition_shown"] = True
            session = await chat_engine.update_session(request.session_id, {"profile": profile})
            return ChatResponse(
                session_id=request.session_id,
                response="Great foundation! Now I need the details that'll save you the most money. Choose how you'd like to continue:",
                response_type="transition",
                show_transition=True,
                conversation_mode="guided",
                profile_summary={
                    "filing_status": profile["filing_status"],
                    "total_income": profile["total_income"],
                    "state": profile["state"],
                    "dependents": profile.get("dependents", 0),
                    "income_type": profile["income_type"],
                },
                profile_completeness=0.15,
                quick_actions=[
                    {"label": "Tell me everything", "value": "mode_freeform"},
                    {"label": "Guide me step by step", "value": "mode_guided"},
                ],
                metadata={"_source": "transition"},
            )

        # ── HYBRID FLOW: Free-form mode handler ─────────────────────────
        if profile.get("_conversation_mode") == "freeform" and not _quick_action_handled:
            # User just picked freeform — show the intake screen
            if not profile.get("_freeform_submitted"):
                return ChatResponse(
                    session_id=request.session_id,
                    response="Tell me about your tax situation. Include anything you think is relevant — income sources, deductions, life changes, investments, retirement accounts, anything unusual.",
                    response_type="freeform_intake",
                    conversation_mode="freeform",
                    quick_actions=[
                        {"label": "Switch to guided mode", "value": "mode_guided"},
                    ],
                    metadata={"_source": "freeform_intake"},
                )

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

            # ── Topic grouping for guided mode ───────────────────────────
            _topic_name, _topic_num = _get_topic_for_question(next_q)

            # ── Proactive advice (Feature 3) ─────────────────────────────
            _advice = _get_proactive_advice(profile, updates) if updates else ""
            if _advice:
                ack = ack + _advice + "\n\n"

            # ── Live tax estimate (Feature 1) ────────────────────────────
            _estimate = _quick_tax_estimate(profile)
            _live_amount = _estimate["amount"] if _estimate["confidence"] != "none" else None
            _live_confidence = _estimate["confidence"]
            _live_label = _estimate["label"]

            # ── Progress confidence (Feature 9) ──────────────────────────
            _completeness = chat_engine.calculate_profile_completeness(profile)
            if _completeness < 0.3:
                _progress_msg = f"Profile {int(_completeness*100)}% complete — estimate will improve as we continue."
            elif _completeness < 0.6:
                _progress_msg = f"We're {int(_completeness*100)}% complete — estimate getting reliable."
            elif _completeness < 0.9:
                _progress_msg = f"Almost there — {int(_completeness*100)}% complete."
            else:
                _progress_msg = "Profile complete — high confidence in calculation."

            return ChatResponse(
                session_id=request.session_id,
                response=ack + next_q,
                response_type="question",
                conversation_mode=profile.get("_conversation_mode", "guided"),
                multi_select=_is_multi_select_question(next_q),
                topic_name=_topic_name,
                topic_number=_topic_num,
                topic_total=6,
                profile_completeness=_completeness,
                lead_score=chat_engine.calculate_lead_score(profile),
                complexity=chat_engine.determine_complexity(profile),
                quick_actions=next_actions,
                live_tax_estimate=_live_amount,
                live_estimate_confidence=_live_confidence,
                live_estimate_label=_live_label,
                completion_hint=_progress_msg,
                metadata={"_source": "template"},
            )
        else:
            # All questions answered — show confirmation before calculating
            if not profile.get("_confirmed_profile"):
                _summary = _build_profile_summary(profile)
                return ChatResponse(
                    session_id=request.session_id,
                    response="Here's your complete tax profile. Anything to add or change before I run the numbers?",
                    response_type="confirmation",
                    show_confirmation=True,
                    conversation_mode="confirmation",
                    full_profile_summary=_summary,
                    profile_completeness=1.0,
                    quick_actions=[
                        {"label": "Looks right — run the numbers!", "value": "confirm_and_calculate"},
                        {"label": "I need to change something", "value": "edit_profile"},
                    ],
                    metadata={"_source": "confirmation"},
                )
            # else: confirmed — fall through to calculation below

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
            ai_updates = await asyncio.wait_for(
                chat_engine._ai_extract_profile_data(msg_original, session),
                timeout=5.0,
            )
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

    # ── MULTI-FIELD EXTRACTION ACKNOWLEDGMENT (Feature 6) ───────────────
    # When user provides multiple pieces of info in one message, acknowledge all
    multi_field_ack = ""
    if extracted_fields and len(extracted_fields) > 1 and not correction_made:
        _field_labels = {
            "filing_status": "filing status", "total_income": "income",
            "state": "state", "dependents": "dependents", "income_type": "income type",
            "business_income": "business income", "investment_income": "investment income",
            "rental_income": "rental income", "mortgage_interest": "mortgage interest",
            "property_taxes": "property taxes", "charitable_donations": "charitable donations",
            "retirement_401k": "401(k) contributions", "retirement_ira": "IRA contributions",
            "hsa_contributions": "HSA contributions", "childcare_costs": "childcare costs",
            "spouse_income": "spouse income", "age": "age",
            "is_self_employed": "self-employment", "has_rental_income": "rental income",
            "has_investment_income": "investments", "has_mortgage": "mortgage",
            "has_charitable": "charitable donations",
        }
        _acknowledged = []
        for f in extracted_fields[:5]:  # Cap at 5 to avoid overwhelming
            if f in _field_labels:
                val = extracted.get(f)
                if isinstance(val, (int, float)) and val > 0:
                    _acknowledged.append(f"{_field_labels[f]} (${val:,.0f})")
                elif val and not str(val).startswith("_"):
                    _acknowledged.append(_field_labels[f])
        if len(_acknowledged) >= 2:
            multi_field_ack = "I captured: " + ", ".join(_acknowledged) + ". "

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
                question=msg_original,
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

    # ── HYBRID FLOW: Transition check for NON-quick-action path ────────
    # This catches the case where frontend sends "Run Full Analysis" with
    # a complete Phase 1 profile — we need to show transition before Phase 2
    _p1_done = all([profile.get("filing_status"), profile.get("total_income"),
                    profile.get("state"), profile.get("dependents") is not None,
                    profile.get("income_type") or profile.get("is_self_employed")])
    if _p1_done and not profile.get("_transition_shown"):
        profile["_transition_shown"] = True
        session = await chat_engine.update_session(request.session_id, {"profile": profile})
        return ChatResponse(
            session_id=request.session_id,
            response="Great foundation! Now I need the details that'll save you the most money. Choose how you'd like to continue:",
            response_type="transition",
            show_transition=True,
            conversation_mode="guided",
            profile_summary={
                "filing_status": profile.get("filing_status"),
                "total_income": profile.get("total_income"),
                "state": profile.get("state"),
                "dependents": profile.get("dependents", 0),
                "income_type": profile.get("income_type"),
            },
            profile_completeness=0.15,
            quick_actions=[
                {"label": "Tell me everything", "value": "mode_freeform"},
                {"label": "Guide me step by step", "value": "mode_guided"},
            ],
            metadata={"_source": "transition"},
        )

    # Check if there are still deep-dive questions to ask before calculating
    has_basics = profile.get("total_income") is not None and profile.get("filing_status") and profile.get("state")
    next_deep_q, next_deep_actions = _get_dynamic_next_question(profile, session=session)

    # If basics are done but deep-dive questions remain, ask them first
    if has_basics and next_deep_q:
        # Include a "Skip to Results" option so user isn't trapped
        if next_deep_actions and not any(a.get("value") == "skip_deep_dive" for a in next_deep_actions):
            next_deep_actions.append({"label": "Skip to Results", "value": "skip_deep_dive"})

        # Compute running estimate to show progress
        try:
            running_calc = await chat_engine.get_tax_calculation(profile)
            if running_calc and running_calc.total_tax > 0:
                refund_or_owed = running_calc.refund_or_owed
                if running_calc.is_refund:
                    estimate_hint = f"\n\n\U0001f4a1 **Running estimate: ${abs(refund_or_owed):,.0f} refund** (updates as you answer more questions)"
                else:
                    estimate_hint = f"\n\n\U0001f4a1 **Running estimate: ${abs(refund_or_owed):,.0f} owed** (updates as you answer more questions)"
                next_deep_q = estimate_hint + "\n\n" + next_deep_q
        except Exception:
            pass  # Don't let estimate failure block the question

        # Use contextual follow-up if available (from topic detection)
        contextual = session.get("_contextual_followup")
        _ack_prefix = multi_field_ack or correction_prefix
        if contextual:
            response_text = f"{_ack_prefix}{contextual}"
            session.pop("_contextual_followup", None)
        else:
            response_text = f"{_ack_prefix}{next_deep_q}"

        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            response_type="question",
            multi_select=_is_multi_select_question(next_deep_q),
            profile_completeness=completeness,
            lead_score=lead_score,
            complexity=complexity,
            quick_actions=next_deep_actions,
            metadata={"_source": "template"},
        )

    # If we have enough data, calculate taxes
    if has_basics:
        tax_calculation = await chat_engine.get_tax_calculation(profile)

        # Get strategies (with timeout to prevent hangs when AI is unavailable)
        try:
            strategies = await asyncio.wait_for(
                chat_engine.get_tax_strategies(profile, tax_calculation),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Strategy generation timed out — using basic strategies")
            strategies = []

        # Enrich top strategies with AI in background (non-blocking)
        if AI_CHAT_ENABLED and complexity != "simple" and strategies:
            async def _enrich_strategies_background(sid, strats, prof):
                """Background task: enrich strategies with AI reasoning + narratives."""
                try:
                    import time as _time
                    _ai_start = _time.monotonic()

                    # Reasoning enrichment
                    try:
                        from services.ai.tax_reasoning_service import get_tax_reasoning_service
                        reasoning_svc = get_tax_reasoning_service()
                        reasoning_tasks = [
                            reasoning_svc.analyze(
                                problem=f"Evaluate strategy: {s.title} with savings of ${s.estimated_savings:,.0f}",
                                context=_summarize_profile(prof),
                            ) for s in strats[:2]
                        ]
                        reasoning_results = await asyncio.wait_for(
                            asyncio.gather(*reasoning_tasks, return_exceptions=True),
                            timeout=10.0,
                        )
                        for s, result in zip(strats[:2], reasoning_results):
                            if isinstance(result, Exception):
                                continue
                            if result and result.confidence:
                                s.confidence = "high" if result.confidence > 0.8 else "medium" if result.confidence > 0.5 else "low"
                    except Exception:
                        pass

                    # Narrative enrichment
                    try:
                        from advisory.ai_narrative_generator import get_narrative_generator, ClientProfile as NarrClientProfile
                        narrator = get_narrative_generator()
                        client_profile = NarrClientProfile(
                            name=prof.get("name", "Client"),
                            occupation=prof.get("occupation", ""),
                            financial_goals=["Minimize tax liability"],
                            primary_concern="Tax optimization",
                        )
                        narr_tasks = [
                            narrator.generate_recommendation_explanation(
                                {"title": s.title, "savings": s.estimated_savings, "priority": s.priority, "explanation": s.detailed_explanation or ""},
                                client_profile,
                            ) for s in strats[:3]
                        ]
                        narr_results = await asyncio.wait_for(
                            asyncio.gather(*narr_tasks, return_exceptions=True),
                            timeout=10.0,
                        )
                        for s, narrative in zip(strats[:3], narr_results):
                            if isinstance(narrative, Exception):
                                continue
                            if narrative and narrative.content:
                                s.detailed_explanation = narrative.content[:800]
                    except Exception:
                        pass

                    # Save enriched strategies back to session
                    try:
                        session = chat_engine.sessions.get(sid)
                        if session:
                            session["strategies"] = strats
                            await chat_engine._save_session_to_db(sid, session)
                    except Exception:
                        pass

                    _ai_elapsed = (_time.monotonic() - _ai_start) * 1000
                    logger.info(f"Background AI enrichment completed in {_ai_elapsed:.0f}ms for session {sid}")
                except Exception as e:
                    logger.warning(f"Background AI enrichment failed: {e}")

            # Fire and forget — response returns immediately
            asyncio.create_task(_enrich_strategies_background(request.session_id, strategies, profile))

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

        # Run safety checks (non-blocking — skip if unavailable)
        if tax_calculation:
            try:
                from web.advisor.safety_checks import run_safety_checks as _run_safety_checks_fn
                safety_data = await asyncio.wait_for(
                    _run_safety_checks_fn(request.session_id, profile, tax_calculation),
                    timeout=5.0,
                )
            except (ImportError, NameError):
                safety_data = None  # Safety check module not available
            except asyncio.TimeoutError:
                logger.warning("Safety checks timed out — will show on next response")
                safety_data = None
            except Exception:
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

        # ================================================================
        # UNIFIED ADVISORY REPORT — One clean, premium output
        # ================================================================

        refund_owed_amount = abs(tax_calculation.refund_or_owed)
        se_tax = tax_calculation.self_employment_tax or 0
        withholding = profile.get("federal_withholding", 0) or 0
        est_payments = profile.get("estimated_payments", 0) or 0
        total_payments = withholding + est_payments

        if tax_calculation.is_refund:
            headline = f"## Estimated Refund: ${refund_owed_amount:,.0f}"
        else:
            headline = f"## Estimated Tax Owed: ${refund_owed_amount:,.0f}"

        # Tax breakdown
        breakdown = f"| Federal Income Tax | ${tax_calculation.federal_tax:,.0f} |"
        if tax_calculation.state_tax > 0:
            breakdown += f"\n| State Tax ({profile.get('state', '')}) | ${tax_calculation.state_tax:,.0f} |"
        if se_tax > 0:
            breakdown += f"\n| Self-Employment Tax | ${se_tax:,.0f} |"
        breakdown += f"\n| **Total Tax** | **${tax_calculation.total_tax:,.0f}** |"
        if total_payments > 0:
            breakdown += f"\n| Withholding & Payments | -${total_payments:,.0f} |"
            label = "**Refund**" if tax_calculation.is_refund else "**Balance Due**"
            breakdown += f"\n| {label} | **${refund_owed_amount:,.0f}** |"

        # Credits
        credits_info = ""
        ctc = tax_calculation.child_tax_credit or 0
        if ctc > 0:
            credits_info += f"\nChild Tax Credit: ${ctc:,.0f}"
        if tax_calculation.total_tax < 0:
            credits_info += "\nEarned Income Credit applied"

        # Top recommendation
        top_rec = ""
        if strategies:
            s = strategies[0]
            top_rec = f"\n\n---\n\n### Top Recommendation: {s.title}\n\n**Potential savings: ${s.estimated_savings:,.0f}**\n\n{s.summary or s.detailed_explanation or ''}\n\n*{s.irs_reference or ''}*"
            if len(strategies) > 1:
                other_savings = sum(st.estimated_savings for st in strategies[1:])
                top_rec += f"\n\n*{len(strategies) - 1} additional strategies identified (${other_savings:,.0f} more in potential savings)*"

        response_text = f"""{correction_prefix}{headline}
*{filing_display} | {profile.get('state', '')} | Tax Year 2025*

| | |
|---|---:|
{breakdown}

Effective Rate: **{tax_calculation.effective_rate:.1f}%** | Marginal Rate: **{tax_calculation.marginal_rate}%**

Deduction: **{(tax_calculation.deduction_type or 'standard').title()}** (${tax_calculation.deductions or 0:,.0f}){credits_info}{top_rec}"""

        quick_actions = [
            {"label": "Generate Full Report", "value": "generate_report"},
            {"label": "Ask a question", "value": "ask_question"},
            {"label": "Update my info", "value": "edit_profile"},
        ]

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
                growth_factor = 1.03 ** (year - 2025)  # 3% compound annual growth
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
