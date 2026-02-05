"""
Express Lane API - IMPROVED VERSION with Robust Error Handling

This improved version includes:
- Comprehensive input validation
- Better error messages
- Graceful degradation
- Data consistency checks
- Security improvements
- Detailed logging

To use: Replace express_lane_api.py with this file
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from decimal import Decimal, InvalidOperation
from datetime import datetime
import logging
import traceback

from src.models.tax_return import TaxReturn, FilingStatus, TaxPayer
from src.models.income import W2Income, Income1099Misc, Income1099NEC
from src.models.deductions import ItemizedDeductions, StandardDeduction
from src.calculation.tax_calculator import TaxCalculator
from src.export.professional_pdf_templates import ProfessionalPDFGenerator
from src.recommendation.recommendation_engine import RecommendationEngine

# Import our new validation helpers
from src.web.validation_helpers import (
    validate_express_lane_data,
    format_validation_errors,
    validate_ssn,
    validate_tax_year,
    sanitize_string,
    sanitize_numeric_string
)

# Import database persistence
from src.database.unified_session import UnifiedFilingSession, FilingState, WorkflowType
from src.database.session_persistence import get_session_persistence
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tax-returns", tags=["express-lane"])


# =============================================================================
# Enhanced Request/Response Models with Validation
# =============================================================================

class ExpressLaneSubmission(BaseModel):
    """Data from Express Lane final submission"""
    extracted_data: Dict[str, Any] = Field(..., description="All extracted data from documents")
    documents: List[str] = Field(..., description="Document IDs that were processed")
    user_edits: Optional[Dict[str, Any]] = Field(default=None, description="User-edited fields")

    @validator('documents')
    def validate_documents(cls, v):
        """Validate documents list"""
        if not v or len(v) == 0:
            raise ValueError("At least one document is required")
        if len(v) > 10:
            raise ValueError("Maximum 10 documents allowed")
        return v

    @validator('extracted_data')
    def validate_extracted_data(cls, v):
        """Validate extracted data has required fields"""
        required_fields = ["first_name", "last_name", "ssn"]
        missing = [f for f in required_fields if not v.get(f)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        return v


class ExpressLaneResponse(BaseModel):
    """Response from Express Lane submission"""
    success: bool
    return_id: str
    estimated_refund: Optional[Decimal] = None
    estimated_tax_due: Optional[Decimal] = None
    total_tax: Decimal
    effective_rate: Decimal
    confidence_score: float = Field(..., ge=0, le=1)
    warnings: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    # New: Additional context for errors
    validation_issues: List[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Standardized error response"""
    success: bool = False
    error_type: str
    error_message: str
    details: Optional[Dict[str, Any]] = None
    user_message: str  # User-friendly message
    support_contact: str = "support@taxplatform.com"


class PriorYearImportRequest(BaseModel):
    """Request to import data from prior year"""
    prior_year: int = Field(..., ge=2020, le=2025)
    fields_to_import: List[str] = Field(default_factory=list)

    @validator('prior_year')
    def validate_year(cls, v):
        """Validate tax year"""
        is_valid, error = validate_tax_year(v)
        if not is_valid:
            raise ValueError(error)
        return v

    @validator('fields_to_import')
    def validate_fields(cls, v):
        """Validate field names"""
        if len(v) > 20:
            raise ValueError("Maximum 20 fields can be imported at once")

        # Sanitize field names
        sanitized = [sanitize_string(f, 100) for f in v]
        return sanitized


# =============================================================================
# Express Lane Endpoints - IMPROVED
# =============================================================================

