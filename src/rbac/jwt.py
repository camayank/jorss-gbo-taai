"""
CA4CPA GLOBAL LLC - JWT Token Handling

Simple JWT encoding/decoding for authentication.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
import jwt

from .roles import Role


# =============================================================================
# CONFIGURATION
# =============================================================================

JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_HOURS = 8
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7

# Environment detection
_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "development")
_IS_PRODUCTION = _ENVIRONMENT in ("production", "prod", "staging")


def _get_jwt_secret() -> str:
    """
    Get JWT secret from environment.

    SECURITY: In production, JWT_SECRET must be set.
    In development, a warning is logged if using default.
    """
    secret = os.environ.get("JWT_SECRET")

    if not secret:
        if _IS_PRODUCTION:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: JWT_SECRET environment variable is required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Development fallback - use cryptographically secure random secret
        # This is unique per process start but unpredictable
        import warnings
        import secrets as _secrets
        warnings.warn(
            "JWT_SECRET not set - using generated development secret. "
            "Set JWT_SECRET environment variable for production.",
            UserWarning
        )
        return f"DEV-ONLY-{_secrets.token_hex(32)}"

    # Validate secret strength
    if len(secret) < 32:
        raise ValueError("JWT_SECRET must be at least 32 characters for security")

    return secret


# Lazy initialization to allow startup validation
_jwt_secret_cache: str = None


def get_jwt_secret() -> str:
    """Get the JWT secret (cached after first call)."""
    global _jwt_secret_cache
    if _jwt_secret_cache is None:
        _jwt_secret_cache = _get_jwt_secret()
    return _jwt_secret_cache


# =============================================================================
# TOKEN CREATION
# =============================================================================

def create_access_token(
    user_id: UUID,
    email: str,
    name: str,
    role: Role,
    user_type: str,
    firm_id: Optional[UUID] = None,
    firm_name: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's unique identifier
        email: User's email
        name: User's display name
        role: User's role (one of the 8 roles)
        user_type: Type of user (platform_admin, firm_user, client)
        firm_id: Firm ID (for firm users and firm clients)
        firm_name: Firm name (for display)
        expires_delta: Custom expiration time

    Returns:
        JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)

    expire = datetime.utcnow() + expires_delta
    issued_at = datetime.utcnow()

    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "role": role.value,
        "user_type": user_type,
        "iat": issued_at,
        "exp": expire,
        "type": "access",
    }

    if firm_id:
        payload["firm_id"] = str(firm_id)
    if firm_name:
        payload["firm_name"] = firm_name

    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(
    user_id: UUID,
    user_type: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens contain minimal information and are used to get new access tokens.
    """
    if expires_delta is None:
        expires_delta = timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    expire = datetime.utcnow() + expires_delta

    payload = {
        "sub": str(user_id),
        "user_type": user_type,
        "exp": expire,
        "type": "refresh",
    }

    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


# =============================================================================
# TOKEN DECODING
# =============================================================================

def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Token payload as dictionary

    Raises:
        jwt.InvalidTokenError: If token is invalid or expired
    """
    return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])


def decode_token_safe(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without raising exceptions.

    Returns None if token is invalid.
    """
    try:
        return decode_token(token)
    except jwt.InvalidTokenError:
        return None


# =============================================================================
# TOKEN VALIDATION
# =============================================================================

def validate_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate an access token.

    Returns payload if valid, None if invalid.
    """
    payload = decode_token_safe(token)
    if payload and payload.get("type") == "access":
        return payload
    return None


def validate_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate a refresh token.

    Returns payload if valid, None if invalid.
    """
    payload = decode_token_safe(token)
    if payload and payload.get("type") == "refresh":
        return payload
    return None


# =============================================================================
# TOKEN UTILITIES
# =============================================================================

def get_token_expiry(token: str) -> Optional[datetime]:
    """Get the expiration time of a token."""
    payload = decode_token_safe(token)
    if payload and "exp" in payload:
        return datetime.fromtimestamp(payload["exp"])
    return None


def is_token_expired(token: str) -> bool:
    """Check if a token is expired."""
    expiry = get_token_expiry(token)
    if expiry is None:
        return True
    return expiry < datetime.utcnow()
