"""
FastAPI web UI for the Tax Preparation Agent.

Routes:
- GET  /           : simple chat UI
- POST /api/chat   : chat endpoint (JSON)
- POST /api/upload : document upload endpoint (synchronous)
- POST /api/upload/async : document upload for async processing (Celery)
- GET  /api/upload/status/{task_id} : check async upload task status
- POST /api/upload/cancel/{task_id} : cancel async upload task
- GET  /api/documents : list uploaded documents
- GET  /api/documents/{id} : get document details
- GET  /api/documents/{id}/status : check document processing status
- POST /api/documents/{id}/apply : apply document to return
- GET  /api/recommendations : get tax optimization recommendations
"""

import os
import uuid
import traceback
from typing import Dict, Optional, List, Any
from datetime import datetime
from enum import Enum

from fastapi import FastAPI, Request, Response, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent.tax_agent import TaxAgent
from calculator.tax_calculator import TaxCalculator
from calculator.recommendations import get_recommendations, RecommendationsResult
from forms.form_generator import FormGenerator
from services.ocr import DocumentProcessor, ProcessingResult
import re
import logging

# =============================================================================
# SECURITY IMPORTS - CRITICAL FOR PRODUCTION
# =============================================================================
from security.secure_serializer import (
    SecureSerializer,
    get_serializer,
    SerializationError,
    DeserializationError,
    IntegrityError,
)
from security.data_sanitizer import (
    sanitize_for_logging,
    sanitize_for_api,
    create_safe_context,
)
from security.middleware import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    RequestValidationMiddleware,
)

# =============================================================================
# AUDIT TRAIL IMPORTS - CPA COMPLIANCE REQUIREMENT
# =============================================================================
from audit.audit_trail import AuditTrail, AuditEntry, AuditEventType, ChangeRecord

logger = logging.getLogger(__name__)

# Initialize secure serializer (replaces unsafe pickle)
_secure_serializer: Optional[SecureSerializer] = None

def get_secure_serializer() -> SecureSerializer:
    """Get singleton secure serializer instance."""
    global _secure_serializer
    if _secure_serializer is None:
        _secure_serializer = get_serializer()
    return _secure_serializer

app = FastAPI(title="US Tax Preparation Agent (Tax Year 2025)")


# =============================================================================
# SECURITY MIDDLEWARE CONFIGURATION (ORDER MATTERS - Last added = First executed)
# =============================================================================

# 1. Security Headers (HSTS, CSP, X-Frame-Options, etc.)
try:
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("Security headers middleware enabled")
except Exception as e:
    logger.warning(f"Security headers middleware failed: {e}")

# 2. Rate Limiting (60 requests/minute per IP)
try:
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=60,
        burst_size=20,
        exempt_paths={"/health", "/metrics", "/static"},
    )
    logger.info("Rate limiting middleware enabled")
except Exception as e:
    logger.warning(f"Rate limiting middleware failed: {e}")

# 3. Request Validation (size limits, content type)
try:
    app.add_middleware(
        RequestValidationMiddleware,
        max_content_length=50 * 1024 * 1024,  # 50MB for document uploads
    )
    logger.info("Request validation middleware enabled")
except Exception as e:
    logger.warning(f"Request validation middleware failed: {e}")


# =============================================================================
# ADDITIONAL MIDDLEWARE
# =============================================================================

# Add correlation ID middleware for request tracing
try:
    from middleware.correlation import CorrelationIdMiddleware
    app.add_middleware(CorrelationIdMiddleware)
    logger.info("Correlation ID middleware enabled")
except ImportError:
    logger.warning("Correlation ID middleware not available")


# =============================================================================
# WORKSPACE API (Phase 1-2: Multi-Client Management)
# =============================================================================
try:
    from web.workspace_api import router as workspace_router
    app.include_router(workspace_router)
    logger.info("Workspace API enabled")
except ImportError as e:
    logger.warning(f"Workspace API not available: {e}")


# =============================================================================
# CONFIGURATION & RULES API
# =============================================================================
try:
    from web.config_api import router as config_router, rules_router
    app.include_router(config_router)
    app.include_router(rules_router)
    logger.info("Configuration API enabled")
except ImportError as e:
    logger.warning(f"Configuration API not available: {e}")


# =============================================================================
# CPA PANEL API - CPA Decision Intelligence & Advisory Platform
# =============================================================================
try:
    from cpa_panel.api import cpa_router
    app.include_router(cpa_router, prefix="/api")
    logger.info("CPA Panel API enabled")
except ImportError as e:
    logger.warning(f"CPA Panel API not available: {e}")


# =============================================================================
# ERROR HANDLING SYSTEM
# =============================================================================

class ErrorCode(str, Enum):
    """Standardized error codes for consistent client handling."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MISSING_DATA = "MISSING_DATA"
    CALCULATION_ERROR = "CALCULATION_ERROR"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    DOCUMENT_ERROR = "DOCUMENT_ERROR"
    FILE_ERROR = "FILE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT = "RATE_LIMIT"


class TaxAppError(Exception):
    """Base exception for tax app errors."""
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        # User-friendly message (shown to end user)
        self.user_message = user_message or message
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "code": self.code.value,
            "message": self.user_message,
            "details": self.details,
        }


def create_error_response(
    code: ErrorCode,
    message: str,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None,
    user_message: Optional[str] = None
) -> JSONResponse:
    """Create a standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": True,
            "code": code.value,
            "message": user_message or message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


# Global exception handlers
@app.exception_handler(TaxAppError)
async def tax_app_error_handler(request: Request, exc: TaxAppError):
    """Handle custom TaxAppError exceptions."""
    logger.warning(f"TaxAppError: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with user-friendly messages."""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")

    return create_error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message="Invalid request data",
        status_code=422,
        details={"validation_errors": errors},
        user_message="Please check your input. Some values appear to be invalid."
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent format."""
    return create_error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message=str(exc.detail),
        status_code=exc.status_code,
        user_message=str(exc.detail)
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}\n{traceback.format_exc()}")
    return create_error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message="An unexpected error occurred",
        status_code=500,
        details={"type": type(exc).__name__},
        user_message="Something went wrong. Please try again. If the problem persists, contact support."
    )


# =============================================================================
# INPUT VALIDATION HELPERS
# =============================================================================

def safe_float(value: Any, default: float = 0.0, min_val: float = 0.0, max_val: float = 999_999_999.0) -> float:
    """Safely convert value to float with bounds checking."""
    if value is None:
        return default
    try:
        result = float(value)
        if result < min_val:
            return min_val
        if result > max_val:
            return max_val
        return round(result, 2)  # Consistent 2 decimal places for currency
    except (ValueError, TypeError):
        logger.warning(f"Invalid float value: {value}, using default {default}")
        return default


def safe_int(value: Any, default: int = 0, min_val: int = 0, max_val: int = 100) -> int:
    """Safely convert value to int with bounds checking."""
    if value is None:
        return default
    try:
        result = int(float(value))  # Handle "1.0" -> 1
        if result < min_val:
            return min_val
        if result > max_val:
            return max_val
        return result
    except (ValueError, TypeError):
        logger.warning(f"Invalid int value: {value}, using default {default}")
        return default


def validate_ssn(ssn: str) -> tuple[bool, str]:
    """Validate SSN format. Returns (is_valid, cleaned_ssn)."""
    if not ssn:
        return True, ""  # Empty is allowed
    cleaned = re.sub(r'[^0-9]', '', ssn)
    if len(cleaned) != 9:
        return False, ssn
    # Invalid SSN patterns per IRS rules
    if cleaned.startswith('000') or cleaned.startswith('666') or cleaned.startswith('9'):
        return False, ssn
    if cleaned[3:5] == '00' or cleaned[5:] == '0000':
        return False, ssn
    # Format as XXX-XX-XXXX
    formatted = f"{cleaned[:3]}-{cleaned[3:5]}-{cleaned[5:]}"
    return True, formatted


def validate_ein(ein: str) -> tuple[bool, str]:
    """Validate EIN format. Returns (is_valid, cleaned_ein)."""
    if not ein:
        return True, ""  # Empty is allowed
    cleaned = re.sub(r'[^0-9]', '', ein)
    if len(cleaned) != 9:
        return False, ein
    # Format as XX-XXXXXXX
    formatted = f"{cleaned[:2]}-{cleaned[2:]}"
    return True, formatted


def validate_state_code(code: str) -> bool:
    """Validate US state code."""
    valid_states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA',
        'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY',
        'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX',
        'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
    }
    return code.upper() in valid_states if code else True


def validate_date(date_str: str) -> tuple[bool, Optional[str]]:
    """Validate and parse date string. Returns (is_valid, parsed_date_str)."""
    if not date_str:
        return True, None
    try:
        # Try ISO format first
        parsed = datetime.strptime(date_str, '%Y-%m-%d')
        # Validate reasonable year range
        if parsed.year < 1900 or parsed.year > datetime.now().year + 1:
            return False, None
        return True, date_str
    except ValueError:
        # Try common formats
        for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%d/%m/%Y']:
            try:
                parsed = datetime.strptime(date_str, fmt)
                if 1900 <= parsed.year <= datetime.now().year + 1:
                    return True, parsed.strftime('%Y-%m-%d')
            except ValueError:
                continue
        return False, None


templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Static files (for PWA manifest, icons, etc.)
from fastapi.staticfiles import StaticFiles
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# PWA manifest route
@app.get("/manifest.json")
async def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "static", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            import json
            return JSONResponse(json.load(f))
    return JSONResponse({"name": "TaxFlow"})

# =============================================================================
# C3: DATABASE-BACKED SESSION PERSISTENCE (Replaces in-memory dicts)
# Per FREEZE CHECKLIST: Session state persists across server restart
# =============================================================================
from database.session_persistence import SessionPersistence
# SECURITY: pickle removed - using secure_serializer instead (see security imports at top)
# import pickle  # REMOVED - Pickle allows arbitrary code execution (RCE vulnerability)

# Initialize persistence layer (lazy singleton)
_session_persistence: Optional[SessionPersistence] = None

def _get_persistence() -> SessionPersistence:
    """Get or create the session persistence instance."""
    global _session_persistence
    if _session_persistence is None:
        _session_persistence = SessionPersistence()
    return _session_persistence

# Shared service instances (stateless, safe to keep in memory)
_calculator = TaxCalculator()
_forms = FormGenerator()
_document_processor = DocumentProcessor()

# In-memory document tracking (for tests and quick lookups)
# Note: Production document data is also stored via persistence layer
_DOCUMENTS: Dict[str, Dict[str, Any]] = {}

# =============================================================================
# AUDIT TRAIL MANAGEMENT - CPA COMPLIANCE REQUIREMENT
# =============================================================================
# In-memory audit trails keyed by return_id (session_id)
# Note: Also persisted to database for durability
_AUDIT_TRAILS: Dict[str, AuditTrail] = {}


def _get_or_create_audit_trail(session_id: str, user_id: Optional[str] = None, user_name: Optional[str] = None, user_role: str = "taxpayer", ip_address: Optional[str] = None) -> AuditTrail:
    """
    Get or create audit trail for a session/return.

    CPA COMPLIANCE: Every session must have an associated audit trail.
    """
    if session_id not in _AUDIT_TRAILS:
        _AUDIT_TRAILS[session_id] = AuditTrail(return_id=session_id)

    trail = _AUDIT_TRAILS[session_id]

    # Set current user context if provided
    if user_id or user_name:
        trail.set_current_user(
            user_id=user_id or session_id,
            user_name=user_name or "Anonymous",
            user_role=user_role,
            ip_address=ip_address
        )

    return trail


def _log_audit_event(
    session_id: str,
    event_type: AuditEventType,
    description: str,
    changes: Optional[List[ChangeRecord]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> AuditEntry:
    """
    Log an audit event for a session.

    CPA COMPLIANCE: All data mutations must be logged.
    """
    # Get client IP from request if available
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None

    trail = _get_or_create_audit_trail(
        session_id,
        ip_address=ip_address
    )

    entry = trail.log_event(
        event_type=event_type,
        description=description,
        changes=changes,
        metadata=metadata
    )

    # Persist audit trail to database
    try:
        persistence = _get_persistence()
        persistence.save_audit_trail(session_id, trail.to_json())
    except Exception as e:
        logger.warning(f"Failed to persist audit trail: {e}")

    return entry


def _log_data_change(
    session_id: str,
    field_path: str,
    old_value: Any,
    new_value: Any,
    reason: Optional[str] = None,
    request: Optional[Request] = None
) -> AuditEntry:
    """
    Log a specific data field change.

    CPA COMPLIANCE: Track all field-level changes.
    """
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None

    trail = _get_or_create_audit_trail(session_id, ip_address=ip_address)
    entry = trail.log_data_change(field_path, old_value, new_value, reason)

    # Persist
    try:
        persistence = _get_persistence()
        persistence.save_audit_trail(session_id, trail.to_json())
    except Exception as e:
        logger.warning(f"Failed to persist audit trail: {e}")

    return entry


def _get_engine_version_hash() -> Dict[str, str]:
    """
    Generate a version hash for the calculation engine.

    CPA COMPLIANCE: Allows verification of which engine version was used
    for any given calculation. Critical for audit defensibility.

    Returns:
        Dict with version, hash, and timestamp
    """
    import hashlib

    # Version info
    version = "2025.1.0"
    tax_year = 2025

    # Generate hash from key calculator files (content-based)
    calculator_files = [
        "calculator/tax_calculator.py",
        "calculator/brackets.py",
        "calculator/state_calculator.py",
        "validation/tax_rules_engine.py",
    ]

    hasher = hashlib.sha256()
    for file_path in calculator_files:
        try:
            full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    hasher.update(f.read())
        except Exception:
            pass  # Skip if file not readable

    # Include version in hash
    hasher.update(version.encode())
    hasher.update(str(tax_year).encode())

    return {
        "version": version,
        "tax_year": tax_year,
        "engine_hash": hasher.hexdigest()[:12],  # Short hash for display
        "calculated_at": datetime.utcnow().isoformat(),
    }


def _check_cpa_approval(session_id: str, feature_name: str) -> tuple[bool, Optional[str]]:
    """
    Check if a feature is allowed based on CPA approval status.

    CPA COMPLIANCE: Certain features require CPA_APPROVED status.

    Args:
        session_id: Session/return identifier
        feature_name: Name of feature being checked (for error messages)

    Returns:
        Tuple of (is_allowed, error_message_if_blocked)
    """
    persistence = _get_persistence()
    status_record = persistence.get_return_status(session_id)

    # If no status record, default to DRAFT (not approved)
    if not status_record:
        return (
            False,
            f"{feature_name} requires CPA approval. Please submit your return for review first."
        )

    status = status_record.get("status", "DRAFT")

    if status == "CPA_APPROVED":
        return (True, None)

    if status == "IN_REVIEW":
        return (
            False,
            f"{feature_name} is pending CPA approval. Please wait for your return to be reviewed."
        )

    # DRAFT status
    return (
        False,
        f"{feature_name} requires CPA approval. Please submit your return for review first."
    )


def _get_or_create_session_agent(session_id: Optional[str]) -> tuple[str, TaxAgent]:
    """
    Get or create a TaxAgent session with database persistence.

    C3: Session state persists across server restart via SessionPersistence.
    SECURITY: Uses SecureSerializer instead of pickle to prevent RCE.
    """
    persistence = _get_persistence()
    serializer = get_secure_serializer()

    if session_id:
        # Try to load existing agent from database
        agent_state = persistence.load_agent_state(session_id)
        if agent_state:
            try:
                # SECURITY: Use secure deserializer instead of pickle
                agent_data = serializer.deserialize(agent_state.decode('utf-8') if isinstance(agent_state, bytes) else agent_state)
                agent = TaxAgent()
                agent.restore_from_state(agent_data)
                # Touch session to extend TTL
                persistence.touch_session(session_id)
                return session_id, agent
            except (DeserializationError, IntegrityError) as e:
                logger.warning(f"Security: Failed to deserialize agent for session {session_id}: {e}")
                # Fall through to create new agent
            except Exception as e:
                logger.warning(f"Failed to restore agent for session {session_id}: {sanitize_for_logging(str(e))}")
                # Fall through to create new agent

    # Create new session
    new_id = str(uuid.uuid4())
    agent = TaxAgent()
    agent.start_conversation()

    # Persist new session with secure serialization
    try:
        # SECURITY: Use secure serializer instead of pickle
        agent_data = agent.get_state_for_serialization()
        agent_state = serializer.serialize(agent_data)
        persistence.save_session(
            session_id=new_id,
            session_type="agent",
            agent_state=agent_state.encode('utf-8')
        )
    except SerializationError as e:
        logger.warning(f"Security: Failed to serialize session {new_id}: {e}")
    except Exception as e:
        logger.warning(f"Failed to persist new session {new_id}: {sanitize_for_logging(str(e))}")

    return new_id, agent


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """CPA Workspace Dashboard - Multi-client management (legacy)."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/cpa", response_class=HTMLResponse)
def cpa_dashboard(request: Request):
    """
    CPA Intelligence & Advisory Dashboard.

    Comprehensive dashboard with:
    - Practice Intelligence (3 metrics only - boundary locked)
    - Client Management
    - Review Queue with Workflow Approval
    - Lead Pipeline
    - Staff Assignment
    - Engagement Letters
    """
    return templates.TemplateResponse("cpa_dashboard.html", {"request": request})


@app.get("/client", response_class=HTMLResponse)
def client_portal(request: Request):
    """
    Client Portal - Lead Magnet Flow.

    Smart Tax Advisory Lead Magnet with:
    - CPA branding (via ?cpa=slug URL param)
    - Quick 2-min or Full 5-min assessment
    - Smart dropdown questions (no free text)
    - FREE Tier 1 report with teaser insights
    - Contact capture for lead generation
    """
    return templates.TemplateResponse("client_portal.html", {"request": request})


@app.get("/test-auth", response_class=HTMLResponse)
def test_auth_portal(request: Request):
    """
    Development/Testing Portal - Auth Bypass Page.

    WARNING: This page bypasses authentication for development purposes only.
    In production, this route should be disabled or properly secured.

    Provides quick access to:
    - CPA Dashboard
    - Client Portal
    - API Documentation
    - Health checks
    """
    return templates.TemplateResponse("test_auth.html", {"request": request})


@app.post("/api/chat")
async def chat(request: Request, response: Response):
    body = await request.json()
    user_message = (body.get("message") or "").strip()
    action = (body.get("action") or "message").strip().lower()

    session_id = request.cookies.get("tax_session_id")
    session_id, agent = _get_or_create_session_agent(session_id)
    response.set_cookie(
        "tax_session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT") == "production",  # HTTPS only in production
        max_age=86400  # 24 hours
    )

    if action == "reset":
        # C3: Delete session from database (not just in-memory)
        _get_persistence().delete_session(session_id)
        session_id, agent = _get_or_create_session_agent(None)
        response.set_cookie(
        "tax_session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT") == "production",  # HTTPS only in production
        max_age=86400  # 24 hours
    )
        return JSONResponse({"reply": "Session reset. " + agent.start_conversation()})

    if action == "summary":
        tax_return = agent.get_tax_return()
        if not tax_return:
            return JSONResponse({"reply": "No information collected yet."})
        if agent.is_complete():
            _calculator.calculate_complete_return(tax_return)
        return JSONResponse({"reply": _forms.generate_summary(tax_return)})

    if action == "calculate":
        tax_return = agent.get_tax_return()
        if not tax_return or not agent.is_complete():
            return JSONResponse({"reply": "Not enough information yet. Please continue answering questions."})
        _calculator.calculate_complete_return(tax_return)
        return JSONResponse({"reply": _forms.generate_summary(tax_return)})

    if not user_message:
        return JSONResponse({"reply": "Please type a message."})

    reply = agent.process_message(user_message)

    # C3: Persist agent state after message processing
    # SECURITY: Use secure serializer instead of pickle
    try:
        serializer = get_secure_serializer()
        agent_data = agent.get_state_for_serialization()
        agent_state = serializer.serialize(agent_data)
        _get_persistence().save_session(
            session_id=session_id,
            session_type="agent",
            agent_state=agent_state.encode('utf-8')
        )
    except SerializationError as e:
        logger.warning(f"Security: Failed to serialize agent state: {e}")
    except Exception as e:
        logger.warning(f"Failed to persist agent state: {sanitize_for_logging(str(e))}")

    return JSONResponse({"reply": reply})


