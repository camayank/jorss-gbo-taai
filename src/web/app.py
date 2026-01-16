"""
FastAPI web UI for the Tax Preparation Agent.

Routes:
- GET  /           : simple chat UI
- POST /api/chat   : chat endpoint (JSON)
- POST /api/upload : document upload endpoint
- GET  /api/documents : list uploaded documents
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

logger = logging.getLogger(__name__)

app = FastAPI(title="US Tax Preparation Agent (Tax Year 2025)")


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

# In-memory session store (for demo/dev). Replace with Redis/DB for production.
_SESSIONS: Dict[str, TaxAgent] = {}
_DOCUMENTS: Dict[str, Dict] = {}  # document_id -> {result, session_id, created_at}
_TAX_RETURNS: Dict[str, Any] = {}  # session_id -> TaxReturn (for document-only flow)
_calculator = TaxCalculator()
_forms = FormGenerator()
_document_processor = DocumentProcessor()


def _get_or_create_session_agent(session_id: Optional[str]) -> tuple[str, TaxAgent]:
    if session_id and session_id in _SESSIONS:
        return session_id, _SESSIONS[session_id]

    new_id = str(uuid.uuid4())
    agent = TaxAgent()
    agent.start_conversation()
    _SESSIONS[new_id] = agent
    return new_id, agent


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat")
async def chat(request: Request, response: Response):
    body = await request.json()
    user_message = (body.get("message") or "").strip()
    action = (body.get("action") or "message").strip().lower()

    session_id = request.cookies.get("tax_session_id")
    session_id, agent = _get_or_create_session_agent(session_id)
    response.set_cookie("tax_session_id", session_id, httponly=True, samesite="lax")

    if action == "reset":
        _SESSIONS.pop(session_id, None)
        session_id, agent = _get_or_create_session_agent(None)
        response.set_cookie("tax_session_id", session_id, httponly=True, samesite="lax")
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

    # Store document result
    doc_id = str(result.document_id)
    _DOCUMENTS[doc_id] = {
        "result": result,
        "session_id": session_id,
        "filename": file.filename,
        "created_at": datetime.now().isoformat(),
    }

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
    json_response.set_cookie("tax_session_id", session_id, httponly=True, samesite="lax")
    return json_response


@app.get("/api/documents")
async def list_documents(request: Request):
    """List all uploaded documents for the current session."""
    session_id = request.cookies.get("tax_session_id")
    if not session_id:
        return JSONResponse({"documents": []})

    docs = []
    for doc_id, doc_data in _DOCUMENTS.items():
        if doc_data["session_id"] == session_id:
            result = doc_data["result"]
            docs.append({
                "document_id": doc_id,
                "filename": doc_data["filename"],
                "document_type": result.document_type,
                "tax_year": result.tax_year,
                "status": result.status,
                "ocr_confidence": result.ocr_confidence,
                "extraction_confidence": result.extraction_confidence,
                "created_at": doc_data["created_at"],
            })

    return JSONResponse({"documents": docs})


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str, request: Request):
    """Get details of a specific uploaded document."""
    session_id = request.cookies.get("tax_session_id") or ""

    if document_id not in _DOCUMENTS:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_data = _DOCUMENTS[document_id]
    if doc_data["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = doc_data["result"]
    return JSONResponse({
        "document_id": document_id,
        "filename": doc_data["filename"],
        "document_type": result.document_type,
        "tax_year": result.tax_year,
        "status": result.status,
        "ocr_confidence": result.ocr_confidence,
        "extraction_confidence": result.extraction_confidence,
        "extracted_fields": [f.to_dict() for f in result.extracted_fields],
        "extracted_data": result.get_extracted_data(),
        "warnings": result.warnings,
        "errors": result.errors,
        "created_at": doc_data["created_at"],
    })


def _get_or_create_tax_return(session_id: str):
    """Get or create a tax return for the session (without requiring OpenAI)."""
    from models.tax_return import TaxReturn
    from models.taxpayer import TaxpayerInfo, FilingStatus
    from models.income import Income
    from models.deductions import Deductions
    from models.credits import TaxCredits

    if session_id in _TAX_RETURNS:
        return _TAX_RETURNS[session_id]

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
    _TAX_RETURNS[session_id] = tax_return
    return tax_return


@app.post("/api/documents/{document_id}/apply")
async def apply_document(document_id: str, request: Request):
    """
    Apply extracted document data to the current tax return.

    This automatically populates the tax return with data from the document.
    """
    session_id = request.cookies.get("tax_session_id") or ""

    if document_id not in _DOCUMENTS:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_data = _DOCUMENTS[document_id]
    if doc_data["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result: ProcessingResult = doc_data["result"]

    # Get or create tax return (without requiring OpenAI)
    tax_return = _get_or_create_tax_return(session_id)

    # Apply document based on type
    from services.ocr.document_processor import DocumentIntegration
    integration = DocumentIntegration()

    success, messages = integration.apply_document_to_return(result, tax_return)

    if success:
        # Update document status
        result.status = "applied"

        # Generate summary of applied data
        extracted_data = result.get_extracted_data()
        summary_items = []
        if "wages" in extracted_data:
            summary_items.append(f"Wages: ${extracted_data['wages']:,.2f}")
        if "federal_tax_withheld" in extracted_data:
            summary_items.append(f"Federal Withheld: ${extracted_data['federal_tax_withheld']:,.2f}")

        return JSONResponse({
            "success": True,
            "document_id": document_id,
            "document_type": result.document_type,
            "message": f"Successfully applied {result.document_type.upper()} to tax return",
            "applied_data": summary_items,
            "warnings": messages,
        })
    else:
        return JSONResponse({
            "success": False,
            "document_id": document_id,
            "document_type": result.document_type,
            "message": "Failed to apply document",
            "errors": messages,
        }, status_code=400)


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str, request: Request):
    """Delete an uploaded document."""
    session_id = request.cookies.get("tax_session_id") or ""

    if document_id not in _DOCUMENTS:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_data = _DOCUMENTS[document_id]
    if doc_data["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    del _DOCUMENTS[document_id]
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

    # Get tax return from session or document-only flow
    tax_return = None
    if session_id in _SESSIONS:
        tax_return = _SESSIONS[session_id].get_tax_return()
    if not tax_return and session_id in _TAX_RETURNS:
        tax_return = _TAX_RETURNS[session_id]

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
    """
    from export.pdf_generator import TaxReturnPDFGenerator
    from fastapi.responses import Response

    session_id = request.cookies.get("tax_session_id") or ""
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
    """
    session_id = request.cookies.get("tax_session_id") or ""
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
    """Helper to get tax return from either session or document flow."""
    if session_id in _SESSIONS:
        return _SESSIONS[session_id].get_tax_return()
    if session_id in _TAX_RETURNS:
        return _TAX_RETURNS[session_id]
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

    # Store in session
    _TAX_RETURNS[session_id] = tax_return

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
    response.set_cookie("tax_session_id", session_id, httponly=True, samesite="lax")
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

        # Store in session
        session_id = request.cookies.get("tax_session_id") or str(uuid.uuid4())
        _TAX_RETURNS[session_id] = tax_return

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
        response.set_cookie("tax_session_id", session_id, httponly=True, samesite="lax")
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

