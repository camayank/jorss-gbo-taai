"""
Authentication Routes - Login, logout, token management.

Provides:
- User login/logout
- Token refresh
- Password management
- MFA verification
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, EmailStr

from ..auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenType,
)
from ..auth.password import verify_password, validate_password_strength, hash_password
from ..auth.rbac import get_current_user, TenantContext

router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class LoginRequest(BaseModel):
    """Login request."""
    email: EmailStr
    password: str
    remember_me: bool = False


class LoginResponse(BaseModel):
    """Login response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class RefreshResponse(BaseModel):
    """Token refresh response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(..., min_length=12)


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=12)


class MfaVerifyRequest(BaseModel):
    """MFA verification request."""
    code: str = Field(..., min_length=6, max_length=6)


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    credentials: LoginRequest,
):
    """
    Authenticate user and return tokens.

    Returns access token (1 hour) and refresh token (7 days or 30 if remember_me).
    """
    # TODO: Implement actual authentication
    # - Find user by email
    # - Verify password
    # - Check if account is active/locked
    # - Check if MFA is required
    # - Record login

    # Mock implementation for API structure
    # In production, this would query the database

    # Simulate invalid credentials
    if credentials.email == "invalid@example.com":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create tokens
    user_id = "user-123"
    firm_id = "firm-456"
    role = "firm_admin"
    permissions = ["manage_team", "view_billing", "create_client"]

    access_token = create_access_token(
        user_id=user_id,
        email=credentials.email,
        firm_id=firm_id,
        role=role,
        permissions=permissions,
    )

    from datetime import timedelta
    refresh_expires = timedelta(days=30) if credentials.remember_me else timedelta(days=7)
    refresh_token = create_refresh_token(
        user_id=user_id,
        email=credentials.email,
        expires_delta=refresh_expires,
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,  # 1 hour
        user={
            "user_id": user_id,
            "email": credentials.email,
            "role": role,
            "firm_id": firm_id,
            "full_name": "Demo User",
        },
    )


@router.post("/logout")
async def logout(
    user: TenantContext = Depends(get_current_user),
):
    """
    Logout user and invalidate tokens.

    Note: JWT tokens cannot be truly invalidated server-side.
    This endpoint is for client-side token clearing and
    audit logging purposes.
    """
    # TODO: Add token to blacklist (if using Redis)
    # TODO: Log logout event
    return {"status": "success", "message": "Logged out successfully"}


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: RefreshRequest,
):
    """
    Refresh access token using refresh token.

    Returns a new access token if refresh token is valid.
    """
    try:
        payload = decode_token(request.refresh_token, verify_type=TokenType.REFRESH)

        # Create new access token
        # In production, also fetch fresh permissions from database
        access_token = create_access_token(
            user_id=payload.sub,
            email=payload.email,
            firm_id=payload.firm_id,
            role=payload.role,
            permissions=payload.permissions,
        )

        return RefreshResponse(
            access_token=access_token,
            expires_in=3600,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )


@router.post("/password/change")
async def change_password(
    request: PasswordChangeRequest,
    user: TenantContext = Depends(get_current_user),
):
    """
    Change user's password.

    Requires current password verification.
    """
    # Validate new password strength
    is_valid, errors = validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet requirements", "errors": errors},
        )

    # TODO: Verify current password
    # TODO: Update password in database
    # TODO: Invalidate existing tokens
    # TODO: Log password change

    return {
        "status": "success",
        "message": "Password changed successfully. Please log in again.",
    }


@router.post("/password/reset")
async def request_password_reset(
    request: PasswordResetRequest,
):
    """
    Request password reset email.

    Sends email with reset link if account exists.
    Always returns success to prevent email enumeration.
    """
    # TODO: Find user by email
    # TODO: Generate reset token
    # TODO: Send reset email

    # Always return success (security best practice)
    return {
        "status": "success",
        "message": "If an account exists with this email, you will receive a password reset link.",
    }


@router.post("/password/reset/confirm")
async def confirm_password_reset(
    request: PasswordResetConfirm,
):
    """
    Confirm password reset with token.

    Resets password if token is valid.
    """
    # Validate new password strength
    is_valid, errors = validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet requirements", "errors": errors},
        )

    # TODO: Verify reset token
    # TODO: Update password
    # TODO: Invalidate reset token
    # TODO: Log password reset

    return {
        "status": "success",
        "message": "Password has been reset. You can now log in with your new password.",
    }


@router.post("/mfa/verify")
async def verify_mfa(
    request: MfaVerifyRequest,
    user: TenantContext = Depends(get_current_user),
):
    """
    Verify MFA code.

    Used during login when MFA is required.
    """
    # TODO: Verify TOTP code against user's MFA secret
    # TODO: Mark session as MFA verified

    # Mock validation
    if request.code != "123456":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code",
        )

    return {"status": "success", "message": "MFA verified"}


@router.post("/mfa/setup")
async def setup_mfa(
    user: TenantContext = Depends(get_current_user),
):
    """
    Setup MFA for user account.

    Returns QR code URL and backup codes.
    """
    # TODO: Generate TOTP secret
    # TODO: Generate QR code URL
    # TODO: Generate backup codes

    import secrets
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]

    return {
        "status": "pending_verification",
        "qr_code_url": "otpauth://totp/TaxPlatform:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=TaxPlatform",
        "secret": "JBSWY3DPEHPK3PXP",  # Only shown once
        "backup_codes": backup_codes,  # Only shown once
        "message": "Scan the QR code with your authenticator app, then verify with a code.",
    }


@router.delete("/mfa")
async def disable_mfa(
    user: TenantContext = Depends(get_current_user),
    current_password: str = None,
):
    """
    Disable MFA for user account.

    Requires password verification.
    """
    # TODO: Verify password
    # TODO: Clear MFA secret and backup codes
    # TODO: Log MFA disable

    return {"status": "success", "message": "MFA has been disabled"}


@router.get("/me")
async def get_current_user_info(
    user: TenantContext = Depends(get_current_user),
):
    """
    Get current authenticated user information.

    Returns user profile and permissions.
    """
    return {
        "user_id": user.user_id,
        "email": user.email,
        "firm_id": user.firm_id,
        "role": user.role,
        "permissions": list(user.permissions),
        "is_platform_admin": user.is_platform_admin,
    }