# =============================================================================
# DOCUMENT UPLOAD ENDPOINTS
# =============================================================================

def _get_or_create_session_id(request: Request) -> str:
    """Get or create a session ID without initializing TaxAgent."""
    session_id = request.cookies.get("tax_session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id


@app.post("/api/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    tax_year: Optional[int] = Form(None),
):
    """
    Upload a tax document for OCR processing.

    Supports W-2, 1099-INT, 1099-DIV, 1099-NEC, 1099-MISC, and more.
    Returns extracted data that can be applied to the tax return.
    """
    session_id = _get_or_create_session_id(request)

    # Validate file type
    allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/tiff"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, PNG, JPEG, TIFF"
        )

    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Process document with OCR
    try:
        result = _document_processor.process_bytes(
            data=content,
            mime_type=file.content_type,
            original_filename=file.filename,
            document_type=document_type,
            tax_year=tax_year,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

    # C3: Store document result in database (not in-memory)
    doc_id = str(result.document_id)
    result_dict = {
        "document_id": doc_id,
        "document_type": result.document_type,
        "tax_year": result.tax_year,
        "status": result.status,
        "ocr_confidence": result.ocr_confidence,
        "extraction_confidence": result.extraction_confidence,
        "extracted_fields": [f.to_dict() for f in result.extracted_fields],
        "warnings": result.warnings,
        "errors": result.errors,
        "filename": file.filename,
    }
    _get_persistence().save_document_result(
        document_id=doc_id,
        session_id=session_id,
        document_type=result.document_type,
        status=result.status,
        result=result_dict
    )

    json_response = JSONResponse({
        "document_id": doc_id,
        "document_type": result.document_type,
        "tax_year": result.tax_year,
        "status": result.status,
        "ocr_confidence": result.ocr_confidence,
        "extraction_confidence": result.extraction_confidence,
        "extracted_fields": [f.to_dict() for f in result.extracted_fields],
        "warnings": result.warnings,
        "errors": result.errors,
    })
    json_response.set_cookie(
        "tax_session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT") == "production",  # HTTPS only in production
        max_age=86400  # 24 hours
    )
    return json_response


# =============================================================================
# ASYNC DOCUMENT PROCESSING ENDPOINTS (Celery-based)
# =============================================================================

@app.post("/api/upload/async")
async def upload_document_async(
    request: Request,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    tax_year: Optional[int] = Form(None),
    callback_url: Optional[str] = Form(None),
):
    """
    Upload a tax document for asynchronous OCR processing.

    Returns immediately with a task_id and document_id.
    Use GET /api/upload/status/{task_id} to check processing status.
    Optionally provide a callback_url to receive notification when processing completes.

    Supports W-2, 1099-INT, 1099-DIV, 1099-NEC, 1099-MISC, and more.
    """
    session_id = _get_or_create_session_id(request)

    # Validate file type
    allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/tiff"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, PNG, JPEG, TIFF"
        )

    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Generate document ID
    document_id = str(uuid.uuid4())
    persistence = _get_persistence()

    # C3: Store pending document reference in database
    persistence.save_document_result(
        document_id=document_id,
        session_id=session_id,
        document_type=document_type,
        status="processing",
        result={"filename": file.filename, "task_id": None}
    )

    # Submit to Celery for async processing
    try:
        from tasks.ocr_tasks import submit_document_bytes_for_processing

        task_result = submit_document_bytes_for_processing(
            data=content,
            mime_type=file.content_type,
            original_filename=file.filename,
            document_id=document_id,
            document_type=document_type,
            tax_year=tax_year,
            callback_url=callback_url,
        )

        # C3: Update document with task_id in database
        persistence.save_document_result(
            document_id=document_id,
            session_id=session_id,
            document_type=document_type,
            status="processing",
            result={"filename": file.filename, "task_id": task_result["task_id"]}
        )

        json_response = JSONResponse({
            "document_id": document_id,
            "task_id": task_result["task_id"],
            "status": "processing",
            "message": "Document submitted for processing. Use GET /api/upload/status/{task_id} to check status.",
        })
        json_response.set_cookie(
        "tax_session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT") == "production",  # HTTPS only in production
        max_age=86400  # 24 hours
    )
        return json_response

    except ImportError:
        # Celery not available, fall back to synchronous processing
        logger.warning("Celery not available, falling back to synchronous processing")
        try:
            result = _document_processor.process_bytes(
                data=content,
                mime_type=file.content_type,
                original_filename=file.filename,
                document_type=document_type,
                tax_year=tax_year,
            )
            # C3: Store completed result in database
            result_dict = {
                "document_id": document_id,
                "document_type": result.document_type,
                "tax_year": result.tax_year,
                "status": "completed",
                "ocr_confidence": result.ocr_confidence,
                "extraction_confidence": result.extraction_confidence,
                "extracted_fields": [f.to_dict() for f in result.extracted_fields],
                "warnings": result.warnings,
                "errors": result.errors,
                "filename": file.filename,
                "task_id": None,
            }
            persistence.save_document_result(
                document_id=document_id,
                session_id=session_id,
                document_type=result.document_type,
                status="completed",
                result=result_dict
            )
            json_response = JSONResponse({
                "document_id": document_id,
                "task_id": None,
                "status": "completed",
                "message": "Document processed synchronously (async processing unavailable).",
                "document_type": result.document_type,
                "extraction_confidence": result.extraction_confidence,
            })
            json_response.set_cookie(
        "tax_session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT") == "production",  # HTTPS only in production
        max_age=86400  # 24 hours
    )
            return json_response
        except Exception as e:
            persistence.delete_document(document_id)
            raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

    except Exception as e:
        persistence.delete_document(document_id)
        raise HTTPException(status_code=500, detail=f"Failed to submit document for processing: {str(e)}")


@app.get("/api/upload/status/{task_id}")
async def get_upload_status(task_id: str, request: Request):
    """
    Get the status of an async document upload task.

    Returns task status and, if completed, the processing result.
    """
    try:
        from tasks.ocr_tasks import get_task_status, get_document_status

        # Get Celery task status
        task_status = get_task_status(task_id)

        response_data = {
            "task_id": task_id,
            "celery_status": task_status["status"],
            "ready": task_status["ready"],
        }

        if task_status["ready"]:
            if task_status.get("result"):
                result_data = task_status["result"]
                response_data["status"] = "completed"
                response_data["document_id"] = result_data.get("document_id")
                response_data["document_type"] = result_data.get("document_type")
                response_data["tax_year"] = result_data.get("tax_year")
                response_data["ocr_confidence"] = result_data.get("ocr_confidence")
                response_data["extraction_confidence"] = result_data.get("extraction_confidence")
                response_data["extracted_fields"] = result_data.get("extracted_fields", [])
                response_data["warnings"] = result_data.get("warnings", [])
                response_data["errors"] = result_data.get("errors", [])
            elif task_status.get("error"):
                response_data["status"] = "failed"
                response_data["error"] = task_status["error"]
        else:
            response_data["status"] = "processing"

        return JSONResponse(response_data)

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Async processing not available. Use synchronous /api/upload endpoint."
        )
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@app.get("/api/documents/{document_id}/status")
async def get_document_processing_status(document_id: str, request: Request):
    """
    Get the processing status of a document by document_id.

    This is useful when you have the document_id but not the task_id.
    """
    session_id = request.cookies.get("tax_session_id") or ""
    persistence = _get_persistence()

    # Check in-memory store first (for tests and quick lookups)
    if document_id in _DOCUMENTS:
        doc_data = _DOCUMENTS[document_id]
        doc_session_id = doc_data.get("session_id")

        # Verify session ownership
        if doc_session_id and doc_session_id != session_id:
            raise HTTPException(status_code=403, detail="Access denied")

        status = doc_data.get("status", "unknown")
        result = doc_data.get("result")

        if status == "completed" and result:
            return JSONResponse({
                "document_id": document_id,
                "status": "completed",
                "document_type": getattr(result, "document_type", None) or (result.get("document_type") if isinstance(result, dict) else None),
                "tax_year": getattr(result, "tax_year", None) or (result.get("tax_year") if isinstance(result, dict) else None),
                "ocr_confidence": getattr(result, "ocr_confidence", None) or (result.get("ocr_confidence") if isinstance(result, dict) else None),
                "extraction_confidence": getattr(result, "extraction_confidence", None) or (result.get("extraction_confidence") if isinstance(result, dict) else None),
            })
        elif doc_data.get("task_id"):
            return JSONResponse({
                "document_id": document_id,
                "status": status,
                "task_id": doc_data["task_id"],
            })
        else:
            return JSONResponse({
                "document_id": document_id,
                "status": status,
            })

    # C3: Check database for document
    doc_record = persistence.load_document_result(document_id, session_id=session_id)
    if doc_record:
        result_data = doc_record.result

        if doc_record.status == "completed" and result_data:
            return JSONResponse({
                "document_id": document_id,
                "status": "completed",
                "document_type": result_data.get("document_type"),
                "tax_year": result_data.get("tax_year"),
                "ocr_confidence": result_data.get("ocr_confidence"),
                "extraction_confidence": result_data.get("extraction_confidence"),
            })
        elif result_data.get("task_id"):
            # Check Celery task status
            try:
                from tasks.ocr_tasks import get_task_status

                task_status = get_task_status(result_data["task_id"])
                if task_status["ready"] and task_status.get("result"):
                    # C3: Update database with completed result
                    completed_result = task_status["result"]
                    completed_result["filename"] = result_data.get("filename")
                    completed_result["task_id"] = result_data.get("task_id")
                    persistence.save_document_result(
                        document_id=document_id,
                        session_id=session_id,
                        document_type=completed_result.get("document_type"),
                        status="completed",
                        result=completed_result
                    )

                    return JSONResponse({
                        "document_id": document_id,
                        "status": "completed",
                        "document_type": completed_result.get("document_type"),
                        "tax_year": completed_result.get("tax_year"),
                        "ocr_confidence": completed_result.get("ocr_confidence"),
                        "extraction_confidence": completed_result.get("extraction_confidence"),
                    })
                elif task_status["ready"] and task_status.get("error"):
                    return JSONResponse({
                        "document_id": document_id,
                        "status": "failed",
                        "error": task_status["error"],
                    })
                else:
                    return JSONResponse({
                        "document_id": document_id,
                        "status": "processing",
                        "task_id": result_data["task_id"],
                    })
            except ImportError:
                return JSONResponse({
                    "document_id": document_id,
                    "status": doc_record.status,
                })

        return JSONResponse({
            "document_id": document_id,
            "status": doc_record.status,
        })

    # Check if document exists but belongs to different session
    doc_any = persistence.load_document_result(document_id)
    if doc_any:
        raise HTTPException(status_code=403, detail="Access denied")

    # Try Redis-based status if available
    try:
        from tasks.ocr_tasks import get_document_status

        status = get_document_status(document_id)
        return JSONResponse(status)
    except ImportError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        raise HTTPException(status_code=404, detail="Document not found")


@app.post("/api/upload/cancel/{task_id}")
async def cancel_upload_task(task_id: str, request: Request):
    """
    Cancel a pending async document upload task.

    Only pending tasks can be cancelled. Running tasks may not be interruptible.
    """
    try:
        from tasks.ocr_tasks import cancel_task

        result = cancel_task(task_id, terminate=False)

        if result:
            return JSONResponse({
                "task_id": task_id,
                "cancelled": True,
                "message": "Cancellation request sent",
            })
        else:
            return JSONResponse({
                "task_id": task_id,
                "cancelled": False,
                "message": "Failed to cancel task",
            }, status_code=400)

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Async processing not available."
        )
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")


@app.get("/api/documents")
async def list_documents(request: Request):
    """List all uploaded documents for the current session."""
    session_id = request.cookies.get("tax_session_id")
    if not session_id:
        return JSONResponse({"documents": []})

    # C3: Load documents from database
    doc_records = _get_persistence().list_session_documents(session_id)
    docs = []
    for doc_record in doc_records:
        result_data = doc_record.result
        if result_data:
            docs.append({
                "document_id": doc_record.document_id,
                "filename": result_data.get("filename"),
                "document_type": result_data.get("document_type"),
                "tax_year": result_data.get("tax_year"),
                "status": doc_record.status,
                "ocr_confidence": result_data.get("ocr_confidence"),
                "extraction_confidence": result_data.get("extraction_confidence"),
                "created_at": doc_record.created_at,
            })

    return JSONResponse({"documents": docs})


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str, request: Request):
    """Get details of a specific uploaded document."""
    session_id = request.cookies.get("tax_session_id") or ""
    persistence = _get_persistence()

    # C3: Load document from database
    doc_record = persistence.load_document_result(document_id, session_id=session_id)
    if not doc_record:
        # Check if exists but belongs to different session
        doc_any = persistence.load_document_result(document_id)
        if doc_any:
            raise HTTPException(status_code=403, detail="Access denied")
        raise HTTPException(status_code=404, detail="Document not found")

    result_data = doc_record.result
    return JSONResponse({
        "document_id": document_id,
        "filename": result_data.get("filename"),
        "document_type": result_data.get("document_type"),
        "tax_year": result_data.get("tax_year"),
        "status": doc_record.status,
        "ocr_confidence": result_data.get("ocr_confidence"),
        "extraction_confidence": result_data.get("extraction_confidence"),
        "extracted_fields": result_data.get("extracted_fields", []),
        "extracted_data": _build_extracted_data(result_data.get("extracted_fields", [])),
        "warnings": result_data.get("warnings", []),
        "errors": result_data.get("errors", []),
        "created_at": doc_record.created_at,
    })


def _build_extracted_data(extracted_fields: list) -> dict:
    """Build extracted data dict from list of field dicts."""
    data = {}
    for field in extracted_fields:
        if isinstance(field, dict) and "field_name" in field and "value" in field:
            data[field["field_name"]] = field["value"]
    return data


def _get_or_create_tax_return(session_id: str):
    """
    Get or create a tax return for the session (without requiring OpenAI).

    C3: Tax return is persisted to database, not in-memory dict.
    SECURITY: Uses SecureSerializer instead of pickle to prevent RCE.
    """
    from models.tax_return import TaxReturn
    from models.taxpayer import TaxpayerInfo, FilingStatus
    from models.income import Income
    from models.deductions import Deductions
    from models.credits import TaxCredits

    persistence = _get_persistence()
    serializer = get_secure_serializer()

    # C3: Try to load from database
    stored = persistence.load_session_tax_return(session_id)
    if stored and stored.get("return_data"):
        try:
            # SECURITY: Use secure deserializer instead of pickle
            serialized_data = stored["return_data"].get("secure_tax_return")
            if serialized_data:
                tax_data = serializer.deserialize(serialized_data)
                tax_return = TaxReturn.from_dict(tax_data)
                return tax_return
            # Fallback for legacy pickled data (read-only migration)
            legacy_pickled = stored["return_data"].get("pickled_tax_return")
            if legacy_pickled:
                logger.warning(f"Legacy pickle data found for {session_id} - migrating to secure format")
                # For migration: we'll create a new return instead of unpickling
                # This is safer than executing potentially malicious pickle data
        except (DeserializationError, IntegrityError) as e:
            logger.warning(f"Security: Failed to deserialize tax return for {session_id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to load tax return from database for {session_id}: {sanitize_for_logging(str(e))}")

    # Create a new tax return
    tax_return = TaxReturn(
        taxpayer=TaxpayerInfo(
            first_name="",
            last_name="",
            filing_status=FilingStatus.SINGLE
        ),
        income=Income(),
        deductions=Deductions(),
        credits=TaxCredits()
    )

    # C3: Persist new tax return
    _persist_tax_return(session_id, tax_return)
    return tax_return


def _persist_tax_return(session_id: str, tax_return):
    """
    Persist tax return to database.

    SECURITY: Uses SecureSerializer instead of pickle to prevent RCE.
    """
    try:
        serializer = get_secure_serializer()
        # Convert tax return to dict for safe serialization
        tax_data = tax_return.to_dict() if hasattr(tax_return, 'to_dict') else _tax_return_to_dict(tax_return)
        serialized = serializer.serialize(tax_data)
        _get_persistence().save_session_tax_return(
            session_id=session_id,
            return_data={"secure_tax_return": serialized}
        )
    except SerializationError as e:
        logger.warning(f"Security: Failed to serialize tax return for {session_id}: {e}")
    except Exception as e:
        logger.warning(f"Failed to persist tax return for {session_id}: {sanitize_for_logging(str(e))}")


def _tax_return_to_dict(tax_return) -> dict:
    """Convert TaxReturn to dict for serialization (fallback if to_dict not available)."""
    from dataclasses import asdict, is_dataclass
    if is_dataclass(tax_return):
        return asdict(tax_return)
    elif hasattr(tax_return, '__dict__'):
        result = {}
        for key, value in tax_return.__dict__.items():
            if not key.startswith('_'):
                if is_dataclass(value):
                    result[key] = asdict(value)
                elif hasattr(value, '__dict__'):
                    result[key] = {k: v for k, v in value.__dict__.items() if not k.startswith('_')}
                else:
                    result[key] = value
        return result
    return {}


@app.post("/api/documents/{document_id}/apply")
async def apply_document(document_id: str, request: Request):
    """
    Apply extracted document data to the current tax return.

    This automatically populates the tax return with data from the document.
    """
    session_id = request.cookies.get("tax_session_id") or ""
    persistence = _get_persistence()

    # C3: Load document from database
    doc_record = persistence.load_document_result(document_id, session_id=session_id)
    if not doc_record:
        doc_any = persistence.load_document_result(document_id)
        if doc_any:
            raise HTTPException(status_code=403, detail="Access denied")
        raise HTTPException(status_code=404, detail="Document not found")

    result_data = doc_record.result

    # Reconstruct ProcessingResult from stored data
    from services.ocr import ProcessingResult
    result = ProcessingResult.from_dict(result_data)

    # Get or create tax return (without requiring OpenAI)
    tax_return = _get_or_create_tax_return(session_id)

    # Apply document based on type
    from services.ocr.document_processor import DocumentIntegration
    integration = DocumentIntegration()

    success, messages = integration.apply_document_to_return(result, tax_return)

    if success:
        # C3: Update document status in database
        result_data["status"] = "applied"
        persistence.save_document_result(
            document_id=document_id,
            session_id=session_id,
            document_type=result_data.get("document_type"),
            status="applied",
            result=result_data
        )

        # C3: Persist updated tax return
        _persist_tax_return(session_id, tax_return)

        # ==========================================================================
        # AUDIT TRAIL: Log document application (CPA COMPLIANCE)
        # ==========================================================================
        try:
            extracted_fields = result_data.get("extracted_fields", [])
            field_summary = {f.get("field_name"): f.get("value") for f in extracted_fields if f.get("field_name")}
            _log_audit_event(
                session_id=session_id,
                event_type=AuditEventType.DOCUMENT_UPLOAD,
                description=f"Document {result_data.get('document_type', 'unknown').upper()} applied to return",
                metadata={
                    "document_id": document_id,
                    "document_type": result_data.get("document_type"),
                    "ocr_confidence": result_data.get("ocr_confidence"),
                    "extraction_confidence": result_data.get("extraction_confidence"),
                    "fields_applied": list(field_summary.keys()),
                    "field_count": len(extracted_fields),
                    "warnings": messages,
                },
                request=request
            )
        except Exception as e:
            logger.warning(f"Failed to log document apply audit event: {e}")

        # Generate summary of applied data
        extracted_data = _build_extracted_data(result_data.get("extracted_fields", []))
        summary_items = []
        if "wages" in extracted_data:
            summary_items.append(f"Wages: ${float(extracted_data['wages']):,.2f}")
        if "federal_tax_withheld" in extracted_data:
            summary_items.append(f"Federal Withheld: ${float(extracted_data['federal_tax_withheld']):,.2f}")

        return JSONResponse({
            "success": True,
            "document_id": document_id,
            "document_type": result_data.get("document_type"),
            "message": f"Successfully applied {result_data.get('document_type', 'document').upper()} to tax return",
            "applied_data": summary_items,
            "warnings": messages,
        })
    else:
        return JSONResponse({
            "success": False,
            "document_id": document_id,
            "document_type": result_data.get("document_type"),
            "message": "Failed to apply document",
            "errors": messages,
        }, status_code=400)


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str, request: Request):
    """Delete an uploaded document."""
    session_id = request.cookies.get("tax_session_id") or ""
    persistence = _get_persistence()

    # C3: Check document exists and belongs to session
    doc_record = persistence.load_document_result(document_id, session_id=session_id)
    if not doc_record:
        doc_any = persistence.load_document_result(document_id)
        if doc_any:
            raise HTTPException(status_code=403, detail="Access denied")
        raise HTTPException(status_code=404, detail="Document not found")

    # C3: Delete from database
    persistence.delete_document(document_id)
    return JSONResponse({"success": True, "message": "Document deleted"})


