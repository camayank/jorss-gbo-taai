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

# Comprehensive template globals to prevent UndefinedError
_page_defaults = {
    "current_path": "", "active_page": "", "nav_sections": [],
    "branding": {"platform_name": "Tax Advisory Platform", "support_email": "support@example.com"},
    "brand_name": "Tax Advisory Platform", "platform_name": "Tax Advisory Platform",
    "platform_url": "", "contact_email": "support@example.com",
    "tenant_features": {"documents": True, "support": True, "tasks": True, "appointments": True, "deadlines": True, "messaging": True, "analytics": True},
    "sidebar_theme": "default", "logo_url": "",
    "user": {"role": "anonymous", "name": "Guest", "email": ""},
}
for _k, _v in _page_defaults.items():
    templates.env.globals.setdefault(_k, _v)

class _PageConfig:
    APP_NAME = "Tax Advisory Platform"
    SUPPORT_EMAIL = "support@example.com"
    TAX_YEAR = 2025
templates.env.globals.setdefault("config", _PageConfig())


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
    return RedirectResponse(url="/landing", status_code=301)


# =========================================================================
# CANONICAL REAL PAGES
# =========================================================================

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


# =========================================================================
# CPA SETTINGS PAGES
# =========================================================================

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


# =========================================================================
# LEGAL PAGES
# =========================================================================

@router.get("/for-cpas", response_class=HTMLResponse)
def cpa_landing_page(request: Request):
    """CPA Landing Page - Marketing page for CPA lead generation platform."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("cpa_landing.html", {"request": request, "branding": branding})


@router.get("/terms", response_class=HTMLResponse)
def terms_of_service(request: Request):
    """Terms of Service - Legal terms and conditions."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("terms.html", {"request": request, "branding": branding})


@router.get("/privacy", response_class=HTMLResponse)
def privacy_policy(request: Request):
    """Privacy Policy - Data collection and usage policies."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return templates.TemplateResponse("privacy.html", {"request": request, "branding": branding})


@router.get("/cookies", response_class=HTMLResponse)
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


# =========================================================================
# CONTACT
# =========================================================================

@router.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})


# =========================================================================
# CLIENT LOGIN
# =========================================================================

@router.get("/client/login", response_class=HTMLResponse)
def client_login_page(request: Request, next: str = "/app/portal"):
    """Client portal login entrypoint."""
    return templates.TemplateResponse(
        "auth/client_login.html",
        {"request": request, "next_url": next or "/app/portal"},
    )


# =========================================================================
# LOGOUT
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


# =========================================================================
# ADVISORY REPORT PREVIEW & SCENARIOS
# =========================================================================

@router.get("/advisory-report-preview", response_class=HTMLResponse)
async def advisory_report_preview(request: Request):
    """Serve advisory report preview page."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    return templates.TemplateResponse("advisory_report_preview.html", {"request": request})


@router.get("/scenarios", response_class=HTMLResponse)
def scenarios_page(request: Request, session_id: str = None):
    """Scenario comparison - compare tax scenarios side by side."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    user_context = _ui_user_context(request)
    return templates.TemplateResponse(
        "scenarios.html",
        {"request": request, "user": user_context, "session_id": session_id, "page_title": "Scenario Comparison"}
    )


@router.get("/projections", response_class=HTMLResponse)
def projections_redirect(request: Request, session_id: str = None):
    """Redirect to intelligent advisor for tax projections."""
    if session_id:
        return RedirectResponse(url=f"/intelligent-advisor?session_id={session_id}", status_code=302)
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


@router.get("/refund-tracker", response_class=HTMLResponse)
def refund_tracker(request: Request):
    """Refund status tracker — links to IRS Where's My Refund."""
    user_context = _ui_user_context(request)
    return templates.TemplateResponse("refund_tracker.html", {
        "request": request, "user": user_context, "page_title": "Refund Tracker"
    })


