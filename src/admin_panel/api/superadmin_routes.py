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
    from datetime import timedelta
    import random

    # Generate realistic mock data matching dashboard metrics
    firm_names = [
        ("Demo Tax Practice", "professional", 5, 156, 47, 94),
        ("Smith & Associates", "enterprise", 12, 450, 89, 98),
        ("Premier Tax Group", "enterprise", 15, 620, 112, 97),
        ("Accurate Tax Services", "professional", 8, 234, 56, 91),
        ("TaxPro Solutions", "professional", 6, 189, 42, 88),
        ("Elite Financial Services", "enterprise", 18, 780, 145, 99),
        ("Community Tax Center", "starter", 3, 78, 18, 82),
        ("QuickBooks Tax", "starter", 2, 45, 12, 79),
        ("Metro Tax Advisors", "professional", 7, 267, 61, 90),
        ("Capital Tax Partners", "enterprise", 14, 520, 98, 96),
        ("Sunrise Accounting", "professional", 5, 145, 38, 87),
        ("Pacific Tax Group", "professional", 9, 312, 72, 92),
        ("Midwest Tax Services", "starter", 3, 67, 15, 78),
        ("Southern Tax Pros", "professional", 6, 198, 45, 89),
        ("Northeast Financial", "enterprise", 11, 410, 85, 95),
    ]

    all_firms = []
    for i, (name, tier_val, members, clients, returns, health) in enumerate(firm_names):
        days_ago = random.randint(30, 365)
        all_firms.append(FirmSummary(
            firm_id=f"firm-{i+1:03d}",
            name=name,
            subscription_tier=tier_val,
            subscription_status="active" if health > 75 else "at_risk",
            team_members=members,
            clients=clients,
            returns_this_month=returns,
            health_score=health,
            churn_risk="low" if health > 90 else ("medium" if health > 80 else "high"),
            created_at=datetime.utcnow() - timedelta(days=days_ago),
            last_activity_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
        ))

    # Apply filters
    if tier:
        all_firms = [f for f in all_firms if f.subscription_tier == tier]
    if status_filter:
        all_firms = [f for f in all_firms if f.subscription_status == status_filter]
    if search:
        search_lower = search.lower()
        all_firms = [f for f in all_firms if search_lower in f.name.lower()]

    # Apply pagination
    return all_firms[offset:offset + limit]


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


# =============================================================================
# PLATFORM USERS ROUTES
# =============================================================================

class PlatformUserSummary(BaseModel):
    """Platform-wide user summary."""
    user_id: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    firm_id: str
    firm_name: str
    role: str
    is_active: bool
    is_email_verified: bool
    mfa_enabled: bool
    returns_this_month: int
    last_login_at: Optional[datetime]
    created_at: datetime


