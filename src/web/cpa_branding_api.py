"""
CPA Branding API

Allows CPAs to customize their personal branding within tenant's theme.
Staff and Partner roles can customize their own profiles.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import uuid4
import os

from ..rbac.dependencies import require_auth, AuthContext
from ..rbac.roles import Role
from ..database.tenant_persistence import get_tenant_persistence
from ..database.tenant_models import CPABranding


router = APIRouter(prefix="/api/cpa/branding", tags=["cpa-branding"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class UpdateCPABrandingRequest(BaseModel):
    """Request to update CPA branding"""
    display_name: Optional[str] = None
    tagline: Optional[str] = None
    accent_color: Optional[str] = None

    # Contact
    direct_email: Optional[EmailStr] = None
    direct_phone: Optional[str] = None
    office_address: Optional[str] = None

    # Bio
    bio: Optional[str] = None
    credentials: Optional[List[str]] = None
    years_experience: Optional[int] = None
    specializations: Optional[List[str]] = None

    # Client Portal
    welcome_message: Optional[str] = None


class CPABrandingResponse(BaseModel):
    """CPA branding response"""
    cpa_id: str
    tenant_id: str
    display_name: Optional[str]
    tagline: Optional[str]
    accent_color: Optional[str]
    profile_photo_url: Optional[str]
    signature_image_url: Optional[str]
    direct_email: Optional[str]
    direct_phone: Optional[str]
    office_address: Optional[str]
    bio: Optional[str]
    credentials: List[str]
    years_experience: Optional[int]
    specializations: List[str]
    welcome_message: Optional[str]


# =============================================================================
# PERMISSION HELPERS
# =============================================================================

def require_cpa_role(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
    """Require STAFF or PARTNER role"""
    if ctx.role not in {Role.STAFF, Role.PARTNER, Role.PLATFORM_ADMIN}:
        raise HTTPException(403, "CPA access required")
    return ctx


# =============================================================================
# CPA BRANDING ENDPOINTS
# =============================================================================

@router.get("/my-branding", response_model=CPABrandingResponse)
async def get_my_branding(ctx: AuthContext = Depends(require_cpa_role)):
    """
    Get my CPA branding.

    **CPA Only** (Staff, Partner)

    Returns personal branding configuration.
    """
    persistence = get_tenant_persistence()
    cpa_branding = persistence.get_cpa_branding(str(ctx.user_id))

    if not cpa_branding:
        # Return empty/default branding
        return CPABrandingResponse(
            cpa_id=str(ctx.user_id),
            tenant_id=ctx.tenant_id or "default",
            display_name=None,
            tagline=None,
            accent_color=None,
            profile_photo_url=None,
            signature_image_url=None,
            direct_email=None,
            direct_phone=None,
            office_address=None,
            bio=None,
            credentials=[],
            years_experience=None,
            specializations=[],
            welcome_message=None,
        )

    return CPABrandingResponse(
        cpa_id=cpa_branding.cpa_id,
        tenant_id=cpa_branding.tenant_id,
        display_name=cpa_branding.display_name,
        tagline=cpa_branding.tagline,
        accent_color=cpa_branding.accent_color,
        profile_photo_url=cpa_branding.profile_photo_url,
        signature_image_url=cpa_branding.signature_image_url,
        direct_email=cpa_branding.direct_email,
        direct_phone=cpa_branding.direct_phone,
        office_address=cpa_branding.office_address,
        bio=cpa_branding.bio,
        credentials=cpa_branding.credentials,
        years_experience=cpa_branding.years_experience,
        specializations=cpa_branding.specializations,
        welcome_message=cpa_branding.welcome_message,
    )


@router.patch("/my-branding")
async def update_my_branding(
    request: UpdateCPABrandingRequest,
    ctx: AuthContext = Depends(require_cpa_role)
):
    """
    Update my CPA branding.

    **CPA Only** (Staff, Partner)

    Customize personal branding within tenant's theme.
    """
    persistence = get_tenant_persistence()

    # Get or create CPA branding
    cpa_branding = persistence.get_cpa_branding(str(ctx.user_id))

    if not cpa_branding:
        # Create new branding
        cpa_branding = CPABranding(
            cpa_id=str(ctx.user_id),
            tenant_id=ctx.tenant_id or "default",
        )

    # Verify tenant allows sub-branding
    if ctx.tenant_id:
        tenant = persistence.get_tenant(ctx.tenant_id)
        if tenant and not tenant.branding.allow_sub_branding:
            raise HTTPException(403, "CPA branding customization not allowed by tenant")

    # Update fields
    if request.display_name is not None:
        cpa_branding.display_name = request.display_name
    if request.tagline is not None:
        cpa_branding.tagline = request.tagline
    if request.accent_color is not None:
        cpa_branding.accent_color = request.accent_color
    if request.direct_email is not None:
        cpa_branding.direct_email = request.direct_email
    if request.direct_phone is not None:
        cpa_branding.direct_phone = request.direct_phone
    if request.office_address is not None:
        cpa_branding.office_address = request.office_address
    if request.bio is not None:
        cpa_branding.bio = request.bio
    if request.credentials is not None:
        cpa_branding.credentials = request.credentials
    if request.years_experience is not None:
        cpa_branding.years_experience = request.years_experience
    if request.specializations is not None:
        cpa_branding.specializations = request.specializations
    if request.welcome_message is not None:
        cpa_branding.welcome_message = request.welcome_message

    cpa_branding.updated_at = datetime.now()

    success = persistence.save_cpa_branding(cpa_branding)

    if not success:
        raise HTTPException(500, "Failed to update branding")

    return {"message": "Branding updated", "branding": cpa_branding.to_dict()}


@router.post("/my-branding/profile-photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(require_cpa_role)
):
    """
    Upload profile photo.

    **CPA Only** (Staff, Partner)

    Uploads and sets profile photo.
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "Invalid file type. Use JPEG, PNG, or WebP")

    # Validate file size (max 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 5MB")

    # Save file
    upload_dir = Path("./uploads/profile_photos")
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{ctx.user_id}_{uuid4().hex[:8]}.{file.filename.split('.')[-1]}"
    file_path = upload_dir / filename

    with open(file_path, "wb") as f:
        f.write(content)

    # Update CPA branding
    persistence = get_tenant_persistence()
    cpa_branding = persistence.get_cpa_branding(str(ctx.user_id))

    if not cpa_branding:
        cpa_branding = CPABranding(
            cpa_id=str(ctx.user_id),
            tenant_id=ctx.tenant_id or "default",
        )

    cpa_branding.profile_photo_url = f"/uploads/profile_photos/{filename}"
    cpa_branding.updated_at = datetime.now()

    persistence.save_cpa_branding(cpa_branding)

    return {
        "message": "Profile photo uploaded",
        "url": cpa_branding.profile_photo_url
    }


