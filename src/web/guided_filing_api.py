"""
Guided Filing API

Step-by-step tax filing workflow with progress tracking.
Complements the unified filing API with guided-specific endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid
import logging

try:
    from rbac.dependencies import require_auth, AuthContext, optional_auth
except ImportError:
    class AuthContext:
        user_id: Optional[str] = None
        role: Any = None
    def require_auth():
        return AuthContext()
    def optional_auth():
        return AuthContext()

try:
    from database.session_persistence import get_session_persistence
except ImportError:
    def get_session_persistence():
        raise HTTPException(500, "Session persistence not available")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/filing/guided", tags=["guided-filing"])


# =============================================================================
# MODELS
# =============================================================================

class GuidedStep(str, Enum):
    """Steps in the guided filing workflow"""
    PERSONAL = "personal"
    FILING_STATUS = "filing_status"
    INCOME = "income"
    DEDUCTIONS = "deductions"
    CREDITS = "credits"
    REVIEW = "review"
    COMPLETE = "complete"


class PersonalInfo(BaseModel):
    """Personal information data"""
    firstName: str = ""
    lastName: str = ""
    ssn: str = ""
    dateOfBirth: str = ""


class W2Income(BaseModel):
    """W-2 wage income"""
    employerName: str = ""
    wages: str = ""
    federalWithheld: str = ""
    stateWithheld: str = ""


class IncomeData(BaseModel):
    """All income sources"""
    w2: W2Income = Field(default_factory=W2Income)
    selfEmployment: Dict[str, str] = Field(default_factory=dict)
    investments: Dict[str, str] = Field(default_factory=dict)


class DeductionsData(BaseModel):
    """Deduction details"""
    mortgageInterest: str = ""
    salt: str = ""
    charitable: str = ""
    medical: str = ""


class GuidedFormData(BaseModel):
    """Complete guided filing form data"""
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    filingStatus: str = ""
    incomeTypes: List[str] = Field(default_factory=list)
    income: IncomeData = Field(default_factory=IncomeData)
    deductionMethod: str = "standard"
    deductions: DeductionsData = Field(default_factory=DeductionsData)
    credits: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class SaveProgressRequest(BaseModel):
    """Request to save guided filing progress"""
    step: GuidedStep
    data: Dict[str, Any]


class ProgressResponse(BaseModel):
    """Progress response"""
    session_id: str
    currentStep: str
    completedSteps: List[str]
    formData: Dict[str, Any]
    lastUpdated: datetime


class StartGuidedRequest(BaseModel):
    """Start a new guided filing session"""
    tax_year: int = Field(default=2024, ge=2020, le=2030)


# =============================================================================
# STEP DEFINITIONS
# =============================================================================

GUIDED_STEPS = [
    {
        "id": "personal",
        "label": "Personal Info",
        "description": "Your basic information",
        "required_fields": ["personal.firstName", "personal.lastName"],
    },
    {
        "id": "filing_status",
        "label": "Filing Status",
        "description": "How you'll file your return",
        "required_fields": ["filingStatus"],
    },
    {
        "id": "income",
        "label": "Income",
        "description": "All sources of income",
        "required_fields": ["incomeTypes"],
    },
    {
        "id": "deductions",
        "label": "Deductions",
        "description": "Standard or itemized deductions",
        "required_fields": ["deductionMethod"],
    },
    {
        "id": "credits",
        "label": "Credits",
        "description": "Tax credits you qualify for",
        "required_fields": [],
    },
    {
        "id": "review",
        "label": "Review",
        "description": "Review and submit",
        "required_fields": [],
    },
    {
        "id": "complete",
        "label": "Complete",
        "description": "Filing complete",
        "required_fields": [],
    },
]


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/start")
async def start_guided_filing(
    request: StartGuidedRequest,
    ctx: AuthContext = Depends(optional_auth)
) -> Dict[str, Any]:
    """
    Start a new guided filing session.

    Creates a session with guided workflow type and returns the session ID.
    """
    try:
        persistence = get_session_persistence()

        # Create a new session
        session_id = str(uuid.uuid4())

        session_data = {
            "workflow_type": "guided",
            "tax_year": request.tax_year,
            "current_step": "personal",
            "completed_steps": [],
            "form_data": GuidedFormData().dict(),
            "created_at": datetime.utcnow().isoformat(),
            "user_id": str(ctx.user_id) if ctx.user_id else None,
        }

        # Save session
        from database.unified_session import UnifiedFilingSession

        session = UnifiedFilingSession(
            session_id=session_id,
            workflow_type="guided",
            tax_year=request.tax_year,
            data=session_data,
            tenant_id=str(ctx.firm_id) if hasattr(ctx, 'firm_id') and ctx.firm_id else "default",
        )

        persistence.save_session(session)

        logger.info(f"[GUIDED] Started new session: {session_id}")

        return {
            "session_id": session_id,
            "workflow_type": "guided",
            "current_step": "personal",
            "steps": GUIDED_STEPS,
            "tax_year": request.tax_year,
        }

    except Exception as e:
        logger.error(f"[GUIDED] Failed to start session: {e}")
        raise HTTPException(500, f"Failed to start guided filing: {str(e)}")


@router.get("/{session_id}/progress")
async def get_progress(
    session_id: str,
    ctx: AuthContext = Depends(optional_auth)
) -> Dict[str, Any]:
    """
    Get the current progress of a guided filing session.

    Returns the current step, completed steps, and form data.
    """
    try:
        persistence = get_session_persistence()
        session = persistence.load_session(session_id)

        if not session:
            raise HTTPException(404, "Session not found")

        session_data = session.data or {}

        return {
            "session_id": session_id,
            "currentStep": session_data.get("current_step", "personal"),
            "completedSteps": session_data.get("completed_steps", []),
            "formData": session_data.get("form_data", {}),
            "lastUpdated": session.updated_at.isoformat() if session.updated_at else None,
            "steps": GUIDED_STEPS,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GUIDED] Failed to get progress for {session_id}: {e}")
        raise HTTPException(500, f"Failed to get progress: {str(e)}")


@router.post("/{session_id}/progress")
async def save_progress(
    session_id: str,
    request: SaveProgressRequest,
    ctx: AuthContext = Depends(optional_auth)
) -> Dict[str, Any]:
    """
    Save progress for a guided filing step.

    Updates the session with the current step data and marks completed steps.
    """
    try:
        persistence = get_session_persistence()
        session = persistence.load_session(session_id)

        if not session:
            raise HTTPException(404, "Session not found")

        session_data = session.data or {}

        # Update form data
        form_data = session_data.get("form_data", {})
        form_data.update(request.data)
        session_data["form_data"] = form_data

        # Update current step
        session_data["current_step"] = request.step.value

        # Track completed steps
        completed = session_data.get("completed_steps", [])
        step_index = next((i for i, s in enumerate(GUIDED_STEPS) if s["id"] == request.step.value), -1)

        # Mark all previous steps as completed
        for i, step in enumerate(GUIDED_STEPS):
            if i < step_index and step["id"] not in completed:
                completed.append(step["id"])

        session_data["completed_steps"] = completed
        session_data["last_updated"] = datetime.utcnow().isoformat()

        # Save updated session
        session.data = session_data
        persistence.save_session(session)

        logger.info(f"[GUIDED] Saved progress for {session_id} at step {request.step.value}")

        return {
            "success": True,
            "session_id": session_id,
            "currentStep": request.step.value,
            "completedSteps": completed,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GUIDED] Failed to save progress for {session_id}: {e}")
        raise HTTPException(500, f"Failed to save progress: {str(e)}")


@router.post("/{session_id}/submit")
async def submit_guided_return(
    session_id: str,
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Submit the completed guided filing return.

    Validates all required data is present and creates the tax return record.
    """
    try:
        persistence = get_session_persistence()
        session = persistence.load_session(session_id)

        if not session:
            raise HTTPException(404, "Session not found")

        session_data = session.data or {}
        form_data = session_data.get("form_data", {})

        # Validate required fields
        errors = []

        personal = form_data.get("personal", {})
        if not personal.get("firstName"):
            errors.append("First name is required")
        if not personal.get("lastName"):
            errors.append("Last name is required")

        if not form_data.get("filingStatus"):
            errors.append("Filing status is required")

        if errors:
            raise HTTPException(400, {"errors": errors})

        # Mark as submitted
        session_data["status"] = "submitted"
        session_data["submitted_at"] = datetime.utcnow().isoformat()
        session_data["current_step"] = "complete"
        session_data["completed_steps"] = [s["id"] for s in GUIDED_STEPS]

        session.data = session_data
        persistence.save_session(session)

        logger.info(f"[GUIDED] Submitted return for session {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "status": "submitted",
            "message": "Your tax return has been submitted for review.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GUIDED] Failed to submit return for {session_id}: {e}")
        raise HTTPException(500, f"Failed to submit return: {str(e)}")


