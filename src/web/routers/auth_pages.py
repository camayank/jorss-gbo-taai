"""
Auth page routes — extracted from app.py.

Routes:
- GET /login, /signin, /auth/login
- GET /signup, /register, /auth/register
- GET /forgot-password, /auth/forgot-password
- GET /reset-password, /auth/reset-password
- GET /auth/mfa-setup, /mfa-setup
- GET /auth/mfa-verify, /mfa-verify
- GET /auth/post-login-redirect
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["auth-pages"])


# ---------------------------------------------------------------------------
# Role-bucket resolution (imported from app at mount time)
# ---------------------------------------------------------------------------

def _resolve_request_role_bucket(request: Request) -> str:
    """Resolve authenticated principal into a UI role bucket."""
    from security.auth_decorators import get_user_from_request
    from web.constants import (
        ADMIN_UI_ROLES,
        CPA_UI_ROLES,
        CLIENT_UI_ROLES,
    )

    def _norm(value):
        if value is None:
            return ""
        if hasattr(value, "value"):
            value = value.value
        return str(value).strip().lower()

    user = get_user_from_request(request)
    if user:
        role = _norm(user.get("role"))
        user_type = _norm(user.get("user_type"))
        if role in ADMIN_UI_ROLES or user_type == "platform_admin":
            return "admin"
        if role in CPA_UI_ROLES or user_type in {"cpa_team", "firm_user"}:
            return "cpa"
        if role in CLIENT_UI_ROLES or user_type in {"client", "cpa_client", "consumer"}:
            return "client"

    return "anonymous"


# ---------------------------------------------------------------------------
# Template helper
# ---------------------------------------------------------------------------

def _get_templates():
    """Lazy-import the shared Jinja2Templates instance from app."""
    from web.app import templates
    return templates


# ---------------------------------------------------------------------------
# Auth page routes
# ---------------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
@router.get("/signin", response_class=HTMLResponse)
@router.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Login Page — premium authentication experience."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return _get_templates().TemplateResponse("auth/login.html", {"request": request, "branding": branding})


@router.get("/signup", response_class=HTMLResponse)
@router.get("/register", response_class=HTMLResponse)
@router.get("/auth/register", response_class=HTMLResponse)
def signup_page(request: Request):
    """Signup Page — create new account."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return _get_templates().TemplateResponse("auth/signup.html", {"request": request, "branding": branding})


@router.get("/forgot-password", response_class=HTMLResponse)
@router.get("/auth/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    """Forgot Password Page."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return _get_templates().TemplateResponse("auth/forgot_password.html", {"request": request, "branding": branding})


@router.get("/reset-password", response_class=HTMLResponse)
@router.get("/auth/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = None):
    """Reset Password Page — allows users to set new password with token."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return _get_templates().TemplateResponse(
        "auth/reset-password.html",
        {"request": request, "branding": branding, "reset_token": token},
    )


@router.get("/auth/mfa-setup", response_class=HTMLResponse)
@router.get("/mfa-setup", response_class=HTMLResponse)
def mfa_setup_page(request: Request):
    """MFA Setup Page — configure two-factor authentication."""
    return _get_templates().TemplateResponse("auth/mfa_setup.html", {"request": request})


@router.get("/auth/mfa-verify", response_class=HTMLResponse)
@router.get("/mfa-verify", response_class=HTMLResponse)
def mfa_verify_page(request: Request, next: str = "/intelligent-advisor"):
    """MFA Verification Page — enter TOTP code during login."""
    from config.branding import get_branding_config
    branding = get_branding_config()
    return _get_templates().TemplateResponse(
        "auth/mfa_verify.html",
        {"request": request, "branding": branding, "next_url": next},
    )


@router.get("/auth/post-login-redirect", response_class=HTMLResponse)
def post_login_redirect(request: Request):
    """Role-based post-login redirect."""
    bucket = _resolve_request_role_bucket(request)
    destinations = {
        "admin": "/admin",
        "cpa": "/cpa/dashboard",
        "client": "/intelligent-advisor",
        "anonymous": "/landing",
    }
    destination = destinations.get(bucket, "/intelligent-advisor")

    # Check for explicit ?next= parameter (with open-redirect protection)
    next_url = request.query_params.get("next")
    if next_url and next_url.startswith("/") and not next_url.startswith("//") and not next_url.startswith("/\\"):
        from urllib.parse import urlparse
        parsed = urlparse(next_url)
        if not parsed.netloc:
            destination = parsed.path + (f"?{parsed.query}" if parsed.query else "")

    return RedirectResponse(url=destination, status_code=302)
