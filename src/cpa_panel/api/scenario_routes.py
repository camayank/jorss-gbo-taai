"""
CPA Panel Scenario Routes

API endpoints for what-if scenario analysis, enabling CPAs to
show clients the tax impact of different financial decisions.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

scenario_router = APIRouter(tags=["Scenario Analysis"])


def get_scenario_service():
    """Get the scenario service singleton."""
    from cpa_panel.services.scenario_service import get_scenario_service
    return get_scenario_service()


# =============================================================================
# SCENARIO COMPARISON
# =============================================================================

@scenario_router.post("/session/{session_id}/scenarios/compare")
async def compare_scenarios(session_id: str, request: Request):
    """
    Compare multiple tax scenarios against the base case.

    Request body:
        - scenarios: List of scenario configurations
            Each can be:
            - {"template_id": "max_401k", "values": {"contribution_amount": 20000}}
            - {"name": "Custom", "adjustments": [{"field": "income", "value": 10000}]}

    Returns:
        Side-by-side comparison of all scenarios with:
        - Tax liability for each
        - Delta from base case
        - Best/worst scenario identification
        - Max potential savings
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    scenarios = body.get("scenarios", [])
    if not scenarios:
        raise HTTPException(status_code=400, detail="scenarios list is required")

    try:
        service = get_scenario_service()
        result = service.compare_scenarios(session_id, scenarios)

        if not result.get("success"):
            raise HTTPException(
                status_code=400 if "not found" in result.get("error", "") else 500,
                detail=result.get("error", "Comparison failed"),
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scenario comparison error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@scenario_router.post("/session/{session_id}/scenarios/compare-templates")
async def compare_from_templates(session_id: str, request: Request):
    """
    Compare scenarios using pre-built templates.

    Request body:
        - template_ids: List of template IDs to compare (max 4)
        - custom_values: Optional {template_id: {variable: value}} overrides

    Example:
        {
            "template_ids": ["max_401k", "max_ira", "charitable_bunching"],
            "custom_values": {
                "max_401k": {"contribution_amount": 15000}
            }
        }
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    template_ids = body.get("template_ids", [])
    custom_values = body.get("custom_values", {})

    if not template_ids:
        raise HTTPException(status_code=400, detail="template_ids list is required")

    try:
        service = get_scenario_service()
        result = service.compare_from_templates(session_id, template_ids, custom_values)

        if not result.get("success"):
            raise HTTPException(
                status_code=400 if "not found" in result.get("error", "") else 500,
                detail=result.get("error", "Comparison failed"),
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template comparison error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# TEMPLATES
# =============================================================================

@scenario_router.get("/session/{session_id}/scenarios/templates")
async def get_scenario_templates(session_id: str, request: Request, category: Optional[str] = None):
    """
    Get available scenario templates.

    Query params:
        - category: Filter by category (retirement, charitable, business, etc.)

    Returns list of templates with:
        - Template ID
        - Name and description
        - Category
        - Adjustments that will be made
        - Variables that can be customized
        - Default values
        - Usage notes
    """
    try:
        service = get_scenario_service()
        templates = service.get_templates(category)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "category_filter": category,
            "templates": templates,
            "total": len(templates),
        })

    except Exception as e:
        logger.error(f"Get templates error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@scenario_router.get("/scenarios/categories")
async def get_template_categories(request: Request):
    """
    Get list of template categories with counts.

    Returns:
        - Category names
        - Number of templates per category
        - Template IDs in each category
    """
    try:
        service = get_scenario_service()
        categories = service.get_template_categories()

        return JSONResponse({
            "success": True,
            "categories": categories,
        })

    except Exception as e:
        logger.error(f"Get categories error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# QUICK COMPARE
# =============================================================================

@scenario_router.post("/session/{session_id}/scenarios/quick-compare")
async def quick_compare(session_id: str, request: Request):
    """
    Quick tax impact calculation using marginal rate approximation.

    Request body:
        - adjustments: List of {field, value} adjustments
            Fields: income, deduction, credit, 401k_contribution, ira_contribution

    Example:
        {
            "adjustments": [
                {"field": "401k_contribution", "value": 10000},
                {"field": "deduction", "value": 5000}
            ]
        }

    Returns quick estimate without full tax recalculation.
    Useful for real-time what-if during client conversations.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    adjustments = body.get("adjustments", [])
    if not adjustments:
        raise HTTPException(status_code=400, detail="adjustments list is required")

    try:
        service = get_scenario_service()
        result = service.quick_compare(session_id, adjustments)

        if not result.get("success"):
            raise HTTPException(
                status_code=400 if "not found" in result.get("error", "") else 500,
                detail=result.get("error", "Quick compare failed"),
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quick compare error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SUGGESTED SCENARIOS
# =============================================================================

@scenario_router.get("/session/{session_id}/scenarios/suggested")
async def get_suggested_scenarios(session_id: str, request: Request):
    """
    Get suggested scenarios based on client's tax profile.

    Analyzes the client's tax return and suggests relevant
    what-if scenarios to explore.

    Returns:
        - Suggested scenarios tailored to client
        - Pre-populated with relevant values
    """
    try:
        service = get_scenario_service()
        result = service.get_common_scenarios(session_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=400 if "not found" in result.get("error", "") else 500,
                detail=result.get("error", "Failed to get suggestions"),
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get suggested scenarios error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
