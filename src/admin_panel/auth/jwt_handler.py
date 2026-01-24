"""
JWT Token Handler - Secure token generation and validation.

Security Features:
- Short-lived access tokens (1 hour)
- Refresh token rotation
- Token blacklisting support
- Claim validation
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
import logging

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

logger = logging.getLogger(__name__)

# Configuration - secure defaults
JWT_ALGORITHM = "HS256"


def _get_jwt_secret() -> str:
    """Get JWT secret with production enforcement."""
    secret = os.environ.get("JWT_SECRET")
    is_production = os.environ.get("ENVIRONMENT", "development").lower() == "production"

    if not secret:
        if is_production:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: JWT_SECRET environment variable is required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        logger.warning(
            "JWT_SECRET not set - using insecure development default. "
            "Set JWT_SECRET environment variable for production."
        )
        return "development-only-insecure-secret-key-32ch"

    if len(secret) < 32:
        raise ValueError("JWT_SECRET must be at least 32 characters for security")

    return secret


JWT_SECRET = _get_jwt_secret()
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenType(str, Enum):
    """Token type identifier."""
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass
class TokenPayload:
    """Decoded token payload."""
    sub: str  # User ID or Admin ID
    email: str
    type: TokenType
    firm_id: Optional[str] = None  # For firm users
    role: Optional[str] = None
    permissions: Optional[list] = None
    is_platform_admin: bool = False
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    jti: Optional[str] = None  # Token ID for blacklisting

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JWT encoding."""
        data = {
            "sub": self.sub,
            "email": self.email,
            "type": self.type.value if isinstance(self.type, TokenType) else self.type,
            "is_platform_admin": self.is_platform_admin,
        }
        if self.firm_id:
            data["firm_id"] = self.firm_id
        if self.role:
            data["role"] = self.role
        if self.permissions:
            data["permissions"] = self.permissions
        if self.jti:
            data["jti"] = self.jti
        return data


def create_access_token(
    user_id: str,
    email: str,
    firm_id: Optional[str] = None,
    role: Optional[str] = None,
    permissions: Optional[list] = None,
    is_platform_admin: bool = False,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a new access token.

    Args:
        user_id: User or admin ID
        email: User email
        firm_id: Firm ID (for firm users)
        role: User role
        permissions: List of permissions
        is_platform_admin: True if platform admin
        expires_delta: Custom expiration time

    Returns:
        JWT access token string
    """
    import uuid

    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.utcnow()
    expire = now + expires_delta

    payload = TokenPayload(
        sub=str(user_id),
        email=email,
        type=TokenType.ACCESS,
        firm_id=str(firm_id) if firm_id else None,
        role=role,
        permissions=permissions or [],
        is_platform_admin=is_platform_admin,
        exp=expire,
        iat=now,
        jti=str(uuid.uuid4()),
    )

    token_data = payload.to_dict()
    token_data["exp"] = expire
    token_data["iat"] = now

    return jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    email: str,
    is_platform_admin: bool = False,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a new refresh token.

    Args:
        user_id: User or admin ID
        email: User email
        is_platform_admin: True if platform admin
        expires_delta: Custom expiration time

    Returns:
        JWT refresh token string
    """
    import uuid

    if expires_delta is None:
        expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.utcnow()
    expire = now + expires_delta

    token_data = {
        "sub": str(user_id),
        "email": email,
        "type": TokenType.REFRESH.value,
        "is_platform_admin": is_platform_admin,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str, verify_type: Optional[TokenType] = None) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string
        verify_type: Expected token type (optional)

    Returns:
        TokenPayload with decoded claims

    Raises:
        InvalidTokenError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Verify token type if specified
        token_type = payload.get("type")
        if verify_type and token_type != verify_type.value:
            raise InvalidTokenError(f"Expected {verify_type.value} token, got {token_type}")

        return TokenPayload(
            sub=payload.get("sub"),
            email=payload.get("email"),
            type=TokenType(token_type) if token_type else TokenType.ACCESS,
            firm_id=payload.get("firm_id"),
            role=payload.get("role"),
            permissions=payload.get("permissions"),
            is_platform_admin=payload.get("is_platform_admin", False),
            exp=datetime.fromtimestamp(payload.get("exp")) if payload.get("exp") else None,
            iat=datetime.fromtimestamp(payload.get("iat")) if payload.get("iat") else None,
            jti=payload.get("jti"),
        )

    except ExpiredSignatureError:
        logger.warning("Token expired")
        raise InvalidTokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise InvalidTokenError(f"Invalid token: {str(e)}")


def verify_token(token: str) -> bool:
    """
    Verify if a token is valid without returning payload.

    Args:
        token: JWT token string

    Returns:
        True if token is valid
    """
    try:
        decode_token(token)
        return True
    except InvalidTokenError:
        return False


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get token expiry time without full validation.

    Args:
        token: JWT token string

    Returns:
        Expiry datetime or None
    """
    try:
        # Decode without verification to get expiry
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp")
        return datetime.fromtimestamp(exp) if exp else None
    except Exception:
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired.

    Args:
        token: JWT token string

    Returns:
        True if token is expired
    """
    expiry = get_token_expiry(token)
    if expiry is None:
        return True
    return datetime.utcnow() > expiry