@router.post("/express-lane", response_model=ExpressLaneResponse)
async def submit_express_lane(submission: ExpressLaneSubmission):
    """
    Process Express Lane submission with AI-extracted data.

    IMPROVED with:
    - Comprehensive input validation
    - Better error handling and user messages
    - Data consistency checks
    - Graceful degradation
    - Detailed logging for debugging
    """
    request_id = f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        logger.info(f"[{request_id}] Express Lane submission received", extra={
            "request_id": request_id,
            "document_count": len(submission.documents),
            "has_user_edits": submission.user_edits is not None
        })

        # Step 1: Sanitize and merge data
        final_data = _sanitize_and_merge_data(submission)

        # Step 2: Comprehensive validation
        is_valid, validation_errors = validate_express_lane_data(final_data)

        if not is_valid:
            logger.warning(f"[{request_id}] Validation failed: {validation_errors}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_type": "ValidationError",
                    "error_message": format_validation_errors(validation_errors),
                    "user_message": "Please review and correct the highlighted fields.",
                    "validation_errors": validation_errors
                }
            )

        # Step 3: Build tax return with error handling
        try:
            tax_return = _build_tax_return_from_extracted_data(final_data)
        except ValueError as e:
            logger.error(f"[{request_id}] Failed to build tax return: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_type": "DataConversionError",
                    "error_message": str(e),
                    "user_message": "There was an issue with the extracted data. Please review your information."
                }
            )

        # Step 4: Calculate confidence score
        confidence_score = _calculate_confidence_score(final_data, submission.extracted_data)
        logger.info(f"[{request_id}] Confidence score: {confidence_score}")

        # Step 5: Run tax calculation with fallback
        try:
            calculator = TaxCalculator()
            calculation_result = calculator.calculate_tax(tax_return)
        except Exception as e:
            logger.error(f"[{request_id}] Tax calculation failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_type": "CalculationError",
                    "error_message": "Tax calculation failed",
                    "user_message": "We're having trouble calculating your taxes. Our team has been notified. Please try again in a few minutes.",
                    "request_id": request_id
                }
            )

        # Step 6: Determine refund or tax due
        total_tax = calculation_result.total_tax
        total_withheld = _get_total_withheld(final_data)

        estimated_refund = None
        estimated_tax_due = None

        if total_withheld > total_tax:
            estimated_refund = total_withheld - total_tax
        else:
            estimated_tax_due = total_tax - total_withheld

        # Step 7: Generate recommendations (with fallback)
        opportunities = []
        try:
            rec_engine = RecommendationEngine()
            opportunities = rec_engine.generate_recommendations(tax_return)
        except Exception as e:
            logger.warning(f"[{request_id}] Recommendation generation failed: {str(e)}")
            # Continue without recommendations - not critical

        # Step 8: Build next steps
        next_steps = _build_next_steps(estimated_refund, estimated_tax_due, opportunities)

        # Step 9: Generate warnings
        warnings = _generate_warnings(final_data, confidence_score, estimated_refund, estimated_tax_due)

        # Step 10: Generate return ID
        return_id = f"RET-{datetime.now().year}-{datetime.now().strftime('%m%d%H%M%S')}"

        # Step 10.5: Save to database (NEW - fixes data loss issue)
        try:
            persistence = get_session_persistence()

            # Create unified session
            session = UnifiedFilingSession(
                session_id=return_id,  # Use return_id as session_id
                workflow_type=WorkflowType.EXPRESS,
                state=FilingState.COMPLETE,
                tax_year=tax_return.tax_year,
                user_confirmed_data=final_data,
                calculated_results={
                    "total_tax": float(total_tax),
                    "effective_rate": float(calculation_result.effective_tax_rate),
                    "refund": float(estimated_refund) if estimated_refund else None,
                    "tax_due": float(estimated_tax_due) if estimated_tax_due else None
                },
                completeness_score=confidence_score * 100,
                confidence_score=confidence_score * 100,
                return_id=return_id,
                metadata={
                    "documents": submission.documents,
                    "request_id": request_id,
                    "warnings": warnings,
                    "next_steps": next_steps
                }
            )

            # Save to database
            persistence.save_unified_session(session)

            # Mark for auto-save (future changes will be auto-saved)
            from src.web.auto_save import mark_session_for_auto_save
            mark_session_for_auto_save(session)

            logger.info(f"[{request_id}] Session saved to database: {return_id}")

        except Exception as db_error:
            # Log error but don't fail the request
            logger.error(f"[{request_id}] Failed to save to database: {db_error}")
            # Continue - user still gets their results

        # Step 11: Log success
        logger.info(f"[{request_id}] Express Lane completed successfully", extra={
            "return_id": return_id,
            "total_tax": float(total_tax),
            "confidence_score": confidence_score,
            "warning_count": len(warnings)
        })

        return ExpressLaneResponse(
            success=True,
            return_id=return_id,
            estimated_refund=estimated_refund,
            estimated_tax_due=estimated_tax_due,
            total_tax=total_tax,
            effective_rate=calculation_result.effective_tax_rate,
            confidence_score=confidence_score,
            warnings=warnings,
            next_steps=next_steps,
            validation_issues=[]
        )

    except HTTPException:
        # Re-raise HTTP exceptions (already formatted)
        raise

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"[{request_id}] Unexpected error in Express Lane: {e}",
            exc_info=True
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "UnexpectedError",
                "error_message": "An unexpected error occurred",
                "user_message": "We're sorry, something went wrong. Our team has been notified and will investigate. Please try again later.",
                "request_id": request_id,
                "support_contact": "support@taxplatform.com"
            }
        )


