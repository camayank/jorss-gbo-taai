"""
HTML page renderer routes extracted from app.py.

Contains all GET routes that return TemplateResponse or RedirectResponse
for browser-facing pages (not API endpoints).
"""

import os
import logging
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.constants import (
    ADMIN_UI_ROLES as _ADMIN_UI_ROLES,
    CPA_UI_ROLES as _CPA_UI_ROLES,
    CLIENT_UI_ROLES as _CLIENT_UI_ROLES,
)
from security.auth_decorators import get_user_from_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Pages"])

# Templates setup (same as app.py)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))

# Import CSRF token function to add to template globals
try:
    from web.app import generate_csrf_token
    templates.env.globals["csrf_token"] = generate_csrf_token
except ImportError:
    pass


# =========================================================================
# AUTH/ROLE HELPER FUNCTIONS
# =========================================================================

def _normalize_auth_value(value: Any) -> str:
    """Normalize role/user type values for routing."""
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    return str(value).strip().lower()


def _resolve_request_role_bucket(request: Request) -> str:
    """Resolve authenticated principal into a UI role bucket."""
    user = get_user_from_request(request)
    if user:
        role = _normalize_auth_value(user.get("role"))
        user_type = _normalize_auth_value(user.get("user_type"))
        if role in _ADMIN_UI_ROLES or user_type == "platform_admin":
            return "admin"
        if role in _CPA_UI_ROLES or user_type in {"cpa_team", "firm_user"}:
            return "cpa"
        if role in _CLIENT_UI_ROLES or user_type in {"client", "cpa_client", "consumer"}:
            return "client"
    return "anonymous"


def _ui_user_context(request: Request, default_role: str = "user") -> dict:
    """Build lightweight template context for user identity."""
    return {
        "role": request.cookies.get("user_role", default_role),
        "name": request.cookies.get("user_name", "User"),
        "email": request.cookies.get("user_email", ""),
    }


def _safe_next_path(path: str) -> str:
    """Sanitize a redirect path for the ?next= parameter to prevent open redirects."""
    if not path or not path.startswith("/") or path.startswith("//") or ":" in path.split("?")[0]:
        return "/"
    return path.split("?")[0].split("#")[0]


def _require_any_auth(request: Request) -> Optional[RedirectResponse]:
    """Restrict page to any authenticated user."""
    role_bucket = _resolve_request_role_bucket(request)
    if role_bucket != "anonymous":
        return None
    return RedirectResponse(url=f"/login?next={_safe_next_path(request.url.path)}", status_code=302)


def _require_admin_page_access(request: Request) -> Optional[RedirectResponse]:
    """Restrict /admin web pages to authenticated admin principals."""
    role_bucket = _resolve_request_role_bucket(request)
    if role_bucket == "admin":
        return None
    if role_bucket == "cpa":
        return RedirectResponse(url="/cpa/dashboard", status_code=302)
    if role_bucket == "client":
        return RedirectResponse(url="/app/portal", status_code=302)
    return RedirectResponse(url="/login?next=/admin", status_code=302)


def _require_cpa_or_admin_access(request: Request) -> Optional[RedirectResponse]:
    """Restrict page to CPA or admin roles."""
    role_bucket = _resolve_request_role_bucket(request)
    if role_bucket in ("cpa", "admin"):
        return None
    if role_bucket == "client":
        return RedirectResponse(url="/app/portal", status_code=302)
    return RedirectResponse(url=f"/login?next={_safe_next_path(request.url.path)}", status_code=302)


# =========================================================================
# MAIN ENTRY POINT
# =========================================================================

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Main entry point - redirects to landing page for new visitors."""
    return RedirectResponse(url="/landing", status_code=302)


@router.get("/file", response_class=HTMLResponse)
@router.get("/intelligent-advisor", response_class=HTMLResponse)
def intelligent_tax_advisor(request: Request):
    """Intelligent Conversational Tax Advisory Platform — publicly accessible."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    user_ctx = _ui_user_context(request, default_role="client")
    return templates.TemplateResponse("intelligent_advisor.html", {
        "request": request,
        "branding": branding,
        "user": user_ctx,
        "current_path": str(request.url.path),
        "brand_name": getattr(branding, "platform_name", "Tax Advisory"),
        "tenant_features": {},
    })


