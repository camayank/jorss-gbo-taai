"""
Core Authentication API Routes

Unified authentication endpoints for all user types:
- Email/password login
- Magic link login (passwordless)
- Registration
- Token refresh
- Logout

These endpoints work identically for consumers, CPA clients,
CPA team members, and platform administrators.
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Query, status
from typing import Optional
import logging

from ..services.auth_service import (
    get_auth_service,
    CoreAuthService,
    LoginRequest,
    MagicLinkRequest,
    RegisterRequest,
    AuthResponse,
)
from ..models.user import UserContext, UserType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Core Authentication"])


# =============================================================================
# DEPENDENCY: Get current user from token
# =============================================================================

async def get_current_user(
    authorization: Optional[str] = Header(None),
    auth_service: CoreAuthService = Depends(get_auth_service)
) -> UserContext:
    """
    Extract and validate user from Authorization header.

    Returns UserContext for authenticated users.
    Raises 401 for missing/invalid tokens.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = parts[1]

    # Validate token
    context = auth_service.validate_access_token(token)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return context


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    auth_service: CoreAuthService = Depends(get_auth_service)
) -> Optional[UserContext]:
    """
    Extract user from Authorization header if present.

    Returns UserContext for authenticated users, None for anonymous.
    Does not raise errors for missing tokens.
    """
    if not authorization:
        return None

    try:
        return await get_current_user(authorization, auth_service)
    except HTTPException:
        return None


# =============================================================================
# LOGIN ENDPOINTS
# =============================================================================

@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    auth_service: CoreAuthService = Depends(get_auth_service)
):
    """
    Authenticate with email and password.

    Works for all user types:
    - Consumers: email/password from registration
    - CPA Clients: credentials provided by CPA
    - CPA Team: firm credentials
    - Platform Admins: admin credentials

    Returns:
    - access_token: JWT for API authentication
    - refresh_token: Token to get new access tokens (if remember_me=true)
    - user: Basic user information
    """
    response = await auth_service.login(request)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=response.message
        )

    return response


@router.post("/magic-link", response_model=AuthResponse)
async def request_magic_link(
    request: MagicLinkRequest,
    auth_service: CoreAuthService = Depends(get_auth_service)
):
    """
    Request a magic link for passwordless login.

    Sends an email with a one-time login link.
    Primarily used by consumers for easy access.

    Note: Always returns success to prevent email enumeration.
    """
    return await auth_service.request_magic_link(request)


@router.get("/magic-link/verify", response_model=AuthResponse)
async def verify_magic_link(
    token: str = Query(..., description="Magic link token"),
    auth_service: CoreAuthService = Depends(get_auth_service)
):
    """
    Verify magic link and authenticate user.

    Called when user clicks the magic link in their email.
    Returns access and refresh tokens on success.
    """
    response = await auth_service.verify_magic_link(token)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=response.message
        )

    return response


# =============================================================================
# REGISTRATION ENDPOINTS
# =============================================================================

@router.post("/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    auth_service: CoreAuthService = Depends(get_auth_service)
):
    """
    Register a new user.

    Supports registration for:
    - Consumers: Basic email/password (user_type=consumer)
    - CPA Clients: Requires assigned_cpa_id (user_type=cpa_client)
    - CPA Team: Requires firm_id and cpa_role (user_type=cpa_team)

    Platform admin registration is not allowed via this endpoint.
    """
    # Prevent platform admin registration via public endpoint
    if request.user_type == UserType.PLATFORM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin registration not allowed"
        )

    response = await auth_service.register(request)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.message
        )

    return response


@router.post("/register/consumer", response_model=AuthResponse)
async def register_consumer(
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    phone: Optional[str] = None,
    auth_service: CoreAuthService = Depends(get_auth_service)
):
    """
    Register a new consumer (B2C user).

    Simplified endpoint for consumer registration.
    """
    request = RegisterRequest(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        user_type=UserType.CONSUMER
    )

    response = await auth_service.register(request)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.message
        )

    return response


# =============================================================================
# TOKEN MANAGEMENT
# =============================================================================

@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    refresh_token: str,
    auth_service: CoreAuthService = Depends(get_auth_service)
):
    """
    Refresh access token using refresh token.

    Use this endpoint when your access token expires
    to get a new one without re-authenticating.
    """
    response = await auth_service.refresh_access_token(refresh_token)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=response.message
        )

    return response


@router.post("/logout", response_model=AuthResponse)
async def logout(
    refresh_token: Optional[str] = None,
    auth_service: CoreAuthService = Depends(get_auth_service)
):
    """
    Logout user and invalidate refresh token.

    Clears server-side session if refresh token is provided.
    """
    return await auth_service.logout(refresh_token)


# =============================================================================
# TOKEN VALIDATION
# =============================================================================

@router.get("/me")
async def get_current_user_info(
    user: UserContext = Depends(get_current_user)
):
    """
    Get current authenticated user information.

    Returns the user context extracted from the access token.
    Useful for verifying authentication and getting user details.
    """
    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "user_type": user.user_type,
        "firm_id": user.firm_id,
        "firm_name": user.firm_name,
        "permissions": user.permissions
    }


@router.get("/verify")
async def verify_token(
    user: UserContext = Depends(get_current_user)
):
    """
    Verify that the current token is valid.

    Returns basic confirmation if token is valid.
    Raises 401 if token is invalid or expired.
    """
    return {
        "valid": True,
        "user_id": user.user_id,
        "user_type": user.user_type
    }