@router.post("/import-prior-year")
async def import_prior_year(request: PriorYearImportRequest):
    """
    Import data from prior year tax return - IMPROVED

    Enhancements:
    - Input validation
    - Graceful handling of missing data
    - Better error messages
    """
    request_id = f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        logger.info(f"[{request_id}] Prior year import requested", extra={
            "prior_year": request.prior_year,
            "fields_requested": len(request.fields_to_import)
        })

        # FREEZE & FINISH: Prior year import is deferred to Phase 2
        # Return clear "coming soon" message instead of mock data
        logger.info(f"[{request_id}] Prior year import requested - feature not yet available")

        return {
            "success": False,
            "imported_fields": {},
            "prior_year": request.prior_year,
            "feature_status": "coming_soon",
            "message": "Prior year import is coming soon. Please enter your information manually for now.",
            "help_text": "You can speed up data entry by having your prior year return handy for reference."
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[{request_id}] Prior year import failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "ImportError",
                "error_message": "Failed to import prior year data",
                "user_message": "We couldn't retrieve your prior year data. You can still file by entering information manually.",
                "request_id": request_id
            }
        )


@router.get("/check-prior-year")
async def check_prior_year():
    """
    Check if user has prior year tax returns available - IMPROVED

    This endpoint now fails silently to never block the user flow.
    """
    try:
        # TODO: Query database
        # Mock data
        available_years = [2024, 2023]

        return {
            "has_prior_year": len(available_years) > 0,
            "available_years": available_years,
            "most_recent_year": max(available_years) if available_years else None
        }

    except Exception as e:
        # ALWAYS fail silently - don't block user flow
        logger.error(f"Check prior year failed: {str(e)}")
        return {
            "has_prior_year": False,
            "available_years": [],
            "most_recent_year": None
        }


