"""
Lead Magnet API Routes

Smart Tax Advisory Lead Magnet Flow endpoints:
1. Start assessment session with CPA branding
2. Submit smart tax profile (quick questions)
3. Capture contact info (lead gate)
4. Generate/retrieve tiered reports
5. CPA lead management
"""

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
try:
    from pydantic import EmailStr
except ImportError:
    EmailStr = str
from typing import Optional, Dict, Any, List
import logging

from ..services.lead_magnet_service import (
    get_lead_magnet_service,
    TaxComplexity,
)
from ..services.report_templates import get_report_template_service

logger = logging.getLogger(__name__)

lead_magnet_router = APIRouter(
    prefix="/lead-magnet",
    tags=["Lead Magnet"]
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class StartAssessmentRequest(BaseModel):
    """Request to start a new lead magnet assessment session."""
    cpa_slug: Optional[str] = Field(
        None,
        description="CPA's unique URL slug (e.g., 'john-smith-cpa')"
    )
    assessment_mode: str = Field(
        default="quick",
        description="Assessment mode: 'quick' (2 min) or 'full' (5 min)"
    )
    referral_source: Optional[str] = Field(
        None,
        description="How the prospect found this (e.g., 'google', 'referral')"
    )


class StartAssessmentResponse(BaseModel):
    """Response after starting assessment session."""
    session_id: str
    cpa_profile: Dict[str, Any]
    assessment_mode: str
    screens: List[str]


class TaxProfileRequest(BaseModel):
    """Smart tax profile questions - all dropdowns/checkboxes, no free text."""
    filing_status: str = Field(
        ...,
        description="Filing status: single, married_jointly, married_separately, head_of_household"
    )
    dependents_count: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Number of dependents (0-10)"
    )
    has_children_under_17: bool = Field(
        default=False,
        description="Has children under 17 (CTC eligibility)"
    )
    income_range: str = Field(
        ...,
        description="Income range: 'under_50k', '50k_75k', '75k_100k', '100k_150k', '150k_200k', '200k_500k', 'over_500k'"
    )
    income_sources: List[str] = Field(
        default=[],
        description="Income sources: 'w2', 'self_employed', 'investments', 'rental', 'retirement'"
    )
    is_homeowner: bool = Field(
        default=False,
        description="Is homeowner (mortgage interest, property tax)"
    )
    retirement_savings: str = Field(
        default="none",
        description="Retirement savings level: 'none', 'some', 'maxed'"
    )
    healthcare_type: str = Field(
        default="employer",
        description="Healthcare type: 'employer', 'hdhp_hsa', 'marketplace', 'none'"
    )
    life_events: List[str] = Field(
        default=[],
        description="Recent life events: 'new_job', 'baby', 'home_purchase', 'marriage', 'divorce', 'retirement', 'college_student'"
    )
    has_student_loans: bool = Field(
        default=False,
        description="Has student loans (interest deduction)"
    )
    has_business: bool = Field(
        default=False,
        description="Owns a business or side hustle"
    )
    privacy_consent: bool = Field(
        default=False,
        description="User consented to privacy policy"
    )


class TaxProfileResponse(BaseModel):
    """Response after submitting tax profile."""
    session_id: str
    complexity: str
    income_range_display: str
    insights_preview: int
    next_screen: str


class CaptureContactRequest(BaseModel):
    """Request to capture prospect contact info."""
    first_name: str = Field(..., description="Prospect's first name")
    email: str = Field(..., description="Prospect's email address")
    phone: Optional[str] = Field(None, description="Prospect's phone number (optional)")


class CaptureContactResponse(BaseModel):
    """Response after capturing contact info."""
    session_id: str
    lead_id: str
    report_ready: bool
    redirect_url: str


class TierOneReportResponse(BaseModel):
    """Tier 1 FREE report response."""
    session_id: str
    lead_id: str
    tier: int
    cpa_name: str
    cpa_firm: str
    client_name: str
    filing_status: str
    complexity: str
    savings_range: str
    insights: List[Dict[str, Any]]
    total_insights: int
    locked_count: int
    cta_text: str
    booking_link: str
    report_html: str


