"""
Smart Tax API Routes

Provides API endpoints for the Smart Tax document-first workflow:
- Session management
- Document processing with real-time feedback
- Real OCR document upload
- Complexity routing
- Real-time tax estimates
- Adaptive questions
"""

import logging
import os
import tempfile
from typing import Dict, Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field

from smart_tax import (
    SmartTaxOrchestrator,
    SmartTaxSession,
    ComplexityRouter,
    SmartDocumentProcessor,
    # Phase 4 imports
    AdaptiveQuestionGenerator,
    SmartDeductionDetector,
    TaxPlanningEngine,
)
from smart_tax.orchestrator import SessionState, ComplexityLevel
from smart_tax.complexity_router import assess_and_route
from recommendation.realtime_estimator import RealTimeEstimator, quick_estimate_from_w2

# OCR imports
from src.services.ocr import (
    OCREngine,
    OCREngineType,
    OCREngineError,
    FieldExtractor,
)
from src.services.ocr.field_extractor import get_templates_for_document

# Environment variable for OCR mode
OCR_STRICT_MODE = os.environ.get("OCR_STRICT_MODE", "false").lower() == "true"

# Phase 4 instances
_question_generator: Optional[AdaptiveQuestionGenerator] = None
_deduction_detector: Optional[SmartDeductionDetector] = None
_planning_engine: Optional[TaxPlanningEngine] = None

# OCR engine instance
_ocr_engine: Optional[OCREngine] = None
_field_extractor: Optional[FieldExtractor] = None