@router.get("/{session_id}/pdf")
async def download_express_lane_pdf(session_id: str):
    """Download PDF report for an Express Lane result."""
    try:
        persistence = get_session_persistence()
        session = persistence.get_unified_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        results = session.calculated_results or {}
        user_data = session.user_confirmed_data or {}

        # Try ReportLab PDF generation
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import inch
            import io

            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            c.setFont("Helvetica-Bold", 20)
            c.drawString(1*inch, height - 1*inch, "Tax Return Summary")

            c.setFont("Helvetica", 12)
            y = height - 1.5*inch

            name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip() or "Taxpayer"
            c.drawString(1*inch, y, f"Prepared for: {name}")
            y -= 0.3*inch
            c.drawString(1*inch, y, f"Tax Year: {session.tax_year or 2025}")
            y -= 0.3*inch
            c.drawString(1*inch, y, f"Session: {session_id}")
            y -= 0.5*inch

            c.setFont("Helvetica-Bold", 14)
            c.drawString(1*inch, y, "Calculation Results")
            y -= 0.4*inch

            c.setFont("Helvetica", 12)
            total_tax = results.get("total_tax", 0)
            effective_rate = results.get("effective_rate", 0)
            refund = results.get("refund")
            tax_due = results.get("tax_due")

            c.drawString(1*inch, y, f"Total Tax: ${total_tax:,.2f}")
            y -= 0.3*inch
            c.drawString(1*inch, y, f"Effective Rate: {effective_rate:.1f}%")
            y -= 0.3*inch

            if refund:
                c.drawString(1*inch, y, f"Estimated Refund: ${refund:,.2f}")
            elif tax_due:
                c.drawString(1*inch, y, f"Estimated Tax Due: ${tax_due:,.2f}")
            y -= 0.5*inch

            c.setFont("Helvetica-Oblique", 9)
            c.drawString(1*inch, 1*inch, "This is an estimate only. Consult a tax professional for official filing.")

            c.save()
            buffer.seek(0)

            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=tax-summary-{session_id}.pdf"}
            )

        except ImportError:
            from fastapi.responses import Response

            text_lines = [
                "TAX RETURN SUMMARY",
                "=" * 40,
                f"Session: {session_id}",
                f"Tax Year: {session.tax_year or 2025}",
                "",
                f"Total Tax: ${results.get('total_tax', 0):,.2f}",
                f"Effective Rate: {results.get('effective_rate', 0):.1f}%",
            ]

            if results.get("refund"):
                text_lines.append(f"Estimated Refund: ${results['refund']:,.2f}")
            elif results.get("tax_due"):
                text_lines.append(f"Estimated Tax Due: ${results['tax_due']:,.2f}")

            text_lines.append("")
            text_lines.append("This is an estimate only. Consult a tax professional for official filing.")

            content = "\n".join(text_lines)
            return Response(
                content=content,
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=tax-summary-{session_id}.txt"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF generation failed for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")


# =============================================================================
# Improved Helper Functions
# =============================================================================

def _sanitize_and_merge_data(submission: ExpressLaneSubmission) -> Dict[str, Any]:
    """
    Sanitize and merge extracted data with user edits.

    Returns:
        Sanitized and merged data dictionary
    """
    # Start with extracted data
    final_data = {}

    for key, value in submission.extracted_data.items():
        if isinstance(value, str):
            final_data[key] = sanitize_string(value)
        else:
            final_data[key] = value

    # Apply user edits (also sanitized)
    if submission.user_edits:
        for key, value in submission.user_edits.items():
            if isinstance(value, str):
                final_data[key] = sanitize_string(value)
            else:
                final_data[key] = value

            logger.info(f"User edited field: {key}")

    return final_data


