"""
Authentication and Authorization Module.

Provides JWT-based authentication with proper token validation.
CRITICAL: Replaces unvalidated header/cookie-based authentication.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization check fails."""
    pass


class UserRole(str, Enum):
    """User roles for authorization."""
    TAXPAYER = "taxpayer"
    PREPARER = "preparer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


@dataclass
class JWTClaims:
    """JWT token claims."""
    sub: str  # Subject (user ID)
    role: UserRole
    tenant_id: str
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    jti: str  # JWT ID (for revocation)
    permissions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuthenticationManager:
    """
    JWT-based authentication manager.

    Security Features:
    - HMAC-SHA256 signed tokens
    - Token expiration
    - Token revocation support
    - Rate limiting (per user)
    - Role-based access control
    """

    # Default token expiration (1 hour)
    DEFAULT_EXPIRATION = 3600
    # Maximum token lifetime (24 hours)
    MAX_EXPIRATION = 86400
    # Rate limit: requests per minute
    RATE_LIMIT = 60

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize the authentication manager.

        Args:
            secret_key: JWT signing key. If not provided, uses JWT_SECRET_KEY
                       environment variable.
        """
        self._secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")

        if not self._secret_key:
            env = os.environ.get("APP_ENVIRONMENT", "development")
            if env == "production":
                raise ValueError(
                    "JWT_SECRET_KEY environment variable is required in production. "
                    "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            else:
                logger.warning(
                    "JWT_SECRET_KEY not set. Using random key (tokens will not persist across restarts)."
                )
                self._secret_key = secrets.token_hex(32)

        self._key_bytes = self._secret_key.encode("utf-8")

        # Token revocation list (in production, use Redis)
        self._revoked_tokens: Set[str] = set()

        # Rate limiting tracking (in production, use Redis)
        self._rate_limits: Dict[str, List[float]] = {}

    def create_token(
        self,
        user_id: str,
        role: UserRole,
        tenant_id: str,
        expiration: Optional[int] = None,
        permissions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a signed JWT token.

        Args:
            user_id: Unique user identifier
            role: User's role
            tenant_id: Tenant identifier for multi-tenancy
            expiration: Token lifetime in seconds (default: 1 hour)
            permissions: List of permission strings
            metadata: Additional claims

        Returns:
            Signed JWT token string
        """
        now = int(time.time())
        exp = now + min(expiration or self.DEFAULT_EXPIRATION, self.MAX_EXPIRATION)

        claims = JWTClaims(
            sub=user_id,
            role=role,
            tenant_id=tenant_id,
            exp=exp,
            iat=now,
            jti=secrets.token_hex(16),
            permissions=permissions or [],
            metadata=metadata or {},
        )

        return self._encode_token(claims)

    def verify_token(self, token: str) -> JWTClaims:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded JWT claims

        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            claims = self._decode_token(token)

            # Check expiration
            if claims.exp < int(time.time()):
                raise AuthenticationError("Token expired")

            # Check revocation
            if claims.jti in self._revoked_tokens:
                raise AuthenticationError("Token has been revoked")

            return claims

        except AuthenticationError:
            raise
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            raise AuthenticationError("Invalid token") from e

    def revoke_token(self, token: str) -> None:
        """
        Revoke a token (add to revocation list).

        Args:
            token: Token to revoke
        """
        try:
            claims = self._decode_token(token)
            self._revoked_tokens.add(claims.jti)
            logger.info(f"Token revoked: {claims.jti[:8]}...")
        except Exception:
            pass  # Token already invalid

    def check_rate_limit(self, user_id: str) -> bool:
        """
        Check if user has exceeded rate limit.

        Args:
            user_id: User identifier

        Returns:
            True if within limit, False if exceeded
        """
        now = time.time()
        window_start = now - 60  # 1 minute window

        if user_id not in self._rate_limits:
            self._rate_limits[user_id] = []

        # Remove old entries
        self._rate_limits[user_id] = [
            t for t in self._rate_limits[user_id] if t > window_start
        ]

        if len(self._rate_limits[user_id]) >= self.RATE_LIMIT:
            return False

        self._rate_limits[user_id].append(now)
        return True

    def check_permission(self, claims: JWTClaims, required_permission: str) -> bool:
        """
        Check if user has a specific permission.

        Args:
            claims: User's JWT claims
            required_permission: Permission to check

        Returns:
            True if user has permission
        """
        # Admin has all permissions
        if claims.role == UserRole.ADMIN:
            return True

        return required_permission in claims.permissions

    def check_tenant_access(self, claims: JWTClaims, resource_tenant_id: str) -> bool:
        """
        Check if user can access a resource in a specific tenant.

        Args:
            claims: User's JWT claims
            resource_tenant_id: Tenant ID of the resource

        Returns:
            True if user can access the resource
        """
        # Admin can access all tenants
        if claims.role == UserRole.ADMIN:
            return True

        return claims.tenant_id == resource_tenant_id

    def _encode_token(self, claims: JWTClaims) -> str:
        """Encode claims into a signed JWT token."""
        # Create header
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = self._base64url_encode(json.dumps(header))

        # Create payload
        payload = {
            "sub": claims.sub,
            "role": claims.role.value,
            "tenant_id": claims.tenant_id,
            "exp": claims.exp,
            "iat": claims.iat,
            "jti": claims.jti,
            "permissions": claims.permissions,
            "metadata": claims.metadata,
        }
        payload_b64 = self._base64url_encode(json.dumps(payload))

        # Create signature
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            self._key_bytes,
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
        signature_b64 = self._base64url_encode_bytes(signature)

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def _decode_token(self, token: str) -> JWTClaims:
        """Decode and verify a JWT token."""
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthenticationError("Invalid token format")

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        message = f"{header_b64}.{payload_b64}"
        expected_signature = hmac.new(
            self._key_bytes,
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
        actual_signature = self._base64url_decode_bytes(signature_b64)

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise AuthenticationError("Invalid token signature")

        # Decode payload
        payload = json.loads(self._base64url_decode(payload_b64))

        return JWTClaims(
            sub=payload["sub"],
            role=UserRole(payload["role"]),
            tenant_id=payload["tenant_id"],
            exp=payload["exp"],
            iat=payload["iat"],
            jti=payload["jti"],
            permissions=payload.get("permissions", []),
            metadata=payload.get("metadata", {}),
        )

    def _base64url_encode(self, data: str) -> str:
        """Base64url encode a string."""
        import base64
        return base64.urlsafe_b64encode(data.encode("utf-8")).rstrip(b"=").decode("utf-8")

    def _base64url_encode_bytes(self, data: bytes) -> str:
        """Base64url encode bytes."""
        import base64
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

    def _base64url_decode(self, data: str) -> str:
        """Base64url decode to string."""
        import base64
        # Add padding
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data).decode("utf-8")

    def _base64url_decode_bytes(self, data: str) -> bytes:
        """Base64url decode to bytes."""
        import base64
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)


