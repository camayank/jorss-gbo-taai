"""
Advisory Report REST API - FastAPI endpoints for advisory reports.

Provides endpoints to:
- Generate advisory reports
- Check report status
- Download PDF reports
- List reports for a session
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from pathlib import Path
import logging
import uuid

# Standardized error handling
try:
    from web.helpers.error_responses import (
        create_error_response,
        raise_api_error,
        not_found_error,
        server_error,
        ErrorCode,
    )
    STANDARD_ERRORS_AVAILABLE = True
except ImportError:
    STANDARD_ERRORS_AVAILABLE = False

from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income
from models.deductions import Deductions
from models.credits import TaxCredits
from advisory import generate_advisory_report, ReportType
from advisory.report_generator import AdvisoryReportResult
from export import export_advisory_report_to_pdf
from database.session_persistence import get_session_persistence
from database.advisory_models import (
    create_advisory_report_from_result,
    get_advisory_report_by_id,
    get_advisory_reports_by_session,
    update_report_pdf_path,
    delete_advisory_report,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Tax Opportunity Detection
try:
    from services.tax_opportunity_detector import (
        TaxOpportunityDetector,
        TaxpayerProfile,
        create_profile_from_tax_return,
    )
    OPPORTUNITY_DETECTOR_AVAILABLE = True
except ImportError:
    OPPORTUNITY_DETECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/advisory-reports", tags=["Advisory Reports"])

# Database setup
DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class AdvisoryReportRequest(BaseModel):
    """Request to generate an advisory report."""
    session_id: str = Field(..., description="Tax session ID")
    report_type: str = Field(
        default="standard_report",
        description="Report type: executive_summary, standard_report, entity_comparison, multi_year, full_analysis"
    )
    include_entity_comparison: bool = Field(default=False, description="Include business entity analysis")
    include_multi_year: bool = Field(default=True, description="Include multi-year projections")
    years_ahead: int = Field(default=3, ge=1, le=10, description="Years to project (1-10)")
    generate_pdf: bool = Field(default=True, description="Generate PDF immediately")
    watermark: Optional[str] = Field(default="DRAFT", description="PDF watermark (null for final)")


class AdvisoryReportResponse(BaseModel):
    """Response with report information."""
    report_id: str
    session_id: str
    status: str  # "generating", "complete", "error"
    report_type: str
    taxpayer_name: str
    generated_at: str

    # Financial summary
    current_tax_liability: float
    potential_savings: float
    recommendations_count: int
    confidence_score: float

    # PDF info
    pdf_available: bool = False
    pdf_url: Optional[str] = None

    # Error info
    error_message: Optional[str] = None


class ReportListResponse(BaseModel):
    """List of reports."""
    reports: List[AdvisoryReportResponse]
    total: int


# ============================================================================
# IN-MEMORY STORAGE (with DB fallback for persistence across restarts)
# ============================================================================

# Store generated reports (report_id -> AdvisoryReportResult)
_report_store: dict[str, AdvisoryReportResult] = {}

# Store PDF paths (report_id -> pdf_path)
_pdf_store: dict[str, str] = {}

# Store session mappings (session_id -> list[report_id])
_session_reports: dict[str, List[str]] = {}

# Store reverse mapping (report_id -> session_id)
_report_session: dict[str, str] = {}


def _hydrate_from_db(report_id: str) -> Optional[AdvisoryReportResult]:
    """Load a report from DB into memory cache. Returns None if not found."""
    try:
        db_session = SessionLocal()
        try:
            db_report = get_advisory_report_by_id(report_id, db_session)
            if not db_report:
                return None

            # Re-cache in memory stores
            report_data = db_report.report_data or {}
            report = AdvisoryReportResult(**report_data) if report_data else None
            if report:
                _report_store[report_id] = report
                _report_session[report_id] = db_report.session_id
                if db_report.session_id not in _session_reports:
                    _session_reports[db_report.session_id] = []
                if report_id not in _session_reports[db_report.session_id]:
                    _session_reports[db_report.session_id].append(report_id)
                if db_report.pdf_path and db_report.pdf_generated:
                    _pdf_store[report_id] = db_report.pdf_path

            return report
        finally:
            db_session.close()
    except Exception as e:
        logger.warning(f"DB hydration failed for report {report_id}: {e}")
        return None


def _hydrate_session_from_db(session_id: str) -> List[str]:
    """Load all reports for a session from DB into memory cache."""
    try:
        db_session = SessionLocal()
        try:
            db_reports = get_advisory_reports_by_session(session_id, db_session)
            report_ids = []
            for db_report in db_reports:
                rid = db_report.report_id
                report_ids.append(rid)
                if rid not in _report_store:
                    report_data = db_report.report_data or {}
                    try:
                        report = AdvisoryReportResult(**report_data)
                        _report_store[rid] = report
                        _report_session[rid] = session_id
                        if db_report.pdf_path and db_report.pdf_generated:
                            _pdf_store[rid] = db_report.pdf_path
                    except Exception:
                        pass
            if report_ids:
                _session_reports[session_id] = report_ids
            return report_ids
        finally:
            db_session.close()
    except Exception as e:
        logger.warning(f"DB session hydration failed for {session_id}: {e}")
        return []


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_tax_return_from_session(session_id: str, tenant_id: str = "default") -> TaxReturn:
    """
    Get TaxReturn from session ID by loading from database.

    Args:
        session_id: Session identifier
        tenant_id: Tenant identifier for security

    Returns:
        TaxReturn object

    Raises:
        HTTPException: If session not found or tax return data missing
    """
    persistence = get_session_persistence()

    # Load tax return data from session
    tax_return_data = persistence.load_session_tax_return(session_id, tenant_id)

    if not tax_return_data:
        if STANDARD_ERRORS_AVAILABLE:
            raise_api_error(
                ErrorCode.SESSION_NOT_FOUND,
                message=f"No tax return data found for session {session_id}",
                details=[{"field": "session_id", "message": "Session not found or expired"}]
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No tax return data found for session {session_id}"
            )

    # Extract data
    return_data = tax_return_data.get("return_data", {})
    calculated_results = tax_return_data.get("calculated_results")
    tax_year = tax_return_data.get("tax_year", 2025)

    try:
        # Reconstruct TaxReturn object from stored data
        taxpayer_data = return_data.get("taxpayer", {})
        income_data = return_data.get("income", {})
        deductions_data = return_data.get("deductions", {})
        credits_data = return_data.get("credits", {})

        # Build taxpayer info
        filing_status_str = taxpayer_data.get("filing_status", "SINGLE")
        filing_status = FilingStatus[filing_status_str] if isinstance(filing_status_str, str) else filing_status_str

        taxpayer = TaxpayerInfo(
            first_name=taxpayer_data.get("first_name", "Unknown"),
            last_name=taxpayer_data.get("last_name", "Taxpayer"),
            ssn=taxpayer_data.get("ssn", "000-00-0000"),
            filing_status=filing_status,
        )

        # Build income
        income = Income(
            w2_wages=float(income_data.get("w2_wages", 0)),
            federal_withholding=float(income_data.get("federal_withholding", 0)),
            self_employment_income=float(income_data.get("self_employment_income", 0)),
            self_employment_expenses=float(income_data.get("self_employment_expenses", 0)),
            investment_income=float(income_data.get("investment_income", 0)),
            capital_gains=float(income_data.get("capital_gains", 0)),
            rental_income=float(income_data.get("rental_income", 0)),
        )

        # Build deductions
        deductions = Deductions(
            use_standard_deduction=deductions_data.get("use_standard_deduction", True),
            itemized_deductions=float(deductions_data.get("itemized_deductions", 0)),
            state_local_taxes=float(deductions_data.get("state_local_taxes", 0)),
            mortgage_interest=float(deductions_data.get("mortgage_interest", 0)),
            charitable_contributions=float(deductions_data.get("charitable_contributions", 0)),
        )

        # Build credits
        credits = TaxCredits(
            child_tax_credit=float(credits_data.get("child_tax_credit", 0)),
            earned_income_credit=float(credits_data.get("earned_income_credit", 0)),
            education_credits=float(credits_data.get("education_credits", 0)),
            retirement_savings_credit=float(credits_data.get("retirement_savings_credit", 0)),
        )

        # Create TaxReturn
        tax_return = TaxReturn(
            tax_year=tax_year,
            taxpayer=taxpayer,
            income=income,
            deductions=deductions,
            credits=credits,
        )

        # Calculate if not already calculated
        if not calculated_results:
            tax_return.calculate()

        return tax_return

    except Exception as e:
        logger.error(f"Error reconstructing TaxReturn from session data: {str(e)}", exc_info=True)
        if STANDARD_ERRORS_AVAILABLE:
            raise_api_error(
                ErrorCode.PROCESSING_ERROR,
                message="Failed to load tax return data. Please try again.",
                details=[{"field": "session_data", "message": str(e)}]
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading tax return data: {str(e)}"
            )


def _generate_report_sync(
    tax_return: TaxReturn,
    report_type: ReportType,
    include_entity_comparison: bool,
    include_multi_year: bool,
    years_ahead: int,
) -> AdvisoryReportResult:
    """Generate report synchronously."""
    try:
        report = generate_advisory_report(
            tax_return=tax_return,
            report_type=report_type,
            include_entity_comparison=include_entity_comparison,
            include_multi_year=include_multi_year,
            years_ahead=years_ahead,
        )
        return report
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        raise


def _generate_pdf_async(report_id: str, report: AdvisoryReportResult, watermark: Optional[str]):
    """Generate PDF in background task and update database."""
    try:
        output_dir = Path("/tmp/advisory_reports")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{report_id}.pdf"

        pdf_path = export_advisory_report_to_pdf(
            report=report,
            output_path=str(output_path),
            watermark=watermark,
            include_charts=False,  # Can enable when charts implemented
        )

        # Update database with PDF path
        db_session = SessionLocal()
        try:
            update_report_pdf_path(report_id, pdf_path, db_session)
            logger.info(f"PDF generated and saved for report {report_id}: {pdf_path}")
        finally:
            db_session.close()

        # Also store in memory for backward compatibility
        _pdf_store[report_id] = pdf_path

    except Exception as e:
        logger.error(f"Error generating PDF for {report_id}: {str(e)}", exc_info=True)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/generate", response_model=AdvisoryReportResponse)
async def generate_report(
    request: AdvisoryReportRequest,
    background_tasks: BackgroundTasks,
    tax_return: Optional[TaxReturn] = None,  # For testing, can pass directly
):
    """
    Generate an advisory report.

    Returns immediately with report data. PDF generation happens in background.
    Poll /api/v1/advisory-reports/{report_id} to check PDF status.
    """
    logger.info(f"Generating advisory report for session {request.session_id}")

    # Get tax return
    if tax_return is None:
        tax_return = _get_tax_return_from_session(request.session_id)

    # Parse report type
    try:
        report_type = ReportType(request.report_type)
    except ValueError:
        if STANDARD_ERRORS_AVAILABLE:
            raise_api_error(
                ErrorCode.INVALID_INPUT,
                message=f"Invalid report type: {request.report_type}",
                details=[{
                    "field": "report_type",
                    "message": "Must be one of: executive_summary, standard_report, entity_comparison, multi_year, full_analysis"
                }]
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid report type: {request.report_type}"
            )

    # Generate report
    try:
        report = _generate_report_sync(
            tax_return=tax_return,
            report_type=report_type,
            include_entity_comparison=request.include_entity_comparison,
            include_multi_year=request.include_multi_year,
            years_ahead=request.years_ahead,
        )

        # Save report to database
        db_session = SessionLocal()
        try:
            db_report = create_advisory_report_from_result(
                result=report,
                session_id=request.session_id,
                session=db_session,
            )
            logger.info(f"Saved advisory report {report.report_id} to database")
        except Exception as e:
            logger.error(f"Error saving report to database: {str(e)}", exc_info=True)
            # Continue even if database save fails
        finally:
            db_session.close()

        # Also store in memory for backward compatibility
        _report_store[report.report_id] = report

        # Track session -> report mapping (in-memory)
        if request.session_id not in _session_reports:
            _session_reports[request.session_id] = []
        _session_reports[request.session_id].append(report.report_id)

        # Track reverse mapping (report_id -> session_id)
        _report_session[report.report_id] = request.session_id

        # Generate PDF in background if requested
        if request.generate_pdf:
            background_tasks.add_task(
                _generate_pdf_async,
                report.report_id,
                report,
                request.watermark,
            )

        # Build response
        response = AdvisoryReportResponse(
            report_id=report.report_id,
            session_id=request.session_id,
            status=report.status,
            report_type=report.report_type.value,
            taxpayer_name=report.taxpayer_name,
            generated_at=report.generated_at,
            current_tax_liability=float(report.current_tax_liability),
            potential_savings=float(report.potential_savings),
            recommendations_count=report.top_recommendations_count,
            confidence_score=float(report.confidence_score),
            pdf_available=False,  # PDF generating in background
            pdf_url=f"/api/v1/advisory-reports/{report.report_id}/pdf",
            error_message=report.error_message,
        )

        return response

    except Exception as e:
        logger.error(f"Error in generate_report: {str(e)}", exc_info=True)
        if STANDARD_ERRORS_AVAILABLE:
            raise_api_error(
                ErrorCode.PROCESSING_ERROR,
                message="Failed to generate advisory report. Please try again.",
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}", response_model=AdvisoryReportResponse)
async def get_report_status(report_id: str):
    """
    Get report status and metadata.

    Check if PDF is ready for download.
    """
    report = _report_store.get(report_id) or _hydrate_from_db(report_id)

    if not report:
        if STANDARD_ERRORS_AVAILABLE:
            raise_api_error(
                ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Report with ID '{report_id}' not found.",
                details=[{"field": "report_id", "message": "Report does not exist or has expired"}]
            )
        else:
            raise HTTPException(status_code=404, detail="Report not found")

    # Get session_id from mapping
    session_id = _report_session.get(report_id, "unknown")

    # Check if PDF is ready
    pdf_available = report_id in _pdf_store
    pdf_url = f"/api/v1/advisory-reports/{report_id}/pdf" if pdf_available else None

    return AdvisoryReportResponse(
        report_id=report.report_id,
        session_id=session_id,
        status=report.status,
        report_type=report.report_type.value,
        taxpayer_name=report.taxpayer_name,
        generated_at=report.generated_at,
        current_tax_liability=float(report.current_tax_liability),
        potential_savings=float(report.potential_savings),
        recommendations_count=report.top_recommendations_count,
        confidence_score=float(report.confidence_score),
        pdf_available=pdf_available,
        pdf_url=pdf_url,
        error_message=report.error_message,
    )


@router.get("/{report_id}/pdf")
async def download_pdf(report_id: str):
    """
    Download PDF report.

    Returns 404 if PDF not ready yet.
    """
    pdf_path = _pdf_store.get(report_id)

    # Try DB fallback if not in memory
    if not pdf_path:
        _hydrate_from_db(report_id)
        pdf_path = _pdf_store.get(report_id)

    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail="PDF not ready yet. Check /api/v1/advisory-reports/{report_id} for status."
        )

    # Get report for filename
    report = _report_store.get(report_id)
    filename = f"advisory_report_{report.tax_year}_{report.taxpayer_name.replace(' ', '_')}.pdf"

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.get("/{report_id}/data")
async def get_report_data(report_id: str):
    """
    Get report data as JSON.

    Returns full report structure for frontend display.
    """
    report = _report_store.get(report_id) or _hydrate_from_db(report_id)

    if not report:
        if STANDARD_ERRORS_AVAILABLE:
            raise_api_error(
                ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Report data for ID '{report_id}' not found.",
            )
        else:
            raise HTTPException(status_code=404, detail="Report not found")

    return report.to_dict()


@router.get("/session/{session_id}/reports", response_model=ReportListResponse)
async def list_session_reports(session_id: str):
    """
    List all reports for a session.
    """
    report_ids = _session_reports.get(session_id, [])

    # Fall back to DB if no reports in memory for this session
    if not report_ids:
        report_ids = _hydrate_session_from_db(session_id)

    reports = []
    for report_id in report_ids:
        report = _report_store.get(report_id)
        if report:
            pdf_available = report_id in _pdf_store

            reports.append(AdvisoryReportResponse(
                report_id=report.report_id,
                session_id=session_id,
                status=report.status,
                report_type=report.report_type.value,
                taxpayer_name=report.taxpayer_name,
                generated_at=report.generated_at,
                current_tax_liability=float(report.current_tax_liability),
                potential_savings=float(report.potential_savings),
                recommendations_count=report.top_recommendations_count,
                confidence_score=float(report.confidence_score),
                pdf_available=pdf_available,
                pdf_url=f"/api/v1/advisory-reports/{report_id}/pdf" if pdf_available else None,
            ))

    return ReportListResponse(
        reports=reports,
        total=len(reports),
    )


@router.delete("/{report_id}")
async def delete_report(report_id: str):
    """
    Delete a report and its PDF.
    """
    # Delete from stores
    if report_id in _report_store:
        del _report_store[report_id]

    # Delete PDF file
    if report_id in _pdf_store:
        pdf_path = _pdf_store[report_id]
        try:
            Path(pdf_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not delete PDF {pdf_path}: {e}")
        del _pdf_store[report_id]

    # Remove from session mappings
    for session_id, report_ids in _session_reports.items():
        if report_id in report_ids:
            report_ids.remove(report_id)

    return {"status": "deleted", "report_id": report_id}


# ============================================================================
# TESTING ENDPOINT (Remove in production)
# ============================================================================

@router.post("/test/generate-sample")
async def generate_sample_report(background_tasks: BackgroundTasks):
    """
    Generate a sample advisory report for testing.

    This endpoint creates a sample TaxReturn and generates a report.
    Remove in production - for testing only.
    """
    from models.taxpayer import TaxpayerInfo, FilingStatus
    from models.income import Income
    from models.deductions import Deductions
    from models.credits import TaxCredits

    # Create sample tax return
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Sample",
            last_name="Client",
            ssn="000-00-0000",
            filing_status=FilingStatus.SINGLE,
        ),
        income=Income(
            w2_wages=100000.0,
            federal_withholding=18000.0,
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )
    tax_return.calculate()

    # Generate report
    request = AdvisoryReportRequest(
        session_id="test_session",
        report_type="full_analysis",
        generate_pdf=True,
    )

    return await generate_report(request, background_tasks, tax_return=tax_return)


# ============================================================================
# TAX OPPORTUNITY DETECTION ENDPOINTS
# ============================================================================

class TaxOpportunityRequest(BaseModel):
    """Request for tax opportunity detection."""
    session_id: str = Field(..., description="Tax session ID")
    include_ai_analysis: bool = Field(default=True, description="Include AI-powered analysis")


class TaxOpportunityItem(BaseModel):
    """A single tax-saving opportunity."""
    id: str
    title: str
    description: str
    category: str
    priority: str  # high, medium, low
    estimated_savings: Optional[float] = None
    savings_range: Optional[dict] = None  # {min, max}
    action_required: str
    irs_reference: Optional[str] = None
    deadline: Optional[str] = None
    confidence: float
    follow_up_questions: List[str] = []


class TaxOpportunitiesResponse(BaseModel):
    """Response with detected tax opportunities."""
    session_id: str
    total_opportunities: int
    estimated_total_savings: float
    savings_range: Optional[dict] = None  # {min, max}
    high_priority_count: int
    opportunities: List[TaxOpportunityItem]
    by_category: dict = {}  # category -> count
    generated_at: str


@router.post("/opportunities", response_model=TaxOpportunitiesResponse)
async def detect_tax_opportunities(request: TaxOpportunityRequest):
    """
    Detect tax-saving opportunities for a session.

    Uses AI-powered analysis to identify:
    - Missed deductions
    - Eligible credits
    - Retirement contribution opportunities
    - Business optimization strategies
    - Timing opportunities

    Returns prioritized list with estimated savings.
    """
    if not OPPORTUNITY_DETECTOR_AVAILABLE:
        if STANDARD_ERRORS_AVAILABLE:
            raise_api_error(
                ErrorCode.SERVICE_UNAVAILABLE,
                message="Tax opportunity detection is temporarily unavailable.",
            )
        else:
            raise HTTPException(
                status_code=501,
                detail="Tax opportunity detection not available"
            )

    logger.info(f"Detecting tax opportunities for session {request.session_id}")

    # Get tax return from session
    tax_return = _get_tax_return_from_session(request.session_id)

    try:
        # Create profile from tax return
        profile = create_profile_from_tax_return(tax_return)

        # Detect opportunities
        detector = TaxOpportunityDetector()
        opportunities = detector.detect_opportunities(profile)

        # Get summary
        summary = detector.get_opportunity_summary(opportunities)

        # Convert to response format
        opp_items = []
        for opp in opportunities:
            opp_items.append(TaxOpportunityItem(
                id=opp.id,
                title=opp.title,
                description=opp.description,
                category=opp.category.value,
                priority=opp.priority.value,
                estimated_savings=float(opp.estimated_savings) if opp.estimated_savings else None,
                savings_range={
                    "min": float(opp.savings_range[0]),
                    "max": float(opp.savings_range[1])
                } if opp.savings_range else None,
                action_required=opp.action_required,
                irs_reference=opp.irs_reference,
                deadline=opp.deadline,
                confidence=opp.confidence,
                follow_up_questions=opp.follow_up_questions or []
            ))

        return TaxOpportunitiesResponse(
            session_id=request.session_id,
            total_opportunities=summary["total_opportunities"],
            estimated_total_savings=summary["estimated_total_savings"],
            savings_range=summary.get("savings_range"),
            high_priority_count=summary["high_priority_count"],
            opportunities=opp_items,
            by_category={k: len(v) for k, v in summary.get("by_category", {}).items()},
            generated_at=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error detecting opportunities: {str(e)}", exc_info=True)
        if STANDARD_ERRORS_AVAILABLE:
            raise_api_error(
                ErrorCode.PROCESSING_ERROR,
                message="Failed to detect tax opportunities. Please try again.",
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities/{session_id}", response_model=TaxOpportunitiesResponse)
async def get_tax_opportunities(session_id: str):
    """
    Get tax opportunities for a session (GET version).

    Same as POST but uses path parameter.
    """
    request = TaxOpportunityRequest(session_id=session_id)
    return await detect_tax_opportunities(request)