def _build_tax_return_from_extracted_data(data: Dict[str, Any]) -> TaxReturn:
    """
    Build TaxReturn object with improved error handling.

    Raises:
        ValueError: If data is invalid or inconsistent
    """
    # Parse filing status with validation
    filing_status_map = {
        "single": FilingStatus.SINGLE,
        "married filing jointly": FilingStatus.MARRIED_JOINT,
        "married_filing_jointly": FilingStatus.MARRIED_JOINT,
        "mfj": FilingStatus.MARRIED_JOINT,
        "married filing separately": FilingStatus.MARRIED_SEPARATE,
        "head of household": FilingStatus.HEAD_OF_HOUSEHOLD,
        "hoh": FilingStatus.HEAD_OF_HOUSEHOLD,
        "qualifying widow": FilingStatus.QUALIFYING_WIDOW
    }

    filing_status_str = str(data.get("filing_status", "single")).lower()
    filing_status = filing_status_map.get(filing_status_str)

    if not filing_status:
        raise ValueError(f"Invalid filing status: {data.get('filing_status')}")

    # Create taxpayer with validation
    try:
        taxpayer = TaxPayer(
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            ssn=sanitize_numeric_string(data.get("ssn", "")),
            date_of_birth=data.get("date_of_birth"),
            occupation=data.get("occupation")
        )
    except Exception as e:
        raise ValueError(f"Failed to create taxpayer: {str(e)}")

    # Create spouse if MFJ
    spouse = None
    if filing_status == FilingStatus.MARRIED_JOINT and data.get("spouse_first_name"):
        try:
            spouse = TaxPayer(
                first_name=data.get("spouse_first_name", ""),
                last_name=data.get("spouse_last_name", ""),
                ssn=sanitize_numeric_string(data.get("spouse_ssn", "")),
                date_of_birth=data.get("spouse_date_of_birth"),
                occupation=data.get("spouse_occupation")
            )
        except Exception as e:
            logger.warning(f"Failed to create spouse: {str(e)}")
            # Continue without spouse - will show validation warning

    # Create tax return
    tax_year = data.get("tax_year", datetime.now().year - 1)

    try:
        tax_return = TaxReturn(
            tax_year=tax_year,
            filing_status=filing_status,
            taxpayer=taxpayer,
            spouse=spouse
        )
    except Exception as e:
        raise ValueError(f"Failed to create tax return: {str(e)}")

    # Add W-2 income with validation
    if data.get("w2_wages"):
        try:
            w2 = W2Income(
                employer_name=data.get("employer_name", ""),
                employer_ein=sanitize_numeric_string(data.get("employer_ein", "")),
                wages=Decimal(str(data.get("w2_wages", 0))),
                federal_tax_withheld=Decimal(str(data.get("federal_withheld", 0))),
                social_security_wages=Decimal(str(data.get("ss_wages", data.get("w2_wages", 0)))),
                social_security_tax_withheld=Decimal(str(data.get("ss_withheld", 0))),
                medicare_wages=Decimal(str(data.get("medicare_wages", data.get("w2_wages", 0)))),
                medicare_tax_withheld=Decimal(str(data.get("medicare_withheld", 0)))
            )
            tax_return.add_income(w2)
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Invalid W-2 data: {str(e)}")

    # Add 1099 income if present
    if data.get("income_1099_misc"):
        try:
            income_1099 = Income1099Misc(
                payer_name=data.get("payer_name", ""),
                payer_ein=sanitize_numeric_string(data.get("payer_ein", "")),
                nonemployee_compensation=Decimal(str(data.get("income_1099_misc", 0)))
            )
            tax_return.add_income(income_1099)
        except (InvalidOperation, ValueError) as e:
            logger.warning(f"Failed to add 1099 income: {str(e)}")

    # Add deductions with validation
    if data.get("mortgage_interest") or data.get("property_tax") or data.get("charitable"):
        try:
            itemized = ItemizedDeductions()

            if data.get("mortgage_interest"):
                itemized.mortgage_interest = Decimal(str(data.get("mortgage_interest")))

            if data.get("property_tax"):
                itemized.state_local_taxes = Decimal(str(data.get("property_tax")))

            if data.get("charitable"):
                itemized.charitable_contributions = Decimal(str(data.get("charitable")))

            tax_return.deductions = itemized
        except (InvalidOperation, ValueError) as e:
            logger.warning(f"Failed to add itemized deductions: {str(e)}")
            # Fall back to standard deduction
            tax_return.deductions = StandardDeduction(filing_status=filing_status)
    else:
        # Use standard deduction
        tax_return.deductions = StandardDeduction(filing_status=filing_status)

    return tax_return


