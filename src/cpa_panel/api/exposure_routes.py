"""
CPA Panel Prospect Exposure Routes

Endpoints for prospect-safe tax discovery exposure.
Implements the Red Line contracts - no exact values leak to prospects.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from .common import get_tax_return_adapter, get_tenant_id

logger = logging.getLogger(__name__)

exposure_router = APIRouter(tags=["Prospect Exposure"])


# =============================================================================
# PROSPECT DISCOVERY ENDPOINT
# =============================================================================

@exposure_router.get("/prospect/{session_id}/discovery")
async def get_prospect_discovery(session_id: str, request: Request):
    """
    Get prospect-safe discovery summary.

    This is the PRIMARY endpoint for prospect-facing exposure.
    All values are transformed to directional/categorical - no exact amounts.

    RED LINE COMPLIANT:
    - Outcome: Bands (0-500, 500-2k, etc.), not exact amounts
    - Drivers: Categories and directions, not dollar values
    - Opportunities: Labels only, not specific recommendations
    - Scenarios: Better/Worse direction, not amounts
    """
    from cpa_panel.prospect_exposure import (
        OutcomeWrapper,
        ComplexityClassifier,
        DriverSanitizer,
        OpportunityLabeler,
        ScenarioDirection,
        ProspectExposureAssembler,
    )

    adapter = get_tax_return_adapter()
    tax_return = adapter.get_tax_return(session_id)

    if not tax_return:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # Get summary for transformation
        summary = adapter.get_summary(session_id)

        if not summary:
            raise HTTPException(status_code=404, detail="Tax data not available")

        # Build internal data for transformation
        refund_or_owed = summary.refund_or_owed
        confidence_pct = 70.0  # Default confidence

        # Build complexity flags
        complexity_flags = {
            'has_schedule_c': summary.has_schedule_c,
            'has_schedule_e': summary.has_schedule_e,
            'has_virtual_currency': summary.has_virtual_currency,
            'has_foreign_income': summary.has_foreign_accounts,
            'has_k1': False,  # Would need to check tax_return
            'is_multi_state': bool(summary.state),
            'is_high_income': summary.total_income > 200000,
            'is_itemizing': not summary.using_standard_deduction,
            'has_capital_gains': summary.capital_gains > 0,
        }

        # Build internal drivers from summary
        internal_drivers = []
        if summary.wages > 0:
            internal_drivers.append({
                'type': 'wages',
                'amount': summary.wages,
                'impact': summary.wages * 0.22,  # Rough marginal rate
            })
        if summary.business_income > 0:
            internal_drivers.append({
                'type': 'self_employment',
                'amount': summary.business_income,
                'impact': -summary.business_income * 0.15,  # SE tax estimate
            })
        if summary.total_payments > 0:
            internal_drivers.append({
                'type': 'withholding',
                'amount': summary.total_payments,
                'impact': summary.total_payments,
            })
        if summary.total_deductions > 0:
            internal_drivers.append({
                'type': 'standard_deduction' if summary.using_standard_deduction else 'itemized_deductions',
                'amount': summary.total_deductions,
                'impact': -summary.total_deductions * summary.marginal_rate,
            })

        # Build internal opportunities (simplified)
        internal_opportunities = []
        if summary.has_schedule_c and summary.business_income > 50000:
            internal_opportunities.append({
                'type': 'retirement_contribution',
                'potential_savings': min(summary.business_income * 0.25, 66000),
            })
        if not summary.has_schedule_c and summary.wages > 0:
            internal_opportunities.append({
                'type': 'ira',
                'potential_savings': 6500,
            })

        # Build scenarios (empty for now - would need scenario engine)
        internal_scenarios = []

        # Transform through red line compliant adapters
        outcome = OutcomeWrapper.transform(refund_or_owed, confidence_pct)
        complexity = ComplexityClassifier.transform(complexity_flags)
        drivers = DriverSanitizer.transform(internal_drivers)
        opportunities = OpportunityLabeler.transform(internal_opportunities)
        scenarios = ScenarioDirection.transform(internal_scenarios)

        # Assemble final summary
        discovery = ProspectExposureAssembler.compose(
            outcome=outcome,
            complexity=complexity,
            drivers=drivers,
            opportunities=opportunities,
            scenarios=scenarios,
        )

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "discovery": discovery.model_dump(),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prospect discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# INDIVIDUAL EXPOSURE ENDPOINTS
# =============================================================================

@exposure_router.get("/prospect/{session_id}/outcome")
async def get_prospect_outcome(session_id: str, request: Request):
    """
    Get prospect-safe outcome exposure only.

    Returns directional outcome (refund/owed/unclear) with amount band.
    """
    from cpa_panel.prospect_exposure import OutcomeWrapper

    adapter = get_tax_return_adapter()
    summary = adapter.get_summary(session_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        outcome = OutcomeWrapper.transform(
            refund_or_owed=summary.refund_or_owed,
            confidence_pct=70.0,
        )

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "outcome": outcome.model_dump(),
        })
    except Exception as e:
        logger.error(f"Error getting prospect outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@exposure_router.get("/prospect/{session_id}/complexity")
async def get_prospect_complexity(session_id: str, request: Request):
    """
    Get prospect-safe complexity assessment.

    Returns complexity level (simple/moderate/complex) with up to 3 reasons.
    """
    from cpa_panel.prospect_exposure import ComplexityClassifier

    adapter = get_tax_return_adapter()
    summary = adapter.get_summary(session_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        flags = {
            'has_schedule_c': summary.has_schedule_c,
            'has_schedule_e': summary.has_schedule_e,
            'has_virtual_currency': summary.has_virtual_currency,
            'has_foreign_income': summary.has_foreign_accounts,
            'is_high_income': summary.total_income > 200000,
            'is_itemizing': not summary.using_standard_deduction,
            'has_capital_gains': summary.capital_gains > 0,
        }

        complexity = ComplexityClassifier.transform(flags)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "complexity": complexity.model_dump(),
        })
    except Exception as e:
        logger.error(f"Error getting prospect complexity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@exposure_router.get("/prospect/{session_id}/drivers")
async def get_prospect_drivers(session_id: str, request: Request):
    """
    Get prospect-safe tax drivers.

    Returns top 3 drivers with category and direction only - no amounts.
    """
    from cpa_panel.prospect_exposure import DriverSanitizer

    adapter = get_tax_return_adapter()
    summary = adapter.get_summary(session_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # Build internal drivers
        internal_drivers = []
        if summary.wages > 0:
            internal_drivers.append({
                'type': 'wages',
                'impact': summary.wages * 0.22,
            })
        if summary.business_income > 0:
            internal_drivers.append({
                'type': 'self_employment',
                'impact': -summary.business_income * 0.15,
            })
        if summary.total_payments > 0:
            internal_drivers.append({
                'type': 'withholding',
                'impact': summary.total_payments,
            })
        if summary.total_credits > 0:
            internal_drivers.append({
                'type': 'child_tax_credit',
                'impact': summary.total_credits,
            })

        drivers = DriverSanitizer.transform(internal_drivers)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "drivers": drivers.model_dump(),
        })
    except Exception as e:
        logger.error(f"Error getting prospect drivers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# EXPOSURE CONTRACTS INFO
# =============================================================================

@exposure_router.get("/exposure/contracts")
async def get_exposure_contracts(request: Request):
    """
    Get information about exposure contracts and their constraints.

    Documents the red line enforcement for API consumers.
    """
    from cpa_panel.prospect_exposure import (
        OutcomeType,
        AmountBand,
        ConfidenceBand,
        ComplexityLevel,
        ComplexityReason,
        DriverCategory,
        DriverDirection,
        OpportunityCategory,
        ScenarioOutcomeShift,
    )

    try:
        contracts = {
            "outcome": {
                "description": "Directional outcome exposure - never exact amounts",
                "fields": {
                    "outcome_type": [t.value for t in OutcomeType],
                    "amount_band": [b.value for b in AmountBand],
                    "confidence_band": [c.value for c in ConfidenceBand],
                },
                "constraints": [
                    "Exact amounts are NEVER exposed",
                    "Amount bands are intentionally coarse",
                    "Confidence is qualitative, not percentage",
                ],
            },
            "complexity": {
                "description": "Complexity classification - max 3 reasons",
                "fields": {
                    "level": [l.value for l in ComplexityLevel],
                    "reasons": [r.value for r in ComplexityReason],
                },
                "constraints": [
                    "Maximum 3 complexity reasons",
                    "No scoring or percentages",
                ],
            },
            "drivers": {
                "description": "Tax drivers - categories and directions only",
                "fields": {
                    "category": [c.value for c in DriverCategory],
                    "direction": [d.value for d in DriverDirection],
                },
                "constraints": [
                    "Maximum 3 drivers",
                    "Unique ranks (1, 2, 3)",
                    "No dollar amounts",
                ],
            },
            "opportunities": {
                "description": "Opportunity labels - categories only",
                "fields": {
                    "category": [c.value for c in OpportunityCategory],
                },
                "constraints": [
                    "Maximum 3 visible",
                    "No specific recommendations",
                    "No potential savings amounts",
                ],
            },
            "scenarios": {
                "description": "Scenario comparisons - direction only",
                "fields": {
                    "outcome_shift": [s.value for s in ScenarioOutcomeShift],
                },
                "constraints": [
                    "Maximum 2 comparisons",
                    "No dollar deltas",
                    "Direction only (better/worse)",
                ],
            },
        }

        red_lines = [
            "1. No final/actionable tax positions",
            "2. No filing-ready outputs/forms",
            "3. No optimization logic/how-to mechanics",
            "4. No risk conclusions/audit exposure judgments",
            "5. No AI-generated advisory language",
            "6. No completeness/confidence signals (exact %)",
            "7. No CPA internal review artifacts",
            "8. No comparative CPA intelligence",
            "9. No irreversibility/urgency framing",
        ]

        return JSONResponse({
            "success": True,
            "contracts": contracts,
            "red_lines": red_lines,
        })
    except Exception as e:
        logger.error(f"Error getting exposure contracts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