@router.get("/advisory-report-preview", response_class=HTMLResponse)
async def advisory_report_preview(request: Request):
    """Serve advisory report preview page with session data."""
    denied = _require_any_auth(request)
    if denied:
        return denied

    session_id = request.query_params.get('session_id') or request.cookies.get('tax_session_id')
    taxpayer_name = "Client"
    filing_status = ""
    tax_year = 2025
    disclaimer = ""

    if session_id:
        try:
            from database.session_persistence import get_session_persistence
            persistence = get_session_persistence()
            raw = persistence.load_session_tax_return(session_id)
            if raw:
                rd = raw.get("return_data", raw) if isinstance(raw, dict) else {}
                tp = rd.get("taxpayer", {})
                taxpayer_name = f"{tp.get('first_name', '')} {tp.get('last_name', '')}".strip() or "Client"
                filing_status = rd.get("filing_status", "")
                tax_year = rd.get("tax_year", 2025)
        except Exception:
            pass

    try:
        from advisory.disclaimer import CIRCULAR_230_DISCLAIMER
        disclaimer = CIRCULAR_230_DISCLAIMER
    except ImportError:
        disclaimer = "This report is for informational purposes only."

    user_context = _ui_user_context(request)
    return templates.TemplateResponse("advisory_report_preview.html", {
        "request": request,
        "user": user_context,
        "session_id": session_id,
        "taxpayer_name": taxpayer_name,
        "filing_status": filing_status,
        "tax_year": tax_year,
        "circular_230_disclaimer": disclaimer,
    })


# =========================================================================
# RESULTS
# =========================================================================

@router.get("/results", response_class=HTMLResponse)
def filing_results(request: Request, session_id: str = None):
    """Show completed tax return results with subscription tier filtering."""
    from config.branding import get_branding_config
    from database.session_persistence import get_session_persistence
    from subscription.tier_control import ReportAccessControl, SubscriptionTier, get_user_tier

    if not session_id:
        session_id = request.query_params.get('session_id')
    if not session_id:
        session_id = request.cookies.get('tax_session_id')

    # Allow access with session_id even without login (for advisor → results flow)
    if not session_id:
        denied = _require_any_auth(request)
        if denied:
            return denied
    if not session_id:
        return RedirectResponse(url="/lead-magnet/", status_code=302)

    persistence = get_session_persistence()
    session_data = persistence.load_session(session_id)
    if not session_data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Return not found or expired.")

    raw_return = persistence.load_session_tax_return(session_id)
    if not raw_return:
        raw_return = {}

    # Unwrap nested structure: load_session_tax_return returns
    # {"return_data": {...}, "calculated_results": {...}, "tax_year": ...}
    return_data = raw_return.get('return_data', raw_return) if isinstance(raw_return, dict) else {}
    calculated = raw_return.get('calculated_results', {}) if isinstance(raw_return, dict) else {}
    # Merge calculated results into return_data for template access
    if calculated:
        for k, v in calculated.items():
            if k not in return_data or not return_data[k]:
                return_data[k] = v

    total_tax = return_data.get('tax_liability', 0) or return_data.get('total_tax', 0)
    total_withholding = return_data.get('total_payments', 0) or return_data.get('total_withholding', 0)
    refund = None
    tax_owed = None
    if total_withholding > total_tax:
        refund = total_withholding - total_tax
    else:
        tax_owed = total_tax - total_withholding

    branding = get_branding_config()
    # session_data is a SessionRecord (dataclass), not a dict
    sd = session_data.data if hasattr(session_data, 'data') else (session_data if isinstance(session_data, dict) else {})
    user_id = sd.get("user_id") if isinstance(sd, dict) else getattr(session_data, 'tenant_id', None)
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
    return templates.TemplateResponse("results.html", context)


# =========================================================================
# ADMIN
# =========================================================================

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


# =========================================================================
# 301 REDIRECTS — AUTH ALIASES
# =========================================================================

@router.get("/signin", include_in_schema=False)
def signin_redirect():
    return RedirectResponse(url="/login", status_code=301)


@router.get("/register", include_in_schema=False)
def register_redirect():
    return RedirectResponse(url="/signup", status_code=301)


