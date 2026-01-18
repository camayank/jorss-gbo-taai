"""
Settings Routes - Firm settings and branding management endpoints.

Provides:
- Firm profile management
- Branding customization
- Security settings
- API key management (Enterprise)
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from pydantic import BaseModel, Field, EmailStr

from ..auth.rbac import (
    get_current_user,
    get_current_firm,
    TenantContext,
    require_permission,
    require_firm_admin,
)
from ..models.user import UserPermission

router = APIRouter(prefix="/settings", tags=["Settings"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class FirmProfile(BaseModel):
    """Firm profile information."""
    name: str
    legal_name: Optional[str]
    ein: Optional[str]
    email: Optional[EmailStr]
    phone: Optional[str]
    website: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]


class FirmProfileUpdate(BaseModel):
    """Update firm profile request."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    legal_name: Optional[str] = Field(None, max_length=255)
    ein: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=255)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=2)
    zip_code: Optional[str] = Field(None, max_length=10)


class BrandingSettings(BaseModel):
    """Firm branding settings."""
    logo_url: Optional[str]
    primary_color: str = "#059669"
    secondary_color: str = "#1e40af"
    custom_domain: Optional[str] = None  # Enterprise only
    email_signature: Optional[str] = None
    disclaimer_text: Optional[str] = None
    welcome_message: Optional[str] = None


class BrandingUpdate(BaseModel):
    """Update branding request."""
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    email_signature: Optional[str] = Field(None, max_length=1000)
    disclaimer_text: Optional[str] = Field(None, max_length=2000)
    welcome_message: Optional[str] = Field(None, max_length=1000)


class SecuritySettings(BaseModel):
    """Firm security settings."""
    mfa_required: bool = False
    session_timeout_minutes: int = 60
    password_expiry_days: int = 90
    ip_whitelist: Optional[List[str]] = None  # Enterprise only
    require_reviewer_approval: bool = True
    allow_self_review: bool = False


class SecuritySettingsUpdate(BaseModel):
    """Update security settings request."""
    mfa_required: Optional[bool] = None
    session_timeout_minutes: Optional[int] = Field(None, ge=15, le=480)
    password_expiry_days: Optional[int] = Field(None, ge=30, le=365)
    ip_whitelist: Optional[List[str]] = None
    require_reviewer_approval: Optional[bool] = None
    allow_self_review: Optional[bool] = None


class ApiKey(BaseModel):
    """API key information."""
    key_id: str
    name: str
    prefix: str  # First 8 chars of key
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool


class ApiKeyCreate(BaseModel):
    """Create API key request."""
    name: str = Field(..., min_length=1, max_length=100)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class ApiKeyCreated(BaseModel):
    """API key creation response (includes full key - only shown once)."""
    key_id: str
    name: str
    api_key: str  # Full key - only shown once!
    created_at: datetime
    expires_at: Optional[datetime]


class AllSettings(BaseModel):
    """Complete settings response."""
    profile: FirmProfile
    branding: BrandingSettings
    security: SecuritySettings
    integrations: dict
    api_keys_enabled: bool


# =============================================================================
# ROUTES
# =============================================================================

