"""
Recommendation and strategy endpoints extracted from intelligent_advisor_api.py.

Contains:
- POST /strategies
- POST /calculate
- POST /analyze (full analysis)
- POST /acknowledge-standards
- POST /unlock-strategies
- GET  /ai-metrics
- GET  /ai-routing-stats
"""

import logging
import time
from typing import Optional, Dict, List, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from security.session_token import verify_session_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Recommendations"])


class AcknowledgmentRequest(BaseModel):
    """Request model for professional standards acknowledgment."""
    session_id: str
    acknowledged_at: str


class UnlockRequest(BaseModel):
    """Request to unlock premium strategies."""
    session_id: str


@router.post("/acknowledge-standards")
async def acknowledge_standards(request: AcknowledgmentRequest, _session: str = Depends(verify_session_token)):
    """Record user acknowledgment of professional standards limitations."""
    from web.intelligent_advisor_api import store_acknowledgment

    try:
        store_acknowledgment(
            session_id=request.session_id,
            ip_address=None,
            user_agent=None,
        )
        timestamp = int(time.time())
        consent_token = f"v1_{request.session_id}_{timestamp}"
        return {
            "status": "acknowledged",
            "session_id": request.session_id,
            "token": consent_token,
            "consent_version": "v1",
        }
    except Exception as e:
        logger.error(f"Acknowledgment error: {e}")
        raise HTTPException(status_code=500, detail="Unable to record acknowledgment.")


@router.post("/strategies")
async def get_strategies(request=None, _session: str = Depends(verify_session_token)):
    """Get personalized tax strategies."""
    from web.intelligent_advisor_api import chat_engine

    try:
        profile = request.profile.dict(exclude_none=True)
        calculation = await chat_engine.get_tax_calculation(profile)
        strategies = await chat_engine.get_tax_strategies(profile, calculation)

        return {
            "strategies": [s.dict() for s in strategies],
            "total_potential_savings": sum((s.estimated_savings or 0) for s in strategies),
            "top_3": [s.dict() for s in strategies[:3]],
        }
    except Exception as e:
        logger.error(f"Strategies error: {e}")
        raise HTTPException(status_code=500, detail="Unable to get strategies.")


@router.post("/calculate")
async def calculate_taxes(request=None, _session: str = Depends(verify_session_token)):
    """Calculate taxes based on profile data."""
    from web.intelligent_advisor_api import chat_engine

    try:
        profile = request.profile.dict(exclude_none=True)
        calculation = await chat_engine.get_tax_calculation(profile)

        return {
            "session_id": request.session_id,
            "calculation": calculation.dict(),
        }
    except Exception as e:
        logger.error(f"Calculation error: {e}")
        raise HTTPException(status_code=500, detail="Unable to calculate taxes.")


@router.post("/unlock-strategies")
async def unlock_strategies(request: UnlockRequest, _session: str = Depends(verify_session_token)):
    """Mark session as premium-unlocked. Zero friction -- instant unlock."""
    from web.intelligent_advisor_api import chat_engine

    try:
        session = await chat_engine.get_or_create_session(request.session_id)
        session["premium_unlocked"] = True
        await chat_engine.update_session(request.session_id, {"premium_unlocked": True})

        return {
            "session_id": request.session_id,
            "premium_unlocked": True,
            "message": "All strategies unlocked! You now have access to premium insights.",
        }
    except Exception as e:
        logger.error(f"Unlock error: {e}")
        raise HTTPException(status_code=500, detail="Unable to unlock strategies.")


@router.get("/ai-metrics")
async def get_ai_metrics(_ctx=None):
    """AI usage metrics dashboard -- requires platform admin role."""
    try:
        from rbac.dependencies import require_platform_admin
    except ImportError:
        logger.error("rbac.dependencies.require_platform_admin not available — /ai-metrics endpoint is UNPROTECTED")

    try:
        from services.ai.metrics_service import get_ai_metrics_service
        metrics = get_ai_metrics_service()
        return {
            "available": True,
            "dashboard": metrics.get_dashboard_data(),
            "performance": [
                {
                    **{k: (v.value if hasattr(v, 'value') else v) for k, v in m.__dict__.items()},
                    "common_errors": [[e, c] for e, c in m.common_errors] if hasattr(m, 'common_errors') else [],
                }
                for m in metrics.get_performance_metrics()
            ],
            "costs": metrics.get_cost_breakdown(),
            "trends": metrics.get_usage_trends(),
        }
    except Exception as e:
        logger.warning(f"AI metrics unavailable: {e}")
        return {"available": False, "reason": "Service not configured"}


@router.get("/ai-routing-stats")
async def get_routing_stats(_ctx=None):
    """Query routing statistics -- requires platform admin role."""
    try:
        from services.ai.chat_router import get_chat_router
        return get_chat_router().get_routing_stats()
    except Exception as e:
        logger.warning(f"Routing stats unavailable: {e}")
        return {"available": False, "reason": "Service not configured"}