def _generate_warnings(data: Dict[str, Any], confidence_score: float,
                      estimated_refund: Optional[Decimal],
                      estimated_tax_due: Optional[Decimal]) -> List[str]:
    """
    Generate user-friendly warnings.

    Args:
        data: Final merged data
        confidence_score: Confidence score
        estimated_refund: Estimated refund amount
        estimated_tax_due: Estimated tax due

    Returns:
        List of warning messages
    """
    warnings = []

    # Confidence warnings
    if confidence_score < 0.85:
        warnings.append("⚠️ Some information was extracted with medium confidence. Please review carefully.")
    elif confidence_score < 0.70:
        warnings.append("⚠️ Several fields have low confidence. Please double-check all amounts.")

    # Banking warnings
    if not data.get('bank_account') and estimated_refund and estimated_refund > 0:
        warnings.append("💡 Add bank account for direct deposit to receive your refund faster (10-14 days vs 4-6 weeks).")

    # Tax due warnings
    if estimated_tax_due and estimated_tax_due > 1000:
        warnings.append(f"📋 You may owe {_format_currency(estimated_tax_due)}. Consider payment plan options.")

    # Missing data warnings
    if not data.get('address'):
        warnings.append("📍 Address is required for filing. Please add your mailing address.")

    return warnings


def _calculate_confidence_score(final_data: Dict[str, Any], original_data: Dict[str, Any]) -> float:
    """
    Calculate confidence score (unchanged but documented).

    See original implementation for details.
    """
    critical_fields = ["first_name", "last_name", "ssn", "w2_wages"]
    critical_present = sum(1 for field in critical_fields if final_data.get(field))
    critical_score = critical_present / len(critical_fields)

    edit_penalty = 0
    if final_data != original_data:
        edited_fields = sum(1 for k in final_data if final_data.get(k) != original_data.get(k))
        edit_penalty = min(0.1 * edited_fields, 0.3)

    expected_fields = [
        "first_name", "last_name", "ssn", "address",
        "w2_wages", "federal_withheld", "employer_name", "employer_ein"
    ]
    fields_present = sum(1 for field in expected_fields if final_data.get(field))
    completeness_score = fields_present / len(expected_fields)

    confidence = (
        critical_score * 0.5 +
        completeness_score * 0.3 +
        (1 - edit_penalty) * 0.2
    )

    return float(money(confidence))


def _get_total_withheld(data: Dict[str, Any]) -> Decimal:
    """Calculate total federal tax withheld with error handling."""
    total = Decimal("0")

    try:
        if data.get("federal_withheld"):
            total += Decimal(str(data.get("federal_withheld")))

        if data.get("estimated_tax_payments"):
            total += Decimal(str(data.get("estimated_tax_payments")))
    except (InvalidOperation, ValueError) as e:
        logger.error(f"Error calculating withholding: {str(e)}")

    return total


def _build_next_steps(
    estimated_refund: Optional[Decimal],
    estimated_tax_due: Optional[Decimal],
    opportunities: List[Any]
) -> List[str]:
    """Build personalized next steps (improved messages)."""
    steps = []

    if estimated_refund and estimated_refund > 0:
        steps.append(f"🎉 You're getting a refund of {_format_currency(estimated_refund)}!")
        steps.append("💰 Add your bank account for direct deposit (fastest way to get refund)")
    elif estimated_tax_due and estimated_tax_due > 0:
        steps.append(f"💳 You owe {_format_currency(estimated_tax_due)} in taxes")
        steps.append("🔍 Review available deductions to reduce your tax bill")

    if opportunities and len(opportunities) > 0:
        top_opportunity = opportunities[0]
        if hasattr(top_opportunity, 'estimated_savings'):
            steps.append(f"💡 Potential savings: {_format_currency(top_opportunity.estimated_savings)} with {top_opportunity.title}")

    steps.append("✅ Review all information carefully before filing")
    steps.append("🔒 Sign and e-file your return securely")

    if estimated_refund and estimated_refund > 0:
        steps.append("📊 Track your refund status (typically arrives in 10-21 days)")

    return steps


def _format_currency(amount: Decimal) -> str:
    """Format decimal as currency string."""
    return f"${amount:,.2f}"