def get_ocr_engine() -> OCREngine:
    """Get or create OCR engine with real Tesseract processing."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine(
            engine_type=OCREngineType.TESSERACT,
            strict_mode=OCR_STRICT_MODE,
            lang="eng",
        )
    return _ocr_engine


def get_field_extractor() -> FieldExtractor:
    """Get or create field extractor."""
    global _field_extractor
    if _field_extractor is None:
        _field_extractor = FieldExtractor()
    return _field_extractor


def get_question_generator() -> AdaptiveQuestionGenerator:
    """Get or create question generator."""
    global _question_generator
    if _question_generator is None:
        _question_generator = AdaptiveQuestionGenerator()
    return _question_generator


def get_deduction_detector() -> SmartDeductionDetector:
    """Get or create deduction detector."""
    global _deduction_detector
    if _deduction_detector is None:
        _deduction_detector = SmartDeductionDetector()
    return _deduction_detector


def get_planning_engine() -> TaxPlanningEngine:
    """Get or create planning engine."""
    global _planning_engine
    if _planning_engine is None:
        _planning_engine = TaxPlanningEngine()
    return _planning_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smart-tax", tags=["Smart Tax"])

# Global orchestrator instance
_orchestrator: Optional[SmartTaxOrchestrator] = None


def get_orchestrator() -> SmartTaxOrchestrator:
    """Get or create the Smart Tax orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SmartTaxOrchestrator()
    return _orchestrator


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new Smart Tax session."""
    filing_status: str = Field(default="single", description="Filing status")
    num_dependents: int = Field(default=0, ge=0, description="Number of dependents")
    tax_year: int = Field(default=2024, description="Tax year")


class CreateSessionResponse(BaseModel):
    """Response after creating a session."""
    session_id: str
    state: str
    filing_status: str
    message: str


class ProcessDocumentRequest(BaseModel):
    """Request to process a document."""
    session_id: str
    document_type: str
    extracted_fields: Dict[str, Any]
    ocr_confidence: float = Field(default=85.0, ge=0, le=100)


class ProcessDocumentResponse(BaseModel):
    """Response after processing a document."""
    success: bool
    document_count: int
    confidence: float
    needs_review: bool
    estimate: Optional[Dict[str, Any]] = None
    warnings: List[str] = []
    next_state: str


class AnswerQuestionRequest(BaseModel):
    """Request to answer a question."""
    session_id: str
    question_id: str
    answer: Any


class QuickEstimateRequest(BaseModel):
    """Request for quick estimate from W-2 data."""
    wages: float
    federal_withheld: float
    filing_status: str = "single"
    num_dependents: int = 0


class ComplexityAssessmentRequest(BaseModel):
    """Request for complexity assessment."""
    documents: List[Dict[str, Any]]
    extracted_data: Dict[str, Any]
    filing_status: str = "single"
    user_inputs: Optional[Dict[str, Any]] = None


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    Create a new Smart Tax session.

    This initializes a new tax preparation workflow.
    """
    orchestrator = get_orchestrator()

    session = orchestrator.create_session(
        filing_status=request.filing_status,
        num_dependents=request.num_dependents,
        tax_year=request.tax_year,
    )

    return CreateSessionResponse(
        session_id=session.session_id,
        state=session.state.value,
        filing_status=session.filing_status,
        message="Session created. Ready for document upload.",
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details and current state."""
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "state": session.state.value,
        "filing_status": session.filing_status,
        "num_dependents": session.num_dependents,
        "tax_year": session.tax_year,
        "document_count": len(session.documents),
        "complexity": session.complexity.value if session.complexity else None,
        "current_estimate": session.current_estimate,
        "overall_confidence": session.overall_confidence,
        "data_completeness": session.data_completeness,
        "pending_questions": len(session.pending_questions),
    }


@router.get("/sessions/{session_id}/summary")
async def get_session_summary(session_id: str):
    """Get full session summary including documents and estimates."""
    orchestrator = get_orchestrator()
    return orchestrator.get_session_summary(session_id)


# =============================================================================
# DOCUMENT PROCESSING
# =============================================================================

@router.post("/sessions/{session_id}/documents")
async def process_document(session_id: str, request: ProcessDocumentRequest):
    """
    Process an uploaded document.

    Returns real-time feedback including:
    - Confidence scores
    - Inferred fields
    - Updated tax estimate
    - Warnings/issues
    """
    if session_id != request.session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")

    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = orchestrator.process_document(
        session_id=session_id,
        document_type=request.document_type,
        extracted_fields=request.extracted_fields,
        ocr_confidence=request.ocr_confidence,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Get updated session state
    session = orchestrator.get_session(session_id)

    return {
        "success": True,
        "document_count": len(session.documents),
        "confidence": session.overall_confidence,
        "needs_review": result.get("needs_review", False),
        "estimate": session.current_estimate,
        "warnings": result.get("warnings", []),
        "next_state": session.state.value,
        "inferred_fields": result.get("inferred_fields", []),
        "validation_issues": result.get("validation_issues", []),
    }


@router.post("/sessions/{session_id}/upload")
async def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
):
    """
    Upload a document file and process it with real OCR.

    This endpoint:
    1. Accepts PDF or image files (PNG, JPG, JPEG, TIFF)
    2. Runs Tesseract OCR to extract text
    3. Extracts tax form fields from OCR text
    4. Processes the document in the session

    Args:
        session_id: The session ID
        file: The uploaded file (PDF or image)
        document_type: Optional document type hint (w2, 1099_nec, etc.)
                       If not provided, will attempt auto-detection

    Returns:
        Extracted fields, OCR confidence, and processing results
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate file type
    allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/tiff"]
    allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"]

    content_type = file.content_type or ""
    filename = file.filename or "unknown"
    file_ext = os.path.splitext(filename)[1].lower()

    if content_type not in allowed_types and file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Allowed: PDF, PNG, JPG, TIFF"
        )

    # Read file content
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Run OCR
    try:
        ocr_engine = get_ocr_engine()
        mime_type = content_type if content_type else f"image/{file_ext.lstrip('.')}"
        ocr_result = ocr_engine.process_bytes(file_content, mime_type)
    except OCREngineError as e:
        raise HTTPException(
            status_code=503,
            detail=f"OCR engine not available: {str(e)}"
        )
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

    # Check if OCR was successful
    if not ocr_result.raw_text or ocr_result.confidence < 10:
        return {
            "success": False,
            "error": "Could not extract text from document. Please ensure the image is clear and readable.",
            "ocr_confidence": ocr_result.confidence,
            "engine_used": ocr_result.engine_used,
        }

    # Auto-detect document type if not provided
    detected_type = document_type
    if not detected_type:
        detected_type = _detect_document_type(ocr_result.raw_text)

    # Extract fields from OCR result using templates
    extracted_fields = {}
    try:
        field_extractor = get_field_extractor()
        templates = get_templates_for_document(detected_type)

        if templates:
            extracted_list = field_extractor.extract(ocr_result, templates)
            extracted_fields = {
                field.field_name: field.normalized_value
                for field in extracted_list
                if field.normalized_value is not None
            }
        else:
            # No templates for this document type - use raw text
            logger.warning(f"No templates for document type: {detected_type}")
            extracted_fields = {"raw_text": ocr_result.raw_text}

    except Exception as e:
        logger.error(f"Field extraction failed: {str(e)}")
        extracted_fields = {"raw_text": ocr_result.raw_text}

    # Process document in session
    result = orchestrator.process_document(
        session_id=session_id,
        document_type=detected_type,
        extracted_fields=extracted_fields,
        ocr_confidence=ocr_result.confidence,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Get updated session state
    session = orchestrator.get_session(session_id)

    return {
        "success": True,
        "ocr": {
            "confidence": ocr_result.confidence,
            "engine_used": ocr_result.engine_used,
            "page_count": ocr_result.page_count,
            "processing_time_ms": ocr_result.processing_time_ms,
        },
        "document_type": detected_type,
        "extracted_fields": extracted_fields,
        "document_count": len(session.documents),
        "session_confidence": session.overall_confidence,
        "needs_review": result.get("needs_review", False),
        "estimate": session.current_estimate,
        "warnings": result.get("warnings", []),
        "next_state": session.state.value,
    }


def _detect_document_type(text: str) -> str:
    """Auto-detect document type from OCR text."""
    text_lower = text.lower()

    # W-2 patterns
    if "w-2" in text_lower or "wage and tax statement" in text_lower:
        return "w2"

    # 1099-NEC patterns
    if "1099-nec" in text_lower or "nonemployee compensation" in text_lower:
        return "1099_nec"

    # 1099-INT patterns
    if "1099-int" in text_lower or "interest income" in text_lower:
        return "1099_int"

    # 1099-DIV patterns
    if "1099-div" in text_lower or "dividends and distributions" in text_lower:
        return "1099_div"

    # 1099-B patterns
    if "1099-b" in text_lower or "proceeds from broker" in text_lower:
        return "1099_b"

    # 1099-R patterns
    if "1099-r" in text_lower or "distributions from pensions" in text_lower:
        return "1099_r"

    # 1099-G patterns
    if "1099-g" in text_lower or "government payments" in text_lower:
        return "1099_g"

    # 1098 patterns
    if "1098" in text_lower and "mortgage interest" in text_lower:
        return "1098"

    # 1098-T patterns
    if "1098-t" in text_lower or "tuition statement" in text_lower:
        return "1098_t"

    return "unknown"


@router.get("/sessions/{session_id}/documents")
async def get_session_documents(session_id: str):
    """Get all documents in a session with their summaries."""
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "document_count": len(session.documents),
        "documents": [
            {
                "type": doc["type"],
                "field_count": len(doc.get("fields", {})),
                "processed_at": doc.get("processed_at"),
                "issues": doc.get("validation_issues", []),
            }
            for doc in session.documents
        ],
    }