# Singleton instance
_auth_manager: Optional[AuthenticationManager] = None


def get_auth_manager() -> AuthenticationManager:
    """Get the singleton authentication manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthenticationManager()
    return _auth_manager


# FastAPI security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> Optional[JWTClaims]:
    """
    FastAPI dependency to get current authenticated user.

    Usage:
        @app.get("/api/protected")
        async def protected_endpoint(user: JWTClaims = Depends(get_current_user)):
            ...
    """
    # Try Authorization header first
    if credentials and credentials.credentials:
        try:
            return get_auth_manager().verify_token(credentials.credentials)
        except AuthenticationError:
            pass

    # Try cookie as fallback
    token = request.cookies.get("auth_token")
    if token:
        try:
            return get_auth_manager().verify_token(token)
        except AuthenticationError:
            pass

    return None


def require_auth(
    roles: Optional[List[UserRole]] = None,
    permissions: Optional[List[str]] = None,
):
    """
    Decorator to require authentication and optionally specific roles/permissions.

    Usage:
        @app.get("/api/admin")
        @require_auth(roles=[UserRole.ADMIN])
        async def admin_endpoint(request: Request):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get credentials from header
            auth_header = request.headers.get("Authorization", "")
            token = None

            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            else:
                token = request.cookies.get("auth_token")

            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            try:
                auth_manager = get_auth_manager()
                claims = auth_manager.verify_token(token)

                # Check rate limit
                if not auth_manager.check_rate_limit(claims.sub):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded",
                    )

                # Check roles
                if roles and claims.role not in roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient role",
                    )

                # Check permissions
                if permissions:
                    for perm in permissions:
                        if not auth_manager.check_permission(claims, perm):
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Missing permission: {perm}",
                            )

                # Add claims to request state
                request.state.user = claims

                return await func(request, *args, **kwargs)

            except AuthenticationError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(e),
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return wrapper
    return decorator