@router.get("/landing", response_class=HTMLResponse)
def landing_page(request: Request):
    """Smart Landing Page - Unified entry point for tax filing."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("landing.html", {"request": request, "branding": branding})


@router.get("/quick-estimate", response_class=HTMLResponse)
@router.get("/estimate", response_class=HTMLResponse)
def quick_estimate_page(request: Request):
    """Redirect quick-estimate entry point to intelligent advisor."""
    return RedirectResponse(url="/intelligent-advisor?entry=quick-estimate", status_code=302)


@router.get("/profile", response_class=HTMLResponse)
@router.get("/settings/profile", response_class=HTMLResponse)
def user_profile_page(request: Request):
    """User Profile Page - View and edit profile settings."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    user_context = _ui_user_context(request)
    return templates.TemplateResponse(
        "settings/profile.html",
        {"request": request, "user": user_context}
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """CPA Workspace Dashboard - Multi-client management."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    from config.branding import get_branding_config
    branding = get_branding_config()
    response = templates.TemplateResponse("dashboard.html", {"request": request, "branding": branding})
    return response


# =========================================================================
# ROLE-BASED APPLICATION ROUTER
# =========================================================================

@router.get("/app", response_class=HTMLResponse)
async def app_router(request: Request):
    """Role-based application router."""
    role_bucket = _resolve_request_role_bucket(request)
    if role_bucket == "admin":
        return RedirectResponse(url="/admin", status_code=302)
    elif role_bucket == "cpa":
        return RedirectResponse(url="/cpa/dashboard", status_code=302)
    elif role_bucket == "client":
        return RedirectResponse(url="/app/portal", status_code=302)
    if role_bucket == "anonymous":
        return RedirectResponse(url="/login?next=/intelligent-advisor", status_code=302)
    return RedirectResponse(url="/intelligent-advisor", status_code=302)


@router.get("/app/workspace", response_class=HTMLResponse)
async def workspace_dashboard(request: Request):
    """CPA Workspace Dashboard."""
    role_bucket = _resolve_request_role_bucket(request)
    if role_bucket == "admin":
        return RedirectResponse(url="/admin", status_code=302)
    if role_bucket == "client":
        return RedirectResponse(url="/app/portal", status_code=302)
    if role_bucket != "cpa":
        return RedirectResponse(url="/login?next=/cpa/dashboard", status_code=302)
    return RedirectResponse(url="/cpa/dashboard", status_code=302)


@router.get("/app/portal", response_class=HTMLResponse)
async def client_portal_entrypoint(request: Request):
    """Client Portal Dashboard."""
    role_bucket = _resolve_request_role_bucket(request)
    portal_token = request.query_params.get("token") or request.cookies.get("client_token")
    if role_bucket == "admin":
        return RedirectResponse(url="/admin", status_code=302)
    if role_bucket == "cpa":
        return RedirectResponse(url="/cpa/dashboard", status_code=302)
    if role_bucket != "client" and not portal_token:
        return RedirectResponse(url="/client/login?next=/app/portal", status_code=302)
    user = _ui_user_context(request, default_role="client")
    return templates.TemplateResponse(
        "client_portal.html",
        {"request": request, "user": user, "current_path": "/app/portal"}
    )


@router.get("/app/settings", response_class=HTMLResponse)
async def app_settings(request: Request):
    """User settings page accessible from any role."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    user = _ui_user_context(request, default_role="user")
    role_bucket = _resolve_request_role_bucket(request)
    if role_bucket == "cpa":
        return RedirectResponse(url="/cpa/settings", status_code=302)
    elif role_bucket == "admin":
        return RedirectResponse(url="/admin/settings", status_code=302)
    else:
        return templates.TemplateResponse(
            "client_portal.html",
            {"request": request, "user": user, "current_path": "/app/settings", "show_settings": True}
        )


# =========================================================================
# LEGACY CPA ROUTES
# =========================================================================

@router.get("/legacy/cpa", include_in_schema=False)
@router.get("/legacy/cpa/v2", include_in_schema=False)
def legacy_cpa_dashboard_redirect():
    """Legacy CPA routes — permanent redirect to CPA dashboard."""
    return RedirectResponse(url="/cpa/dashboard", status_code=301)


@router.get("/cpa/settings/payments", response_class=HTMLResponse)
def cpa_payment_settings(request: Request):
    """CPA Payment Settings - Stripe Connect and payment configuration."""
    denied = _require_cpa_or_admin_access(request)
    if denied:
        return denied
    return templates.TemplateResponse("cpa_payment_settings.html", {"request": request})


@router.get("/cpa/settings/branding", response_class=HTMLResponse)
def cpa_branding_settings(request: Request):
    """CPA Branding Settings - White-label customization."""
    denied = _require_cpa_or_admin_access(request)
    if denied:
        return denied
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("cpa_branding_settings.html", {"request": request, "branding": branding})


@router.get("/legacy/cpa/clients", include_in_schema=False)
def legacy_cpa_clients_redirect():
    """Legacy CPA clients — permanent redirect."""
    return RedirectResponse(url="/cpa/clients", status_code=301)


@router.get("/legacy/cpa/settings", include_in_schema=False)
def legacy_cpa_settings_redirect():
    """Legacy CPA settings — permanent redirect."""
    return RedirectResponse(url="/cpa/settings", status_code=301)


@router.get("/legacy/cpa/team", include_in_schema=False)
def legacy_cpa_team_redirect():
    """Legacy CPA team — permanent redirect."""
    return RedirectResponse(url="/cpa/team", status_code=301)


@router.get("/legacy/cpa/billing", include_in_schema=False)
def legacy_cpa_billing_redirect():
    """Legacy CPA billing — permanent redirect."""
    return RedirectResponse(url="/cpa/billing", status_code=301)


# =========================================================================
# LEGAL PAGES & CPA LANDING
# =========================================================================

@router.get("/cpa-landing", response_class=HTMLResponse)
@router.get("/for-cpas", response_class=HTMLResponse)
def cpa_landing_page(request: Request):
    """CPA Landing Page - Marketing page for CPA lead generation platform."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("landing.html", {"request": request, "branding": branding})


@router.get("/terms", response_class=HTMLResponse)
@router.get("/terms-of-service", response_class=HTMLResponse)
def terms_of_service(request: Request):
    """Terms of Service - Legal terms and conditions."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("terms.html", {"request": request, "branding": branding})


@router.get("/privacy", response_class=HTMLResponse)
@router.get("/privacy-policy", response_class=HTMLResponse)
def privacy_policy(request: Request):
    """Privacy Policy - Data collection and usage policies."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("privacy.html", {"request": request, "branding": branding})


@router.get("/cookies", response_class=HTMLResponse)
@router.get("/cookie-policy", response_class=HTMLResponse)
def cookie_policy(request: Request):
    """Cookie Policy - Cookie usage disclosure."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("cookies.html", {"request": request, "branding": branding})


@router.get("/disclaimer", response_class=HTMLResponse)
def disclaimer_page(request: Request):
    """Disclaimer - Important legal disclaimer."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("disclaimer.html", {"request": request, "branding": branding})


@router.get("/client", response_class=HTMLResponse)
def client_portal_redirect(request: Request):
    """Client Access - Redirect to unified filing interface."""
    logger.info("Client accessing platform - redirecting to /file")
    return RedirectResponse(url="/file", status_code=302)


@router.get("/client/login", response_class=HTMLResponse)
def client_login_page(request: Request, next: str = "/app/portal"):
    """Client portal login entrypoint."""
    return templates.TemplateResponse(
        "auth/client_login.html",
        {"request": request, "next_url": next or "/app/portal"},
    )


# =========================================================================
# REDIRECT ROUTES
# =========================================================================

@router.post("/logout")
def logout_redirect(request: Request):
    """Logout and redirect to home page."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("tax_session_id")
    response.delete_cookie("auth_token")
    response.delete_cookie("client_token")
    response.delete_cookie("user_role")
    response.delete_cookie("user_name")
    response.delete_cookie("user_email")
    response.delete_cookie("cpa_id")
    return response


@router.get("/logout", include_in_schema=False)
def logout_get_fallback(request: Request):
    """GET fallback — clear cookies and redirect (for bookmarks/links)."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("tax_session_id")
    response.delete_cookie("auth_token")
    response.delete_cookie("client_token")
    response.delete_cookie("user_role")
    response.delete_cookie("user_name")
    response.delete_cookie("user_email")
    response.delete_cookie("cpa_id")
    return response


@router.get("/scenarios", response_class=HTMLResponse)
def scenarios_page(request: Request, session_id: str = None):
    """Scenario comparison - compare tax scenarios side by side."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    return templates.TemplateResponse(
        "scenarios.html",
        {"request": request, "session_id": session_id, "page_title": "Scenario Comparison"}
    )


