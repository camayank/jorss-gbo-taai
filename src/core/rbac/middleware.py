"""
RBAC Middleware - Global authentication and authorization middleware.

Provides:
- JWT token extraction and validation
- Permission resolution and caching
- Request context injection
- Audit logging for sensitive operations
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Set, List, Any, Callable
from uuid import UUID
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


# =============================================================================
# RBAC CONTEXT
# =============================================================================

@dataclass
class RBACContextData:
    """
    RBAC context data stored in request.state.

    Contains resolved permissions and user information
    for the current request.
    """
    # User identification
    user_id: Optional[UUID] = None
    email: Optional[str] = None
    firm_id: Optional[UUID] = None
    partner_id: Optional[UUID] = None

    # Role information
    roles: List[str] = field(default_factory=list)
    primary_role: Optional[str] = None
    hierarchy_level: int = 4  # Default to lowest (USER level)

    # Permissions
    permissions: Set[str] = field(default_factory=set)

    # Flags
    is_authenticated: bool = False
    is_platform_admin: bool = False
    is_partner_admin: bool = False
    is_firm_admin: bool = False

    # Token info
    token_type: Optional[str] = None
    token_jti: Optional[str] = None
    token_exp: Optional[datetime] = None

    # Subscription
    subscription_tier: str = "starter"

    # Feature flags (enabled for this user/firm)
    feature_flags: Set[str] = field(default_factory=set)

    # Request metadata
    request_id: Optional[str] = None
    request_start_time: float = 0.0

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Platform admins have all permissions
        if self.is_platform_admin:
            return True
        return permission in self.permissions

    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions."""
        if self.is_platform_admin:
            return True
        return bool(self.permissions.intersection(permissions))

    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if user has all specified permissions."""
        if self.is_platform_admin:
            return True
        return all(p in self.permissions for p in permissions)

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_any_role(self, roles: List[str]) -> bool:
        """Check if user has any of the specified roles."""
        return bool(set(self.roles).intersection(roles))

    def can_access_firm(self, firm_id: UUID) -> bool:
        """Check if user can access a specific firm."""
        if self.is_platform_admin:
            return True
        if self.is_partner_admin and self.partner_id:
            # Partner admins can access their partner's firms
            # (requires additional lookup - simplified here)
            return True
        return self.firm_id == firm_id

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "user_id": str(self.user_id) if self.user_id else None,
            "email": self.email,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "roles": self.roles,
            "primary_role": self.primary_role,
            "is_platform_admin": self.is_platform_admin,
            "permission_count": len(self.permissions),
        }


# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

@dataclass
class RBACMiddlewareConfig:
    """Configuration for RBAC middleware."""
    # Paths that don't require authentication
    public_paths: Set[str] = field(default_factory=lambda: {
        "/",
        "/health",
        "/metrics",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/verify-email",
        "/docs",
        "/redoc",
        "/openapi.json",
    })

    # Path prefixes that don't require authentication
    public_path_prefixes: Set[str] = field(default_factory=lambda: {
        "/static/",
        "/assets/",
    })

    # Enable audit logging for permission checks
    audit_permission_checks: bool = True

    # Feature flag to enable/disable new RBAC (for gradual rollout)
    rbac_v2_enabled: bool = True

    # Fallback to legacy RBAC if v2 fails
    fallback_to_legacy: bool = True


# =============================================================================
# RBAC MIDDLEWARE
# =============================================================================

class RBACMiddleware(BaseHTTPMiddleware):
    """
    Global RBAC middleware for FastAPI.

    Responsibilities:
    1. Extract and validate JWT token
    2. Resolve user permissions (with caching)
    3. Inject RBAC context into request.state
    4. Log audit events for sensitive operations
    """

    def __init__(
        self,
        app: ASGIApp,
        config: Optional[RBACMiddlewareConfig] = None,
        get_db_session: Optional[Callable] = None,
        get_cache: Optional[Callable] = None,
    ):
        super().__init__(app)
        self.config = config or RBACMiddlewareConfig()
        self._get_db_session = get_db_session
        self._get_cache = get_cache

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through RBAC middleware."""
        start_time = time.time()

        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", f"req_{int(time.time() * 1000)}")

        # Initialize RBAC context
        rbac_context = RBACContextData(
            request_id=request_id,
            request_start_time=start_time,
        )

        # Check if path is public
        if self._is_public_path(request.url.path):
            request.state.rbac = rbac_context
            return await call_next(request)

        # Check if RBAC v2 is enabled
        if not self.config.rbac_v2_enabled:
            request.state.rbac = rbac_context
            return await call_next(request)

        try:
            # Extract and validate token
            token = self._extract_token(request)

            if token:
                # Validate and decode token
                rbac_context = await self._resolve_context(token, request_id, start_time)

            # Store context in request state
            request.state.rbac = rbac_context

            # Process request
            response = await call_next(request)

            # Add RBAC headers for debugging (non-production)
            if logger.isEnabledFor(logging.DEBUG):
                response.headers["X-RBAC-User"] = str(rbac_context.user_id) if rbac_context.user_id else "anonymous"
                response.headers["X-RBAC-Roles"] = ",".join(rbac_context.roles)

            return response

        except Exception as e:
            logger.error(f"RBAC middleware error: {e}", exc_info=True)

            # Fallback to legacy RBAC if configured
            if self.config.fallback_to_legacy:
                request.state.rbac = rbac_context
                return await call_next(request)

            return JSONResponse(
                status_code=500,
                content={
                    "error": True,
                    "code": "RBAC_ERROR",
                    "message": "Authorization system error",
                    "request_id": request_id,
                }
            )

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        if path in self.config.public_paths:
            return True

        for prefix in self.config.public_path_prefixes:
            if path.startswith(prefix):
                return True

        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from request."""
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Check cookie (for web UI)
        token = request.cookies.get("access_token")
        if token:
            return token

        return None

    async def _resolve_context(
        self,
        token: str,
        request_id: str,
        start_time: float,
    ) -> RBACContextData:
        """
        Resolve RBAC context from token.

        1. Decode and validate JWT
        2. Check cache for permissions
        3. If not cached, resolve from database
        4. Cache result for future requests
        """
        from admin_panel.auth.jwt_handler import decode_token, TokenPayload, TokenType

        # Decode token
        try:
            payload: TokenPayload = decode_token(token, verify_type=TokenType.ACCESS)
        except Exception as e:
            logger.warning(f"Token decode failed: {e}")
            return RBACContextData(
                request_id=request_id,
                request_start_time=start_time,
            )

        # Build context from token
        context = RBACContextData(
            user_id=UUID(payload.sub) if payload.sub else None,
            email=payload.email,
            firm_id=UUID(payload.firm_id) if payload.firm_id else None,
            is_authenticated=True,
            is_platform_admin=payload.is_platform_admin,
            token_type=payload.type.value if payload.type else None,
            token_jti=payload.jti,
            token_exp=payload.exp,
            request_id=request_id,
            request_start_time=start_time,
        )

        # If platform admin, grant all permissions
        if payload.is_platform_admin:
            context.hierarchy_level = 0
            context.is_platform_admin = True
            context.roles = [payload.role] if payload.role else ["super_admin"]
            context.primary_role = context.roles[0] if context.roles else None
            # Platform admins get all permissions implicitly
            return context

        # Check if permissions are in token (for simple cases)
        if payload.permissions:
            context.permissions = set(payload.permissions)
            context.roles = [payload.role] if payload.role else []
            context.primary_role = payload.role
            context.is_firm_admin = payload.role == "firm_admin"
            return context

        # Full permission resolution from database/cache
        if self._get_cache and self._get_db_session:
            context = await self._resolve_from_database(context, payload)

        return context

    async def _resolve_from_database(
        self,
        context: RBACContextData,
        payload: Any,
    ) -> RBACContextData:
        """
        Resolve permissions from database with caching.

        Uses the permission service and cache layer.
        """
        if not context.user_id:
            return context

        try:
            # Try cache first
            cache = self._get_cache() if self._get_cache else None
            if cache:
                cached = cache.get(
                    user_id=context.user_id,
                    firm_id=context.firm_id,
                    subscription_tier=context.subscription_tier,
                )
                if cached:
                    context.permissions = cached.permissions
                    context.roles = cached.roles
                    context.primary_role = cached.primary_role
                    context.hierarchy_level = cached.hierarchy_level
                    context.is_firm_admin = "firm_admin" in context.roles
                    return context

            # Resolve from database
            db_session = self._get_db_session() if self._get_db_session else None
            if db_session:
                from .permissions import PermissionService

                perm_service = PermissionService(db_session)
                resolved = await perm_service.resolve_user_permissions(
                    user_id=context.user_id,
                    firm_id=context.firm_id,
                    subscription_tier=context.subscription_tier,
                )

                context.permissions = resolved.permissions
                context.roles = resolved.roles
                context.primary_role = resolved.primary_role
                context.hierarchy_level = resolved.hierarchy_level
                context.is_firm_admin = "firm_admin" in context.roles

                # Cache for future requests
                if cache:
                    cache.set(
                        user_id=context.user_id,
                        permissions=resolved.permissions,
                        roles=resolved.roles,
                        primary_role=resolved.primary_role,
                        hierarchy_level=resolved.hierarchy_level,
                        firm_id=context.firm_id,
                        subscription_tier=context.subscription_tier,
                    )

        except Exception as e:
            logger.error(f"Permission resolution failed: {e}", exc_info=True)
            # Fall back to token permissions
            if payload.permissions:
                context.permissions = set(payload.permissions)
            if payload.role:
                context.roles = [payload.role]
                context.primary_role = payload.role

        return context


# =============================================================================
# AUDIT LOGGING
# =============================================================================

class RBACAuditLogger:
    """
    Audit logger for RBAC operations.

    Logs permission checks, access denials, and role changes
    for compliance and security monitoring.
    """

    def __init__(self, db_session_factory: Optional[Callable] = None):
        self._db_session_factory = db_session_factory

    async def log_permission_check(
        self,
        context: RBACContextData,
        permission: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        granted: bool = True,
        denial_reason: Optional[str] = None,
    ) -> None:
        """Log a permission check."""
        from .models import RBACauditLog, AuditAction

        if not self._db_session_factory:
            return

        try:
            with self._db_session_factory() as db:
                log = RBACauditLog(
                    action=AuditAction.PERMISSION_CHECK if granted else AuditAction.ACCESS_DENIED,
                    actor_id=context.user_id,
                    actor_type="user",
                    firm_id=context.firm_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    success=granted,
                    denial_reason=denial_reason,
                    request_id=context.request_id,
                    metadata={
                        "permission": permission,
                        "roles": context.roles,
                    },
                )
                db.add(log)
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to log permission check: {e}")

    async def log_role_change(
        self,
        actor_context: RBACContextData,
        target_user_id: UUID,
        role_id: UUID,
        action: str,  # "assigned" or "removed"
    ) -> None:
        """Log a role assignment or removal."""
        from .models import RBACauditLog, AuditAction

        if not self._db_session_factory:
            return

        try:
            with self._db_session_factory() as db:
                log = RBACauditLog(
                    action=AuditAction.ROLE_ASSIGNED if action == "assigned" else AuditAction.ROLE_REMOVED,
                    actor_id=actor_context.user_id,
                    actor_type="user",
                    target_user_id=target_user_id,
                    target_role_id=role_id,
                    firm_id=actor_context.firm_id,
                    success=True,
                    request_id=actor_context.request_id,
                )
                db.add(log)
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to log role change: {e}")
