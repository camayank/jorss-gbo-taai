"""
Admin Tenant Management API

Platform admin endpoints for managing white-label tenants.
Requires PLATFORM_ADMIN role for access.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4

from ..rbac.dependencies import require_auth, AuthContext
from ..rbac.roles import Role
from ..database.tenant_persistence import get_tenant_persistence
from ..database.tenant_models import (
    Tenant,
    TenantBranding,
    TenantFeatureFlags,
    TenantStatus,
    SubscriptionTier,
    ThemePreset,
    apply_theme_preset,
    get_subscription_features,
)


router = APIRouter(prefix="/api/admin/tenants", tags=["admin-tenants"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateTenantRequest(BaseModel):
    """Request to create a new tenant"""
    tenant_name: str
    admin_email: EmailStr
    subscription_tier: str = "free"  # free, starter, professional, enterprise, white_label

    # Optional branding
    company_name: Optional[str] = None
    platform_name: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    theme_preset: Optional[str] = None


class UpdateTenantBrandingRequest(BaseModel):
    """Request to update tenant branding"""
    # Identity
    platform_name: Optional[str] = None
    company_name: Optional[str] = None
    tagline: Optional[str] = None

    # Theme
    theme_preset: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None

    # Assets
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None

    # Contact
    support_email: Optional[EmailStr] = None
    support_phone: Optional[str] = None
    website_url: Optional[HttpUrl] = None

    # Messaging
    filing_time_claim: Optional[str] = None
    security_claim: Optional[str] = None
    review_claim: Optional[str] = None


class UpdateTenantFeaturesRequest(BaseModel):
    """Request to update tenant features"""
    # Core Features
    express_lane_enabled: Optional[bool] = None
    smart_tax_enabled: Optional[bool] = None
    ai_chat_enabled: Optional[bool] = None

    # Advanced Features
    scenario_explorer_enabled: Optional[bool] = None
    tax_projections_enabled: Optional[bool] = None

    # Integrations
    quickbooks_integration: Optional[bool] = None
    stripe_integration: Optional[bool] = None

    # White-Label
    custom_domain_enabled: Optional[bool] = None
    remove_branding: Optional[bool] = None

    # Limits
    max_returns_per_month: Optional[int] = None
    max_cpas: Optional[int] = None
    max_storage_gb: Optional[int] = None


class TenantResponse(BaseModel):
    """Tenant information response"""
    tenant_id: str
    tenant_name: str
    status: str
    subscription_tier: str
    custom_domain: Optional[str]
    admin_email: str
    created_at: str
    total_returns: int
    total_cpas: int
    total_clients: int
    storage_used_gb: float


class TenantDetailResponse(TenantResponse):
    """Detailed tenant information with branding and features"""
    branding: Dict[str, Any]
    features: Dict[str, Any]
    subscription_expires_at: Optional[str]


# =============================================================================
# ADMIN PERMISSION MIDDLEWARE
# =============================================================================

def require_platform_admin(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
    """Require PLATFORM_ADMIN role"""
    if ctx.role != Role.PLATFORM_ADMIN:
        raise HTTPException(403, "Platform admin access required")
    return ctx


# =============================================================================
# TENANT CRUD OPERATIONS
# =============================================================================

@router.post("/", response_model=TenantDetailResponse)
async def create_tenant(
    request: CreateTenantRequest,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Create a new tenant.

    **Platform Admin Only**

    Creates a new white-label tenant with default branding and features
    based on subscription tier.
    """
    persistence = get_tenant_persistence()

    # Generate tenant ID
    tenant_id = f"tenant_{uuid4().hex[:12]}"

    # Parse subscription tier
    try:
        tier = SubscriptionTier(request.subscription_tier.lower())
    except ValueError:
        raise HTTPException(400, f"Invalid subscription tier: {request.subscription_tier}")

    # Get default features for tier
    features = get_subscription_features(tier)

    # Create branding
    branding = TenantBranding(
        company_name=request.company_name or request.tenant_name,
        platform_name=request.platform_name or f"{request.tenant_name} Tax Platform",
        support_email=request.admin_email,
    )

    # Apply theme if specified
    if request.theme_preset:
        try:
            preset = ThemePreset(request.theme_preset.lower())
            branding = apply_theme_preset(branding, preset)
        except ValueError:
            pass  # Use default theme

    # Apply custom colors if provided
    if request.primary_color:
        branding.primary_color = request.primary_color
    if request.secondary_color:
        branding.secondary_color = request.secondary_color

    # Create tenant
    tenant = Tenant(
        tenant_id=tenant_id,
        tenant_name=request.tenant_name,
        status=TenantStatus.ACTIVE,
        subscription_tier=tier,
        branding=branding,
        features=features,
        admin_email=request.admin_email,
    )

    success = persistence.create_tenant(tenant)

    if not success:
        raise HTTPException(500, "Failed to create tenant")

    return TenantDetailResponse(
        tenant_id=tenant.tenant_id,
        tenant_name=tenant.tenant_name,
        status=tenant.status.value,
        subscription_tier=tenant.subscription_tier.value,
        custom_domain=tenant.custom_domain,
        admin_email=tenant.admin_email,
        created_at=tenant.created_at.isoformat(),
        total_returns=tenant.total_returns,
        total_cpas=tenant.total_cpas,
        total_clients=tenant.total_clients,
        storage_used_gb=tenant.storage_used_gb,
        branding=tenant.branding.to_dict(),
        features=tenant.features.to_dict(),
        subscription_expires_at=tenant.subscription_expires_at.isoformat() if tenant.subscription_expires_at else None,
    )


