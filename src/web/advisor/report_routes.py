"""
Report generation routes for the Intelligent Advisor.

Extracted from intelligent_advisor_api.py for maintainability.
Includes safety check, PDF generation, and universal report endpoints.
"""

import os
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from security.session_token import verify_session_token

logger = logging.getLogger(__name__)

_report_router = APIRouter(tags=["advisor-reports"])


def _get_chat_engine():
    """Lazy-import chat_engine from the main advisor module."""
    from web.intelligent_advisor_api import chat_engine
    return chat_engine


def _get_build_safety_summary():
    """Lazy-import _build_safety_summary from the main advisor module."""
    from web.intelligent_advisor_api import _build_safety_summary
    return _build_safety_summary


# =============================================================================
# SAFETY CHECK ENDPOINT
# =============================================================================

@_report_router.get("/safety-check/{session_id}")
async def get_safety_check(session_id: str, _session: str = Depends(verify_session_token)):
    """Return fraud / compliance / anomaly results for a session (CPA panel polling)."""
    chat_engine = _get_chat_engine()
    _build_safety_summary = _get_build_safety_summary()

    try:
        session = await chat_engine.get_or_create_session(session_id)
        safety = session.get("safety_checks")
        if not safety:
            return {"session_id": session_id, "status": "pending", "safety_checks": None}

        categories = {
            "fraud_detection": {
                "fraud": safety.get("fraud"),
                "identity_theft": safety.get("identity_theft"),
                "refund_risk": safety.get("refund_risk"),
            },
            "compliance": {
                "general": safety.get("compliance"),
                "eitc_due_diligence": safety.get("eitc_compliance"),
                "circular_230": safety.get("circular_230"),
            },
            "anomaly_detection": {
                "anomalies": safety.get("anomaly"),
                "audit_risk": safety.get("audit_risk"),
                "data_errors": safety.get("data_errors"),
            },
        }

        return {
            "session_id": session_id,
            "status": "complete",
            "safety_checks": safety,
            "categories": categories,
            "checks_completed": list(safety.keys()),
            "total_checks": len(safety),
            "user_summary": _build_safety_summary(safety),
        }
    except Exception as e:
        logger.error(f"Safety check retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Unable to retrieve safety checks.")


# =============================================================================
# PDF GENERATION ENDPOINTS
# =============================================================================

@_report_router.get("/report/{session_id}/pdf")
async def get_session_pdf(
    session_id: str,
    background_tasks: BackgroundTasks,
    include_charts: bool = True,
    include_toc: bool = True,
    cpa_id: Optional[str] = None,
    firm_name: Optional[str] = None,
    advisor_name: Optional[str] = None,
    advisor_credentials: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    primary_color: Optional[str] = None,
    watermark: Optional[str] = None,
    _session: str = Depends(verify_session_token),
):
    """Generate and download PDF report for a session."""
    from fastapi.responses import FileResponse

    chat_engine = _get_chat_engine()

    # Lazy-import module-level flags from main file
    from web.intelligent_advisor_api import (
        RATE_LIMITER_AVAILABLE,
        PDF_GENERATION_AVAILABLE,
        build_tax_return_from_profile,
    )

    if RATE_LIMITER_AVAILABLE:
        from web.intelligent_advisor_api import pdf_rate_limiter
        if not pdf_rate_limiter.is_allowed(session_id):
            remaining = pdf_rate_limiter.get_remaining(session_id)
            reset_time = pdf_rate_limiter.get_reset_time(session_id)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": "Too many PDF generation requests. Please wait before trying again.",
                    "remaining": remaining,
                    "retry_after": int(reset_time) + 1,
                }
            )
        pdf_rate_limiter.record_request(session_id)

    session = chat_engine.sessions.get(session_id)

    if not session:
        session = await chat_engine.get_or_create_session(session_id)
        if not session.get("profile"):
            raise HTTPException(status_code=404, detail="Session not found or has no data")

    profile = session.get("profile", {})

    if not profile.get("filing_status") or not profile.get("total_income"):
        raise HTTPException(
            status_code=400,
            detail="Insufficient data for PDF generation. Please complete the tax analysis first."
        )

    if not PDF_GENERATION_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF generation service temporarily unavailable. Please try the advisory reports API."
        )

    try:
        from export.advisory_pdf_exporter import (
            export_advisory_report_to_pdf,
            CPABrandConfig
        )
        from advisory.report_generator import AdvisoryReportGenerator, ReportType

        tax_return = build_tax_return_from_profile(profile)

        generator = AdvisoryReportGenerator()
        report = generator.generate_report(
            tax_return=tax_return,
            report_type=ReportType.FULL_ANALYSIS,
            include_entity_comparison=profile.get("is_self_employed", False),
            include_multi_year=True,
            years_ahead=3
        )

        brand_config = None

        if cpa_id:
            try:
                from web.intelligent_advisor_api import CPA_BRANDING_HELPER_AVAILABLE, create_pdf_brand_config
                if CPA_BRANDING_HELPER_AVAILABLE:
                    brand_config = create_pdf_brand_config(cpa_id)
                    if brand_config:
                        logger.info(f"Using CPA branding from profile: {cpa_id}")
            except ImportError:
                pass

        if not brand_config and any([firm_name, advisor_name, contact_email, contact_phone, primary_color]):
            credentials_list = []
            if advisor_credentials:
                credentials_list = [c.strip() for c in advisor_credentials.split(",")]

            brand_config = CPABrandConfig(
                firm_name=firm_name or "Tax Advisory Services",
                advisor_name=advisor_name,
                advisor_credentials=credentials_list,
                contact_email=contact_email,
                contact_phone=contact_phone,
                primary_color=primary_color or "#2c5aa0",
            )

        import tempfile as _tempfile
        tmp = _tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="advisor_report_")
        pdf_path = tmp.name
        tmp.close()

        export_advisory_report_to_pdf(
            report=report,
            output_path=pdf_path,
            watermark=watermark,
            include_charts=include_charts,
            include_toc=include_toc,
            brand_config=brand_config,
        )

        background_tasks.add_task(os.unlink, pdf_path)

        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"tax_advisory_report_{session_id}.pdf"
        )

    except Exception as e:
        logger.exception(f"PDF generation failed for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate PDF report. Please try again."
        )


