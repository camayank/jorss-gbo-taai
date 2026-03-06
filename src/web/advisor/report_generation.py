"""
Report generation endpoints extracted from intelligent_advisor_api.py.

Contains:
- POST /report (session report)
- POST /generate-report (full advisory report)
- POST /report/email (email report)
- Branding/logo endpoints
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel

from security.session_token import verify_session_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Report Generation"])


class SessionReportRequest(BaseModel):
    """Request for session-based report."""
    session_id: str


class EmailReportRequest(BaseModel):
    """Request to email a report."""
    session_id: str
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None


@router.post("/report")
async def get_session_report(request: SessionReportRequest, _session: str = Depends(verify_session_token)):
    """Get report data for a session (used by report preview page)."""
    from web.intelligent_advisor_api import chat_engine

    try:
        CPA_BRANDING_HELPER_AVAILABLE = False
        get_cpa_branding_for_report = None
        try:
            from utils.cpa_branding_helper import get_cpa_branding_for_report as _get_branding
            CPA_BRANDING_HELPER_AVAILABLE = True
            get_cpa_branding_for_report = _get_branding
        except ImportError:
            pass

        session = await chat_engine.get_or_create_session(request.session_id)

        if not session.get("profile"):
            raise HTTPException(status_code=404, detail="Session not found or has no data")

        calculation = session.get("calculations")
        strategies = session.get("strategies", [])
        profile = session.get("profile", {})

        if not calculation and profile and profile.get("total_income") and profile.get("filing_status"):
            calculation = await chat_engine.get_tax_calculation(profile)
            strategies = await chat_engine.get_tax_strategies(profile, calculation)
            await chat_engine.update_session(request.session_id, {
                "calculations": calculation,
                "strategies": strategies,
            })

        if not calculation:
            raise HTTPException(
                status_code=400,
                detail="No tax calculation available. Please complete the tax analysis first."
            )

        cpa_branding = None
        try:
            session_cpa_id = session.get("cpa_id")
            if session_cpa_id and CPA_BRANDING_HELPER_AVAILABLE:
                cpa_branding = get_cpa_branding_for_report(session_cpa_id)
        except Exception:
            pass

        # Try full report generation via AdvisoryReportGenerator (same as PDF route)
        try:
            from advisory.report_generator import AdvisoryReportGenerator, ReportType
            from web.intelligent_advisor_api import build_tax_return_from_profile

            tax_return = build_tax_return_from_profile(profile)
            generator = AdvisoryReportGenerator()
            report = generator.generate_report(
                tax_return=tax_return,
                report_type=ReportType.FULL_ANALYSIS,
                include_entity_comparison=profile.get("is_self_employed", False),
                include_multi_year=True,
                years_ahead=3,
            )

            report_dict = report.to_dict()

            # Build action_plan for backward compat with intelligent-advisor.js
            action_plan = None
            try:
                for sec in report.sections:
                    if sec.section_id == "action_plan":
                        action_plan = sec.content
                        break
            except Exception:
                pass

            return {
                "session_id": request.session_id,
                **report_dict,
                "cpa_branding": cpa_branding,
                "report": {"action_plan": action_plan},
            }
        except Exception as gen_err:
            logger.warning(f"AdvisoryReportGenerator failed, falling back to raw response: {gen_err}")

        # Fallback: return raw calculation/strategies/profile
        return {
            "session_id": request.session_id,
            "tax_calculation": calculation.dict() if hasattr(calculation, 'dict') else calculation,
            "strategies": [s.dict() if hasattr(s, 'dict') else s for s in strategies],
            "profile": profile,
            "cpa_branding": cpa_branding,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session report error: {e}")
        raise HTTPException(status_code=500, detail="Unable to retrieve session report.")


@router.post("/generate-report")
async def generate_report(request=None, _session: str = Depends(verify_session_token)):
    """Generate a professional advisory report."""
    from web.intelligent_advisor_api import (
        chat_engine, AI_REPORT_NARRATIVES_ENABLED, STANDARD_DISCLAIMER,
    )

    CPA_BRANDING_HELPER_AVAILABLE = False
    get_cpa_branding_for_report = None
    try:
        from utils.cpa_branding_helper import get_cpa_branding_for_report as _get_branding
        CPA_BRANDING_HELPER_AVAILABLE = True
        get_cpa_branding_for_report = _get_branding
    except ImportError:
        pass

    try:
        profile = request.profile.dict(exclude_none=True)
        calculation = await chat_engine.get_tax_calculation(profile)
        strategies = await chat_engine.get_tax_strategies(profile, calculation)

        summary = await chat_engine.generate_executive_summary(profile, calculation, strategies)

        # Generate multi-level summaries (AI-powered, optional)
        multi_summaries = None
        if AI_REPORT_NARRATIVES_ENABLED:
            try:
                from advisory.report_summarizer import get_report_summarizer
                summarizer = get_report_summarizer()
                report_data = {
                    "metrics": {
                        "total_tax": calculation.total_tax,
                        "federal_tax": calculation.federal_tax,
                        "state_tax": calculation.state_tax,
                        "effective_rate": calculation.effective_rate,
                        "total_savings": sum(s.estimated_savings for s in strategies),
                    },
                    "recommendations": [
                        {"title": s.title, "savings": s.estimated_savings, "priority": s.priority}
                        for s in strategies[:5]
                    ],
                }
                summaries = await summarizer.generate_all_summaries(
                    report_data, profile.get("name", "Taxpayer")
                )
                multi_summaries = {
                    "one_liner": summaries.one_liner if summaries.one_liner else None,
                    "tweet": summaries.tweet if summaries.tweet else None,
                    "executive": summaries.executive if summaries.executive else None,
                    "detailed": summaries.detailed if summaries.detailed else None,
                }
            except Exception as e:
                logger.warning(f"Multi-level summaries failed: {e}")

        # Safety checks
        safety_checks = None
        try:
            sess = await chat_engine.get_or_create_session(request.session_id)
            safety_checks = sess.get("safety_checks")
        except Exception:
            pass

        # Build action items
        action_items = [
            {
                "priority": s.priority,
                "action": s.action_steps[0] if s.action_steps else s.title,
                "title": s.title,
                "deadline": s.deadline,
            }
            for s in strategies[:5]
        ]

        # Generate AI action plan narrative
        action_plan = None
        if AI_REPORT_NARRATIVES_ENABLED:
            try:
                from advisory.ai_narrative_generator import get_narrative_generator, ClientProfile as NarrClientProfile
                narrator = get_narrative_generator()
                client_profile = NarrClientProfile(
                    name=profile.get("name", "Taxpayer"),
                    occupation=profile.get("occupation", ""),
                    financial_goals=["Minimize tax liability and maximize savings"],
                    primary_concern="Tax optimization",
                )
                plan_narrative = await narrator.generate_action_plan_narrative(action_items, client_profile)
                if plan_narrative and plan_narrative.content:
                    action_plan = {
                        "narrative": plan_narrative.content,
                        "key_points": plan_narrative.key_points,
                        "tone": plan_narrative.tone_used,
                    }
            except Exception as e:
                logger.warning(f"Action plan narrative failed: {e}")

        # Email summaries
        email_summary_client = None
        email_summary_internal = None
        if AI_REPORT_NARRATIVES_ENABLED:
            try:
                from advisory.report_summarizer import get_report_summarizer
                summarizer = get_report_summarizer()
                report_data_for_email = {
                    "metrics": {
                        "total_tax": calculation.total_tax,
                        "federal_tax": calculation.federal_tax,
                        "state_tax": calculation.state_tax,
                        "effective_rate": calculation.effective_rate,
                        "total_savings": sum(s.estimated_savings for s in strategies),
                    },
                    "recommendations": [
                        {"title": s.title, "savings": s.estimated_savings, "priority": s.priority}
                        for s in strategies[:5]
                    ],
                }
                email_summary_client = await summarizer.generate_summary_for_email(
                    report_data_for_email, recipient_type="client"
                )
                email_summary_internal = await summarizer.generate_summary_for_email(
                    report_data_for_email, recipient_type="internal"
                )
            except Exception as e:
                logger.warning(f"Email summary generation failed: {e}")

        # CPA branding
        cpa_branding = None
        try:
            sess = sess if 'sess' in dir() else await chat_engine.get_or_create_session(request.session_id)
            session_cpa_id = sess.get("cpa_id") if sess else None
            if session_cpa_id and CPA_BRANDING_HELPER_AVAILABLE:
                cpa_branding = get_cpa_branding_for_report(session_cpa_id)
        except Exception as brand_err:
            logger.debug(f"CPA branding lookup failed (non-blocking): {brand_err}")

        return {
            "session_id": request.session_id,
            "report": {
                "title": "Tax Advisory Report - 2025",
                "generated_at": datetime.now().isoformat(),
                "executive_summary": summary,
                "summaries": multi_summaries,
                "tax_position": calculation.dict(),
                "strategies": [s.dict() for s in strategies],
                "total_potential_savings": sum(s.estimated_savings for s in strategies),
                "action_items": action_items,
                "action_plan": action_plan,
                "email_summary_client": email_summary_client,
                "email_summary_internal": email_summary_internal,
                "safety_checks": safety_checks,
                "cpa_branding": cpa_branding,
                "disclaimer": (
                    "This report is for informational purposes only and does not constitute professional tax advice.\n"
                    "Please consult with a licensed CPA or tax professional before making any tax-related decisions.\n"
                    "Tax laws are subject to change, and individual circumstances may vary."
                ),
            },
            "download_url": f"/api/advisor/report/{request.session_id}/pdf",
        }
    except Exception as e:
        logger.error(f"Generate report error: {e}")
        raise HTTPException(status_code=500, detail="Unable to generate report.")


@router.post("/report/email")
async def email_report(request: EmailReportRequest, _session: str = Depends(verify_session_token)):
    """Email a tax advisory report to the user."""
    from web.intelligent_advisor_api import chat_engine

    try:
        session = await chat_engine.get_or_create_session(request.session_id)
        profile = session.get("profile", {})

        if not profile:
            raise HTTPException(status_code=404, detail="No profile data for this session.")

        calculation = session.get("calculations")
        strategies = session.get("strategies", [])

        if not calculation:
            calculation = await chat_engine.get_tax_calculation(profile)
            strategies = await chat_engine.get_tax_strategies(profile, calculation)

        # Generate email body
        total_savings = sum(
            (s.estimated_savings if hasattr(s, 'estimated_savings') else s.get('estimated_savings', 0))
            for s in strategies
        )

        email_body_client = f"""
