"""
Lead Generation API Routes

Provides endpoints for prospect lead generation and management:
1. Quick estimate form (prospect-facing)
2. Document upload for teaser (prospect-facing)
3. Contact capture (prospect-facing)
4. Lead management (CPA-facing)
5. Lead conversion (CPA-facing)
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from pydantic import BaseModel, Field
try:
    from pydantic import EmailStr
except ImportError:
    EmailStr = str  # Fallback if email-validator not installed
from typing import Optional, Dict, Any, List
import logging

from ..services.lead_generation_service import (
    get_lead_generation_service,
    LeadSource,
    LeadStatus,
    LeadPriority,
)
from .auth_dependencies import require_internal_cpa_auth

logger = logging.getLogger(__name__)

lead_generation_router = APIRouter(
    prefix="/leads",
    tags=["Lead Generation"]
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class QuickEstimateRequest(BaseModel):
    """Request for quick tax savings estimate."""
    filing_status: str = Field(
        ...,
        description="Filing status: single, mfj, mfs, hoh"
    )
    estimated_income: float = Field(
        ...,
        description="Estimated annual income",
        gt=0
    )
    has_dependents: bool = Field(
        default=False,
        description="Whether taxpayer has dependents"
    )
    num_dependents: int = Field(
        default=0,
        description="Number of dependents",
        ge=0
    )


class TeaserResponse(BaseModel):
    """Teaser shown to prospects."""
    lead_id: str
    potential_savings_range: str
    opportunity_count: int
    opportunity_categories: List[str]
    headline: str
    call_to_action: str


class CaptureContactRequest(BaseModel):
    """Request to capture prospect contact info."""
    email: str = Field(..., description="Prospect's email address")
    name: Optional[str] = Field(None, description="Prospect's name")
    phone: Optional[str] = Field(None, description="Prospect's phone number")


class LeadResponse(BaseModel):
    """Lead information response."""
    lead_id: str
    status: str
    source: str
    priority: str
    contact: Dict[str, Any]
    tax_profile: Dict[str, Any]
    teaser: Dict[str, Any]
    assignment: Dict[str, Any]


class FullAnalysisResponse(BaseModel):
    """Full analysis unlocked after contact capture."""
    lead_id: str
    contact: Dict[str, Any]
    total_potential_savings: float
    opportunities: List[Dict[str, Any]]
    tax_summary: Dict[str, Any]
    recommendations_count: int


class AssignLeadRequest(BaseModel):
    """Request to assign lead to CPA."""
    cpa_id: str = Field(..., description="ID of CPA to assign")


class UpdateStatusRequest(BaseModel):
    """Request to update lead status."""
    status: str = Field(
        ...,
        description="New status: new, qualified, contacted, engaged, converted, lost"
    )
    note: Optional[str] = Field(None, description="Optional note about the update")


class PipelineSummaryResponse(BaseModel):
    """Lead pipeline summary."""
    total: int
    by_status: Dict[str, int]
    by_priority: Dict[str, int]
    by_source: Dict[str, int]
    total_potential_savings: float
    conversion_rate: float


# =============================================================================
# PROSPECT-FACING ENDPOINTS
# =============================================================================

@lead_generation_router.post(
    "/estimate",
    response_model=TeaserResponse,
    summary="Get quick tax savings estimate",
    description="Get a teaser of potential tax savings based on basic info"
)
async def get_quick_estimate(request: QuickEstimateRequest):
    """
    Generate a quick tax savings estimate for a prospect.

    This is the fastest lead generation path:
    1. Prospect answers 3-4 questions
    2. System generates teaser showing potential savings
    3. Teaser encourages prospect to provide contact info

    No document upload required.
    """
    try:
        service = get_lead_generation_service()

        lead, teaser = service.create_lead_from_quick_estimate(
            filing_status=request.filing_status,
            estimated_income=request.estimated_income,
            has_dependents=request.has_dependents,
            num_dependents=request.num_dependents,
        )

        return TeaserResponse(
            lead_id=lead.lead_id,
            potential_savings_range=teaser.potential_savings_range,
            opportunity_count=teaser.opportunity_count,
            opportunity_categories=teaser.opportunity_categories,
            headline=teaser.headline,
            call_to_action=teaser.call_to_action,
        )

    except Exception as e:
        logger.error(f"Quick estimate failed: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@lead_generation_router.post(
    "/upload",
    response_model=TeaserResponse,
    summary="Upload 1040 for tax savings estimate",
    description="Upload a 1040 to get a more accurate savings estimate"
)
async def upload_for_estimate(
    file: UploadFile = File(..., description="1040 PDF or image file")
):
    """
    Generate a tax savings estimate from uploaded 1040.

    This provides the most accurate teaser since we have actual
    tax return data to analyze.

    Flow:
    1. Prospect uploads prior year 1040
    2. System extracts data via OCR
    3. System generates teaser with accurate savings estimate
    4. Teaser encourages prospect to provide contact info
    """
    try:
        service = get_lead_generation_service()

        # Read file content
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        if len(content) > 20 * 1024 * 1024:  # 20MB limit
            raise HTTPException(status_code=400, detail="File too large (max 20MB)")

        lead, teaser = await service.create_lead_from_document(
            file_content=content,
            filename=file.filename or "upload.pdf",
            content_type=file.content_type or "application/pdf",
        )

        return TeaserResponse(
            lead_id=lead.lead_id,
            potential_savings_range=teaser.potential_savings_range,
            opportunity_count=teaser.opportunity_count,
            opportunity_categories=teaser.opportunity_categories,
            headline=teaser.headline,
            call_to_action=teaser.call_to_action,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload for estimate failed: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@lead_generation_router.post(
    "/{lead_id}/contact",
    response_model=FullAnalysisResponse,
    summary="Capture contact info and unlock full analysis",
    description="Provide contact info to see the full tax savings analysis"
)
async def capture_contact(lead_id: str, request: CaptureContactRequest):
    """
    Capture prospect's contact info and unlock full analysis.

    Once contact info is provided:
    1. Lead is marked as qualified
    2. Full analysis is generated
    3. Lead is ready for CPA follow-up
    """
    try:
        service = get_lead_generation_service()

        lead = service.capture_contact_info(
            lead_id=lead_id,
            email=request.email,
            name=request.name,
            phone=request.phone,
        )

        if not lead.full_analysis:
            raise HTTPException(status_code=500, detail="Analysis failed")

        return FullAnalysisResponse(
            lead_id=lead.lead_id,
            contact={
                "email": lead.email,
                "name": lead.name,
                "phone": lead.phone,
            },
            total_potential_savings=float(lead.full_analysis.total_potential_savings),
            opportunities=[o.to_dict() for o in lead.full_analysis.opportunities],
            tax_summary=lead.full_analysis.tax_summary,
            recommendations_count=lead.full_analysis.recommendations_count,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail="Resource not found")
    except Exception as e:
        logger.error(f"Contact capture failed for lead {lead_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# =============================================================================
# CPA-FACING ENDPOINTS
# =============================================================================

@lead_generation_router.get(
    "/pipeline-summary",
    response_model=PipelineSummaryResponse,
    summary="Get lead pipeline summary",
    description="Get overview of lead pipeline with counts by status, priority, and source",
    dependencies=[Depends(require_internal_cpa_auth)],
)
async def get_pipeline_summary(
    cpa_id: Optional[str] = Query(None, description="Filter by assigned CPA")
):
    """
    Get a summary of the lead pipeline.

    Returns counts by status, priority, and source,
    plus total potential savings and conversion rate.
    """
    service = get_lead_generation_service()
    summary = service.get_lead_pipeline_summary(cpa_id)

    return PipelineSummaryResponse(**summary)


@lead_generation_router.get(
    "/unassigned",
    summary="Get unassigned leads",
    description="Get all leads not yet assigned to a CPA",
    dependencies=[Depends(require_internal_cpa_auth)],
)
async def get_unassigned_leads():
    """
    Get all unassigned leads for assignment.

    Returns leads sorted by priority and potential savings.
    """
    service = get_lead_generation_service()
    leads = service.get_unassigned_leads()

    return {
        "count": len(leads),
        "leads": [
            {
                "lead_id": l.lead_id,
                "source": l.source.value,
                "status": l.status.value,
                "priority": l.priority.value,
                "contact": {
                    "email": l.email,
                    "name": l.name,
                },
                "teaser_savings": float(l.teaser_savings) if l.teaser_savings else None,
                "opportunity_categories": l.teaser_opportunities,
                "created_at": l.created_at.isoformat(),
            }
            for l in sorted(leads, key=lambda x: (
                0 if x.priority == LeadPriority.HIGH else 1 if x.priority == LeadPriority.MEDIUM else 2,
                float(x.teaser_savings or 0) * -1,  # Higher savings first
            ))
        ],
    }


@lead_generation_router.get(
    "/high-priority",
    summary="Get high priority leads",
    description="Get all high priority leads for immediate follow-up",
    dependencies=[Depends(require_internal_cpa_auth)],
)
async def get_high_priority_leads():
    """
    Get all high priority leads.

    These are leads with significant potential savings that
    warrant immediate CPA attention.
    """
    service = get_lead_generation_service()
    leads = service.get_high_priority_leads()

    return {
        "count": len(leads),
        "leads": [
            {
                "lead_id": l.lead_id,
                "source": l.source.value,
                "status": l.status.value,
                "contact": {
                    "email": l.email,
                    "name": l.name,
                    "phone": l.phone,
                },
                "teaser_savings": float(l.teaser_savings) if l.teaser_savings else None,
                "opportunity_categories": l.teaser_opportunities,
                "assigned_cpa": l.assigned_cpa_id,
                "created_at": l.created_at.isoformat(),
            }
            for l in sorted(leads, key=lambda x: x.created_at, reverse=True)
        ],
    }


@lead_generation_router.get(
    "/cpa/{cpa_id}",
    summary="Get leads for CPA",
    description="Get all leads assigned to a specific CPA",
    dependencies=[Depends(require_internal_cpa_auth)],
)
async def get_leads_for_cpa(
    cpa_id: str,
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    Get all leads assigned to a CPA.

    Optionally filter by status.
    """
    service = get_lead_generation_service()

    # Parse status if provided
    lead_status = None
    if status:
        try:
            lead_status = LeadStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    leads = service.get_leads_for_cpa(cpa_id, lead_status)

    return {
        "cpa_id": cpa_id,
        "count": len(leads),
        "leads": [l.to_dict() for l in leads],
    }


