"""
Lead Magnet Page Routes

Serves HTML templates for the lead magnet funnel with CPA branding.
This module handles the frontend pages that interact with the lead magnet API.
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from cpa_panel.services.lead_magnet_service import get_lead_magnet_service

logger = logging.getLogger(__name__)

# Create router
lead_magnet_pages_router = APIRouter(
    prefix="/lead-magnet",
    tags=["Lead Magnet Pages"]
)

# Templates directory - includes lead_magnet subdirectory
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


def get_default_cpa_profile() -> dict:
    """Get default CPA profile for when no slug is specified."""
    return {
        "cpa_id": "default",
        "cpa_slug": "default",
        "display_name": "Tax Advisory Team",
        "firm_name": "Your Tax Advisor",
        "credentials": ["CPA", "EA"],
        "logo_url": None,
        "primary_color": "#2563eb",
        "secondary_color": "#1d4ed8",
        "accent_color": "#10b981",
        "booking_link": "#",
        "email": "contact@example.com",
        "phone": None,
        "bio": "Professional tax advisory services",
        "specialties": ["Individual Tax", "Business Tax", "Tax Planning"],
    }


async def get_cpa_profile_for_page(cpa_slug: Optional[str] = None) -> dict:
    """
    Load CPA profile for page rendering.

    Args:
        cpa_slug: CPA's unique URL slug

    Returns:
        CPA profile dict for template rendering
    """
    if not cpa_slug or cpa_slug == "default":
        return get_default_cpa_profile()

    try:
        service = get_lead_magnet_service()
        profile = service.get_cpa_profile_by_slug(cpa_slug)

        if profile:
            return profile
    except Exception as e:
        logger.warning(f"Failed to load CPA profile for {cpa_slug}: {e}")

    return get_default_cpa_profile()


async def get_session_data(session_id: str) -> Optional[dict]:
    """
    Load session data for page rendering.

    Args:
        session_id: Assessment session ID

    Returns:
        Session data dict or None
    """
    try:
        service = get_lead_magnet_service()
        session = service.get_session(session_id)
        if session:
            # Convert LeadMagnetSession object to dict for template use
            session_dict = session.to_dict()
            # Add cpa_slug for page routing
            if session.cpa_profile:
                session_dict["cpa_slug"] = session.cpa_profile.cpa_slug
            return session_dict
        return None
    except Exception as e:
        logger.warning(f"Failed to load session {session_id}: {e}")
        return None


# =============================================================================
# LEAD MAGNET LANDING PAGE
# =============================================================================

@lead_magnet_pages_router.get("/", response_class=HTMLResponse)
@lead_magnet_pages_router.get("", response_class=HTMLResponse)
async def lead_magnet_landing(
    request: Request,
    cpa: Optional[str] = None
):
    """
    Lead magnet landing page with CPA branding.

    URL: /lead-magnet?cpa=john-smith-cpa
    or: /lead-magnet/ (uses default branding)
    """
    cpa_profile = await get_cpa_profile_for_page(cpa)

    return templates.TemplateResponse(
        "lead_magnet/landing.html",
        {
            "request": request,
            "cpa": cpa_profile,
        }
    )


# =============================================================================
# QUICK ESTIMATE FORM (3 QUESTIONS)
# =============================================================================

@lead_magnet_pages_router.get("/estimate", response_class=HTMLResponse)
async def quick_estimate_form(
    request: Request,
    session: Optional[str] = None,
    cpa: Optional[str] = None
):
    """
    Quick estimate form - 3 questions to determine tax complexity.

    URL: /lead-magnet/estimate?session=xxx
    """
    # Validate session if provided
    session_data = None
    if session:
        session_data = await get_session_data(session)
        if not session_data:
            # Invalid session, redirect to landing
            return templates.TemplateResponse(
                "lead_magnet/landing.html",
                {
                    "request": request,
                    "cpa": await get_cpa_profile_for_page(cpa),
                    "error": "Session expired. Please start over.",
                }
            )
        # Get CPA from session if not specified
        if not cpa and session_data.get("cpa_slug"):
            cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)

    return templates.TemplateResponse(
        "lead_magnet/quick_estimate.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
        }
    )


# =============================================================================
# SAVINGS TEASER PAGE (TIER 1 PREVIEW)
# =============================================================================

@lead_magnet_pages_router.get("/teaser", response_class=HTMLResponse)
async def savings_teaser(
    request: Request,
    session: Optional[str] = None,
    cpa: Optional[str] = None
):
    """
    Savings teaser page - shows potential savings range to encourage contact capture.

    URL: /lead-magnet/teaser?session=xxx
    """
    session_data = None
    if session:
        session_data = await get_session_data(session)
        if not session_data:
            return templates.TemplateResponse(
                "lead_magnet/landing.html",
                {
                    "request": request,
                    "cpa": await get_cpa_profile_for_page(cpa),
                    "error": "Session expired. Please start over.",
                }
            )
        if not cpa and session_data.get("cpa_slug"):
            cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)

    return templates.TemplateResponse(
        "lead_magnet/savings_teaser.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
        }
    )


# =============================================================================
# CONTACT CAPTURE FORM (LEAD GATE)
# =============================================================================

@lead_magnet_pages_router.get("/contact", response_class=HTMLResponse)
async def contact_capture_form(
    request: Request,
    session: Optional[str] = None,
    cpa: Optional[str] = None
):
    """
    Contact capture form - the lead gate that creates the lead.

    URL: /lead-magnet/contact?session=xxx
    """
    session_data = None
    if session:
        session_data = await get_session_data(session)
        if not session_data:
            return templates.TemplateResponse(
                "lead_magnet/landing.html",
                {
                    "request": request,
                    "cpa": await get_cpa_profile_for_page(cpa),
                    "error": "Session expired. Please start over.",
                }
            )
        if not cpa and session_data.get("cpa_slug"):
            cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)

    return templates.TemplateResponse(
        "lead_magnet/contact_capture.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
        }
    )


# =============================================================================
# TIER 1 REPORT (FREE TEASER REPORT)
# =============================================================================

@lead_magnet_pages_router.get("/report", response_class=HTMLResponse)
async def tier_one_report(
    request: Request,
    session: Optional[str] = None,
    cpa: Optional[str] = None
):
    """
    Tier 1 FREE report page - shows teaser insights.

    URL: /lead-magnet/report?session=xxx
    """
    if not session:
        return templates.TemplateResponse(
            "lead_magnet/landing.html",
            {
                "request": request,
                "cpa": await get_cpa_profile_for_page(cpa),
                "error": "No session specified.",
            }
        )

    session_data = await get_session_data(session)
    if not session_data:
        return templates.TemplateResponse(
            "lead_magnet/landing.html",
            {
                "request": request,
                "cpa": await get_cpa_profile_for_page(cpa),
                "error": "Session expired. Please start over.",
            }
        )

    if not cpa and session_data.get("cpa_slug"):
        cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)

    # Get the Tier 1 report data
    try:
        service = get_lead_magnet_service()
        report_data = service.get_tier_one_report(session)
    except Exception as e:
        logger.error(f"Failed to get report for session {session}: {e}")
        report_data = None

    return templates.TemplateResponse(
        "lead_magnet/tier1_report.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
            "report": report_data,
        }
    )


# =============================================================================
# TIER 2 FULL ANALYSIS (REQUIRES ENGAGEMENT)
# =============================================================================

@lead_magnet_pages_router.get("/analysis", response_class=HTMLResponse)
async def tier_two_analysis(
    request: Request,
    session: Optional[str] = None,
    cpa: Optional[str] = None
):
    """
    Tier 2 full analysis page - requires engagement and letter acknowledgment.

    URL: /lead-magnet/analysis?session=xxx
    """
    if not session:
        return templates.TemplateResponse(
            "lead_magnet/landing.html",
            {
                "request": request,
                "cpa": await get_cpa_profile_for_page(cpa),
                "error": "No session specified.",
            }
        )

    session_data = await get_session_data(session)
    if not session_data:
        return templates.TemplateResponse(
            "lead_magnet/landing.html",
            {
                "request": request,
                "cpa": await get_cpa_profile_for_page(cpa),
                "error": "Session expired. Please start over.",
            }
        )

    if not cpa and session_data.get("cpa_slug"):
        cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)

    # Check if Tier 2 is unlocked
    try:
        service = get_lead_magnet_service()
        can_access, reason = service.can_access_tier_two_report_by_session(session)

        if not can_access:
            # Show locked state
            return templates.TemplateResponse(
                "lead_magnet/tier2_locked.html",
                {
                    "request": request,
                    "cpa": cpa_profile,
                    "session_id": session,
                    "session_data": session_data,
                    "reason": reason,
                }
            )

        # Get full report data
        report_data = service.get_tier_two_report(session)

    except Exception as e:
        logger.error(f"Failed to get full analysis for session {session}: {e}")
        return templates.TemplateResponse(
            "lead_magnet/tier1_report.html",
            {
                "request": request,
                "cpa": cpa_profile,
                "session_id": session,
                "session_data": session_data,
                "report": None,
                "error": "Unable to load full analysis. Please try again.",
            }
        )

    return templates.TemplateResponse(
        "lead_magnet/tier2_analysis.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
            "report": report_data,
        }
    )


# =============================================================================
# ENGAGEMENT LETTER PAGE
# =============================================================================

@lead_magnet_pages_router.get("/engagement-letter", response_class=HTMLResponse)
async def engagement_letter(
    request: Request,
    session: Optional[str] = None,
    lead: Optional[str] = None,
    cpa: Optional[str] = None
):
    """
    Engagement letter acknowledgment page.

    URL: /lead-magnet/engagement-letter?session=xxx&lead=yyy
    """
    if not session or not lead:
        return templates.TemplateResponse(
            "lead_magnet/landing.html",
            {
                "request": request,
                "cpa": await get_cpa_profile_for_page(cpa),
                "error": "Missing session or lead information.",
            }
        )

    session_data = await get_session_data(session)
    if not session_data:
        return templates.TemplateResponse(
            "lead_magnet/landing.html",
            {
                "request": request,
                "cpa": await get_cpa_profile_for_page(cpa),
                "error": "Session expired. Please start over.",
            }
        )

    if not cpa and session_data.get("cpa_slug"):
        cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)

    return templates.TemplateResponse(
        "lead_magnet/engagement_letter.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "lead_id": lead,
            "session_data": session_data,
        }
    )


# =============================================================================
# UNIVERSAL REPORT (DYNAMIC VISUALIZATION REPORT)
# =============================================================================

@lead_magnet_pages_router.get("/universal-report", response_class=HTMLResponse)
async def universal_report_page(
    request: Request,
    session: Optional[str] = None,
    cpa: Optional[str] = None,
    tier: int = 1
):
    """
    Universal Report page - dynamic report with visualizations.

    Uses the Universal Report Engine for:
    - Savings gauge/meter
    - Charts and graphs
    - CPA branding
    - Tiered content (1=teaser, 2=full, 3=complete)

    URL: /lead-magnet/universal-report?session=xxx&cpa=john-smith&tier=2
    """
    if not session:
        return templates.TemplateResponse(
            "lead_magnet/landing.html",
            {
                "request": request,
                "cpa": await get_cpa_profile_for_page(cpa),
                "error": "No session specified.",
            }
        )

    session_data = await get_session_data(session)
    if not session_data:
        return templates.TemplateResponse(
            "lead_magnet/landing.html",
            {
                "request": request,
                "cpa": await get_cpa_profile_for_page(cpa),
                "error": "Session expired. Please start over.",
            }
        )

    if not cpa and session_data.get("cpa_slug"):
        cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)

    try:
        from universal_report import UniversalReportEngine

        # Convert CPA profile to theme format
        theme_profile = {
            "firm_name": cpa_profile.get("firm_name", "Tax Advisory"),
            "advisor_name": cpa_profile.get("display_name"),
            "credentials": cpa_profile.get("credentials", []),
            "primary_color": cpa_profile.get("primary_color", "#2563eb"),
            "secondary_color": cpa_profile.get("secondary_color", "#1d4ed8"),
            "accent_color": cpa_profile.get("accent_color", "#10b981"),
            "logo_url": cpa_profile.get("logo_url"),
            "contact_email": cpa_profile.get("email"),
            "contact_phone": cpa_profile.get("phone"),
        }

        # Generate universal report HTML
        engine = UniversalReportEngine()
        html_content = engine.generate_html_report(
            source_type='lead_magnet',
            source_id=session,
            source_data=session_data,
            cpa_profile=theme_profile,
            tier_level=tier,
        )

        # Return the generated HTML directly
        return HTMLResponse(content=html_content, media_type="text/html")

    except ImportError as e:
        logger.warning(f"Universal report engine not available: {e}")
        # Fallback to template-based report
        return templates.TemplateResponse(
            "lead_magnet/tier1_report.html",
            {
                "request": request,
                "cpa": cpa_profile,
                "session_id": session,
                "session_data": session_data,
                "report": None,
                "error": "Enhanced report temporarily unavailable.",
            }
        )
    except Exception as e:
        logger.error(f"Universal report generation failed: {e}")
        return templates.TemplateResponse(
            "lead_magnet/tier1_report.html",
            {
                "request": request,
                "cpa": cpa_profile,
                "session_id": session,
                "session_data": session_data,
                "report": None,
                "error": f"Report generation failed: {str(e)}",
            }
        )
