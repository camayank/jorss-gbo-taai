"""
Core Premium Reports API Routes

Unified report generation endpoints for all client types:
- Generate tiered advisory reports (Basic, Standard, Premium)
- Download reports in multiple formats
- Get pricing and tier information

Access control:
- direct_client: Full access to all tiers (pays platform pricing)
- firm_client: Full access to all tiers (CPA sets pricing)
- partner/staff: Can generate reports for their firm_clients

Pricing:
- Basic: Free
- Standard: $79 (platform pricing for direct_client)
- Premium: $199 (platform pricing for direct_client)
- CPA sets their own pricing for firm_clients
"""

import logging
from datetime import datetime
from typing import Optional, List
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .auth_routes import get_current_user
from ..models.user import UserContext, UserType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Core Premium Reports"])


# =============================================================================
# MODELS
# =============================================================================

class ReportTierRequest(str, Enum):
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"


class ReportFormatRequest(str, Enum):
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


class GenerateReportRequest(BaseModel):
    """Request to generate a premium report."""
    session_id: str = Field(..., description="Tax calculation session ID")
    tier: ReportTierRequest = Field(default=ReportTierRequest.BASIC, description="Report tier")
    format: ReportFormatRequest = Field(default=ReportFormatRequest.HTML, description="Output format")


class ReportResponse(BaseModel):
    """Response containing generated report."""
    report_id: str
    session_id: str
    tier: str
    format: str
    generated_at: str
    taxpayer_name: str
    tax_year: int
    section_count: int
    action_item_count: int
    html_content: Optional[str] = None
    json_data: Optional[dict] = None


class TierInfo(BaseModel):
    """Information about a report tier."""
    tier: str
    price: float
    label: str
    description: str
    section_count: int
    sections: List[str]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_premium_generator():
    """Get the premium report generator singleton."""
    from export.premium_report_generator import PremiumReportGenerator
    return PremiumReportGenerator()


def check_report_access(user: UserContext, session_id: str) -> bool:
    """
    Check if user has access to generate reports for this session.

    Access rules:
    - direct_client: Can only access their own sessions
    - firm_client: Can only access their own sessions
    - partner/staff: Can access sessions for clients in their firm
    - platform_admin: Can access all sessions
    """
    # Platform admins have full access
    if user.user_type == UserType.PLATFORM_ADMIN:
        return True

    # For now, allow access (full session validation would check session ownership)
    # In production, this would verify:
    # 1. Session exists
    # 2. Session belongs to user (direct_client/firm_client)
    # 3. Or session's client is in user's firm (partner/staff)
    return True