@router.get("/mfa-setup", include_in_schema=False)
def mfa_setup_redirect():
    return RedirectResponse(url="/auth/mfa-setup", status_code=301)


@router.get("/mfa-verify", include_in_schema=False)
def mfa_verify_redirect():
    return RedirectResponse(url="/auth/mfa-verify", status_code=301)


@router.get("/forgot-password", include_in_schema=False)
def forgot_password_redirect():
    return RedirectResponse(url="/auth/forgot-password", status_code=301)


@router.get("/reset-password", include_in_schema=False)
def reset_password_redirect():
    return RedirectResponse(url="/auth/reset-password", status_code=301)


# =========================================================================
# 301 REDIRECTS — PORTAL / DASHBOARD ALIASES
# =========================================================================

@router.get("/portal", include_in_schema=False)
def portal_redirect():
    return RedirectResponse(url="/app/portal", status_code=301)


@router.get("/client", include_in_schema=False)
def client_redirect():
    return RedirectResponse(url="/app/portal", status_code=301)


@router.get("/app/settings", include_in_schema=False)
def app_settings_redirect():
    return RedirectResponse(url="/settings/profile", status_code=301)


@router.get("/app/workspace", include_in_schema=False)
def app_workspace_redirect():
    return RedirectResponse(url="/cpa/dashboard", status_code=301)


@router.get("/settings", include_in_schema=False)
def settings_redirect():
    return RedirectResponse(url="/settings/profile", status_code=301)


@router.get("/profile", include_in_schema=False)
def profile_redirect():
    return RedirectResponse(url="/settings/profile", status_code=301)


@router.get("/dashboard", include_in_schema=False)
def dashboard_redirect():
    return RedirectResponse(url="/cpa/dashboard", status_code=301)


@router.get("/workspace", include_in_schema=False)
def workspace_redirect():
    return RedirectResponse(url="/cpa/dashboard", status_code=301)


@router.get("/cpa-landing", include_in_schema=False)
def cpa_landing_redirect():
    return RedirectResponse(url="/for-cpas", status_code=301)


# =========================================================================
# 301 REDIRECTS — DATA PAGE ALIASES
# =========================================================================

@router.get("/clients", include_in_schema=False)
def clients_redirect():
    return RedirectResponse(url="/cpa/clients", status_code=301)