class TierTwoReportResponse(BaseModel):
    """Tier 2 full report response."""
    session_id: str
    lead_id: str
    tier: int
    total_savings: str
    all_insights: List[Dict[str, Any]]
    action_items: List[Dict[str, Any]]
    tax_calendar: List[Dict[str, Any]]
    report_html: str


class LeadDashboardItem(BaseModel):
    """Lead item for CPA dashboard."""
    lead_id: str
    session_id: str
    first_name: str
    email: str
    phone: Optional[str]
    filing_status: str
    complexity: str
    income_range: str
    lead_score: int
    lead_temperature: str
    estimated_engagement_value: float
    conversion_probability: float
    savings_range: str
    engaged: bool
    created_at: str
    time_spent_seconds: int


class EngageLeadRequest(BaseModel):
    """Request to mark a lead as engaged."""
    notes: Optional[str] = Field(None, description="Optional notes about engagement")
    engagement_letter_acknowledged: bool = Field(
        default=False,
        description="Whether the engagement letter has been acknowledged (REQUIRED for Tier 2 access)"
    )


class AcknowledgeEngagementLetterRequest(BaseModel):
    """Request to acknowledge engagement letter."""
    acknowledged: bool = Field(
        ...,
        description="Confirmation that engagement letter has been acknowledged"
    )


class CPAProfileRequest(BaseModel):
    """Request to create/update a CPA profile."""
    first_name: str = Field(..., description="CPA's first name")
    last_name: str = Field(..., description="CPA's last name")
    cpa_slug: str = Field(..., description="URL-friendly identifier (e.g., 'john-smith-cpa')")
    credentials: Optional[str] = Field("CPA", description="Credentials (CPA, EA, CMA)")
    firm_name: Optional[str] = Field(None, description="Firm name")
    logo_url: Optional[str] = Field(None, description="Logo image URL")
    email: Optional[str] = Field(None, description="Contact email")
    phone: Optional[str] = Field(None, description="Contact phone")
    booking_link: Optional[str] = Field(None, description="Calendar booking link")
    address: Optional[str] = Field(None, description="Office address")
    bio: Optional[str] = Field(None, description="Professional bio")
    specialties: List[str] = Field(default=[], description="List of specialties")


# =============================================================================
# PROSPECT-FACING ENDPOINTS (Lead Magnet Flow)
# =============================================================================

