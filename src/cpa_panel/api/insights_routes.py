"""
CPA Panel Insights Routes

Endpoints for CPA-specific insights and review checklists.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

from .common import get_tax_return_adapter

logger = logging.getLogger(__name__)

insights_router = APIRouter(tags=["CPA Insights"])


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))