@router.get("/projections", response_class=HTMLResponse)
def projections_redirect(request: Request, session_id: str = None):
    """Redirect to intelligent advisor for tax projections."""
    if session_id:
        return RedirectResponse(url=f"/intelligent-advisor?session_id={session_id}", status_code=302)
    return RedirectResponse(url="/intelligent-advisor", status_code=302)


@router.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request):
    return RedirectResponse(url="/intelligent-advisor", status_code=302)


@router.get("/settings", response_class=HTMLResponse)
def settings_redirect(request: Request):
    """Redirect to appropriate settings page based on role."""
    role_bucket = _resolve_request_role_bucket(request)
    if role_bucket == "admin":
        return RedirectResponse(url="/admin/settings", status_code=302)
    if role_bucket == "cpa":
        return RedirectResponse(url="/cpa/settings", status_code=302)
    return RedirectResponse(url="/app/settings", status_code=302)


@router.get("/documents", response_class=HTMLResponse)
def documents_redirect(request: Request):
    return RedirectResponse(url="/file", status_code=302)


@router.get("/returns", response_class=HTMLResponse)
def returns_redirect(request: Request):
    return RedirectResponse(url="/file", status_code=302)


@router.get("/clients", response_class=HTMLResponse)
def clients_redirect(request: Request):
    return RedirectResponse(url="/cpa/clients", status_code=302)