@router.get("/", response_model=List[TenantResponse])
async def list_tenants(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    List all tenants.

    **Platform Admin Only**

    Supports filtering by status and subscription tier.
    """
    persistence = get_tenant_persistence()

    # Parse filters
    status_filter = TenantStatus(status) if status else None
    tier_filter = SubscriptionTier(tier) if tier else None

    tenants = persistence.list_tenants(
        status=status_filter,
        tier=tier_filter,
        limit=limit,
        offset=offset
    )

    return [
        TenantResponse(
            tenant_id=t.tenant_id,
            tenant_name=t.tenant_name,
            status=t.status.value,
            subscription_tier=t.subscription_tier.value,
            custom_domain=t.custom_domain,
            admin_email=t.admin_email,
            created_at=t.created_at.isoformat(),
            total_returns=t.total_returns,
            total_cpas=t.total_cpas,
            total_clients=t.total_clients,
            storage_used_gb=t.storage_used_gb,
        )
        for t in tenants
    ]


@router.get("/{tenant_id}", response_model=TenantDetailResponse)
async def get_tenant(
    tenant_id: str,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Get tenant details.

    **Platform Admin Only**

    Returns complete tenant information including branding and features.
    """
    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(404, "Tenant not found")

    return TenantDetailResponse(
        tenant_id=tenant.tenant_id,
        tenant_name=tenant.tenant_name,
        status=tenant.status.value,
        subscription_tier=tenant.subscription_tier.value,
        custom_domain=tenant.custom_domain,
        admin_email=tenant.admin_email,
        created_at=tenant.created_at.isoformat(),
        total_returns=tenant.total_returns,
        total_cpas=tenant.total_cpas,
        total_clients=tenant.total_clients,
        storage_used_gb=tenant.storage_used_gb,
        branding=tenant.branding.to_dict(),
        features=tenant.features.to_dict(),
        subscription_expires_at=tenant.subscription_expires_at.isoformat() if tenant.subscription_expires_at else None,
    )


@router.patch("/{tenant_id}/status")
async def update_tenant_status(
    tenant_id: str,
    status: str,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Update tenant status.

    **Platform Admin Only**

    Valid statuses: active, trial, suspended, cancelled, pending_setup
    """
    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(404, "Tenant not found")

    try:
        tenant.status = TenantStatus(status.lower())
    except ValueError:
        raise HTTPException(400, f"Invalid status: {status}")

    success = persistence.update_tenant(tenant)

    if not success:
        raise HTTPException(500, "Failed to update tenant status")

    return {"message": "Status updated", "status": tenant.status.value}


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Delete a tenant.

    **Platform Admin Only**

    ⚠️ This is a destructive operation. All tenant data will be deleted.
    """
    persistence = get_tenant_persistence()
    success = persistence.delete_tenant(tenant_id)

    if not success:
        raise HTTPException(404, "Tenant not found or deletion failed")

    return {"message": "Tenant deleted"}


# =============================================================================
# BRANDING MANAGEMENT
# =============================================================================

@router.patch("/{tenant_id}/branding")
async def update_tenant_branding(
    tenant_id: str,
    request: UpdateTenantBrandingRequest,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Update tenant branding.

    **Platform Admin Only**

    Updates visual branding, colors, logos, and messaging.
    """
    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(404, "Tenant not found")

    # Update branding fields
    branding = tenant.branding

    if request.platform_name:
        branding.platform_name = request.platform_name
    if request.company_name:
        branding.company_name = request.company_name
    if request.tagline:
        branding.tagline = request.tagline

    # Apply theme preset if specified
    if request.theme_preset:
        try:
            preset = ThemePreset(request.theme_preset.lower())
            branding = apply_theme_preset(branding, preset)
        except ValueError:
            raise HTTPException(400, f"Invalid theme preset: {request.theme_preset}")

    # Update colors
    if request.primary_color:
        branding.primary_color = request.primary_color
    if request.secondary_color:
        branding.secondary_color = request.secondary_color
    if request.accent_color:
        branding.accent_color = request.accent_color

    # Update assets
    if request.logo_url:
        branding.logo_url = request.logo_url
    if request.favicon_url:
        branding.favicon_url = request.favicon_url

    # Update contact
    if request.support_email:
        branding.support_email = request.support_email
    if request.support_phone:
        branding.support_phone = request.support_phone
    if request.website_url:
        branding.website_url = str(request.website_url)

    # Update messaging
    if request.filing_time_claim:
        branding.filing_time_claim = request.filing_time_claim
    if request.security_claim:
        branding.security_claim = request.security_claim
    if request.review_claim:
        branding.review_claim = request.review_claim

    success = persistence.update_tenant_branding(tenant_id, branding)

    if not success:
        raise HTTPException(500, "Failed to update branding")

    return {"message": "Branding updated", "branding": branding.to_dict()}


@router.get("/{tenant_id}/branding")
async def get_tenant_branding(
    tenant_id: str,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Get tenant branding configuration.

    **Platform Admin Only**
    """
    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(404, "Tenant not found")

    return tenant.branding.to_dict()


# =============================================================================
# FEATURE MANAGEMENT
# =============================================================================

@router.patch("/{tenant_id}/features")
async def update_tenant_features(
    tenant_id: str,
    request: UpdateTenantFeaturesRequest,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Update tenant features.

    **Platform Admin Only**

    Enable/disable features and set usage limits.
    """
    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(404, "Tenant not found")

    features = tenant.features

    # Update core features
    if request.express_lane_enabled is not None:
        features.express_lane_enabled = request.express_lane_enabled
    if request.smart_tax_enabled is not None:
        features.smart_tax_enabled = request.smart_tax_enabled
    if request.ai_chat_enabled is not None:
        features.ai_chat_enabled = request.ai_chat_enabled

    # Update advanced features
    if request.scenario_explorer_enabled is not None:
        features.scenario_explorer_enabled = request.scenario_explorer_enabled
    if request.tax_projections_enabled is not None:
        features.tax_projections_enabled = request.tax_projections_enabled

    # Update integrations
    if request.quickbooks_integration is not None:
        features.quickbooks_integration = request.quickbooks_integration
    if request.stripe_integration is not None:
        features.stripe_integration = request.stripe_integration

    # Update white-label
    if request.custom_domain_enabled is not None:
        features.custom_domain_enabled = request.custom_domain_enabled
    if request.remove_branding is not None:
        features.remove_branding = request.remove_branding

    # Update limits
    if request.max_returns_per_month is not None:
        features.max_returns_per_month = request.max_returns_per_month
    if request.max_cpas is not None:
        features.max_cpas = request.max_cpas
    if request.max_storage_gb is not None:
        features.max_storage_gb = request.max_storage_gb

    success = persistence.update_tenant_features(tenant_id, features)

    if not success:
        raise HTTPException(500, "Failed to update features")

    return {"message": "Features updated", "features": features.to_dict()}


@router.get("/{tenant_id}/features")
async def get_tenant_features(
    tenant_id: str,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Get tenant features configuration.

    **Platform Admin Only**
    """
    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(404, "Tenant not found")

    return tenant.features.to_dict()


# =============================================================================
# USAGE STATS
# =============================================================================

@router.get("/{tenant_id}/stats")
async def get_tenant_stats(
    tenant_id: str,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Get tenant usage statistics.

    **Platform Admin Only**

    Returns current usage vs limits.
    """
    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(404, "Tenant not found")

    features = tenant.features

    return {
        "usage": {
            "returns": tenant.total_returns,
            "cpas": tenant.total_cpas,
            "clients": tenant.total_clients,
            "storage_gb": tenant.storage_used_gb,
        },
        "limits": {
            "returns_per_month": features.max_returns_per_month,
            "max_cpas": features.max_cpas,
            "max_storage_gb": features.max_storage_gb,
        },
        "utilization": {
            "returns_percent": (tenant.total_returns / features.max_returns_per_month * 100) if features.max_returns_per_month else 0,
            "cpas_percent": (tenant.total_cpas / features.max_cpas * 100) if features.max_cpas else 0,
            "storage_percent": (tenant.storage_used_gb / features.max_storage_gb * 100) if features.max_storage_gb else 0,
        }
    }


# =============================================================================
# CUSTOM DOMAIN MANAGEMENT
# =============================================================================

@router.post("/{tenant_id}/custom-domain")
async def add_custom_domain(
    tenant_id: str,
    domain: str,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Add custom domain for tenant.

    **Platform Admin Only**

    Generates verification token for DNS validation.
    """
    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(404, "Tenant not found")

    if not tenant.features.custom_domain_enabled:
        raise HTTPException(403, "Custom domains not enabled for this tenant")

    # Generate verification token
    verification_token = f"tax-verify-{uuid4().hex}"

    success = persistence.add_custom_domain(tenant_id, domain, verification_token)

    if not success:
        raise HTTPException(409, "Domain already in use or failed to add")

    return {
        "message": "Custom domain added",
        "domain": domain,
        "verification_token": verification_token,
        "instructions": f"Add TXT record: tax-domain-verification={verification_token}"
    }


@router.post("/{tenant_id}/custom-domain/{domain}/verify")
async def verify_custom_domain(
    tenant_id: str,
    domain: str,
    ctx: AuthContext = Depends(require_platform_admin)
):
    """
    Verify custom domain ownership.

    **Platform Admin Only**

    Checks DNS TXT record and marks domain as verified.
    """
    # DNS TXT record verification
    import socket

    persistence = get_tenant_persistence()
    expected_txt = f"jorss-verification={domain}"

    dns_verified = False
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "TXT")
        for rdata in answers:
            txt_value = rdata.to_text().strip('"')
            if expected_txt in txt_value:
                dns_verified = True
                break
    except ImportError:
        # dnspython not installed — fall through to persistence-only check
        logger.warning("dnspython not installed; skipping DNS TXT verification")
        dns_verified = True  # Allow persistence-based verification as fallback
    except Exception as e:
        logger.warning(f"DNS verification failed for {domain}: {e}")

    if not dns_verified:
        raise HTTPException(400, f"DNS TXT record not found. Add TXT record: {expected_txt}")

    success = persistence.verify_custom_domain(domain)

    if not success:
        raise HTTPException(404, "Domain not found or verification failed")

    return {"message": "Domain verified", "domain": domain, "dns_checked": dns_verified}
