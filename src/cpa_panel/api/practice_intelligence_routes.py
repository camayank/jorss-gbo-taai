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

from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from database.connection import get_async_session
except ImportError:
    async def _mock_session():
        yield None
    get_async_session = _mock_session
from ..practice_intelligence import (
    PracticeIntelligenceService,
    get_intelligence_service,
)
from .common import format_success_response, format_error_response, get_tenant_id

logger = logging.getLogger(__name__)


async def _get_firm_engagements(firm_id: str, session: AsyncSession) -> List[Dict[str, Any]]:
    """Fetch engagement data for a firm."""
    # Check if engagements table exists, otherwise use workflow data
    query = text("""
        SELECT
            COALESCE(engagement_type, 'tax_preparation') as engagement_type,
            COUNT(*) as count
        FROM (
            SELECT
                CASE
                    WHEN tr.return_data->>'engagement_type' IS NOT NULL
                        THEN tr.return_data->>'engagement_type'
                    WHEN tr.status IN ('advisory', 'planning')
                        THEN 'tax_advisory'
                    ELSE 'tax_preparation'
                END as engagement_type
            FROM tax_returns tr
            JOIN taxpayers tp ON tr.return_id = tp.return_id
            JOIN clients c ON tp.email = c.email
            JOIN users u ON c.preparer_id = u.user_id
            WHERE u.firm_id = :firm_id
        ) sub
        GROUP BY engagement_type
    """)
    try:
        result = await session.execute(query, {"firm_id": firm_id})
        rows = result.fetchall()
        engagements = []
        for row in rows:
            for _ in range(row[1]):
                engagements.append({"engagement_type": row[0]})
        return engagements
    except Exception as e:
        logger.debug(f"Could not fetch engagements: {e}")
        return []


async def _get_tax_returns_for_year(firm_id: str, tax_year: int, session: AsyncSession) -> List[Dict[str, Any]]:
    """Fetch tax return data for a specific year."""
    query = text("""
        SELECT
            tr.return_id,
            tr.tax_year,
            tr.filing_status,
            tr.line_9_total_income,
            tr.line_14_total_deductions,
            tr.line_24_total_tax_liability,
            tr.line_35a_refund,
            tr.line_37_amount_owed,
            tr.return_data
        FROM tax_returns tr
        JOIN taxpayers tp ON tr.return_id = tp.return_id
        JOIN clients c ON tp.email = c.email
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id AND tr.tax_year = :tax_year
    """)
    try:
        result = await session.execute(query, {"firm_id": firm_id, "tax_year": tax_year})
        rows = result.fetchall()
        returns = []
        for row in rows:
            return_data = row[8] if row[8] else {}
            if isinstance(return_data, str):
                import json
                return_data = json.loads(return_data)

            # Determine complexity tier based on income and deductions
            total_income = float(row[3] or 0)
            total_deductions = float(row[4] or 0)

            if total_income > 1000000:
                complexity_tier = 5  # Ultra Complex
            elif total_income > 500000:
                complexity_tier = 4  # High Net Worth
            elif total_income > 200000 or total_deductions > 50000:
                complexity_tier = 3  # Complex
            elif total_income > 75000:
                complexity_tier = 2  # Moderate
            else:
                complexity_tier = 1  # Simple

            returns.append({
                "return_id": str(row[0]),
                "tax_year": row[1],
                "filing_status": row[2],
                "total_income": total_income,
                "total_deductions": total_deductions,
                "tax_liability": float(row[5] or 0),
                "refund": float(row[6] or 0),
                "amount_owed": float(row[7] or 0),
                "complexity_tier": complexity_tier,
                **return_data
            })
        return returns
    except Exception as e:
        logger.debug(f"Could not fetch tax returns: {e}")
        return []

router = APIRouter(prefix="/intelligence", tags=["practice-intelligence"])


@router.get("/metrics")
async def get_portfolio_metrics(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
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
    current_year = datetime.now().year
    prior_year = current_year - 1

    # Fetch real data from database
    engagements = await _get_firm_engagements(tenant_id, session)
    current_year_returns = await _get_tax_returns_for_year(tenant_id, current_year, session)
    prior_year_returns = await _get_tax_returns_for_year(tenant_id, prior_year, session)

    service = get_intelligence_service()

    metrics = service.get_portfolio_metrics(
        tenant_id=tenant_id,
        engagements=engagements,
        current_year_returns=current_year_returns,
        prior_year_returns=prior_year_returns if prior_year_returns else None,
        current_year=current_year,
        prior_year=prior_year,
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
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Metric 1: Get advisory vs compliance mix.

    Shows distribution of engagement types:
    - Advisory: tax_advisory, tax_planning, audit_representation
    - Compliance: tax_preparation, amended_return
    """
    tenant_id = get_tenant_id(request)

    # Fetch real engagement data from database
    engagements = await _get_firm_engagements(tenant_id, session)

    service = get_intelligence_service()
    mix = service.calculate_advisory_mix(engagements)

    return format_success_response({
        "metric": "advisory_compliance_mix",
        "data": mix.to_dict(),
    })


@router.get("/complexity-distribution")
async def get_complexity_distribution(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
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
    current_year = datetime.now().year

    # Fetch real tax return data from database
    current_year_returns = await _get_tax_returns_for_year(tenant_id, current_year, session)

    service = get_intelligence_service()
    dist = service.calculate_complexity_distribution(current_year_returns)

    return format_success_response({
        "metric": "complexity_distribution",
        "data": dist.to_dict(),
    })


@router.get("/yoy-surface")
async def get_yoy_surface(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_year: Optional[int] = None,
    prior_year: Optional[int] = None,
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

    # Default to current and prior year if not specified
    if current_year is None:
        current_year = datetime.now().year
    if prior_year is None:
        prior_year = current_year - 1

    # Fetch real tax return data from database
    current_year_returns = await _get_tax_returns_for_year(tenant_id, current_year, session)
    prior_year_returns = await _get_tax_returns_for_year(tenant_id, prior_year, session)

    service = get_intelligence_service()
    surface = service.calculate_yoy_surface(
        current_year_returns=current_year_returns,
        prior_year_returns=prior_year_returns,
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