@router.get("/advisory-report-preview", response_class=HTMLResponse)
async def advisory_report_preview(request: Request):
    """Serve advisory report preview page."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    return templates.TemplateResponse("advisory_report_preview.html", {"request": request})


# =========================================================================
# UNIFIED APP ROUTER - Single Entry Point
# =========================================================================

@router.get("/workspace", response_class=HTMLResponse, operation_id="unified_workspace_dashboard")
def unified_workspace_dashboard_alias(request: Request):
    return RedirectResponse(url="/app/workspace", status_code=302)


@router.get("/portal", response_class=HTMLResponse, operation_id="unified_client_portal")
def unified_client_portal_alias(request: Request):
    return RedirectResponse(url="/app/portal", status_code=302)


@router.get("/admin", response_class=HTMLResponse)
@router.get("/admin/{path:path}", response_class=HTMLResponse)
def admin_dashboard(request: Request, path: str = ""):
    """Admin Dashboard - Firm Administration Portal."""
    denied = _require_admin_page_access(request)
    if denied:
        return denied
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "branding": branding})


@router.get("/hub", response_class=HTMLResponse)
@router.get("/system-hub", response_class=HTMLResponse)
def system_hub(request: Request):
    """System Hub - Central Navigation Portal."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    return templates.TemplateResponse("system_hub.html", {"request": request})


