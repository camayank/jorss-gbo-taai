"""
Tenant Isolation Middleware.

Provides tenant isolation without authentication (Prompt 7 compliance).
Extracts X-Tenant-ID from request headers and attaches to request state
for downstream data isolation.

This is NOT authentication. It's a trust-based isolation mechanism
for separating data between different tenants (e.g., different CPA firms).
"""

import logging
from typing import Optional, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Header name for tenant identification
TENANT_HEADER = "X-Tenant-ID"

# Default tenant for requests without header (e.g., browser-based)
DEFAULT_TENANT = "default"


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts tenant ID from request headers.

    Usage:
        1. Requests with X-Tenant-ID header are scoped to that tenant
        2. Requests without the header use 'default' tenant
        3. Tenant ID is available via request.state.tenant_id

    This provides data isolation without requiring authentication.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Extract tenant ID and attach to request state."""
        # Extract tenant ID from header
        tenant_id = request.headers.get(TENANT_HEADER, DEFAULT_TENANT)

        # Validate tenant ID format (basic sanitization)
        tenant_id = self._sanitize_tenant_id(tenant_id)

        # Attach to request state for downstream access
        request.state.tenant_id = tenant_id

        # Log tenant access (for audit purposes)
        logger.debug(f"Request tenant: {tenant_id} - {request.method} {request.url.path}")

        # Continue with request
        response = await call_next(request)

        # Include tenant ID in response headers for debugging
        response.headers["X-Tenant-ID"] = tenant_id

        return response

    def _sanitize_tenant_id(self, tenant_id: str) -> str:
        """
        Sanitize tenant ID to prevent injection attacks.

        Only allows alphanumeric characters, hyphens, and underscores.
        Max length 64 characters.
        """
        if not tenant_id:
            return DEFAULT_TENANT

        # Strip whitespace
        tenant_id = tenant_id.strip()

        # Limit length
        if len(tenant_id) > 64:
            tenant_id = tenant_id[:64]

        # Only allow safe characters
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if not all(c in safe_chars for c in tenant_id):
            logger.warning(f"Invalid tenant ID format, using default: {tenant_id}")
            return DEFAULT_TENANT

        return tenant_id


def get_tenant_id(request: Request) -> str:
    """
    Get the tenant ID from request state.

    Args:
        request: The FastAPI/Starlette request object

    Returns:
        The tenant ID (default if not set)
    """
    return getattr(request.state, 'tenant_id', DEFAULT_TENANT)


def require_tenant(request: Request) -> str:
    """
    Get tenant ID, raising error if not set.

    Use this in endpoints that REQUIRE tenant isolation.

    Args:
        request: The FastAPI/Starlette request object

    Returns:
        The tenant ID

    Raises:
        ValueError: If tenant ID is not set or is default
    """
    tenant_id = get_tenant_id(request)
    if tenant_id == DEFAULT_TENANT:
        raise ValueError("Tenant ID required but not provided")
    return tenant_id


class TenantScope:
    """
    Context manager for tenant-scoped operations.

    Usage:
        with TenantScope(request) as tenant_id:
            # Operations here are scoped to tenant_id
            data = load_data(tenant_id=tenant_id)
    """

    def __init__(self, request: Request):
        self.request = request
        self.tenant_id = get_tenant_id(request)

    def __enter__(self) -> str:
        return self.tenant_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def tenant_filter(tenant_id: str):
    """
    Create a filter function for tenant-scoped data.

    Usage:
        records = [r for r in all_records if tenant_filter(tenant_id)(r)]

    Args:
        tenant_id: The tenant ID to filter by

    Returns:
        Filter function that checks if record belongs to tenant
    """
    def _filter(record) -> bool:
        # Handle dict records
        if isinstance(record, dict):
            record_tenant = record.get('tenant_id', DEFAULT_TENANT)
            return record_tenant == tenant_id or record_tenant == DEFAULT_TENANT

        # Handle object records
        record_tenant = getattr(record, 'tenant_id', DEFAULT_TENANT)
        return record_tenant == tenant_id or record_tenant == DEFAULT_TENANT

    return _filter