@lead_generation_router.get(
    "/{lead_id}/profile",
    response_model=LeadResponse,
    summary="Get lead details",
    description="Get detailed information about a specific lead",
    dependencies=[Depends(require_internal_cpa_auth)],
)
async def get_lead(lead_id: str):
    """
    Get detailed information about a lead.
    """
    service = get_lead_generation_service()
    lead = service.get_lead(lead_id)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return LeadResponse(
        lead_id=lead.lead_id,
        status=lead.status.value,
        source=lead.source.value,
        priority=lead.priority.value,
        contact={
            "email": lead.email,
            "name": lead.name,
            "phone": lead.phone,
        },
        tax_profile={
            "filing_status": lead.filing_status.value if lead.filing_status else None,
            "estimated_agi": float(lead.estimated_agi) if lead.estimated_agi else None,
            "has_dependents": lead.has_dependents,
            "num_dependents": lead.num_dependents,
        },
        teaser={
            "potential_savings": float(lead.teaser_savings) if lead.teaser_savings else None,
            "opportunities": lead.teaser_opportunities,
        },
        assignment={
            "cpa_id": lead.assigned_cpa_id,
        },
    )


@lead_generation_router.get(
    "/{lead_id}/analysis",
    summary="Get lead's full analysis",
    description="Get the full tax savings analysis for a lead",
    dependencies=[Depends(require_internal_cpa_auth)],
)
async def get_lead_analysis(lead_id: str):
    """
    Get the full analysis for a lead.

    Only available after contact info has been captured.
    """
    service = get_lead_generation_service()
    lead = service.get_lead(lead_id)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not lead.full_analysis:
        raise HTTPException(
            status_code=400,
            detail="Full analysis not available. Contact info required."
        )

    return {
        "lead_id": lead.lead_id,
        "analysis": lead.full_analysis.to_dict(),
    }


