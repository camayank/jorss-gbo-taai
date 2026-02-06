"""
CPA Dashboard Page Routes

Serves HTML templates for the CPA lead management dashboard.
This module handles the frontend pages for CPAs to manage their leads.

Authentication:
- All routes require authentication
- User must have CPA, ADMIN, or PREPARER role
- Unauthenticated users are redirected to login
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)

# Import auth utilities
try:
    from security.auth_decorators import get_user_from_request, Role
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    logger.warning("Auth decorators not available - CPA dashboard running without auth")

    class Role:
        CPA = "cpa"
        ADMIN = "admin"
        PREPARER = "preparer"

    def get_user_from_request(request):
        return None

# Create router
cpa_dashboard_router = APIRouter(
    prefix="/cpa",
    tags=["CPA Dashboard"]
)

# Templates directory
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


# =============================================================================
# AUTHENTICATION
# =============================================================================

# Allowed roles for CPA dashboard
CPA_ALLOWED_ROLES = ["cpa", "admin", "preparer", "partner", "staff"]

# Demo mode configuration - MUST be explicitly enabled AND in non-production environment
_DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing"})


def _is_demo_mode_allowed() -> bool:
    """
    Check if demo mode is allowed.

    Demo mode requires BOTH:
    1. ENABLE_DEMO_MODE=true environment variable
    2. APP_ENVIRONMENT is a development environment (not production)

    This fail-closed design prevents accidental demo mode exposure in production.
    """
    demo_enabled = os.environ.get("ENABLE_DEMO_MODE", "").lower() == "true"
    app_env = os.environ.get("APP_ENVIRONMENT", "").lower().strip()

    # Only allow demo mode in explicitly allowlisted development environments
    is_dev_env = app_env in _DEV_ENVIRONMENTS

    if demo_enabled and not is_dev_env:
        logger.warning(
            f"[SECURITY] Demo mode requested but blocked - "
            f"APP_ENVIRONMENT='{app_env}' is not a development environment"
        )
        return False

    return demo_enabled and is_dev_env


async def require_cpa_auth(request: Request) -> dict:
    """
    Dependency to require CPA authentication for dashboard pages.

    Returns:
        User dict if authenticated with correct role
        Raises HTTPException or redirects if not authenticated
    """
    # Get user from request
    user = get_user_from_request(request) if AUTH_AVAILABLE else None

    # Check for demo mode - ONLY if explicitly enabled AND in dev environment
    demo_requested = request.query_params.get("demo") == "true"
    cpa_cookie = request.cookies.get("cpa_id")

    if demo_requested and _is_demo_mode_allowed():
        # Allow demo access with mock user (only in dev environments)
        logger.info("[DEMO] Demo mode access granted for CPA dashboard")
        return {
            "id": cpa_cookie or "demo-cpa",
            "role": "cpa",
            "tenant_id": "default",
            "email": "demo@example.com",
            "name": "Demo CPA"
        }
    elif demo_requested:
        # Demo was requested but not allowed - log security event
        logger.warning(
            f"[SECURITY] Demo mode access denied - not enabled or not in dev environment | "
            f"ip={request.client.host if request.client else 'unknown'}"
        )

    if not user:
        # Not authenticated - redirect to login
        logger.warning(f"Unauthenticated access to CPA dashboard: {request.url.path}")

        # For API requests, return 401
        if request.headers.get("accept", "").startswith("application/json"):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "AuthenticationRequired",
                    "message": "Please log in to access the CPA dashboard",
                    "redirect": "/login?next=/cpa/dashboard"
                }
            )

        # For browser requests - only allow demo user if demo mode is explicitly enabled
        if _is_demo_mode_allowed():
            logger.info("[DEMO] Demo fallback user granted for unauthenticated browser request")
            return {
                "id": "demo-cpa",
                "role": "cpa",
                "tenant_id": "default",
                "email": "demo@example.com",
                "name": "Demo CPA (Login Required)"
            }

        # In production, redirect to login page
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AuthenticationRequired",
                "message": "Please log in to access the CPA dashboard",
                "redirect": "/login?next=/cpa/dashboard"
            }
        )

    # Check role
    user_role = user.get("role", "").lower()
    if user_role not in CPA_ALLOWED_ROLES:
        logger.warning(f"Unauthorized role {user_role} accessing CPA dashboard: {request.url.path}")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "InsufficientPermissions",
                "message": "You do not have permission to access the CPA dashboard",
                "required_roles": CPA_ALLOWED_ROLES
            }
        )

    return user


def get_cpa_id_from_user(user: dict) -> str:
    """Extract CPA ID from user object."""
    return user.get("cpa_id") or user.get("id") or "default"


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
        "primary_color": "#1e3a5f",
        "secondary_color": "#152b47",
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
            "conversion_trend": 0,  # Added missing field for template compatibility
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
async def cpa_dashboard(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """
    CPA Dashboard - Main overview page.

    Requires authentication with CPA role.

    Shows:
    - Summary cards with lead counts
    - Recent leads table
    - Priority queue
    - Quick actions
    - Recent activity
    """
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = get_cpa_id_from_user(current_user) or cpa_profile.get("cpa_id", "default")

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
    current_user: dict = Depends(require_cpa_auth),
):
    """
    CPA Leads List - Full lead management view.

    Requires authentication with CPA role.

    Supports filtering by:
    - state: Lead state (browsing, curious, evaluating, advisory_ready, high_leverage)
    - temperature: Lead temperature (hot, warm, cold)
    - search: Search query for name/email
    """
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = get_cpa_id_from_user(current_user) or cpa_profile.get("cpa_id", "default")

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
async def cpa_lead_detail(
    request: Request,
    lead_id: str,
    current_user: dict = Depends(require_cpa_auth)
):
    """
    CPA Lead Detail - Individual lead view.

    Requires authentication with CPA role.

    Shows:
    - Lead contact info
    - Tax profile summary
    - State history
    - Engagement timeline
    - Action buttons
    """
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = get_cpa_id_from_user(current_user) or cpa_profile.get("cpa_id", "default")

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
async def cpa_assignments(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Assignments - Leads assigned to this CPA. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = get_cpa_id_from_user(current_user) or cpa_profile.get("cpa_id", "default")

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
async def cpa_converted(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Converted - Leads that became clients. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = get_cpa_id_from_user(current_user) or cpa_profile.get("cpa_id", "default")

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
async def cpa_analytics(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Analytics - Performance metrics and charts. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = get_cpa_id_from_user(current_user) or cpa_profile.get("cpa_id", "default")

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
async def cpa_profile_page(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Profile - Edit personal profile. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = get_cpa_id_from_user(current_user) or cpa_profile.get("cpa_id", "default")
    stats = await get_dashboard_stats(cpa_id)

    return templates.TemplateResponse(
        "cpa/profile.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "current_user": current_user,
            "active_page": "profile",
        }
    )


@cpa_dashboard_router.get("/branding", response_class=HTMLResponse)
async def cpa_branding_page(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Branding - Edit lead magnet branding. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = get_cpa_id_from_user(current_user) or cpa_profile.get("cpa_id", "default")
    stats = await get_dashboard_stats(cpa_id)

    return templates.TemplateResponse(
        "cpa/branding.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "current_user": current_user,
            "active_page": "branding",
        }
    )


@cpa_dashboard_router.get("/settings", response_class=HTMLResponse)
async def cpa_settings_page(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Settings - Account and notification settings. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    stats = await get_dashboard_stats(get_cpa_id_from_user(current_user))

    return templates.TemplateResponse(
        "cpa/settings.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "current_user": current_user,
            "active_page": "settings",
        }
    )


@cpa_dashboard_router.get("/team", response_class=HTMLResponse)
async def cpa_team_page(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Team - Team member management. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    stats = await get_dashboard_stats(get_cpa_id_from_user(current_user))

    # Mock team members for now
    team_members = [
        {"id": "1", "name": "Demo User", "email": "demo@example.com", "role": "Admin", "status": "active"},
    ]

    return templates.TemplateResponse(
        "cpa/team.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "team_members": team_members,
            "current_user": current_user,
            "active_page": "team",
        }
    )


@cpa_dashboard_router.get("/clients", response_class=HTMLResponse)
async def cpa_clients_page(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Clients - Client management. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    stats = await get_dashboard_stats(get_cpa_id_from_user(current_user))

    # Get converted leads as clients
    clients = []
    try:
        from cpa_panel.services.lead_magnet_service import get_lead_magnet_service
        service = get_lead_magnet_service()
        cpa_id = get_cpa_id_from_user(current_user)
        leads_result = service.list_leads(cpa_id=cpa_id, state="converted", limit=50)
        for lead in leads_result.get("leads", []):
            clients.append({
                "id": lead.get("lead_id"),
                "name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or "Client",
                "email": lead.get("email", ""),
                "phone": lead.get("phone"),
                "status": "active",
                "created_at": lead.get("created_at"),
            })
    except Exception as e:
        logger.warning(f"Failed to load clients: {e}")

    return templates.TemplateResponse(
        "cpa/clients.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "clients": clients,
            "current_user": current_user,
            "active_page": "clients",
        }
    )


@cpa_dashboard_router.get("/billing", response_class=HTMLResponse)
async def cpa_billing_page(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Billing - Subscription and payment management. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    stats = await get_dashboard_stats(get_cpa_id_from_user(current_user))

    # Mock billing data
    billing = {
        "plan": "Professional",
        "status": "active",
        "next_billing": "February 1, 2026",
        "amount": 99.00,
        "leads_this_month": stats.get("total_leads", 0),
        "leads_limit": 100,
    }

    return templates.TemplateResponse(
        "cpa/billing.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "billing": billing,
            "current_user": current_user,
            "active_page": "billing",
        }
    )


@cpa_dashboard_router.get("/tasks", response_class=HTMLResponse)
async def cpa_tasks_page(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Tasks - Task management for CPA workflows. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    stats = await get_dashboard_stats(get_cpa_id_from_user(current_user))

    return templates.TemplateResponse(
        "cpa/tasks.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "current_user": current_user,
            "active_page": "tasks",
            "page_title": "Task Management",
        }
    )


@cpa_dashboard_router.get("/appointments", response_class=HTMLResponse)
async def cpa_appointments_page(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Appointments - Calendar and scheduling management. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    stats = await get_dashboard_stats(get_cpa_id_from_user(current_user))

    return templates.TemplateResponse(
        "cpa/appointments.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "current_user": current_user,
            "active_page": "appointments",
            "page_title": "Appointment Calendar",
        }
    )


@cpa_dashboard_router.get("/deadlines", response_class=HTMLResponse)
async def cpa_deadlines_page(
    request: Request,
    current_user: dict = Depends(require_cpa_auth)
):
    """CPA Deadlines - Tax deadline tracker and reminders. Requires authentication."""
    cpa_profile = await get_cpa_profile_from_context(request)
    stats = await get_dashboard_stats(get_cpa_id_from_user(current_user))

    return templates.TemplateResponse(
        "cpa/deadlines.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "stats": stats,
            "current_user": current_user,
            "active_page": "deadlines",
            "page_title": "Deadline Tracker",
        }
    )


# =============================================================================
# RETURN QUEUE AND REVIEW PAGES
# =============================================================================

@cpa_dashboard_router.get("/returns/queue", response_class=HTMLResponse)
async def cpa_return_queue_page(
    request: Request,
    status: str = "pending_review",
    current_user: dict = Depends(require_cpa_auth)
):
    """
    CPA Return Queue - View and manage tax returns awaiting review.

    Supports filtering by status:
    - pending_review: Returns submitted by clients awaiting initial review
    - in_review: Returns currently being reviewed
    - ready_for_approval: Returns ready for final CPA approval
    - approved: Completed approved returns
    """
    cpa_profile = await get_cpa_profile_from_context(request)
    cpa_id = get_cpa_id_from_user(current_user)

    # Get returns from queue API
    returns = []
    counts = {
        "pending_review": 0,
        "in_review": 0,
        "ready_for_approval": 0,
        "approved": 0,
        "total": 0
    }

    try:
        # Import session persistence to get returns
        from database.session_persistence import SessionPersistence
        persistence = SessionPersistence()

        # Get all returns for this CPA (mock implementation - adjust based on actual data model)
        # In production, this would query by CPA ID and filter by status
        all_sessions = []

        # For demo purposes, create mock returns if none exist
        if not all_sessions:
            returns = [
                {
                    "session_id": "demo-session-1",
                    "client_name": "John Smith",
                    "client_email": "john.smith@email.com",
                    "tax_year": 2025,
                    "filing_status": "Single",
                    "refund_or_owed": 2450.00,
                    "submitted_at": "2026-02-05",
                    "status": status
                },
                {
                    "session_id": "demo-session-2",
                    "client_name": "Sarah Johnson",
                    "client_email": "sarah.j@email.com",
                    "tax_year": 2025,
                    "filing_status": "Married Filing Jointly",
                    "refund_or_owed": -1200.00,
                    "submitted_at": "2026-02-04",
                    "status": status
                }
            ]
            counts = {
                "pending_review": 3,
                "in_review": 1,
                "ready_for_approval": 2,
                "approved": 5,
                "total": 11
            }

    except Exception as e:
        logger.error(f"Error loading return queue: {e}")
        returns = []

    return templates.TemplateResponse(
        "cpa/return_queue.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "current_user": current_user,
            "active_page": "returns",
            "page_title": "Return Queue",
            "status": status,
            "returns": returns,
            "counts": counts
        }
    )


@cpa_dashboard_router.get("/returns/{session_id}/review", response_class=HTMLResponse)
async def cpa_return_review_page(
    request: Request,
    session_id: str,
    current_user: dict = Depends(require_cpa_auth)
):
    """
    CPA Return Review Page - Detailed view of a tax return for review and approval.

    Features:
    - Income summary and breakdown
    - Deductions and credits overview
    - Add review notes
    - Approve or request changes
    - Download PDF/JSON exports
    """
    cpa_profile = await get_cpa_profile_from_context(request)

    # Load return data
    return_data = {}
    client_name = "Unknown Client"
    tax_year = 2025
    notes = []

    try:
        from database.session_persistence import SessionPersistence
        persistence = SessionPersistence()

        session = persistence.load_unified_session(session_id)
        if session:
            # Extract tax return data
            tax_return = None
            if hasattr(session, 'tax_return'):
                tax_return = session.tax_return
            elif isinstance(session, dict) and 'tax_return' in session:
                tax_return = session['tax_return']

            if tax_return:
                # Build return_data from TaxReturn
                if hasattr(tax_return, 'model_dump'):
                    return_data = tax_return.model_dump()
                elif isinstance(tax_return, dict):
                    return_data = tax_return
                else:
                    return_data = {}

                # Extract key fields
                if hasattr(tax_return, 'taxpayer') and tax_return.taxpayer:
                    tp = tax_return.taxpayer
                    client_name = f"{getattr(tp, 'first_name', '')} {getattr(tp, 'last_name', '')}".strip() or "Unknown Client"
                    return_data['filing_status'] = getattr(tp, 'filing_status', 'single')
                    if hasattr(return_data['filing_status'], 'value'):
                        return_data['filing_status'] = return_data['filing_status'].value

                if hasattr(tax_return, 'income') and tax_return.income:
                    inc = tax_return.income
                    return_data['w2_wages'] = getattr(inc, 'get_total_wages', lambda: 0)() if callable(getattr(inc, 'get_total_wages', None)) else 0
                    return_data['interest_income'] = getattr(inc, 'interest_income', 0)
                    return_data['dividend_income'] = getattr(inc, 'dividend_income', 0)
                    return_data['self_employment_income'] = getattr(inc, 'self_employment_income', 0)
                    return_data['total_income'] = getattr(inc, 'get_total_income', lambda: 0)() if callable(getattr(inc, 'get_total_income', None)) else 0

                return_data['agi'] = getattr(tax_return, 'adjusted_gross_income', 0) or 0
                return_data['taxable_income'] = getattr(tax_return, 'taxable_income', 0) or 0
                return_data['total_tax'] = getattr(tax_return, 'tax_liability', 0) or 0
                return_data['refund_or_owed'] = getattr(tax_return, 'refund_or_owed', 0) or 0
                return_data['total_payments'] = getattr(tax_return, 'total_payments', 0) or 0

                tax_year = getattr(tax_return, 'tax_year', 2025)

            # Get return status
            return_data['status'] = getattr(session, 'status', 'pending_review') if hasattr(session, 'status') else session.get('status', 'pending_review')

            # Get notes if available
            if hasattr(session, 'notes'):
                notes = session.notes or []
            elif isinstance(session, dict) and 'notes' in session:
                notes = session.get('notes', [])

    except Exception as e:
        logger.error(f"Error loading return for review: {e}")
        # Use demo data
        return_data = {
            "status": "pending_review",
            "filing_status": "Single",
            "w2_wages": 75000,
            "interest_income": 500,
            "dividend_income": 1200,
            "self_employment_income": 0,
            "other_income": 0,
            "total_income": 76700,
            "agi": 76700,
            "taxable_income": 62100,
            "use_standard_deduction": True,
            "total_deduction": 14600,
            "federal_withholding": 12000,
            "estimated_payments": 0,
            "child_tax_credit": 0,
            "eitc": 0,
            "total_payments": 12000,
            "total_tax": 9245,
            "refund_or_owed": 2755
        }
        client_name = "Demo Client"

    return templates.TemplateResponse(
        "cpa/return_review.html",
        {
            "request": request,
            "cpa": cpa_profile,
            "current_user": current_user,
            "active_page": "returns",
            "page_title": f"Review Return - {client_name}",
            "session_id": session_id,
            "return_data": return_data,
            "client_name": client_name,
            "tax_year": tax_year,
            "notes": notes
        }
    )
