"""
Superadmin Routes - Platform administration endpoints.

Provides:
- Multi-firm management
- Subscription oversight
- Feature flag management
- System health monitoring

Access restricted to platform admins only.
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..auth.rbac import (
    get_current_user,
    TenantContext,
    require_platform_admin,
)

router = APIRouter(tags=["Platform Admin"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class FirmSummary(BaseModel):
    """Firm summary for list view."""
    firm_id: str
    name: str
    subscription_tier: str
    subscription_status: str
    team_members: int
    clients: int
    returns_this_month: int
    health_score: int
    churn_risk: str  # low, medium, high
    created_at: datetime
    last_activity_at: Optional[datetime]


class FirmDetails(BaseModel):
    """Detailed firm information."""
    firm_id: str
    name: str
    legal_name: Optional[str]
    ein: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    subscription_tier: str
    subscription_status: str
    billing_cycle: str
    current_period_end: Optional[datetime]
    team_members: int
    max_team_members: int
    clients: int
    max_clients: int
    usage_this_month: dict
    health_score: int
    compliance_score: int
    created_at: datetime
    onboarded_at: Optional[datetime]


class PlatformMetrics(BaseModel):
    """Platform-wide metrics."""
    total_firms: int
    active_firms: int
    trial_firms: int
    total_mrr: float
    tier_distribution: dict
    churn_rate: float
    avg_health_score: float
    feature_adoption: dict


class FeatureFlagSummary(BaseModel):
    """Feature flag summary."""
    flag_id: str
    feature_key: str
    name: str
    description: Optional[str]
    is_enabled_globally: bool
    min_tier: Optional[str]
    rollout_percentage: int
    enabled_firms: int
    usage_this_month: int


class SystemHealth(BaseModel):
    """System health status."""
    status: str  # healthy, degraded, down
    services: dict
    error_rate_1h: float
    avg_response_time_ms: float
    active_jobs: int
    failed_jobs_1h: int


# =============================================================================
# FIRMS ROUTES
# =============================================================================

@router.get("/firms", response_model=List[FirmSummary])
@require_platform_admin
async def list_all_firms(
    user: TenantContext = Depends(get_current_user),
    tier: Optional[str] = Query(None, description="Filter by subscription tier"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all firms on the platform.

    Platform admins only. Supports filtering, search, and pagination.
    """
    # TODO: Implement actual query
    return [
        FirmSummary(
            firm_id="firm-1",
            name="Demo Tax Practice",
            subscription_tier="professional",
            subscription_status="active",
            team_members=5,
            clients=156,
            returns_this_month=47,
            health_score=94,
            churn_risk="low",
            created_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
        ),
        FirmSummary(
            firm_id="firm-2",
            name="Smith & Associates",
            subscription_tier="enterprise",
            subscription_status="active",
            team_members=12,
            clients=450,
            returns_this_month=89,
            health_score=98,
            churn_risk="low",
            created_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
        ),
    ]


