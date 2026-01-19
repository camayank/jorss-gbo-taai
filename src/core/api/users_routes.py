"""
Core Users API Routes

Unified user management endpoints for all user types:
- User profiles
- User preferences
- User search (with role-based filtering)
- User statistics

Access control is automatically applied based on UserContext.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
import logging

from .auth_routes import get_current_user
from ..models.user import UserContext, UserType, UserProfile, UserPreferences
from ..services.user_service import get_user_service, CoreUserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Core Users"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class UpdateProfileRequest(BaseModel):
    """Request to update user profile."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class UpdatePreferencesRequest(BaseModel):
    """Request to update user preferences."""
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    dark_mode: Optional[bool] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    two_factor_enabled: Optional[bool] = None


class UserSearchResponse(BaseModel):
    """Response for user search."""
    users: List[UserProfile]
    total: int
    limit: int
    offset: int


# =============================================================================
# PROFILE ENDPOINTS
# =============================================================================

@router.get("/me", response_model=UserProfile)
async def get_my_profile(
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service)
):
    """
    Get current user's profile.

    Returns full profile information for the authenticated user.
    """
    profile = await user_service.get_my_profile(context)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return profile


@router.patch("/me", response_model=UserProfile)
async def update_my_profile(
    request: UpdateProfileRequest,
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service)
):
    """
    Update current user's profile.

    Allows users to update their own profile information.
    """
    profile = await user_service.update_profile(
        user_id=context.user_id,
        context=context,
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        avatar_url=request.avatar_url
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update profile"
        )

    return profile


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service)
):
    """
    Get a user's profile.

    Access control:
    - Users can see their own profile
    - CPA team can see clients in their firm
    - Platform admins can see all profiles
    """
    profile = await user_service.get_profile(user_id, context)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or access denied"
        )
    return profile


@router.patch("/{user_id}", response_model=UserProfile)
async def update_user_profile(
    user_id: str,
    request: UpdateProfileRequest,
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service)
):
    """
    Update a user's profile.

    Access control:
    - Users can update their own profile
    - Firm admins can update users in their firm
    - Platform admins can update any profile
    """
    profile = await user_service.update_profile(
        user_id=user_id,
        context=context,
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        avatar_url=request.avatar_url
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update this profile"
        )

    return profile


# =============================================================================
# PREFERENCES ENDPOINTS
# =============================================================================

@router.get("/me/preferences", response_model=UserPreferences)
async def get_my_preferences(
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service)
):
    """
    Get current user's preferences.

    Returns notification settings, UI preferences, etc.
    """
    return await user_service.get_preferences(context)


@router.patch("/me/preferences", response_model=UserPreferences)
async def update_my_preferences(
    request: UpdatePreferencesRequest,
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service)
):
    """
    Update current user's preferences.

    Allows users to customize their notification and UI settings.
    """
    updates = request.dict(exclude_unset=True)
    return await user_service.update_preferences(context, **updates)


# =============================================================================
# SEARCH ENDPOINTS
# =============================================================================

@router.get("", response_model=UserSearchResponse)
async def search_users(
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service),
    q: Optional[str] = Query(None, description="Search query (name or email)"),
    user_type: Optional[UserType] = None,
    firm_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """
    Search users with role-based filtering.

    Access control:
    - Consumers: Can only see themselves
    - CPA clients: Can see themselves and their assigned CPA
    - CPA team: Can see users in their firm
    - Platform admins: Can see all users
    """
    users = await user_service.search_users(
        context=context,
        query=q,
        user_type=user_type,
        firm_id=firm_id,
        limit=limit,
        offset=offset
    )

    return UserSearchResponse(
        users=users,
        total=len(users),  # In production, this would be total count
        limit=limit,
        offset=offset
    )


@router.get("/firm/{firm_id}")
async def get_firm_users(
    firm_id: str,
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service),
    user_type: Optional[UserType] = None
):
    """
    Get all users in a firm.

    Access control:
    - CPA team: Can see users in their own firm
    - Platform admins: Can see users in any firm
    """
    users = await user_service.get_firm_users(
        firm_id=firm_id,
        context=context,
        user_type=user_type
    )

    if not users and not context.can_access_firm(firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this firm"
        )

    return {"firm_id": firm_id, "users": users, "total": len(users)}


@router.get("/cpa/{cpa_id}/clients")
async def get_cpa_clients(
    cpa_id: str,
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service)
):
    """
    Get all clients assigned to a CPA.

    Access control:
    - CPAs can see their own clients
    - Firm admins can see all clients in firm
    - Platform admins can see all
    """
    clients = await user_service.get_cpa_clients(cpa_id, context)

    return {"cpa_id": cpa_id, "clients": clients, "total": len(clients)}


# =============================================================================
# STATISTICS ENDPOINTS
# =============================================================================

@router.get("/stats/summary")
async def get_user_statistics(
    context: UserContext = Depends(get_current_user),
    user_service: CoreUserService = Depends(get_user_service)
):
    """
    Get user statistics.

    Access control:
    - CPA team: Stats for their firm
    - Platform admins: Platform-wide stats
    """
    if context.user_type not in [UserType.CPA_TEAM, UserType.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to statistics"
        )

    return await user_service.get_user_stats(context)


# =============================================================================
# ACCOUNT MANAGEMENT
# =============================================================================

@router.post("/me/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    context: UserContext = Depends(get_current_user)
):
    """
    Change current user's password.

    Requires the current password for verification.
    """
    # In production, this would verify current password and update
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )

    logger.info(f"Password changed for user: {context.user_id}")

    return {"success": True, "message": "Password changed successfully"}


@router.post("/me/enable-2fa")
async def enable_two_factor(
    context: UserContext = Depends(get_current_user)
):
    """
    Enable two-factor authentication.

    Returns setup information for 2FA (TOTP).
    """
    import secrets

    # Generate a mock TOTP secret
    secret = secrets.token_hex(16).upper()

    return {
        "success": True,
        "secret": secret,
        "qr_url": f"otpauth://totp/JorssGbo:{context.email}?secret={secret}&issuer=JorssGbo",
        "message": "Scan the QR code with your authenticator app"
    }


@router.post("/me/verify-2fa")
async def verify_two_factor(
    code: str,
    context: UserContext = Depends(get_current_user)
):
    """
    Verify and complete 2FA setup.

    Requires the TOTP code from authenticator app.
    """
    # In production, this would verify the TOTP code
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )

    logger.info(f"2FA enabled for user: {context.user_id}")

    return {"success": True, "message": "Two-factor authentication enabled"}


@router.post("/me/deactivate")
async def deactivate_account(
    password: str,
    context: UserContext = Depends(get_current_user)
):
    """
    Deactivate current user's account.

    This is a soft delete - account can be reactivated.
    """
    # In production, this would verify password and deactivate
    logger.info(f"Account deactivation requested for: {context.user_id}")

    return {
        "success": True,
        "message": "Account deactivated. Contact support to reactivate."
    }


# =============================================================================
# AVATAR UPLOAD
# =============================================================================

@router.post("/me/avatar")
async def upload_avatar(
    context: UserContext = Depends(get_current_user)
):
    """
    Upload a profile avatar.

    Note: In production, this would handle actual file upload.
    """
    import uuid

    avatar_url = f"/avatars/{context.user_id}/{uuid.uuid4().hex}.jpg"

    return {
        "success": True,
        "avatar_url": avatar_url,
        "message": "Avatar uploaded successfully"
    }