@router.get("/{session_id}/summary")
async def get_summary(
    session_id: str,
    ctx: AuthContext = Depends(optional_auth)
) -> Dict[str, Any]:
    """
    Get a summary of the guided filing return.

    Returns calculated totals and tax estimates.
    """
    try:
        persistence = get_session_persistence()
        session = persistence.load_session(session_id)

        if not session:
            raise HTTPException(404, "Session not found")

        session_data = session.data or {}
        form_data = session_data.get("form_data", {})

        # Calculate totals
        income = form_data.get("income", {})
        w2 = income.get("w2", {})

        def parse_currency(val: str) -> float:
            if not val:
                return 0.0
            return float(val.replace("$", "").replace(",", "").strip() or 0)

        total_income = parse_currency(w2.get("wages", ""))

        # Standard deduction amounts for 2024
        standard_deductions = {
            "single": 14600,
            "mfj": 29200,
            "mfs": 14600,
            "hoh": 21900,
            "qw": 29200,
        }

        filing_status = form_data.get("filingStatus", "single")
        standard_deduction = standard_deductions.get(filing_status, 14600)

        deduction_method = form_data.get("deductionMethod", "standard")
        if deduction_method == "itemized":
            deductions = form_data.get("deductions", {})
            itemized_total = sum([
                parse_currency(deductions.get("mortgageInterest", "")),
                min(parse_currency(deductions.get("salt", "")), 10000),  # SALT cap
                parse_currency(deductions.get("charitable", "")),
                parse_currency(deductions.get("medical", "")),
            ])
            total_deduction = max(itemized_total, standard_deduction)
        else:
            total_deduction = standard_deduction

        taxable_income = max(0, total_income - total_deduction)

        # Simplified tax calculation (2024 single brackets)
        def calculate_tax(income: float) -> float:
            if income <= 11600:
                return income * 0.10
            elif income <= 47150:
                return 1160 + (income - 11600) * 0.12
            elif income <= 100525:
                return 5426 + (income - 47150) * 0.22
            else:
                return 17168.50 + (income - 100525) * 0.24

        estimated_tax = calculate_tax(taxable_income)
        withheld = parse_currency(w2.get("federalWithheld", ""))

        refund_or_owed = withheld - estimated_tax

        return {
            "session_id": session_id,
            "summary": {
                "total_income": total_income,
                "total_deduction": total_deduction,
                "deduction_method": deduction_method,
                "taxable_income": taxable_income,
                "estimated_tax": round(estimated_tax, 2),
                "total_withheld": withheld,
                "refund_or_owed": round(refund_or_owed, 2),
                "is_refund": refund_or_owed >= 0,
            },
            "filing_status": filing_status,
            "tax_year": session_data.get("tax_year", 2024),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GUIDED] Failed to get summary for {session_id}: {e}")
        raise HTTPException(500, f"Failed to get summary: {str(e)}")


