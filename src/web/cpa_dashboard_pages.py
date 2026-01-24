"""
CPA Dashboard Page Routes

Serves HTML templates for the CPA lead management dashboard.
This module handles the frontend pages for CPAs to manage their leads.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)

# Create router
cpa_dashboard_router = APIRouter(
    prefix="/cpa",
    tags=["CPA Dashboard"]
)

# Templates directory
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_default_cpa_profile() -> dict:
    """Get default CPA profile for when no auth context is available."""
    return {
        "cpa_id": "default",
        "cpa_slug": "default",
        "first_name": "CPA",
        "last_name": "User",
        "display_name": "CPA User",
        "firm_name": "Tax Practice",
        "credentials": ["CPA"],
        "logo_url": None,
        "primary_color": "#2563eb",
        "secondary_color": "#1d4ed8",
        "accent_color": "#10b981",
        "profile_photo_url": None,
        "email": None,
    }


async def get_cpa_profile_from_context(request: Request) -> dict:
    """
    Get CPA profile from authentication context.

    In production, this would use the auth context to get the logged-in CPA's profile.
    For now, returns default profile or demo data.
    """
    # TODO: Integrate with actual auth when available
    # auth_context = request.state.auth if hasattr(request.state, 'auth') else None

    # Check for demo mode or test user
    cpa_id = request.cookies.get("cpa_id") or request.query_params.get("demo")

    if cpa_id:
        try:
            from cpa_panel.services.lead_magnet_service import get_lead_magnet_service
            service = get_lead_magnet_service()
            profile = service.get_cpa_profile(cpa_id)
            if profile:
                return profile
        except Exception as e:
            logger.warning(f"Failed to load CPA profile: {e}")

    return get_default_cpa_profile()


async def get_dashboard_stats(cpa_id: str) -> dict:
    """
    Get dashboard statistics for a CPA.

    Returns counts for each lead state and summary metrics.
    """
    try:
        from cpa_panel.services.pipeline_service import get_pipeline_service
        service = get_pipeline_service()

        # Get pipeline by state
        pipeline = service.get_pipeline_by_state(cpa_id)

        # Calculate stats
        stats = {
            "new_leads": 0,
            "advisory_ready": 0,
            "high_leverage": 0,
            "evaluating": 0,
            "converted": 0,
            "total_leads": 0,
            "total_revenue": 0,
            "new_leads_trend": 0,
            "conversion_rate": 0,
            "conversion_trend": 0,
        }

        if pipeline and "stages" in pipeline:
            for stage in pipeline["stages"]:
                state = stage.get("state", "").lower()
                count = stage.get("count", 0)
                value = stage.get("total_value", 0)

                stats["total_leads"] += count
                stats["total_revenue"] += value

                if state in ("browsing", "curious"):
                    stats["new_leads"] += count
                elif state == "evaluating":
                    stats["evaluating"] = count
                elif state == "advisory_ready":
                    stats["advisory_ready"] = count
                elif state == "high_leverage":
                    stats["high_leverage"] = count
                elif state == "converted":
                    stats["converted"] = count

        # Calculate conversion rate
        if stats["total_leads"] > 0:
            stats["conversion_rate"] = round((stats["converted"] / stats["total_leads"]) * 100, 1)

        return stats

    except Exception as e:
        logger.warning(f"Failed to get dashboard stats: {e}")
        return {
            "new_leads": 0,
            "advisory_ready": 0,
            "high_leverage": 0,
            "evaluating": 0,
            "converted": 0,
            "total_leads": 0,
            "total_revenue": 0,
            "new_leads_trend": 0,
            "conversion_rate": 0,
        }


async def get_recent_leads(cpa_id: str, limit: int = 10) -> List[dict]:
    """
    Get recent leads for dashboard display.
    """
    try:
        from cpa_panel.services.lead_magnet_service import get_lead_magnet_service
        service = get_lead_magnet_service()

        leads = service.list_leads(cpa_id=cpa_id, limit=limit, offset=0)

        result = []
        for lead in leads.get("leads", []):
            result.append({
                "id": lead.get("lead_id"),
                "name": lead.get("first_name", ""),
                "email": lead.get("email", ""),
                "state": lead.get("state", "browsing"),
                "state_display": lead.get("state_display", "Browsing"),
                "temperature": lead.get("temperature", "cold"),
                "estimated_savings": lead.get("estimated_savings", 0),
                "complexity": lead.get("complexity", "simple"),
                "age": _format_age(lead.get("created_at")),
                "time_in_state": _format_age(lead.get("state_changed_at")),
            })

        return result

    except Exception as e:
        logger.warning(f"Failed to get recent leads: {e}")
        return []


async def get_priority_leads(cpa_id: str, limit: int = 5) -> List[dict]:
    """
    Get priority leads for the priority queue.
    """
    try:
        from cpa_panel.services.pipeline_service import get_pipeline_service
        service = get_pipeline_service()

        queue = service.get_priority_queue(cpa_id, limit=limit)

        result = []
        for lead in queue.get("leads", []):
            result.append({
                "id": lead.get("lead_id"),
                "name": lead.get("first_name", ""),
                "email": lead.get("email", ""),
                "state": lead.get("state", "browsing"),
                "state_display": lead.get("state_display", "Browsing"),
                "estimated_savings": lead.get("estimated_savings", 0),
                "complexity": lead.get("complexity", "simple"),
                "time_in_state": _format_age(lead.get("state_changed_at")),
                "priority_score": lead.get("priority_score", 0),
            })

        return result

    except Exception as e:
        logger.warning(f"Failed to get priority leads: {e}")
        return []


async def get_recent_activity(cpa_id: str, limit: int = 5) -> List[dict]:
    """
    Get recent activity feed for dashboard.
    """
    # TODO: Implement activity tracking
    # For now, return empty list
    return []


def _format_age(timestamp) -> str:
    """Format a timestamp as human-readable age."""
    if not timestamp:
        return "Just now"

    try:
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            dt = timestamp

        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt

        if diff.days > 30:
            return f"{diff.days // 30}mo ago"
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "Just now"
    except Exception:
        return "Recently"


# =============================================================================
# DASHBOARD ROUTES
# =============================================================================

@cpa_dashboard_router.get("/", response_class=HTMLResponse)
@cpa_dashboard_router.get("", response_class=HTMLResponse)
async def cpa_dashboard_redirect(request: Request):
    """Redirect root /cpa to /cpa/dashboard."""
    return RedirectResponse(url="/cpa/dashboard", status_code=302)


@cpa_dashboard_router.get("/dashboard", response_class=HTMLResponse)
async def cpa_dashboard(request: Request):
    """
    CPA Dashboard - Main overview page.

    Shows:
    - Summary cards with lead counts
    - Recent leads table
    - Priority queue
    - Quick actions
    - Recent activity
    """
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = cpa_profile.get("cpa_id", "default")

    # Get dashboard data
    stats = await get_dashboard_stats(cpa_id)
    leads = await get_recent_leads(cpa_id, limit=10)
    priority_leads = await get_priority_leads(cpa_id, limit=5)
    activities = await get_recent_activity(cpa_id, limit=5)

    return templates.TemplateResponse(
        "cpa/dashboard.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "leads": leads,
            "priority_leads": priority_leads,
            "activities": activities,
            "active_page": "dashboard",
        }
    )


@cpa_dashboard_router.get("/leads", response_class=HTMLResponse)
async def cpa_leads_list(
    request: Request,
    state: Optional[str] = None,
    temperature: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
):
    """
    CPA Leads List - Full lead management view.

    Supports filtering by:
    - state: Lead state (browsing, curious, evaluating, advisory_ready, high_leverage)
    - temperature: Lead temperature (hot, warm, cold)
    - search: Search query for name/email
    """
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = cpa_profile.get("cpa_id", "default")

    stats = await get_dashboard_stats(cpa_id)

    # Get filtered leads
    limit = 25
    offset = (page - 1) * limit

    try:
        from cpa_panel.services.lead_magnet_service import get_lead_magnet_service
        service = get_lead_magnet_service()

        leads_result = service.list_leads(
            cpa_id=cpa_id,
            state=state,
            temperature=temperature,
            search=search,
            limit=limit,
            offset=offset,
        )

        leads = []
        for lead in leads_result.get("leads", []):
            leads.append({
                "id": lead.get("lead_id"),
                "name": lead.get("first_name", ""),
                "email": lead.get("email", ""),
                "phone": lead.get("phone"),
                "state": lead.get("state", "browsing"),
                "state_display": lead.get("state_display", "Browsing"),
                "temperature": lead.get("temperature", "cold"),
                "estimated_savings": lead.get("estimated_savings", 0),
                "complexity": lead.get("complexity", "simple"),
                "age": _format_age(lead.get("created_at")),
                "created_at": lead.get("created_at"),
            })

        total_count = leads_result.get("total_count", 0)
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    except Exception as e:
        logger.warning(f"Failed to get leads list: {e}")
        leads = []
        total_count = 0
        total_pages = 1

    # Determine active page based on filter
    active_page = "leads"
    if state:
        active_page = state.lower().replace(" ", "_")

    return templates.TemplateResponse(
        "cpa/leads_list.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "leads": leads,
            "total_count": total_count,
            "page": page,
            "total_pages": total_pages,
            "filter_state": state,
            "filter_temperature": temperature,
            "search_query": search,
            "active_page": active_page,
        }
    )


@cpa_dashboard_router.get("/leads/{lead_id}", response_class=HTMLResponse)
async def cpa_lead_detail(request: Request, lead_id: str):
    """
    CPA Lead Detail - Individual lead view.

    Shows:
    - Lead contact info
    - Tax profile summary
    - State history
    - Engagement timeline
    - Action buttons
    """
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = cpa_profile.get("cpa_id", "default")

    stats = await get_dashboard_stats(cpa_id)

    try:
        from cpa_panel.services.lead_magnet_service import get_lead_magnet_service
        service = get_lead_magnet_service()

        lead = service.get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Get lead's tax profile and insights
        session_id = lead.get("session_id")
        tax_profile = None
        insights = []

        if session_id:
            session = service.get_session(session_id)
            if session:
                tax_profile = session.get("tax_profile")

            # Get Tier 1 report for insights
            try:
                report = service.get_tier_one_report(session_id)
                if report:
                    insights = report.get("insights", [])[:5]
            except Exception:
                pass

        lead_data = {
            "id": lead.get("lead_id"),
            "name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or lead.get("email", "").split("@")[0],
            "first_name": lead.get("first_name", ""),
            "last_name": lead.get("last_name", ""),
            "email": lead.get("email", ""),
            "phone": lead.get("phone"),
            "state": lead.get("state", "browsing"),
            "state_display": lead.get("state_display", "Browsing"),
            "temperature": lead.get("temperature", "cold"),
            "estimated_savings": lead.get("estimated_savings", 0),
            "complexity": lead.get("complexity", "simple"),
            "score": lead.get("score", 0),
            "created_at": lead.get("created_at"),
            "age": _format_age(lead.get("created_at")),
            "session_id": session_id,
            "engaged": lead.get("engaged", False),
            "engagement_letter_acknowledged": lead.get("engagement_letter_acknowledged", False),
            "tax_profile": tax_profile,
            "insights": insights,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get lead detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to load lead")

    return templates.TemplateResponse(
        "cpa/lead_detail.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "lead": lead_data,
            "active_page": "leads",
        }
    )


@cpa_dashboard_router.get("/assignments", response_class=HTMLResponse)
async def cpa_assignments(request: Request):
    """CPA Assignments - Leads assigned to this CPA."""
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = cpa_profile.get("cpa_id", "default")

    stats = await get_dashboard_stats(cpa_id)

    # For now, redirect to leads with assigned filter
    return templates.TemplateResponse(
        "cpa/leads_list.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "leads": [],
            "total_count": 0,
            "page": 1,
            "total_pages": 1,
            "filter_state": "assigned",
            "active_page": "assignments",
        }
    )


@cpa_dashboard_router.get("/converted", response_class=HTMLResponse)
async def cpa_converted(request: Request):
    """CPA Converted - Leads that became clients."""
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = cpa_profile.get("cpa_id", "default")

    stats = await get_dashboard_stats(cpa_id)

    # Get converted leads
    leads = []  # TODO: Filter by converted status

    return templates.TemplateResponse(
        "cpa/leads_list.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "leads": leads,
            "total_count": 0,
            "page": 1,
            "total_pages": 1,
            "filter_state": "converted",
            "active_page": "converted",
        }
    )


@cpa_dashboard_router.get("/analytics", response_class=HTMLResponse)
async def cpa_analytics(request: Request):
    """CPA Analytics - Performance metrics and charts."""
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = cpa_profile.get("cpa_id", "default")

    stats = await get_dashboard_stats(cpa_id)

    # Get analytics data
    try:
        from cpa_panel.services.pipeline_service import get_pipeline_service
        service = get_pipeline_service()

        conversion_metrics = service.get_conversion_metrics(cpa_id)
        velocity_metrics = service.get_velocity_metrics(cpa_id)

    except Exception as e:
        logger.warning(f"Failed to get analytics: {e}")
        conversion_metrics = {}
        velocity_metrics = {}

    return templates.TemplateResponse(
        "cpa/analytics.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "conversion_metrics": conversion_metrics,
            "velocity_metrics": velocity_metrics,
            "active_page": "analytics",
        }
    )


@cpa_dashboard_router.get("/profile", response_class=HTMLResponse)
async def cpa_profile_page(request: Request):
    """CPA Profile - Edit personal profile."""
    cpa_profile = await get_cpa_profile_from_context(request)

    return templates.TemplateResponse(
        "cpa/profile.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "active_page": "profile",
        }
    )


@cpa_dashboard_router.get("/branding", response_class=HTMLResponse)
async def cpa_branding_page(request: Request):
    """CPA Branding - Edit lead magnet branding."""
    cpa_profile = await get_cpa_profile_from_context(request)

    return templates.TemplateResponse(
        "cpa/branding.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "active_page": "branding",
        }
    )
