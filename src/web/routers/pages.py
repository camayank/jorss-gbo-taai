"""
Page Routes - HTML UI Pages

SPEC-005: Extracted from app.py for modularity.

Routes:
- Landing pages (/, /landing, /file, etc.)
- Dashboard pages (/dashboard, /cpa, /client)
- Legal pages (/terms, /privacy, /cookies, /disclaimer)
- Admin pages (/admin, /hub)
- Workflow pages (/workflow, /smart-tax, /results)
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Pages"])

# Templates will be set by the main app
templates: Jinja2Templates = None


def set_templates(t: Jinja2Templates):
    """Set the templates instance from the main app."""
    global templates
    templates = t


# =============================================================================
# LANDING PAGES
# =============================================================================

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Main landing page - redirects to intelligent advisor."""
    return templates.TemplateResponse("intelligent_advisor.html", {"request": request})


@router.get("/file", response_class=HTMLResponse)
@router.get("/intelligent-advisor", response_class=HTMLResponse)
def intelligent_tax_advisor(request: Request):
    """Intelligent Tax Advisor - main filing interface."""
    return templates.TemplateResponse("intelligent_advisor.html", {"request": request})


@router.get("/landing", response_class=HTMLResponse)
def landing_page(request: Request):
    """Marketing landing page."""
    return templates.TemplateResponse("landing.html", {"request": request})


# =============================================================================
# DASHBOARD PAGES
# =============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """User dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/cpa", response_class=HTMLResponse)
def cpa_dashboard(request: Request):
    """CPA dashboard - redirects to CPA dashboard pages."""
    return RedirectResponse(url="/cpa/dashboard", status_code=302)


@router.get("/cpa/settings/payments", response_class=HTMLResponse)
def cpa_payment_settings(request: Request):
    """CPA payment settings page."""
    return templates.TemplateResponse(
        "cpa/settings_payments.html",
        {"request": request}
    )


@router.get("/cpa/settings/branding", response_class=HTMLResponse)
def cpa_branding_settings(request: Request):
    """CPA branding settings page."""
    return templates.TemplateResponse(
        "cpa/settings_branding.html",
        {"request": request}
    )


@router.get("/cpa-landing", response_class=HTMLResponse)
@router.get("/for-cpas", response_class=HTMLResponse)
def cpa_landing_page(request: Request):
    """CPA marketing landing page."""
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/client", response_class=HTMLResponse)
def client_portal(request: Request):
    """Client portal page."""
    return templates.TemplateResponse(
        "client_portal.html",
        {
            "request": request,
            "page_title": "Client Portal",
            "client_name": "Client",
        }
    )


# =============================================================================
# LEGAL PAGES
# =============================================================================

@router.get("/terms", response_class=HTMLResponse)
@router.get("/terms-of-service", response_class=HTMLResponse)
def terms_of_service(request: Request):
    """Terms of Service page."""
    return templates.TemplateResponse("legal/terms.html", {"request": request})


@router.get("/privacy", response_class=HTMLResponse)
@router.get("/privacy-policy", response_class=HTMLResponse)
def privacy_policy(request: Request):
    """Privacy Policy page."""
    return templates.TemplateResponse("legal/privacy.html", {"request": request})


@router.get("/cookies", response_class=HTMLResponse)
@router.get("/cookie-policy", response_class=HTMLResponse)
def cookie_policy(request: Request):
    """Cookie Policy page."""
    return templates.TemplateResponse("legal/cookies.html", {"request": request})


@router.get("/disclaimer", response_class=HTMLResponse)
def disclaimer_page(request: Request):
    """Disclaimer page."""
    return templates.TemplateResponse("legal/disclaimer.html", {"request": request})


# =============================================================================
# REDIRECT PAGES
# =============================================================================