@router.get("", response_model=AllSettings)
async def get_all_settings(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    Get all firm settings.

    Returns profile, branding, security, and integration settings.
    """
    # TODO: Implement actual database query
    return AllSettings(
        profile=FirmProfile(
            name="Demo Tax Practice",
            legal_name="Demo Tax Practice LLC",
            ein="12-3456789",
            email="contact@demotax.com",
            phone="555-0100",
            website="https://demotax.com",
            address_line1="123 Main St",
            address_line2="Suite 400",
            city="San Francisco",
            state="CA",
            zip_code="94105",
        ),
        branding=BrandingSettings(
            logo_url="/static/logos/demo-tax.png",
            primary_color="#059669",
            secondary_color="#1e40af",
            email_signature="Thank you for choosing Demo Tax Practice.",
            disclaimer_text="This communication is for informational purposes only.",
        ),
        security=SecuritySettings(
            mfa_required=False,
            session_timeout_minutes=60,
            password_expiry_days=90,
            require_reviewer_approval=True,
            allow_self_review=False,
        ),
        integrations={
            "calendar_sync": False,
            "slack_notifications": False,
        },
        api_keys_enabled=False,  # Based on plan
    )


@router.get("/profile", response_model=FirmProfile)
async def get_firm_profile(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Get firm profile information."""
    # TODO: Implement actual query
    return FirmProfile(
        name="Demo Tax Practice",
        legal_name="Demo Tax Practice LLC",
        ein="12-3456789",
        email="contact@demotax.com",
        phone="555-0100",
        website="https://demotax.com",
        address_line1="123 Main St",
        address_line2="Suite 400",
        city="San Francisco",
        state="CA",
        zip_code="94105",
    )


@router.put("/profile", response_model=FirmProfile)
@require_firm_admin
async def update_firm_profile(
    update: FirmProfileUpdate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Update firm profile information."""
    # TODO: Implement actual update
    return FirmProfile(
        name=update.name or "Demo Tax Practice",
        legal_name=update.legal_name,
        ein=update.ein,
        email=update.email,
        phone=update.phone,
        website=update.website,
        address_line1=update.address_line1,
        address_line2=update.address_line2,
        city=update.city,
        state=update.state,
        zip_code=update.zip_code,
    )


@router.get("/branding", response_model=BrandingSettings)
async def get_branding_settings(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Get firm branding settings."""
    return BrandingSettings(
        logo_url="/static/logos/demo-tax.png",
        primary_color="#059669",
        secondary_color="#1e40af",
    )


@router.put("/branding", response_model=BrandingSettings)
@require_permission(UserPermission.UPDATE_BRANDING)
async def update_branding_settings(
    update: BrandingUpdate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Update firm branding settings."""
    # TODO: Implement actual update
    return BrandingSettings(
        logo_url="/static/logos/demo-tax.png",
        primary_color=update.primary_color or "#059669",
        secondary_color=update.secondary_color or "#1e40af",
        email_signature=update.email_signature,
        disclaimer_text=update.disclaimer_text,
        welcome_message=update.welcome_message,
    )


@router.post("/branding/logo")
@require_permission(UserPermission.UPDATE_BRANDING)
async def upload_logo(
    file: UploadFile = File(...),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    Upload firm logo.

    Accepted formats: PNG, JPG, SVG
    Max size: 2MB
    Recommended size: 200x200px
    """
    # Validate file
    allowed_types = {"image/png", "image/jpeg", "image/svg+xml"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}",
        )

    # TODO: Implement actual file upload
    # - Validate file size
    # - Store in S3/cloud storage
    # - Update firm record

    return {
        "status": "success",
        "logo_url": f"/static/logos/{firm_id}/logo.png",
    }


@router.get("/security", response_model=SecuritySettings)
async def get_security_settings(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Get firm security settings."""
    return SecuritySettings(
        mfa_required=False,
        session_timeout_minutes=60,
        password_expiry_days=90,
        require_reviewer_approval=True,
        allow_self_review=False,
    )


@router.put("/security", response_model=SecuritySettings)
@require_firm_admin
async def update_security_settings(
    update: SecuritySettingsUpdate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Update firm security settings."""
    # IP whitelist is Enterprise only
    if update.ip_whitelist is not None:
        # TODO: Check if firm is on Enterprise plan
        pass

    # TODO: Implement actual update
    return SecuritySettings(
        mfa_required=update.mfa_required if update.mfa_required is not None else False,
        session_timeout_minutes=update.session_timeout_minutes or 60,
        password_expiry_days=update.password_expiry_days or 90,
        ip_whitelist=update.ip_whitelist,
        require_reviewer_approval=update.require_reviewer_approval if update.require_reviewer_approval is not None else True,
        allow_self_review=update.allow_self_review if update.allow_self_review is not None else False,
    )


# =============================================================================
# API KEY ROUTES (ENTERPRISE ONLY)
# =============================================================================

@router.get("/api-keys", response_model=List[ApiKey])
@require_permission(UserPermission.MANAGE_API_KEYS)
async def list_api_keys(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    List all API keys for the firm.

    NOTE: Full keys are never shown after creation.
    """
    # TODO: Check if firm has API access (Enterprise plan)
    # TODO: Implement actual query
    return [
        ApiKey(
            key_id="key-1",
            name="Production Integration",
            prefix="tp_live_",
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow(),
            expires_at=None,
            is_active=True,
        ),
    ]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
@require_permission(UserPermission.MANAGE_API_KEYS)
async def create_api_key(
    request: ApiKeyCreate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    Create a new API key.

    IMPORTANT: The full API key is only shown once in this response.
    Store it securely - it cannot be retrieved later.
    """
    # TODO: Check if firm has API access (Enterprise plan)
    # TODO: Generate secure API key
    import secrets
    api_key = f"tp_live_{secrets.token_urlsafe(32)}"

    return ApiKeyCreated(
        key_id="key-new",
        name=request.name,
        api_key=api_key,
        created_at=datetime.utcnow(),
        expires_at=None,
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission(UserPermission.MANAGE_API_KEYS)
async def revoke_api_key(
    key_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Revoke an API key."""
    # TODO: Implement actual revocation
    return None
