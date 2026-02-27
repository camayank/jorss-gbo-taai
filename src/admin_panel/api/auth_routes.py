"""
Authentication Routes - Login, logout, token management.

Provides:
- User login/logout
- Token refresh
- Password management
- MFA verification

All routes use database-backed authentication when available.
"""

import secrets
import logging
from typing import Optional
from datetime import datetime, timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenType,
)
from ..auth.password import verify_password, validate_password_strength, hash_password
from ..auth.rbac import get_current_user, TenantContext
from database.async_engine import get_async_session

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

# Token blacklist for logout (in production, use Redis)
_token_blacklist: set = set()

# Password reset tokens (in production, store in database)
_reset_tokens: dict = {}


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
    session: AsyncSession = Depends(get_async_session),
):
    """
    Authenticate user and return tokens.

    Returns access token (1 hour) and refresh token (7 days or 30 if remember_me).
    """
    email_lower = credentials.email.lower()
    client_ip = request.client.host if request.client else None

    # Try to find user in different tables
    user = await _find_user_by_email(session, email_lower)

    if not user:
        logger.warning(f"Login failed: user not found - {email_lower}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check if account is locked
    if user.get("locked_until"):
        lock_time = user["locked_until"]
        if isinstance(lock_time, str):
            lock_time = datetime.fromisoformat(lock_time)
        if datetime.utcnow() < lock_time:
            logger.warning(f"Login failed: account locked - {email_lower}")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked due to too many failed attempts",
            )

    # Check if account is active
    if not user.get("is_active", True):
        logger.warning(f"Login failed: account inactive - {email_lower}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    # Verify password
    if not user.get("password_hash"):
        logger.warning(f"Login failed: no password set - {email_lower}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(credentials.password, user["password_hash"]):
        # Increment failed login attempts
        await _increment_failed_login(session, user)
        logger.warning(f"Login failed: invalid password - {email_lower}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last login and reset failed attempts
    await _update_login_success(session, user, client_ip)

    # Create tokens
    access_token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        firm_id=user.get("firm_id"),
        role=user.get("role", "user"),
        permissions=user.get("permissions", []),
    )

    refresh_expires = timedelta(days=30) if credentials.remember_me else timedelta(days=7)
    refresh_token = create_refresh_token(
        user_id=user["id"],
        email=user["email"],
        expires_delta=refresh_expires,
    )

    logger.info(f"Login successful: {email_lower}")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
        user={
            "user_id": user["id"],
            "email": user["email"],
            "role": user.get("role", "user"),
            "firm_id": user.get("firm_id"),
            "full_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "User",
            "mfa_required": user.get("mfa_enabled", False),
        },
    )


async def _find_user_by_email(session: AsyncSession, email: str) -> Optional[dict]:
    """Find user by email across all user tables."""
    # Check platform admins first
    query = text("""
        SELECT admin_id as id, email, password_hash, first_name, last_name,
               role, is_active, mfa_enabled, NULL as firm_id, NULL as locked_until,
               0 as failed_login_attempts, 'platform_admin' as user_type
        FROM platform_admins
        WHERE email = :email AND is_active = true
    """)
    result = await session.execute(query, {"email": email})
    row = result.fetchone()
    if row:
        return dict(row._mapping)

    # Check firm users
    query = text("""
        SELECT u.user_id as id, u.email, u.password_hash, u.first_name, u.last_name,
               u.role, u.is_active, u.mfa_enabled, u.firm_id::text, u.locked_until,
               u.failed_login_attempts, u.custom_permissions, f.name as firm_name
        FROM users u
        LEFT JOIN firms f ON u.firm_id = f.firm_id
        WHERE u.email = :email
    """)
    result = await session.execute(query, {"email": email})
    row = result.fetchone()
    if row:
        data = dict(row._mapping)
        data["user_type"] = "firm_user"
        # Parse permissions
        import json
        perms = json.loads(data.get("custom_permissions") or "[]") if data.get("custom_permissions") else []
        data["permissions"] = perms + _get_role_permissions(data.get("role"))
        return data

    return None


def _get_role_permissions(role: str) -> list:
    """Get default permissions for a role."""
    role_permissions = {
        "owner": ["*"],
        "firm_admin": [
            "manage_team", "manage_billing", "manage_settings",
            "view_clients", "edit_returns", "approve_returns",
            "create_scenarios", "send_messages", "view_analytics"
        ],
        "manager": [
            "view_clients", "edit_returns", "approve_returns",
            "create_scenarios", "send_messages", "view_analytics"
        ],
        "senior_preparer": [
            "view_clients", "edit_returns", "create_scenarios",
            "send_messages"
        ],
        "preparer": ["view_clients", "edit_returns", "create_scenarios"],
        "reviewer": ["view_clients", "view_returns", "add_notes"],
        "viewer": ["view_clients", "view_returns"],
    }
    return role_permissions.get(role, [])


async def _increment_failed_login(session: AsyncSession, user: dict) -> None:
    """Increment failed login attempts and lock if needed."""
    if user.get("user_type") == "platform_admin":
        return  # Platform admins don't have lockout

    failed = user.get("failed_login_attempts", 0) + 1
    locked_until = None

    # Lock after 5 failed attempts
    if failed >= 5:
        locked_until = datetime.utcnow() + timedelta(minutes=15)

    query = text("""
        UPDATE users SET
            failed_login_attempts = :failed,
            locked_until = :locked_until
        WHERE user_id = :user_id
    """)
    await session.execute(query, {
        "user_id": user["id"],
        "failed": failed,
        "locked_until": locked_until.isoformat() if locked_until else None,
    })
    await session.commit()


async def _update_login_success(session: AsyncSession, user: dict, ip_address: str) -> None:
    """Update user record on successful login."""
    now = datetime.utcnow().isoformat()

    if user.get("user_type") == "platform_admin":
        query = text("""
            UPDATE platform_admins SET last_login_at = :now
            WHERE admin_id = :user_id
        """)
    else:
        query = text("""
            UPDATE users SET
                last_login_at = :now,
                last_login_ip = :ip,
                failed_login_attempts = 0,
                locked_until = NULL
            WHERE user_id = :user_id
        """)

    await session.execute(query, {
        "user_id": user["id"],
        "now": now,
        "ip": ip_address,
    })
    await session.commit()


@router.post("/logout")
async def logout(
    request: Request,
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Logout user and invalidate tokens.

    Note: JWT tokens cannot be truly invalidated server-side without a blacklist.
    This endpoint adds the token to an in-memory blacklist and logs the event.
    """
    # Get the token from the Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        _token_blacklist.add(token)

    # Log logout event
    try:
        query = text("""
            INSERT INTO admin_audit_log (
                log_id, admin_id, action, resource_type, details, ip_address, created_at
            ) VALUES (
                gen_random_uuid(), :admin_id, 'logout', 'session',
                '{"message": "User logged out"}', :ip, NOW()
            )
        """)
        await session.execute(query, {
            "admin_id": user.user_id,
            "ip": request.client.host if request.client else None,
        })
        await session.commit()
    except Exception as e:
        logger.warning(f"Failed to log logout event: {e}")

    logger.info(f"User logged out: {user.email}")
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
    session: AsyncSession = Depends(get_async_session),
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

    # Get current password hash
    user_data = await _find_user_by_email(session, user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify current password
    if not verify_password(request.current_password, user_data.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Hash new password
    new_hash = hash_password(request.new_password)
    now = datetime.utcnow().isoformat()

    # Update password in database
    if user_data.get("user_type") == "platform_admin":
        query = text("""
            UPDATE platform_admins SET password_hash = :new_hash
            WHERE admin_id = :user_id
        """)
    else:
        query = text("""
            UPDATE users SET
                password_hash = :new_hash,
                password_changed_at = :now,
                must_change_password = false
            WHERE user_id = :user_id
        """)

    await session.execute(query, {
        "user_id": user_data["id"],
        "new_hash": new_hash,
        "now": now,
    })
    await session.commit()

    logger.info(f"Password changed for user: {user.email}")

    return {
        "status": "success",
        "message": "Password changed successfully. Please log in again.",
    }


@router.post("/password/reset")
async def request_password_reset(
    reset_request: PasswordResetRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Request password reset email.

    Sends email with reset link if account exists.
    Always returns success to prevent email enumeration.
    """
    email_lower = reset_request.email.lower()

    # Find user by email
    user = await _find_user_by_email(session, email_lower)

    if user:
        # Generate reset token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        # Store reset token (in production, store in database)
        _reset_tokens[token] = {
            "user_id": user["id"],
            "email": user["email"],
            "user_type": user.get("user_type"),
            "expires_at": expires_at,
        }

        # Generate reset link
        reset_link = f"/auth/reset-password?token={token}"

        # Attempt to send email via configured email service
        email_sent = False
        try:
            from services.email_service import send_password_reset_email
            await send_password_reset_email(user["email"], reset_link)
            email_sent = True
            logger.info(f"Password reset email sent to {email_lower}")
        except ImportError:
            logger.warning(
                f"[AUTH] Email service not configured — password reset link for "
                f"{email_lower} logged but NOT emailed. Configure email service for production."
            )
            logger.info(f"Password reset link (NOT emailed): {reset_link}")
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email_lower}: {e}")

    # Always return success (security best practice - don't reveal if user exists)
    return {
        "status": "success",
        "message": "If an account exists with this email, you will receive a password reset link.",
    }


@router.post("/password/reset/confirm")
async def confirm_password_reset(
    reset_confirm: PasswordResetConfirm,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Confirm password reset with token.

    Resets password if token is valid.
    """
    # Validate new password strength
    is_valid, errors = validate_password_strength(reset_confirm.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet requirements", "errors": errors},
        )

    # Verify reset token
    token_data = _reset_tokens.get(reset_confirm.token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Check expiration
    if datetime.utcnow() > token_data["expires_at"]:
        del _reset_tokens[reset_confirm.token]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    # Hash new password
    new_hash = hash_password(reset_confirm.new_password)
    now = datetime.utcnow().isoformat()

    # Update password in database
    if token_data.get("user_type") == "platform_admin":
        query = text("""
            UPDATE platform_admins SET password_hash = :new_hash
            WHERE admin_id = :user_id
        """)
    else:
        query = text("""
            UPDATE users SET
                password_hash = :new_hash,
                password_changed_at = :now,
                must_change_password = false,
                failed_login_attempts = 0,
                locked_until = NULL
            WHERE user_id = :user_id
        """)

    await session.execute(query, {
        "user_id": token_data["user_id"],
        "new_hash": new_hash,
        "now": now,
    })
    await session.commit()

    # Invalidate reset token
    del _reset_tokens[reset_confirm.token]

    logger.info(f"Password reset completed for user: {token_data['email']}")

    return {
        "status": "success",
        "message": "Password has been reset. You can now log in with your new password.",
    }


@router.post("/mfa/verify")
async def verify_mfa(
    mfa_request: MfaVerifyRequest,
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Verify MFA code.

    Used during login when MFA is required.
    """
    # Get user's MFA secret from database
    user_data = await _find_user_by_email(session, user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    mfa_secret = user_data.get("mfa_secret")
    if not mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled for this account",
        )

    # Verify TOTP code using pyotp
    if len(mfa_request.code) != 6 or not mfa_request.code.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code format - must be 6 digits",
        )

    totp = pyotp.TOTP(mfa_secret)
    # valid_window=1 allows for 30 seconds of clock drift
    if not totp.verify(mfa_request.code, valid_window=1):
        logger.warning(f"MFA verification failed for user: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code. Please try again.",
        )

    logger.info(f"MFA verified successfully for user: {user.email}")

    return {"status": "success", "message": "MFA verified"}


@router.post("/mfa/setup")
async def setup_mfa(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Setup MFA for user account.

    Returns QR code URL and backup codes.
    """
    import base64

    # Generate TOTP secret (32 characters, base32 encoded)
    # In production, use pyotp.random_base32()
    secret_bytes = secrets.token_bytes(20)
    mfa_secret = base64.b32encode(secret_bytes).decode('utf-8').rstrip('=')

    # Generate backup codes
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]

    # Store secret temporarily (user must verify before it's activated)
    # In production, store in a pending_mfa table
    _reset_tokens[f"mfa_setup_{user.user_id}"] = {
        "secret": mfa_secret,
        "backup_codes": backup_codes,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
    }

    # Generate QR code URL (otpauth format)
    issuer = "TaxPlatform"
    qr_url = f"otpauth://totp/{issuer}:{user.email}?secret={mfa_secret}&issuer={issuer}"

    return {
        "status": "pending_verification",
        "qr_code_url": qr_url,
        "secret": mfa_secret,  # Only shown once
        "backup_codes": backup_codes,  # Only shown once
        "message": "Scan the QR code with your authenticator app, then verify with a code.",
    }


@router.post("/mfa/setup/confirm")
async def confirm_mfa_setup(
    mfa_request: MfaVerifyRequest,
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Confirm MFA setup by verifying a code.

    This activates MFA for the account.
    """
    # Get pending setup data
    setup_key = f"mfa_setup_{user.user_id}"
    setup_data = _reset_tokens.get(setup_key)

    if not setup_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending MFA setup. Please start the setup process again.",
        )

    if datetime.utcnow() > setup_data["expires_at"]:
        del _reset_tokens[setup_key]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup has expired. Please start again.",
        )

    # Verify the code against the secret using pyotp
    if len(mfa_request.code) != 6 or not mfa_request.code.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code format - must be 6 digits",
        )

    totp = pyotp.TOTP(setup_data["secret"])
    if not totp.verify(mfa_request.code, valid_window=1):
        logger.warning(f"MFA setup verification failed for user: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code. Please check your authenticator app and try again.",
        )

    # Activate MFA in database
    user_data = await _find_user_by_email(session, user.email)
    if user_data.get("user_type") == "platform_admin":
        query = text("""
            UPDATE platform_admins SET
                mfa_enabled = true,
                mfa_secret = :secret
            WHERE admin_id = :user_id
        """)
    else:
        query = text("""
            UPDATE users SET
                mfa_enabled = true,
                mfa_secret = :secret
            WHERE user_id = :user_id
        """)

    await session.execute(query, {
        "user_id": user_data["id"],
        "secret": setup_data["secret"],
    })
    await session.commit()

    # Clean up setup data
    del _reset_tokens[setup_key]

    logger.info(f"MFA enabled for user: {user.email}")

    return {
        "status": "success",
        "message": "MFA has been enabled. You will need to provide a code on future logins.",
        "backup_codes": setup_data["backup_codes"],  # Show backup codes one more time
    }


class DisableMfaRequest(BaseModel):
    """Request to disable MFA."""
    current_password: str


@router.delete("/mfa")
async def disable_mfa(
    disable_request: DisableMfaRequest,
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Disable MFA for user account.

    Requires password verification.
    """
    # Get user data
    user_data = await _find_user_by_email(session, user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify password
    if not verify_password(disable_request.current_password, user_data.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    # Disable MFA in database
    if user_data.get("user_type") == "platform_admin":
        query = text("""
            UPDATE platform_admins SET
                mfa_enabled = false,
                mfa_secret = NULL
            WHERE admin_id = :user_id
        """)
    else:
        query = text("""
            UPDATE users SET
                mfa_enabled = false,
                mfa_secret = NULL
            WHERE user_id = :user_id
        """)

    await session.execute(query, {"user_id": user_data["id"]})
    await session.commit()

    logger.info(f"MFA disabled for user: {user.email}")

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
