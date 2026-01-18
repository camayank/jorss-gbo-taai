"""
Practice Intelligence API Routes

READ-ONLY portfolio analytics endpoints.

SCOPE BOUNDARIES (ENFORCED - 3 METRICS ONLY):
1. Advisory vs Compliance Mix
2. Complexity Tier Distribution
3. YoY Value Surface

NOT IN SCOPE (USE EXTERNAL PMS):
- Time tracking
- Staff productivity
- Revenue per staff
- Utilization metrics
- Billable hours
- Any practice management features
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List, Optional
import logging

from ..practice_intelligence import (
    PracticeIntelligenceService,
    get_intelligence_service,
)
from .common import format_success_response, format_error_response, get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["practice-intelligence"])


@router.get("/metrics")
async def get_portfolio_metrics(
    request: Request,
) -> Dict[str, Any]:
    """
    Get portfolio metrics for the tenant.

    Returns ONLY the 3 allowed metrics:
    1. Advisory vs Compliance Mix
    2. Complexity Tier Distribution
    3. YoY Value Surface

    NOTE: This is READ-ONLY analytics. For practice management
    features, integrate with Karbon, Canopy, or Jetpack.
    """
    tenant_id = get_tenant_id(request)

    # In production, these would come from the database
    # For now, return structure with empty data
    service = get_intelligence_service()

    # Placeholder data - would be populated from actual tenant data
    metrics = service.get_portfolio_metrics(
        tenant_id=tenant_id,
        engagements=[],
        current_year_returns=[],
        prior_year_returns=None,
        current_year=2024,
        prior_year=2023,
    )

    return format_success_response({
        "metrics": metrics.to_dict(),
        "scope_notice": (
            "Practice Intelligence provides portfolio analytics only. "
            "Time tracking, staff productivity, and revenue metrics "
            "are NOT in scope. Integrate with your PMS for those features."
        ),
    })


@router.post("/metrics/calculate")
async def calculate_portfolio_metrics(
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculate portfolio metrics from provided data.

    Request body:
    - engagements: List of engagement records with 'engagement_type'
    - current_year_returns: List of return records for current year
    - prior_year_returns: Optional list for prior year (for YoY)
    - current_year: Tax year (default: 2024)
    - prior_year: Prior tax year (default: 2023)

    Returns ONLY:
    1. Advisory vs Compliance Mix
    2. Complexity Tier Distribution
    3. YoY Value Surface
    """
    tenant_id = get_tenant_id(request)

    engagements = body.get("engagements", [])
    current_year_returns = body.get("current_year_returns", [])
    prior_year_returns = body.get("prior_year_returns")
    current_year = body.get("current_year", 2024)
    prior_year = body.get("prior_year", 2023)

    service = get_intelligence_service()

    metrics = service.get_portfolio_metrics(
        tenant_id=tenant_id,
        engagements=engagements,
        current_year_returns=current_year_returns,
        prior_year_returns=prior_year_returns,
        current_year=current_year,
        prior_year=prior_year,
    )

    return format_success_response({
        "metrics": metrics.to_dict(),
    })


@router.get("/advisory-mix")
async def get_advisory_mix(
    request: Request,
) -> Dict[str, Any]:
    """
    Metric 1: Get advisory vs compliance mix.

    Shows distribution of engagement types:
    - Advisory: tax_advisory, tax_planning, audit_representation
    - Compliance: tax_preparation, amended_return
    """
    tenant_id = get_tenant_id(request)

    # In production, would fetch from database
    service = get_intelligence_service()
    mix = service.calculate_advisory_mix([])

    return format_success_response({
        "metric": "advisory_compliance_mix",
        "data": mix.to_dict(),
    })


@router.get("/complexity-distribution")
async def get_complexity_distribution(
    request: Request,
) -> Dict[str, Any]:
    """
    Metric 2: Get complexity tier distribution.

    Shows count of returns by complexity:
    - Tier 1: Simple
    - Tier 2: Moderate
    - Tier 3: Complex
    - Tier 4: High Net Worth
    - Tier 5: Ultra Complex
    """
    tenant_id = get_tenant_id(request)

    # In production, would fetch from database
    service = get_intelligence_service()
    dist = service.calculate_complexity_distribution([])

    return format_success_response({
        "metric": "complexity_distribution",
        "data": dist.to_dict(),
    })


@router.get("/yoy-surface")
async def get_yoy_surface(
    request: Request,
    current_year: int = 2024,
    prior_year: int = 2023,
) -> Dict[str, Any]:
    """
    Metric 3: Get year-over-year value surface.

    Compares TAX METRICS between years:
    - Average refunds
    - Average tax liability
    - Average deductions
    - Return volume

    NOTE: This is NOT revenue tracking.
    """
    tenant_id = get_tenant_id(request)

    # In production, would fetch from database
    service = get_intelligence_service()
    surface = service.calculate_yoy_surface(
        current_year_returns=[],
        prior_year_returns=[],
        current_year=current_year,
        prior_year=prior_year,
    )

    return format_success_response({
        "metric": "yoy_value_surface",
        "data": surface.to_dict(),
    })


@router.get("/scope")
async def get_scope_boundaries() -> Dict[str, Any]:
    """
    Returns the scope boundaries for Practice Intelligence.

    This endpoint explicitly documents what IS and IS NOT
    in scope for this module.
    """
    return format_success_response({
        "module": "Practice Intelligence Dashboard",
        "in_scope": {
            "metrics": [
                {
                    "name": "Advisory vs Compliance Mix",
                    "description": "Distribution of engagement types (advisory vs compliance)",
                    "endpoint": "/cpa/intelligence/advisory-mix",
                },
                {
                    "name": "Complexity Tier Distribution",
                    "description": "Count of returns by complexity tier",
                    "endpoint": "/cpa/intelligence/complexity-distribution",
                },
                {
                    "name": "YoY Value Surface",
                    "description": "Year-over-year tax metric comparisons",
                    "endpoint": "/cpa/intelligence/yoy-surface",
                },
            ],
            "purpose": "Portfolio analytics for CPA firms",
            "data_type": "READ-ONLY aggregated statistics",
        },
        "out_of_scope": {
            "features": [
                "Time tracking",
                "Staff productivity metrics",
                "Revenue per staff",
                "Utilization rates",
                "Billable hours tracking",
                "Realization rates",
                "WIP tracking",
                "Staff performance metrics",
                "Capacity planning",
            ],
            "reason": "These are Practice Management System (PMS) features",
            "alternatives": [
                "Karbon - https://karbonhq.com",
                "Canopy - https://canopytax.com",
                "Jetpack Workflow - https://jetpackworkflow.com",
            ],
        },
        "boundary_notice": (
            "This boundary is LOCKED. Do not expand this module to include "
            "practice management features. This platform is a CPA Intelligence "
            "& Advisory Amplifier, not a Practice Management System."
        ),
    })