@router.get("/documents/library", response_class=HTMLResponse)
def documents_library_page(request: Request):
    """Document library page."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    from config.branding import get_branding_config
    return templates.TemplateResponse("documents/library.html", {
        "request": request,
        "branding": get_branding_config(),
    })


@router.get("/documents", include_in_schema=False)
def documents_redirect():
    return RedirectResponse(url="/documents/library", status_code=301)


@router.get("/returns", include_in_schema=False)
def returns_redirect():
    return RedirectResponse(url="/cpa/returns/queue", status_code=301)


@router.get("/projections", include_in_schema=False)
def projections_redirect():
    return RedirectResponse(url="/scenarios", status_code=301)


@router.get("/support", include_in_schema=False)
def support_redirect():
    return RedirectResponse(url="/support/tickets", status_code=301)


# =========================================================================
# 301 REDIRECTS — LEGAL ALIASES
# =========================================================================

@router.get("/privacy-policy", include_in_schema=False)
def privacy_policy_redirect():
    return RedirectResponse(url="/privacy", status_code=301)


@router.get("/terms-of-service", include_in_schema=False)
def terms_of_service_redirect():
    return RedirectResponse(url="/terms", status_code=301)


@router.get("/cookie-policy", include_in_schema=False)
def cookie_policy_redirect():
    return RedirectResponse(url="/cookies", status_code=301)


# =========================================================================
# 301 REDIRECTS — LEAD MAGNET ALIASES
# =========================================================================

@router.get("/estimate", include_in_schema=False)
@router.get("/quick-estimate", include_in_schema=False)
@router.get("/start", include_in_schema=False)
@router.get("/start/v2", include_in_schema=False)
@router.get("/simple", include_in_schema=False)
@router.get("/file", include_in_schema=False)
def lead_magnet_redirect():
    return RedirectResponse(url="/lead-magnet", status_code=301)


@router.get("/lead-magnet/universal-report", include_in_schema=False)
def lead_magnet_universal_report_redirect():
    return RedirectResponse(url="/lead-magnet/report", status_code=301)


# =========================================================================
# 301 REDIRECTS — INTELLIGENT ADVISOR ALIASES
# =========================================================================

@router.get("/chat", include_in_schema=False)
@router.get("/advisor", include_in_schema=False)
@router.get("/advisory", include_in_schema=False)
@router.get("/advisory/v2", include_in_schema=False)
@router.get("/conversation", include_in_schema=False)
@router.get("/analysis", include_in_schema=False)
@router.get("/guided", include_in_schema=False)
@router.get("/guided/{session_id}", include_in_schema=False)
@router.get("/smart-tax", include_in_schema=False)
@router.get("/smart-tax-legacy", include_in_schema=False)
@router.get("/smart-tax/{path:path}", include_in_schema=False)
@router.get("/tax-advisory", include_in_schema=False)
@router.get("/tax-advisory/v2", include_in_schema=False)
def advisor_aliases_redirect():
    return RedirectResponse(url="/intelligent-advisor", status_code=301)


# =========================================================================
# SEO CALCULATOR PAGES
# =========================================================================

@router.get("/self-employment-tax", response_class=HTMLResponse)
def self_employment_tax_page(request: Request):
    """Self-employment tax calculator — public SEO page."""
    return templates.TemplateResponse(
        "self_employment_tax.html", {"request": request}
    )


@router.get("/scorp-vs-llc", response_class=HTMLResponse)
def scorp_vs_llc_page(request: Request):
    """S-Corp vs LLC tax savings calculator — public SEO page."""
    return templates.TemplateResponse(
        "scorp_vs_llc.html", {"request": request}
    )


@router.get("/tax-brackets", response_class=HTMLResponse)
def tax_brackets_page(request: Request):
    """2025 federal tax brackets calculator — public SEO page."""
    return templates.TemplateResponse(
        "tax_brackets.html", {"request": request}
    )


# =========================================================================
# CPA TAX TOOLS (capital gains, K-1 basis, rental depreciation)
# =========================================================================

@router.get("/capital-gains", response_class=HTMLResponse)
def capital_gains_page(request: Request):
    """Capital gains tax calculator — CPA/client tool."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    user_context = _ui_user_context(request)
    return templates.TemplateResponse(
        "capital_gains.html",
        {"request": request, "user": user_context, "page_title": "Capital Gains Calculator"}
    )


@router.get("/k1-basis", response_class=HTMLResponse)
def k1_basis_page(request: Request):
    """K-1 basis tracker — CPA/client tool."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    user_context = _ui_user_context(request)
    return templates.TemplateResponse(
        "k1_basis.html",
        {"request": request, "user": user_context, "page_title": "K-1 Basis Tracker"}
    )


@router.get("/rental-depreciation", response_class=HTMLResponse)
def rental_depreciation_page(request: Request):
    """Rental property depreciation calculator — CPA/client tool."""
    denied = _require_any_auth(request)
    if denied:
        return denied
    user_context = _ui_user_context(request)
    return templates.TemplateResponse(
        "rental_depreciation.html",
        {"request": request, "user": user_context, "page_title": "Rental Depreciation Calculator"}
    )


# =========================================================================
# UPGRADE / PRICING REDIRECT
# =========================================================================

@router.get("/upgrade", include_in_schema=False)
def upgrade_redirect():
    """Redirect to CPA pricing page — used by locked strategy card CTAs."""
    return RedirectResponse(url="/for-cpas#pricing", status_code=302)


@router.get("/pricing", include_in_schema=False)
def pricing_redirect():
    """Redirect to CPA pricing page."""
    return RedirectResponse(url="/for-cpas#pricing", status_code=302)
