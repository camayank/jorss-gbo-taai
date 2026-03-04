"""
Journey API — Client tax journey progress and next-step CTAs.

Endpoints:
    GET /api/journey/progress   — Current stage + completion
    GET /api/journey/next-step  — Context-aware next action
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/journey", tags=["Journey"])

_orchestrator_instance = None


def _get_orchestrator():
    global _orchestrator_instance
    if _orchestrator_instance is None:
        from services.journey_orchestrator import get_orchestrator
        _orchestrator_instance = get_orchestrator()
    return _orchestrator_instance


def _extract_user(request: Request):
    """Extract user_id and tenant_id from request headers."""
    user_id = request.headers.get("X-User-ID", "anonymous")
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    return user_id, tenant_id


@router.get("/progress")
async def get_journey_progress(request: Request):
    """Get current journey stage and progress for the authenticated user."""
    user_id, tenant_id = _extract_user(request)
    orchestrator = _get_orchestrator()
    progress = orchestrator.get_progress(user_id, tenant_id)
    return JSONResponse(progress)


@router.get("/next-step")
async def get_next_step(request: Request):
    """Get the context-aware next step CTA for the authenticated user."""
    user_id, tenant_id = _extract_user(request)
    orchestrator = _get_orchestrator()
    next_step = orchestrator.get_next_step(user_id, tenant_id)
    if next_step is None:
        return JSONResponse({"action": None, "message": "All steps complete!"})
    return JSONResponse(next_step)