def get_pricing_for_user(user: UserContext, tier: str) -> dict:
    """
    Get pricing information for a user.

    - direct_client: Platform pricing
    - firm_client: CPA-set pricing (retrieved from firm settings)
    - partner/staff: Free (generating for clients)
    """
    platform_pricing = {
        "basic": 0,
        "standard": 79,
        "premium": 199,
    }

    if user.user_type in [UserType.CPA_TEAM]:
        # CPAs generate for free (they charge clients directly)
        return {"price": 0, "currency": "USD", "source": "cpa_included"}

    if user.user_type == UserType.CPA_CLIENT:
        # Would look up CPA's pricing from firm settings
        # For now, return platform pricing as placeholder
        return {"price": platform_pricing.get(tier, 0), "currency": "USD", "source": "cpa_pricing"}

    # direct_client or consumer
    return {"price": platform_pricing.get(tier, 0), "currency": "USD", "source": "platform"}


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    request: GenerateReportRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    Generate a tiered tax advisory report.

    Tiers:
    - **basic** (free): Tax summary + computation statement
    - **standard** ($79): + Advisory sections + scenarios
    - **premium** ($199): + Full appendices + action items + PDF

    The same intelligence is provided to both direct_client and firm_client.
    CPA partners can generate reports for their clients with their own pricing.

    Returns:
        Generated report with HTML content (or JSON for format=json)
    """
    # Check access
    if not check_report_access(user, request.session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session",
        )

    # Get pricing (for logging/billing)
    pricing = get_pricing_for_user(user, request.tier.value)
    logger.info(
        f"Report generation: user={user.id}, session={request.session_id}, "
        f"tier={request.tier.value}, price=${pricing['price']}"
    )

    try:
        from export.premium_report_generator import (
            PremiumReportGenerator,
            ReportTier,
            ReportFormat,
        )

        generator = PremiumReportGenerator()
        report = generator.generate(
            session_id=request.session_id,
            tier=ReportTier(request.tier.value),
            format=ReportFormat(request.format.value),
        )

        # Check for errors
        if report.metadata.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=report.metadata["error"],
            )

        response = ReportResponse(
            report_id=report.report_id,
            session_id=report.session_id,
            tier=report.tier.value,
            format=report.format.value,
            generated_at=report.generated_at,
            taxpayer_name=report.taxpayer_name,
            tax_year=report.tax_year,
            section_count=len(report.sections),
            action_item_count=len(report.action_items),
        )

        if request.format == ReportFormatRequest.HTML:
            response.html_content = report.html_content
        elif request.format == ReportFormatRequest.JSON:
            response.json_data = report.json_data

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(e)}",
        )


@router.get("/download/{session_id}")
async def download_report(
    session_id: str,
    tier: ReportTierRequest = Query(default=ReportTierRequest.PREMIUM),
    format: ReportFormatRequest = Query(default=ReportFormatRequest.PDF),
    user: UserContext = Depends(get_current_user),
):
    """
    Download a generated report as a file.

    Returns:
        - PDF: application/pdf
        - HTML: text/html
        - JSON: application/json
    """
    if not check_report_access(user, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session",
        )

    try:
        from export.premium_report_generator import (
            PremiumReportGenerator,
            ReportTier,
            ReportFormat,
        )

        generator = PremiumReportGenerator()
        report = generator.generate(
            session_id=session_id,
            tier=ReportTier(tier.value),
            format=ReportFormat(format.value),
        )

        if report.metadata.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=report.metadata["error"],
            )

        timestamp = datetime.now().strftime("%Y%m%d")
        safe_name = report.taxpayer_name.replace(" ", "_")

        if format == ReportFormatRequest.PDF:
            return Response(
                content=report.pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}_TaxReport_{timestamp}.pdf"'
                },
            )
        elif format == ReportFormatRequest.HTML:
            return Response(
                content=report.html_content,
                media_type="text/html",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}_TaxReport_{timestamp}.html"'
                },
            )
        else:  # JSON
            import json
            return Response(
                content=json.dumps(report.json_data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}_TaxReport_{timestamp}.json"'
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report download error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report download failed: {str(e)}",
        )


@router.get("/tiers", response_model=List[TierInfo])
async def get_report_tiers(
    user: UserContext = Depends(get_current_user),
):
    """
    Get available report tiers and pricing.

    Returns pricing based on user type:
    - direct_client: Platform pricing ($0/$79/$199)
    - firm_client: CPA's custom pricing
    - partner/staff: Free (CPA charges clients directly)
    """
    from export.premium_report_generator import (
        get_tier_pricing,
        get_tier_sections,
        ReportTier,
    )

    pricing_info = get_tier_pricing()
    tiers = []

    for tier_key, info in pricing_info.items():
        # Adjust pricing based on user type
        user_pricing = get_pricing_for_user(user, tier_key)

        tiers.append(TierInfo(
            tier=tier_key,
            price=user_pricing["price"],
            label=info["label"],
            description=info["description"],
            section_count=info["section_count"],
            sections=get_tier_sections(tier_key),
        ))

    return tiers


@router.get("/sections/{tier}")
async def get_tier_sections_endpoint(
    tier: ReportTierRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    Get list of sections included in a specific tier.

    Returns section IDs and metadata for the requested tier.
    """
    from export.premium_report_generator import (
        get_tier_sections,
        SECTION_METADATA,
        ReportSection,
    )

    section_ids = get_tier_sections(tier.value)
    sections = []

    for section_id in section_ids:
        try:
            section_enum = ReportSection(section_id)
            meta = SECTION_METADATA.get(section_enum, {})
            sections.append({
                "section_id": section_id,
                "title": meta.get("title", section_id),
                "description": meta.get("description", ""),
                "order": meta.get("order", 50),
            })
        except ValueError:
            sections.append({
                "section_id": section_id,
                "title": section_id,
                "description": "",
                "order": 50,
            })

    # Sort by order
    sections.sort(key=lambda s: s["order"])

    return {
        "tier": tier.value,
        "section_count": len(sections),
        "sections": sections,
    }