@router.get("/{session_id}/validate")
async def validate_step(
    session_id: str,
    step: GuidedStep,
    ctx: AuthContext = Depends(optional_auth)
) -> Dict[str, Any]:
    """
    Validate a specific step's data.

    Returns validation errors if any required fields are missing.
    """
    try:
        persistence = get_session_persistence()
        session = persistence.load_session(session_id)

        if not session:
            raise HTTPException(404, "Session not found")

        session_data = session.data or {}
        form_data = session_data.get("form_data", {})

        # Get step definition
        step_def = next((s for s in GUIDED_STEPS if s["id"] == step.value), None)
        if not step_def:
            raise HTTPException(400, "Invalid step")

        errors = []
        warnings = []

        # Validate based on step
        if step == GuidedStep.PERSONAL:
            personal = form_data.get("personal", {})
            if not personal.get("firstName"):
                errors.append("First name is required")
            if not personal.get("lastName"):
                errors.append("Last name is required")
            if personal.get("ssn") and len(personal["ssn"].replace("-", "")) != 9:
                errors.append("SSN must be 9 digits")

        elif step == GuidedStep.FILING_STATUS:
            if not form_data.get("filingStatus"):
                errors.append("Please select a filing status")

        elif step == GuidedStep.INCOME:
            income_types = form_data.get("incomeTypes", [])
            if not income_types:
                warnings.append("No income sources selected")

            if "w2" in income_types:
                w2 = form_data.get("income", {}).get("w2", {})
                if not w2.get("wages"):
                    errors.append("W-2 wages amount is required")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "step": step.value,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GUIDED] Failed to validate step for {session_id}: {e}")
        raise HTTPException(500, f"Failed to validate: {str(e)}")