Hi {request.name or 'there'},

Thank you for using our Tax Advisory platform. Here's a summary of your analysis:

Total Potential Tax Savings: ${total_savings:,.0f}
Number of Strategies Identified: {len(strategies)}

A CPA will reach out within 24 hours to discuss your personalized plan.

Best regards,
Tax Advisory Team
"""

        email_body_internal = f"""
New Lead Report:
- Name: {request.name or 'Not provided'}
- Email: {request.email}
- Phone: {request.phone or 'Not provided'}
- Session: {request.session_id}
- Potential Savings: ${total_savings:,.0f}
- Strategies: {len(strategies)}
"""

        # Try to send email
        email_sent = False
        try:
            from services.email import send_email
            await send_email(
                to=request.email,
                subject="Your Tax Advisory Report",
                body=email_body_client,
            )
            email_sent = True
        except Exception as e:
            logger.warning(f"Email delivery failed (lead still captured): {e}")

        return {
            "success": True,
            "session_id": request.session_id,
            "lead_captured": True,
            "email_queued": email_sent,
            "message": (
                "Your report has been emailed. A CPA will reach out within 24 hours."
                if email_sent
                else "Your information has been received. A CPA will reach out within 24 hours."
            ),
            "email_body_client": email_body_client,
            "email_body_internal": email_body_internal,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email report error: {e}")
        raise HTTPException(status_code=500, detail="Unable to send report email.")


# =========================================================================
# BRANDING / LOGO ENDPOINTS
# =========================================================================

@router.post("/branding/upload-logo")
async def upload_logo(
    cpa_id: str = Form(...),
    file: UploadFile = File(...),
    _session: str = Depends(verify_session_token),
):
    """Upload a logo for CPA branding."""
    try:
        from utils.logo_handler import logo_handler
    except ImportError:
        raise HTTPException(status_code=503, detail="Logo handler not available")

    allowed_types = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    try:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:  # 5MB limit
            raise HTTPException(status_code=400, detail="Logo file too large (max 5MB)")

        result = logo_handler.save_logo(cpa_id, content, file.content_type, file.filename)
        return {
            "success": True,
            "cpa_id": cpa_id,
            "logo_url": result.get("url"),
            "message": "Logo uploaded successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logo upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload logo")


@router.get("/branding/logo/{cpa_id}")
async def get_logo(cpa_id: str):
    """Get CPA logo image."""
    try:
        from utils.logo_handler import logo_handler
    except ImportError:
        raise HTTPException(status_code=503, detail="Logo handler not available")

    try:
        logo_data = logo_handler.get_logo(cpa_id)
        if not logo_data:
            raise HTTPException(status_code=404, detail="Logo not found")

        from fastapi.responses import Response
        return Response(
            content=logo_data["content"],
            media_type=logo_data.get("content_type", "image/png"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logo retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve logo")


@router.delete("/branding/logo/{cpa_id}")
async def delete_logo(cpa_id: str, _session: str = Depends(verify_session_token)):
    """Delete CPA logo."""
    try:
        from utils.logo_handler import logo_handler
    except ImportError:
        raise HTTPException(status_code=503, detail="Logo handler not available")

    try:
        logo_handler.delete_logo(cpa_id)
        return {"success": True, "message": "Logo deleted"}
    except Exception as e:
        logger.error(f"Logo delete error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete logo")


@router.get("/rate-limit/status")
async def get_rate_limit_status(session_id: str, _session: str = Depends(verify_session_token)):
    """Get rate limit status for a session."""
    try:
        from utils.rate_limiter import pdf_rate_limiter
        return {
            "session_id": session_id,
            "rate_limit": {
                "max_requests": pdf_rate_limiter.config.max_requests,
                "window_seconds": pdf_rate_limiter.config.window_seconds,
            },
        }
    except ImportError:
        return {"session_id": session_id, "rate_limit": {"available": False}}
