"""
Funnel Orchestration API Routes

Provides endpoints to trigger the complete lead funnel:
1. Process qualified lead (CONVERT + MATCH + FACILITATE)
2. Generate and deliver advisory report
3. Auto-assign lead to CPA
4. Calculate platform fees
5. Manage CPA capacity for auto-assignment
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from .auth_dependencies import require_internal_cpa_auth

logger = logging.getLogger(__name__)

funnel_router = APIRouter(
    prefix="/funnel",
    tags=["Funnel Orchestration"],
    dependencies=[Depends(require_internal_cpa_auth)],
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ProcessLeadRequest(BaseModel):
    """Request to process a qualified lead through the funnel."""
    lead_id: str = Field(..., description="Lead identifier")
    session_id: str = Field(..., description="Tax session ID with answers")
    lead_email: str = Field(..., description="Lead's email address")
    lead_name: str = Field(..., description="Lead's name")
    cpa_pool: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Optional list of CPAs to consider for assignment"
    )
    brand_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional branding configuration"
    )


class FunnelResultResponse(BaseModel):
    """Response from funnel processing."""
    success: bool
    lead_id: str
    session_id: str
    report_generated: bool
    pdf_generated: bool
    pdf_path: Optional[str]
    lead_email_sent: bool
    cpa_email_sent: bool
    cpa_assigned: Optional[str]
    nurture_enrolled: bool
    errors: List[str]


class GenerateReportRequest(BaseModel):
    """Request to generate and deliver advisory report."""
    lead_id: str
    session_id: str
    lead_email: str
    lead_name: str
    cpa_id: Optional[str] = None
    cpa_email: Optional[str] = None
    cpa_name: Optional[str] = None
    brand_config: Optional[Dict[str, Any]] = None


class PlatformFeeRequest(BaseModel):
    """Request to calculate platform fees."""
    engagement_value: float = Field(..., gt=0, description="Engagement value in dollars")
    is_high_value: bool = Field(False, description="Whether this is a high-value engagement (>$5000)")


class PlatformFeeResponse(BaseModel):
    """Platform fee calculation response."""
    engagement_value: float
    lead_revenue_share: float
    lead_revenue_share_percent: float
    stripe_processing_fee: float
    stripe_processing_percent: float
    total_platform_fee: float
    net_to_cpa: float
    breakdown: Dict[str, float]


class RegisterCPARequest(BaseModel):
    """Request to register a CPA for auto-assignment."""
    cpa_id: str
    cpa_email: str
    cpa_name: str
    firm_id: str = "default"
    max_daily_leads: int = 10
    handles_complex: bool = True
    handles_business: bool = True
    handles_international: bool = False


class AssignmentStatsResponse(BaseModel):
    """CPA assignment statistics."""
    registered_cpas: int
    available_cpas: int
    total_assignments_today: int
    cpa_details: List[Dict[str, Any]]


# =============================================================================
# ENDPOINTS
# =============================================================================

@funnel_router.post(
    "/process-lead",
    response_model=FunnelResultResponse,
    summary="Process qualified lead through funnel",
    description="Runs the complete CONVERT + MATCH + FACILITATE flow for a qualified lead"
)
async def process_qualified_lead(
    request: ProcessLeadRequest,
    background_tasks: BackgroundTasks,
):
    """
    Process a fully qualified lead through the funnel.

    This endpoint:
    1. Generates the advisory report from the tax session
    2. Exports to professional PDF
    3. Sends report to lead via email
    4. Auto-assigns to a CPA (if pool provided)
    5. Notifies CPA with lead details and report
    6. Enrolls lead in nurture sequence

    Use this after a lead has completed the questionnaire (QUALIFY step).
    """
    try:
        from cpa_panel.services.funnel_orchestrator import get_funnel_orchestrator

        orchestrator = get_funnel_orchestrator()

        result = await orchestrator.process_qualified_lead(
            lead_id=request.lead_id,
            lead_email=request.lead_email,
            lead_name=request.lead_name,
            session_id=request.session_id,
            cpa_pool=request.cpa_pool,
            brand_config=request.brand_config,
        )

        return FunnelResultResponse(**result)

    except Exception as e:
        logger.exception(f"Funnel processing failed for lead {request.lead_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@funnel_router.post(
    "/generate-report",
    response_model=FunnelResultResponse,
    summary="Generate and deliver advisory report",
    description="Generates PDF report and delivers via email"
)
async def generate_and_deliver_report(request: GenerateReportRequest):
    """
    Generate advisory report, export to PDF, and deliver via email.

    This is a more granular endpoint for just the CONVERT step,
    useful when you want to control assignment separately.
    """
    try:
        from cpa_panel.services.funnel_orchestrator import get_funnel_orchestrator

        orchestrator = get_funnel_orchestrator()

        result = await orchestrator.generate_and_deliver_report(
            lead_id=request.lead_id,
            session_id=request.session_id,
            lead_email=request.lead_email,
            lead_name=request.lead_name,
            cpa_id=request.cpa_id,
            cpa_email=request.cpa_email,
            cpa_name=request.cpa_name,
            brand_config=request.brand_config,
        )

        return FunnelResultResponse(**result)

    except Exception as e:
        logger.exception(f"Report generation failed for lead {request.lead_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@funnel_router.post(
    "/calculate-fee",
    response_model=PlatformFeeResponse,
    summary="Calculate platform fees for engagement",
    description="Calculate lead revenue share and processing fees"
)
async def calculate_platform_fee(request: PlatformFeeRequest):
    """
    Calculate platform fees for a lead engagement.

    Returns breakdown of:
    - Lead revenue share (15% standard, 12% for high-value)
    - Stripe processing fee (2.9% + $0.30)
    - Total platform fee
    - Net amount to CPA
    """
    try:
        from cpa_panel.services.funnel_orchestrator import calculate_lead_platform_fee

        result = calculate_lead_platform_fee(
            engagement_value=request.engagement_value,
            is_high_value=request.is_high_value,
        )

        return PlatformFeeResponse(
            engagement_value=result.engagement_value,
            lead_revenue_share=result.lead_revenue_share,
            lead_revenue_share_percent=result.lead_revenue_share_percent,
            stripe_processing_fee=result.stripe_processing_fee,
            stripe_processing_percent=result.stripe_processing_percent,
            total_platform_fee=result.total_platform_fee,
            net_to_cpa=result.net_to_cpa,
            breakdown=result.breakdown,
        )

    except Exception as e:
        logger.exception(f"Fee calculation failed: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@funnel_router.post(
    "/register-cpa",
    summary="Register CPA for auto-assignment",
    description="Register a CPA in the auto-assignment pool"
)
async def register_cpa_for_assignment(request: RegisterCPARequest):
    """
    Register a CPA for automatic lead assignment.

    CPAs must be registered before they can receive auto-assigned leads.
    This endpoint sets their capacity and specialization preferences.
    """
    try:
        from cpa_panel.services.funnel_orchestrator import get_auto_assigner, CPACapacity

        assigner = get_auto_assigner()

        cpa = CPACapacity(
            cpa_id=request.cpa_id,
            cpa_email=request.cpa_email,
            cpa_name=request.cpa_name,
            firm_id=request.firm_id,
            max_daily_leads=request.max_daily_leads,
            handles_complex=request.handles_complex,
            handles_business=request.handles_business,
            handles_international=request.handles_international,
            is_available=True,
        )

        assigner.register_cpa(cpa)

        return {
            "success": True,
            "message": f"CPA {request.cpa_name} registered for auto-assignment",
            "cpa_id": request.cpa_id,
        }

    except Exception as e:
        logger.exception(f"CPA registration failed: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@funnel_router.get(
    "/assignment-stats",
    response_model=AssignmentStatsResponse,
    summary="Get CPA assignment statistics",
    description="Get statistics about registered CPAs and assignments"
)
async def get_assignment_stats():
    """
    Get statistics about CPA registration and lead assignments.

    Returns information about:
    - Number of registered CPAs
    - Number available for assignment
    - Today's assignment counts
    - Per-CPA capacity details
    """
    try:
        from cpa_panel.services.funnel_orchestrator import get_auto_assigner

        assigner = get_auto_assigner()

        cpas = list(assigner._cpa_capacities.values())
        available = [c for c in cpas if c.is_available and c.leads_today < c.max_daily_leads]
        total_today = sum(c.leads_today for c in cpas)

        return AssignmentStatsResponse(
            registered_cpas=len(cpas),
            available_cpas=len(available),
            total_assignments_today=total_today,
            cpa_details=[
                {
                    "cpa_id": c.cpa_id,
                    "cpa_name": c.cpa_name,
                    "firm_id": c.firm_id,
                    "leads_today": c.leads_today,
                    "leads_this_week": c.leads_this_week,
                    "max_daily_leads": c.max_daily_leads,
                    "is_available": c.is_available,
                    "handles_complex": c.handles_complex,
                    "handles_business": c.handles_business,
                }
                for c in cpas
            ],
        )

    except Exception as e:
        logger.exception(f"Failed to get assignment stats: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@funnel_router.post(
    "/assign-lead",
    summary="Manually trigger lead auto-assignment",
    description="Assign a lead to the next available CPA"
)
async def assign_lead_to_cpa(
    lead_id: str,
    lead_complexity: str = "moderate",
    has_business: bool = False,
    firm_id: Optional[str] = None,
    algorithm: str = "round_robin",
):
    """
    Manually trigger lead auto-assignment.

    Algorithms:
    - round_robin: Distribute evenly (default)
    - complexity_match: Match lead complexity to CPA expertise
    - capacity: Assign to CPA with most available capacity
    """
    try:
        from cpa_panel.services.funnel_orchestrator import get_auto_assigner

        assigner = get_auto_assigner()

        cpa_id = assigner.assign_lead(
            lead_id=lead_id,
            lead_data={
                "complexity": lead_complexity,
                "has_business": has_business,
            },
            algorithm=algorithm,
            firm_id=firm_id,
        )

        if cpa_id:
            return {
                "success": True,
                "lead_id": lead_id,
                "assigned_cpa_id": cpa_id,
                "algorithm": algorithm,
            }
        else:
            return {
                "success": False,
                "lead_id": lead_id,
                "message": "No available CPA for assignment",
            }

    except Exception as e:
        logger.exception(f"Lead assignment failed: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@funnel_router.get(
    "/config",
    summary="Get funnel configuration",
    description="Get current funnel orchestration settings"
)
async def get_funnel_config():
    """Get current funnel configuration settings."""
    try:
        from cpa_panel.services.funnel_orchestrator import get_funnel_config

        config = get_funnel_config()

        return {
            "lead_revenue_share_percent": config.lead_revenue_share_percent,
            "high_value_revenue_share_percent": config.high_value_revenue_share_percent,
            "auto_assignment_enabled": config.auto_assignment_enabled,
            "assignment_algorithm": config.assignment_algorithm,
            "max_leads_per_cpa_per_day": config.max_leads_per_cpa_per_day,
            "send_report_to_lead": config.send_report_to_lead,
            "send_report_to_cpa": config.send_report_to_cpa,
            "send_hot_lead_alerts": config.send_hot_lead_alerts,
            "auto_enroll_nurture": config.auto_enroll_nurture,
            "default_nurture_sequence": config.default_nurture_sequence,
        }

    except Exception as e:
        logger.exception(f"Failed to get config: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")