@lead_magnet_router.post(
    "/start",
    response_model=StartAssessmentResponse,
    summary="Start lead magnet assessment session",
    description="Initialize a new assessment session with optional CPA branding"
)
async def start_assessment(request: StartAssessmentRequest):
    """
    Start a new lead magnet assessment session.

    This is the entry point for the lead magnet funnel:
    1. Creates a new session
    2. Loads CPA branding if cpa_slug provided
    3. Returns session ID and flow configuration
    """
    try:
        service = get_lead_magnet_service()

        session = service.start_assessment_session(
            cpa_slug=request.cpa_slug,
            assessment_mode=request.assessment_mode,
            referral_source=request.referral_source,
        )

        # Determine screens based on mode
        screens = ["welcome", "profile", "contact", "report"]
        if request.assessment_mode == "full":
            screens = ["welcome", "profile", "documents", "contact", "report"]

        return StartAssessmentResponse(
            session_id=session["session_id"],
            cpa_profile=session["cpa_profile"],
            assessment_mode=session["assessment_mode"],
            screens=screens,
        )

    except Exception as e:
        logger.error(f"Failed to start assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.post(
    "/{session_id}/profile",
    response_model=TaxProfileResponse,
    summary="Submit smart tax profile",
    description="Submit answers to quick tax profile questions"
)
async def submit_tax_profile(session_id: str, request: TaxProfileRequest):
    """
    Submit the smart tax profile questionnaire.

    All questions are dropdown/checkbox - no free text required.
    System detects complexity and identifies initial insights.
    """
    try:
        service = get_lead_magnet_service()

        result = service.submit_tax_profile(
            session_id=session_id,
            filing_status=request.filing_status,
            dependents_count=request.dependents_count,
            has_children_under_17=request.has_children_under_17,
            income_range=request.income_range,
            income_sources=request.income_sources,
            is_homeowner=request.is_homeowner,
            retirement_savings=request.retirement_savings,
            healthcare_type=request.healthcare_type,
            life_events=request.life_events,
            has_student_loans=request.has_student_loans,
            has_business=request.has_business,
            privacy_consent=request.privacy_consent,
        )

        # Income range display mapping
        income_display = {
            "under_50k": "Under $50,000",
            "50k_75k": "$50,000 - $75,000",
            "75k_100k": "$75,000 - $100,000",
            "100k_150k": "$100,000 - $150,000",
            "150k_200k": "$150,000 - $200,000",
            "200k_500k": "$200,000 - $500,000",
            "over_500k": "Over $500,000",
        }.get(request.income_range, request.income_range)

        return TaxProfileResponse(
            session_id=session_id,
            complexity=result["complexity"],
            income_range_display=income_display,
            insights_preview=result["insights_count"],
            next_screen="contact",
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit profile for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.post(
    "/{session_id}/contact",
    response_model=CaptureContactResponse,
    summary="Capture contact info (lead gate)",
    description="Capture prospect's contact info to create lead and generate report"
)
async def capture_contact(session_id: str, request: CaptureContactRequest):
    """
    Capture contact info - this is the lead gate.

    Once contact is captured:
    1. Lead is created in the system
    2. Lead score is calculated
    3. Tier 1 report is generated
    4. Lead appears in CPA dashboard
    """
    try:
        service = get_lead_magnet_service()

        result = service.capture_contact_and_create_lead(
            session_id=session_id,
            first_name=request.first_name,
            email=request.email,
            phone=request.phone,
        )

        return CaptureContactResponse(
            session_id=session_id,
            lead_id=result["lead_id"],
            report_ready=True,
            redirect_url=f"/api/cpa/lead-magnet/{session_id}/report",
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to capture contact for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.get(
    "/{session_id}/report",
    summary="Get Tier 1 FREE report",
    description="Retrieve the FREE lead magnet report with teaser insights"
)
async def get_tier_one_report(
    session_id: str,
    format: str = Query(default="json", description="Response format: 'json' or 'html'")
):
    """
    Get the Tier 1 FREE report.

    Shows:
    - CPA name & credentials (full)
    - Client name (full)
    - Filing status & complexity (full)
    - Savings estimate (range only, e.g., $500 - $2,000)
    - 3-5 teaser insights
    - Prominent CTA to contact CPA

    Hides:
    - Specific dollar amounts
    - Action items
    - IRS references
    """
    try:
        service = get_lead_magnet_service()

        report = service.get_tier_one_report(session_id)

        if format == "html":
            return Response(
                content=report["report_html"],
                media_type="text/html"
            )

        return report

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get report for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.get(
    "/{session_id}/report/full",
    summary="Get Tier 2 full report",
    description="Retrieve the full report (requires engagement AND engagement letter acknowledgment)"
)
async def get_tier_two_report(
    session_id: str,
    format: str = Query(default="json", description="Response format: 'json' or 'html'")
):
    """
    Get the Tier 2 full report.

    COMPLIANCE REQUIREMENT: Both conditions must be met:
    1. CPA must mark lead as engaged
    2. Engagement letter must be acknowledged

    This two-step requirement ensures:
    - Liability containment
    - CPA-client relationship is established
    - Professional standards are maintained

    Shows everything from Tier 1 plus:
    - Exact savings amounts
    - All insights (8+)
    - Action items with deadlines
    - IRS form references
    - Tax calendar
    """
    try:
        service = get_lead_magnet_service()

        # COMPLIANCE GUARDRAIL: Check both requirements
        can_access, reason = service.can_access_tier_two_report_by_session(session_id)
        if not can_access:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Tier 2 report access denied",
                    "reason": reason,
                    "requirements": {
                        "engaged": "CPA must mark lead as engaged",
                        "engagement_letter_acknowledged": "Engagement letter must be acknowledged"
                    }
                }
            )

        report = service.get_tier_two_report(session_id)

        if format == "html":
            return Response(
                content=report["report_html"],
                media_type="text/html"
            )

        return report

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get full report for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CPA-FACING ENDPOINTS (Lead Management)
# =============================================================================