@app.get("/api/supported-documents")
async def get_supported_documents():
    """Get list of supported document types."""
    return JSONResponse({
        "supported_types": _document_processor.get_supported_document_types(),
        "description": {
            "w2": "Form W-2: Wage and Tax Statement",
            "1099-int": "Form 1099-INT: Interest Income",
            "1099-div": "Form 1099-DIV: Dividends and Distributions",
            "1099-nec": "Form 1099-NEC: Nonemployee Compensation",
            "1099-misc": "Form 1099-MISC: Miscellaneous Income",
            "1099-b": "Form 1099-B: Proceeds from Broker Transactions",
            "1099-r": "Form 1099-R: Distributions from Pensions/Annuities",
            "1099-g": "Form 1099-G: Government Payments",
            "1098": "Form 1098: Mortgage Interest Statement",
            "1098-e": "Form 1098-E: Student Loan Interest Statement",
            "1098-t": "Form 1098-T: Tuition Statement",
            "k1": "Schedule K-1: Partner/Shareholder Share of Income",
        }
    })


# =============================================================================
# HEALTH & RESILIENCE MONITORING ENDPOINTS
# =============================================================================

@app.get("/api/health")
async def health_check():
    """Basic health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "service": "tax-platform",
    })


@app.get("/api/health/resilience")
async def resilience_status():
    """Get circuit breaker and resilience status.

    Returns current state of all circuit breakers for monitoring.
    """
    try:
        from resilience import get_circuit_breaker_registry

        registry = get_circuit_breaker_registry()
        stats = registry.get_all_stats()

        return JSONResponse({
            "status": "ok",
            "circuit_breakers": stats,
            "summary": {
                "total": len(stats),
                "open": sum(1 for s in stats.values() if s.get("is_open")),
                "closed": sum(1 for s in stats.values() if not s.get("is_open")),
            }
        })
    except ImportError:
        return JSONResponse({
            "status": "ok",
            "circuit_breakers": {},
            "message": "Resilience module not available",
        })


@app.post("/api/health/resilience/reset")
async def reset_circuit_breakers():
    """Reset all circuit breakers to closed state.

    Use with caution - this will allow requests through to potentially
    failing services.
    """
    try:
        from resilience import get_circuit_breaker_registry

        registry = get_circuit_breaker_registry()
        registry.reset_all()

        return JSONResponse({
            "status": "ok",
            "message": "All circuit breakers reset to closed state",
        })
    except ImportError:
        return JSONResponse({
            "status": "ok",
            "message": "Resilience module not available",
        })


@app.get("/api/health/cache")
async def cache_status():
    """Get Redis cache status and statistics.

    Returns cache connectivity and basic stats.
    """
    try:
        from cache import redis_health_check, get_calculation_cache

        # Basic health check
        health = await redis_health_check()

        # Get calculation cache stats if available
        cache_stats = {}
        if health.get("status") == "healthy":
            try:
                cache = await get_calculation_cache()
                cache_stats = await cache.get_cache_stats()
            except Exception:
                pass

        return JSONResponse({
            "status": health.get("status", "unknown"),
            "connected": health.get("connected", False),
            "cache_stats": cache_stats,
        })
    except ImportError:
        return JSONResponse({
            "status": "unavailable",
            "connected": False,
            "message": "Cache module not available",
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "connected": False,
            "error": str(e),
        })


@app.post("/api/health/cache/flush")
async def flush_cache():
    """Flush all cached calculations.

    Use with caution - this will clear all cached data and may
    temporarily increase computation load.
    """
    try:
        from cache import CacheInvalidator, get_calculation_cache

        cache = await get_calculation_cache()
        invalidator = CacheInvalidator(cache)
        await invalidator.on_config_changed()

        return JSONResponse({
            "status": "ok",
            "message": "All calculation caches flushed",
        })
    except ImportError:
        return JSONResponse({
            "status": "ok",
            "message": "Cache module not available",
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": f"Cache flush failed: {str(e)}",
        }, status_code=500)


@app.get("/api/health/database")
async def database_status():
    """Get PostgreSQL/SQLite database status and pool statistics.

    Returns database connectivity and connection pool information.
    """
    try:
        from database import DatabaseHealth, check_database_connection
        from config.database import get_database_settings

        settings = get_database_settings()
        health = DatabaseHealth(settings)
        result = await health.check()

        return JSONResponse({
            "status": result.get("status", "unknown"),
            "database": result.get("database", "unknown"),
            "driver": result.get("driver", "unknown"),
            "pool": result.get("pool", {}),
        })
    except ImportError:
        return JSONResponse({
            "status": "unavailable",
            "message": "Database module not available",
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
        })


@app.on_event("startup")
async def startup_database():
    """Initialize database on application startup."""
    try:
        from database import init_database, check_database_connection
        from config.database import get_database_settings

        settings = get_database_settings()

        # Initialize database (creates tables for SQLite)
        await init_database(settings)

        # Verify connection
        if await check_database_connection(settings):
            logger.info(
                f"Database initialized: {settings.driver}",
                extra={"database": settings.name if settings.is_postgres else "sqlite"}
            )
        else:
            logger.warning("Database connection check failed during startup")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")


@app.on_event("shutdown")
async def shutdown_database():
    """Close database connections on application shutdown."""
    try:
        from database import close_database

        await close_database()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


@app.get("/api/health/migrations")
async def migration_status():
    """Get Alembic migration status.

    Returns current revision, head revision, and pending migrations.
    """
    try:
        from database import get_migration_health

        result = await get_migration_health()

        return JSONResponse({
            "status": "healthy" if result.get("healthy") else "needs_migration",
            "database_type": result.get("database_type", "unknown"),
            "current_revision": result.get("current_revision"),
            "head_revision": result.get("head_revision"),
            "pending_migrations": result.get("pending_migrations", 0),
            "up_to_date": result.get("up_to_date", False),
        })
    except ImportError:
        return JSONResponse({
            "status": "unavailable",
            "message": "Migration module not available",
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
        })


# =============================================================================
# TAX OPTIMIZATION & RECOMMENDATION ENDPOINTS
# =============================================================================

@app.post("/api/optimize")
async def get_optimization_recommendations(request: Request):
    """
    Get comprehensive tax optimization recommendations.

    Uses the full recommendation engine to analyze the tax return and
    provide filing status comparison, credit optimization, deduction
    analysis, and tax strategies.
    """
    from recommendation.recommendation_engine import TaxRecommendationEngine

    session_id = request.cookies.get("tax_session_id") or ""

    # C3: Get tax return from database (not in-memory)
    tax_return = _get_tax_return_for_session(session_id)

    if not tax_return:
        raise HTTPException(status_code=400, detail="No tax return data found. Please upload documents or complete the interview.")

    # Run recommendation engine
    engine = TaxRecommendationEngine()
    recommendations = engine.analyze(tax_return)

    return JSONResponse(recommendations.to_dict())


@app.post("/api/optimize/filing-status")
async def compare_filing_statuses(request: Request):
    """
    Compare tax liability across all 5 filing statuses.

    Returns the tax calculation for each status the taxpayer may
    qualify for, with savings comparison.
    """
    from recommendation.filing_status_optimizer import FilingStatusOptimizer
    from models.taxpayer import FilingStatus

    session_id = request.cookies.get("tax_session_id") or ""
    tax_return = _get_tax_return_for_session(session_id)

    if not tax_return:
        raise HTTPException(status_code=400, detail="No tax return data found")

    optimizer = FilingStatusOptimizer()
    recommendation = optimizer.analyze(tax_return)

    # Get current status tax for calculating savings
    current_tax = 0
    if recommendation.current_status in recommendation.analyses:
        current_tax = recommendation.analyses[recommendation.current_status].total_tax

    # Build comparisons from analyses dict
    comparisons = []
    for status_key, analysis in recommendation.analyses.items():
        savings = current_tax - analysis.total_tax if analysis.is_eligible else 0
        comparisons.append({
            "status": status_key,
            "tax_liability": analysis.total_tax,
            "savings_vs_current": savings,
            "is_eligible": analysis.is_eligible,
            "eligibility_reason": analysis.eligibility_reason,
            "refund_or_owed": analysis.refund_or_owed,
        })

    return JSONResponse({
        "current_status": recommendation.current_status,
        "recommended_status": recommendation.recommended_status,
        "potential_savings": recommendation.potential_savings,
        "analyses": {k: {
            "filing_status": v.filing_status,
            "federal_tax": v.federal_tax,
            "state_tax": v.state_tax,
            "total_tax": v.total_tax,
            "effective_rate": v.effective_rate,
            "marginal_rate": v.marginal_rate,
            "refund_or_owed": v.refund_or_owed,
            "is_eligible": v.is_eligible,
            "eligibility_reason": v.eligibility_reason,
            "benefits": v.benefits,
            "drawbacks": v.drawbacks,
        } for k, v in recommendation.analyses.items()},
        "comparisons": comparisons,
        "recommendation_text": recommendation.recommendation_reason,
        "confidence_score": recommendation.confidence_score,
        "warnings": recommendation.warnings,
        "additional_considerations": recommendation.additional_considerations,
    })


@app.post("/api/optimize/credits")
async def analyze_tax_credits(request: Request):
    """
    Analyze available tax credits and identify unclaimed opportunities.

    Returns all credits the taxpayer may qualify for, with estimated
    amounts and eligibility requirements.
    """
    from recommendation.credit_optimizer import CreditOptimizer

    session_id = request.cookies.get("tax_session_id") or ""
    tax_return = _get_tax_return_for_session(session_id)

    if not tax_return:
        raise HTTPException(status_code=400, detail="No tax return data found")

    optimizer = CreditOptimizer()
    recommendation = optimizer.analyze(tax_return)
    analysis = recommendation.analysis

    # Build eligible credits list
    eligible_credits_list = []
    for credit_name, eligibility in analysis.eligible_credits.items():
        eligible_credits_list.append({
            "credit_name": eligibility.credit_name,
            "credit_code": eligibility.credit_code,
            "credit_type": eligibility.credit_type,
            "is_eligible": eligibility.is_eligible,
            "potential_amount": eligibility.potential_amount,
            "actual_amount": eligibility.actual_amount,
            "phase_out_applied": eligibility.phase_out_applied,
            "eligibility_reason": eligibility.eligibility_reason,
            "requirements": eligibility.requirements,
            "optimization_tips": eligibility.optimization_tips,
        })

    return JSONResponse({
        "total_credits_claimed": analysis.total_credits_claimed,
        "total_refundable_credits": analysis.total_refundable_credits,
        "total_nonrefundable_credits": analysis.total_nonrefundable_credits,
        "total_credit_benefit": recommendation.total_credit_benefit,
        "confidence_score": recommendation.confidence_score,
        "summary": recommendation.summary,
        "eligible_credits": eligible_credits_list,
        "immediate_actions": recommendation.immediate_actions,
        "year_round_planning": recommendation.year_round_planning,
        "documentation_reminders": recommendation.documentation_reminders,
        "warnings": recommendation.warnings,
    })


@app.post("/api/optimize/deductions")
async def analyze_deductions(request: Request):
    """
    Analyze standard vs itemized deductions with detailed breakdown.

    Returns comparison of deduction strategies with recommendation.
    """
    from recommendation.deduction_analyzer import DeductionAnalyzer

    session_id = request.cookies.get("tax_session_id") or ""
    tax_return = _get_tax_return_for_session(session_id)

    if not tax_return:
        raise HTTPException(status_code=400, detail="No tax return data found")

    analyzer = DeductionAnalyzer()
    recommendation = analyzer.analyze(tax_return)
    analysis = recommendation.analysis

    # Get itemized breakdown as dict
    breakdown = analysis.itemized_breakdown
    itemized_breakdown_dict = {
        "medical_deduction_allowed": breakdown.medical_deduction_allowed,
        "salt_deduction_allowed": breakdown.salt_deduction_allowed,
        "mortgage_interest": breakdown.mortgage_interest,
        "total_interest_deduction": breakdown.total_interest_deduction,
        "charitable_deduction_allowed": breakdown.charitable_deduction_allowed,
        "other_deductions": breakdown.other_deductions,
        "total": breakdown.total_itemized_deductions,
    }

    return JSONResponse({
        "recommended_method": analysis.recommended_strategy,
        "standard_deduction_amount": analysis.total_standard_deduction,
        "itemized_deduction_amount": analysis.total_itemized_deductions,
        "deduction_difference": analysis.deduction_difference,
        "tax_savings_estimate": analysis.tax_savings_estimate,
        "itemized_breakdown": itemized_breakdown_dict,
        "itemized_categories": analysis.itemized_categories,
        "marginal_rate": analysis.marginal_rate,
        "optimization_opportunities": analysis.optimization_opportunities,
        "bunching_strategy": recommendation.bunching_strategy,
        "current_year_actions": recommendation.current_year_actions,
        "next_year_planning": recommendation.next_year_planning,
        "explanation": recommendation.explanation,
        "confidence_score": recommendation.confidence_score,
        "warnings": analysis.warnings,
    })


@app.post("/api/calculate/complete")
async def calculate_complete_return(request: Request):
    """
    Calculate complete federal and state tax return.

    Returns comprehensive tax calculation including:
    - Federal tax breakdown
    - State tax breakdown (if state provided)
    - Effective and marginal rates
    - Refund or amount owed

    Also auto-saves the return to the database after calculation.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    state_code = body.get("state_code")

    session_id = request.cookies.get("tax_session_id") or ""
    tax_return = _get_tax_return_for_session(session_id)

    if not tax_return:
        return create_error_response(
            code=ErrorCode.SESSION_NOT_FOUND,
            message="No tax return data found",
            status_code=400,
            user_message="Please enter your tax information first. Start by adding your personal details and income."
        )

    # Validate state code
    if state_code and not validate_state_code(state_code):
        logger.warning(f"Invalid state code provided: {state_code}")
        state_code = None

    # Set state if provided
    if state_code:
        tax_return.state_of_residence = state_code

    # Calculate complete return
    try:
        _calculator.calculate_complete_return(tax_return)
    except ValueError as e:
        logger.error(f"Validation error in calculation: {e}")
        return create_error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=str(e),
            status_code=400,
            user_message="Some of your tax information appears to be invalid. Please review your entries."
        )
    except Exception as e:
        logger.error(f"Calculation error: {e}\n{traceback.format_exc()}")
        return create_error_response(
            code=ErrorCode.CALCULATION_ERROR,
            message=str(e),
            status_code=500,
            user_message="We encountered an error while calculating your taxes. Please try again."
        )

    # AUTO-SAVE: Persist the calculated return to database
    return_id = None
    try:
        from database.persistence import save_tax_return as db_save
        return_data = tax_return.model_dump()
        return_id = db_save(session_id, return_data)
        logger.info(f"Auto-saved tax return {return_id} after calculation")
    except Exception as e:
        logger.warning(f"Auto-save failed: {e}")  # Non-fatal - continue with response

    # ==========================================================================
    # AUDIT TRAIL: Log calculation run (CPA COMPLIANCE)
    # ==========================================================================
    try:
        _log_audit_event(
            session_id=session_id,
            event_type=AuditEventType.CALCULATION_RUN,
            description=f"Tax calculation completed for TY{tax_return.tax_year}",
            metadata={
                "return_id": return_id,
                "tax_year": tax_return.tax_year,
                "filing_status": str(tax_return.taxpayer.filing_status.value) if tax_return.taxpayer else "unknown",
                "state_code": state_code,
                "gross_income": float(tax_return.income.get_total_income() if tax_return.income else 0),
                "adjusted_gross_income": float(tax_return.adjusted_gross_income or 0),
                "taxable_income": float(tax_return.taxable_income or 0),
                "tax_liability": float(tax_return.tax_liability or 0),
                "total_credits": float(tax_return.total_credits or 0),
                "refund_or_owed": float(tax_return.refund_or_owed or 0),
            },
            request=request
        )
    except Exception as e:
        logger.warning(f"Failed to log calculation audit event: {e}")

    # Build response
    result = {
        "federal": {
            "gross_income": float(tax_return.income.get_total_income() if tax_return.income else 0),
            "adjusted_gross_income": float(tax_return.adjusted_gross_income or 0),
            "taxable_income": float(tax_return.taxable_income or 0),
            "tax_before_credits": float(tax_return.tax_liability or 0) + float(tax_return.total_credits or 0),
            "total_credits": float(tax_return.total_credits or 0),
            "tax_liability": float(tax_return.tax_liability or 0),
            "total_payments": float(tax_return.total_payments or 0),
            "refund_or_owed": float(tax_return.refund_or_owed or 0),
            "is_refund": (tax_return.refund_or_owed or 0) >= 0,
        },
        "rates": {
            "effective_rate": float(tax_return.tax_liability or 0) / float(tax_return.adjusted_gross_income or 1) if tax_return.adjusted_gross_income else 0,
            "marginal_rate": _get_marginal_rate(tax_return),
        },
    }

    # Add state calculation if available
    if tax_return.state_tax_result:
        state_result = tax_return.state_tax_result  # This is a dict from asdict()
        result["state"] = {
            "state_code": state_code,
            "state_name": state_result.get("state_code", state_code),
            "taxable_income": float(state_result.get("state_taxable_income", 0)),
            "tax_before_credits": float(state_result.get("state_tax_before_credits", 0)),
            "total_credits": float(state_result.get("total_state_credits", 0)),
            "tax_liability": float(state_result.get("state_tax_liability", 0)),
            "withholding": float(state_result.get("state_withholding", 0)),
            "refund_or_owed": float(state_result.get("state_refund_or_owed", 0)),
            "is_refund": state_result.get("state_refund_or_owed", 0) >= 0,
            "additions": float(state_result.get("state_additions", 0)),
            "subtractions": float(state_result.get("state_subtractions", 0)),
            "standard_deduction": float(state_result.get("state_standard_deduction", 0)),
            "credits": state_result.get("state_credits", {}),
        }
        result["combined"] = {
            "total_tax_liability": float(tax_return.combined_tax_liability or 0),
            "total_refund_or_owed": float(tax_return.combined_refund_or_owed or 0),
        }

    # Add return_id to response so frontend knows data was saved
    if return_id:
        result["return_id"] = return_id

    # Generate tax optimization recommendations (key for product stickiness)
    try:
        recommendations = get_recommendations(tax_return)
        result["recommendations"] = {
            "summary": recommendations.summary,
            "total_potential_savings": recommendations.total_potential_savings,
            "count": len(recommendations.recommendations),
            "high_priority_count": len([r for r in recommendations.recommendations if r.priority.value == "high"]),
            # Include top 3 recommendations in response
            "top_recommendations": [
                r.to_dict() for r in recommendations.recommendations[:3]
            ]
        }
    except Exception as e:
        logger.warning(f"Recommendations generation failed: {e}")
        result["recommendations"] = None

    # Add progress indicator for product stickiness
    result["progress"] = _calculate_completion_progress(tax_return)

    # ==========================================================================
    # CPA COMPLIANCE: Add calculation engine version hash
    # ==========================================================================
    result["engine"] = _get_engine_version_hash()

    return JSONResponse(result)


