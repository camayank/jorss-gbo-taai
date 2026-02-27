"""
CPA Panel Pipeline Routes

API endpoints for lead pipeline visualization, conversion metrics,
and practice growth analytics.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from .common import get_tenant_id

logger = logging.getLogger(__name__)

pipeline_router = APIRouter(tags=["Lead Pipeline"])


def get_pipeline_service():
    """Get the pipeline service singleton."""
    from cpa_panel.services.pipeline_service import get_pipeline_service
    return get_pipeline_service()


# =============================================================================
# PIPELINE VIEWS
# =============================================================================

@pipeline_router.get("/leads/pipeline")
async def get_pipeline(request: Request):
    """
    Get lead pipeline organized by state (Kanban view).

    Returns leads in each pipeline stage with:
    - Lead details
    - Estimated value
    - Time in stage
    - Visibility level
    """
    tenant_id = get_tenant_id(request)

    try:
        service = get_pipeline_service()
        result = service.get_pipeline_by_state(tenant_id)

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Get pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@pipeline_router.get("/leads/pipeline/metrics")
async def get_pipeline_metrics(request: Request):
    """
    Get comprehensive pipeline metrics.

    Returns:
    - Conversion metrics (rates, timing)
    - Velocity metrics (leads per day/week)
    - Bottleneck identification
    """
    tenant_id = get_tenant_id(request)

    try:
        service = get_pipeline_service()

        conversion = service.get_conversion_metrics(tenant_id)
        velocity = service.get_velocity_metrics(tenant_id)

        return JSONResponse({
            "success": True,
            "conversion": conversion.get("metrics", {}),
            "velocity": velocity.get("metrics", {}),
            "timestamp": conversion.get("timestamp"),
        })

    except Exception as e:
        logger.error(f"Get pipeline metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@pipeline_router.get("/leads/pipeline/conversion")
async def get_conversion_metrics(request: Request):
    """
    Get lead conversion metrics.

    Returns:
    - Total and converted lead counts
    - Conversion rate
    - Average conversion time
    - Stage-by-stage conversion rates
    """
    tenant_id = get_tenant_id(request)

    try:
        service = get_pipeline_service()
        result = service.get_conversion_metrics(tenant_id)

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Get conversion metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@pipeline_router.get("/leads/pipeline/velocity")
async def get_velocity_metrics(request: Request):
    """
    Get lead velocity metrics.

    Returns:
    - Leads per day/week
    - Average time to advisory ready
    - Average time to conversion
    - Bottleneck identification
    - Acceleration opportunities
    """
    tenant_id = get_tenant_id(request)

    try:
        service = get_pipeline_service()
        result = service.get_velocity_metrics(tenant_id)

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Get velocity metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PRIORITY QUEUE
# =============================================================================

@pipeline_router.get("/leads/priority-queue")
async def get_priority_queue(request: Request, limit: int = 20):
    """
    Get prioritized lead queue for CPA action.

    Returns leads ordered by priority score, which combines:
    - State (higher states = higher priority)
    - Engagement level (signal count)
    - Time in current state
    - Estimated value

    Each lead includes:
    - Priority score
    - Estimated value
    - Recommended action
    """
    tenant_id = get_tenant_id(request)

    try:
        service = get_pipeline_service()
        result = service.get_priority_queue(tenant_id, limit)

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Get priority queue error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# LEAD ACTIONS
# =============================================================================

@pipeline_router.post("/leads/{lead_id}/advance")
async def advance_lead(lead_id: str, request: Request):
    """
    Manually advance a lead to a target state.

    Request body:
        - target_state: Target state (CURIOUS, EVALUATING, ADVISORY_READY, HIGH_LEVERAGE)

    Used by CPAs to move leads forward in the pipeline
    based on manual qualification decisions.
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.debug(f"Failed to parse request body: {e}")
        body = {}

    target_state = body.get("target_state")
    if not target_state:
        raise HTTPException(status_code=400, detail="target_state is required")

    tenant_id = get_tenant_id(request)

    try:
        service = get_pipeline_service()
        result = service.advance_lead(lead_id, target_state, tenant_id)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Advance failed"))

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Advance lead error for {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
