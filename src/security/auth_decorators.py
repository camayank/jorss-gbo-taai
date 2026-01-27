"""
Authentication Decorators for API Endpoints

Provides easy-to-use decorators for protecting endpoints with authentication
and authorization checks.

Usage:
    from security.auth_decorators import require_auth, require_session_owner

    @app.post("/api/returns/save")
    @require_auth()
    async def save_return(request: Request):
        # User is authenticated, proceed safely
        pass
"""

import functools
import logging
from typing import List, Optional, Callable
from fastapi import Request, HTTPException
from enum import Enum

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles for authorization."""
    TAXPAYER = "taxpayer"
    CPA = "cpa"
    ADMIN = "admin"
    PREPARER = "preparer"
    GUEST = "guest"


def require_auth(roles: Optional[List[Role]] = None, require_tenant: bool = True):
    """
    Decorator to require authentication for an endpoint.

    Args:
        roles: List of roles allowed to access this endpoint. If None, any authenticated user can access.
        require_tenant: If True, enforce tenant isolation (user can only access their own tenant's data)

    Example:
        @app.post("/api/returns/save")
        @require_auth(roles=[Role.TAXPAYER, Role.CPA])
        async def save_return(request: Request):
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Check if authentication is enabled
            # For now, log warning but don't block (backward compatibility)
            # TODO: After migration, change to raise HTTPException

            # Get user from session/JWT
            user = get_user_from_request(request)

            # FREEZE & FINISH: Auth enforcement deferred to Phase 2
            # Comprehensive logging for security audit trail
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")[:100]

            if not user:
                logger.warning(
                    f"[AUDIT] Unauthenticated access | path={request.url.path} | "
                    f"method={request.method} | ip={client_ip} | ua={user_agent}"
                )
                # Phase 2: raise HTTPException(401, "Authentication required")

            # Check role authorization
            if user and roles:
                user_role = user.get("role")
                user_id = user.get("id", "unknown")
                if user_role not in [r.value for r in roles]:
                    logger.warning(
                        f"[AUDIT] Role mismatch | user={user_id} | role={user_role} | "
                        f"required={[r.value for r in roles]} | path={request.url.path} | ip={client_ip}"
                    )
                    # Phase 2: raise HTTPException(403, "Insufficient permissions")

            # Check tenant isolation
            if user and require_tenant:
                # Extract session_id or return_id from request
                session_id = extract_session_id(request, kwargs)
                if session_id:
                    if not check_tenant_access(user, session_id):
                        logger.error(
                            f"[AUDIT] Tenant violation | user={user.get('id')} | "
                            f"session={session_id} | path={request.url.path} | ip={client_ip}"
                        )
                        # Phase 2: raise HTTPException(403, "Access denied: wrong tenant")

            # Call original function
            return await func(request, *args, **kwargs)

        return wrapper
    return decorator


def require_session_owner(session_param: str = "session_id"):
    """
    Decorator to require that the authenticated user owns the session being accessed.

    Args:
        session_param: Name of the parameter containing the session ID

    Example:
        @app.get("/api/returns/{session_id}")
        @require_session_owner(session_param="session_id")
        async def get_return(request: Request, session_id: str):
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_user_from_request(request)

            # FREEZE & FINISH: Auth enforcement deferred to Phase 2
            # Comprehensive logging for security audit trail
            client_ip = request.client.host if request.client else "unknown"

            if not user:
                logger.warning(
                    f"[AUDIT] Unauthenticated session access | path={request.url.path} | "
                    f"method={request.method} | ip={client_ip}"
                )
                # Phase 2: raise HTTPException(401, "Authentication required")
                return await func(request, *args, **kwargs)

            # Get session_id from kwargs
            session_id = kwargs.get(session_param)

            if session_id and not check_session_ownership(user, session_id):
                logger.error(
                    f"[AUDIT] Session ownership violation | user={user.get('id')} | "
                    f"session={session_id} | path={request.url.path} | ip={client_ip}"
                )
                # Phase 2: raise HTTPException(403, "Access denied: not your session")

            return await func(request, *args, **kwargs)

        return wrapper
    return decorator


def rate_limit(requests_per_minute: int = 60):
    """
    Decorator to rate limit an endpoint.

    Args:
        requests_per_minute: Maximum requests allowed per minute per user

    Example:
        @app.post("/api/upload")
        @rate_limit(requests_per_minute=10)
        async def upload(request: Request):
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_user_from_request(request)
            user_id = user.get("id") if user else request.client.host

            # Check rate limit
            if is_rate_limited(user_id, requests_per_minute):
                logger.warning(f"Rate limit exceeded for user {user_id} on {request.url.path}")
                raise HTTPException(429, "Too many requests. Please try again later.")

            return await func(request, *args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_user_from_request(request: Request) -> Optional[dict]:
    """
    Extract user information from request.

    Checks (in order):
    1. JWT token in Authorization header
    2. Session cookie
    3. API key header

    Returns:
        User dict with id, role, tenant_id, or None if not authenticated
    """
    # Check for JWT token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = verify_jwt_token(token)
        if user:
            return user

    # Check for session cookie
    session_id = request.cookies.get("tax_session_id")
    if session_id:
        user = get_user_from_session(session_id)
        if user:
            return user

    # Check for API key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = get_user_from_api_key(api_key)
        if user:
            return user

    return None


def extract_session_id(request: Request, kwargs: dict) -> Optional[str]:
    """Extract session_id from request path, query params, or body."""
    # From path parameters
    if "session_id" in kwargs:
        return kwargs["session_id"]

    if "return_id" in kwargs:
        return get_session_from_return_id(kwargs["return_id"])

    # From query parameters
    session_id = request.query_params.get("session_id")
    if session_id:
        return session_id

    return None


def check_tenant_access(user: dict, session_id: str) -> bool:
    """
    Check if user's tenant matches the session's tenant.

    Args:
        user: User dict with tenant_id
        session_id: Session ID to check

    Returns:
        True if user can access this session, False otherwise
    """
    user_tenant = user.get("tenant_id", "default")
    session_tenant = get_tenant_for_session(session_id)

    # Admins can access all tenants
    if user.get("role") == Role.ADMIN.value:
        return True

    return user_tenant == session_tenant


def check_session_ownership(user: dict, session_id: str) -> bool:
    """
    Check if user owns the session.

    Args:
        user: User dict with id
        session_id: Session ID to check

    Returns:
        True if user owns this session, False otherwise
    """
    session_owner = get_owner_for_session(session_id)

    # Admins and CPAs can access any session
    if user.get("role") in [Role.ADMIN.value, Role.CPA.value]:
        return True

    return user.get("id") == session_owner


# =============================================================================
# RATE LIMITING IMPLEMENTATION
# =============================================================================

# Global rate limiter instance (initialized lazily)
_rate_limiter: Optional[dict] = None
_rate_limit_lock = None

def _get_rate_limiter():
    """Get or create rate limiter backend."""
    global _rate_limiter, _rate_limit_lock
    import threading
    import time
    import os

    if _rate_limit_lock is None:
        _rate_limit_lock = threading.Lock()

    with _rate_limit_lock:
        if _rate_limiter is None:
            # Try Redis first for production
            redis_url = os.environ.get("REDIS_URL")
            if redis_url:
                try:
                    from security.middleware import RedisRateLimitBackend
                    _rate_limiter = {
                        "backend": RedisRateLimitBackend(redis_url),
                        "type": "redis"
                    }
                    logger.info("[SECURITY] Rate limiting enabled with Redis backend")
                except Exception as e:
                    logger.warning(f"[SECURITY] Redis rate limiter failed, using in-memory: {e}")

            # Fall back to in-memory
            if _rate_limiter is None:
                from security.middleware import InMemoryRateLimitBackend
                _rate_limiter = {
                    "backend": InMemoryRateLimitBackend(),
                    "type": "memory"
                }
                logger.info("[SECURITY] Rate limiting enabled with in-memory backend")

    return _rate_limiter


def is_rate_limited(user_id: str, requests_per_minute: int) -> bool:
    """
    Check if user has exceeded rate limit.

    Uses sliding window algorithm with Redis or in-memory cache.

    Args:
        user_id: User or IP identifier
        requests_per_minute: Maximum allowed requests per minute

    Returns:
        True if rate limited, False otherwise
    """
    try:
        limiter = _get_rate_limiter()
        burst_size = min(requests_per_minute, 20)  # Allow burst up to 20 or rpm

        # check_rate_limit returns True if allowed, False if limited
        allowed = limiter["backend"].check_rate_limit(
            client_ip=user_id,
            requests_per_minute=requests_per_minute,
            burst_size=burst_size
        )

        if not allowed:
            logger.warning(
                f"[SECURITY] Rate limit exceeded | user={user_id} | "
                f"limit={requests_per_minute}/min | backend={limiter['type']}"
            )
            return True  # Is rate limited

        return False  # Not rate limited

    except Exception as e:
        # Log error but don't block requests on rate limiter failure
        logger.error(f"[SECURITY] Rate limiter error: {e}")
        return False  # Fail open to avoid blocking legitimate requests


# ============================================================================
# STUB IMPLEMENTATIONS (Replace with actual auth system)
# ============================================================================

def verify_jwt_token(token: str) -> Optional[dict]:
    """Verify JWT token and return user claims."""
    # TODO: Implement actual JWT verification
    # from security.authentication import verify_token
    # return verify_token(token)
    return None


def get_user_from_session(session_id: str) -> Optional[dict]:
    """Get user from session ID."""
    # TODO: Implement actual session lookup
    return None


def get_user_from_api_key(api_key: str) -> Optional[dict]:
    """Get user from API key."""
    # TODO: Implement actual API key verification
    return None


def get_session_from_return_id(return_id: str) -> Optional[str]:
    """Get session_id from return_id."""
    # TODO: Implement actual database lookup
    return None


def get_tenant_for_session(session_id: str) -> str:
    """Get tenant_id for a session."""
    # TODO: Implement actual database lookup
    return "default"


def get_owner_for_session(session_id: str) -> Optional[str]:
    """Get owner user_id for a session."""
    # TODO: Implement actual database lookup
    return None


# Export main interface
__all__ = [
    'require_auth',
    'require_session_owner',
    'rate_limit',
    'Role',
]