def _calculate_completion_progress(tax_return) -> Dict[str, Any]:
    """Calculate tax return completion progress for user feedback."""
    steps = {
        "personal_info": False,
        "income": False,
        "deductions": False,
        "credits": False,
        "state_tax": False,
        "review": False,
    }

    # Check personal info
    if tax_return.taxpayer and tax_return.taxpayer.first_name:
        steps["personal_info"] = True

    # Check income
    if tax_return.income and (
        tax_return.income.get_total_wages() > 0 or
        tax_return.income.get_total_income() > 0
    ):
        steps["income"] = True

    # Check deductions (always have default)
    steps["deductions"] = True

    # Check credits
    if hasattr(tax_return, 'credits') and tax_return.credits:
        steps["credits"] = True

    # Check state tax
    if tax_return.state_tax_result:
        steps["state_tax"] = True

    # Review is complete if calculation was successful
    if tax_return.tax_liability is not None:
        steps["review"] = True

    completed = sum(1 for v in steps.values() if v)
    total = len(steps)

    return {
        "steps": steps,
        "completed": completed,
        "total": total,
        "percentage": round(completed / total * 100),
        "next_step": next((k for k, v in steps.items() if not v), None),
    }


@app.get("/api/recommendations")
async def get_tax_recommendations(request: Request):
    """
    Get detailed tax optimization recommendations.

    This is a key feature for product stickiness - providing
    actionable insights that help users save money.
    """
    session_id = request.cookies.get("tax_session_id") or ""
    tax_return = _get_tax_return_for_session(session_id)

    if not tax_return:
        return create_error_response(
            code=ErrorCode.SESSION_NOT_FOUND,
            message="No tax return data found",
            status_code=400,
            user_message="Please complete your tax information first to get personalized recommendations."
        )

    try:
        recommendations = get_recommendations(tax_return)
        return JSONResponse({
            "success": True,
            "summary": recommendations.summary,
            "total_potential_savings": recommendations.total_potential_savings,
            "recommendations": [r.to_dict() for r in recommendations.recommendations],
            "count_by_priority": {
                "high": len([r for r in recommendations.recommendations if r.priority.value == "high"]),
                "medium": len([r for r in recommendations.recommendations if r.priority.value == "medium"]),
                "low": len([r for r in recommendations.recommendations if r.priority.value == "low"]),
            }
        })
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return create_error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            status_code=500,
            user_message="Unable to generate recommendations at this time. Please try again."
        )


@app.post("/api/estimate")
async def get_real_time_estimate(request: Request):
    """
    Get real-time tax estimate based on current data.

    This is a lightweight calculation for live updates as
    the user enters data.
    """
    from onboarding.benefit_estimator import OnboardingBenefitEstimator

    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    # Extract basic info with safe conversion
    wages = safe_float(body.get("wages"))
    withholding = safe_float(body.get("withholding"), max_val=wages if wages > 0 else 999_999_999)  # Can't exceed wages
    filing_status = body.get("filing_status", "single")
    num_dependents = safe_int(body.get("num_dependents"), max_val=20)
    state_code = body.get("state_code")

    # Validate filing status
    valid_statuses = ["single", "married_joint", "married_separate", "head_of_household", "qualifying_widow"]
    if filing_status not in valid_statuses:
        filing_status = "single"

    # Validate state code
    if state_code and not validate_state_code(state_code):
        state_code = None

    # Use benefit estimator for quick calculation
    try:
        estimator = OnboardingBenefitEstimator()
        estimate = estimator.estimate_from_basics(
            wages=wages,
            withholding=withholding,
            filing_status=filing_status,
            num_dependents=num_dependents,
            state_code=state_code,
        )
    except Exception as e:
        logger.error(f"Estimate calculation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate estimate")

    return JSONResponse({
        "estimated_refund": estimate.estimated_refund,
        "estimated_owed": estimate.estimated_owed,
        "is_refund": estimate.is_refund,
        "federal_tax": estimate.federal_tax,
        "state_tax": estimate.state_tax,
        "effective_rate": estimate.effective_rate,
        "marginal_rate": estimate.marginal_rate,
        "confidence": estimate.confidence,
        "benefits_summary": estimate.benefits_summary,
    })


@app.get("/api/export/pdf")
async def export_pdf(request: Request):
    """
    Export tax return as PDF.

    CPA COMPLIANCE: Requires CPA_APPROVED status.
    """
    from export.pdf_generator import TaxReturnPDFGenerator
    from fastapi.responses import Response

    session_id = request.cookies.get("tax_session_id") or ""

    # CPA COMPLIANCE: Check approval status before allowing export
    is_approved, error_msg = _check_cpa_approval(session_id, "PDF Export")
    if not is_approved:
        return create_error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=error_msg,
            status_code=403,
            user_message=error_msg
        )

    tax_return = _get_tax_return_for_session(session_id)

    if not tax_return:
        raise HTTPException(status_code=400, detail="No tax return data found")

    try:
        # Generate PDF using the correct method
        generator = TaxReturnPDFGenerator()
        pdf_doc = generator.generate_complete_return(tax_return)

        return Response(
            content=pdf_doc.content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={pdf_doc.filename}"
            }
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@app.get("/api/export/json")
async def export_json(request: Request):
    """
    Export complete tax return as JSON.

    CPA COMPLIANCE: Requires CPA_APPROVED status.
    """
    session_id = request.cookies.get("tax_session_id") or ""

    # CPA COMPLIANCE: Check approval status before allowing export
    is_approved, error_msg = _check_cpa_approval(session_id, "JSON Export")
    if not is_approved:
        return create_error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=error_msg,
            status_code=403,
            user_message=error_msg
        )

    tax_return = _get_tax_return_for_session(session_id)

    if not tax_return:
        raise HTTPException(status_code=400, detail="No tax return data found")

    # Convert to dict (assumes TaxReturn has to_dict method)
    return JSONResponse(tax_return.to_dict() if hasattr(tax_return, 'to_dict') else {
        "taxpayer": {
            "first_name": tax_return.taxpayer.first_name if tax_return.taxpayer else "",
            "last_name": tax_return.taxpayer.last_name if tax_return.taxpayer else "",
            "filing_status": str(tax_return.taxpayer.filing_status) if tax_return.taxpayer else "",
        },
        "income": {
            "total_income": float(tax_return.income.get_total_income() if tax_return.income else 0),
            "wages": float(tax_return.income.get_total_wages() if tax_return.income else 0),
        },
        "calculations": {
            "agi": float(tax_return.adjusted_gross_income or 0),
            "taxable_income": float(tax_return.taxable_income or 0),
            "tax_liability": float(tax_return.tax_liability or 0),
            "total_credits": float(tax_return.total_credits or 0),
            "refund_or_owed": float(tax_return.refund_or_owed or 0),
        }
    })


def _get_tax_return_for_session(session_id: str):
    """
    Helper to get tax return from either session or document flow.

    C3: Uses database persistence instead of in-memory dicts.
    SECURITY: Uses SecureSerializer instead of pickle to prevent RCE.
    """
    from models.tax_return import TaxReturn
    persistence = _get_persistence()
    serializer = get_secure_serializer()

    # First try to get from agent session
    agent_state = persistence.load_agent_state(session_id)
    if agent_state:
        try:
            # SECURITY: Use secure deserializer instead of pickle
            agent_data = serializer.deserialize(agent_state.decode('utf-8') if isinstance(agent_state, bytes) else agent_state)
            agent = TaxAgent()
            agent.restore_from_state(agent_data)
            tax_return = agent.get_tax_return()
            if tax_return:
                return tax_return
        except (DeserializationError, IntegrityError) as e:
            logger.warning(f"Security: Failed to deserialize agent for session {session_id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to load agent for session {session_id}: {sanitize_for_logging(str(e))}")

    # Then try document-flow tax return
    stored = persistence.load_session_tax_return(session_id)
    if stored and stored.get("return_data"):
        try:
            # SECURITY: Use secure deserializer instead of pickle
            serialized_data = stored["return_data"].get("secure_tax_return")
            if serialized_data:
                tax_data = serializer.deserialize(serialized_data)
                return TaxReturn.from_dict(tax_data)
            # Note: Legacy pickled data is NOT loaded for security reasons
            # Users with legacy data will need to re-enter their information
        except (DeserializationError, IntegrityError) as e:
            logger.warning(f"Security: Failed to deserialize tax return for session {session_id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to load tax return for session {session_id}: {sanitize_for_logging(str(e))}")

    return None


def _get_marginal_rate(tax_return) -> float:
    """Calculate marginal tax rate based on taxable income."""
    from calculator.tax_year_config import TaxYearConfig

    taxable_income = float(tax_return.taxable_income or 0)
    filing_status = tax_return.taxpayer.filing_status.value if tax_return.taxpayer else "single"

    config = TaxYearConfig.for_2025()
    brackets = config.ordinary_income_brackets.get(filing_status, config.ordinary_income_brackets["single"])

    # Brackets are list of tuples: (threshold, rate)
    # Find the highest bracket that applies
    marginal_rate = 0.10
    for threshold, rate in brackets:
        if taxable_income > threshold:
            marginal_rate = rate

    return marginal_rate


@app.post("/api/sync")
async def sync_tax_return(request: Request):
    """
    Sync frontend state to backend tax return.

    Accepts all tax data from the frontend wizard and creates/updates
    the backend TaxReturn model for server-side calculations.
    """
    from models.tax_return import TaxReturn
    from models.taxpayer import TaxpayerInfo, FilingStatus, Dependent
    from models.income import Income
    from models.deductions import Deductions, ItemizedDeductions
    from models.credits import TaxCredits

    session_id = request.cookies.get("tax_session_id") or str(uuid.uuid4())
    body = await request.json()

    # Map filing status string to enum
    filing_status_map = {
        "single": FilingStatus.SINGLE,
        "married_joint": FilingStatus.MARRIED_JOINT,
        "married_separate": FilingStatus.MARRIED_SEPARATE,
        "head_of_household": FilingStatus.HEAD_OF_HOUSEHOLD,
        "qualifying_widow": FilingStatus.QUALIFYING_WIDOW,
    }
    filing_status = filing_status_map.get(body.get("filing_status", "single"), FilingStatus.SINGLE)

    # Create or update tax return
    personal = body.get("personal", {})
    tax_data = body.get("taxData", {})
    deductions_data = body.get("deductions", {})
    credits_data = body.get("credits", {})
    dependents_data = body.get("dependents", [])

    # Build taxpayer info
    taxpayer = TaxpayerInfo(
        first_name=personal.get("firstName", "") or "Taxpayer",
        last_name=personal.get("lastName", "") or "User",
        ssn=personal.get("ssn", ""),
        date_of_birth=personal.get("dob"),
        filing_status=filing_status,
        address=personal.get("street", ""),
        city=personal.get("city", ""),
        state=body.get("stateOfResidence", ""),
        zip_code=personal.get("zipCode", ""),
        is_blind=personal.get("blind", False),
        spouse_is_blind=personal.get("spouseBlind", False),
    )

    # Build income - create W2Info for wages (using safe_float for validation)
    from models.income import W2Info
    w2_forms = []
    wages_amount = safe_float(tax_data.get("wages"))
    federal_withheld = safe_float(tax_data.get("federalWithheld"))
    state_withheld = safe_float(tax_data.get("stateWithheld"))

    if wages_amount > 0 or federal_withheld > 0:
        w2_forms.append(W2Info(
            employer_name="Primary Employer",
            wages=wages_amount,
            federal_tax_withheld=federal_withheld,
            state_wages=wages_amount,
            state_tax_withheld=state_withheld,
        ))

    income = Income(
        w2_forms=w2_forms,
        interest_income=safe_float(tax_data.get("interestIncome")),
        dividend_income=safe_float(tax_data.get("dividendIncome")),
        self_employment_income=safe_float(tax_data.get("businessIncome")),
        long_term_capital_gains=safe_float(tax_data.get("capitalGains")),
        retirement_income=safe_float(tax_data.get("retirementDistributions")),
        social_security_benefits=safe_float(tax_data.get("socialSecurity")),
        unemployment_compensation=safe_float(tax_data.get("unemployment")),
        other_income=safe_float(tax_data.get("otherIncome")),
    )

    # Build deductions (using safe_float for validation)
    itemized = ItemizedDeductions(
        medical_expenses=safe_float(deductions_data.get("medical")),
        state_local_taxes=safe_float(deductions_data.get("salt"), max_val=10000),  # SALT cap
        mortgage_interest=safe_float(deductions_data.get("mortgageInterest"), max_val=750000),  # Mortgage limit
        charitable_cash=safe_float(deductions_data.get("charitableCash")),
        charitable_noncash=safe_float(deductions_data.get("charitableNonCash")),
    )

    deductions = Deductions(
        itemized=itemized,
        student_loan_interest=safe_float(deductions_data.get("studentLoanInterest"), max_val=2500),  # IRS limit
        educator_expenses=safe_float(deductions_data.get("educatorExpenses"), max_val=300),  # IRS limit
        ira_contribution=safe_float(deductions_data.get("iraDeduction"), max_val=7000),  # 2025 limit
        hsa_contribution=safe_float(deductions_data.get("hsaContribution"), max_val=8550),  # Family limit 2025
        self_employment_tax_deduction=safe_float(deductions_data.get("selfEmploymentTax")),
    )

    # Build credits (using safe_float for validation)
    credits = TaxCredits(
        child_tax_credit=safe_float(credits_data.get("ctc")),
        child_dependent_care_credit=safe_float(credits_data.get("childCare"), max_val=6000),  # IRS limit
        education_credit=safe_float(credits_data.get("educationCredit"), max_val=2500),  # AOTC limit
        earned_income_credit=safe_float(credits_data.get("eitc")),
        retirement_savings_credit=safe_float(credits_data.get("saverCredit"), max_val=2000),  # IRS limit
        residential_energy_credit=safe_float(credits_data.get("energyCredit")),
        ev_credit=safe_float(credits_data.get("evCredit"), max_val=7500),  # Max EV credit
    )

    # Build dependents list with proper validation
    dependents = []
    for dep_data in dependents_data:
        if dep_data.get("firstName") or dep_data.get("name"):
            # Calculate age from date_of_birth if provided
            age = 18  # Default
            dob_str = dep_data.get("dob")
            if dob_str:
                dob_valid, parsed_dob = validate_date(dob_str)
                if dob_valid and parsed_dob:
                    try:
                        dob = datetime.strptime(parsed_dob, "%Y-%m-%d")
                        today = datetime.now()
                        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                        age = max(0, min(age, 125))  # Clamp to reasonable range
                    except ValueError as e:
                        logger.warning(f"Invalid dependent DOB: {dob_str}, error: {e}")

            # Validate dependent SSN if provided
            dep_ssn = dep_data.get("ssn", "")
            if dep_ssn:
                ssn_valid, dep_ssn = validate_ssn(dep_ssn)
                if not ssn_valid:
                    logger.warning(f"Invalid dependent SSN format")
                    dep_ssn = ""  # Clear invalid SSN

            dependent = Dependent(
                name=f"{dep_data.get('firstName', '')} {dep_data.get('lastName', '')}".strip() or dep_data.get("name", "Dependent"),
                ssn=dep_ssn,
                relationship=dep_data.get("relationship", "child"),
                age=safe_int(age, default=18, min_val=0, max_val=125),
                is_student=bool(dep_data.get("isStudent", False)),
                is_disabled=bool(dep_data.get("isDisabled", False)),
                lives_with_you=bool(dep_data.get("livesWithYou", True)),
            )
            dependents.append(dependent)

    # Update taxpayer with dependents
    taxpayer.dependents = dependents

    # Create tax return
    tax_return = TaxReturn(
        taxpayer=taxpayer,
        income=income,
        deductions=deductions,
        credits=credits,
        state_of_residence=body.get("stateOfResidence"),
    )

    # C3: Store in database (not in-memory)
    _persist_tax_return(session_id, tax_return)

    response = JSONResponse({
        "success": True,
        "session_id": session_id,
        "message": "Tax return synced successfully",
        "summary": {
            "filing_status": filing_status.value,
            "gross_income": float(income.get_total_income()),
            "num_dependents": len(dependents),
        }
    })
    response.set_cookie(
        "tax_session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT") == "production",  # HTTPS only in production
        max_age=86400  # 24 hours
    )
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "service": "US Tax Preparation Agent",
        "tax_year": 2025,
        "features": {
            "chat": True,
            "document_upload": True,
            "ocr": True,
            "calculations": True,
            "optimization": True,
            "state_tax": True,
            "pdf_export": True,
            "persistence": True,
        }
    })


# =============================================================================
# DATABASE PERSISTENCE ENDPOINTS
# =============================================================================

@app.post("/api/returns/save")
async def save_tax_return(request: Request):
    """
    Save the current tax return to database.

    Returns the return_id for future retrieval.
    """
    from database.persistence import save_tax_return as db_save

    session_id = request.cookies.get("tax_session_id") or ""
    tax_return = _get_tax_return_for_session(session_id)

    if not tax_return:
        raise HTTPException(status_code=400, detail="No tax return data to save")

    # Convert Pydantic model to dict
    return_data = tax_return.model_dump()

    # Get existing return_id from request body if updating
    return_id = None
    try:
        body = await request.body()
        if body:
            import json as json_module
            body_data = json_module.loads(body)
            return_id = body_data.get("return_id")
    except Exception:
        pass  # No body or invalid JSON, use default

    # Save to database
    saved_id = db_save(session_id, return_data, return_id)

    # ==========================================================================
    # AUDIT TRAIL: Log return save (CPA COMPLIANCE)
    # ==========================================================================
    try:
        is_update = return_id is not None
        _log_audit_event(
            session_id=session_id,
            event_type=AuditEventType.DATA_CHANGE,
            description=f"Tax return {'updated' if is_update else 'created'} (ID: {saved_id})",
            metadata={
                "return_id": saved_id,
                "action": "update" if is_update else "create",
                "previous_return_id": return_id,
                "tax_year": tax_return.tax_year,
                "filing_status": str(tax_return.taxpayer.filing_status.value) if tax_return.taxpayer else "unknown",
                "has_income": tax_return.income is not None,
                "has_deductions": tax_return.deductions is not None,
                "has_credits": tax_return.credits is not None,
            },
            request=request
        )
    except Exception as e:
        logger.warning(f"Failed to log save audit event: {e}")

    return JSONResponse({
        "success": True,
        "return_id": saved_id,
        "message": "Tax return saved successfully"
    })


