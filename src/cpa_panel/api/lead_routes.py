"""
CPA Panel Lead State Routes

Endpoints for lead state management and signal processing.
Implements the Lead State Engine for CPA lead qualification.

SECURITY: All lead endpoints validate tenant access to prevent
cross-tenant data leakage.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

from .common import get_tenant_id, get_lead_state_engine, log_and_raise_http_error
from security.tenant_isolation import (
    verify_lead_access,
    verify_tenant_access,
    TenantAccessLevel,
)
from security.middleware import (
    SIGNALS_RATE_LIMITER,
    CONTACT_RATE_LIMITER,
    ESTIMATES_RATE_LIMITER,
)

logger = logging.getLogger(__name__)

lead_router = APIRouter(tags=["Lead State"])

# Singleton engine instance for the application
_engine_instance = None


def get_engine():
    """Get or create the lead state engine singleton."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = get_lead_state_engine()
    return _engine_instance


# =============================================================================
# LEAD MANAGEMENT ENDPOINTS
# =============================================================================

@lead_router.get("/leads/{lead_id}", operation_id="get_lead_details")
async def get_lead_details(lead_id: str, request: Request):
    """
    Get lead details by ID.

    SECURITY: Validates tenant access before returning lead data.
    Returns current state, visibility, and signal history.
    """
    tenant_id = get_tenant_id(request)

    # Get user ID from auth context for audit logging
    auth_context = getattr(request.state, "auth", None)
    user_id = auth_context.user_id if auth_context else None

    # SECURITY: Verify lead belongs to requesting tenant
    verify_lead_access(
        lead_id=lead_id,
        tenant_id=tenant_id,
        user_id=user_id,
        required_level=TenantAccessLevel.READ,
    )

    try:
        engine = get_engine()
        lead = engine.get_lead(lead_id)

        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead not found: {lead_id}")

        return JSONResponse({
            "success": True,
            "lead": lead.to_dict(),
        })
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_http_error(e, category="db", context=f"getting lead {lead_id}")


@lead_router.post("/leads")
async def create_lead(request: Request):
    """
    Create or get a lead for a session.

    Request body:
        - lead_id: Lead identifier (required)
        - session_id: Session identifier (required)
        - tenant_id: Tenant identifier (optional, from header or body)
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    lead_id = body.get("lead_id")
    session_id = body.get("session_id")
    tenant_id = body.get("tenant_id") or get_tenant_id(request)

    if not lead_id:
        raise HTTPException(status_code=400, detail="lead_id is required")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        engine = get_engine()
        lead = engine.get_or_create_lead(
            lead_id=lead_id,
            session_id=session_id,
            tenant_id=tenant_id,
        )

        return JSONResponse({
            "success": True,
            "lead": lead.to_dict(),
            "created": len(lead.signals_received) == 0,
        })
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="creating lead")


# =============================================================================
# SIGNAL PROCESSING ENDPOINTS
# =============================================================================

@lead_router.post("/leads/{lead_id}/signals")
async def process_signal(lead_id: str, request: Request):
    """
    Process a behavioral signal for a lead.

    SECURITY: Rate limited to 30 signals/minute per client.
    This is the primary endpoint for recording prospect behavior
    and triggering state transitions.

    Request body:
        - signal_id: Signal identifier from catalog (required)
        - session_id: Session identifier (required for new leads)
        - metadata: Optional signal metadata
    """
    # Rate limiting: 30 signals per minute
    await SIGNALS_RATE_LIMITER.check(request)

    from cpa_panel.lead_state import TransitionError

    try:
        body = await request.json()
    except Exception:
        body = {}

    signal_id = body.get("signal_id")
    session_id = body.get("session_id")
    tenant_id = body.get("tenant_id") or get_tenant_id(request)
    metadata = body.get("metadata", {})

    if not signal_id:
        raise HTTPException(status_code=400, detail="signal_id is required")

    try:
        engine = get_engine()
        lead = engine.process_signal(
            lead_id=lead_id,
            signal_id=signal_id,
            session_id=session_id,
            tenant_id=tenant_id,
            metadata=metadata,
        )

        # Check if state changed
        state_changed = len(lead.transitions) > 0 and (
            lead.transitions[-1].trigger_signal.signal_id == signal_id
        )

        return JSONResponse({
            "success": True,
            "lead": lead.to_dict(),
            "signal_processed": signal_id,
            "state_changed": state_changed,
            "current_state": lead.current_state.name,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid signal or lead data provided.")
    except TransitionError as e:
        raise HTTPException(status_code=400, detail="Invalid state transition requested.")
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="processing signal")


@lead_router.post("/leads/{lead_id}/signals/batch")
async def process_signals_batch(lead_id: str, request: Request):
    """
    Process multiple signals for a lead in one request.

    Request body:
        - signals: List of signal_ids to process
        - session_id: Session identifier (required for new leads)
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    signals = body.get("signals", [])
    session_id = body.get("session_id")
    tenant_id = body.get("tenant_id") or get_tenant_id(request)

    if not signals:
        raise HTTPException(status_code=400, detail="signals list is required")

    try:
        engine = get_engine()
        processed = []
        errors = []

        for signal_id in signals:
            try:
                lead = engine.process_signal(
                    lead_id=lead_id,
                    signal_id=signal_id,
                    session_id=session_id,
                    tenant_id=tenant_id,
                )
                processed.append(signal_id)
            except Exception as e:
                errors.append({"signal_id": signal_id, "error": str(e)})

        lead = engine.get_lead(lead_id)

        return JSONResponse({
            "success": len(errors) == 0,
            "lead": lead.to_dict() if lead else None,
            "processed": processed,
            "errors": errors,
        })
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="processing batch signals")


