"""
Smart Onboarding API Routes

Provides endpoints for the 60-second client onboarding flow:
1. Start onboarding session
2. Upload document (1040 PDF/image)
3. Get smart questions
4. Submit answers
5. Get instant analysis
6. Create client
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from sqlalchemy.ext.asyncio import AsyncSession

try:
    from database.connection import get_async_session
except ImportError:
    async def get_async_session():
        raise HTTPException(status_code=503, detail="Database session dependency unavailable")
from ..services.smart_onboarding_service import (
    get_smart_onboarding_service,
    OnboardingStatus,
)

logger = logging.getLogger(__name__)

smart_onboarding_router = APIRouter(
    prefix="/onboarding",
    tags=["Smart Onboarding"]
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class StartOnboardingRequest(BaseModel):
    """Request to start a new onboarding session."""
    cpa_id: str = Field(..., description="ID of the CPA initiating onboarding")


class StartOnboardingResponse(BaseModel):
    """Response with new session details."""
    session_id: str
    status: str
    message: str


class SubmitAnswersRequest(BaseModel):
    """Request to submit answers to smart questions."""
    answers: Dict[str, str] = Field(
        ...,
        description="Map of question_id to selected answer value"
    )


class CreateClientRequest(BaseModel):
    """Request to create client from onboarding session."""
    client_name: Optional[str] = Field(
        None,
        description="Override client name (defaults to extracted name)"
    )


class QuestionResponse(BaseModel):
    """Single question for the frontend."""
    id: str
    question: str
    category: str
    priority: str
    options: List[Dict[str, str]]
    reason: str
    potential_impact: str
    depends_on: Optional[str] = None
    show_if_answer: Optional[str] = None


class QuestionsResponse(BaseModel):
    """Response with smart questions."""
    questions: List[QuestionResponse]
    taxpayer_profile: str
    estimated_question_count: int
    categories_covered: List[str]


class OpportunityResponse(BaseModel):
    """Single optimization opportunity."""
    id: str
    title: str
    category: str
    potential_savings: float
    confidence: str
    description: str
    action_required: str
    priority: int


class AnalysisResponse(BaseModel):
    """Instant analysis response."""
    total_potential_savings: float
    opportunities: List[OpportunityResponse]
    tax_summary: Dict[str, Any]
    recommendations_count: int
    analysis_confidence: str


class SessionSummaryResponse(BaseModel):
    """Session summary for UI display."""
    session_id: str
    status: str
    progress: int
    extracted_data: Optional[Dict[str, Any]] = None
    extraction_confidence: Optional[float] = None
    questions: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    client: Optional[Dict[str, Any]] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@smart_onboarding_router.post(
    "/start",
    response_model=StartOnboardingResponse,
    summary="Start smart onboarding session",
    description="Initialize a new 60-second onboarding session for a CPA"
)
async def start_onboarding(request: StartOnboardingRequest):
    """
    Start a new smart onboarding session.

    This creates a session that will track the onboarding progress
    through document upload, question generation, and analysis.
    """
    try:
        service = get_smart_onboarding_service()
        session = service.start_onboarding(request.cpa_id)

        return StartOnboardingResponse(
            session_id=session.session_id,
            status=session.status.value,
            message="Onboarding session started. Upload a 1040 document to continue."
        )
    except Exception as e:
        logger.error(f"Failed to start onboarding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@smart_onboarding_router.post(
    "/{session_id}/upload",
    summary="Upload 1040 document",
    description="Upload a prior year 1040 (PDF or image) for OCR processing"
)
async def upload_document(
    session_id: str,
    file: UploadFile = File(..., description="1040 PDF or image file")
):
    """
    Upload a 1040 tax return for processing.

    The document will be:
    1. Processed through OCR (~10 seconds)
    2. Parsed to extract all tax data
    3. Used to generate smart follow-up questions

    Supported formats: PDF, JPG, PNG, TIFF
    """
    try:
        service = get_smart_onboarding_service()

        # Read file content
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        if len(content) > 20 * 1024 * 1024:  # 20MB limit
            raise HTTPException(status_code=400, detail="File too large (max 20MB)")

        # Process document
        session = await service.process_document(
            session_id=session_id,
            file_content=content,
            filename=file.filename or "upload.pdf",
            content_type=file.content_type or "application/pdf"
        )

        if session.status == OnboardingStatus.FAILED:
            raise HTTPException(status_code=400, detail=session.error_message)

        # Build response with extracted data and questions
        response = {
            "session_id": session.session_id,
            "status": session.status.value,
            "extraction_confidence": session.extraction_confidence,
        }

        if session.parsed_1040:
            response["extracted_data"] = {
                "taxpayer_name": session.parsed_1040.taxpayer_name,
                "filing_status": session.parsed_1040.filing_status.value if session.parsed_1040.filing_status else None,
                "agi": float(session.parsed_1040.adjusted_gross_income or 0),
                "wages": float(session.parsed_1040.wages_salaries_tips or 0),
                "total_income": float(session.parsed_1040.total_income or 0),
                "total_tax": float(session.parsed_1040.total_tax or 0),
                "refund": float(session.parsed_1040.refund_amount or 0),
                "amount_owed": float(session.parsed_1040.amount_owed or 0),
                "dependents": session.parsed_1040.total_dependents,
                "fields_extracted": session.parsed_1040.fields_extracted,
            }

        if session.questions:
            response["questions"] = session.questions.to_dict()

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@smart_onboarding_router.get(
    "/{session_id}/questions",
    response_model=QuestionsResponse,
    summary="Get smart questions",
    description="Get the AI-generated smart questions for this session"
)
async def get_questions(session_id: str):
    """
    Get the smart follow-up questions generated based on extracted 1040 data.

    Questions are:
    - Tailored to the specific taxpayer's situation
    - Prioritized by potential impact
    - Limited to 3-8 questions for quick completion
    """
    service = get_smart_onboarding_service()
    session = service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.questions:
        raise HTTPException(
            status_code=400,
            detail="Questions not yet generated. Upload a document first."
        )

    return QuestionsResponse(
        questions=[
            QuestionResponse(
                id=q.id,
                question=q.question,
                category=q.category.value,
                priority=q.priority.value,
                options=q.options,
                reason=q.reason,
                potential_impact=q.potential_impact,
                depends_on=q.depends_on,
                show_if_answer=q.show_if_answer,
            )
            for q in session.questions.questions
        ],
        taxpayer_profile=session.questions.taxpayer_profile,
        estimated_question_count=session.questions.estimated_question_count,
        categories_covered=session.questions.categories_covered,
    )


@smart_onboarding_router.post(
    "/{session_id}/answers",
    response_model=AnalysisResponse,
    summary="Submit answers and get analysis",
    description="Submit answers to smart questions and receive instant analysis"
)
async def submit_answers(session_id: str, request: SubmitAnswersRequest):
    """
    Submit answers to the smart questions.

    This triggers instant analysis that identifies:
    - Tax optimization opportunities
    - Potential annual savings
    - Specific action items

    Returns the complete analysis with prioritized recommendations.
    """
    try:
        service = get_smart_onboarding_service()
        session = service.submit_answers(session_id, request.answers)

        if not session.analysis:
            raise HTTPException(status_code=500, detail="Analysis failed")

        return AnalysisResponse(
            total_potential_savings=float(session.analysis.total_potential_savings),
            opportunities=[
                OpportunityResponse(
                    id=o.id,
                    title=o.title,
                    category=o.category,
                    potential_savings=float(o.potential_savings),
                    confidence=o.confidence,
                    description=o.description,
                    action_required=o.action_required,
                    priority=o.priority,
                )
                for o in session.analysis.opportunities
            ],
            tax_summary=session.analysis.tax_summary,
            recommendations_count=session.analysis.recommendations_count,
            analysis_confidence=session.analysis.analysis_confidence,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Answer submission failed for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@smart_onboarding_router.post(
    "/{session_id}/create-client",
    summary="Create client from session",
    description="Create a new client from the completed onboarding session"
)
async def create_client(
    session_id: str,
    request: CreateClientRequest,
    db_session: AsyncSession = Depends(get_async_session),
):
    """
    Create a client from the onboarding session.

    This finalizes the onboarding by:
    - Creating a client record
    - Storing the extracted tax data
    - Saving the identified opportunities
    - Making the client available in the CPA dashboard
    """
    try:
        service = get_smart_onboarding_service()
        session = await service.create_client(
            session_id,
            request.client_name,
            db_session=db_session,
        )

        return {
            "session_id": session.session_id,
            "status": session.status.value,
            "client_id": session.client_id,
            "client_name": session.client_name,
            "message": "Client created successfully",
            "analysis_summary": {
                "total_potential_savings": float(session.analysis.total_potential_savings) if session.analysis else 0,
                "opportunities_count": len(session.analysis.opportunities) if session.analysis else 0,
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Client creation failed for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@smart_onboarding_router.get(
    "/{session_id}",
    response_model=SessionSummaryResponse,
    summary="Get session status",
    description="Get the current status and summary of an onboarding session"
)
async def get_session_status(session_id: str):
    """
    Get the current status of an onboarding session.

    Returns:
    - Current status and progress percentage
    - Extracted data (if available)
    - Questions (if generated)
    - Analysis results (if complete)
    - Client info (if created)
    """
    service = get_smart_onboarding_service()
    summary = service.get_session_summary(session_id)

    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])

    return SessionSummaryResponse(**summary)


@smart_onboarding_router.get(
    "/{session_id}/full",
    summary="Get full session data",
    description="Get complete session data including all extracted fields"
)
async def get_full_session(session_id: str):
    """
    Get the complete session data for detailed review.

    This includes all extracted 1040 fields, all questions,
    all answers, and the full analysis.
    """
    service = get_smart_onboarding_service()
    session = service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.to_dict()


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

@smart_onboarding_router.post(
    "/batch/quick-add",
    summary="Quick add client with minimal data",
    description="Create a client with minimal manual data entry (no document upload)"
)
async def quick_add_client(
    cpa_id: str = Form(...),
    client_name: str = Form(...),
    filing_status: str = Form(...),
    wages: float = Form(0),
    agi: float = Form(0),
    dependents: int = Form(0),
):
    """
    Quick add a client without document upload.

    This is useful when CPA has basic info but no uploaded return.
    Still generates smart questions based on provided data.
    """
    try:
        service = get_smart_onboarding_service()

        # Start session
        session = service.start_onboarding(cpa_id)

        # Create mock parsed data
        from ..services.form_1040_parser import Parsed1040Data, FilingStatus
        from decimal import Decimal

        # Map filing status
        status_map = {
            "single": FilingStatus.SINGLE,
            "mfj": FilingStatus.MARRIED_FILING_JOINTLY,
            "mfs": FilingStatus.MARRIED_FILING_SEPARATELY,
            "hoh": FilingStatus.HEAD_OF_HOUSEHOLD,
        }
        fs = status_map.get(filing_status.lower(), FilingStatus.SINGLE)

        # Create parsed data from form inputs
        parsed = Parsed1040Data(
            taxpayer_name=client_name,
            filing_status=fs,
            wages_salaries_tips=Decimal(str(wages)),
            adjusted_gross_income=Decimal(str(agi)) if agi > 0 else Decimal(str(wages)),
            total_dependents=dependents,
            extraction_confidence=100.0,  # Manual entry = 100% confident
        )

        # Store in session
        session.parsed_1040 = parsed
        session.status = OnboardingStatus.OCR_COMPLETE

        # Generate questions
        from ..services.ai_question_generator import AIQuestionGenerator
        generator = AIQuestionGenerator()
        questions = generator.generate_questions(parsed)
        session.questions = questions
        session.status = OnboardingStatus.QUESTIONS_GENERATED

        return {
            "session_id": session.session_id,
            "status": session.status.value,
            "client_name": client_name,
            "questions": questions.to_dict(),
            "message": "Quick add successful. Answer questions to continue."
        }

    except Exception as e:
        logger.error(f"Quick add failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# DEMO/TESTING ENDPOINTS
# =============================================================================

@smart_onboarding_router.get(
    "/demo/sample-questions",
    summary="Get sample questions",
    description="Get sample smart questions for UI development/testing"
)
async def get_sample_questions():
    """
    Get sample questions for demo/testing purposes.

    This returns a typical set of questions without requiring
    actual document upload or OCR processing.
    """
    return {
        "questions": [
            {
                "id": "retirement_401k_available",
                "question": "Does your employer offer a 401(k) or similar retirement plan?",
                "category": "retirement",
                "priority": "high",
                "options": [
                    {"value": "yes_with_match", "label": "Yes, with employer match"},
                    {"value": "yes_no_match", "label": "Yes, but no match"},
                    {"value": "no", "label": "No"},
                    {"value": "unknown", "label": "Not sure"},
                ],
                "reason": "Employer retirement plans offer significant tax benefits",
                "potential_impact": "401(k) contributions can save 22-37% in taxes",
            },
            {
                "id": "retirement_401k_contribution",
                "question": "What's your current 401(k) contribution rate?",
                "category": "retirement",
                "priority": "high",
                "options": [
                    {"value": "0", "label": "0% (not contributing)"},
                    {"value": "1-5", "label": "1-5%"},
                    {"value": "6-10", "label": "6-10%"},
                    {"value": "11-15", "label": "11-15%"},
                    {"value": "max", "label": "Maxing out ($23,000)"},
                ],
                "reason": "Understanding current contributions helps identify optimization",
                "potential_impact": "Increasing to max could save $2,000-5,000+ annually",
                "depends_on": "retirement_401k_available",
                "show_if_answer": "yes_with_match,yes_no_match",
            },
            {
                "id": "healthcare_hdhp",
                "question": "Do you have a High Deductible Health Plan (HDHP)?",
                "category": "healthcare",
                "priority": "high",
                "options": [
                    {"value": "yes", "label": "Yes"},
                    {"value": "no", "label": "No"},
                    {"value": "unknown", "label": "Not sure"},
                ],
                "reason": "HDHPs qualify for HSA contributions with triple tax benefits",
                "potential_impact": "HSA saves taxes now, grows tax-free, withdraws tax-free",
            },
            {
                "id": "dependents_childcare",
                "question": "Do you pay for childcare or daycare?",
                "category": "dependents",
                "priority": "high",
                "options": [
                    {"value": "yes_high", "label": "Yes, $5,000+ per year"},
                    {"value": "yes_low", "label": "Yes, under $5,000 per year"},
                    {"value": "no", "label": "No"},
                ],
                "reason": "Childcare expenses may qualify for tax credits and FSA",
                "potential_impact": "Child and Dependent Care Credit up to $2,100",
            },
            {
                "id": "credits_energy",
                "question": "Have you made energy-efficient improvements or bought an EV?",
                "category": "credits",
                "priority": "medium",
                "options": [
                    {"value": "ev", "label": "Yes, electric vehicle"},
                    {"value": "solar", "label": "Yes, solar panels"},
                    {"value": "other", "label": "Yes, other improvements"},
                    {"value": "no", "label": "No"},
                ],
                "reason": "Energy credits can be significant",
                "potential_impact": "EV credit up to $7,500, solar credit 30% of cost",
            },
        ],
        "taxpayer_profile": "Demo Taxpayer | W-2 Income: $85,000 | AGI: $85,000",
        "estimated_question_count": 5,
        "categories_covered": ["retirement", "healthcare", "dependents", "credits"],
    }


@smart_onboarding_router.get(
    "/demo/sample-analysis",
    summary="Get sample analysis",
    description="Get sample analysis results for UI development/testing"
)
async def get_sample_analysis():
    """
    Get sample analysis for demo/testing purposes.
    """
    return {
        "total_potential_savings": 4200.00,
        "opportunities": [
            {
                "id": "opp_401k",
                "title": "Maximize 401(k) Contributions",
                "category": "retirement",
                "potential_savings": 2100.00,
                "confidence": "high",
                "description": "Increase 401(k) contributions from current 6% to maximum $23,000",
                "action_required": "Contact HR to increase contribution rate",
                "priority": 1,
            },
            {
                "id": "opp_hsa",
                "title": "Maximize HSA Contributions",
                "category": "healthcare",
                "potential_savings": 1250.00,
                "confidence": "high",
                "description": "Contribute maximum $8,300 to your HSA for triple tax benefits",
                "action_required": "Set up HSA payroll deductions",
                "priority": 2,
            },
            {
                "id": "opp_dcfsa",
                "title": "Dependent Care FSA",
                "category": "dependents",
                "potential_savings": 850.00,
                "confidence": "medium",
                "description": "Use pre-tax dollars for childcare through Dependent Care FSA",
                "action_required": "Enroll in Dependent Care FSA during open enrollment",
                "priority": 3,
            },
        ],
        "tax_summary": {
            "tax_year": 2024,
            "filing_status": "married_filing_jointly",
            "adjusted_gross_income": 142500.00,
            "total_income": 142500.00,
            "total_tax": 17840.00,
            "effective_rate": 12.5,
            "refund_or_owed": 1230.00,
        },
        "recommendations_count": 3,
        "analysis_confidence": "high",
    }