@router.get("/firms/{firm_id}", response_model=FirmDetails)
@require_platform_admin
async def get_firm_details(
    firm_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get detailed information about a specific firm."""
    # TODO: Implement actual query
    return FirmDetails(
        firm_id=firm_id,
        name="Demo Tax Practice",
        legal_name="Demo Tax Practice LLC",
        ein="12-3456789",
        email="contact@demotax.com",
        phone="555-0100",
        address="123 Main St, San Francisco, CA 94105",
        subscription_tier="professional",
        subscription_status="active",
        billing_cycle="monthly",
        current_period_end=datetime.utcnow(),
        team_members=5,
        max_team_members=10,
        clients=156,
        max_clients=500,
        usage_this_month={
            "returns": 47,
            "scenarios": 234,
            "documents": 312,
        },
        health_score=94,
        compliance_score=96,
        created_at=datetime.utcnow(),
        onboarded_at=datetime.utcnow(),
    )


@router.post("/firms/{firm_id}/impersonate")
@require_platform_admin
async def impersonate_firm(
    firm_id: str,
    user: TenantContext = Depends(get_current_user),
    reason: str = Query(..., description="Reason for impersonation (logged)"),
):
    """
    Enter support mode for a firm.

    Creates a temporary session with firm admin access.
    All actions are logged with the original admin ID.
    """
    # TODO: Implement impersonation
    # - Log impersonation start with reason
    # - Create temporary token with firm context
    # - Set flag indicating impersonation mode

    return {
        "status": "success",
        "impersonation_token": "imp_token_xxx",
        "firm_name": "Demo Tax Practice",
        "expires_in": 3600,
        "note": "All actions will be logged under your admin account",
    }


# =============================================================================
# SUBSCRIPTION METRICS ROUTES
# =============================================================================

@router.get("/dashboard", response_model=PlatformMetrics)
@require_platform_admin
async def get_platform_dashboard(
    user: TenantContext = Depends(get_current_user),
):
    """
    Get platform-wide dashboard metrics.

    Includes MRR, churn, tier distribution, and feature adoption.
    """
    return PlatformMetrics(
        total_firms=234,
        active_firms=218,
        trial_firms=16,
        total_mrr=98500.00,
        tier_distribution={
            "starter": 120,
            "professional": 95,
            "enterprise": 19,
        },
        churn_rate=2.3,
        avg_health_score=89,
        feature_adoption={
            "scenario_analysis": 87,
            "multi_state": 45,
            "api_access": 19,
            "lead_magnet": 62,
        },
    )


@router.get("/subscriptions/mrr")
@require_platform_admin
async def get_mrr_breakdown(
    user: TenantContext = Depends(get_current_user),
    period: str = Query("month", description="month, quarter, year"),
):
    """
    Get MRR breakdown and trends.

    Includes breakdown by tier and growth trends.
    """
    return {
        "total_mrr": 98500.00,
        "by_tier": {
            "starter": {"count": 120, "mrr": 23880.00},
            "professional": {"count": 95, "mrr": 47405.00},
            "enterprise": {"count": 19, "mrr": 18981.00},
        },
        "trends": {
            "previous_period": 94200.00,
            "change": 4300.00,
            "change_percent": 4.56,
        },
        "forecast_next_month": 101200.00,
    }


@router.get("/subscriptions/churn")
@require_platform_admin
async def get_churn_analysis(
    user: TenantContext = Depends(get_current_user),
    period: str = Query("quarter", description="month, quarter, year"),
):
    """
    Get churn analysis.

    Includes churn rate, reasons, and at-risk firms.
    """
    return {
        "churn_rate": 2.3,
        "churned_firms": 5,
        "at_risk_firms": 12,
        "by_tier": {
            "starter": {"churned": 3, "rate": 2.5},
            "professional": {"churned": 2, "rate": 2.1},
            "enterprise": {"churned": 0, "rate": 0.0},
        },
        "top_reasons": [
            {"reason": "Price", "count": 2},
            {"reason": "Features missing", "count": 2},
            {"reason": "Business closed", "count": 1},
        ],
        "at_risk_list": [
            {"firm_id": "firm-x", "name": "XYZ Tax", "risk_score": 78, "signals": ["low_usage", "support_tickets"]},
        ],
    }


# =============================================================================
# FEATURE FLAGS ROUTES
# =============================================================================

@router.get("/features", response_model=List[FeatureFlagSummary])
@require_platform_admin
async def list_feature_flags(
    user: TenantContext = Depends(get_current_user),
):
    """List all feature flags."""
    return [
        FeatureFlagSummary(
            flag_id="flag-1",
            feature_key="multi_state_analysis",
            name="Multi-State Analysis",
            description="Support for clients with income in multiple states",
            is_enabled_globally=True,
            min_tier="professional",
            rollout_percentage=100,
            enabled_firms=114,
            usage_this_month=1234,
        ),
        FeatureFlagSummary(
            flag_id="flag-2",
            feature_key="ai_recommendations_v2",
            name="AI Recommendations v2",
            description="Enhanced AI-powered tax optimization recommendations",
            is_enabled_globally=False,
            min_tier=None,
            rollout_percentage=25,
            enabled_firms=58,
            usage_this_month=456,
        ),
    ]


@router.post("/features")
@require_platform_admin
async def create_feature_flag(
    feature_key: str,
    name: str,
    description: Optional[str] = None,
    min_tier: Optional[str] = None,
    user: TenantContext = Depends(get_current_user),
):
    """Create a new feature flag."""
    return {
        "status": "success",
        "flag_id": "flag-new",
        "feature_key": feature_key,
    }


@router.put("/features/{flag_id}")
@require_platform_admin
async def update_feature_flag(
    flag_id: str,
    is_enabled_globally: Optional[bool] = None,
    min_tier: Optional[str] = None,
    rollout_percentage: Optional[int] = Query(None, ge=0, le=100),
    user: TenantContext = Depends(get_current_user),
):
    """Update a feature flag."""
    return {"status": "success", "flag_id": flag_id}


@router.post("/features/{flag_id}/rollout")
@require_platform_admin
async def adjust_rollout(
    flag_id: str,
    percentage: int = Query(..., ge=0, le=100),
    user: TenantContext = Depends(get_current_user),
):
    """Adjust rollout percentage for a feature flag."""
    return {
        "status": "success",
        "flag_id": flag_id,
        "new_percentage": percentage,
        "affected_firms": 50,  # Estimated
    }


# =============================================================================
# SYSTEM HEALTH ROUTES
# =============================================================================

@router.get("/system/health", response_model=SystemHealth)
@require_platform_admin
async def get_system_health(
    user: TenantContext = Depends(get_current_user),
):
    """Get system health status."""
    return SystemHealth(
        status="healthy",
        services={
            "api": {"status": "healthy", "latency_ms": 45},
            "database": {"status": "healthy", "connections": 25},
            "redis": {"status": "healthy", "memory_mb": 128},
            "celery": {"status": "healthy", "workers": 4},
            "ocr": {"status": "healthy", "queue_size": 12},
        },
        error_rate_1h=0.02,
        avg_response_time_ms=87,
        active_jobs=45,
        failed_jobs_1h=2,
    )


@router.get("/system/errors")
@require_platform_admin
async def get_error_logs(
    user: TenantContext = Depends(get_current_user),
    severity: Optional[str] = Query(None, description="error, critical"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent error logs."""
    return {
        "errors": [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "error",
                "message": "OCR processing failed",
                "service": "ocr",
                "count": 3,
                "sample_request_id": "req-123",
            },
        ],
        "summary": {
            "total_1h": 5,
            "by_severity": {"error": 5, "critical": 0},
            "by_service": {"ocr": 3, "api": 2},
        },
    }


@router.post("/system/announcements")
@require_platform_admin
async def create_announcement(
    title: str,
    message: str,
    severity: str = Query("info", description="info, warning, urgent"),
    target_tiers: Optional[List[str]] = Query(None, description="Target subscription tiers"),
    user: TenantContext = Depends(get_current_user),
):
    """
    Create a system announcement.

    Announcements are shown to users on their dashboard.
    """
    return {
        "status": "success",
        "announcement_id": "ann-new",
        "will_reach_firms": 234,
    }
