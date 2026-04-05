"""
CPA Integration Status Routes

Manages third-party integration connections (QuickBooks, Xero, Google Calendar, etc.).
Stripe Connect is handled separately via payment_settings_routes.py.

QuickBooks OAuth2 Flow:
1. POST /integrations/quickbooks/authorize - Generate authorization URL
2. User visits authorization URL and grants permissions
3. QB redirects to /integrations/quickbooks/callback with code and state
4. Token is stored in database
"""

import logging
import os
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_dependencies import require_internal_cpa_auth
from database import get_async_session, QuickBooksConnectionRecord, QuickBooksTokenRecord
from integrations.quickbooks.oauth import QuickBooksOAuthClient
from integrations.quickbooks.config import QB_CONFIG

logger = logging.getLogger(__name__)

integration_router = APIRouter(prefix="/integrations", tags=["CPA Integrations"])

# In-memory integration state (per-session; production would use DB)
_integration_state: dict[str, dict[str, str]] = {}

SUPPORTED_INTEGRATIONS = {
    "quickbooks": {
        "name": "QuickBooks",
        "description": "Sync client financial data and invoices",
        "setup_url": "https://developer.intuit.com/app/developer/qbo/docs/get-started",
    },
    "xero": {
        "name": "Xero",
        "description": "Connect Xero accounting for seamless bookkeeping sync",
        "setup_url": "https://developer.xero.com/documentation/getting-started-guide/",
    },
    "gcal": {
        "name": "Google Calendar",
        "description": "Sync appointments and deadlines with Google Calendar",
        "setup_url": "https://developers.google.com/calendar/api/quickstart/python",
    },
    "calendly": {
        "name": "Calendly",
        "description": "Let clients book consultation sessions directly",
        "setup_url": "https://developer.calendly.com/getting-started",
    },
    "zapier": {
        "name": "Zapier",
        "description": "Automate workflows between 5000+ apps",
        "setup_url": "https://zapier.com/developer",
    },
}


class IntegrationStatusResponse(BaseModel):
    provider: str
    name: str
    description: str
    status: str = Field(description="connected, disconnected, pending")
    setup_url: Optional[str] = None


class ConnectResponse(BaseModel):
    provider: str
    status: str
    message: str
    setup_url: Optional[str] = None


class QBAuthorizeRequest(BaseModel):
    """Request to initiate QuickBooks OAuth2 flow."""
    pass


class QBAuthorizeResponse(BaseModel):
    """Response with authorization URL for QuickBooks."""
    authorization_url: str = Field(
        description="URL to redirect user to for QB authorization"
    )
    state: str = Field(
        description="CSRF protection state token (store for callback validation)"
    )


class QBCallbackRequest(BaseModel):
    """Request from QuickBooks authorization callback."""
    code: str = Field(description="Authorization code from QB")
    state: str = Field(description="State token from QB (must match stored value)")
    realm_id: str = Field(description="QB Company ID (Realm ID)")


class QBCallbackResponse(BaseModel):
    """Response after successful token exchange."""
    status: str = Field(default="connected")
    message: str = Field(default="QuickBooks token saved successfully")


@integration_router.get(
    "/status",
    summary="Get all integration statuses",
    response_model=list[IntegrationStatusResponse],
)
async def get_integration_statuses(_auth=Depends(require_internal_cpa_auth)):
    """Return the connection status for all supported integrations."""
    cpa_id = "default"  # Would come from auth context in production
    cpa_state = _integration_state.get(cpa_id, {})

    results = []
    for provider_id, info in SUPPORTED_INTEGRATIONS.items():
        results.append(IntegrationStatusResponse(
            provider=provider_id,
            name=info["name"],
            description=info["description"],
            status=cpa_state.get(provider_id, "disconnected"),
        ))
    return results


@integration_router.post(
    "/{provider}/connect",
    summary="Connect an integration",
    response_model=ConnectResponse,
)
async def connect_integration(provider: str, _auth=Depends(require_internal_cpa_auth)):
    """
    Initiate connection to a third-party integration.

    For integrations requiring OAuth (QuickBooks, Xero), returns setup instructions.
    For simpler integrations, marks as connected.
    """
    if provider not in SUPPORTED_INTEGRATIONS:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {provider}")

    info = SUPPORTED_INTEGRATIONS[provider]
    cpa_id = "default"

    if provider in ("quickbooks", "xero"):
        # These require real OAuth — provide setup instructions
        _integration_state.setdefault(cpa_id, {})[provider] = "pending"
        return ConnectResponse(
            provider=provider,
            status="pending",
            message=f"To complete {info['name']} setup, configure your API credentials in the developer portal.",
            setup_url=info["setup_url"],
        )
    else:
        # Simpler integrations can be toggled on directly
        _integration_state.setdefault(cpa_id, {})[provider] = "connected"
        return ConnectResponse(
            provider=provider,
            status="connected",
            message=f"{info['name']} connected successfully",
        )


@integration_router.post(
    "/{provider}/disconnect",
    summary="Disconnect an integration",
    response_model=ConnectResponse,
)
async def disconnect_integration(provider: str, _auth=Depends(require_internal_cpa_auth)):
    """Disconnect a third-party integration."""
    if provider not in SUPPORTED_INTEGRATIONS:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {provider}")

    cpa_id = "default"
    _integration_state.setdefault(cpa_id, {})[provider] = "disconnected"

    return ConnectResponse(
        provider=provider,
        status="disconnected",
        message=f"{SUPPORTED_INTEGRATIONS[provider]['name']} disconnected",
    )