@lead_magnet_router.get(
    "/leads",
    summary="Get all lead magnet leads",
    description="Get all leads from lead magnet funnel for CPA dashboard"
)
async def get_lead_magnet_leads(
    cpa_id: Optional[str] = Query(None, description="Filter by CPA ID"),
    temperature: Optional[str] = Query(None, description="Filter by temperature: hot, warm, cold"),
    engaged: Optional[bool] = Query(None, description="Filter by engagement status"),
    limit: int = Query(default=50, le=100, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
):
    """
    Get leads from the lead magnet funnel.

    Returns leads with scoring data for CPA follow-up prioritization.
    """
    try:
        service = get_lead_magnet_service()

        leads = service.get_leads(
            cpa_id=cpa_id,
            temperature=temperature,
            engaged=engaged,
            limit=limit,
            offset=offset,
        )

        return {
            "count": len(leads),
            "offset": offset,
            "limit": limit,
            "leads": leads,
        }

    except Exception as e:
        logger.error(f"Failed to get leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.get(
    "/leads/hot",
    summary="Get hot leads",
    description="Get high-score hot leads for immediate follow-up"
)
async def get_hot_leads(
    cpa_id: Optional[str] = Query(None, description="Filter by CPA ID"),
):
    """
    Get hot leads - highest priority for follow-up.

    Hot leads have:
    - Lead score >= 70
    - High engagement value
    - Complex tax situations
    """
    try:
        service = get_lead_magnet_service()

        leads = service.get_leads(
            cpa_id=cpa_id,
            temperature="hot",
            engaged=False,  # Only show unengaged leads
            limit=20,
        )

        return {
            "count": len(leads),
            "temperature": "hot",
            "leads": leads,
        }

    except Exception as e:
        logger.error(f"Failed to get hot leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.get(
    "/leads/stats",
    summary="Get lead statistics",
    description="Get aggregate statistics for lead magnet leads"
)
async def get_lead_stats(
    cpa_id: Optional[str] = Query(None, description="Filter by CPA ID"),
):
    """
    Get aggregate statistics for leads.

    Returns:
    - Total leads
    - By temperature (hot/warm/cold)
    - By complexity
    - By engagement status
    - Average lead score
    - Total potential engagement value
    """
    try:
        service = get_lead_magnet_service()

        stats = service.get_lead_statistics(cpa_id)

        return stats

    except Exception as e:
        logger.error(f"Failed to get lead stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.get(
    "/leads/{lead_id}",
    summary="Get lead details",
    description="Get detailed information about a specific lead"
)
async def get_lead_details(lead_id: str):
    """
    Get detailed information about a lead.

    Includes all scoring data and session history.
    """
    try:
        service = get_lead_magnet_service()

        lead = service.get_lead(lead_id)

        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        return lead

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get lead {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.post(
    "/leads/{lead_id}/engage",
    summary="Mark lead as engaged",
    description="Mark a lead as engaged (step 1 of Tier 2 unlock)"
)
async def engage_lead(lead_id: str, request: Optional[EngageLeadRequest] = None):
    """
    Mark a lead as engaged.

    COMPLIANCE NOTE: This is step 1 of the two-step Tier 2 unlock process.
    For full Tier 2 report access, engagement letter must also be acknowledged.

    Steps to unlock Tier 2:
    1. CPA marks lead as engaged (this endpoint)
    2. Client acknowledges engagement letter (/leads/{lead_id}/acknowledge-engagement)

    Both steps must be completed before Tier 2 report is accessible.
    """
    try:
        service = get_lead_magnet_service()

        engagement_letter_ack = request.engagement_letter_acknowledged if request else False
        result = service.mark_lead_engaged(lead_id, engagement_letter_ack)

        if not result:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Check if Tier 2 is fully unlocked
        tier_2_unlocked = result.can_access_tier_two()

        return {
            "lead_id": lead_id,
            "engaged": True,
            "engaged_at": result.engaged_at.isoformat() if result.engaged_at else None,
            "engagement_letter_acknowledged": result.engagement_letter_acknowledged,
            "tier_2_unlocked": tier_2_unlocked,
            "message": "Lead marked as engaged." + (
                " Tier 2 report is now available." if tier_2_unlocked
                else " Engagement letter acknowledgment required for Tier 2 access."
            ),
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to engage lead {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.post(
    "/leads/{lead_id}/acknowledge-engagement",
    summary="Acknowledge engagement letter",
    description="Acknowledge the engagement letter (step 2 of Tier 2 unlock)"
)
async def acknowledge_engagement_letter(lead_id: str, request: AcknowledgeEngagementLetterRequest):
    """
    Acknowledge the engagement letter.

    COMPLIANCE REQUIREMENT: This is step 2 of the two-step Tier 2 unlock process.
    The engagement letter establishes:
    - CPA-client relationship
    - Scope of engagement
    - Liability terms
    - Fee structure

    Both engagement AND this acknowledgment are required for Tier 2 access.
    """
    try:
        if not request.acknowledged:
            raise HTTPException(
                status_code=400,
                detail="Engagement letter must be acknowledged (acknowledged=true)"
            )

        service = get_lead_magnet_service()

        result = service.acknowledge_engagement_letter(lead_id)

        if not result:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Check if Tier 2 is fully unlocked
        tier_2_unlocked = result.can_access_tier_two()

        return {
            "lead_id": lead_id,
            "engagement_letter_acknowledged": True,
            "acknowledged_at": result.engagement_letter_acknowledged_at.isoformat() if result.engagement_letter_acknowledged_at else None,
            "engaged": result.engaged,
            "tier_2_unlocked": tier_2_unlocked,
            "message": "Engagement letter acknowledged." + (
                " Tier 2 report is now available." if tier_2_unlocked
                else " CPA engagement required for Tier 2 access."
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge engagement letter for lead {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.post(
    "/leads/{lead_id}/convert",
    summary="Convert lead to client",
    description="Convert an engaged lead to a full client"
)
async def convert_lead(lead_id: str):
    """
    Convert a lead to a client.

    This marks the lead as converted and can trigger
    client onboarding flows.
    """
    try:
        service = get_lead_magnet_service()

        result = service.convert_lead(lead_id)

        return {
            "lead_id": lead_id,
            "converted": True,
            "converted_at": result["converted_at"],
            "message": "Lead successfully converted to client.",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to convert lead {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CPA PROFILE MANAGEMENT
# =============================================================================

@lead_magnet_router.post(
    "/cpa-profiles",
    summary="Create CPA profile",
    description="Create a new CPA profile for lead magnet branding"
)
async def create_cpa_profile(request: CPAProfileRequest):
    """
    Create a CPA profile for the lead magnet flow.

    The cpa_slug becomes the unique URL identifier:
    client_portal.html?cpa=john-smith-cpa
    """
    try:
        service = get_lead_magnet_service()

        profile = service.create_cpa_profile(
            first_name=request.first_name,
            last_name=request.last_name,
            cpa_slug=request.cpa_slug,
            credentials=request.credentials,
            firm_name=request.firm_name,
            logo_url=request.logo_url,
            email=request.email,
            phone=request.phone,
            booking_link=request.booking_link,
            address=request.address,
            bio=request.bio,
            specialties=request.specialties,
        )

        return {
            "cpa_id": profile["cpa_id"],
            "cpa_slug": profile["cpa_slug"],
            "portal_url": f"/client_portal.html?cpa={profile['cpa_slug']}",
            "message": "CPA profile created successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create CPA profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.get(
    "/cpa-profiles/{cpa_slug}",
    summary="Get CPA profile by slug",
    description="Get CPA profile for branding purposes"
)
async def get_cpa_profile(cpa_slug: str):
    """
    Get CPA profile by URL slug.

    Used by the client portal to load branding.
    """
    try:
        service = get_lead_magnet_service()

        profile = service.get_cpa_profile_by_slug(cpa_slug)

        if not profile:
            raise HTTPException(status_code=404, detail="CPA profile not found")

        return profile

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get CPA profile {cpa_slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@lead_magnet_router.put(
    "/cpa-profiles/{cpa_id}",
    summary="Update CPA profile",
    description="Update an existing CPA profile"
)
async def update_cpa_profile(cpa_id: str, request: CPAProfileRequest):
    """
    Update a CPA profile.
    """
    try:
        service = get_lead_magnet_service()

        profile = service.update_cpa_profile(
            cpa_id=cpa_id,
            first_name=request.first_name,
            last_name=request.last_name,
            cpa_slug=request.cpa_slug,
            credentials=request.credentials,
            firm_name=request.firm_name,
            logo_url=request.logo_url,
            email=request.email,
            phone=request.phone,
            booking_link=request.booking_link,
            address=request.address,
            bio=request.bio,
            specialties=request.specialties,
        )

        return {
            "cpa_id": cpa_id,
            "updated": True,
            "profile": profile,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update CPA profile {cpa_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# DEMO / TESTING ENDPOINTS
# =============================================================================

@lead_magnet_router.get(
    "/demo/report",
    summary="Get demo Tier 1 report",
    description="Get a sample Tier 1 report for demo/testing"
)
async def get_demo_report(
    format: str = Query(default="json", description="Response format: 'json' or 'html'")
):
    """
    Get a sample Tier 1 report for demo purposes.
    """
    demo_report = {
        "session_id": "demo-session-123",
        "lead_id": "demo-lead-456",
        "tier": 1,
        "cpa_name": "John Smith, CPA",
        "cpa_firm": "Smith Tax Advisory",
        "client_name": "Demo Client",
        "filing_status": "Married Filing Jointly",
        "complexity": "Moderate",
        "savings_range": "$1,500 - $4,200",
        "insights": [
            {
                "category": "Retirement",
                "title": "Maximize 401(k) Contributions",
                "teaser_description": "You may be able to increase tax-deferred savings...",
                "savings_range": "$800 - $2,100",
            },
            {
                "category": "Healthcare",
                "title": "HSA Contribution Opportunity",
                "teaser_description": "Your healthcare plan may qualify for additional savings...",
                "savings_range": "$400 - $1,200",
            },
            {
                "category": "Family",
                "title": "Child Tax Credit Optimization",
                "teaser_description": "Based on your family situation, there may be credits...",
                "savings_range": "$300 - $900",
            },
        ],
        "total_insights": 8,
        "locked_count": 5,
        "cta_text": "Schedule a free consultation to unlock your full analysis",
        "booking_link": "https://calendly.com/demo-cpa",
    }

    if format == "html":
        # Return simple HTML demo
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Demo Report</title></head>
        <body>
            <h1>Tax Advisory Report - Demo</h1>
            <p>Prepared by: {demo_report['cpa_name']}</p>
            <p>Potential Savings: {demo_report['savings_range']}</p>
            <p>Insights found: {demo_report['total_insights']}</p>
        </body>
        </html>
        """
        return Response(content=html, media_type="text/html")

    return demo_report