@_report_router.post("/report/{session_id}/generate-pdf")
async def generate_session_pdf(session_id: str, _session: str = Depends(verify_session_token)):
    """Generate PDF via the advisory reports API."""
    chat_engine = _get_chat_engine()

    session = await chat_engine.get_or_create_session(session_id)
    profile = session.get("profile", {})

    if not profile.get("filing_status") or not profile.get("total_income"):
        raise HTTPException(
            status_code=400,
            detail="Insufficient data. Please complete the tax analysis first."
        )

    chat_engine._save_tax_return_for_advisory(session_id, profile)

    try:
        from web.advisory_api import (
            _report_store, _pdf_store, _session_reports, _report_session,
            _get_tax_return_from_session, _generate_report_sync, _generate_pdf_async
        )
        from advisory.report_generator import ReportType

        tax_return = _get_tax_return_from_session(session_id)

        report = _generate_report_sync(
            tax_return=tax_return,
            report_type=ReportType.FULL_ANALYSIS,
            include_entity_comparison=profile.get("is_self_employed", False),
            include_multi_year=True,
            years_ahead=3
        )

        _report_store[report.report_id] = report
        if session_id not in _session_reports:
            _session_reports[session_id] = []
        _session_reports[session_id].append(report.report_id)
        _report_session[report.report_id] = session_id

        _generate_pdf_async(report.report_id, report, watermark=None)
        pdf_available = report.report_id in _pdf_store

        return {
            "success": True,
            "report_id": report.report_id,
            "session_id": session_id,
            "pdf_available": pdf_available,
            "pdf_url": f"/api/v1/advisory-reports/{report.report_id}/pdf",
            "taxpayer_name": report.taxpayer_name,
            "potential_savings": float(report.potential_savings),
            "recommendations_count": report.top_recommendations_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to generate PDF for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate report. Please try again."
        )


# =============================================================================
# UNIVERSAL REPORT ENDPOINTS
# =============================================================================

class UniversalReportRequest(BaseModel):
    """Request for universal report generation."""
    session_id: str
    cpa_profile: Optional[Dict[str, Any]] = None
    output_format: str = "html"  # "html", "pdf", "both"
    tier_level: int = 2  # 1=teaser, 2=full, 3=complete


@_report_router.post("/universal-report")
async def generate_universal_report(request: UniversalReportRequest, _session: str = Depends(verify_session_token)):
    """Generate a universal report with dynamic visualizations."""
    chat_engine = _get_chat_engine()

    try:
        from universal_report import UniversalReportEngine

        session = await chat_engine.get_or_create_session(request.session_id)
        profile = session.get("profile", {})

        if not profile.get("filing_status"):
            raise HTTPException(
                status_code=400,
                detail="Insufficient data. Please complete the tax analysis first."
            )

        calculation = session.get("calculations")
        strategies = session.get("strategies", [])

        if not calculation and profile.get("total_income"):
            calculation = await chat_engine.get_tax_calculation(profile)
            strategies = await chat_engine.get_tax_strategies(profile, calculation)
            await chat_engine.update_session(request.session_id, {
                "calculations": calculation,
                "strategies": strategies
            })

        session_data = {
            "profile": profile,
            "calculations": calculation.dict() if hasattr(calculation, 'dict') else calculation,
            "strategies": [s.dict() if hasattr(s, 'dict') else s for s in strategies],
            "lead_score": session.get("lead_score", 0),
            "complexity": chat_engine.determine_complexity(profile),
            "key_insights": session.get("key_insights", []),
            "warnings": session.get("warnings", []),
        }

        engine = UniversalReportEngine()
        output = engine.generate_report(
            source_type='chatbot',
            source_id=request.session_id,
            source_data=session_data,
            cpa_profile=request.cpa_profile,
            output_format=request.output_format,
            tier_level=request.tier_level,
        )

        return {
            "success": True,
            "report_id": output.report_id,
            "session_id": request.session_id,
            "html_content": output.html_content if request.output_format in ('html', 'both') else None,
            "pdf_available": output.pdf_bytes is not None,
            "taxpayer_name": output.taxpayer_name,
            "tax_year": output.tax_year,
            "potential_savings": output.potential_savings,
            "recommendation_count": output.recommendation_count,
            "total_sections": output.total_sections,
        }

    except ImportError as e:
        logger.error(f"Universal report module not available: {e}")
        raise HTTPException(status_code=503, detail="Universal report generation not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Universal report generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report. Please try again.")


