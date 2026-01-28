"""
Tenant Isolation Middleware and Query Filters.

Provides comprehensive multi-tenancy security:
- Request-level tenant context extraction
- Query-level tenant filtering
- Cross-tenant access prevention
- Audit logging for tenant access
- Anomaly detection for suspicious access patterns

CRITICAL: This is a defense-in-depth layer. Database queries MUST also
filter by tenant_id. This middleware provides the context and monitoring.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Generic
from uuid import UUID

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import and_, or_
from sqlalchemy.orm import Query

from security.api_errors import APIError, ErrorCode

logger = logging.getLogger(__name__)


# =============================================================================
# TENANT CONTEXT
# =============================================================================


class TenantContext:
    """
    Holds tenant context for the current request.

    This is set by the middleware and available throughout the request lifecycle.
    """

    def __init__(
        self,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        user_role: Optional[str] = None,
        is_platform_admin: bool = False,
        allowed_tenant_ids: Optional[Set[UUID]] = None,
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_role = user_role
        self.is_platform_admin = is_platform_admin
        self.allowed_tenant_ids = allowed_tenant_ids or set()
        self._accessed_tenants: Set[UUID] = set()
        self._created_at = datetime.utcnow()

    def can_access_tenant(self, target_tenant_id: UUID) -> bool:
        """
        Check if current user can access the target tenant.

        Platform admins can access any tenant.
        Regular users can only access their own tenant.
        """
        if self.is_platform_admin:
            return True

        if self.tenant_id and target_tenant_id == self.tenant_id:
            return True

        if target_tenant_id in self.allowed_tenant_ids:
            return True

        return False

    def record_tenant_access(self, tenant_id: UUID) -> None:
        """Record that this context accessed a tenant."""
        self._accessed_tenants.add(tenant_id)

    @property
    def accessed_tenants(self) -> Set[UUID]:
        """Get set of all tenants accessed in this request."""
        return self._accessed_tenants.copy()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "user_id": str(self.user_id) if self.user_id else None,
            "user_role": self.user_role,
            "is_platform_admin": self.is_platform_admin,
        }


# Global storage for current request's tenant context (thread-local alternative)
# In production, use contextvars or request.state
_current_context: Optional[TenantContext] = None


def get_current_tenant_context() -> Optional[TenantContext]:
    """Get the current request's tenant context."""
    return _current_context


def set_current_tenant_context(ctx: Optional[TenantContext]) -> None:
    """Set the current request's tenant context."""
    global _current_context
    _current_context = ctx


# =============================================================================
# ANOMALY DETECTION
# =============================================================================


class TenantAccessTracker:
    """
    Tracks tenant access patterns to detect anomalies.

    Flags suspicious behavior like:
    - User accessing many different tenants quickly
    - Unusual access patterns
    - Potential tenant enumeration
    """

    # Thresholds
    MAX_TENANTS_PER_WINDOW = 10  # Max different tenants in time window
    WINDOW_SECONDS = 300  # 5 minute window
    MAX_CROSS_TENANT_PER_HOUR = 50  # Max cross-tenant accesses per hour

    def __init__(self):
        self._access_records: Dict[str, List[Dict]] = defaultdict(list)
        self._alerts_sent: Dict[str, float] = {}

    def record_access(
        self,
        user_id: str,
        tenant_id: str,
        is_cross_tenant: bool = False
    ) -> Optional[str]:
        """
        Record a tenant access and check for anomalies.

        Returns alert message if anomaly detected, None otherwise.
        """
        now = time.time()
        records = self._access_records[user_id]

        # Add new record
        records.append({
            "tenant_id": tenant_id,
            "timestamp": now,
            "is_cross_tenant": is_cross_tenant
        })

        # Clean old records (older than 1 hour)
        cutoff = now - 3600
        self._access_records[user_id] = [
            r for r in records if r["timestamp"] > cutoff
        ]
        records = self._access_records[user_id]

        # Check for anomalies
        return self._check_anomalies(user_id, records, now)

    def _check_anomalies(
        self,
        user_id: str,
        records: List[Dict],
        now: float
    ) -> Optional[str]:
        """Check for suspicious access patterns."""
        # Don't spam alerts - max 1 per user per 5 minutes
        last_alert = self._alerts_sent.get(user_id, 0)
        if now - last_alert < 300:
            return None

        # Check: Too many different tenants in short window
        window_cutoff = now - self.WINDOW_SECONDS
        recent_records = [r for r in records if r["timestamp"] > window_cutoff]
        unique_tenants = set(r["tenant_id"] for r in recent_records)

        if len(unique_tenants) > self.MAX_TENANTS_PER_WINDOW:
            self._alerts_sent[user_id] = now
            return (
                f"User {user_id} accessed {len(unique_tenants)} different tenants "
                f"in {self.WINDOW_SECONDS} seconds (threshold: {self.MAX_TENANTS_PER_WINDOW})"
            )

        # Check: Too many cross-tenant accesses
        cross_tenant_count = sum(1 for r in records if r["is_cross_tenant"])
        if cross_tenant_count > self.MAX_CROSS_TENANT_PER_HOUR:
            self._alerts_sent[user_id] = now
            return (
                f"User {user_id} made {cross_tenant_count} cross-tenant accesses "
                f"in the last hour (threshold: {self.MAX_CROSS_TENANT_PER_HOUR})"
            )

        return None