@lead_generation_router.post(
    "/{lead_id}/assign",
    summary="Assign lead to CPA",
    description="Assign a lead to a CPA for follow-up",
    dependencies=[Depends(require_internal_cpa_auth)],
)
async def assign_lead(lead_id: str, request: AssignLeadRequest):
    """
    Assign a lead to a CPA.

    This makes the CPA responsible for following up with
    the prospect and converting them to a client.
    """
    try:
        service = get_lead_generation_service()
        lead = service.assign_lead_to_cpa(lead_id, request.cpa_id)

        return {
            "lead_id": lead.lead_id,
            "assigned_cpa_id": lead.assigned_cpa_id,
            "status": lead.status.value,
            "message": f"Lead assigned to CPA {request.cpa_id}",
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail="Resource not found")


@lead_generation_router.post(
    "/{lead_id}/status",
    summary="Update lead status",
    description="Update the status of a lead",
    dependencies=[Depends(require_internal_cpa_auth)],
)
async def update_status(lead_id: str, request: UpdateStatusRequest):
    """
    Update the status of a lead.

    Valid statuses: new, qualified, contacted, engaged, converted, lost
    """
    try:
        status = LeadStatus(request.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    try:
        service = get_lead_generation_service()
        lead = service.update_lead_status(lead_id, status, request.note)

        return {
            "lead_id": lead.lead_id,
            "status": lead.status.value,
            "notes_count": len(lead.notes),
            "message": f"Status updated to {request.status}",
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail="Resource not found")


@lead_generation_router.post(
    "/{lead_id}/convert",
    summary="Convert lead to client",
    description="Convert a qualified lead into a client",
    dependencies=[Depends(require_internal_cpa_auth)],
)
async def convert_lead(lead_id: str, cpa_id: str = Query(..., description="CPA ID")):
    """
    Convert a lead to a client.

    This finalizes the lead generation process by:
    1. Creating a client record
    2. Transferring all collected data
    3. Marking the lead as converted
    """
    try:
        service = get_lead_generation_service()
        lead, client_id = service.convert_lead_to_client(lead_id, cpa_id)

        return {
            "lead_id": lead.lead_id,
            "status": lead.status.value,
            "client_id": client_id,
            "message": "Lead successfully converted to client",
            "analysis_summary": {
                "total_potential_savings": float(lead.full_analysis.total_potential_savings) if lead.full_analysis else 0,
                "opportunities_count": len(lead.full_analysis.opportunities) if lead.full_analysis else 0,
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid request")


# =============================================================================
# DEMO ENDPOINTS
# =============================================================================

@lead_generation_router.get(
    "/demo/teaser",
    response_model=TeaserResponse,
    summary="Get sample teaser",
    description="Get a sample teaser for demo/testing"
)
async def get_demo_teaser():
    """
    Get a sample teaser for demo purposes.
    """
    return TeaserResponse(
        lead_id="demo-lead-123",
        potential_savings_range="$2,400 - $4,800",
        opportunity_count=4,
        opportunity_categories=[
            "Retirement Savings",
            "Healthcare Tax Benefits",
            "Family Tax Credits",
            "Deduction Strategy",
        ],
        headline="Based on your income, we found significant tax savings!",
        call_to_action="Enter your email to see your personalized tax savings report.",
    )


@lead_generation_router.get(
    "/demo/full-analysis",
    response_model=FullAnalysisResponse,
    summary="Get sample full analysis",
    description="Get a sample full analysis for demo/testing"
)
async def get_demo_analysis():
    """
    Get a sample full analysis for demo purposes.
    """
    return FullAnalysisResponse(
        lead_id="demo-lead-123",
        contact={
            "email": "prospect@example.com",
            "name": "Demo Prospect",
            "phone": None,
        },
        total_potential_savings=4200.00,
        opportunities=[
            {
                "id": "opp_401k",
                "title": "Maximize 401(k) Contributions",
                "category": "retirement",
                "potential_savings": 2100.00,
                "confidence": "high",
                "description": "Increase 401(k) contributions to maximum allowed",
                "action_required": "Contact HR to increase contribution rate",
                "priority": 1,
            },
            {
                "id": "opp_hsa",
                "title": "Maximize HSA Contributions",
                "category": "healthcare",
                "potential_savings": 1250.00,
                "confidence": "high",
                "description": "Contribute maximum to Health Savings Account",
                "action_required": "Set up HSA contributions",
                "priority": 2,
            },
            {
                "id": "opp_dcfsa",
                "title": "Dependent Care FSA",
                "category": "dependents",
                "potential_savings": 850.00,
                "confidence": "medium",
                "description": "Use pre-tax dollars for childcare",
                "action_required": "Enroll during open enrollment",
                "priority": 3,
            },
        ],
        tax_summary={
            "estimated_agi": 85000.00,
            "filing_status": "single",
            "dependents": 0,
        },
        recommendations_count=3,
    )