@router.post("/my-branding/signature")
async def upload_signature(
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(require_cpa_role)
):
    """
    Upload signature image.

    **CPA Only** (Staff, Partner)

    Uploads and sets signature for documents.
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "Invalid file type. Use JPEG, PNG, or WebP")

    # Validate file size (max 2MB)
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 2MB")

    # Save file
    upload_dir = Path("./uploads/signatures")
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{ctx.user_id}_{uuid4().hex[:8]}.{file.filename.split('.')[-1]}"
    file_path = upload_dir / filename

    with open(file_path, "wb") as f:
        f.write(content)

    # Update CPA branding
    persistence = get_tenant_persistence()
    cpa_branding = persistence.get_cpa_branding(str(ctx.user_id))

    if not cpa_branding:
        cpa_branding = CPABranding(
            cpa_id=str(ctx.user_id),
            tenant_id=ctx.tenant_id or "default",
        )

    cpa_branding.signature_image_url = f"/uploads/signatures/{filename}"
    cpa_branding.updated_at = datetime.now()

    persistence.save_cpa_branding(cpa_branding)

    return {
        "message": "Signature uploaded",
        "url": cpa_branding.signature_image_url
    }


@router.get("/{cpa_id}", response_model=CPABrandingResponse)
async def get_cpa_branding(
    cpa_id: str,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Get CPA branding by ID.

    **Authenticated Users**

    Allows clients to see their assigned CPA's branding.
    """
    persistence = get_tenant_persistence()
    cpa_branding = persistence.get_cpa_branding(cpa_id)

    if not cpa_branding:
        raise HTTPException(404, "CPA branding not found")

    # TODO: Verify client has access to this CPA (assignment check)

    return CPABrandingResponse(
        cpa_id=cpa_branding.cpa_id,
        tenant_id=cpa_branding.tenant_id,
        display_name=cpa_branding.display_name,
        tagline=cpa_branding.tagline,
        accent_color=cpa_branding.accent_color,
        profile_photo_url=cpa_branding.profile_photo_url,
        signature_image_url=cpa_branding.signature_image_url,
        direct_email=cpa_branding.direct_email,
        direct_phone=cpa_branding.direct_phone,
        office_address=cpa_branding.office_address,
        bio=cpa_branding.bio,
        credentials=cpa_branding.credentials,
        years_experience=cpa_branding.years_experience,
        specializations=cpa_branding.specializations,
        welcome_message=cpa_branding.welcome_message,
    )


@router.delete("/my-branding")
async def delete_my_branding(ctx: AuthContext = Depends(require_cpa_role)):
    """
    Reset my CPA branding to defaults.

    **CPA Only** (Staff, Partner)

    Removes all customizations.
    """
    persistence = get_tenant_persistence()
    success = persistence.delete_cpa_branding(str(ctx.user_id))

    if not success:
        raise HTTPException(404, "No branding found to delete")

    return {"message": "Branding reset to defaults"}


# =============================================================================
# THEME PREVIEW
# =============================================================================

@router.get("/preview/colors")
async def preview_colors(
    primary: str,
    secondary: str,
    accent: Optional[str] = None,
    ctx: AuthContext = Depends(require_cpa_role)
):
    """
    Preview color scheme.

    **CPA Only** (Staff, Partner)

    Returns CSS variables for live preview.
    """
    return {
        "css_variables": {
            "--primary-color": primary,
            "--secondary-color": secondary,
            "--accent-color": accent or primary,
            "--primary-hover": f"{primary}dd",
            "--secondary-hover": f"{secondary}dd",
        },
        "sample_html": f"""
            <div style="background: {primary}; color: white; padding: 20px;">
                Primary Color Sample
            </div>
            <div style="background: {secondary}; color: white; padding: 20px;">
                Secondary Color Sample
            </div>
            <div style="background: {accent or primary}; color: white; padding: 20px;">
                Accent Color Sample
            </div>
        """
    }
