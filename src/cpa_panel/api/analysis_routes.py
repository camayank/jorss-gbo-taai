"""
CPA Panel Analysis Routes

Endpoints for delta analysis, tax drivers, and scenario comparison.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

from .common import get_tax_return_adapter

logger = logging.getLogger(__name__)

analysis_router = APIRouter(tags=["CPA Analysis"])


@analysis_router.post("/returns/{session_id}/delta")
async def calculate_delta(session_id: str, request: Request):
    """
    Calculate before/after delta for a proposed change.

    CPA AHA MOMENT: Instant impact visualization.

    Request body:
        - change_type: Type of change (income, deduction, credit, etc.)
        - field: Field being changed
        - old_value: Current value
        - new_value: Proposed new value
    """
    from cpa_panel.analysis import DeltaAnalyzer, ChangeType

    try:
        body = await request.json()
    except Exception as e:
        logger.debug(f"Failed to parse request body: {e}")
        body = {}

    change_type_str = body.get("change_type", "other")
    field = body.get("field", "")
    old_value = body.get("old_value", 0)
    new_value = body.get("new_value", 0)

    adapter = get_tax_return_adapter()
    tax_return = adapter.get_tax_return(session_id)

    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found for this session")

    try:
        change_type = ChangeType(change_type_str.lower())
    except ValueError:
        change_type = ChangeType.OTHER

    try:
        analyzer = DeltaAnalyzer()
        result = analyzer.analyze_change(
            session_id=session_id,
            tax_return=tax_return,
            change_type=change_type,
            field=field,
            old_value=old_value,
            new_value=new_value,
        )

        return JSONResponse({
            "success": True,
            **result.to_dict(),
        })
    except Exception as e:
        logger.error(f"Error calculating delta: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analysis_router.get("/returns/{session_id}/tax-drivers")
async def get_tax_drivers(session_id: str, request: Request):
    """
    Get 'What Drives Your Tax Outcome' breakdown.

    CLIENT AHA MOMENT: Clear visualization of tax factors.
    """
    from cpa_panel.analysis import TaxDriversAnalyzer

    adapter = get_tax_return_adapter()
    tax_return = adapter.get_tax_return(session_id)

    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found for this session")

    try:
        analyzer = TaxDriversAnalyzer()
        result = analyzer.analyze(session_id, tax_return)

        return JSONResponse({
            "success": True,
            **result.to_dict(),
        })
    except Exception as e:
        logger.error(f"Error analyzing tax drivers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analysis_router.post("/returns/{session_id}/compare-scenarios")
async def compare_scenarios(session_id: str, request: Request):
    """
    Compare multiple tax scenarios side-by-side.

    CLIENT AHA MOMENT: What-if analysis.

    Request body:
        - scenarios: List of scenarios to compare
          Each: {name: str, adjustments: [{field: str, value: float}]}
    """
    from cpa_panel.analysis import ScenarioComparator, Scenario

    try:
        body = await request.json()
    except Exception as e:
        logger.debug(f"Failed to parse request body: {e}")
        body = {}

    scenarios_data = body.get("scenarios", [])

    adapter = get_tax_return_adapter()
    tax_return = adapter.get_tax_return(session_id)

    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found for this session")

    try:
        scenarios = [Scenario.from_dict(s) for s in scenarios_data]
        comparator = ScenarioComparator()
        result = comparator.compare(session_id, tax_return, scenarios)

        return JSONResponse({
            "success": True,
            **result.to_dict(),
        })
    except Exception as e:
        logger.error(f"Error comparing scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@analysis_router.get("/returns/{session_id}/suggested-scenarios")
async def get_suggested_scenarios(session_id: str, request: Request):
    """Get common scenarios for comparison."""
    from cpa_panel.analysis import ScenarioComparator

    adapter = get_tax_return_adapter()
    tax_return = adapter.get_tax_return(session_id)

    if not tax_return:
        raise HTTPException(status_code=404, detail="Tax return not found for this session")

    try:
        comparator = ScenarioComparator()
        scenarios = comparator.create_common_scenarios(tax_return)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "scenarios": [s.to_dict() for s in scenarios],
            "count": len(scenarios),
        })
    except Exception as e:
        logger.error(f"Error getting scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))
