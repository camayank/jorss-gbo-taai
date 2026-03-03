"""
CPA Integration Status Routes

Manages third-party integration connections (QuickBooks, Xero, Google Calendar, etc.).
Stripe Connect is handled separately via payment_settings_routes.py.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth_dependencies import require_internal_cpa_auth

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
