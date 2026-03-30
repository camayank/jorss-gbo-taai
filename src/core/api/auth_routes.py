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

SECURITY: All sensitive endpoints have rate limiting to prevent brute force attacks.
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Query, status, Request
from typing import Optional
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta

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
# RATE LIMITING FOR AUTH ENDPOINTS
# =============================================================================
# SECURITY: Simple in-memory rate limiter for auth endpoints
# In production, this should use Redis for distributed rate limiting

_auth_rate_limits: dict = defaultdict(list)  # In-memory fallback for dev
_AUTH_RATE_LIMIT_WINDOW = 60  # seconds
_AUTH_LOGIN_LIMIT = 5  # max login attempts per window
_AUTH_FORGOT_PASSWORD_LIMIT = 3  # max forgot password requests per window

_rate_limit_redis = None


def _get_rate_limit_backend():
    """Get Redis client for rate limiting. Falls back to in-memory in dev."""
    global _rate_limit_redis
    if _rate_limit_redis is not None:
        return _rate_limit_redis
    try:
        import redis as _sync_redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        client = _sync_redis.from_url(redis_url, decode_responses=True)
        client.ping()
        _rate_limit_redis = client
        return _rate_limit_redis
    except Exception:
        if os.environ.get("APP_ENVIRONMENT") in ("production", "prod", "staging"):
            raise RuntimeError("Redis required for rate limiting in production")
        logger.debug("Redis unavailable for rate limiting, using in-memory")
        return None


def _check_auth_rate_limit(identifier: str, limit: int) -> bool:
    """
    Check if identifier has exceeded rate limit.

    Returns True if request is allowed, False if rate limited.
    Uses Redis sorted sets when available, in-memory fallback for dev.
    """
    backend = _get_rate_limit_backend()
    if backend:
        import time as _time
        now = _time.time()
        key = f"rate_limit:auth:{identifier}"
        pipe = backend.pipeline()
        pipe.zremrangebyscore(key, 0, now - _AUTH_RATE_LIMIT_WINDOW)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, _AUTH_RATE_LIMIT_WINDOW)
        results = pipe.execute()
        current_count = results[1]
        return current_count < limit
    # In-memory fallback (dev only)
    now = time.time()
    window_start = now - _AUTH_RATE_LIMIT_WINDOW
    _auth_rate_limits[identifier] = [
        ts for ts in _auth_rate_limits[identifier] if ts > window_start
    ]
    if len(_auth_rate_limits[identifier]) >= limit:
        return False
    _auth_rate_limits[identifier].append(now)
    return True


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request.

    SECURITY: Uses request.client.host (the actual TCP peer address) instead of
    X-Forwarded-For / X-Real-IP headers which can be spoofed by attackers to
    bypass rate limiting.  If the app is behind a trusted reverse proxy, the
    proxy should set request.client to the real client IP via PROXY protocol
    or equivalent middleware.
    """
    return request.client.host if request.client else "unknown"

# Include OAuth routes
from .oauth_routes import router as oauth_router
router.include_router(oauth_router)


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
    http_request: Request,
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

    SECURITY: Rate limited to 5 attempts per minute per IP/email to prevent brute force.
    """
    # SECURITY: Rate limit by IP and email to prevent brute force attacks
    client_ip = _get_client_ip(http_request)
    rate_limit_key = f"login:{client_ip}:{request.email}"

    if not _check_auth_rate_limit(rate_limit_key, _AUTH_LOGIN_LIMIT):
        logger.warning(f"Login rate limit exceeded for {client_ip} / {request.email}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(_AUTH_RATE_LIMIT_WINDOW)}
        )

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