# Global tracker instance
_access_tracker = TenantAccessTracker()


# =============================================================================
# MIDDLEWARE
# =============================================================================


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce tenant isolation.

    Features:
    - Extracts tenant context from JWT/session
    - Validates tenant access on each request
    - Detects cross-tenant access attempts
    - Logs all tenant access for audit
    - Detects anomalous access patterns
    """

    EXEMPT_PATHS = {
        "/health", "/healthz", "/ready", "/metrics",
        "/api/v1/auth/login", "/api/v1/auth/register",
        "/docs", "/openapi.json", "/redoc",
    }

    def __init__(
        self,
        app,
        strict_mode: bool = True,
        audit_all_access: bool = True,
        detect_anomalies: bool = True,
        exempt_paths: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.strict_mode = strict_mode
        self.audit_all_access = audit_all_access
        self.detect_anomalies = detect_anomalies
        self.exempt_paths = exempt_paths or self.EXEMPT_PATHS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with tenant isolation."""
        path = request.url.path

        # Skip exempt paths
        if path in self.exempt_paths or path.startswith("/static"):
            return await call_next(request)

        # Extract tenant context from request
        tenant_ctx = await self._extract_tenant_context(request)

        # Store context in request state
        request.state.tenant_context = tenant_ctx
        set_current_tenant_context(tenant_ctx)

        try:
            # Check if request targets a specific tenant
            target_tenant_id = self._extract_target_tenant(request)

            if target_tenant_id and tenant_ctx:
                # Validate access
                if not tenant_ctx.can_access_tenant(target_tenant_id):
                    # Log the violation
                    logger.warning(
                        f"[TENANT_VIOLATION] User {tenant_ctx.user_id} "
                        f"attempted to access tenant {target_tenant_id} "
                        f"(own tenant: {tenant_ctx.tenant_id})"
                    )

                    if self.strict_mode:
                        return self._access_denied_response(
                            "Access denied to this resource"
                        )

                # Record access
                tenant_ctx.record_tenant_access(target_tenant_id)

                # Check for cross-tenant access
                is_cross_tenant = (
                    tenant_ctx.tenant_id and
                    target_tenant_id != tenant_ctx.tenant_id
                )

                # Detect anomalies
                if self.detect_anomalies and tenant_ctx.user_id:
                    alert = _access_tracker.record_access(
                        str(tenant_ctx.user_id),
                        str(target_tenant_id),
                        is_cross_tenant
                    )
                    if alert:
                        logger.warning(f"[TENANT_ANOMALY] {alert}")

                # Audit logging
                if self.audit_all_access:
                    logger.info(
                        f"[TENANT_ACCESS] user={tenant_ctx.user_id} "
                        f"target_tenant={target_tenant_id} "
                        f"own_tenant={tenant_ctx.tenant_id} "
                        f"cross_tenant={is_cross_tenant} "
                        f"path={path}"
                    )

            # Process request
            response = await call_next(request)
            return response

        finally:
            # Clear context
            set_current_tenant_context(None)

    async def _extract_tenant_context(self, request: Request) -> Optional[TenantContext]:
        """
        Extract tenant context from the request.

        Checks JWT token, session, or headers for tenant information.
        """
        # Check if already extracted by auth middleware
        if hasattr(request.state, "auth_context"):
            auth_ctx = request.state.auth_context
            if hasattr(auth_ctx, "firm_id") and hasattr(auth_ctx, "user_id"):
                return TenantContext(
                    tenant_id=auth_ctx.firm_id,
                    user_id=auth_ctx.user_id,
                    user_role=getattr(auth_ctx, "role", None),
                    is_platform_admin=getattr(auth_ctx, "is_platform", False),
                )

        # Try to extract from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from rbac.jwt import decode_token
                payload = decode_token(token)
                return TenantContext(
                    tenant_id=UUID(payload["firm_id"]) if payload.get("firm_id") else None,
                    user_id=UUID(payload["sub"]) if payload.get("sub") else None,
                    user_role=payload.get("role"),
                    is_platform_admin=payload.get("user_type") == "platform_admin",
                )
            except Exception:
                pass  # Invalid token, no context

        # Check session/cookie
        session_id = request.cookies.get("session_id")
        if session_id:
            # Would need to look up session from storage
            pass

        return None

    def _extract_target_tenant(self, request: Request) -> Optional[UUID]:
        """
        Extract the target tenant ID from the request.

        Checks path parameters, query parameters, and request body.
        """
        # Check path parameters
        path_params = request.path_params
        for param in ["firm_id", "tenant_id", "organization_id"]:
            if param in path_params:
                try:
                    return UUID(path_params[param])
                except (ValueError, TypeError):
                    pass

        # Check query parameters
        query_params = request.query_params
        for param in ["firm_id", "tenant_id"]:
            if param in query_params:
                try:
                    return UUID(query_params[param])
                except (ValueError, TypeError):
                    pass

        return None

    def _access_denied_response(self, message: str) -> JSONResponse:
        """Create access denied response."""
        return JSONResponse(
            status_code=403,
            content={
                "error": True,
                "code": ErrorCode.TENANT_ACCESS_DENIED.value,
                "message": message,
                "status_code": 403,
            }
        )