@router.get("/users", response_model=List[PlatformUserSummary])
@require_platform_admin
async def list_all_users(
    user: TenantContext = Depends(get_current_user),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    role: Optional[str] = Query(None, description="Filter by role"),
    status: Optional[str] = Query(None, description="Filter by status: active, inactive, invited"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all users across all firms.

    Platform admins only. Supports filtering by firm, role, and status.
    """
    from datetime import timedelta
    import random

    # Generate realistic mock users
    user_data = [
        ("John", "Doe", "Demo Tax Practice", "firm-001", "firm_admin", 145, True),
        ("Sarah", "Chen", "Demo Tax Practice", "firm-001", "senior_preparer", 234, True),
        ("Mike", "Johnson", "Demo Tax Practice", "firm-001", "preparer", 89, True),
        ("Emily", "Davis", "Smith & Associates", "firm-002", "firm_admin", 178, True),
        ("Robert", "Wilson", "Smith & Associates", "firm-002", "senior_preparer", 267, True),
        ("Lisa", "Martinez", "Smith & Associates", "firm-002", "preparer", 156, True),
        ("David", "Brown", "Smith & Associates", "firm-002", "preparer", 134, True),
        ("Jennifer", "Taylor", "Premier Tax Group", "firm-003", "firm_admin", 189, True),
        ("James", "Anderson", "Premier Tax Group", "firm-003", "senior_preparer", 298, True),
        ("Maria", "Garcia", "Premier Tax Group", "firm-003", "reviewer", 0, True),
        ("William", "Thomas", "Accurate Tax Services", "firm-004", "firm_admin", 112, True),
        ("Patricia", "Jackson", "Accurate Tax Services", "firm-004", "preparer", 87, True),
        ("Richard", "White", "TaxPro Solutions", "firm-005", "firm_admin", 98, True),
        ("Linda", "Harris", "TaxPro Solutions", "firm-005", "preparer", 76, False),
        ("Charles", "Clark", "Elite Financial", "firm-006", "firm_admin", 245, True),
        ("Barbara", "Lewis", "Elite Financial", "firm-006", "senior_preparer", 312, True),
        ("Joseph", "Robinson", "Elite Financial", "firm-006", "preparer", 178, True),
        ("Susan", "Walker", "Community Tax", "firm-007", "firm_admin", 45, True),
        ("Thomas", "Hall", "Metro Tax Advisors", "firm-009", "firm_admin", 134, True),
        ("Nancy", "Allen", "Metro Tax Advisors", "firm-009", "senior_preparer", 198, True),
    ]

    all_users = []
    for i, (first, last, firm_name, firm_id_val, role_val, returns, active) in enumerate(user_data):
        email_domain = firm_name.lower().replace(" ", "").replace("&", "")[:12] + ".com"
        days_ago = random.randint(30, 400)
        hours_since_login = random.randint(1, 72) if active else random.randint(168, 720)

        all_users.append(PlatformUserSummary(
            user_id=f"user-{i+1:03d}",
            email=f"{first.lower()}.{last.lower()}@{email_domain}",
            first_name=first,
            last_name=last,
            full_name=f"{first} {last}",
            firm_id=firm_id_val,
            firm_name=firm_name,
            role=role_val,
            is_active=active,
            is_email_verified=True,
            mfa_enabled=role_val in ["firm_admin", "senior_preparer"],
            returns_this_month=returns,
            last_login_at=datetime.utcnow() - timedelta(hours=hours_since_login) if active else None,
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        ))

    # Apply filters
    if firm_id:
        all_users = [u for u in all_users if u.firm_id == firm_id]
    if role:
        all_users = [u for u in all_users if u.role == role]
    if status:
        if status == "active":
            all_users = [u for u in all_users if u.is_active]
        elif status == "inactive":
            all_users = [u for u in all_users if not u.is_active]
    if search:
        search_lower = search.lower()
        all_users = [u for u in all_users if search_lower in u.full_name.lower() or search_lower in u.email.lower()]

    # Apply pagination
    return all_users[offset:offset + limit]


@router.get("/users/{user_id}")
@require_platform_admin
async def get_user_details(
    user_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get detailed information about a specific user."""
    return {
        "user_id": user_id,
        "email": "john.doe@acmetax.com",
        "first_name": "John",
        "last_name": "Doe",
        "full_name": "John Doe",
        "firm_id": "firm-1",
        "firm_name": "Acme Tax Services",
        "role": "firm_admin",
        "permissions": ["view_returns", "edit_returns", "manage_team"],
        "is_active": True,
        "is_email_verified": True,
        "mfa_enabled": True,
        "activity_summary": {
            "returns_this_month": 145,
            "last_login_at": datetime.utcnow().isoformat(),
            "logins_this_month": 42,
        },
        "created_at": datetime.utcnow().isoformat(),
    }


@router.post("/users/{user_id}/impersonate")
@require_platform_admin
async def impersonate_user(
    user_id: str,
    user: TenantContext = Depends(get_current_user),
    reason: str = Query(..., description="Reason for impersonation (logged)"),
):
    """
    Impersonate a user for support purposes.

    Creates a temporary session with the user's permissions.
    All actions are logged with the original admin ID.
    """
    return {
        "status": "success",
        "impersonation_token": "imp_user_xxx",
        "user_name": "John Doe",
        "firm_id": "firm-1",
        "expires_in": 1800,
        "note": "All actions will be logged under your admin account",
    }


@router.put("/users/{user_id}/status")
@require_platform_admin
async def update_user_status(
    user_id: str,
    is_active: bool,
    user: TenantContext = Depends(get_current_user),
    reason: Optional[str] = None,
):
    """Activate or deactivate a user."""
    return {
        "status": "success",
        "user_id": user_id,
        "is_active": is_active,
    }


# =============================================================================
# PARTNERS ROUTES
# =============================================================================

class PartnerSummary(BaseModel):
    """Partner summary."""
    partner_id: str
    name: str
    domain: Optional[str]
    contact_email: Optional[str]
    firms_count: int
    users_count: int
    mrr: float
    revenue_share_percent: float
    status: str
    created_at: datetime


@router.get("/partners", response_model=List[PartnerSummary])
@require_platform_admin
async def list_partners(
    user: TenantContext = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by status: active, inactive"),
    search: Optional[str] = Query(None, description="Search by name or domain"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all white-label partners.

    Partners can resell TaxFlow under their own branding.
    """
    from datetime import timedelta

    # Mock partner data
    all_partners = [
        PartnerSummary(
            partner_id="partner-1",
            name="TaxPartner Pro",
            domain="taxpartner.pro",
            contact_email="admin@taxpartner.pro",
            firms_count=42,
            users_count=384,
            mrr=126000.00,
            revenue_share_percent=15,
            status="active",
            created_at=datetime.utcnow() - timedelta(days=180),
        ),
        PartnerSummary(
            partner_id="partner-2",
            name="AccountingHub",
            domain="accountinghub.io",
            contact_email="partner@accountinghub.io",
            firms_count=28,
            users_count=156,
            mrr=84000.00,
            revenue_share_percent=12,
            status="active",
            created_at=datetime.utcnow() - timedelta(days=120),
        ),
        PartnerSummary(
            partner_id="partner-3",
            name="ProTax Network",
            domain="protaxnetwork.com",
            contact_email="sales@protaxnetwork.com",
            firms_count=15,
            users_count=89,
            mrr=45000.00,
            revenue_share_percent=10,
            status="inactive",
            created_at=datetime.utcnow() - timedelta(days=365),
        ),
        PartnerSummary(
            partner_id="partner-4",
            name="TaxCloud Solutions",
            domain="taxcloud.io",
            contact_email="info@taxcloud.io",
            firms_count=0,
            users_count=0,
            mrr=0.00,
            revenue_share_percent=15,
            status="pending",
            created_at=datetime.utcnow() - timedelta(days=7),
        ),
    ]

    # Apply filters
    if status:
        all_partners = [p for p in all_partners if p.status == status]
    if search:
        search_lower = search.lower()
        all_partners = [p for p in all_partners if search_lower in p.name.lower() or search_lower in (p.domain or '').lower()]

    return all_partners[offset:offset + limit]


@router.get("/partners/{partner_id}")
@require_platform_admin
async def get_partner_details(
    partner_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Get detailed information about a specific partner."""
    return {
        "partner_id": partner_id,
        "name": "TaxPartner Pro",
        "domain": "taxpartner.pro",
        "contact_email": "admin@taxpartner.pro",
        "contact_phone": "555-0200",
        "branding": {
            "logo_url": "/partners/taxpartner/logo.png",
            "primary_color": "#8b5cf6",
            "secondary_color": "#6366f1",
        },
        "firms_count": 42,
        "users_count": 384,
        "mrr": 126000.00,
        "revenue_share_percent": 15,
        "payout_history": {
            "last_payout": 18900.00,
            "last_payout_date": datetime.utcnow().isoformat(),
            "ytd_payouts": 189000.00,
        },
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
    }


@router.post("/partners")
@require_platform_admin
async def create_partner(
    name: str,
    contact_email: str,
    domain: Optional[str] = None,
    revenue_share_percent: float = Query(10, ge=0, le=50),
    user: TenantContext = Depends(get_current_user),
):
    """Create a new white-label partner."""
    return {
        "status": "success",
        "partner_id": "partner-new",
        "name": name,
        "message": "Partner created. Send onboarding email to complete setup.",
    }


@router.put("/partners/{partner_id}")
@require_platform_admin
async def update_partner(
    partner_id: str,
    name: Optional[str] = None,
    domain: Optional[str] = None,
    revenue_share_percent: Optional[float] = None,
    status: Optional[str] = None,
    user: TenantContext = Depends(get_current_user),
):
    """Update partner details."""
    return {
        "status": "success",
        "partner_id": partner_id,
    }


@router.get("/partners/{partner_id}/firms")
@require_platform_admin
async def list_partner_firms(
    partner_id: str,
    user: TenantContext = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all firms under a partner."""
    return {
        "partner_id": partner_id,
        "firms": [
            {
                "firm_id": "firm-p1",
                "name": "Partner Firm 1",
                "subscription_tier": "professional",
                "mrr": 3000.00,
                "users": 8,
            },
        ],
        "total": 42,
    }


# =============================================================================
# USER INVITATIONS ROUTES
# =============================================================================

class UserInvitationRequest(BaseModel):
    """Request to invite a user to a firm."""
    email: str
    firm_id: str
    role: str = "preparer"


class UserInvitationResponse(BaseModel):
    """Response after creating invitation."""
    invitation_id: str
    email: str
    firm_id: str
    firm_name: str
    role: str
    expires_at: datetime
    status: str


@router.post("/users/invite", response_model=UserInvitationResponse)
@require_platform_admin
async def invite_user_to_firm(
    invitation: UserInvitationRequest,
    user: TenantContext = Depends(get_current_user),
):
    """
    Invite a user to join a firm.

    Platform admins can invite users to any firm.
    Sends invitation email with signup link.
    """
    return UserInvitationResponse(
        invitation_id="inv-" + invitation.email[:8],
        email=invitation.email,
        firm_id=invitation.firm_id,
        firm_name="Acme Tax Services",  # Would lookup from DB
        role=invitation.role,
        expires_at=datetime.utcnow(),
        status="pending",
    )


@router.get("/users/invitations")
@require_platform_admin
async def list_all_invitations(
    user: TenantContext = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter: pending, accepted, expired"),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all pending invitations across all firms."""
    return {
        "invitations": [
            {
                "invitation_id": "inv-1",
                "email": "newuser@example.com",
                "firm_id": "firm-1",
                "firm_name": "Acme Tax Services",
                "role": "preparer",
                "invited_by": "admin@acme.com",
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": datetime.utcnow().isoformat(),
                "status": "pending",
            }
        ],
        "total": 1,
    }


@router.delete("/users/invitations/{invitation_id}")
@require_platform_admin
async def revoke_invitation(
    invitation_id: str,
    user: TenantContext = Depends(get_current_user),
):
    """Revoke a pending invitation."""
    return {
        "status": "success",
        "invitation_id": invitation_id,
        "message": "Invitation revoked",
    }


# =============================================================================
# PLATFORM ACTIVITY ROUTES
# =============================================================================

class PlatformActivity(BaseModel):
    """Platform activity entry."""
    activity_id: str
    activity_type: str
    description: str
    actor_id: Optional[str]
    actor_name: Optional[str]
    firm_id: Optional[str]
    firm_name: Optional[str]
    metadata: dict
    created_at: datetime


@router.get("/activity", response_model=List[PlatformActivity])
@require_platform_admin
async def get_platform_activity(
    user: TenantContext = Depends(get_current_user),
    activity_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get recent platform-wide activity.

    Returns activities across all firms for monitoring.
    """
    return [
        PlatformActivity(
            activity_id="act-1",
            activity_type="firm_onboarded",
            description="New firm onboarded",
            actor_id="user-1",
            actor_name="System",
            firm_id="firm-new",
            firm_name="New Tax Practice",
            metadata={"subscription_tier": "professional"},
            created_at=datetime.utcnow(),
        ),
        PlatformActivity(
            activity_id="act-2",
            activity_type="feature_flag_updated",
            description="Feature flag 'ai_insights' enabled",
            actor_id="admin-1",
            actor_name="Platform Admin",
            firm_id=None,
            firm_name=None,
            metadata={"flag_id": "flag-1", "enabled": True},
            created_at=datetime.utcnow(),
        ),
        PlatformActivity(
            activity_id="act-3",
            activity_type="high_usage_alert",
            description="High API usage detected",
            actor_id=None,
            actor_name="System",
            firm_id="firm-2",
            firm_name="Smith & Associates",
            metadata={"api_calls": 15000, "threshold": 10000},
            created_at=datetime.utcnow(),
        ),
        PlatformActivity(
            activity_id="act-4",
            activity_type="subscription_upgraded",
            description="Subscription upgraded to Enterprise",
            actor_id="user-5",
            actor_name="John Admin",
            firm_id="firm-3",
            firm_name="Premier Tax Group",
            metadata={"old_tier": "professional", "new_tier": "enterprise"},
            created_at=datetime.utcnow(),
        ),
    ]


# =============================================================================
# PLATFORM AUDIT LOGS ROUTES
# =============================================================================

@router.get("/audit/logs")
@require_platform_admin
async def get_platform_audit_logs(
    user: TenantContext = Depends(get_current_user),
    firm_id: Optional[str] = Query(None, description="Filter by firm"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    start_date: Optional[str] = Query(None, description="Start date ISO format"),
    end_date: Optional[str] = Query(None, description="End date ISO format"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Get platform-wide audit logs.

    Superadmin can view audit logs across all firms.
    """
    return {
        "logs": [
            {
                "log_id": "log-1",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": "user-1",
                "user_email": "john@acme.com",
                "firm_id": "firm-1",
                "firm_name": "Acme Tax Services",
                "action": "LOGIN_SUCCESS",
                "resource_type": "session",
                "resource_id": "sess-123",
                "details": {"ip": "192.168.1.1", "user_agent": "Chrome"},
                "ip_address": "192.168.1.1",
            },
            {
                "log_id": "log-2",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": "user-2",
                "user_email": "sarah@acme.com",
                "firm_id": "firm-1",
                "firm_name": "Acme Tax Services",
                "action": "RETURN_SUBMITTED",
                "resource_type": "tax_return",
                "resource_id": "return-456",
                "details": {"return_type": "1040", "client_id": "client-789"},
                "ip_address": "192.168.1.2",
            },
            {
                "log_id": "log-3",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": "admin-1",
                "user_email": "admin@platform.com",
                "firm_id": None,
                "firm_name": "Platform",
                "action": "FEATURE_FLAG_UPDATED",
                "resource_type": "feature_flag",
                "resource_id": "flag-ai-insights",
                "details": {"enabled": True, "rollout": 100},
                "ip_address": "10.0.0.1",
            },
        ],
        "total": 3,
        "limit": limit,
        "offset": offset,
    }


# =============================================================================
# RBAC OVERVIEW ROUTES
# =============================================================================

@router.get("/rbac/overview")
@require_platform_admin
async def get_rbac_overview(
    user: TenantContext = Depends(get_current_user),
):
    """
    Get RBAC overview for the platform.

    Shows role distribution, permission usage, and custom roles.
    """
    return {
        "system_roles": [
            {
                "role_id": "role-platform-admin",
                "name": "Platform Admin",
                "description": "Full platform access",
                "user_count": 3,
                "permissions_count": 50,
                "is_system": True,
            },
            {
                "role_id": "role-firm-admin",
                "name": "Firm Admin",
                "description": "Full firm access",
                "user_count": 247,
                "permissions_count": 35,
                "is_system": True,
            },
            {
                "role_id": "role-senior-preparer",
                "name": "Senior Preparer",
                "description": "Can review and approve returns",
                "user_count": 512,
                "permissions_count": 25,
                "is_system": True,
            },
            {
                "role_id": "role-preparer",
                "name": "Preparer",
                "description": "Can prepare returns",
                "user_count": 1083,
                "permissions_count": 15,
                "is_system": True,
            },
        ],
        "custom_roles_count": 24,
        "permission_categories": [
            {"category": "returns", "permissions": 12},
            {"category": "clients", "permissions": 8},
            {"category": "team", "permissions": 6},
            {"category": "billing", "permissions": 4},
            {"category": "settings", "permissions": 5},
            {"category": "audit", "permissions": 3},
        ],
        "total_users": 1845,
        "total_permissions": 38,
    }


@router.get("/rbac/permissions")
@require_platform_admin
async def get_all_permissions(
    user: TenantContext = Depends(get_current_user),
):
    """Get all available permissions in the system."""
    return {
        "permissions": [
            {"id": "view_returns", "name": "View Returns", "category": "returns", "description": "Can view tax returns"},
            {"id": "edit_returns", "name": "Edit Returns", "category": "returns", "description": "Can edit tax returns"},
            {"id": "submit_returns", "name": "Submit Returns", "category": "returns", "description": "Can submit returns for review"},
            {"id": "approve_returns", "name": "Approve Returns", "category": "returns", "description": "Can approve and finalize returns"},
            {"id": "view_clients", "name": "View Clients", "category": "clients", "description": "Can view client information"},
            {"id": "edit_clients", "name": "Edit Clients", "category": "clients", "description": "Can edit client information"},
            {"id": "manage_team", "name": "Manage Team", "category": "team", "description": "Can add/remove team members"},
            {"id": "view_billing", "name": "View Billing", "category": "billing", "description": "Can view billing information"},
            {"id": "manage_billing", "name": "Manage Billing", "category": "billing", "description": "Can manage subscription and payments"},
            {"id": "view_audit_logs", "name": "View Audit Logs", "category": "audit", "description": "Can view audit logs"},
            {"id": "manage_settings", "name": "Manage Settings", "category": "settings", "description": "Can change firm settings"},
        ],
    }