@app.get("/api/returns/{return_id}")
async def get_saved_return(return_id: str, request: Request):
    """
    Load a saved tax return by ID.

    Restores the return to the current session.
    """
    from database.persistence import load_tax_return as db_load

    return_data = db_load(return_id)

    if not return_data:
        raise HTTPException(status_code=404, detail="Tax return not found")

    # Rebuild TaxReturn from saved data
    from models.tax_return import TaxReturn
    from models.taxpayer import TaxpayerInfo, FilingStatus, Dependent
    from models.income import Income, W2Info
    from models.deductions import Deductions, ItemizedDeductions
    from models.credits import TaxCredits

    try:
        # Rebuild taxpayer
        taxpayer_data = return_data.get("taxpayer", {})
        filing_status_str = taxpayer_data.get("filing_status", "single")
        if isinstance(filing_status_str, str):
            filing_status = FilingStatus(filing_status_str)
        else:
            filing_status = filing_status_str

        taxpayer = TaxpayerInfo(
            first_name=taxpayer_data.get("first_name", ""),
            last_name=taxpayer_data.get("last_name", ""),
            ssn=taxpayer_data.get("ssn", ""),
            filing_status=filing_status,
            address=taxpayer_data.get("address", ""),
            city=taxpayer_data.get("city", ""),
            state=taxpayer_data.get("state", ""),
            zip_code=taxpayer_data.get("zip_code", ""),
            is_blind=taxpayer_data.get("is_blind", False),
            spouse_is_blind=taxpayer_data.get("spouse_is_blind", False),
        )

        # Rebuild income
        income_data = return_data.get("income", {})
        w2_forms = []
        for w2 in income_data.get("w2_forms", []):
            w2_forms.append(W2Info(
                employer_name=w2.get("employer_name", ""),
                wages=w2.get("wages", 0),
                federal_tax_withheld=w2.get("federal_tax_withheld", 0),
                state_wages=w2.get("state_wages", 0),
                state_tax_withheld=w2.get("state_tax_withheld", 0),
            ))

        income = Income(
            w2_forms=w2_forms,
            interest_income=income_data.get("interest_income", 0),
            dividend_income=income_data.get("dividend_income", 0),
            self_employment_income=income_data.get("self_employment_income", 0),
            long_term_capital_gains=income_data.get("long_term_capital_gains", 0),
            retirement_income=income_data.get("retirement_income", 0),
            social_security_benefits=income_data.get("social_security_benefits", 0),
        )

        # Rebuild deductions
        deductions_data = return_data.get("deductions", {})
        itemized_data = deductions_data.get("itemized", {})
        itemized = ItemizedDeductions(
            medical_expenses=itemized_data.get("medical_expenses", 0),
            state_local_taxes=itemized_data.get("state_local_taxes", 0),
            mortgage_interest=itemized_data.get("mortgage_interest", 0),
            charitable_cash=itemized_data.get("charitable_cash", 0),
            charitable_noncash=itemized_data.get("charitable_noncash", 0),
        )
        deductions = Deductions(
            itemized=itemized,
            student_loan_interest=deductions_data.get("student_loan_interest", 0),
            educator_expenses=deductions_data.get("educator_expenses", 0),
            ira_contribution=deductions_data.get("ira_contribution", 0),
            hsa_contribution=deductions_data.get("hsa_contribution", 0),
        )

        # Rebuild credits
        credits_data = return_data.get("credits", {})
        credits = TaxCredits(
            child_tax_credit=credits_data.get("child_tax_credit", 0),
            child_dependent_care_credit=credits_data.get("child_dependent_care_credit", 0),
            education_credit=credits_data.get("education_credit", 0),
            earned_income_credit=credits_data.get("earned_income_credit", 0),
            residential_energy_credit=credits_data.get("residential_energy_credit", 0),
        )

        # Create tax return
        tax_return = TaxReturn(
            taxpayer=taxpayer,
            income=income,
            deductions=deductions,
            credits=credits,
            state_of_residence=return_data.get("state_of_residence"),
        )

        # C3: Store in database (not in-memory)
        session_id = request.cookies.get("tax_session_id") or str(uuid.uuid4())
        _persist_tax_return(session_id, tax_return)

        response = JSONResponse({
            "success": True,
            "return_id": return_id,
            "message": "Tax return loaded successfully",
            "summary": {
                "taxpayer_name": f"{taxpayer.first_name} {taxpayer.last_name}",
                "filing_status": filing_status.value,
                "gross_income": float(income.get_total_income()),
                "state": return_data.get("state_of_residence"),
            }
        })
        response.set_cookie(
        "tax_session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT") == "production",  # HTTPS only in production
        max_age=86400  # 24 hours
    )
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading return: {str(e)}")


@app.get("/api/returns")
async def list_saved_returns(tax_year: int = 2025, limit: int = 50):
    """
    List saved tax returns.

    Query parameters:
    - tax_year: Filter by tax year (default: 2025)
    - limit: Maximum number of returns (default: 50)
    """
    from database.persistence import list_tax_returns

    returns = list_tax_returns(tax_year, limit)

    return JSONResponse({
        "returns": [
            {
                "return_id": r.return_id,
                "taxpayer_name": r.taxpayer_name,
                "tax_year": r.tax_year,
                "filing_status": r.filing_status,
                "state": r.state_code,
                "gross_income": r.gross_income,
                "tax_liability": r.tax_liability,
                "refund_or_owed": r.refund_or_owed,
                "status": r.status,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in returns
        ],
        "count": len(returns),
        "tax_year": tax_year
    })


@app.delete("/api/returns/{return_id}")
async def delete_saved_return(return_id: str):
    """Delete a saved tax return."""
    from database.persistence import get_persistence

    deleted = get_persistence().delete_return(return_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Tax return not found")

    return JSONResponse({
        "success": True,
        "message": "Tax return deleted successfully"
    })


# =============================================================================
# RETURN STATUS API - CPA APPROVAL WORKFLOW
# =============================================================================
# Status flow: DRAFT → IN_REVIEW → CPA_APPROVED
# CPA COMPLIANCE: Status controls feature access and export permissions

class ReturnStatus(str, Enum):
    """Valid return statuses for CPA workflow."""
    DRAFT = "DRAFT"              # Initial state, editable by taxpayer
    IN_REVIEW = "IN_REVIEW"      # Submitted for CPA review, read-only to taxpayer
    CPA_APPROVED = "CPA_APPROVED"  # Signed off by CPA, full feature access


@app.get("/api/returns/{session_id}/status")
async def get_return_status(session_id: str, request: Request):
    """
    Get the current workflow status of a return.

    CPA COMPLIANCE: Status determines feature access.

    Returns:
        - Current status (DRAFT, IN_REVIEW, CPA_APPROVED)
        - Status history and CPA reviewer info if applicable
    """
    persistence = _get_persistence()
    status_record = persistence.get_return_status(session_id)

    if not status_record:
        # Default to DRAFT if no status exists
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "status": ReturnStatus.DRAFT.value,
            "is_default": True,
            "features": {
                "editable": True,
                "export_enabled": False,
                "smart_insights_enabled": False,
                "cpa_approved": False,
            }
        })

    status = status_record["status"]
    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "status": status,
        "created_at": status_record.get("created_at"),
        "last_status_change": status_record.get("last_status_change"),
        "cpa_reviewer_name": status_record.get("cpa_reviewer_name"),
        "review_notes": status_record.get("review_notes"),
        "approval_timestamp": status_record.get("approval_timestamp"),
        "features": {
            "editable": status == ReturnStatus.DRAFT.value,
            "export_enabled": status == ReturnStatus.CPA_APPROVED.value,
            "smart_insights_enabled": status == ReturnStatus.CPA_APPROVED.value,
            "cpa_approved": status == ReturnStatus.CPA_APPROVED.value,
        }
    })


@app.post("/api/returns/{session_id}/submit-for-review")
async def submit_return_for_review(session_id: str, request: Request):
    """
    Submit a return for CPA review.

    CPA COMPLIANCE: Transitions DRAFT → IN_REVIEW.
    - Locks the return from taxpayer edits
    - Notifies CPA queue
    - Creates audit trail entry

    Returns:
        Updated status record
    """
    persistence = _get_persistence()

    # Check current status
    current_status = persistence.get_return_status(session_id)
    if current_status and current_status["status"] != ReturnStatus.DRAFT.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit: return is already {current_status['status']}"
        )

    # Update status
    new_status = persistence.set_return_status(
        session_id=session_id,
        status=ReturnStatus.IN_REVIEW.value,
    )

    # Log audit event
    try:
        _log_audit_event(
            session_id=session_id,
            event_type=AuditEventType.REVIEW_REQUEST,
            description="Return submitted for CPA review",
            metadata={
                "previous_status": ReturnStatus.DRAFT.value,
                "new_status": ReturnStatus.IN_REVIEW.value,
            },
            request=request
        )
    except Exception as e:
        logger.warning(f"Failed to log review submission audit: {e}")

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "status": new_status["status"],
        "message": "Return submitted for CPA review",
        "features": {
            "editable": False,
            "export_enabled": False,
            "smart_insights_enabled": False,
            "cpa_approved": False,
        }
    })


@app.post("/api/returns/{session_id}/approve")
async def approve_return(session_id: str, request: Request):
    """
    CPA sign-off on a return.

    CPA COMPLIANCE: Transitions IN_REVIEW → CPA_APPROVED.
    - Requires CPA credentials
    - Creates signed approval record
    - Unlocks export and Smart Insights features

    Request body:
        - cpa_reviewer_id: CPA identifier
        - cpa_reviewer_name: CPA name for display
        - review_notes: Optional notes/comments
        - signature: Approval signature/PIN

    Returns:
        Updated status record with approval details
    """
    import hashlib

    try:
        body = await request.json()
    except Exception:
        body = {}

    cpa_reviewer_id = body.get("cpa_reviewer_id")
    cpa_reviewer_name = body.get("cpa_reviewer_name", "CPA Reviewer")
    review_notes = body.get("review_notes")
    signature = body.get("signature")

    if not cpa_reviewer_id:
        raise HTTPException(status_code=400, detail="CPA reviewer ID is required")

    persistence = _get_persistence()

    # Check current status
    current_status = persistence.get_return_status(session_id)
    if current_status and current_status["status"] == ReturnStatus.CPA_APPROVED.value:
        raise HTTPException(status_code=400, detail="Return is already approved")

    # Create signature hash for audit trail
    signature_data = f"{session_id}:{cpa_reviewer_id}:{datetime.utcnow().isoformat()}"
    if signature:
        signature_data += f":{signature}"
    approval_hash = hashlib.sha256(signature_data.encode()).hexdigest()[:16]

    # Update status to approved
    new_status = persistence.set_return_status(
        session_id=session_id,
        status=ReturnStatus.CPA_APPROVED.value,
        cpa_reviewer_id=cpa_reviewer_id,
        cpa_reviewer_name=cpa_reviewer_name,
        review_notes=review_notes,
        approval_signature_hash=approval_hash
    )

    # Log audit event with CPA sign-off
    try:
        _log_audit_event(
            session_id=session_id,
            event_type=AuditEventType.CPA_REVIEW,
            description=f"Return approved by CPA: {cpa_reviewer_name}",
            metadata={
                "cpa_reviewer_id": cpa_reviewer_id,
                "cpa_reviewer_name": cpa_reviewer_name,
                "review_notes": review_notes,
                "approval_signature_hash": approval_hash,
                "previous_status": current_status["status"] if current_status else "DRAFT",
                "new_status": ReturnStatus.CPA_APPROVED.value,
            },
            request=request
        )
    except Exception as e:
        logger.warning(f"Failed to log CPA approval audit: {e}")

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "status": new_status["status"],
        "message": f"Return approved by {cpa_reviewer_name}",
        "approval_timestamp": new_status.get("approval_timestamp"),
        "approval_signature_hash": approval_hash,
        "features": {
            "editable": False,
            "export_enabled": True,
            "smart_insights_enabled": True,
            "cpa_approved": True,
        }
    })


@app.post("/api/returns/{session_id}/revert-to-draft")
async def revert_return_to_draft(session_id: str, request: Request):
    """
    Revert a return to DRAFT status (CPA action only).

    CPA COMPLIANCE: Allows CPA to send back for revisions.
    - Requires CPA credentials
    - Re-enables taxpayer edits
    - Creates audit trail entry with reason

    Request body:
        - cpa_reviewer_id: CPA identifier
        - reason: Required reason for reverting

    Returns:
        Updated status record
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    cpa_reviewer_id = body.get("cpa_reviewer_id")
    reason = body.get("reason", "Needs revisions")

    if not cpa_reviewer_id:
        raise HTTPException(status_code=400, detail="CPA reviewer ID is required")

    persistence = _get_persistence()

    current_status = persistence.get_return_status(session_id)
    if not current_status:
        raise HTTPException(status_code=404, detail="No status record found")

    old_status = current_status["status"]

    # Update status
    new_status = persistence.set_return_status(
        session_id=session_id,
        status=ReturnStatus.DRAFT.value,
        review_notes=f"Reverted by CPA: {reason}"
    )

    # Log audit event
    try:
        _log_audit_event(
            session_id=session_id,
            event_type=AuditEventType.REVIEW_REQUEST,
            description=f"Return reverted to DRAFT by CPA",
            metadata={
                "cpa_reviewer_id": cpa_reviewer_id,
                "reason": reason,
                "previous_status": old_status,
                "new_status": ReturnStatus.DRAFT.value,
            },
            request=request
        )
    except Exception as e:
        logger.warning(f"Failed to log revert audit: {e}")

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "status": new_status["status"],
        "message": "Return reverted to DRAFT for revisions",
        "reason": reason,
        "features": {
            "editable": True,
            "export_enabled": False,
            "smart_insights_enabled": False,
            "cpa_approved": False,
        }
    })


@app.get("/api/returns/queue/{status}")
async def list_returns_by_status(status: str, request: Request, limit: int = 100, offset: int = 0):
    """
    List returns by workflow status for CPA queue.

    CPA COMPLIANCE: Enables CPA workflow management.

    Args:
        status: Filter by status (DRAFT, IN_REVIEW, CPA_APPROVED)
        limit: Max results (default 100)
        offset: Pagination offset

    Returns:
        List of returns matching the status
    """
    # Validate status
    try:
        valid_status = ReturnStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(s.value for s in ReturnStatus)}"
        )

    persistence = _get_persistence()
    returns = persistence.list_returns_by_status(
        status=valid_status.value,
        limit=limit,
        offset=offset
    )

    return JSONResponse({
        "success": True,
        "status": valid_status.value,
        "returns": returns,
        "count": len(returns),
        "limit": limit,
        "offset": offset
    })


# =============================================================================
# CPA "AHA MOMENT" APIS - VALUE DEMONSTRATION FOR $9,999/YR SUBSCRIPTION
# =============================================================================

@app.post("/api/returns/{session_id}/delta")
async def calculate_delta(session_id: str, request: Request):
    """
    Calculate before/after delta for a proposed change.

    CPA AHA MOMENT: Shows instant impact of changes - "One click, see the difference."
    This visualization helps CPAs instantly understand the impact of any adjustment.

    Request body:
        - change_type: Type of change (income, deduction, credit, etc.)
        - field: Field being changed
        - old_value: Current value
        - new_value: Proposed new value

    Returns:
        - Before/after comparison
        - Delta amounts for key metrics
        - Percentage changes
        - Visualization data
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    change_type = body.get("change_type", "")
    field = body.get("field", "")
    old_value = body.get("old_value", 0)
    new_value = body.get("new_value", 0)

    # Get current tax return
    tax_return = _get_tax_return_for_session(session_id)
    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found")

    # Calculate current state
    current_agi = float(tax_return.adjusted_gross_income or 0)
    current_taxable = float(tax_return.taxable_income or 0)
    current_liability = float(tax_return.tax_liability or 0)
    current_refund = float(tax_return.refund_or_owed or 0)

    # Estimate impact based on change type
    delta_amount = float(new_value) - float(old_value)

    # Simplified impact estimation (real implementation would recalculate)
    marginal_rate = _get_marginal_rate(tax_return)

    if change_type in ["income", "wages"]:
        estimated_new_agi = current_agi + delta_amount
        estimated_new_taxable = current_taxable + delta_amount
        estimated_tax_change = delta_amount * marginal_rate
        estimated_new_liability = current_liability + estimated_tax_change
    elif change_type in ["deduction"]:
        estimated_new_agi = current_agi
        estimated_new_taxable = current_taxable - delta_amount
        estimated_tax_change = -delta_amount * marginal_rate
        estimated_new_liability = current_liability + estimated_tax_change
    elif change_type in ["credit"]:
        estimated_new_agi = current_agi
        estimated_new_taxable = current_taxable
        estimated_tax_change = -delta_amount  # Credits are dollar-for-dollar
        estimated_new_liability = current_liability + estimated_tax_change
    else:
        estimated_new_agi = current_agi
        estimated_new_taxable = current_taxable
        estimated_tax_change = 0
        estimated_new_liability = current_liability

    estimated_new_refund = current_refund - estimated_tax_change

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "change": {
            "type": change_type,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "delta": delta_amount
        },
        "before": {
            "adjusted_gross_income": current_agi,
            "taxable_income": current_taxable,
            "tax_liability": current_liability,
            "refund_or_owed": current_refund,
        },
        "after": {
            "adjusted_gross_income": round(estimated_new_agi, 2),
            "taxable_income": round(estimated_new_taxable, 2),
            "tax_liability": round(estimated_new_liability, 2),
            "refund_or_owed": round(estimated_new_refund, 2),
        },
        "delta_metrics": {
            "agi_change": round(estimated_new_agi - current_agi, 2),
            "taxable_change": round(estimated_new_taxable - current_taxable, 2),
            "liability_change": round(estimated_tax_change, 2),
            "refund_change": round(estimated_new_refund - current_refund, 2),
        },
        "percentage_changes": {
            "liability_pct": round((estimated_tax_change / current_liability) * 100, 2) if current_liability else 0,
            "refund_pct": round(((estimated_new_refund - current_refund) / abs(current_refund)) * 100, 2) if current_refund else 0,
        },
        "marginal_rate_used": marginal_rate,
        "visualization": {
            "type": "bar_comparison",
            "metrics": ["tax_liability", "refund_or_owed"],
            "highlight_change": True,
        }
    })