@_report_router.get("/universal-report/{session_id}/html")
async def get_universal_report_html(
    session_id: str,
    cpa: Optional[str] = None,
    tier: int = 2,
    _session: str = Depends(verify_session_token),
):
    """Get HTML universal report for a session."""
    from fastapi.responses import HTMLResponse

    chat_engine = _get_chat_engine()

    try:
        from universal_report import UniversalReportEngine

        session = await chat_engine.get_or_create_session(session_id)
        profile = session.get("profile", {})

        if not profile.get("filing_status"):
            raise HTTPException(status_code=404, detail="Session not found or has no data")

        cpa_profile = None
        if cpa:
            try:
                from cpa_panel.services.lead_magnet_service import get_lead_magnet_service
                service = get_lead_magnet_service()
                cpa_profile = service.get_cpa_profile_by_slug(cpa)
            except Exception:
                pass
            if not cpa_profile:
                cpa_profile = {"firm_name": cpa, "preset": "professional"}

        calculation = session.get("calculations")
        strategies = session.get("strategies", [])

        if not calculation and profile.get("total_income"):
            calculation = await chat_engine.get_tax_calculation(profile)
            strategies = await chat_engine.get_tax_strategies(profile, calculation)

        session_data = {
            "profile": profile,
            "calculations": calculation.dict() if hasattr(calculation, 'dict') else calculation,
            "strategies": [s.dict() if hasattr(s, 'dict') else s for s in strategies],
            "lead_score": session.get("lead_score", 0),
            "complexity": chat_engine.determine_complexity(profile),
        }

        engine = UniversalReportEngine()
        html = engine.generate_html_report(
            source_type='chatbot',
            source_id=session_id,
            source_data=session_data,
            cpa_profile=cpa_profile,
            tier_level=tier,
        )

        return HTMLResponse(content=html, media_type="text/html")

    except ImportError as e:
        logger.error(f"Universal report module not available: {e}")
        raise HTTPException(status_code=503, detail="Universal report not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Universal report HTML failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate HTML report. Please try again.")


@_report_router.get("/universal-report/{session_id}/pdf")
async def get_universal_report_pdf(
    session_id: str,
    cpa: Optional[str] = None,
    tier: int = 2,
    _session: str = Depends(verify_session_token),
):
    """Get PDF universal report for a session."""
    chat_engine = _get_chat_engine()

    try:
        from universal_report import UniversalReportEngine

        session = await chat_engine.get_or_create_session(session_id)
        profile = session.get("profile", {})

        if not profile.get("filing_status"):
            raise HTTPException(status_code=404, detail="Session not found or has no data")

        cpa_profile = None
        if cpa:
            try:
                from cpa_panel.services.lead_magnet_service import get_lead_magnet_service
                service = get_lead_magnet_service()
                cpa_profile = service.get_cpa_profile_by_slug(cpa)
            except Exception:
                pass
            if not cpa_profile:
                cpa_profile = {"firm_name": cpa, "preset": "professional"}

        calculation = session.get("calculations")
        strategies = session.get("strategies", [])

        if not calculation and profile.get("total_income"):
            calculation = await chat_engine.get_tax_calculation(profile)
            strategies = await chat_engine.get_tax_strategies(profile, calculation)

        session_data = {
            "profile": profile,
            "calculations": calculation.dict() if hasattr(calculation, 'dict') else calculation,
            "strategies": [s.dict() if hasattr(s, 'dict') else s for s in strategies],
            "lead_score": session.get("lead_score", 0),
            "complexity": chat_engine.determine_complexity(profile),
        }

        engine = UniversalReportEngine()
        output = engine.generate_report(
            source_type='chatbot',
            source_id=session_id,
            source_data=session_data,
            cpa_profile=cpa_profile,
            output_format='pdf',
            tier_level=tier,
        )

        if output.pdf_bytes:
            import io as _io
            return StreamingResponse(
                _io.BytesIO(output.pdf_bytes),
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="tax_report_{session_id}.pdf"'}
            )
        else:
            raise HTTPException(status_code=500, detail="PDF generation failed")

    except ImportError as e:
        logger.error(f"Universal report module not available: {e}")
        raise HTTPException(status_code=503, detail="Universal report not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Universal report PDF failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF report. Please try again.")
