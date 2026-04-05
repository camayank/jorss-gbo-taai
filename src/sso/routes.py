"""
SSO Authentication Routes

OIDC flow (Okta, Azure AD, Google Workspace):
  GET /sso/oidc/start?firm_id=<uuid>           → redirect user to IdP
  GET /sso/oidc/callback?code=&state=          → exchange code, provision user, issue JWT

SAML 2.0 flow:
  GET  /sso/saml/start?firm_id=<uuid>          → redirect user to IdP
  POST /sso/saml/acs                           → process SAMLResponse, provision user, issue JWT
  GET  /sso/saml/slo?firm_id=<uuid>            → SP-initiated single logout

Config management (requires PARTNER role):
  GET  /sso/config/{firm_id}                   → get SSO config
  PUT  /sso/config/{firm_id}                   → create/update SSO config
  POST /sso/config/{firm_id}/enable            → enable SSO for firm
  POST /sso/config/{firm_id}/disable           → disable SSO for firm
"""
import logging
import os
from datetime import timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db_session as get_db
from rbac.dependencies import require_role
from rbac.roles import Role
from rbac.jwt import create_access_token

from .config_service import SSOConfigService
from .models import SSOProvider
from .oidc_service import OIDCService, map_groups_to_role
from .provisioning import JITProvisioningService

logger = logging.getLogger(__name__)

sso_router = APIRouter(prefix="/sso", tags=["SSO Authentication"])

# Temporary in-memory state store — replace with Redis in production
# Maps state_token → firm_id string
_oidc_state_store: dict = {}

_IS_PROD = os.environ.get("APP_ENVIRONMENT", "development") not in (
    "development", "dev", "local", "test", "testing"
)


def _get_base_url() -> str:
    return os.environ.get("APP_BASE_URL", "https://app.example.com")


def _make_jwt(user, firm_id: UUID, session_max_age_seconds: int = 0) -> str:
    """Issue an app JWT for a freshly-provisioned SSO user."""
    from rbac.roles import Role as RBACRole
    try:
        rbac_role = RBACRole(user.role)
    except ValueError:
        rbac_role = RBACRole.STAFF

    expires = timedelta(seconds=session_max_age_seconds) if session_max_age_seconds > 0 else None
    return create_access_token(
        user_id=user.user_id,
        email=user.email,
        name=user.full_name,
        role=rbac_role,
        user_type="firm_user",
        firm_id=firm_id,
        expires_delta=expires,
    )


def _redirect_with_token(token: str) -> RedirectResponse:
    """Redirect to CPA dashboard with the JWT as cookie and URL param."""
    resp = RedirectResponse(
        url=f"/cpa/dashboard?sso_success=true&token={token}",
        status_code=302,
    )
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=_IS_PROD,
        samesite="lax",
    )
    return resp


# ─── OIDC Flow ────────────────────────────────────────────────────────────────

@sso_router.get("/oidc/start")
async def oidc_start(
    firm_id: UUID = Query(..., description="Firm UUID for SSO lookup"),
    db: Session = Depends(get_db),
):
    """Begin OIDC SSO flow. Redirects user to the configured IdP."""
    cfg = SSOConfigService(db).get_enabled_config(firm_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="SSO not configured or not enabled for this firm")

    if cfg.provider not in (
        SSOProvider.OKTA_OIDC.value,
        SSOProvider.AZURE_AD_OIDC.value,
        SSOProvider.GOOGLE_WORKSPACE_OIDC.value,
    ):
        raise HTTPException(status_code=400, detail="This firm uses SAML, not OIDC")

    oidc = OIDCService(
        client_id=cfg.oidc_client_id,
        client_secret=cfg.oidc_client_secret,
        discovery_url=cfg.oidc_discovery_url,
        redirect_uri=f"{_get_base_url()}/api/core/auth/sso/oidc/callback",
    )
    url, state = await oidc.get_authorization_url()
    _oidc_state_store[state] = str(firm_id)
    return RedirectResponse(url=url, status_code=302)


