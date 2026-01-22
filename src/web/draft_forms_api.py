"""
Draft Tax Form PDF API

REST API endpoints for generating draft IRS-style tax form PDFs.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
import logging

# Import draft form generator
try:
    from export.draft_form_generator import DraftFormPDFGenerator, DraftReturnPackage
    DRAFT_FORMS_AVAILABLE = True
except ImportError:
    DRAFT_FORMS_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/draft-forms", tags=["Draft Tax Form PDFs"])


# =============================================================================
# REQUEST MODELS
# =============================================================================

class Form1040Input(BaseModel):
    """Input for generating draft Form 1040."""
    taxpayer_name: str = Field(..., description="Taxpayer's full name")
    ssn: str = Field(default="XXX-XX-XXXX", description="SSN (masked)")
    filing_status: str = Field(default="Single", description="Filing status")
    tax_year: int = Field(default=2024, description="Tax year")

    # Income
    wages: float = Field(default=0, ge=0, description="W-2 wages")
    interest_income: float = Field(default=0, ge=0, description="Interest income")
    dividend_income: float = Field(default=0, ge=0, description="Dividend income")
    capital_gains: float = Field(default=0, description="Capital gains/losses")
    business_income: float = Field(default=0, description="Schedule C income")
    rental_income: float = Field(default=0, description="Rental income")
    other_income: float = Field(default=0, description="Other income")

    # Deductions
    standard_deduction: float = Field(default=0, ge=0, description="Standard deduction")
    itemized_deductions: float = Field(default=0, ge=0, description="Itemized deductions")
    qbi_deduction: float = Field(default=0, ge=0, description="QBI deduction")

    # Tax and credits
    tax_liability: float = Field(default=0, ge=0, description="Total tax liability")
    child_tax_credit: float = Field(default=0, ge=0, description="Child tax credit")
    other_credits: float = Field(default=0, ge=0, description="Other credits")

    # Payments
    withholding: float = Field(default=0, ge=0, description="Federal tax withheld")
    estimated_payments: float = Field(default=0, ge=0, description="Estimated payments")


class ScheduleInput(BaseModel):
    """Input for generating a draft schedule."""
    schedule_name: str = Field(..., description="Schedule identifier (A, B, C, D, E, SE)")
    schedule_title: str = Field(..., description="Schedule title")
    tax_year: int = Field(default=2024)
    lines: list = Field(..., description="List of (line_num, description, amount) tuples")


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/form-1040", response_class=Response)
async def generate_form_1040(input_data: Form1040Input):
    """
    Generate a draft Form 1040 PDF.

    Returns a PDF with DRAFT watermark suitable for CPA review.
    """
    if not DRAFT_FORMS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Draft form generator not available")

    try:
        generator = DraftFormPDFGenerator(tax_year=input_data.tax_year)

        # Calculate totals
        total_income = (
            input_data.wages +
            input_data.interest_income +
            input_data.dividend_income +
            max(0, input_data.capital_gains) +
            input_data.business_income +
            input_data.rental_income +
            input_data.other_income
        )

        agi = total_income  # Simplified - would have adjustments

        deduction = max(input_data.standard_deduction, input_data.itemized_deductions)
        taxable_income = max(0, agi - deduction - input_data.qbi_deduction)

        total_credits = input_data.child_tax_credit + input_data.other_credits
        tax_after_credits = max(0, input_data.tax_liability - total_credits)

        total_payments = input_data.withholding + input_data.estimated_payments

        # Build data dicts
        income_data = {
            "wages": input_data.wages,
            "taxable_interest": input_data.interest_income,
            "ordinary_dividends": input_data.dividend_income,
            "capital_gains": input_data.capital_gains,
            "other_income": input_data.business_income + input_data.rental_income + input_data.other_income,
            "total_income": total_income,
            "agi": agi
        }

        deduction_data = {
            "total_deduction": deduction,
            "qbi_deduction": input_data.qbi_deduction
        }

        tax_data = {
            "taxable_income": taxable_income,
            "tax_before_credits": input_data.tax_liability,
            "total_tax_before_credits": input_data.tax_liability,
            "child_tax_credit": input_data.child_tax_credit,
            "total_credits": total_credits,
            "tax_after_credits": tax_after_credits,
            "total_tax": tax_after_credits
        }

        payment_data = {
            "withholding": input_data.withholding,
            "estimated_payments": input_data.estimated_payments,
            "total_payments": total_payments
        }

        # Generate PDF
        pdf_bytes = generator.generate_form_1040(
            taxpayer_name=input_data.taxpayer_name,
            ssn=input_data.ssn,
            filing_status=input_data.filing_status,
            income_data=income_data,
            deduction_data=deduction_data,
            tax_data=tax_data,
            payment_data=payment_data
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="Draft_Form_1040_{input_data.tax_year}.pdf"'
            }
        )

    except Exception as e:
        logger.error(f"Error generating Form 1040: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule", response_class=Response)
async def generate_schedule(input_data: ScheduleInput):
    """
    Generate a draft schedule PDF.

    Returns a PDF with DRAFT watermark for the specified schedule.
    """
    if not DRAFT_FORMS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Draft form generator not available")

    try:
        generator = DraftFormPDFGenerator(tax_year=input_data.tax_year)

        # Convert lines list to tuples
        lines = [
            (str(line[0]), str(line[1]), float(line[2]))
            for line in input_data.lines
        ]

        # Generate PDF
        pdf_bytes = generator.generate_schedule_summary(
            schedule_name=input_data.schedule_name,
            schedule_description=input_data.schedule_title,
            lines=lines
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="Draft_Schedule_{input_data.schedule_name}_{input_data.tax_year}.pdf"'
            }
        )

    except Exception as e:
        logger.error(f"Error generating schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/form-1040", response_class=Response)
async def generate_form_1040_from_session(
    session_id: str,
    tax_year: int = Query(default=2024)
):
    """
    Generate draft Form 1040 from a saved tax session.

    Pulls data from the session's tax return and calculation breakdown.
    """
    if not DRAFT_FORMS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Draft form generator not available")

    # This would integrate with the session storage
    # For now, return a sample form
    raise HTTPException(
        status_code=501,
        detail="Session-based form generation requires session storage integration"
    )


@router.get("/templates")
async def list_available_templates():
    """
    List available draft form templates.
    """
    return {
        "available_templates": [
            {
                "form": "1040",
                "title": "U.S. Individual Income Tax Return",
                "endpoint": "/api/v1/draft-forms/form-1040"
            },
            {
                "form": "Schedule A",
                "title": "Itemized Deductions",
                "endpoint": "/api/v1/draft-forms/schedule"
            },
            {
                "form": "Schedule B",
                "title": "Interest and Ordinary Dividends",
                "endpoint": "/api/v1/draft-forms/schedule"
            },
            {
                "form": "Schedule C",
                "title": "Profit or Loss From Business",
                "endpoint": "/api/v1/draft-forms/schedule"
            },
            {
                "form": "Schedule D",
                "title": "Capital Gains and Losses",
                "endpoint": "/api/v1/draft-forms/schedule"
            },
            {
                "form": "Schedule E",
                "title": "Supplemental Income and Loss",
                "endpoint": "/api/v1/draft-forms/schedule"
            },
            {
                "form": "Schedule SE",
                "title": "Self-Employment Tax",
                "endpoint": "/api/v1/draft-forms/schedule"
            }
        ],
        "note": "All outputs are marked as DRAFT for review purposes only"
    }


@router.get("/health")
async def draft_forms_health_check():
    """
    Check if draft forms API is operational.
    """
    return {
        "status": "operational" if DRAFT_FORMS_AVAILABLE else "unavailable",
        "draft_forms_available": DRAFT_FORMS_AVAILABLE,
        "supported_forms": ["Form 1040", "Schedule A-E", "Schedule SE"],
        "timestamp": datetime.now().isoformat()
    }