# =============================================================================
# QUEUE ENDPOINTS (CPA VIEW)
# =============================================================================

@lead_router.get("/leads/queue/summary")
async def get_queue_summary(request: Request):
    """
    Get lead queue summary for CPA dashboard.

    Returns counts by state, visibility levels, and priority leads.
    """
    tenant_id = get_tenant_id(request)

    try:
        engine = get_engine()
        summary = engine.get_queue_summary(tenant_id)

        return JSONResponse({
            "success": True,
            "summary": summary,
            "tenant_id": tenant_id,
        })
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="getting queue summary")


@lead_router.get("/leads/queue/visible")
async def get_visible_leads(request: Request, limit: int = 50, offset: int = 0):
    """
    Get leads visible to CPA (EVALUATING and above).

    These are leads that warrant CPA attention but may not
    be monetizable yet.
    """
    tenant_id = get_tenant_id(request)

    try:
        engine = get_engine()
        leads = engine.get_visible_leads(tenant_id)

        # Apply pagination
        paginated = leads[offset:offset + limit]

        return JSONResponse({
            "success": True,
            "leads": [l.to_dict() for l in paginated],
            "total": len(leads),
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="getting visible leads")


@lead_router.get("/leads/queue/monetizable")
async def get_monetizable_leads(request: Request, limit: int = 50, offset: int = 0):
    """
    Get monetizable leads (ADVISORY_READY and above).

    These are leads ready for CPA engagement and conversion.
    """
    tenant_id = get_tenant_id(request)

    try:
        engine = get_engine()
        leads = engine.get_monetizable_leads(tenant_id)

        # Apply pagination
        paginated = leads[offset:offset + limit]

        return JSONResponse({
            "success": True,
            "leads": [l.to_dict() for l in paginated],
            "total": len(leads),
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="getting monetizable leads")


@lead_router.get("/leads/queue/priority")
async def get_priority_leads(request: Request):
    """
    Get priority leads (HIGH_LEVERAGE only).

    These are the highest-value leads that should be
    prioritized by CPAs.
    """
    tenant_id = get_tenant_id(request)

    try:
        engine = get_engine()
        leads = engine.get_priority_leads(tenant_id)

        return JSONResponse({
            "success": True,
            "leads": [l.to_dict() for l in leads],
            "count": len(leads),
        })
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="getting priority leads")


@lead_router.get("/leads/queue/state/{state}")
async def get_leads_by_state(state: str, request: Request, limit: int = 50, offset: int = 0):
    """
    Get leads by specific state.

    Args:
        state: Lead state (BROWSING, CURIOUS, EVALUATING, ADVISORY_READY, HIGH_LEVERAGE)
    """
    from cpa_panel.lead_state import LeadState

    try:
        valid_state = LeadState[state.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state '{state}'. Must be one of: {', '.join(s.name for s in LeadState)}"
        )

    tenant_id = get_tenant_id(request)

    try:
        engine = get_engine()
        leads = engine.get_leads_by_state(valid_state, tenant_id)

        # Apply pagination
        paginated = leads[offset:offset + limit]

        return JSONResponse({
            "success": True,
            "state": valid_state.name,
            "leads": [l.to_dict() for l in paginated],
            "total": len(leads),
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="getting leads by state")


# =============================================================================
# SIGNAL CATALOG ENDPOINT
# =============================================================================

@lead_router.get("/signals/catalog")
async def get_signal_catalog(request: Request):
    """
    Get the complete signal catalog.

    Returns all available signals with their types, strengths,
    and minimum state targets.
    """
    from cpa_panel.lead_state import SIGNAL_CATALOG

    try:
        catalog = []
        for signal_id, signal in SIGNAL_CATALOG.items():
            catalog.append({
                "signal_id": signal.signal_id,
                "name": signal.name,
                "type": signal.signal_type.value,
                "strength": signal.strength.name,
                "description": signal.description,
                "minimum_state_for": signal.minimum_state_for.name,
            })

        return JSONResponse({
            "success": True,
            "signals": catalog,
            "count": len(catalog),
        })
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="getting signal catalog")


# =============================================================================
# STATE INFO ENDPOINT
# =============================================================================

@lead_router.get("/states/info")
async def get_states_info(request: Request):
    """
    Get information about all lead states.

    Returns state properties, visibility levels, and transition rules.
    """
    from cpa_panel.lead_state import LeadState, VALID_TRANSITIONS
    from cpa_panel.lead_state.states import STATE_VISIBILITY

    try:
        states = []
        for state in LeadState:
            states.append({
                "name": state.name,
                "value": state.value,
                "display_name": state.display_name,
                "visibility": STATE_VISIBILITY[state].value,
                "is_monetizable": state.is_monetizable,
                "is_visible_to_cpa": state.is_visible_to_cpa,
                "is_priority": state.is_priority,
                "valid_transitions": [s.name for s in VALID_TRANSITIONS.get(state, set())],
            })

        return JSONResponse({
            "success": True,
            "states": states,
        })
    except Exception as e:
        log_and_raise_http_error(e, category="db", context="getting states info")
