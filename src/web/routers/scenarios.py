"""
Scenarios Router - What-If Tax Analysis API.

Provides endpoints for:
- Creating and managing tax scenarios
- Filing status comparisons
- Retirement contribution analysis
- Entity structure comparisons
- What-if calculations

Extracted from app.py for better modularity and maintainability.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from rbac.dependencies import require_auth

# Journey event bus integration
try:
    from events.event_bus import get_event_bus
    from events.journey_events import ScenarioCreated as ScenarioCreatedEvent
    _JOURNEY_EVENTS_AVAILABLE = True
except ImportError:
    _JOURNEY_EVENTS_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class ScenarioModificationRequest(BaseModel):
    """A single modification to apply in a scenario."""
    field_path: str = Field(..., description="Dot-notation path to field (e.g., 'taxpayer.filing_status')")
    new_value: Any = Field(..., description="New value to apply")
    description: Optional[str] = Field(None, description="Optional description of this modification")


class CreateScenarioRequest(BaseModel):
    """Request to create a new scenario.

    Accepts frontend field aliases for backward compatibility:
    - ``adjustments`` is accepted as an alias for ``modifications``
    - ``filing_status`` is mapped to ``scenario_type`` when the latter is absent
    """
    return_id: Optional[str] = Field(None, description="ID of the base tax return (optional for frontend compat)")
    name: str = Field("Untitled Scenario", description="Name for this scenario")
    scenario_type: Optional[str] = Field(None, description="Type: what_if, filing_status, retirement, entity_structure, etc.")
    modifications: Optional[List[ScenarioModificationRequest]] = Field(None, description="List of modifications to apply")
    # Frontend aliases
    adjustments: Optional[List[Dict[str, Any]]] = Field(None, description="Alias for modifications (frontend compat)")
    filing_status: Optional[str] = Field(None, description="Alias: mapped to scenario_type='filing_status' if scenario_type missing")
    description: Optional[str] = Field(None, description="Optional description")


class WhatIfScenarioRequest(BaseModel):
    """Request to create a quick what-if scenario."""
    return_id: Optional[str] = Field(None, description="ID of the base tax return (optional for frontend compat)")
    name: str = Field("What-If Scenario", description="Name for this scenario")
    modifications: Optional[dict] = Field(None, description="Dict of field_path -> new_value")


class CompareScenarioRequest(BaseModel):
    """Request to compare multiple scenarios."""
    scenario_ids: List[str] = Field(..., description="List of scenario IDs to compare")
    return_id: Optional[str] = Field(None, description="Optional return ID for context")


class FilingStatusScenariosRequest(BaseModel):
    """Request for filing status comparison scenarios."""
    return_id: Optional[str] = Field(None, description="ID of the base tax return (optional for frontend compat)")
    eligible_statuses: Optional[List[str]] = Field(None, description="Optional list of statuses to compare")


class RetirementScenariosRequest(BaseModel):
    """Request for retirement contribution scenarios."""
    return_id: Optional[str] = Field(None, description="ID of the base tax return (optional for frontend compat)")
    contribution_amounts: Optional[List[float]] = Field(None, description="Optional list of amounts to test")


class ApplyScenarioRequest(BaseModel):
    """Request to apply a scenario to its base return."""
    session_id: Optional[str] = Field(None, description="Session ID (optional, uses cookie if not provided)")


class EntityComparisonRequest(BaseModel):
    """Request for business entity structure comparison."""
    gross_revenue: float = Field(..., description="Total business gross revenue")
    business_expenses: float = Field(..., description="Total deductible business expenses")
    owner_salary: Optional[float] = Field(None, description="Optional fixed owner salary for S-Corp (calculated if not provided)")
    current_entity: str = Field("sole_proprietorship", description="Current entity type")
    filing_status: str = Field("single", description="Tax filing status")
    other_income: float = Field(0.0, description="Other taxable income outside the business")
    state: Optional[str] = Field(None, description="State of residence for state tax considerations")


# =============================================================================
# ROUTER SETUP
# =============================================================================

router = APIRouter(
    prefix="/api/scenarios",
    tags=["Scenarios"],
    responses={404: {"description": "Scenario not found"}},
)

# Scenario service singleton
_scenario_service = None


def _get_scenario_service():
    """Get or create the scenario service singleton."""
    global _scenario_service
    if _scenario_service is None:
        from services.scenario_service import ScenarioService
        _scenario_service = ScenarioService()
    return _scenario_service


# =============================================================================
# SCENARIO CRUD ENDPOINTS
# =============================================================================


@router.post("")
async def create_scenario(request: Request, request_body: CreateScenarioRequest, ctx=Depends(require_auth)):
    """
    Create a new tax scenario.

    Creates a scenario with specified modifications to compare against
    the base return. Use this for custom what-if analysis.

    Frontend compatibility: accepts ``adjustments`` as alias for
    ``modifications``, ``filing_status`` as fallback for ``scenario_type``,
    and allows ``return_id`` to be omitted.
    """
    from domain import ScenarioType

    # --- return_id guard ---
    if not request_body.return_id:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "return_id is required. Please load a tax return before creating scenarios.",
            },
        )

    service = _get_scenario_service()

    # --- Resolve scenario_type (accept filing_status alias) ---
    raw_type = request_body.scenario_type
    if not raw_type and request_body.filing_status:
        raw_type = "filing_status"
    raw_type = raw_type or "what_if"

    try:
        scenario_type = ScenarioType(raw_type)
    except ValueError:
        scenario_type = ScenarioType.WHAT_IF

    # --- Resolve modifications (accept adjustments alias) ---
    modifications: list = []
    if request_body.modifications:
        modifications = [
            {
                "field_path": mod.field_path,
                "new_value": mod.new_value,
                "description": mod.description,
            }
            for mod in request_body.modifications
        ]
    elif request_body.adjustments:
        # Frontend sends adjustments as list of dicts; normalise to
        # the field_path / new_value shape the service expects.
        for adj in request_body.adjustments:
            modifications.append({
                "field_path": adj.get("field_path") or adj.get("field", "unknown"),
                "new_value": adj.get("new_value") or adj.get("value"),
                "description": adj.get("description"),
            })

    try:
        scenario = service.create_scenario(
            return_id=request_body.return_id,
            name=request_body.name,
            scenario_type=scenario_type,
            modifications=modifications,
            description=request_body.description,
        )

        # Journey event: scenario created
        if _JOURNEY_EVENTS_AVAILABLE:
            try:
                bus = get_event_bus()
                user = getattr(request.state, "user", {}) or {}
                if bus:
                    bus.emit(ScenarioCreatedEvent(
                        scenario_id=str(scenario.scenario_id),
                        tenant_id=user.get("tenant_id", "default"),
                        user_id=user.get("id", "unknown"),
                        return_id=request_body.return_id,
                        name=scenario.name,
                    ))
            except Exception:
                pass

        return JSONResponse({
            "success": True,
            "scenario_id": str(scenario.scenario_id),
            "name": scenario.name,
            "type": scenario.scenario_type.value,
            "status": scenario.status.value,
            "modifications_count": len(scenario.modifications),
            "created_at": scenario.created_at.isoformat(),
        })

    except ValueError as e:
        logger.warning(f"Invalid scenario creation request: {e}")
        raise HTTPException(status_code=404, detail="Tax return not found. Please ensure the return exists.")
    except Exception as e:
        logger.exception(f"Error creating scenario: {e}")
        raise HTTPException(status_code=500, detail="Failed to create scenario. Please try again.")


@router.get("")
async def list_scenarios(request: Request, return_id: Optional[str] = None, ctx=Depends(require_auth)):
    """
    List all scenarios for a tax return.

    Returns summary of all scenarios created for the specified return.
    If no return_id is provided, returns an empty list (frontend compat).
    """
    if not return_id:
        return JSONResponse({
            "return_id": None,
            "count": 0,
            "scenarios": [],
            "message": "No return_id provided. Load a tax return first to see scenarios.",
        })

    service = _get_scenario_service()

    scenarios = service.get_scenarios_for_return(return_id)

    return JSONResponse({
        "return_id": return_id,
        "count": len(scenarios),
        "scenarios": [
            {
                "scenario_id": str(s.scenario_id),
                "name": s.name,
                "type": s.scenario_type.value,
                "status": s.status.value,
                "is_recommended": s.is_recommended,
                "total_tax": s.result.total_tax if s.result else None,
                "savings": s.result.savings if s.result else None,
                "created_at": s.created_at.isoformat(),
            }
            for s in scenarios
        ]
    })


@router.get("/{scenario_id}")
async def get_scenario(request: Request, scenario_id: str, ctx=Depends(require_auth)):
    """
    Get detailed information about a specific scenario.

    Returns full scenario details including modifications and results.
    """
    service = _get_scenario_service()

    scenario = service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")

    result_data = None
    if scenario.result:
        result_data = {
            "total_tax": scenario.result.total_tax,
            "federal_tax": scenario.result.federal_tax,
            "effective_rate": scenario.result.effective_rate,
            "marginal_rate": scenario.result.marginal_rate,
            "base_tax": scenario.result.base_tax,
            "savings": scenario.result.savings,
            "savings_percent": scenario.result.savings_percent,
            "taxable_income": scenario.result.taxable_income,
            "total_deductions": scenario.result.total_deductions,
            "total_credits": scenario.result.total_credits,
            "breakdown": scenario.result.breakdown,
        }

    return JSONResponse({
        "scenario_id": str(scenario.scenario_id),
        "return_id": str(scenario.return_id),
        "name": scenario.name,
        "description": scenario.description,
        "type": scenario.scenario_type.value,
        "status": scenario.status.value,
        "is_recommended": scenario.is_recommended,
        "recommendation_reason": scenario.recommendation_reason,
        "created_at": scenario.created_at.isoformat(),
        "calculated_at": scenario.calculated_at.isoformat() if scenario.calculated_at else None,
        "modifications": [
            {
                "field_path": m.field_path,
                "original_value": m.original_value,
                "new_value": m.new_value,
                "description": m.description,
            }
            for m in scenario.modifications
        ],
        "result": result_data,
    })


@router.post("/{scenario_id}/calculate")
async def calculate_scenario(request: Request, scenario_id: str, ctx=Depends(require_auth)):
    """
    Calculate tax results for a scenario.

    Applies the scenario's modifications and computes the tax liability,
    comparing against the base return to determine savings.
    """
    service = _get_scenario_service()

    try:
        scenario = service.calculate_scenario(scenario_id)

        return JSONResponse({
            "success": True,
            "scenario_id": str(scenario.scenario_id),
            "name": scenario.name,
            "status": scenario.status.value,
            "result": {
                "total_tax": scenario.result.total_tax,
                "federal_tax": scenario.result.federal_tax,
                "effective_rate": scenario.result.effective_rate,
                "marginal_rate": scenario.result.marginal_rate,
                "base_tax": scenario.result.base_tax,
                "savings": scenario.result.savings,
                "savings_percent": scenario.result.savings_percent,
                "taxable_income": scenario.result.taxable_income,
                "total_deductions": scenario.result.total_deductions,
                "total_credits": scenario.result.total_credits,
                "breakdown": scenario.result.breakdown,
            }
        })

    except ValueError as e:
        logger.warning(f"Scenario calculation validation error: {e}")
        raise HTTPException(status_code=404, detail="Scenario or tax return not found.")
    except Exception as e:
        logger.exception(f"Error calculating scenario: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate scenario. Please try again.")


@router.delete("/{scenario_id}")
async def delete_scenario(request: Request, scenario_id: str, ctx=Depends(require_auth)):
    """
    Delete a scenario.

    Permanently removes the scenario. This action cannot be undone.
    """
    service = _get_scenario_service()

    success = service.delete_scenario(scenario_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")

    return JSONResponse({
        "success": True,
        "message": f"Scenario {scenario_id} deleted",
    })


# =============================================================================
# SCENARIO COMPARISON ENDPOINTS
# =============================================================================


@router.post("/compare")
async def compare_scenarios(request: Request, request_body: CompareScenarioRequest, ctx=Depends(require_auth)):
    """
    Compare multiple scenarios to find the best option.

    Calculates all scenarios if needed, then compares them to determine
    which provides the lowest tax liability.
    """
    service = _get_scenario_service()

    if len(request_body.scenario_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 scenarios required for comparison")

    try:
        comparison = service.compare_scenarios(
            scenario_ids=request_body.scenario_ids,
            return_id=request_body.return_id,
        )

        return JSONResponse(comparison)

    except ValueError as e:
        logger.warning(f"Scenario comparison validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid scenario parameters")
    except Exception as e:
        logger.exception(f"Error comparing scenarios: {e}")
        raise HTTPException(status_code=500, detail="Failed to compare scenarios. Please try again.")


@router.post("/filing-status")
async def generate_filing_status_scenarios(request: Request, request_body: FilingStatusScenariosRequest, ctx=Depends(require_auth)):
    """
    Generate and compare filing status scenarios.

    Automatically creates scenarios for each eligible filing status and
    calculates the tax liability for each. Returns comparison with
    recommendation for the optimal status.
    """
    if not request_body.return_id:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "return_id is required. Please load a tax return before comparing filing statuses.",
            },
        )

    service = _get_scenario_service()

    try:
        scenarios = service.get_filing_status_scenarios(
            return_id=request_body.return_id,
            eligible_statuses=request_body.eligible_statuses,
        )

        # Find the best option
        calculated = [s for s in scenarios if s.result]
        best = None
        if calculated:
            best = min(calculated, key=lambda s: s.result.total_tax)
            best.mark_as_recommended(f"Lowest tax liability: ${best.result.total_tax:,.2f}")

        return JSONResponse({
            "return_id": request_body.return_id,
            "count": len(scenarios),
            "scenarios": [
                {
                    "scenario_id": str(s.scenario_id),
                    "name": s.name,
                    "filing_status": s.modifications[0].new_value if s.modifications else None,
                    "is_recommended": s.is_recommended,
                    "recommendation_reason": s.recommendation_reason,
                    "result": {
                        "total_tax": s.result.total_tax,
                        "effective_rate": s.result.effective_rate,
                        "savings": s.result.savings,
                        "savings_percent": s.result.savings_percent,
                    } if s.result else None,
                }
                for s in scenarios
            ],
            "recommendation": {
                "scenario_id": str(best.scenario_id),
                "filing_status": best.modifications[0].new_value if best.modifications else None,
                "total_tax": best.result.total_tax,
                "savings": best.result.savings,
            } if best else None,
        })

    except ValueError as e:
        logger.warning(f"Filing status scenarios validation error: {e}")
        raise HTTPException(status_code=404, detail="Tax return not found for filing status comparison.")
    except Exception as e:
        logger.exception(f"Error generating filing status scenarios: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate filing status scenarios. Please try again.")


@router.post("/retirement")
async def generate_retirement_scenarios(request: Request, request_body: RetirementScenariosRequest, ctx=Depends(require_auth)):
    """
    Generate retirement contribution comparison scenarios.

    Creates scenarios for different 401k/IRA contribution levels to
    show the tax impact of increasing retirement savings.
    """
    if not request_body.return_id:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "return_id is required. Please load a tax return before analyzing retirement scenarios.",
            },
        )

    service = _get_scenario_service()

    try:
        scenarios = service.get_retirement_scenarios(
            return_id=request_body.return_id,
            contribution_amounts=request_body.contribution_amounts,
        )

        # Find the best option (lowest tax)
        calculated = [s for s in scenarios if s.result]
        best = min(calculated, key=lambda s: s.result.total_tax) if calculated else None

        return JSONResponse({
            "return_id": request_body.return_id,
            "count": len(scenarios),
            "scenarios": [
                {
                    "scenario_id": str(s.scenario_id),
                    "name": s.name,
                    "contribution_amount": s.modifications[0].new_value if s.modifications else 0,
                    "result": {
                        "total_tax": s.result.total_tax,
                        "effective_rate": s.result.effective_rate,
                        "savings": s.result.savings,
                        "savings_percent": s.result.savings_percent,
                    } if s.result else None,
                }
                for s in scenarios
            ],
            "recommendation": {
                "scenario_id": str(best.scenario_id),
                "contribution_amount": best.modifications[0].new_value if best.modifications else 0,
                "total_tax": best.result.total_tax,
                "max_savings": best.result.savings,
            } if best else None,
        })

    except ValueError as e:
        logger.warning(f"Retirement scenarios validation error: {e}")
        raise HTTPException(status_code=404, detail="Tax return not found for retirement scenario analysis.")
    except Exception as e:
        logger.exception(f"Error generating retirement scenarios: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate retirement scenarios. Please try again.")


@router.post("/what-if")
async def create_what_if_scenario(request: Request, request_body: WhatIfScenarioRequest, ctx=Depends(require_auth)):
    """
    Create a quick what-if scenario with simple field modifications.

    Simplified endpoint for ad-hoc what-if analysis. Pass a dict of
    field_path -> new_value and get immediate tax impact analysis.
    """
    if not request_body.return_id:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "return_id is required. Please load a tax return before running what-if analysis.",
            },
        )

    service = _get_scenario_service()

    try:
        scenario = service.create_what_if_scenario(
            return_id=request_body.return_id,
            name=request_body.name,
            modifications=request_body.modifications or {},
        )

        # Calculate immediately
        scenario = service.calculate_scenario(str(scenario.scenario_id))

        return JSONResponse({
            "success": True,
            "scenario_id": str(scenario.scenario_id),
            "name": scenario.name,
            "modifications": [
                {
                    "field_path": m.field_path,
                    "original_value": m.original_value,
                    "new_value": m.new_value,
                }
                for m in scenario.modifications
            ],
            "result": {
                "total_tax": scenario.result.total_tax,
                "base_tax": scenario.result.base_tax,
                "savings": scenario.result.savings,
                "savings_percent": scenario.result.savings_percent,
                "effective_rate": scenario.result.effective_rate,
                "marginal_rate": scenario.result.marginal_rate,
            }
        })

    except ValueError as e:
        logger.warning(f"What-if scenario validation error: {e}")
        raise HTTPException(status_code=404, detail="Tax return not found for what-if analysis.")
    except Exception as e:
        logger.exception(f"Error creating what-if scenario: {e}")
        raise HTTPException(status_code=500, detail="Failed to create what-if scenario. Please try again.")


@router.post("/{scenario_id}/apply")
async def apply_scenario(request: Request, scenario_id: str, request_body: ApplyScenarioRequest, ctx=Depends(require_auth)):
    """
    Apply a scenario's modifications to the base return.

    This permanently updates the tax return with the scenario's changes.
    Use this when the user decides to adopt a recommended scenario.
    """
    service = _get_scenario_service()

    # Get session ID from request body or cookie
    session_id = request_body.session_id or request.cookies.get("tax_session_id") or ""

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID required")

    try:
        result = service.apply_scenario(
            scenario_id=scenario_id,
            session_id=session_id,
        )

        return JSONResponse({
            "success": True,
            "scenario_id": scenario_id,
            "message": "Scenario applied to tax return",
            "updated_return": result,
        })

    except ValueError as e:
        logger.warning(f"Apply scenario validation error: {e}")
        raise HTTPException(status_code=404, detail="Scenario not found or cannot be applied.")
    except Exception as e:
        logger.exception(f"Error applying scenario: {e}")
        raise HTTPException(status_code=500, detail="Failed to apply scenario. Please try again.")