@sso_router.get("/oidc/callback")
async def oidc_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle OIDC callback. Provisions the user, issues a JWT, redirects to dashboard."""
    if error:
        logger.warning(f"OIDC error from IdP: {error}")
        return RedirectResponse(f"/login?error=sso_failed&detail={error}", status_code=302)

    firm_id_str = _oidc_state_store.pop(state, None)
    if not firm_id_str:
        logger.warning("OIDC callback received with unknown state token")
        return RedirectResponse("/login?error=sso_invalid_state", status_code=302)

    firm_id = UUID(firm_id_str)
    cfg = SSOConfigService(db).get_enabled_config(firm_id)
    if cfg is None:
        return RedirectResponse("/login?error=sso_config_missing", status_code=302)

    oidc = OIDCService(
        client_id=cfg.oidc_client_id,
        client_secret=cfg.oidc_client_secret,
        discovery_url=cfg.oidc_discovery_url,
        redirect_uri=f"{_get_base_url()}/api/core/auth/sso/oidc/callback",
    )
    try:
        user_info = await oidc.exchange_code(code, state)
    except ValueError as e:
        logger.warning(f"OIDC exchange failed for firm {firm_id}: {e}")
        return RedirectResponse("/login?error=sso_failed", status_code=302)

    role = map_groups_to_role(user_info.groups, cfg.attribute_mapping)
    user = JITProvisioningService(db).provision_or_update(
        firm_id=firm_id,
        email=user_info.email,
        first_name=user_info.first_name or "",
        last_name=user_info.last_name or "",
        role=role,
        sso_provider=cfg.provider,
        sso_subject_id=user_info.sub,
    )
    token = _make_jwt(user, firm_id, cfg.session_max_age_seconds)
    return _redirect_with_token(token)


# ─── SAML Flow ────────────────────────────────────────────────────────────────

@sso_router.get("/saml/start")
async def saml_start(
    firm_id: UUID = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Begin SAML 2.0 SP-initiated SSO. Redirects user to IdP login page."""
    from .saml_service import SAMLService

    cfg = SSOConfigService(db).get_enabled_config(firm_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="SSO not configured or not enabled for this firm")
    if cfg.provider != SSOProvider.SAML.value:
        raise HTTPException(status_code=400, detail="This firm uses OIDC, not SAML")

    idp_meta = await _fetch_saml_idp_metadata(cfg.saml_idp_metadata_url)
    saml = SAMLService(
        sp_entity_id=cfg.saml_sp_entity_id,
        acs_url=cfg.saml_acs_url,
        slo_url=cfg.saml_slo_url,
        idp_entity_id=idp_meta["entity_id"],
        idp_sso_url=idp_meta["sso_url"],
        idp_slo_url=idp_meta["slo_url"],
        idp_certificate=cfg.saml_idp_certificate or idp_meta["certificate"],
    )
    request_data = _build_saml_request_data(request, str(firm_id))
    redirect_url = saml.get_redirect_url(request_data)
    return RedirectResponse(url=redirect_url, status_code=302)