@router.get("/preview/{session_id}")
async def preview_report(
    session_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Get a preview of what would be included in each tier.

    Returns a summary without generating the full report.
    Useful for showing users what they get with each tier before purchase.
    """
    if not check_report_access(user, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session",
        )

    from export.premium_report_generator import (
        get_tier_pricing,
        get_tier_sections,
    )

    pricing = get_tier_pricing()
    previews = {}

    for tier_key, info in pricing.items():
        user_pricing = get_pricing_for_user(user, tier_key)
        sections = get_tier_sections(tier_key)

        previews[tier_key] = {
            "price": user_pricing["price"],
            "label": info["label"],
            "description": info["description"],
            "section_count": len(sections),
            "includes": sections,
            "highlights": _get_tier_highlights(tier_key),
        }

    return {
        "session_id": session_id,
        "tiers": previews,
        "recommended": "premium",  # Could be dynamic based on user's situation
    }


def _get_tier_highlights(tier: str) -> List[str]:
    """Get marketing highlights for a tier."""
    highlights = {
        "basic": [
            "Tax calculation summary",
            "Draft Form 1040 preview",
            "Basic computation statement",
        ],
        "standard": [
            "Everything in Basic",
            "Credit eligibility analysis",
            "Deduction optimization",
            "Filing status comparison",
            "What-if scenario analysis",
            "Retirement contribution strategy",
        ],
        "premium": [
            "Everything in Standard",
            "Prioritized action items",
            "Multi-year tax projection",
            "Entity structure analysis",
            "Investment tax planning",
            "Full IRC citations",
            "Downloadable PDF report",
            "Detailed calculation appendix",
        ],
    }
    return highlights.get(tier, [])


# =============================================================================
# CPA-SPECIFIC ENDPOINTS
# =============================================================================

@router.post("/cpa/generate-for-client")
async def generate_report_for_client(
    client_id: str = Query(..., description="Client user ID"),
    session_id: str = Query(..., description="Tax session ID"),
    tier: ReportTierRequest = Query(default=ReportTierRequest.PREMIUM),
    format: ReportFormatRequest = Query(default=ReportFormatRequest.HTML),
    user: UserContext = Depends(get_current_user),
):
    """
    CPA endpoint to generate a report for one of their clients.

    Only accessible by partner/staff users.
    The CPA can then deliver this to their client with their own pricing.
    """
    # Verify user is CPA team member
    if user.user_type != UserType.CPA_TEAM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only for CPA team members",
        )

    # In production, verify client belongs to CPA's firm
    # For now, proceed with generation

    try:
        from export.premium_report_generator import (
            PremiumReportGenerator,
            ReportTier,
            ReportFormat,
        )

        generator = PremiumReportGenerator()
        report = generator.generate(
            session_id=session_id,
            tier=ReportTier(tier.value),
            format=ReportFormat(format.value),
        )

        if report.metadata.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=report.metadata["error"],
            )

        return {
            "report_id": report.report_id,
            "client_id": client_id,
            "session_id": session_id,
            "tier": report.tier.value,
            "generated_at": report.generated_at,
            "taxpayer_name": report.taxpayer_name,
            "section_count": len(report.sections),
            "action_items": [item.to_dict() for item in report.action_items],
            "html_content": report.html_content if format == ReportFormatRequest.HTML else None,
            "message": "Report generated. You can now deliver this to your client with your pricing.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CPA report generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(e)}",
        )


@router.get("/cpa/pricing")
async def get_cpa_pricing_settings(
    user: UserContext = Depends(get_current_user),
):
    """
    Get CPA firm's custom pricing settings for reports.

    Only accessible by partner/staff users.
    """
    if user.user_type != UserType.CPA_TEAM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only for CPA team members",
        )

    # In production, fetch from firm settings
    # For now, return default platform pricing as starting point
    return {
        "firm_id": user.firm_id,
        "pricing": {
            "basic": {"price": 0, "enabled": True},
            "standard": {"price": 99, "enabled": True},  # CPA can charge more
            "premium": {"price": 299, "enabled": True},
        },
        "notes": "Pricing is customizable in your firm settings",
    }
