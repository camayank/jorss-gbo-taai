"""
Settings Routes - Firm settings and branding management endpoints.

Provides:
- Firm profile management
- Branding customization
- Security settings
- API key management (Enterprise)

All routes use database-backed queries.
"""

import json
import logging
import secrets
import hashlib
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File

# Logo storage directory
LOGO_DIR = Path(__file__).parent.parent.parent / "web" / "static" / "logos"
LOGO_DIR.mkdir(parents=True, exist_ok=True)
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.rbac import (
    get_current_user,
    get_current_firm,
    TenantContext,
    require_permission,
    require_firm_admin,
)
from ..models.user import UserPermission
from database.async_engine import get_async_session

router = APIRouter(prefix="/settings", tags=["Settings"])
logger = logging.getLogger(__name__)

# Column whitelist for UPDATE queries — prevents SQL injection in dynamic SET clauses
_FIRM_UPDATABLE_COLUMNS = frozenset({
    "firm_name", "phone", "address", "city", "state", "zip_code",
    "website", "logo_url", "timezone", "billing_email",
    "name", "legal_name", "ein", "email", "address_line1",
    "address_line2", "updated_at",
})


def _parse_json_field(raw_value, default):
    """Parse JSON/JSONB fields safely across DB adapters."""
    if raw_value is None:
        return default
    if isinstance(raw_value, (dict, list)):
        return raw_value
    try:
        return json.loads(raw_value)
    except (TypeError, ValueError):
        return default


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
    secondary_color: str = "#1e3a5f"
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


class IntegrationSettingsUpdate(BaseModel):
    """Update integration settings request."""
    settings: dict = Field(default_factory=dict)


