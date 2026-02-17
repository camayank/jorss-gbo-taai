"""
Lead Magnet Page Routes

Serves HTML templates for the lead magnet funnel with CPA branding.
This module handles the frontend pages that interact with the lead magnet API.
"""

import os
import logging
import random
from typing import Optional
from datetime import date
from html import escape

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response

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

LEAD_MAGNET_VARIANTS = ("A", "B", "C", "D", "E")
LEAD_MAGNET_VARIANT_COOKIE = "lm_variant_hero"
LEAD_MAGNET_DEFAULT_VARIANT = (os.getenv("LEAD_MAGNET_DEFAULT_VARIANT", "A") or "A").strip().upper()
LEAD_MAGNET_RANDOMIZE_VARIANTS = (os.getenv("LEAD_MAGNET_RANDOMIZE_VARIANTS", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}


def get_default_cpa_profile() -> dict:
    """Get default CPA profile for when no slug is specified."""
    return {
        "cpa_id": "default",
        "cpa_slug": "default",
        "display_name": "Tax Advisory Team",
        "firm_name": "Your Tax Advisor",
        "credentials": ["CPA", "EA"],
        "logo_url": None,
        "primary_color": "#1e3a5f",
        "secondary_color": "#152b47",
        "accent_color": "#10b981",
        "booking_link": "#",
        "email": "contact@example.com",
        "phone": None,
        "bio": "Professional tax advisory services",
        "specialties": ["Individual Tax", "Business Tax", "Tax Planning"],
    }


def get_deadline_context() -> dict:
    """Compute tax deadline urgency context for taxpayer-facing pages."""
    today = date.today()
    deadline = date(today.year, 4, 15)
    if today > deadline:
        deadline = date(today.year + 1, 4, 15)

    days_remaining = (deadline - today).days
    if days_remaining <= 30:
        urgency = "critical"
    elif days_remaining <= 75:
        urgency = "high"
    elif days_remaining <= 150:
        urgency = "moderate"
    else:
        urgency = "planning"

    return {
        "deadline_date": deadline.isoformat(),
        "days_remaining": days_remaining,
        "urgency": urgency,
    }


def _normalize_variant(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = str(value).strip().upper()
    if candidate in LEAD_MAGNET_VARIANTS:
        return candidate
    return None


def resolve_variant_id(request: Request, session_data: Optional[dict] = None) -> str:
    """Resolve active funnel variant from query -> session -> cookie -> random."""
    requested = _normalize_variant(request.query_params.get("v"))
    if requested:
        return requested
    if session_data:
        session_variant = _normalize_variant(session_data.get("variant_id"))
        if session_variant:
            return session_variant
    cookie_variant = _normalize_variant(request.cookies.get(LEAD_MAGNET_VARIANT_COOKIE))
    if cookie_variant:
        return cookie_variant
    default_variant = _normalize_variant(LEAD_MAGNET_DEFAULT_VARIANT) or "A"
    if LEAD_MAGNET_RANDOMIZE_VARIANTS:
        return random.choice(LEAD_MAGNET_VARIANTS)
    return default_variant


def apply_variant_cookie(response: HTMLResponse, variant_id: str) -> None:
    response.set_cookie(
        key=LEAD_MAGNET_VARIANT_COOKIE,
        value=variant_id,
        max_age=60 * 60 * 24 * 30,
        httponly=False,
        samesite="lax",
    )


def normalize_cpa_profile(profile: dict) -> dict:
    """Normalize CPA branding payload for template compatibility."""
    normalized = dict(profile or {})
    credentials = normalized.get("credentials")
    if isinstance(credentials, str):
        normalized["credentials"] = [credentials]
    elif not credentials:
        normalized["credentials"] = ["CPA"]

    normalized.setdefault("primary_color", "#1e3a5f")
    normalized.setdefault("secondary_color", "#152b47")
    normalized.setdefault("accent_color", "#10b981")
    return normalized


async def get_cpa_profile_for_page(cpa_slug: Optional[str] = None) -> dict:
    """
    Load CPA profile for page rendering.

    Args:
        cpa_slug: CPA's unique URL slug

    Returns:
        CPA profile dict for template rendering
    """
    if not cpa_slug or cpa_slug == "default":
        return normalize_cpa_profile(get_default_cpa_profile())

    try:
        service = get_lead_magnet_service()
        profile = service.get_cpa_profile_by_slug(cpa_slug)

        if profile:
            return normalize_cpa_profile(profile)
    except Exception as e:
        logger.warning(f"Failed to load CPA profile for {cpa_slug}: {e}")

    return normalize_cpa_profile(get_default_cpa_profile())


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
    variant_id = resolve_variant_id(request)

    response = templates.TemplateResponse(
        "lead_magnet/landing.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "deadline_context": get_deadline_context(),
            "variant_id": variant_id,
        }
    )
    apply_variant_cookie(response, variant_id)
    return response


@lead_magnet_pages_router.get("/share-card.svg")
async def lead_magnet_share_card(
    score: int = 58,
    band: str = "Needs Attention",
    savings: Optional[str] = None,
    cpa: Optional[str] = None,
):
    """Render OG-compatible share card for taxpayer score sharing."""
    safe_score = max(0, min(100, int(score)))
    cpa_profile = await get_cpa_profile_for_page(cpa)
    primary = cpa_profile.get("primary_color") or "#1e3a5f"
    accent = cpa_profile.get("accent_color") or "#10b981"
    firm_name = cpa_profile.get("firm_name") or cpa_profile.get("display_name") or "Your CPA"
    savings_line = savings or "Potential savings identified"
    if safe_score >= 81:
        zone_color = "#16a34a"
    elif safe_score >= 61:
        zone_color = "#84cc16"
    elif safe_score >= 41:
        zone_color = "#f97316"
    else:
        zone_color = "#dc2626"
    circumference = 2 * 3.141592653589793 * 84
    ring_offset = circumference - (safe_score / 100.0) * circumference
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="Tax Health Score share card">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{escape(primary)}"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <g transform="translate(110, 80)">
    <text x="0" y="0" fill="#93c5fd" font-size="30" font-family="Inter,Segoe UI,Arial,sans-serif">Tax Health Score</text>
    <text x="0" y="70" fill="#ffffff" font-size="62" font-family="Inter,Segoe UI,Arial,sans-serif" font-weight="700">{escape(firm_name)}</text>
    <text x="0" y="130" fill="#cbd5e1" font-size="32" font-family="Inter,Segoe UI,Arial,sans-serif">{escape(savings_line)}</text>
    <text x="0" y="185" fill="#cbd5e1" font-size="24" font-family="Inter,Segoe UI,Arial,sans-serif">My score: {safe_score}/100 ({escape(band)})</text>
    <text x="0" y="238" fill="#e2e8f0" font-size="24" font-family="Inter,Segoe UI,Arial,sans-serif">Check yours in under 2 minutes.</text>
  </g>
  <g transform="translate(850, 315)">
    <circle cx="0" cy="0" r="84" fill="none" stroke="#1e293b" stroke-width="20"/>
    <circle cx="0" cy="0" r="84" fill="none" stroke="{zone_color}" stroke-width="20"
      stroke-linecap="round" stroke-dasharray="{circumference:.2f}" stroke-dashoffset="{ring_offset:.2f}"
      transform="rotate(-90)"/>
    <text x="0" y="8" text-anchor="middle" fill="#ffffff" font-size="54" font-family="Inter,Segoe UI,Arial,sans-serif" font-weight="800">{safe_score}</text>
    <text x="0" y="40" text-anchor="middle" fill="#cbd5e1" font-size="20" font-family="Inter,Segoe UI,Arial,sans-serif">/100</text>
  </g>
  <rect x="80" y="540" width="1040" height="4" fill="{escape(accent)}" opacity="0.8"/>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


# =============================================================================
# QUICK ESTIMATE FORM (4 QUESTIONS)
# =============================================================================

@lead_magnet_pages_router.get("/estimate", response_class=HTMLResponse)
async def quick_estimate_form(
    request: Request,
    session: Optional[str] = None,
    cpa: Optional[str] = None
):
    """
    Quick estimate form - 4 questions to determine tax complexity.

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
                    "deadline_context": get_deadline_context(),
                }
            )
        # Get CPA from session if not specified
        if not cpa and session_data.get("cpa_slug"):
            cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)
    variant_id = resolve_variant_id(request, session_data=session_data)

    response = templates.TemplateResponse(
        "lead_magnet/quick_estimate.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
            "deadline_context": get_deadline_context(),
            "variant_id": variant_id,
        }
    )
    apply_variant_cookie(response, variant_id)
    return response


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
                    "deadline_context": get_deadline_context(),
                }
            )
        if not cpa and session_data.get("cpa_slug"):
            cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)
    variant_id = resolve_variant_id(request, session_data=session_data)

    response = templates.TemplateResponse(
        "lead_magnet/savings_teaser.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
            "deadline_context": get_deadline_context(),
            "variant_id": variant_id,
        }
    )
    apply_variant_cookie(response, variant_id)
    return response


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
                    "deadline_context": get_deadline_context(),
                }
            )
        if not cpa and session_data.get("cpa_slug"):
            cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)
    variant_id = resolve_variant_id(request, session_data=session_data)

    response = templates.TemplateResponse(
        "lead_magnet/contact_capture.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
            "deadline_context": get_deadline_context(),
            "variant_id": variant_id,
        }
    )
    apply_variant_cookie(response, variant_id)
    return response


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
                "deadline_context": get_deadline_context(),
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
                "deadline_context": get_deadline_context(),
            }
        )

    if not cpa and session_data.get("cpa_slug"):
        cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)
    variant_id = resolve_variant_id(request, session_data=session_data)

    # Get the Tier 1 report data
    try:
        service = get_lead_magnet_service()
        report_data = service.get_tier_one_report(session)
    except Exception as e:
        logger.error(f"Failed to get report for session {session}: {e}")
        report_data = None

    response = templates.TemplateResponse(
        "lead_magnet/tier1_report.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
            "report": report_data,
            "deadline_context": get_deadline_context(),
            "variant_id": variant_id,
        }
    )
    apply_variant_cookie(response, variant_id)
    return response


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
                "deadline_context": get_deadline_context(),
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
                "deadline_context": get_deadline_context(),
            }
        )

    if not cpa and session_data.get("cpa_slug"):
        cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)
    variant_id = resolve_variant_id(request, session_data=session_data)

    # Check if Tier 2 is unlocked
    try:
        service = get_lead_magnet_service()
        can_access, reason = service.can_access_tier_two_report_by_session(session)

        if not can_access:
            # Show locked state
            response = templates.TemplateResponse(
                "lead_magnet/tier2_locked.html",
                {
                    "request": request,
                    "cpa": cpa_profile,
                    "session_id": session,
                    "session_data": session_data,
                    "reason": reason,
                    "deadline_context": get_deadline_context(),
                    "variant_id": variant_id,
                }
            )
            apply_variant_cookie(response, variant_id)
            return response

        # Get full report data
        report_data = service.get_tier_two_report(session)

    except Exception as e:
        logger.error(f"Failed to get full analysis for session {session}: {e}")
        response = templates.TemplateResponse(
            "lead_magnet/tier1_report.html",
            {
                "request": request,
                "cpa": cpa_profile,
                "session_id": session,
                "session_data": session_data,
                "report": None,
                "error": "Unable to load full analysis. Please try again.",
                "deadline_context": get_deadline_context(),
                "variant_id": variant_id,
            }
        )
        apply_variant_cookie(response, variant_id)
        return response

    response = templates.TemplateResponse(
        "lead_magnet/tier2_analysis.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "session_data": session_data,
            "report": report_data,
            "deadline_context": get_deadline_context(),
            "variant_id": variant_id,
        }
    )
    apply_variant_cookie(response, variant_id)
    return response


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
                "deadline_context": get_deadline_context(),
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
                "deadline_context": get_deadline_context(),
            }
        )

    if not cpa and session_data.get("cpa_slug"):
        cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)
    variant_id = resolve_variant_id(request, session_data=session_data)

    response = templates.TemplateResponse(
        "lead_magnet/engagement_letter.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "session_id": session,
            "lead_id": lead,
            "session_data": session_data,
            "deadline_context": get_deadline_context(),
            "variant_id": variant_id,
        }
    )
    apply_variant_cookie(response, variant_id)
    return response


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
                "deadline_context": get_deadline_context(),
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
                "deadline_context": get_deadline_context(),
            }
        )

    if not cpa and session_data.get("cpa_slug"):
        cpa = session_data["cpa_slug"]

    cpa_profile = await get_cpa_profile_for_page(cpa)
    variant_id = resolve_variant_id(request, session_data=session_data)

    try:
        from universal_report import UniversalReportEngine

        # Convert CPA profile to theme format
        theme_profile = {
            "firm_name": cpa_profile.get("firm_name", "Tax Advisory"),
            "advisor_name": cpa_profile.get("display_name"),
            "credentials": cpa_profile.get("credentials", []),
            "primary_color": cpa_profile.get("primary_color", "#1e3a5f"),
            "secondary_color": cpa_profile.get("secondary_color", "#152b47"),
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
        response = templates.TemplateResponse(
            "lead_magnet/tier1_report.html",
            {
                "request": request,
                "cpa": cpa_profile,
                "session_id": session,
                "session_data": session_data,
                "report": None,
                "error": "Enhanced report temporarily unavailable.",
                "deadline_context": get_deadline_context(),
                "variant_id": variant_id,
            }
        )
        apply_variant_cookie(response, variant_id)
        return response
    except Exception as e:
        logger.error(f"Universal report generation failed: {e}")
        response = templates.TemplateResponse(
            "lead_magnet/tier1_report.html",
            {
                "request": request,
                "cpa": cpa_profile,
                "session_id": session,
                "session_data": session_data,
                "report": None,
                "error": f"Report generation failed: {str(e)}",
                "deadline_context": get_deadline_context(),
                "variant_id": variant_id,
            }
        )
        apply_variant_cookie(response, variant_id)
        return response