# =============================================================================
# QuickBooks OAuth2 Authorization Flow Endpoints
# =============================================================================

# In-memory state cache for CSRF protection (per session)
_qb_state_cache: dict[str, str] = {}  # state -> cpa_id


@integration_router.post(
    "/quickbooks/authorize",
    summary="Initiate QuickBooks OAuth2 authorization",
    response_model=QBAuthorizeResponse,
    tags=["QuickBooks OAuth"],
)
async def initiate_qb_authorization(
    request: QBAuthorizeRequest,
    _auth=Depends(require_internal_cpa_auth),
) -> QBAuthorizeResponse:
    """
    Initiate QuickBooks OAuth2 authorization code flow.

    Step 1 of OAuth2 flow:
    1. Client calls this endpoint to get authorization URL
    2. Client redirects user to returned authorization_url
    3. User logs into QuickBooks and grants permissions
    4. QB redirects user to /integrations/quickbooks/callback with code and state

    Returns:
        authorization_url: URL to redirect user to
        state: CSRF protection token (must store and pass back in callback)
    """
    # Get QuickBooks OAuth credentials from environment
    client_id = os.environ.get("QB_CLIENT_ID", "")
    client_secret = os.environ.get("QB_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("QB_REDIRECT_URI", "")

    if not all([client_id, client_secret, redirect_uri]):
        logger.error("QuickBooks OAuth credentials not configured")
        raise HTTPException(
            status_code=500,
            detail="QuickBooks OAuth2 not configured. Set QB_CLIENT_ID, QB_CLIENT_SECRET, QB_REDIRECT_URI."
        )

    # Create OAuth client
    oauth_client = QuickBooksOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    # Generate authorization URL with state token
    auth_url, state = oauth_client.get_authorization_url()

    # Store state token for validation in callback (tied to CPA user)
    cpa_id = "default"  # In production: extract from auth context
    _qb_state_cache[state] = cpa_id

    logger.info(f"Generated QB authorization URL for state: {state[:8]}...")

    return QBAuthorizeResponse(
        authorization_url=auth_url,
        state=state,
    )


@integration_router.post(
    "/quickbooks/callback",
    summary="Handle QuickBooks OAuth2 callback",
    response_model=QBCallbackResponse,
    tags=["QuickBooks OAuth"],
)
async def handle_qb_callback(
    request: QBCallbackRequest,
    session: AsyncSession = Depends(get_async_session),
    _auth=Depends(require_internal_cpa_auth),
) -> QBCallbackResponse:
    """
    Handle QuickBooks OAuth2 authorization callback.

    Step 2 of OAuth2 flow:
    1. QB redirects user here with authorization code and state
    2. We validate state (CSRF protection)
    3. Exchange code for access/refresh tokens
    4. Store token in database

    Args:
        request: Callback request with code, state, realm_id from QB

    Returns:
        success response with token stored

    Raises:
        HTTPException: If state is invalid (CSRF attack) or token exchange fails
    """
    # Validate state token (CSRF protection)
    cpa_id = _qb_state_cache.pop(request.state, None)
    if not cpa_id:
        logger.warning(
            f"Invalid state token received. Possible CSRF attack: {request.state[:8]}..."
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid state token. Request may be forged."
        )

    # Get QuickBooks OAuth credentials
    client_id = os.environ.get("QB_CLIENT_ID", "")
    client_secret = os.environ.get("QB_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("QB_REDIRECT_URI", "")

    if not all([client_id, client_secret, redirect_uri]):
        raise HTTPException(
            status_code=500,
            detail="QuickBooks OAuth2 not configured"
        )

    # Create OAuth client
    oauth_client = QuickBooksOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    try:
        # Exchange authorization code for tokens
        token_response = await oauth_client.exchange_code_for_token(
            auth_code=request.code,
            state=request.state,
        )
    except ValueError as e:
        logger.error(f"State validation failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="State validation failed"
        )
    except Exception as e:
        logger.error(f"Token exchange failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Token exchange failed: {str(e)}"
        )

    # Extract tokens from response
    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_in = token_response.get("expires_in", 3600)
    token_type = token_response.get("token_type", "Bearer")
    scope = token_response.get("scope", QB_CONFIG.get_scopes_string())

    if not access_token or not refresh_token:
        logger.error("Token response missing required fields")
        raise HTTPException(
            status_code=400,
            detail="Invalid token response from QuickBooks"
        )

    # Store token in database
    try:
        # Create or update QB connection record
        connection = QuickBooksConnectionRecord(
            cpa_id=cpa_id,
            realm_id=request.realm_id,
            status="active",
        )
        session.add(connection)
        await session.flush()  # Get the connection ID

        # Create token record
        now = datetime.now(timezone.utc)
        token_record = QuickBooksTokenRecord(
            connection_id=connection.connection_id,
            access_token_encrypted=access_token,  # In production: encrypt
            refresh_token_encrypted=refresh_token,  # In production: encrypt
            token_type=token_type,
            scope=scope,
            realm_id=request.realm_id,
            issued_at=now,
            expires_at=now + timedelta(seconds=expires_in),
            is_valid=True,
        )
        session.add(token_record)
        await session.commit()

        logger.info(f"Stored QB token for realm_id: {request.realm_id}")

        return QBCallbackResponse(
            status="connected",
            message="QuickBooks token saved successfully",
        )

    except Exception as e:
        logger.error(f"Failed to store QB token: {str(e)}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save token: {str(e)}"
        )