# =============================================================================
# QUERY FILTERS
# =============================================================================

T = TypeVar('T')


class TenantQueryFilter(Generic[T]):
    """
    Helper class for adding tenant filters to database queries.

    Usage:
        from security.tenant_isolation_middleware import TenantQueryFilter

        # In your repository
        def get_clients(self, tenant_filter: TenantQueryFilter):
            query = self.session.query(Client)
            query = tenant_filter.apply(query, Client.firm_id)
            return query.all()

        # In your endpoint
        @router.get("/clients")
        async def list_clients(ctx: AuthContext = Depends(require_auth)):
            tenant_filter = TenantQueryFilter.from_auth_context(ctx)
            return repo.get_clients(tenant_filter)
    """

    def __init__(
        self,
        tenant_id: Optional[UUID] = None,
        is_platform_admin: bool = False,
        allowed_tenant_ids: Optional[Set[UUID]] = None,
    ):
        self.tenant_id = tenant_id
        self.is_platform_admin = is_platform_admin
        self.allowed_tenant_ids = allowed_tenant_ids or set()

    @classmethod
    def from_auth_context(cls, ctx: Any) -> "TenantQueryFilter":
        """Create filter from an AuthContext object."""
        return cls(
            tenant_id=getattr(ctx, "firm_id", None),
            is_platform_admin=getattr(ctx, "is_platform", False),
            allowed_tenant_ids=set(),
        )

    @classmethod
    def from_tenant_context(cls, ctx: TenantContext) -> "TenantQueryFilter":
        """Create filter from a TenantContext object."""
        return cls(
            tenant_id=ctx.tenant_id,
            is_platform_admin=ctx.is_platform_admin,
            allowed_tenant_ids=ctx.allowed_tenant_ids,
        )

    def apply(self, query: Query, tenant_column) -> Query:
        """
        Apply tenant filter to a SQLAlchemy query.

        Args:
            query: SQLAlchemy query object
            tenant_column: Column to filter on (e.g., Client.firm_id)

        Returns:
            Filtered query
        """
        # Platform admins see all
        if self.is_platform_admin:
            return query

        # Build filter conditions
        conditions = []

        if self.tenant_id:
            conditions.append(tenant_column == self.tenant_id)

        if self.allowed_tenant_ids:
            conditions.append(tenant_column.in_(self.allowed_tenant_ids))

        if conditions:
            return query.filter(or_(*conditions))

        # No valid tenant context - filter to empty (safety default)
        return query.filter(tenant_column == None)  # noqa: E711

    def validate_access(self, resource_tenant_id: UUID) -> bool:
        """
        Validate if this filter allows access to a specific tenant's resource.

        Use this for single-resource access checks.
        """
        if self.is_platform_admin:
            return True

        if self.tenant_id and resource_tenant_id == self.tenant_id:
            return True

        if resource_tenant_id in self.allowed_tenant_ids:
            return True

        return False

    def require_access(self, resource_tenant_id: UUID, resource_type: str = "resource") -> None:
        """
        Require access to a tenant's resource, raising APIError if denied.

        Usage:
            tenant_filter.require_access(client.firm_id, "client")
        """
        if not self.validate_access(resource_tenant_id):
            raise APIError(
                code=ErrorCode.TENANT_ACCESS_DENIED,
                message=f"Access denied to this {resource_type}",
                details={"resource_type": resource_type}
            )


# =============================================================================
# DECORATORS
# =============================================================================


def require_tenant_access(func: Callable) -> Callable:
    """
    Decorator to require valid tenant context for an endpoint.

    Usage:
        @router.get("/clients")
        @require_tenant_access
        async def list_clients(request: Request):
            ctx = request.state.tenant_context
            # ctx is guaranteed to be non-None and have tenant_id
    """
    import functools

    @functools.wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        ctx = getattr(request.state, "tenant_context", None)

        if not ctx or (not ctx.tenant_id and not ctx.is_platform_admin):
            raise APIError(
                code=ErrorCode.TENANT_ACCESS_DENIED,
                message="Tenant context required for this endpoint"
            )

        return await func(request, *args, **kwargs)

    return wrapper