@router.get("/logout")
def logout_redirect(request: Request):
    """Logout and redirect to home."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("tax_session_id")
    response.delete_cookie("auth_token")
    return response


@router.get("/scenarios", response_class=HTMLResponse)
def scenarios_redirect(request: Request, session_id: str = None):
    """Redirect to scenarios page."""
    url = f"/intelligent-advisor?tab=scenarios"
    if session_id:
        url += f"&session_id={session_id}"
    return RedirectResponse(url=url, status_code=302)


@router.get("/projections", response_class=HTMLResponse)
def projections_redirect(request: Request, session_id: str = None):
    """Redirect to projections page."""
    url = f"/intelligent-advisor?tab=projections"
    if session_id:
        url += f"&session_id={session_id}"
    return RedirectResponse(url=url, status_code=302)


@router.get("/settings", response_class=HTMLResponse)
def settings_redirect(request: Request):
    """Redirect to settings page."""
    return RedirectResponse(url="/intelligent-advisor?tab=settings", status_code=302)


@router.get("/documents", response_class=HTMLResponse)
def documents_redirect(request: Request):
    """Redirect to documents page."""
    return RedirectResponse(url="/intelligent-advisor?tab=documents", status_code=302)


@router.get("/returns", response_class=HTMLResponse)
def returns_redirect(request: Request):
    """Redirect to returns page."""
    return RedirectResponse(url="/intelligent-advisor?tab=returns", status_code=302)


@router.get("/clients", response_class=HTMLResponse)
def clients_redirect(request: Request):
    """Redirect to clients page."""
    return RedirectResponse(url="/cpa/clients", status_code=302)


# =============================================================================
# ADMIN PAGES
# =============================================================================

@router.get("/admin", response_class=HTMLResponse)
@router.get("/admin/{path:path}", response_class=HTMLResponse)
def admin_dashboard(request: Request, path: str = ""):
    """Admin dashboard SPA."""
    return templates.TemplateResponse("admin/index.html", {"request": request})


@router.get("/hub", response_class=HTMLResponse)
@router.get("/system-hub", response_class=HTMLResponse)
def system_hub(request: Request):
    """System hub page."""
    return templates.TemplateResponse(
        "system_hub.html",
        {
            "request": request,
            "page_title": "System Hub",
        }
    )


@router.get("/workflow", response_class=HTMLResponse)
@router.get("/workflow-hub", response_class=HTMLResponse)
def workflow_hub(request: Request):
    """Workflow hub page."""
    return templates.TemplateResponse(
        "workflow_hub.html",
        {
            "request": request,
            "page_title": "Workflow Hub",
        }
    )


# =============================================================================
# SMART TAX PAGES
# =============================================================================

@router.get("/smart-tax", response_class=HTMLResponse)
@router.get("/smart-tax/{path:path}", response_class=HTMLResponse)
def smart_tax_redirect(request: Request, path: str = ""):
    """Redirect smart-tax to intelligent advisor."""
    return RedirectResponse(url="/intelligent-advisor", status_code=302)


@router.get("/smart-tax-legacy", response_class=HTMLResponse)
def smart_tax_app_legacy(request: Request, path: str = ""):
    """Legacy smart tax app."""
    return templates.TemplateResponse(
        "smart_tax_app.html",
        {"request": request}
    )


# =============================================================================
# ADVISORY PAGES
# =============================================================================

@router.get("/tax-advisory", response_class=HTMLResponse)
@router.get("/advisory", response_class=HTMLResponse)
@router.get("/start", response_class=HTMLResponse)
@router.get("/analysis", response_class=HTMLResponse)
def tax_advisory_page(request: Request):
    """Tax advisory redirect to intelligent advisor."""
    return RedirectResponse(url="/intelligent-advisor", status_code=302)


@router.get("/simple", response_class=HTMLResponse)
@router.get("/conversation", response_class=HTMLResponse)
@router.get("/chat", response_class=HTMLResponse)
def simple_chat_page(request: Request):
    """Simple chat interface redirect."""
    return RedirectResponse(url="/intelligent-advisor", status_code=302)