# =============================================================================
# QUESTIONS & CONFIRMATION
# =============================================================================

@router.get("/sessions/{session_id}/questions")
async def get_pending_questions(session_id: str):
    """Get pending questions that need user answers."""
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "pending_count": len(session.pending_questions),
        "questions": session.pending_questions,
        "answered_count": len(session.answered_questions),
    }


@router.post("/sessions/{session_id}/questions/{question_id}/answer")
async def answer_question(session_id: str, question_id: str, request: AnswerQuestionRequest):
    """Submit an answer to a question."""
    if session_id != request.session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")

    orchestrator = get_orchestrator()
    result = orchestrator.answer_question(
        session_id=session_id,
        question_id=question_id,
        answer=request.answer,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/sessions/{session_id}/confirm")
async def confirm_data(session_id: str, confirmed_fields: Dict[str, Any]):
    """Confirm extracted/inferred data is correct."""
    orchestrator = get_orchestrator()
    result = orchestrator.confirm_data(
        session_id=session_id,
        confirmed_fields=confirmed_fields,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# =============================================================================
# ESTIMATES
# =============================================================================

@router.get("/sessions/{session_id}/estimate")
async def get_estimate(session_id: str):
    """Get current tax estimate for session."""
    orchestrator = get_orchestrator()
    return orchestrator.get_estimate(session_id)


@router.post("/estimate/quick")
async def quick_estimate(request: QuickEstimateRequest):
    """
    Get a quick estimate from minimal W-2 data.

    No session required - useful for landing page estimates.
    """
    result = quick_estimate_from_w2(
        wages=request.wages,
        federal_withheld=request.federal_withheld,
        filing_status=request.filing_status,
        num_dependents=request.num_dependents,
    )

    return result


# =============================================================================
# COMPLEXITY ASSESSMENT
# =============================================================================

@router.post("/assess-complexity")
async def assess_complexity(request: ComplexityAssessmentRequest):
    """
    Assess tax situation complexity and get routing recommendation.

    Returns:
    - Complexity level (SIMPLE/MODERATE/COMPLEX/PROFESSIONAL)
    - Recommended flow
    - Estimated time
    - CPA recommendation if applicable
    """
    decision = assess_and_route(
        documents=request.documents,
        extracted_data=request.extracted_data,
        filing_status=request.filing_status,
        user_inputs=request.user_inputs,
    )

    return decision.to_dict()


@router.get("/sessions/{session_id}/complexity")
async def get_session_complexity(session_id: str):
    """Get complexity assessment for current session."""
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build document list for assessment
    documents = [{"type": doc["type"]} for doc in session.documents]

    decision = assess_and_route(
        documents=documents,
        extracted_data=session.extracted_data,
        filing_status=session.filing_status,
    )

    return {
        "session_id": session_id,
        "complexity": decision.assessment.level,
        "score": decision.assessment.score,
        "factors": [f.value for f in decision.assessment.factors],
        "recommended_flow": decision.flow,
        "estimated_time": decision.assessment.estimated_time_minutes,
        "cpa_recommended": decision.assessment.cpa_recommended,
        "cpa_reason": decision.assessment.cpa_reason,
        "next_steps": decision.next_steps,
        "questions_needed": decision.questions_needed,
    }


# =============================================================================
# FLOW STATE
# =============================================================================

@router.get("/flow-config")
async def get_flow_config():
    """
    Get Smart Tax flow configuration.

    Returns the 5-screen flow structure and complexity levels.
    """
    return {
        "screens": [
            {"id": "upload", "name": "Upload", "description": "Upload your tax documents"},
            {"id": "detect", "name": "Detect", "description": "We analyze your documents"},
            {"id": "confirm", "name": "Confirm", "description": "Review extracted data"},
            {"id": "report", "name": "Report", "description": "View your tax summary"},
            {"id": "act", "name": "Act", "description": "File or get CPA help"},
        ],
        "complexity_levels": [
            {"id": "simple", "name": "Simple", "time": "3-5 minutes", "description": "W-2 only, standard deduction"},
            {"id": "moderate", "name": "Moderate", "time": "8-12 minutes", "description": "Multiple income sources"},
            {"id": "complex", "name": "Complex", "time": "15-20 minutes", "description": "Self-employment, investments"},
            {"id": "professional", "name": "Professional", "time": "CPA Review", "description": "Needs expert assistance"},
        ],
        "supported_documents": [
            {"type": "w2", "name": "W-2", "description": "Wage and Tax Statement"},
            {"type": "1099_nec", "name": "1099-NEC", "description": "Nonemployee Compensation"},
            {"type": "1099_int", "name": "1099-INT", "description": "Interest Income"},
            {"type": "1099_div", "name": "1099-DIV", "description": "Dividend Income"},
            {"type": "1099_b", "name": "1099-B", "description": "Broker Statement"},
            {"type": "1099_r", "name": "1099-R", "description": "Retirement Distribution"},
            {"type": "1098", "name": "1098", "description": "Mortgage Interest"},
            {"type": "1098_t", "name": "1098-T", "description": "Tuition Statement"},
        ],
    }


# =============================================================================
# PHASE 4: ADAPTIVE QUESTIONS
# =============================================================================

@router.get("/sessions/{session_id}/generated-questions")
async def get_generated_questions(
    session_id: str,
    max_questions: int = 10,
):
    """
    Get AI-generated adaptive questions based on the tax situation.

    Questions are prioritized by impact on tax calculation accuracy.
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    generator = get_question_generator()

    # Build document list for question generation
    documents = [{"type": doc["type"]} for doc in session.documents]

    # Get complexity level
    complexity_level = session.complexity.value if session.complexity else "simple"

    questions = generator.generate_questions(
        extracted_data=session.extracted_data,
        documents=documents,
        filing_status=session.filing_status,
        user_answers=session.answered_questions,
        complexity_level=complexity_level,
    )

    # Limit questions
    questions = questions[:max_questions]

    return {
        "session_id": session_id,
        "question_count": len(questions),
        "questions": [q.to_dict() for q in questions],
        "complexity_level": complexity_level,
    }


# =============================================================================
# PHASE 4: DEDUCTION DETECTION
# =============================================================================

@router.get("/sessions/{session_id}/deductions")
async def get_deduction_analysis(session_id: str):
    """
    Analyze deductions and credits for the session.

    Returns:
    - Detected deductions (above-the-line and itemized)
    - Detected credits
    - Standard vs itemized comparison
    - Missed opportunities
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    detector = get_deduction_detector()

    # Build document list
    documents = [{"type": doc["type"]} for doc in session.documents]

    analysis = detector.analyze(
        extracted_data=session.extracted_data,
        documents=documents,
        filing_status=session.filing_status,
        num_dependents=session.num_dependents,
        user_inputs=session.answered_questions,
    )

    return {
        "session_id": session_id,
        "analysis": analysis.to_dict(),
        "summary": {
            "recommended_method": analysis.recommendation,
            "standard_deduction": float(analysis.standard_deduction),
            "total_itemized": float(analysis.total_itemized),
            "savings_difference": float(analysis.savings_difference),
            "deduction_count": len(analysis.detected_deductions),
            "credit_count": len(analysis.detected_credits),
            "missed_opportunity_count": len(analysis.missed_opportunities),
        },
    }


@router.post("/analyze-deductions")
async def analyze_deductions_standalone(
    extracted_data: Dict[str, Any],
    filing_status: str = "single",
    num_dependents: int = 0,
    user_inputs: Optional[Dict[str, Any]] = None,
):
    """
    Standalone deduction analysis (no session required).

    Useful for quick analysis or previews.
    """
    detector = get_deduction_detector()

    analysis = detector.analyze(
        extracted_data=extracted_data,
        documents=[],  # No documents for standalone
        filing_status=filing_status,
        num_dependents=num_dependents,
        user_inputs=user_inputs or {},
    )

    return analysis.to_dict()


# =============================================================================
# PHASE 4: TAX PLANNING INSIGHTS
# =============================================================================

@router.get("/sessions/{session_id}/planning")
async def get_planning_insights(
    session_id: str,
    age: int = 35,
):
    """
    Get proactive tax planning insights and recommendations.

    Returns:
    - Actionable insights by urgency
    - Quarterly estimated tax recommendations
    - Year-end checklist
    - Optimization potential
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    engine = get_planning_engine()

    report = engine.generate_planning_report(
        extracted_data=session.extracted_data,
        answers=session.answered_questions,
        filing_status=session.filing_status,
        age=age,
    )

    return {
        "session_id": session_id,
        "report": report.to_dict(),
        "summary": {
            "tax_year": report.tax_year,
            "projected_tax": float(report.projected_tax_liability),
            "projected_refund_or_owed": float(report.projected_refund_or_owed),
            "optimization_potential": float(report.optimization_potential),
            "insight_count": len(report.insights),
            "urgent_action_count": sum(
                1 for i in report.insights
                if i.urgency.value in ["immediate", "soon"]
            ),
            "checklist_items": len(report.year_end_checklist),
        },
    }


@router.post("/planning-report")
async def generate_planning_report_standalone(
    extracted_data: Dict[str, Any],
    answers: Optional[Dict[str, Any]] = None,
    filing_status: str = "single",
    age: int = 35,
):
    """
    Generate standalone planning report (no session required).

    Useful for quick insights or previews.
    """
    engine = get_planning_engine()

    report = engine.generate_planning_report(
        extracted_data=extracted_data,
        answers=answers or {},
        filing_status=filing_status,
        age=age,
    )

    return report.to_dict()


# =============================================================================
# PHASE 4: COMBINED INTELLIGENCE ENDPOINT
# =============================================================================

@router.get("/sessions/{session_id}/intelligence")
async def get_full_intelligence(
    session_id: str,
    age: int = 35,
    max_questions: int = 5,
):
    """
    Get complete AI intelligence for a session.

    Combines:
    - Adaptive questions
    - Deduction analysis
    - Planning insights

    This is the primary endpoint for the Smart Tax intelligence layer.
    """
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build document list
    documents = [{"type": doc["type"]} for doc in session.documents]
    complexity_level = session.complexity.value if session.complexity else "simple"

    # Generate questions
    generator = get_question_generator()
    questions = generator.generate_questions(
        extracted_data=session.extracted_data,
        documents=documents,
        filing_status=session.filing_status,
        user_answers=session.answered_questions,
        complexity_level=complexity_level,
    )[:max_questions]

    # Analyze deductions
    detector = get_deduction_detector()
    deduction_analysis = detector.analyze(
        extracted_data=session.extracted_data,
        documents=documents,
        filing_status=session.filing_status,
        num_dependents=session.num_dependents,
        user_inputs=session.answered_questions,
    )

    # Generate planning insights
    engine = get_planning_engine()
    planning_report = engine.generate_planning_report(
        extracted_data=session.extracted_data,
        answers=session.answered_questions,
        filing_status=session.filing_status,
        age=age,
    )

    return {
        "session_id": session_id,
        "complexity_level": complexity_level,
        "questions": {
            "count": len(questions),
            "items": [q.to_dict() for q in questions],
        },
        "deductions": {
            "recommendation": deduction_analysis.recommendation,
            "standard_deduction": float(deduction_analysis.standard_deduction),
            "total_itemized": float(deduction_analysis.total_itemized),
            "detected_deductions": [d.to_dict() for d in deduction_analysis.detected_deductions],
            "detected_credits": [c.to_dict() for c in deduction_analysis.detected_credits],
            "missed_opportunities": deduction_analysis.missed_opportunities,
        },
        "planning": {
            "projected_tax": float(planning_report.projected_tax_liability),
            "projected_refund_or_owed": float(planning_report.projected_refund_or_owed),
            "optimization_potential": float(planning_report.optimization_potential),
            "insights": [i.to_dict() for i in planning_report.insights[:5]],
            "quarterly_estimates": [q.to_dict() for q in planning_report.quarterly_estimates],
            "year_end_checklist": planning_report.year_end_checklist[:5],
        },
        "summary": planning_report.summary,
    }