class OnboardingStatus(BaseModel):
    """Firm onboarding checklist status."""
    checklist: dict
    completed: int
    total: int
    percentage: int
    is_complete: bool


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
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get all firm settings.

    Returns profile, branding, security, and integration settings.
    """
    # Get firm data with settings
    query = text("""
        SELECT f.name, f.legal_name, f.ein, f.email, f.phone, f.website,
               f.address_line1, f.address_line2, f.city, f.state, f.zip_code,
               f.branding, f.security_settings, f.integrations,
               sp.features
        FROM firms f
        LEFT JOIN subscriptions s ON f.firm_id = s.firm_id AND s.status = 'active'
        LEFT JOIN subscription_plans sp ON s.plan_id = sp.plan_id
        WHERE f.firm_id = :firm_id
    """)
    result = await session.execute(query, {"firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    # Parse JSON fields
    branding = _parse_json_field(row[11], {})
    security = _parse_json_field(row[12], {})
    integrations = _parse_json_field(row[13], {})
    features = _parse_json_field(row[14], {})

    # Check if API keys are enabled (Enterprise feature)
    api_keys_enabled = features.get("api_access", False)

    return AllSettings(
        profile=FirmProfile(
            name=row[0] or "",
            legal_name=row[1],
            ein=row[2],
            email=row[3],
            phone=row[4],
            website=row[5],
            address_line1=row[6],
            address_line2=row[7],
            city=row[8],
            state=row[9],
            zip_code=row[10],
        ),
        branding=BrandingSettings(
            logo_url=branding.get("logo_url"),
            primary_color=branding.get("primary_color", "#059669"),
            secondary_color=branding.get("secondary_color", "#1e3a5f"),
            custom_domain=branding.get("custom_domain"),
            email_signature=branding.get("email_signature"),
            disclaimer_text=branding.get("disclaimer_text"),
            welcome_message=branding.get("welcome_message"),
        ),
        security=SecuritySettings(
            mfa_required=security.get("mfa_required", False),
            session_timeout_minutes=security.get("session_timeout_minutes", 60),
            password_expiry_days=security.get("password_expiry_days", 90),
            ip_whitelist=security.get("ip_whitelist"),
            require_reviewer_approval=security.get("require_reviewer_approval", True),
            allow_self_review=security.get("allow_self_review", False),
        ),
        integrations=integrations,
        api_keys_enabled=api_keys_enabled,
    )


@router.get("/onboarding-status", response_model=OnboardingStatus)
async def get_onboarding_status(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get launch onboarding checklist status for the current firm."""
    firm_result = await session.execute(
        text("""
            SELECT name, email, phone, branding, integrations
            FROM firms
            WHERE firm_id = :firm_id
            LIMIT 1
        """),
        {"firm_id": firm_id},
    )
    firm_row = firm_result.fetchone()
    if not firm_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    branding = _parse_json_field(firm_row[3], {})
    integrations = _parse_json_field(firm_row[4], {})

    sub_result = await session.execute(
        text("""
            SELECT status
            FROM subscriptions
            WHERE firm_id = :firm_id
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"firm_id": firm_id},
    )
    sub_row = sub_result.fetchone()
    subscription_status = (sub_row[0] if sub_row else "") or ""

    checklist = {
        "profile_completed": bool((firm_row[0] or "").strip() and (firm_row[1] or "").strip()),
        "branding_configured": bool(branding.get("logo_url") and branding.get("primary_color")),
        "lead_routing_configured": bool(
            integrations.get("lead_routing_email") or (firm_row[1] or "").strip()
        ),
        "calendar_configured": bool(integrations.get("booking_link")),
        "embed_verified": bool(integrations.get("embed_verified") or integrations.get("widget_installed")),
        "payment_configured": subscription_status in {"active", "trialing"},
    }

    completed = sum(1 for value in checklist.values() if value)
    total = len(checklist)
    percentage = int((completed / total) * 100) if total else 0

    return OnboardingStatus(
        checklist=checklist,
        completed=completed,
        total=total,
        percentage=percentage,
        is_complete=completed == total,
    )


@router.get("/profile", response_model=FirmProfile)
async def get_firm_profile(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get firm profile information."""
    query = text("""
        SELECT name, legal_name, ein, email, phone, website,
               address_line1, address_line2, city, state, zip_code
        FROM firms WHERE firm_id = :firm_id
    """)
    result = await session.execute(query, {"firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    return FirmProfile(
        name=row[0] or "",
        legal_name=row[1],
        ein=row[2],
        email=row[3],
        phone=row[4],
        website=row[5],
        address_line1=row[6],
        address_line2=row[7],
        city=row[8],
        state=row[9],
        zip_code=row[10],
    )


@router.put("/profile", response_model=FirmProfile)
@require_firm_admin
async def update_firm_profile(
    update: FirmProfileUpdate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update firm profile information."""
    # Build update fields
    updates = []
    params = {"firm_id": firm_id, "updated_at": datetime.utcnow().isoformat()}

    if update.name is not None:
        updates.append("name = :name")
        params["name"] = update.name
    if update.legal_name is not None:
        updates.append("legal_name = :legal_name")
        params["legal_name"] = update.legal_name
    if update.ein is not None:
        updates.append("ein = :ein")
        params["ein"] = update.ein
    if update.email is not None:
        updates.append("email = :email")
        params["email"] = update.email
    if update.phone is not None:
        updates.append("phone = :phone")
        params["phone"] = update.phone
    if update.website is not None:
        updates.append("website = :website")
        params["website"] = update.website
    if update.address_line1 is not None:
        updates.append("address_line1 = :address_line1")
        params["address_line1"] = update.address_line1
    if update.address_line2 is not None:
        updates.append("address_line2 = :address_line2")
        params["address_line2"] = update.address_line2
    if update.city is not None:
        updates.append("city = :city")
        params["city"] = update.city
    if update.state is not None:
        updates.append("state = :state")
        params["state"] = update.state
    if update.zip_code is not None:
        updates.append("zip_code = :zip_code")
        params["zip_code"] = update.zip_code

    if updates:
        updates.append("updated_at = :updated_at")
        # Validate all column names against whitelist before building query
        for clause in updates:
            col = clause.split("=")[0].strip()
            if col not in _FIRM_UPDATABLE_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Invalid field: {col}")
        update_clause = ", ".join(updates)
        query = text(f"UPDATE firms SET {update_clause} WHERE firm_id = :firm_id")
        await session.execute(query, params)
        await session.commit()
        logger.info(f"Firm {firm_id} profile updated by {user.email}")

    # Return updated profile
    return await get_firm_profile(user, firm_id, session)


@router.put("/integrations")
@require_firm_admin
async def update_integrations(
    update: IntegrationSettingsUpdate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update integration settings used for lead routing and onboarding."""
    current_result = await session.execute(
        text("SELECT integrations FROM firms WHERE firm_id = :firm_id"),
        {"firm_id": firm_id},
    )
    row = current_result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    integrations = _parse_json_field(row[0], {})
    integrations.update(update.settings or {})

    await session.execute(
        text("""
            UPDATE firms
            SET integrations = :integrations,
                updated_at = :updated_at
            WHERE firm_id = :firm_id
        """),
        {
            "firm_id": firm_id,
            "integrations": json.dumps(integrations),
            "updated_at": datetime.utcnow().isoformat(),
        },
    )

    await session.execute(
        text("""
            INSERT INTO audit_logs (log_id, firm_id, user_id, action, resource_type, details, created_at)
            VALUES (:log_id, :firm_id, :user_id, 'integrations_updated', 'firm', :details, :created_at)
        """),
        {
            "log_id": str(uuid4()),
            "firm_id": firm_id,
            "user_id": user.user_id,
            "details": json.dumps({"updated_keys": sorted((update.settings or {}).keys())}),
            "created_at": datetime.utcnow().isoformat(),
        },
    )

    await session.commit()
    logger.info(f"Firm {firm_id} integrations updated by {user.email}")
    return {"status": "success", "integrations": integrations}


@router.get("/branding", response_model=BrandingSettings)
async def get_branding_settings(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get firm branding settings."""
    query = text("SELECT branding FROM firms WHERE firm_id = :firm_id")
    result = await session.execute(query, {"firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    branding = _parse_json_field(row[0], {})

    return BrandingSettings(
        logo_url=branding.get("logo_url"),
        primary_color=branding.get("primary_color", "#059669"),
        secondary_color=branding.get("secondary_color", "#1e3a5f"),
        custom_domain=branding.get("custom_domain"),
        email_signature=branding.get("email_signature"),
        disclaimer_text=branding.get("disclaimer_text"),
        welcome_message=branding.get("welcome_message"),
    )


@router.put("/branding", response_model=BrandingSettings)
@require_permission(UserPermission.UPDATE_BRANDING)
async def update_branding_settings(
    update: BrandingUpdate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update firm branding settings."""
    # Get current branding
    query = text("SELECT branding FROM firms WHERE firm_id = :firm_id")
    result = await session.execute(query, {"firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    branding = _parse_json_field(row[0], {})

    # Update fields
    if update.primary_color is not None:
        branding["primary_color"] = update.primary_color
    if update.secondary_color is not None:
        branding["secondary_color"] = update.secondary_color
    if update.email_signature is not None:
        branding["email_signature"] = update.email_signature
    if update.disclaimer_text is not None:
        branding["disclaimer_text"] = update.disclaimer_text
    if update.welcome_message is not None:
        branding["welcome_message"] = update.welcome_message

    # Save
    update_query = text("""
        UPDATE firms SET branding = :branding, updated_at = :updated_at
        WHERE firm_id = :firm_id
    """)
    await session.execute(update_query, {
        "firm_id": firm_id,
        "branding": json.dumps(branding),
        "updated_at": datetime.utcnow().isoformat(),
    })
    await session.commit()
    logger.info(f"Firm {firm_id} branding updated by {user.email}")

    return BrandingSettings(
        logo_url=branding.get("logo_url"),
        primary_color=branding.get("primary_color", "#059669"),
        secondary_color=branding.get("secondary_color", "#1e3a5f"),
        custom_domain=branding.get("custom_domain"),
        email_signature=branding.get("email_signature"),
        disclaimer_text=branding.get("disclaimer_text"),
        welcome_message=branding.get("welcome_message"),
    )


@router.post("/branding/logo")
@require_permission(UserPermission.UPDATE_BRANDING)
async def upload_logo(
    file: UploadFile = File(...),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Upload firm logo.

    Accepted formats: PNG, JPG, SVG
    Max size: 2MB
    Recommended size: 200x200px
    """
    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/svg+xml"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}",
        )

    # Read and validate file size (2MB max)
    content = await file.read()
    max_size = 2 * 1024 * 1024  # 2MB
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 2MB.",
        )

    # Determine file extension
    ext_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/svg+xml": "svg",
    }
    ext = ext_map.get(file.content_type, "png")

    # Create firm-specific logo directory
    firm_logo_dir = LOGO_DIR / firm_id
    firm_logo_dir.mkdir(parents=True, exist_ok=True)

    # Save the logo file
    logo_filename = f"logo.{ext}"
    logo_path = firm_logo_dir / logo_filename
    logo_path.write_bytes(content)

    # Generate URL for the logo
    logo_url = f"/static/logos/{firm_id}/{logo_filename}"

    # Update firm branding with new logo URL
    query = text("SELECT branding FROM firms WHERE firm_id = :firm_id")
    result = await session.execute(query, {"firm_id": firm_id})
    row = result.fetchone()

    branding = _parse_json_field(row[0] if row else None, {})
    branding["logo_url"] = logo_url

    update_query = text("""
        UPDATE firms SET branding = :branding, updated_at = :updated_at
        WHERE firm_id = :firm_id
    """)
    await session.execute(update_query, {
        "firm_id": firm_id,
        "branding": json.dumps(branding),
        "updated_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    logger.info(f"Firm {firm_id} logo uploaded by {user.email} -> {logo_url}")

    return {
        "status": "success",
        "logo_url": logo_url,
        "message": "Logo uploaded successfully",
    }


@router.get("/security", response_model=SecuritySettings)
async def get_security_settings(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get firm security settings."""
    query = text("SELECT security_settings FROM firms WHERE firm_id = :firm_id")
    result = await session.execute(query, {"firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    security = _parse_json_field(row[0], {})

    return SecuritySettings(
        mfa_required=security.get("mfa_required", False),
        session_timeout_minutes=security.get("session_timeout_minutes", 60),
        password_expiry_days=security.get("password_expiry_days", 90),
        ip_whitelist=security.get("ip_whitelist"),
        require_reviewer_approval=security.get("require_reviewer_approval", True),
        allow_self_review=security.get("allow_self_review", False),
    )


@router.put("/security", response_model=SecuritySettings)
@require_firm_admin
async def update_security_settings(
    update: SecuritySettingsUpdate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update firm security settings."""
    # Check if IP whitelist is requested - Enterprise only
    if update.ip_whitelist is not None:
        # Check if firm has Enterprise features
        plan_query = text("""
            SELECT sp.features FROM subscriptions s
            JOIN subscription_plans sp ON s.plan_id = sp.plan_id
            WHERE s.firm_id = :firm_id AND s.status = 'active'
        """)
        plan_result = await session.execute(plan_query, {"firm_id": firm_id})
        plan_row = plan_result.fetchone()
        features = _parse_json_field(plan_row[0] if plan_row else None, {})

        if not features.get("ip_whitelist", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP whitelist is an Enterprise feature. Please upgrade your plan.",
            )

    # Get current security settings
    query = text("SELECT security_settings FROM firms WHERE firm_id = :firm_id")
    result = await session.execute(query, {"firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    security = _parse_json_field(row[0], {})

    # Update fields
    if update.mfa_required is not None:
        security["mfa_required"] = update.mfa_required
    if update.session_timeout_minutes is not None:
        security["session_timeout_minutes"] = update.session_timeout_minutes
    if update.password_expiry_days is not None:
        security["password_expiry_days"] = update.password_expiry_days
    if update.ip_whitelist is not None:
        security["ip_whitelist"] = update.ip_whitelist
    if update.require_reviewer_approval is not None:
        security["require_reviewer_approval"] = update.require_reviewer_approval
    if update.allow_self_review is not None:
        security["allow_self_review"] = update.allow_self_review

    # Save
    update_query = text("""
        UPDATE firms SET security_settings = :security, updated_at = :updated_at
        WHERE firm_id = :firm_id
    """)
    await session.execute(update_query, {
        "firm_id": firm_id,
        "security": json.dumps(security),
        "updated_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    # Log audit event for security changes
    audit_query = text("""
        INSERT INTO audit_logs (log_id, firm_id, user_id, action, resource_type, details, created_at)
        VALUES (:log_id, :firm_id, :user_id, 'security_settings_updated', 'firm', :details, :created_at)
    """)
    await session.execute(audit_query, {
        "log_id": str(uuid4()),
        "firm_id": firm_id,
        "user_id": user.user_id,
        "details": json.dumps({"updated_fields": list(update.model_dump(exclude_unset=True).keys())}),
        "created_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    logger.info(f"Firm {firm_id} security settings updated by {user.email}")

    return SecuritySettings(
        mfa_required=security.get("mfa_required", False),
        session_timeout_minutes=security.get("session_timeout_minutes", 60),
        password_expiry_days=security.get("password_expiry_days", 90),
        ip_whitelist=security.get("ip_whitelist"),
        require_reviewer_approval=security.get("require_reviewer_approval", True),
        allow_self_review=security.get("allow_self_review", False),
    )


# =============================================================================
# API KEY ROUTES (ENTERPRISE ONLY)
# =============================================================================

async def _check_api_access(session: AsyncSession, firm_id: str) -> bool:
    """Check if firm has API access (Enterprise feature)."""
    query = text("""
        SELECT sp.features FROM subscriptions s
        JOIN subscription_plans sp ON s.plan_id = sp.plan_id
        WHERE s.firm_id = :firm_id AND s.status = 'active'
    """)
    result = await session.execute(query, {"firm_id": firm_id})
    row = result.fetchone()
    if not row:
        return False
    features = _parse_json_field(row[0], {})
    return features.get("api_access", False)


@router.get("/api-keys", response_model=List[ApiKey])
@require_permission(UserPermission.MANAGE_API_KEYS)
async def list_api_keys(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    List all API keys for the firm.

    NOTE: Full keys are never shown after creation.
    """
    # Check if firm has API access
    if not await _check_api_access(session, firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API keys are an Enterprise feature. Please upgrade your plan.",
        )

    query = text("""
        SELECT key_id, name, key_prefix, created_at, last_used_at, expires_at, is_active
        FROM api_keys
        WHERE firm_id = :firm_id
        ORDER BY created_at DESC
    """)
    result = await session.execute(query, {"firm_id": firm_id})
    rows = result.fetchall()

    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    return [
        ApiKey(
            key_id=str(row[0]),
            name=row[1] or "",
            prefix=row[2] or "",
            created_at=parse_dt(row[3]) or datetime.utcnow(),
            last_used_at=parse_dt(row[4]),
            expires_at=parse_dt(row[5]),
            is_active=row[6] if row[6] is not None else True,
        )
        for row in rows
    ]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
@require_permission(UserPermission.MANAGE_API_KEYS)
async def create_api_key(
    request: ApiKeyCreate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a new API key.

    IMPORTANT: The full API key is only shown once in this response.
    Store it securely - it cannot be retrieved later.
    """
    # Check if firm has API access
    if not await _check_api_access(session, firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API keys are an Enterprise feature. Please upgrade your plan.",
        )

    # Generate secure API key
    key_id = str(uuid4())
    raw_key = secrets.token_urlsafe(32)
    api_key = f"tp_live_{raw_key}"
    key_prefix = api_key[:12]  # Store first 12 chars for identification

    # Hash the key for storage (we never store the full key)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    now = datetime.utcnow()
    expires_at = None
    if request.expires_in_days:
        expires_at = now + timedelta(days=request.expires_in_days)

    # Insert API key
    query = text("""
        INSERT INTO api_keys (
            key_id, firm_id, name, key_hash, key_prefix,
            created_by, created_at, expires_at, is_active
        ) VALUES (
            :key_id, :firm_id, :name, :key_hash, :key_prefix,
            :created_by, :created_at, :expires_at, true
        )
    """)
    await session.execute(query, {
        "key_id": key_id,
        "firm_id": firm_id,
        "name": request.name,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "created_by": user.user_id,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
    })

    # Log audit event
    audit_query = text("""
        INSERT INTO audit_logs (log_id, firm_id, user_id, action, resource_type, resource_id, details, created_at)
        VALUES (:log_id, :firm_id, :user_id, 'api_key_created', 'api_key', :key_id, :details, :created_at)
    """)
    await session.execute(audit_query, {
        "log_id": str(uuid4()),
        "firm_id": firm_id,
        "user_id": user.user_id,
        "key_id": key_id,
        "details": json.dumps({"name": request.name}),
        "created_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"API key {key_id} created for firm {firm_id} by {user.email}")

    return ApiKeyCreated(
        key_id=key_id,
        name=request.name,
        api_key=api_key,  # Only time the full key is shown!
        created_at=now,
        expires_at=expires_at,
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission(UserPermission.MANAGE_API_KEYS)
async def revoke_api_key(
    key_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Revoke an API key."""
    # Check if firm has API access
    if not await _check_api_access(session, firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API keys are an Enterprise feature. Please upgrade your plan.",
        )

    # Revoke the key (soft delete)
    now = datetime.utcnow()
    query = text("""
        UPDATE api_keys SET is_active = false, revoked_at = :revoked_at, revoked_by = :revoked_by
        WHERE key_id = :key_id AND firm_id = :firm_id
    """)
    result = await session.execute(query, {
        "key_id": key_id,
        "firm_id": firm_id,
        "revoked_at": now.isoformat(),
        "revoked_by": user.user_id,
    })

    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    # Log audit event
    audit_query = text("""
        INSERT INTO audit_logs (log_id, firm_id, user_id, action, resource_type, resource_id, created_at)
        VALUES (:log_id, :firm_id, :user_id, 'api_key_revoked', 'api_key', :key_id, :created_at)
    """)
    await session.execute(audit_query, {
        "log_id": str(uuid4()),
        "firm_id": firm_id,
        "user_id": user.user_id,
        "key_id": key_id,
        "created_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"API key {key_id} revoked for firm {firm_id} by {user.email}")

    return None