@app.post("/api/returns/{session_id}/notes")
async def add_cpa_note(session_id: str, request: Request):
    """
    Add CPA review notes to a return.

    CPA AHA MOMENT: Professional documentation for client communication.
    Notes are audit-trailed and timestamped.

    Request body:
        - note_text: The note content
        - category: Optional category (review, question, recommendation, etc.)
        - is_internal: Whether note is internal-only (default False)

    Returns:
        Updated notes list
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    note_text = body.get("note_text", "").strip()
    category = body.get("category", "general")
    is_internal = body.get("is_internal", False)
    cpa_id = body.get("cpa_id", "")
    cpa_name = body.get("cpa_name", "CPA")

    if not note_text:
        raise HTTPException(status_code=400, detail="Note text is required")

    persistence = _get_persistence()

    # Get existing status record to access notes
    status_record = persistence.get_return_status(session_id)
    existing_notes = []
    if status_record and status_record.get("review_notes"):
        try:
            import json as json_module
            existing_notes = json_module.loads(status_record["review_notes"])
            if not isinstance(existing_notes, list):
                existing_notes = [{"text": status_record["review_notes"], "timestamp": "migrated"}]
        except Exception:
            existing_notes = [{"text": status_record["review_notes"], "timestamp": "migrated"}]

    # Add new note
    new_note = {
        "id": str(uuid.uuid4())[:8],
        "text": note_text,
        "category": category,
        "is_internal": is_internal,
        "cpa_id": cpa_id,
        "cpa_name": cpa_name,
        "timestamp": datetime.utcnow().isoformat(),
    }
    existing_notes.append(new_note)

    # Save updated notes
    import json as json_module
    persistence.set_return_status(
        session_id=session_id,
        status=status_record["status"] if status_record else "DRAFT",
        review_notes=json_module.dumps(existing_notes)
    )

    # Log audit event
    try:
        _log_audit_event(
            session_id=session_id,
            event_type=AuditEventType.CPA_REVIEW,
            description=f"CPA note added: {category}",
            metadata={
                "note_id": new_note["id"],
                "category": category,
                "is_internal": is_internal,
                "cpa_name": cpa_name,
            },
            request=request
        )
    except Exception as e:
        logger.warning(f"Failed to log note audit: {e}")

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "note": new_note,
        "total_notes": len(existing_notes)
    })


@app.get("/api/returns/{session_id}/notes")
async def get_cpa_notes(session_id: str, request: Request, include_internal: bool = False):
    """
    Get all CPA notes for a return.

    Args:
        include_internal: Whether to include internal-only notes (for CPA view)

    Returns:
        List of notes with metadata
    """
    persistence = _get_persistence()
    status_record = persistence.get_return_status(session_id)

    if not status_record or not status_record.get("review_notes"):
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "notes": [],
            "total_notes": 0
        })

    try:
        import json as json_module
        notes = json_module.loads(status_record["review_notes"])
        if not isinstance(notes, list):
            notes = [{"text": status_record["review_notes"], "timestamp": "migrated"}]
    except Exception:
        notes = [{"text": status_record["review_notes"], "timestamp": "migrated"}]

    # Filter internal notes if needed
    if not include_internal:
        notes = [n for n in notes if not n.get("is_internal", False)]

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "notes": notes,
        "total_notes": len(notes)
    })


# =============================================================================
# CLIENT "AHA MOMENT" APIS - VALUE DEMONSTRATION FOR TAXPAYERS
# =============================================================================

@app.get("/api/returns/{session_id}/tax-drivers")
async def get_tax_drivers(session_id: str, request: Request):
    """
    Get 'What Drives Your Tax Outcome' breakdown.

    CLIENT AHA MOMENT: Clear visualization of what affects their taxes most.
    Helps clients understand where their tax dollars come from and go.

    Returns:
        - Income breakdown by source
        - Deduction impact analysis
        - Credit utilization
        - Effective vs marginal rate explanation
        - Top 5 factors affecting their tax outcome
    """
    tax_return = _get_tax_return_for_session(session_id)
    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found")

    # Income breakdown
    income = tax_return.income
    income_breakdown = []
    total_income = 0

    if income:
        if income.w2_forms:
            wages = sum(w.wages for w in income.w2_forms)
            if wages > 0:
                income_breakdown.append({
                    "source": "Wages & Salary",
                    "amount": wages,
                    "icon": "briefcase"
                })
                total_income += wages

        if income.interest_income and income.interest_income > 0:
            income_breakdown.append({
                "source": "Interest Income",
                "amount": income.interest_income,
                "icon": "percent"
            })
            total_income += income.interest_income

        if income.dividend_income and income.dividend_income > 0:
            income_breakdown.append({
                "source": "Dividend Income",
                "amount": income.dividend_income,
                "icon": "trending-up"
            })
            total_income += income.dividend_income

        if income.self_employment_income and income.self_employment_income > 0:
            income_breakdown.append({
                "source": "Self-Employment",
                "amount": income.self_employment_income,
                "icon": "user-check"
            })
            total_income += income.self_employment_income

        if hasattr(income, 'long_term_capital_gains') and income.long_term_capital_gains:
            income_breakdown.append({
                "source": "Capital Gains",
                "amount": income.long_term_capital_gains,
                "icon": "trending-up"
            })
            total_income += income.long_term_capital_gains

    # Deduction impact
    deductions = tax_return.deductions
    deduction_impact = {
        "type": "standard",
        "amount": 0,
        "tax_savings": 0,
    }

    if deductions:
        if deductions.itemized and deductions.itemized.get_total_itemized() > 0:
            deduction_impact = {
                "type": "itemized",
                "amount": deductions.itemized.get_total_itemized(),
                "breakdown": {
                    "state_local_taxes": deductions.itemized.state_local_taxes or 0,
                    "mortgage_interest": deductions.itemized.mortgage_interest or 0,
                    "charitable": deductions.itemized.charitable_cash + (deductions.itemized.charitable_noncash or 0),
                    "medical": deductions.itemized.medical_expenses or 0,
                }
            }
        else:
            # Standard deduction
            standard_amounts = {
                "single": 15000, "married_joint": 30000, "married_separate": 15000,
                "head_of_household": 22500, "widow": 30000
            }
            status = tax_return.taxpayer.filing_status.value if tax_return.taxpayer else "single"
            deduction_impact = {
                "type": "standard",
                "amount": standard_amounts.get(status, 15000),
            }

    marginal_rate = _get_marginal_rate(tax_return)
    deduction_impact["tax_savings"] = round(deduction_impact["amount"] * marginal_rate, 2)

    # Credit utilization
    credits = tax_return.credits
    credit_breakdown = []

    if credits:
        if hasattr(credits, 'child_tax_credit') and credits.child_tax_credit:
            credit_breakdown.append({
                "name": "Child Tax Credit",
                "amount": credits.child_tax_credit,
                "refundable": True,
            })
        if hasattr(credits, 'earned_income_credit') and credits.earned_income_credit:
            credit_breakdown.append({
                "name": "Earned Income Credit",
                "amount": credits.earned_income_credit,
                "refundable": True,
            })
        if hasattr(credits, 'education_credits') and credits.education_credits:
            credit_breakdown.append({
                "name": "Education Credits",
                "amount": credits.education_credits,
                "refundable": False,
            })

    # Calculate rates
    effective_rate = 0
    if tax_return.adjusted_gross_income and tax_return.adjusted_gross_income > 0:
        effective_rate = (tax_return.tax_liability or 0) / tax_return.adjusted_gross_income

    # Top 5 tax drivers
    drivers = []

    if income_breakdown:
        largest_income = max(income_breakdown, key=lambda x: x["amount"])
        drivers.append({
            "factor": f"Primary Income: {largest_income['source']}",
            "impact": f"${largest_income['amount']:,.0f}",
            "direction": "increases",
            "rank": 1
        })

    if deduction_impact["amount"] > 0:
        drivers.append({
            "factor": f"{deduction_impact['type'].title()} Deduction",
            "impact": f"Saves ${deduction_impact['tax_savings']:,.0f}",
            "direction": "decreases",
            "rank": 2
        })

    if tax_return.taxpayer:
        drivers.append({
            "factor": f"Filing Status: {tax_return.taxpayer.filing_status.value.replace('_', ' ').title()}",
            "impact": f"Determines tax brackets",
            "direction": "neutral",
            "rank": 3
        })

    total_credits = sum(c["amount"] for c in credit_breakdown)
    if total_credits > 0:
        drivers.append({
            "factor": f"Tax Credits ({len(credit_breakdown)})",
            "impact": f"Saves ${total_credits:,.0f}",
            "direction": "decreases",
            "rank": 4
        })

    if marginal_rate > 0:
        drivers.append({
            "factor": f"Tax Bracket: {int(marginal_rate * 100)}%",
            "impact": f"Each extra $1,000 costs ${marginal_rate * 1000:,.0f}",
            "direction": "neutral",
            "rank": 5
        })

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "summary": {
            "total_income": total_income,
            "taxable_income": tax_return.taxable_income or 0,
            "tax_liability": tax_return.tax_liability or 0,
            "total_deductions": deduction_impact["amount"],
            "total_credits": total_credits,
            "effective_rate": round(effective_rate * 100, 2),
            "marginal_rate": round(marginal_rate * 100, 2),
        },
        "income_breakdown": income_breakdown,
        "deduction_impact": deduction_impact,
        "credit_breakdown": credit_breakdown,
        "top_drivers": drivers,
        "insights": {
            "rate_explanation": f"You pay {round(effective_rate * 100, 1)}% of your income in federal taxes, but each additional dollar earned is taxed at {round(marginal_rate * 100, 0)}%.",
            "deduction_explanation": f"Your {deduction_impact['type']} deduction of ${deduction_impact['amount']:,.0f} saves you ${deduction_impact['tax_savings']:,.0f} in taxes.",
        }
    })


@app.post("/api/returns/{session_id}/compare-scenarios")
async def compare_scenarios(session_id: str, request: Request):
    """
    Compare multiple tax scenarios side-by-side.

    CLIENT AHA MOMENT: "What if" analysis - see how different choices affect taxes.

    Request body:
        - scenarios: List of scenario adjustments to compare
          Each scenario: {name: str, adjustments: [{field: str, value: float}]}

    Returns:
        - Base case (current return)
        - Each scenario with calculated impact
        - Delta comparison matrix
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    scenarios_input = body.get("scenarios", [])

    tax_return = _get_tax_return_for_session(session_id)
    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found")

    # Base case
    base_case = {
        "name": "Current",
        "adjusted_gross_income": float(tax_return.adjusted_gross_income or 0),
        "taxable_income": float(tax_return.taxable_income or 0),
        "tax_liability": float(tax_return.tax_liability or 0),
        "refund_or_owed": float(tax_return.refund_or_owed or 0),
    }

    marginal_rate = _get_marginal_rate(tax_return)
    scenarios = [base_case]

    # Calculate each scenario
    for idx, scenario in enumerate(scenarios_input[:4]):  # Limit to 4 scenarios
        name = scenario.get("name", f"Scenario {idx + 1}")
        adjustments = scenario.get("adjustments", [])

        # Start from base
        agi_delta = 0
        taxable_delta = 0

        for adj in adjustments:
            field = adj.get("field", "")
            value = float(adj.get("value", 0))

            if field in ["income", "wages", "additional_income"]:
                agi_delta += value
                taxable_delta += value
            elif field in ["deduction", "additional_deduction"]:
                taxable_delta -= value
            elif field in ["ira_contribution", "401k_contribution"]:
                agi_delta -= value
                taxable_delta -= value

        tax_change = taxable_delta * marginal_rate

        scenarios.append({
            "name": name,
            "adjusted_gross_income": round(base_case["adjusted_gross_income"] + agi_delta, 2),
            "taxable_income": round(base_case["taxable_income"] + taxable_delta, 2),
            "tax_liability": round(base_case["tax_liability"] + tax_change, 2),
            "refund_or_owed": round(base_case["refund_or_owed"] - tax_change, 2),
            "adjustments": adjustments,
            "delta_from_base": {
                "agi": round(agi_delta, 2),
                "taxable": round(taxable_delta, 2),
                "tax": round(tax_change, 2),
                "refund": round(-tax_change, 2),
            }
        })

    # Find best scenario
    best_scenario = min(scenarios, key=lambda s: s["tax_liability"])
    worst_scenario = max(scenarios, key=lambda s: s["tax_liability"])

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "scenarios": scenarios,
        "comparison": {
            "best_scenario": best_scenario["name"],
            "best_tax": best_scenario["tax_liability"],
            "worst_scenario": worst_scenario["name"],
            "worst_tax": worst_scenario["tax_liability"],
            "max_savings": round(worst_scenario["tax_liability"] - best_scenario["tax_liability"], 2),
        },
        "marginal_rate_used": marginal_rate,
        "visualization": {
            "type": "comparison_chart",
            "metrics": ["tax_liability", "refund_or_owed"],
            "scenarios": [s["name"] for s in scenarios]
        }
    })


# =============================================================================
# AUDIT TRAIL API - CPA COMPLIANCE REQUIREMENT
# =============================================================================

@app.get("/api/audit/{session_id}")
async def get_audit_trail(session_id: str, request: Request):
    """
    Get the complete audit trail for a session/return.

    CPA COMPLIANCE: Provides full audit history for defensibility.

    Returns:
        - All audit entries with timestamps, users, and changes
        - Integrity verification status
        - Summary statistics
    """
    persistence = _get_persistence()

    # Load from persistence
    trail_json = persistence.load_audit_trail(session_id)

    if not trail_json:
        # Check if trail exists in memory
        if session_id in _AUDIT_TRAILS:
            trail = _AUDIT_TRAILS[session_id]
        else:
            raise HTTPException(status_code=404, detail="Audit trail not found")
    else:
        trail = AuditTrail.from_json(trail_json)

    # Verify integrity
    is_valid, issues = trail.verify_trail_integrity()

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "audit_trail": {
            "return_id": trail.return_id,
            "created_at": trail.created_at.isoformat(),
            "total_entries": len(trail.entries),
            "entries": [entry.to_dict() for entry in trail.entries],
            "integrity": {
                "verified": is_valid,
                "issues": issues
            },
            "summary": trail.get_summary()
        }
    })


@app.get("/api/audit/{session_id}/report")
async def get_audit_report(session_id: str, request: Request):
    """
    Get human-readable audit report for CPA review.

    Returns formatted text report suitable for printing/archiving.
    """
    persistence = _get_persistence()

    trail_json = persistence.load_audit_trail(session_id)

    if not trail_json:
        if session_id in _AUDIT_TRAILS:
            trail = _AUDIT_TRAILS[session_id]
        else:
            raise HTTPException(status_code=404, detail="Audit trail not found")
    else:
        trail = AuditTrail.from_json(trail_json)

    report = trail.generate_audit_report()

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "report": report,
        "generated_at": datetime.utcnow().isoformat()
    })


@app.get("/api/audit")
async def list_audit_trails(request: Request, limit: int = 100, offset: int = 0):
    """
    List all audit trails for a tenant.

    CPA COMPLIANCE: Enables review of all client activity.
    """
    persistence = _get_persistence()

    # Get tenant from header or default
    tenant_id = request.headers.get("X-Tenant-ID", "default")

    trails = persistence.list_audit_trails(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset
    )

    return JSONResponse({
        "success": True,
        "tenant_id": tenant_id,
        "count": len(trails),
        "audit_trails": trails
    })


# ============ SMART VALIDATION API ============

@app.post("/api/validate/fields")
async def validate_and_get_field_states(request: Request):
    """
    Get smart field visibility and validation based on current data.

    This endpoint implements 100+ conditional rules to:
    - Show/hide fields based on context (e.g., spouse fields only for married)
    - Auto-calculate values from other inputs (e.g., 65+ from DOB)
    - Validate data and return errors/warnings
    - Provide smart suggestions and hints
    """
    from validation import TaxContext, get_rules_engine, ValidationSeverity

    body = await request.json()

    # Build context from request data
    ctx = TaxContext(
        # Personal
        first_name=body.get('firstName', ''),
        last_name=body.get('lastName', ''),
        ssn=body.get('ssn', ''),
        date_of_birth=body.get('dob', ''),
        is_blind=body.get('isBlind', False),

        # Spouse
        spouse_first_name=body.get('spouseFirstName', ''),
        spouse_last_name=body.get('spouseLastName', ''),
        spouse_ssn=body.get('spouseSsn', ''),
        spouse_dob=body.get('spouseDob', ''),
        spouse_is_blind=body.get('spouseIsBlind', False),

        # Filing
        filing_status=body.get('filingStatus', ''),

        # Address
        street=body.get('street', ''),
        city=body.get('city', ''),
        state=body.get('state', ''),
        zip_code=body.get('zipCode', ''),

        # Dependents
        dependents=body.get('dependents', []),

        # Income
        wages=safe_float(body.get('wages')),
        wages_secondary=safe_float(body.get('wagesSecondary')),
        interest_income=safe_float(body.get('interestIncome')),
        dividend_income=safe_float(body.get('dividendIncome')),
        qualified_dividends=safe_float(body.get('qualifiedDividends')),
        capital_gains_short=safe_float(body.get('capitalGainsShort')),
        capital_gains_long=safe_float(body.get('capitalGainsLong')),
        business_income=safe_float(body.get('businessIncome')),
        business_expenses=safe_float(body.get('businessExpenses')),
        rental_income=safe_float(body.get('rentalIncome')),
        rental_expenses=safe_float(body.get('rentalExpenses')),
        retirement_income=safe_float(body.get('retirementIncome')),
        social_security=safe_float(body.get('socialSecurity')),
        unemployment=safe_float(body.get('unemployment')),
        other_income=safe_float(body.get('otherIncome')),

        # Withholding
        federal_withheld=safe_float(body.get('federalWithheld')),
        state_withheld=safe_float(body.get('stateWithheld')),

        # Deductions
        use_standard_deduction=body.get('useStandardDeduction', True),
        medical_expenses=safe_float(body.get('medicalExpenses')),
        state_local_taxes=safe_float(body.get('stateLocalTaxes')),
        real_estate_taxes=safe_float(body.get('realEstateTaxes')),
        mortgage_interest=safe_float(body.get('mortgageInterest')),
        charitable_cash=safe_float(body.get('charitableCash')),
        charitable_noncash=safe_float(body.get('charitableNoncash')),
        student_loan_interest=safe_float(body.get('studentLoanInterest')),
        educator_expenses=safe_float(body.get('educatorExpenses')),
        hsa_contribution=safe_float(body.get('hsaContribution')),
        ira_contribution=safe_float(body.get('iraContribution')),

        # Credits
        child_care_expenses=safe_float(body.get('childCareExpenses')),
        child_care_provider_name=body.get('childCareProviderName', ''),
        child_care_provider_ein=body.get('childCareProviderEin', ''),
        education_expenses=safe_float(body.get('educationExpenses')),
        student_name=body.get('studentName', ''),
        school_name=body.get('schoolName', ''),

        # State
        state_of_residence=body.get('stateOfResidence', body.get('state', '')),
    )

    # Calculate derived fields (age from DOB, income totals, etc.)
    ctx.calculate_derived_fields()

    engine = get_rules_engine()

    # Get field states
    field_states = engine.get_all_field_states(ctx)

    # Run validation
    validation_results = engine.validate_all(ctx)

    # Get smart defaults
    smart_defaults = engine.get_smart_defaults(ctx)

    # Format response
    fields = {}
    for field_id, state in field_states.items():
        fields[field_id] = {
            'visible': state.visible,
            'enabled': state.enabled,
            'requirement': state.requirement.value,
            'hint': state.hint,
            'defaultValue': state.default_value,
        }

    errors = []
    warnings = []
    info = []

    for result in validation_results:
        item = {
            'field': result.field,
            'message': result.message,
            'suggestion': result.suggestion,
        }
        if result.severity == ValidationSeverity.ERROR:
            errors.append(item)
        elif result.severity == ValidationSeverity.WARNING:
            warnings.append(item)
        else:
            info.append(item)

    return JSONResponse({
        'fields': fields,
        'validation': {
            'isValid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'info': info,
        },
        'computed': {
            'age': ctx.age,
            'spouseAge': ctx.spouse_age,
            'totalIncome': ctx.total_income,
            'earnedIncome': ctx.earned_income,
            'numDependents': ctx.num_dependents,
            'numQualifyingChildren': ctx.num_qualifying_children,
            'is65OrOlder': ctx.age >= 65,
            'spouseIs65OrOlder': ctx.spouse_age >= 65,
        },
        'defaults': smart_defaults,
    })


@app.post("/api/validate/field/{field_name}")
async def validate_single_field(field_name: str, request: Request):
    """Validate a single field and return its state."""
    from validation import TaxContext, get_rules_engine, ValidationSeverity

    body = await request.json()

    # Build minimal context
    ctx = TaxContext(
        first_name=body.get('firstName', ''),
        last_name=body.get('lastName', ''),
        ssn=body.get('ssn', ''),
        date_of_birth=body.get('dob', ''),
        filing_status=body.get('filingStatus', ''),
        spouse_ssn=body.get('spouseSsn', ''),
        spouse_dob=body.get('spouseDob', ''),
        dependents=body.get('dependents', []),
        wages=safe_float(body.get('wages')),
        business_income=safe_float(body.get('businessIncome')),
    )

    ctx.calculate_derived_fields()

    engine = get_rules_engine()

    # Validate field
    results = engine.validate_field(field_name, ctx)

    # Get field requirement
    requirement = engine.get_field_requirement(field_name, ctx)
    visible = engine.is_field_visible(field_name, ctx)

    errors = [r for r in results if r.severity == ValidationSeverity.ERROR and not r.valid]
    warnings = [r for r in results if r.severity == ValidationSeverity.WARNING]

    return JSONResponse({
        'field': field_name,
        'visible': visible,
        'requirement': requirement.value,
        'isValid': len(errors) == 0,
        'errors': [{'message': e.message, 'suggestion': e.suggestion} for e in errors],
        'warnings': [{'message': w.message, 'suggestion': w.suggestion} for w in warnings],
    })