@sso_router.post("/saml/acs")
async def saml_acs(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Assertion Consumer Service — receives SAMLResponse POST from IdP.
    RelayState must carry the firm_id UUID.
    """
    from .saml_service import SAMLService

    form = await request.form()
    relay_state = form.get("RelayState", "")
    try:
        firm_id = UUID(relay_state)
    except (ValueError, AttributeError):
        return RedirectResponse("/login?error=sso_invalid_relay", status_code=302)

    cfg = SSOConfigService(db).get_enabled_config(firm_id)
    if cfg is None:
        return RedirectResponse("/login?error=sso_config_missing", status_code=302)

    idp_meta = await _fetch_saml_idp_metadata(cfg.saml_idp_metadata_url)
    saml = SAMLService(
        sp_entity_id=cfg.saml_sp_entity_id,
        acs_url=cfg.saml_acs_url,
        slo_url=cfg.saml_slo_url,
        idp_entity_id=idp_meta["entity_id"],
        idp_sso_url=idp_meta["sso_url"],
        idp_slo_url=idp_meta["slo_url"],
        idp_certificate=cfg.saml_idp_certificate or idp_meta["certificate"],
    )
    request_data = _build_saml_request_data(request, relay_state)
    # Inject the actual POST data for python3-saml
    request_data["post_data"] = dict(form)

    try:
        user_info = saml.process_acs_response(request_data)
    except ValueError as e:
        logger.warning(f"SAML ACS failed for firm {firm_id}: {e}")
        return RedirectResponse("/login?error=sso_failed", status_code=302)

    role = map_groups_to_role(user_info.groups, cfg.attribute_mapping)
    user = JITProvisioningService(db).provision_or_update(
        firm_id=firm_id,
        email=user_info.email,
        first_name=user_info.first_name or "",
        last_name=user_info.last_name or "",
        role=role,
        sso_provider="saml",
        sso_subject_id=user_info.name_id,
    )
    token = _make_jwt(user, firm_id, cfg.session_max_age_seconds)
    return _redirect_with_token(token)


@sso_router.get("/saml/slo")
async def saml_slo(
    firm_id: UUID = Query(...),
    db: Session = Depends(get_db),
):
    """
    SP-initiated Single Logout.
    Clears the app session cookie and redirects to login.
    Full IdP SLO redirect requires name_id from the current session —
    extend this endpoint to read it from the JWT cookie in production.
    """
    response = RedirectResponse(url="/login?logout=true", status_code=302)
    response.delete_cookie("access_token")
    return response


# ─── Config Management API ────────────────────────────────────────────────────

class SSOConfigRequest(BaseModel):
    provider: str
    saml_idp_metadata_url: Optional[str] = None
    saml_idp_certificate: Optional[str] = None
    saml_sp_entity_id: Optional[str] = None
    saml_acs_url: Optional[str] = None
    saml_slo_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_discovery_url: Optional[str] = None
    attribute_mapping: dict = {}
    session_max_age_seconds: int = 0
    allow_password_fallback: bool = True


@sso_router.get("/config/{firm_id}")
async def get_sso_config(
    firm_id: UUID,
    db: Session = Depends(get_db),
    auth=Depends(require_role(Role.PARTNER)),
):
    """Get SSO configuration for a firm. Requires PARTNER role."""
    cfg = SSOConfigService(db).get_config(firm_id)
    if cfg is None:
        return {"configured": False}
    return {
        "configured": True,
        "provider": cfg.provider,
        "is_enabled": cfg.is_enabled,
        "saml_idp_metadata_url": cfg.saml_idp_metadata_url,
        "saml_sp_entity_id": cfg.saml_sp_entity_id,
        "saml_acs_url": cfg.saml_acs_url,
        "oidc_client_id": cfg.oidc_client_id,
        "oidc_discovery_url": cfg.oidc_discovery_url,
        "attribute_mapping": cfg.attribute_mapping,
        "session_max_age_seconds": cfg.session_max_age_seconds,
        "allow_password_fallback": cfg.allow_password_fallback,
        # NOTE: oidc_client_secret and saml_idp_certificate are intentionally omitted
    }


@sso_router.put("/config/{firm_id}")
async def upsert_sso_config(
    firm_id: UUID,
    body: SSOConfigRequest,
    db: Session = Depends(get_db),
    auth=Depends(require_role(Role.PARTNER)),
):
    """Create or update SSO configuration for a firm. Requires PARTNER role."""
    try:
        provider = SSOProvider(body.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown SSO provider: {body.provider!r}")

    SSOConfigService(db).upsert_config(
        firm_id=firm_id,
        provider=provider,
        saml_idp_metadata_url=body.saml_idp_metadata_url,
        saml_idp_certificate=body.saml_idp_certificate,
        saml_sp_entity_id=body.saml_sp_entity_id,
        saml_acs_url=body.saml_acs_url,
        saml_slo_url=body.saml_slo_url,
        oidc_client_id=body.oidc_client_id,
        oidc_client_secret=body.oidc_client_secret,
        oidc_discovery_url=body.oidc_discovery_url,
        attribute_mapping=body.attribute_mapping,
        session_max_age_seconds=body.session_max_age_seconds,
        allow_password_fallback=body.allow_password_fallback,
    )
    return {"status": "ok"}


@sso_router.post("/config/{firm_id}/enable")
async def enable_sso(
    firm_id: UUID,
    db: Session = Depends(get_db),
    auth=Depends(require_role(Role.PARTNER)),
):
    """Enable SSO for a firm. Requires PARTNER role."""
    SSOConfigService(db).set_enabled(firm_id, True)
    return {"status": "enabled"}


@sso_router.post("/config/{firm_id}/disable")
async def disable_sso(
    firm_id: UUID,
    db: Session = Depends(get_db),
    auth=Depends(require_role(Role.PARTNER)),
):
    """Disable SSO for a firm (users fall back to password login). Requires PARTNER role."""
    SSOConfigService(db).set_enabled(firm_id, False)
    return {"status": "disabled"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_saml_request_data(request: Request, relay_state: str) -> dict:
    """Build the request_data dict expected by python3-saml from a FastAPI Request."""
    return {
        "https": "on" if request.url.scheme == "https" else "off",
        "http_host": request.url.hostname,
        "script_name": request.url.path,
        "server_port": str(request.url.port or (443 if request.url.scheme == "https" else 80)),
        "get_data": dict(request.query_params),
        "post_data": {},  # Populated from form data in ACS handler
        "relay_state": relay_state,
    }


async def _fetch_saml_idp_metadata(metadata_url: Optional[str]) -> dict:
    """Fetch and parse IdP SAML metadata XML to extract SSO/SLO URLs and certificate."""
    if not metadata_url:
        raise HTTPException(status_code=400, detail="SAML IdP metadata URL not configured")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(metadata_url)
            resp.raise_for_status()
        from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
        parsed = OneLogin_Saml2_IdPMetadataParser.parse(resp.text)
        idp = parsed.get("idp", {})
        cert = (
            list(idp.get("x509certMulti", {}).get("signing", [""]))[0]
            or idp.get("x509cert", "")
        )
        return {
            "entity_id": idp.get("entityId", ""),
            "sso_url": idp.get("singleSignOnService", {}).get("url", ""),
            "slo_url": idp.get("singleLogoutService", {}).get("url", ""),
            "certificate": cert,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch IdP metadata: {e}")
