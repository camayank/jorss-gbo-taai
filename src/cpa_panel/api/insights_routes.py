"""
CPA Panel Insights Routes

Endpoints for CPA-specific insights, review checklists, and
AI-enhanced recommendations.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from .common import get_tax_return_adapter

logger = logging.getLogger(__name__)

insights_router = APIRouter(tags=["CPA Insights"])


def get_ai_adapter():
    """Get the AI advisory adapter singleton."""
    from cpa_panel.adapters.ai_advisory_adapter import get_ai_advisory_adapter
    return get_ai_advisory_adapter()


@insights_router.get("/returns/{session_id}/insights")
async def get_cpa_insights(session_id: str, request: Request):
    """
    Get CPA-specific insights for a return.

    Returns review items, risk flags, compliance alerts,
    and optimization opportunities.
    """
    from cpa_panel.insights import CPAInsightsEngine

    adapter = get_tax_return_adapter()
    tax_return = adapter.get_tax_return(session_id)

    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found for this session")

    try:
        engine = CPAInsightsEngine()
        insights = engine.analyze(tax_return)

        if hasattr(engine, 'get_summary'):
            summary = engine.get_summary(insights)
            summary_dict = summary.to_dict() if hasattr(summary, 'to_dict') else {}
        else:
            summary_dict = {
                "total_insights": len(insights),
                "by_priority": {},
                "by_category": {},
            }

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "insights": [i.to_dict() for i in insights],
            "summary": summary_dict,
        })
    except Exception as e:
        logger.error(f"Error getting insights: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@insights_router.get("/returns/{session_id}/review-checklist")
async def get_review_checklist(session_id: str, request: Request):
    """Get CPA review checklist for a return."""
    from cpa_panel.insights import CPAInsightsEngine

    adapter = get_tax_return_adapter()
    tax_return = adapter.get_tax_return(session_id)

    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found for this session")

    try:
        engine = CPAInsightsEngine()
        checklist = engine.get_review_checklist(tax_return)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "checklist": [c.to_dict() for c in checklist],
            "total_items": len(checklist),
            "completed": sum(1 for c in checklist if c.completed),
        })
    except Exception as e:
        logger.error(f"Error getting checklist: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# =============================================================================
# AI-ENHANCED INSIGHTS
# =============================================================================

@insights_router.get("/session/{session_id}/insights/ai-enhanced")
async def get_ai_enhanced_insights(session_id: str, request: Request):
    """
    Get AI-enhanced tax recommendations.

    Provides personalized explanations, action steps, and Q&A
    for tax saving opportunities identified in the client's return.

    Returns:
        - AI-generated summary
        - Enhanced opportunities with explanations
        - Action steps and common questions
        - Total potential savings
    """
    try:
        adapter = get_ai_adapter()
        result = adapter.get_ai_enhanced_insights(session_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=404 if "not found" in result.get("error", "").lower() else 500,
                detail=result.get("error", "Failed to get insights"),
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI insights error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@insights_router.post("/session/{session_id}/insights/explain/{recommendation_id}")
async def explain_recommendation(
    session_id: str,
    recommendation_id: str,
    request: Request,
):
    """
    Get a plain-language explanation for a specific recommendation.

    Request body (optional):
        - education_level: "general" (default), "detailed", or "expert"

    Returns a client-friendly explanation of the tax opportunity,
    suitable for different audience levels.
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.debug(f"Failed to parse request body: {e}")
        body = {}

    education_level = body.get("education_level", "general")
    if education_level not in ("general", "detailed", "expert"):
        education_level = "general"

    try:
        adapter = get_ai_adapter()
        result = adapter.explain_recommendation(session_id, recommendation_id, education_level)

        if not result.get("success"):
            raise HTTPException(
                status_code=404 if "not found" in result.get("error", "").lower() else 500,
                detail=result.get("error", "Explanation failed"),
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Explain recommendation error: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@insights_router.get("/session/{session_id}/insights/client-summary")
async def get_client_summary(session_id: str, request: Request):
    """
    Generate a client-friendly summary of tax recommendations.

    Creates a summary suitable for client communication with:
    - Plain language overview
    - Top action items
    - Category breakdown
    - Important notes

    This summary can be used in engagement letters or
    client presentation materials.
    """
    try:
        adapter = get_ai_adapter()
        result = adapter.generate_client_summary(session_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=404 if "not found" in result.get("error", "").lower() else 500,
                detail=result.get("error", "Summary generation failed"),
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Client summary error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")