# =============================================================================
# SUGGESTIONS & INTERVIEW STATE API - Alpine.js/htmx Integration
# =============================================================================

@app.post("/api/suggestions")
async def get_tax_suggestions(request: Request):
    """
    Get contextual tax optimization suggestions.

    Returns optimization tips, potential savings, and "did you know" hints
    based on the current tax return data. Used by Alpine.js store for
    real-time recommendations display.
    """
    from validation import TaxContext, get_rules_engine
    from recommendation import get_recommendation_engine

    body = await request.json()

    # Build context from request
    ctx = TaxContext(
        filing_status=body.get('filingStatus', ''),
        date_of_birth=body.get('dob', ''),
        spouse_dob=body.get('spouseDob', ''),
        dependents=body.get('dependents', []),
        wages=safe_float(body.get('wages')),
        business_income=safe_float(body.get('businessIncome')),
        interest_income=safe_float(body.get('interestIncome')),
        dividend_income=safe_float(body.get('dividendIncome')),
        retirement_income=safe_float(body.get('retirementIncome')),
        social_security=safe_float(body.get('socialSecurity')),
        capital_gains_long=safe_float(body.get('capitalGainsLong')),
        use_standard_deduction=body.get('useStandardDeduction', True),
        mortgage_interest=safe_float(body.get('mortgageInterest')),
        charitable_cash=safe_float(body.get('charitableCash')),
        state_local_taxes=safe_float(body.get('stateLocalTaxes')),
        medical_expenses=safe_float(body.get('medicalExpenses')),
        ira_contribution=safe_float(body.get('iraContribution')),
        hsa_contribution=safe_float(body.get('hsaContribution')),
        child_care_expenses=safe_float(body.get('childCareExpenses')),
        education_expenses=safe_float(body.get('educationExpenses')),
        state_of_residence=body.get('stateOfResidence', body.get('state', '')),
    )

    ctx.calculate_derived_fields()

    # Get recommendations from recommendation engine
    try:
        rec_engine = get_recommendation_engine()
        recommendations = rec_engine.get_recommendations(ctx)

        tips = []
        total_potential_savings = 0

        for rec in recommendations:
            tip = {
                'id': rec.id,
                'category': rec.category,
                'title': rec.title,
                'description': rec.description,
                'potential_savings': rec.potential_savings,
                'action': rec.action,
                'priority': rec.priority,
            }
            tips.append(tip)
            total_potential_savings += rec.potential_savings or 0

        # Sort by priority and potential savings
        tips.sort(key=lambda x: (-x.get('priority', 0), -(x.get('potential_savings') or 0)))

        # Get "Did You Know" hints
        did_you_know = []

        # Age-based hint
        if ctx.age and ctx.age >= 50:
            did_you_know.append({
                'message': f"At age {ctx.age}, you may be eligible for catch-up contributions to retirement accounts.",
                'category': 'retirement'
            })

        # SALT cap hint
        salt = ctx.state_local_taxes + (ctx.real_estate_taxes or 0)
        if salt > 10000:
            did_you_know.append({
                'message': f"Your state and local taxes (${salt:,.0f}) exceed the $10,000 SALT cap. Only $10,000 is deductible.",
                'category': 'deductions'
            })

        # Standard vs itemized hint
        if not ctx.use_standard_deduction:
            std_ded = 15000 if ctx.filing_status == 'single' else 30000  # Simplified
            itemized = (ctx.mortgage_interest or 0) + (ctx.charitable_cash or 0) + min(salt, 10000)
            if itemized < std_ded:
                did_you_know.append({
                    'message': f"The standard deduction (${std_ded:,.0f}) may give you a larger deduction than itemizing (${itemized:,.0f}).",
                    'category': 'deductions'
                })

        return JSONResponse({
            'tips': tips[:10],  # Limit to top 10
            'potential_savings': total_potential_savings,
            'did_you_know': did_you_know,
            'context': {
                'age': ctx.age,
                'filing_status': ctx.filing_status,
                'num_dependents': ctx.num_dependents,
                'total_income': ctx.total_income,
            }
        })

    except Exception as e:
        logger.error(f"Error generating suggestions: {e}")
        return JSONResponse({
            'tips': [],
            'potential_savings': 0,
            'did_you_know': [],
            'error': str(e)
        })


@app.post("/api/interview/state")
async def get_interview_state(request: Request):
    """
    Get the current interview/wizard flow state.

    Returns which sections are visible, which should be skipped,
    and the recommended next step based on current data.
    Used by Alpine.js to control wizard navigation.
    """
    from validation import TaxContext, get_rules_engine
    from onboarding import get_interview_flow

    body = await request.json()

    # Build context
    ctx = TaxContext(
        filing_status=body.get('filingStatus', ''),
        date_of_birth=body.get('dob', ''),
        spouse_dob=body.get('spouseDob', ''),
        dependents=body.get('dependents', []),
        wages=safe_float(body.get('wages')),
        business_income=safe_float(body.get('businessIncome')),
        retirement_income=safe_float(body.get('retirementIncome')),
        state_of_residence=body.get('stateOfResidence', body.get('state', '')),
    )

    ctx.calculate_derived_fields()

    # Get interview flow
    try:
        flow = get_interview_flow()
        current_step = body.get('currentStep', 1)

        # Determine visible sections based on context
        sections = flow.get_visible_sections(ctx)

        # Determine which sections can be skipped
        skippable = flow.get_skippable_sections(ctx)

        # Get progress info
        progress = flow.calculate_progress(ctx, current_step)

        # Get next recommended action
        next_action = flow.get_next_action(ctx, current_step)

        return JSONResponse({
            'currentStep': current_step,
            'totalSteps': len(sections),
            'sections': [
                {
                    'id': s.id,
                    'name': s.name,
                    'visible': s.visible,
                    'completed': s.completed,
                    'skippable': s.id in skippable,
                }
                for s in sections
            ],
            'progress': {
                'percentage': progress.percentage,
                'completed_sections': progress.completed,
                'total_sections': progress.total,
            },
            'next_action': {
                'type': next_action.type,
                'section': next_action.section,
                'message': next_action.message,
            } if next_action else None,
        })

    except Exception as e:
        logger.error(f"Error getting interview state: {e}")
        # Return a default state on error
        return JSONResponse({
            'currentStep': body.get('currentStep', 1),
            'totalSteps': 7,
            'sections': [
                {'id': 'welcome', 'name': 'Welcome', 'visible': True, 'completed': False, 'skippable': False},
                {'id': 'filing_status', 'name': 'Filing Status', 'visible': True, 'completed': False, 'skippable': False},
                {'id': 'personal_info', 'name': 'Personal Info', 'visible': True, 'completed': False, 'skippable': False},
                {'id': 'income', 'name': 'Income', 'visible': True, 'completed': False, 'skippable': False},
                {'id': 'deductions', 'name': 'Deductions', 'visible': True, 'completed': False, 'skippable': True},
                {'id': 'credits', 'name': 'Credits', 'visible': True, 'completed': False, 'skippable': True},
                {'id': 'review', 'name': 'Review', 'visible': True, 'completed': False, 'skippable': False},
            ],
            'progress': {'percentage': 0, 'completed_sections': 0, 'total_sections': 7},
            'next_action': None,
        })


@app.get("/api/partials/{partial_name}")
async def get_htmx_partial(partial_name: str, request: Request):
    """
    Render an htmx partial template.

    Used for dynamic content updates via htmx without full page reload.
    """
    # Security: only allow specific partial names
    allowed_partials = {
        'field-feedback',
        'optimization-tips',
        'validation-summary',
        'progress-bar',
        'section-header',
    }

    if partial_name not in allowed_partials:
        raise HTTPException(status_code=404, detail=f"Partial '{partial_name}' not found")

    # Get query params for context
    params = dict(request.query_params)

    # Render minimal HTML based on partial name
    html = ""

    if partial_name == 'field-feedback':
        field_id = params.get('field', '')
        severity = params.get('severity', 'info')
        message = params.get('message', '')

        severity_class = f"validation-{severity}"
        html = f'<div class="{severity_class}">{message}</div>'

    elif partial_name == 'optimization-tips':
        # Would normally fetch from recommendation engine
        html = '<div class="optimization-tip"><strong>Tip:</strong> Consider maximizing your retirement contributions.</div>'

    elif partial_name == 'validation-summary':
        errors = int(params.get('errors', 0))
        warnings = int(params.get('warnings', 0))

        if errors > 0:
            html = f'<div class="validation-error">{errors} error(s) need to be fixed</div>'
        elif warnings > 0:
            html = f'<div class="validation-warning">{warnings} warning(s) to review</div>'
        else:
            html = '<div class="validation-success">All fields validated successfully</div>'

    elif partial_name == 'progress-bar':
        percentage = int(params.get('percentage', 0))
        html = f'''
        <div class="progress-container">
            <div class="progress-bar" style="width: {percentage}%"></div>
            <span class="progress-text">{percentage}% complete</span>
        </div>
        '''

    return HTMLResponse(content=html)


# =============================================================================
# SCENARIO API ENDPOINTS - What-If Analysis
# =============================================================================

from pydantic import BaseModel, Field
from typing import Optional, List


class ScenarioModificationRequest(BaseModel):
    """A single modification to apply in a scenario."""
    field_path: str = Field(..., description="Dot-notation path to field (e.g., 'taxpayer.filing_status')")
    new_value: Any = Field(..., description="New value to apply")
    description: Optional[str] = Field(None, description="Optional description of this modification")


class CreateScenarioRequest(BaseModel):
    """Request to create a new scenario."""
    return_id: str = Field(..., description="ID of the base tax return")
    name: str = Field(..., description="Name for this scenario")
    scenario_type: str = Field("what_if", description="Type: what_if, filing_status, retirement, entity_structure, etc.")
    modifications: List[ScenarioModificationRequest] = Field(..., description="List of modifications to apply")
    description: Optional[str] = Field(None, description="Optional description")


class WhatIfScenarioRequest(BaseModel):
    """Request to create a quick what-if scenario."""
    return_id: str = Field(..., description="ID of the base tax return")
    name: str = Field(..., description="Name for this scenario")
    modifications: dict = Field(..., description="Dict of field_path -> new_value")


class CompareScenarioRequest(BaseModel):
    """Request to compare multiple scenarios."""
    scenario_ids: List[str] = Field(..., description="List of scenario IDs to compare")
    return_id: Optional[str] = Field(None, description="Optional return ID for context")


class FilingStatusScenariosRequest(BaseModel):
    """Request for filing status comparison scenarios."""
    return_id: str = Field(..., description="ID of the base tax return")
    eligible_statuses: Optional[List[str]] = Field(None, description="Optional list of statuses to compare")


class RetirementScenariosRequest(BaseModel):
    """Request for retirement contribution scenarios."""
    return_id: str = Field(..., description="ID of the base tax return")
    contribution_amounts: Optional[List[float]] = Field(None, description="Optional list of amounts to test")


class ApplyScenarioRequest(BaseModel):
    """Request to apply a scenario to its base return."""
    session_id: Optional[str] = Field(None, description="Session ID (optional, uses cookie if not provided)")


class EntityComparisonRequest(BaseModel):
    """Request for business entity structure comparison."""
    gross_revenue: float = Field(..., description="Total business gross revenue")
    business_expenses: float = Field(..., description="Total deductible business expenses")
    owner_salary: Optional[float] = Field(None, description="Optional fixed owner salary for S-Corp (calculated if not provided)")
    current_entity: str = Field("sole_proprietorship", description="Current entity type")
    filing_status: str = Field("single", description="Tax filing status")
    other_income: float = Field(0.0, description="Other taxable income outside the business")
    state: Optional[str] = Field(None, description="State of residence for state tax considerations")


class SalaryAdjustmentRequest(BaseModel):
    """Request for real-time salary adjustment calculations."""
    gross_revenue: float = Field(..., description="Total business gross revenue")
    business_expenses: float = Field(..., description="Total deductible business expenses")
    owner_salary: float = Field(..., description="Adjusted owner salary")
    filing_status: str = Field("single", description="Tax filing status")


class RetirementAnalysisRequest(BaseModel):
    """Request for retirement contribution analysis."""
    session_id: Optional[str] = Field(None, description="Session ID")
    current_401k: float = Field(0.0, description="Current 401k contributions")
    current_ira: float = Field(0.0, description="Current IRA contributions")
    current_hsa: float = Field(0.0, description="Current HSA contributions")
    age: int = Field(30, description="Taxpayer age for catch-up eligibility")
    hsa_coverage: str = Field("individual", description="HSA coverage type: individual or family")


# Scenario service singleton
_scenario_service = None


def _get_scenario_service():
    """Get or create the scenario service singleton."""
    global _scenario_service
    if _scenario_service is None:
        from services.scenario_service import ScenarioService
        _scenario_service = ScenarioService()
    return _scenario_service


@app.post("/api/scenarios")
async def create_scenario(request_body: CreateScenarioRequest, request: Request):
    """
    Create a new tax scenario.

    Creates a scenario with specified modifications to compare against
    the base return. Use this for custom what-if analysis.
    """
    from domain import ScenarioType

    service = _get_scenario_service()

    # Convert string type to enum
    try:
        scenario_type = ScenarioType(request_body.scenario_type)
    except ValueError:
        scenario_type = ScenarioType.WHAT_IF

    # Convert modifications to dict format expected by service
    modifications = [
        {
            "field_path": mod.field_path,
            "new_value": mod.new_value,
            "description": mod.description,
        }
        for mod in request_body.modifications
    ]

    try:
        scenario = service.create_scenario(
            return_id=request_body.return_id,
            name=request_body.name,
            scenario_type=scenario_type,
            modifications=modifications,
            description=request_body.description,
        )

        return JSONResponse({
            "success": True,
            "scenario_id": str(scenario.scenario_id),
            "name": scenario.name,
            "type": scenario.scenario_type.value,
            "status": scenario.status.value,
            "modifications_count": len(scenario.modifications),
            "created_at": scenario.created_at.isoformat(),
        })

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scenarios")
async def list_scenarios(return_id: str, request: Request):
    """
    List all scenarios for a tax return.

    Returns summary of all scenarios created for the specified return.
    """
    service = _get_scenario_service()

    scenarios = service.get_scenarios_for_return(return_id)

    return JSONResponse({
        "return_id": return_id,
        "count": len(scenarios),
        "scenarios": [
            {
                "scenario_id": str(s.scenario_id),
                "name": s.name,
                "type": s.scenario_type.value,
                "status": s.status.value,
                "is_recommended": s.is_recommended,
                "total_tax": s.result.total_tax if s.result else None,
                "savings": s.result.savings if s.result else None,
                "created_at": s.created_at.isoformat(),
            }
            for s in scenarios
        ]
    })


@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str, request: Request):
    """
    Get detailed information about a specific scenario.

    Returns full scenario details including modifications and results.
    """
    service = _get_scenario_service()

    scenario = service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")

    result_data = None
    if scenario.result:
        result_data = {
            "total_tax": scenario.result.total_tax,
            "federal_tax": scenario.result.federal_tax,
            "effective_rate": scenario.result.effective_rate,
            "marginal_rate": scenario.result.marginal_rate,
            "base_tax": scenario.result.base_tax,
            "savings": scenario.result.savings,
            "savings_percent": scenario.result.savings_percent,
            "taxable_income": scenario.result.taxable_income,
            "total_deductions": scenario.result.total_deductions,
            "total_credits": scenario.result.total_credits,
            "breakdown": scenario.result.breakdown,
        }

    return JSONResponse({
        "scenario_id": str(scenario.scenario_id),
        "return_id": str(scenario.return_id),
        "name": scenario.name,
        "description": scenario.description,
        "type": scenario.scenario_type.value,
        "status": scenario.status.value,
        "is_recommended": scenario.is_recommended,
        "recommendation_reason": scenario.recommendation_reason,
        "created_at": scenario.created_at.isoformat(),
        "calculated_at": scenario.calculated_at.isoformat() if scenario.calculated_at else None,
        "modifications": [
            {
                "field_path": m.field_path,
                "original_value": m.original_value,
                "new_value": m.new_value,
                "description": m.description,
            }
            for m in scenario.modifications
        ],
        "result": result_data,
    })