async def create_cpa_profile_record(
    db, cpa_id, firm_id, cpa_slug, firm_name, email, display_name
):
    """Create a CPA profile record with slug. Fail-soft — caller handles exceptions."""
    from database.models import CPAProfile
    profile = CPAProfile(
        cpa_id=cpa_id,
        firm_id=firm_id,
        cpa_slug=cpa_slug,
        firm_name=firm_name,
        contact_email=email,
        display_name=display_name,
        is_active=True,
    )
    db.add(profile)
    db.commit()


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

    # Auto-create Firm + Subscription for CPA signups (fail-soft)
    _user_type_str = str(getattr(request.user_type, 'value', request.user_type))
    if _user_type_str in ('cpa_team', 'cpa') and request.firm_name:
        try:
            from database.models import Firm, Subscription, SubscriptionPlan, User
            from database.db import SessionLocal
            db = SessionLocal()
            try:
                # Look up the newly created user
                user = db.query(User).filter(User.email == request.email).first()
                if not user:
                    raise ValueError(f"User not found after registration: {request.email}")

                firm_id = str(uuid.uuid4())
                trial_end = datetime.now(timezone.utc) + timedelta(days=14)

                # Create firm
                firm = Firm(
                    firm_id=firm_id,
                    name=request.firm_name,
                    email=request.email,
                    subscription_tier='starter',
                    subscription_status='trial',
                    trial_ends_at=trial_end,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(firm)

                # Link user to firm
                user.firm_id = firm_id

                # Find starter plan
                starter_plan = db.query(SubscriptionPlan).filter(
                    SubscriptionPlan.code == 'starter'
                ).first()

                if starter_plan:
                    sub = Subscription(
                        subscription_id=str(uuid.uuid4()),
                        firm_id=firm_id,
                        plan_id=starter_plan.plan_id,
                        status='trialing',
                        trial_end=trial_end,
                        current_period_start=datetime.now(timezone.utc),
                        current_period_end=trial_end,
                    )
                    db.add(sub)

                db.commit()

                # F3 — Generate unique CPA slug
                try:
                    base_slug = (
                        f"{request.firm_name or ''}-"
                        f"{request.first_name or ''}"
                    ).lower()
                    base_slug = re.sub(r'[^a-z0-9-]', '-', base_slug)
                    base_slug = re.sub(r'-+', '-', base_slug).strip('-')
                    base_slug = base_slug[:40] or 'advisor'

                    slug = base_slug
                    counter = 1
                    existing = db.execute(
                        "SELECT cpa_slug FROM cpa_profiles WHERE cpa_slug = :s",
                        {"s": slug}
                    ).fetchone()
                    while existing:
                        slug = f"{base_slug}-{counter}"
                        counter += 1
                        existing = db.execute(
                            "SELECT cpa_slug FROM cpa_profiles WHERE cpa_slug = :s",
                            {"s": slug}
                        ).fetchone()

                    await create_cpa_profile_record(
                        db=db,
                        cpa_id=user.id,
                        firm_id=firm_id,
                        cpa_slug=slug,
                        firm_name=request.firm_name,
                        email=request.email,
                        display_name=f"{request.first_name or ''} {request.last_name or ''}".strip(),
                    )
                except Exception as slug_error:
                    logger.warning(
                        f"CPA slug generation failed for {request.email}: "
                        f"{slug_error} — firm still created"
                    )

            finally:
                db.close()

        except Exception as firm_error:
            logger.warning(
                f"Auto-create firm failed for {request.email}: "
                f"{firm_error} — registration still succeeded"
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
    Revokes token jti via Redis blacklist for immediate invalidation.
    """
    # Revoke token jti via Redis blacklist
    if refresh_token:
        try:
            import os
            import time as _time
            import redis.asyncio as aioredis
            from rbac.jwt import decode_token_safe

            payload = decode_token_safe(refresh_token)
            if payload and payload.get("jti"):
                ttl = max(int(payload.get("exp", 0) - _time.time()), 0)
                if ttl > 0:
                    r = aioredis.from_url(
                        os.environ.get("REDIS_URL", "redis://localhost:6379"),
                        decode_responses=True,
                    )
                    await r.sadd("revoked_jtis", payload["jti"])
                    await r.expire("revoked_jtis", ttl)
                    await r.aclose()
        except Exception as e:
            logger.warning(f"[AUTH] Token revocation failed during logout (Redis may be down): {e}")

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


# =============================================================================
# PASSWORD RESET
# =============================================================================

from pydantic import BaseModel
import secrets
import os
from datetime import datetime, timedelta, timezone

# SECURITY: Token storage backend selection
# In production, Redis is REQUIRED for persistence across workers and restarts.
# In development, falls back to in-memory storage when Redis is unavailable.
_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "development")
_IS_PRODUCTION = _ENVIRONMENT in ("production", "prod", "staging")

_reset_tokens: dict = {}  # Development-only in-memory fallback
_reset_token_redis = None  # Lazy-initialized Redis client


def _get_reset_token_backend():
    """
    Get the password reset token Redis backend.

    In production, raises RuntimeError if Redis is unavailable.
    In development, returns None to fall back to in-memory storage.
    """
    global _reset_token_redis
    if _reset_token_redis is not None:
        return _reset_token_redis

    try:
        import redis as _sync_redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        client = _sync_redis.from_url(redis_url, decode_responses=True)
        client.ping()
        _reset_token_redis = client
        return _reset_token_redis
    except ImportError:
        if _IS_PRODUCTION:
            raise RuntimeError(
                "CRITICAL: redis package is required in production for reset token storage. "
                "Install with: pip install redis[hiredis]"
            )
        logger.warning("redis package not installed — using in-memory reset token storage (dev only)")
        return None
    except Exception as e:
        if _IS_PRODUCTION:
            raise RuntimeError(
                f"Redis is required in production for reset token storage but unavailable: {e}"
            )
        logger.warning(f"Redis unavailable for reset tokens, using in-memory (dev only): {e}")
        return None


def _store_reset_token(token: str, data: dict, ttl_seconds: int = 900):
    """Store a password reset token with expiration."""
    import json as _json
    redis_client = _get_reset_token_backend()
    if redis_client:
        redis_client.setex(f"reset_token:{token}", ttl_seconds, _json.dumps(data, default=str))
    else:
        _reset_tokens[token] = data


def _get_reset_token(token: str) -> dict:
    """Retrieve a password reset token."""
    import json as _json
    redis_client = _get_reset_token_backend()
    if redis_client:
        data = redis_client.get(f"reset_token:{token}")
        return _json.loads(data) if data else None
    return _reset_tokens.get(token)


def _delete_reset_token(token: str):
    """Delete a password reset token after use."""
    redis_client = _get_reset_token_backend()
    if redis_client:
        redis_client.delete(f"reset_token:{token}")
    elif token in _reset_tokens:
        del _reset_tokens[token]


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: str


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    http_request: Request,
    auth_service: CoreAuthService = Depends(get_auth_service)
):
    """
    Request a password reset email.

    Sends an email with a reset link if the account exists.
    Always returns success to prevent email enumeration.

    SECURITY: Rate limited to 3 requests per minute per IP to prevent email bombing.
    """
    from ..services.email_service import get_email_service

    # SECURITY: Rate limit by IP to prevent email bombing/enumeration
    client_ip = _get_client_ip(http_request)
    rate_limit_key = f"forgot_password:{client_ip}"

    if not _check_auth_rate_limit(rate_limit_key, _AUTH_FORGOT_PASSWORD_LIMIT):
        logger.warning(f"Forgot password rate limit exceeded for {client_ip}")
        # Still return success to prevent enumeration, but don't send email
        return {
            "success": True,
            "message": "If an account exists with that email, a reset link has been sent."
        }

    # Find user
    user = auth_service.get_user_by_email(request.email)

    if user:
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        # Store token using secure backend (Redis in production)
        _store_reset_token(reset_token, {
            "user_id": user.id,
            "email": user.email,
            "expires_at": expires_at.isoformat()
        }, ttl_seconds=900)  # 15 minutes

        # Send email
        email_service = get_email_service()
        await email_service.send_password_reset_email(
            to_email=user.email,
            reset_token=reset_token,
            user_name=user.first_name
        )

        logger.info(f"Password reset requested for {request.email}")

    # Always return success to prevent email enumeration
    return {
        "success": True,
        "message": "If an account exists with that email, a reset link has been sent."
    }


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm,
    auth_service: CoreAuthService = Depends(get_auth_service)
):
    """
    Reset password using reset token.

    Validates the token and updates the user's password.
    """
    # Validate token using secure backend
    token_data = _get_reset_token(request.token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Check expiration (handle both datetime and ISO string formats)
    expires_at = token_data["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if datetime.now(timezone.utc) > expires_at:
        _delete_reset_token(request.token)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )

    # Validate new password
    is_valid, error_msg = auth_service._validate_password(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Get user and update password
    user = auth_service.get_user_by_id(token_data["user_id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    # Update password hash
    user.password_hash = auth_service._hash_password(request.new_password)

    # Clean up used token using secure backend
    _delete_reset_token(request.token)

    logger.info(f"Password reset completed for {user.email}")

    return {
        "success": True,
        "message": "Password has been reset successfully. You can now sign in with your new password."
    }