@router.get("/workflow", response_class=HTMLResponse)
@router.get("/workflow-hub", response_class=HTMLResponse)
def workflow_hub(request: Request):
    """Platform Workflow Hub - User Journey Visualization."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    return templates.TemplateResponse("workflow_hub.html", {"request": request})


@router.get("/test-dashboard", response_class=HTMLResponse, include_in_schema=False)
@router.get("/qa", response_class=HTMLResponse, include_in_schema=False)
def test_dashboard(request: Request):
    """QA Test Dashboard — disabled (templates removed)."""
    return RedirectResponse(url="/intelligent-advisor", status_code=302)


@router.get("/smart-tax", response_class=HTMLResponse)
@router.get("/smart-tax/{path:path}", response_class=HTMLResponse)
def smart_tax_redirect(request: Request, path: str = ""):
    """DEPRECATED: Smart Tax merged into Intelligent Advisor."""
    return RedirectResponse(url="/intelligent-advisor", status_code=302)


@router.get("/smart-tax-legacy", include_in_schema=False)
def smart_tax_legacy_redirect():
    """Legacy smart-tax — permanent redirect to intelligent advisor."""
    return RedirectResponse(url="/intelligent-advisor", status_code=301)


@router.get("/guided", response_class=HTMLResponse)
@router.get("/guided/{session_id}", response_class=HTMLResponse)
def guided_filing_page(request: Request, session_id: str = None):
    """Redirect guided filing entry points to intelligent advisor."""
    return RedirectResponse(url="/intelligent-advisor", status_code=302)


@router.get("/results", response_class=HTMLResponse)
def filing_results(request: Request, session_id: str = None):
    """Show completed tax return results with subscription tier filtering."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    from config.branding import get_branding_config
    from database.session_persistence import get_session_persistence
    from subscription.tier_control import ReportAccessControl, SubscriptionTier, get_user_tier

    if not session_id:
        session_id = request.query_params.get('session_id')
    if not session_id:
        session_id = request.cookies.get('tax_session_id')
    if not session_id:
        return RedirectResponse(url="/lead-magnet/", status_code=302)

    persistence = get_session_persistence()
    session_data = persistence.load_session(session_id)
    if not session_data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Return not found or expired.")

    return_data = persistence.load_session_tax_return(session_id)
    if not return_data:
        return_data = {}

    total_tax = return_data.get('total_tax', 0)
    total_withholding = return_data.get('total_withholding', 0)
    refund = None
    tax_owed = None
    if total_withholding > total_tax:
        refund = total_withholding - total_tax
    else:
        tax_owed = total_tax - total_withholding

    branding = get_branding_config()
    user_id = session_data.get("user_id")
    user_tier = get_user_tier(user_id)

    full_report = return_data.get("advisory_report", {
        "current_federal_tax": total_tax,
        "refund": refund,
        "tax_owed": tax_owed,
        "effective_rate": return_data.get("effective_rate", 0),
        "top_opportunities": return_data.get("recommendations", []),
        "detailed_findings": return_data.get("detailed_findings", []),
        "executive_summary": return_data.get("executive_summary", ""),
        "scenarios": return_data.get("scenarios", []),
        "projections": return_data.get("projections", []),
        "overall_confidence": return_data.get("confidence", 85),
    })

    filtered_report = ReportAccessControl.filter_report(full_report, user_tier)
    show_upgrade = (
        user_tier in [SubscriptionTier.FREE, SubscriptionTier.BASIC] and
        "upgrade_prompt" in filtered_report
    )

    template_name = "results.html"
    context = {
        "request": request,
        "session_id": session_id,
        "return_id": return_data.get('return_id', session_id[:12]),
        "return_data": return_data,
        "refund": refund,
        "tax_owed": tax_owed,
        "report": filtered_report,
        "user_tier": user_tier.value,
        "show_upgrade": show_upgrade,
        "branding": {
            "platform_name": branding.platform_name,
            "company_name": branding.company_name,
            "primary_color": branding.primary_color,
            "secondary_color": branding.secondary_color,
            "accent_color": branding.accent_color,
            "logo_url": branding.logo_url,
            "favicon_url": branding.favicon_url,
            "custom_css": branding.custom_css,
            "custom_js": branding.custom_js,
            "meta_description": branding.meta_description,
        }
    }
    response = templates.TemplateResponse(template_name, context)
    return response


# =========================================================================
# LEGACY ADVISOR REDIRECTS
# =========================================================================

@router.get("/advisor", include_in_schema=False)
@router.get("/tax-advisory", include_in_schema=False)
@router.get("/advisory", include_in_schema=False)
@router.get("/start", include_in_schema=False)
@router.get("/analysis", include_in_schema=False)
@router.get("/tax-advisory/v2", include_in_schema=False)
@router.get("/advisory/v2", include_in_schema=False)
@router.get("/start/v2", include_in_schema=False)
@router.get("/simple", include_in_schema=False)
@router.get("/conversation", include_in_schema=False)
@router.get("/chat", include_in_schema=False)
def legacy_advisor_routes_redirect():
    """Legacy advisor routes — permanent redirect to intelligent advisor."""
    return RedirectResponse(url="/intelligent-advisor", status_code=301)