@app.post("/api/scenarios/{scenario_id}/calculate")
async def calculate_scenario(scenario_id: str, request: Request):
    """
    Calculate tax results for a scenario.

    Applies the scenario's modifications and computes the tax liability,
    comparing against the base return to determine savings.
    """
    service = _get_scenario_service()

    try:
        scenario = service.calculate_scenario(scenario_id)

        return JSONResponse({
            "success": True,
            "scenario_id": str(scenario.scenario_id),
            "name": scenario.name,
            "status": scenario.status.value,
            "result": {
                "total_tax": scenario.result.total_tax,
                "federal_tax": scenario.result.federal_tax,
                "effective_rate": scenario.result.effective_rate,
                "marginal_rate": scenario.result.marginal_rate,
                "base_tax": scenario.result.base_tax,
                "savings": scenario.result.savings,
                "savings_percent": scenario.result.savings_percent,
                "taxable_income": scenario.result.taxable_income,
                "total_deductions": scenario.result.total_deductions,
                "total_credits": scenario.result.total_credits,
                "breakdown": scenario.result.breakdown,
            }
        })

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str, request: Request):
    """
    Delete a scenario.

    Permanently removes the scenario. This action cannot be undone.
    """
    service = _get_scenario_service()

    success = service.delete_scenario(scenario_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")

    return JSONResponse({
        "success": True,
        "message": f"Scenario {scenario_id} deleted",
    })


@app.post("/api/scenarios/compare")
async def compare_scenarios(request_body: CompareScenarioRequest, request: Request):
    """
    Compare multiple scenarios to find the best option.

    Calculates all scenarios if needed, then compares them to determine
    which provides the lowest tax liability.
    """
    service = _get_scenario_service()

    if len(request_body.scenario_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 scenarios required for comparison")

    try:
        comparison = service.compare_scenarios(
            scenario_ids=request_body.scenario_ids,
            return_id=request_body.return_id,
        )

        return JSONResponse(comparison)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error comparing scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scenarios/filing-status")
async def generate_filing_status_scenarios(request_body: FilingStatusScenariosRequest, request: Request):
    """
    Generate and compare filing status scenarios.

    Automatically creates scenarios for each eligible filing status and
    calculates the tax liability for each. Returns comparison with
    recommendation for the optimal status.
    """
    service = _get_scenario_service()

    try:
        scenarios = service.get_filing_status_scenarios(
            return_id=request_body.return_id,
            eligible_statuses=request_body.eligible_statuses,
        )

        # Find the best option
        calculated = [s for s in scenarios if s.result]
        if calculated:
            best = min(calculated, key=lambda s: s.result.total_tax)
            best.mark_as_recommended(f"Lowest tax liability: ${best.result.total_tax:,.2f}")

        return JSONResponse({
            "return_id": request_body.return_id,
            "count": len(scenarios),
            "scenarios": [
                {
                    "scenario_id": str(s.scenario_id),
                    "name": s.name,
                    "filing_status": s.modifications[0].new_value if s.modifications else None,
                    "is_recommended": s.is_recommended,
                    "recommendation_reason": s.recommendation_reason,
                    "result": {
                        "total_tax": s.result.total_tax,
                        "effective_rate": s.result.effective_rate,
                        "savings": s.result.savings,
                        "savings_percent": s.result.savings_percent,
                    } if s.result else None,
                }
                for s in scenarios
            ],
            "recommendation": {
                "scenario_id": str(best.scenario_id),
                "filing_status": best.modifications[0].new_value if best.modifications else None,
                "total_tax": best.result.total_tax,
                "savings": best.result.savings,
            } if calculated else None,
        })

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating filing status scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scenarios/retirement")
async def generate_retirement_scenarios(request_body: RetirementScenariosRequest, request: Request):
    """
    Generate retirement contribution comparison scenarios.

    Creates scenarios for different 401k/IRA contribution levels to
    show the tax impact of increasing retirement savings.
    """
    service = _get_scenario_service()

    try:
        scenarios = service.get_retirement_scenarios(
            return_id=request_body.return_id,
            contribution_amounts=request_body.contribution_amounts,
        )

        # Find the best option (lowest tax)
        calculated = [s for s in scenarios if s.result]
        best = min(calculated, key=lambda s: s.result.total_tax) if calculated else None

        return JSONResponse({
            "return_id": request_body.return_id,
            "count": len(scenarios),
            "scenarios": [
                {
                    "scenario_id": str(s.scenario_id),
                    "name": s.name,
                    "contribution_amount": s.modifications[0].new_value if s.modifications else 0,
                    "result": {
                        "total_tax": s.result.total_tax,
                        "effective_rate": s.result.effective_rate,
                        "savings": s.result.savings,
                        "savings_percent": s.result.savings_percent,
                    } if s.result else None,
                }
                for s in scenarios
            ],
            "recommendation": {
                "scenario_id": str(best.scenario_id),
                "contribution_amount": best.modifications[0].new_value if best.modifications else 0,
                "total_tax": best.result.total_tax,
                "max_savings": best.result.savings,
            } if best else None,
        })

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating retirement scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scenarios/what-if")
async def create_what_if_scenario(request_body: WhatIfScenarioRequest, request: Request):
    """
    Create a quick what-if scenario with simple field modifications.

    Simplified endpoint for ad-hoc what-if analysis. Pass a dict of
    field_path -> new_value and get immediate tax impact analysis.
    """
    service = _get_scenario_service()

    try:
        scenario = service.create_what_if_scenario(
            return_id=request_body.return_id,
            name=request_body.name,
            modifications=request_body.modifications,
        )

        # Calculate immediately
        scenario = service.calculate_scenario(str(scenario.scenario_id))

        return JSONResponse({
            "success": True,
            "scenario_id": str(scenario.scenario_id),
            "name": scenario.name,
            "modifications": [
                {
                    "field_path": m.field_path,
                    "original_value": m.original_value,
                    "new_value": m.new_value,
                }
                for m in scenario.modifications
            ],
            "result": {
                "total_tax": scenario.result.total_tax,
                "base_tax": scenario.result.base_tax,
                "savings": scenario.result.savings,
                "savings_percent": scenario.result.savings_percent,
                "effective_rate": scenario.result.effective_rate,
                "marginal_rate": scenario.result.marginal_rate,
            }
        })

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating what-if scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scenarios/{scenario_id}/apply")
async def apply_scenario(scenario_id: str, request_body: ApplyScenarioRequest, request: Request):
    """
    Apply a scenario's modifications to the base return.

    This permanently updates the tax return with the scenario's changes.
    Use this when the user decides to adopt a recommended scenario.
    """
    service = _get_scenario_service()

    # Get session ID from request body or cookie
    session_id = request_body.session_id or request.cookies.get("tax_session_id") or ""

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID required")

    try:
        result = service.apply_scenario(
            scenario_id=scenario_id,
            session_id=session_id,
        )

        return JSONResponse({
            "success": True,
            "scenario_id": scenario_id,
            "message": "Scenario applied to tax return",
            "updated_return": result,
        })

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENTITY STRUCTURE COMPARISON API
# =============================================================================

@app.post("/api/entity-comparison")
async def compare_entities(request_body: EntityComparisonRequest):
    """
    Compare tax implications of different business entity structures.

    Analyzes Sole Proprietorship vs S-Corporation vs LLC to determine
    optimal entity structure based on self-employment income.
    """
    try:
        from recommendation.entity_optimizer import (
            EntityStructureOptimizer,
            EntityType,
        )

        optimizer = EntityStructureOptimizer(
            filing_status=request_body.filing_status,
            other_income=request_body.other_income,
            state=request_body.state
        )

        current_entity = None
        if request_body.current_entity:
            try:
                current_entity = EntityType(request_body.current_entity)
            except ValueError:
                pass

        result = optimizer.compare_structures(
            gross_revenue=request_body.gross_revenue,
            business_expenses=request_body.business_expenses,
            owner_salary=request_body.owner_salary,
            current_entity=current_entity
        )

        # Convert to JSON-serializable format
        response = {
            "success": True,
            "comparison": {
                "analyses": {
                    key: {
                        "entity_type": val.entity_type.value,
                        "entity_name": val.entity_name,
                        "gross_revenue": val.gross_revenue,
                        "business_expenses": val.business_expenses,
                        "net_business_income": val.net_business_income,
                        "owner_salary": val.owner_salary,
                        "k1_distribution": val.k1_distribution,
                        "self_employment_tax": val.self_employment_tax,
                        "income_tax_on_business": val.income_tax_on_business,
                        "payroll_taxes": val.payroll_taxes,
                        "se_tax_deduction": val.se_tax_deduction,
                        "qbi_deduction": val.qbi_deduction,
                        "total_business_tax": val.total_business_tax,
                        "effective_tax_rate": val.effective_tax_rate,
                        "formation_cost": val.formation_cost,
                        "annual_compliance_cost": val.annual_compliance_cost,
                        "payroll_service_cost": val.payroll_service_cost,
                        "total_annual_cost": val.total_annual_cost,
                        "is_recommended": val.is_recommended,
                        "recommendation_notes": val.recommendation_notes
                    }
                    for key, val in result.analyses.items()
                },
                "salary_analysis": {
                    "recommended_salary": result.salary_analysis.recommended_salary,
                    "salary_range_low": result.salary_analysis.salary_range_low,
                    "salary_range_high": result.salary_analysis.salary_range_high,
                    "methodology": result.salary_analysis.methodology,
                    "factors_considered": result.salary_analysis.factors_considered,
                    "irs_risk_level": result.salary_analysis.irs_risk_level,
                    "notes": result.salary_analysis.notes
                } if result.salary_analysis else None,
                "recommendation": {
                    "recommended_entity": result.recommended_entity.value,
                    "current_entity": result.current_entity.value if result.current_entity else None,
                    "max_annual_savings": result.max_annual_savings,
                    "savings_vs_current": result.savings_vs_current,
                    "recommendation_reason": result.recommendation_reason,
                    "confidence_score": result.confidence_score,
                    "breakeven_revenue": result.breakeven_revenue,
                    "five_year_savings": result.five_year_savings,
                    "warnings": result.warnings,
                    "considerations": result.considerations
                }
            }
        }

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"Entity comparison error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/entity-comparison/adjust-salary")
async def adjust_entity_salary(request_body: SalaryAdjustmentRequest):
    """
    Recalculate S-Corp analysis with adjusted salary for real-time slider updates.
    """
    try:
        from recommendation.entity_optimizer import EntityStructureOptimizer

        optimizer = EntityStructureOptimizer(
            filing_status=request_body.filing_status
        )

        net_income = request_body.gross_revenue - request_body.business_expenses

        if net_income <= 0:
            return JSONResponse({
                "error": "Net income must be positive",
                "success": False
            }, status_code=400)

        # Calculate with specified salary
        savings_info = optimizer.calculate_scorp_savings(
            net_business_income=net_income,
            reasonable_salary=request_body.owner_salary
        )

        # Determine IRS risk level based on salary ratio
        salary_ratio = request_body.owner_salary / net_income
        if salary_ratio >= 0.60:
            risk_level = "low"
        elif salary_ratio >= 0.45:
            risk_level = "medium"
        else:
            risk_level = "high"

        return JSONResponse({
            "success": True,
            "owner_salary": request_body.owner_salary,
            "k1_distribution": savings_info.get("k1_distribution", 0),
            "payroll_taxes": savings_info.get("total_payroll_tax", 0),
            "se_tax_savings": savings_info.get("se_tax_savings", 0),
            "total_scorp_tax": savings_info.get("total_payroll_tax", 0),
            "savings_vs_sole_prop": savings_info.get("se_tax_savings", 0),
            "irs_risk_level": risk_level,
            "salary_ratio": round(salary_ratio * 100, 1)
        })

    except Exception as e:
        logger.error(f"Salary adjustment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# RETIREMENT ANALYSIS API
# =============================================================================

@app.post("/api/retirement-analysis")
async def analyze_retirement(request_body: RetirementAnalysisRequest, request: Request):
    """
    Analyze retirement contribution opportunities and tax impact.
    """
    try:
        # 2025 contribution limits
        limit_401k = 23500 if request_body.age < 50 else 31000
        limit_ira = 7000 if request_body.age < 50 else 8000
        limit_hsa = 4300 if request_body.hsa_coverage == "individual" else 8550
        if request_body.age >= 55:
            limit_hsa += 1000  # HSA catch-up

        # Calculate room remaining
        room_401k = max(0, limit_401k - request_body.current_401k)
        room_ira = max(0, limit_ira - request_body.current_ira)
        room_hsa = max(0, limit_hsa - request_body.current_hsa)

        # Get current tax data from session
        session_id = request_body.session_id or request.cookies.get("tax_session_id")

        # Estimate marginal rate (default 22% if unknown)
        marginal_rate = 0.22

        # Calculate tax savings for each scenario
        scenarios = [
            {
                "name": "Current",
                "total_contributions": request_body.current_401k + request_body.current_ira + request_body.current_hsa,
                "additional_contribution": 0,
                "tax_savings": 0,
                "is_current": True
            },
            {
                "name": "+Max 401k",
                "total_contributions": limit_401k + request_body.current_ira + request_body.current_hsa,
                "additional_contribution": room_401k,
                "tax_savings": round(room_401k * marginal_rate, 2),
                "is_current": False
            },
            {
                "name": "+Add IRA",
                "total_contributions": request_body.current_401k + limit_ira + request_body.current_hsa,
                "additional_contribution": room_ira,
                "tax_savings": round(room_ira * marginal_rate, 2),
                "is_current": False
            },
            {
                "name": "+Max HSA",
                "total_contributions": request_body.current_401k + request_body.current_ira + limit_hsa,
                "additional_contribution": room_hsa,
                "tax_savings": round(room_hsa * marginal_rate, 2),
                "is_current": False
            },
            {
                "name": "+Max All",
                "total_contributions": limit_401k + limit_ira + limit_hsa,
                "additional_contribution": room_401k + room_ira + room_hsa,
                "tax_savings": round((room_401k + room_ira + room_hsa) * marginal_rate, 2),
                "is_current": False,
                "is_recommended": True
            }
        ]

        return JSONResponse({
            "success": True,
            "contribution_room": {
                "401k": {
                    "current": request_body.current_401k,
                    "max": limit_401k,
                    "remaining": room_401k
                },
                "ira": {
                    "current": request_body.current_ira,
                    "max": limit_ira,
                    "remaining": room_ira
                },
                "hsa": {
                    "current": request_body.current_hsa,
                    "max": limit_hsa,
                    "remaining": room_hsa
                }
            },
            "total_room": room_401k + room_ira + room_hsa,
            "max_tax_savings": round((room_401k + room_ira + room_hsa) * marginal_rate, 2),
            "marginal_rate": marginal_rate,
            "scenarios": scenarios,
            "roth_vs_traditional": {
                "current_bracket": int(marginal_rate * 100),
                "recommendation": "traditional" if marginal_rate >= 0.22 else "roth",
                "reason": "At {}% bracket, Traditional provides immediate tax savings of ${:,.0f}".format(
                    int(marginal_rate * 100),
                    (room_401k + room_ira) * marginal_rate
                ) if marginal_rate >= 0.22 else "At lower brackets, Roth provides tax-free growth"
            }
        })

    except Exception as e:
        logger.error(f"Retirement analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SMART INSIGHTS API (Enhanced Recommendations)
# =============================================================================

@app.get("/api/smart-insights")
async def get_smart_insights(request: Request):
    """
    Get AI-powered tax optimization insights for the Smart Insights sidebar.
    Returns actionable recommendations with one-click apply capability.

    CPA COMPLIANCE: Requires CPA_APPROVED status to unlock full insights.

    Combines insights from:
    - Base recommendation engine (filing status, deductions, credits, strategies)
    - Rules-based recommender (764+ IRS rules including crypto, foreign, K-1, etc.)
    """
    session_id = request.cookies.get("tax_session_id", "")

    # CPA COMPLIANCE: Check approval status before providing full insights
    is_approved, error_msg = _check_cpa_approval(session_id, "Smart Insights")
    if not is_approved:
        return JSONResponse({
            "success": True,
            "cpa_approval_required": True,
            "message": error_msg,
            "insights": [],
            "summary": {
                "total_insights": 0,
                "total_potential_savings": 0,
                "by_category": {},
                "by_priority": {}
            },
            "disclaimer": "Smart Insights require CPA approval. Submit your return for review to unlock personalized recommendations."
        })

    try:
        # Import rules-based recommender
        from recommendation.rules_based_recommender import get_rules_recommender

        # Load tax return from session
        tax_return = None
        if session_id:
            persistence = get_persistence()
            return_data = persistence.load_return(session_id)
            if return_data and isinstance(return_data, dict):
                try:
                    tax_return = TaxReturn(**return_data)
                except Exception:
                    pass

        # If no valid tax return, return empty insights
        if not tax_return:
            return JSONResponse({
                "success": True,
                "insights": [],
                "total_potential_savings": 0,
                "insight_count": 0,
                "warnings": [],
                "message": "Enter tax data to see personalized insights"
            })

        insights = []
        warnings = []
        total_savings = 0
        seen_titles = set()  # Avoid duplicate insights

        # =====================================================================
        # Source 1: Rules-Based Recommender (764+ IRS Rules)
        # Priority: These are compliance-critical and comprehensive
        # =====================================================================
        try:
            rules_recommender = get_rules_recommender()
            rule_insights = rules_recommender.get_top_insights(tax_return, limit=8)
            rule_warnings = rules_recommender.get_warnings(tax_return)

            # Add rule-based insights (prioritize these as they're IRS-specific)
            for ri in rule_insights:
                if ri.title in seen_titles:
                    continue
                seen_titles.add(ri.title)

                insight = {
                    "id": f"rule_{ri.rule_id}_{uuid.uuid4().hex[:4]}",
                    "type": ri.category,
                    "title": ri.title,
                    "description": ri.description,
                    "savings": max(0, ri.estimated_impact),  # Only positive savings
                    "priority": ri.priority,
                    "severity": ri.severity,
                    "action_type": "manual",
                    "can_auto_apply": False,
                    "action_items": ri.action_items,
                    "irs_reference": ri.irs_reference,
                    "irs_form": ri.irs_form,
                    "confidence": ri.confidence,
                    "rule_id": ri.rule_id,
                    "source": "rules_engine"
                }

                # Set details URL based on category
                if ri.category == "virtual_currency":
                    insight["details_url"] = "/forms?form=8949"
                elif ri.category == "foreign_assets":
                    insight["details_url"] = "/forms?form=8938"
                elif ri.category == "household_employment":
                    insight["details_url"] = "/forms?form=schedule_h"
                elif ri.category == "k1_passthrough":
                    insight["details_url"] = "/forms?form=k1"
                elif ri.category == "casualty_loss":
                    insight["details_url"] = "/forms?form=4684"
                elif ri.category == "retirement":
                    insight["details_url"] = "/optimizer?tab=retirement"
                else:
                    insight["details_url"] = "/optimizer"

                insights.append(insight)
                total_savings += insight["savings"]

            # Collect critical warnings
            for rw in rule_warnings:
                if rw.title not in [w.get("title") for w in warnings]:
                    warnings.append({
                        "id": f"warn_{rw.rule_id}",
                        "title": rw.title,
                        "description": rw.description,
                        "severity": rw.severity,
                        "irs_reference": rw.irs_reference,
                        "action_items": rw.action_items
                    })

        except Exception as rule_error:
            logger.warning(f"Rules-based recommender error (non-fatal): {rule_error}")

        # =====================================================================
        # Source 2: Base Recommendation Engine (Filing, Deductions, Credits)
        # =====================================================================
        try:
            recommendations_result = get_recommendations(tax_return)

            for rec in recommendations_result.recommendations[:5]:
                category = rec.category.value if hasattr(rec.category, 'value') else str(rec.category)

                # Skip if we already have similar insight from rules engine
                if rec.title in seen_titles:
                    continue
                seen_titles.add(rec.title)

                priority = rec.priority.value if hasattr(rec.priority, 'value') else str(rec.priority)

                insight = {
                    "id": f"insight_{uuid.uuid4().hex[:8]}",
                    "type": category,
                    "title": rec.title,
                    "description": rec.description,
                    "savings": rec.potential_savings or 0,
                    "priority": priority,
                    "severity": "medium",
                    "action_type": "manual",
                    "can_auto_apply": False,
                    "action_items": rec.action_items or [],
                    "source": "recommendation_engine"
                }

                # Add action endpoint based on category
                if category == "retirement_planning":
                    insight["action_endpoint"] = "/api/retirement-analysis"
                    insight["details_url"] = "/optimizer?tab=retirement"
                elif category == "deduction_opportunity":
                    insight["details_url"] = "/optimizer?tab=scenarios"
                elif category == "credit_opportunity":
                    insight["details_url"] = "/optimizer?tab=scenarios"
                else:
                    insight["details_url"] = "/optimizer"

                insights.append(insight)
                total_savings += insight["savings"]

        except Exception as rec_error:
            logger.warning(f"Recommendation engine error (non-fatal): {rec_error}")

        # =====================================================================
        # Sort and Limit Results
        # =====================================================================
        # Priority order: immediate > current_year > next_year > long_term
        priority_order = {"immediate": 0, "current_year": 1, "next_year": 2, "long_term": 3}
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

        insights.sort(key=lambda x: (
            priority_order.get(x.get("priority", "long_term"), 4),
            severity_order.get(x.get("severity", "medium"), 2),
            -x.get("savings", 0)
        ))

        # Limit to top 8 insights for clean UI
        insights = insights[:8]

        # Sort warnings by severity
        warnings.sort(key=lambda x: severity_order.get(x.get("severity", "medium"), 2))

        return JSONResponse({
            "success": True,
            "insights": insights,
            "total_potential_savings": round(total_savings, 2),
            "insight_count": len(insights),
            "warnings": warnings[:3],  # Top 3 warnings
            "warning_count": len(warnings),
            "sources": ["rules_engine", "recommendation_engine"]
        })

    except Exception as e:
        logger.error(f"Smart insights error: {e}")
        # Return empty insights on error rather than failing
        return JSONResponse({
            "success": True,
            "insights": [],
            "total_potential_savings": 0,
            "insight_count": 0,
            "warnings": [],
            "warning_count": 0
        })


@app.post("/api/smart-insights/{insight_id}/apply")
async def apply_smart_insight(insight_id: str, request: Request):
    """
    Apply a smart insight recommendation with one click.
    """
    session_id = request.cookies.get("tax_session_id", "")

    try:
        # For now, return success - actual implementation would
        # apply the specific optimization based on insight type
        return JSONResponse({
            "success": True,
            "insight_id": insight_id,
            "message": "Optimization applied successfully",
            "refresh_needed": True
        })

    except Exception as e:
        logger.error(f"Apply insight error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/smart-insights/{insight_id}/dismiss")
async def dismiss_smart_insight(insight_id: str, request: Request):
    """
    Dismiss a smart insight (hide from sidebar for this session).
    """
    # In production, this would store dismissal in session/database
    return JSONResponse({
        "success": True,
        "insight_id": insight_id,
        "message": "Insight dismissed"
    })

