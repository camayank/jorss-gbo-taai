"""
Tenant Resolution Middleware

Automatically determines the tenant for each request based on:
1. Custom domain (e.g., tax.yourfirm.com)
2. Subdomain (e.g., yourfirm.taxplatform.com)
3. URL parameter (e.g., ?tenant_id=xxx) - VALIDATED
4. Header (e.g., X-Tenant-ID) - VALIDATED
5. Default tenant

Injects tenant branding into request state for template rendering.

SECURITY: Tenant IDs from user input are logged and should be validated
against user permissions in subsequent handlers using tenant_isolation module.
"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional

from src.database.tenant_persistence import get_tenant_persistence
from src.database.tenant_models import Tenant

logger = logging.getLogger(__name__)


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to resolve tenant from request and inject branding.

    SECURITY NOTE: This middleware resolves tenant from various sources but
    does NOT validate access permissions. Endpoints should use the
    tenant_isolation module to verify user has access to the resolved tenant.
    """

    def __init__(self, app, default_tenant_id: Optional[str] = None):
        super().__init__(app)
        self.default_tenant_id = default_tenant_id or "default"
        self.persistence = get_tenant_persistence()

    async def dispatch(self, request: Request, call_next):
        """Resolve tenant and inject into request state"""

        tenant, source = self._resolve_tenant(request)

        # Inject tenant into request state
        request.state.tenant = tenant
        request.state.tenant_id = tenant.tenant_id if tenant else self.default_tenant_id
        request.state.tenant_source = source  # Track how tenant was resolved

        # Log tenant resolution from user-controlled sources (security audit)
        if source in ("query_param", "header"):
            logger.info(
                f"Tenant resolved from {source}: {request.state.tenant_id}",
                extra={
                    "event": "tenant_resolution",
                    "tenant_id": request.state.tenant_id,
                    "source": source,
                    "path": request.url.path,
                    "client_ip": request.client.host if request.client else "unknown",
                }
            )

        # Inject branding into request state for templates
        if tenant:
            request.state.branding = self._tenant_branding_to_dict(tenant)
        else:
            # Use default branding from environment
            from src.config.branding import get_branding_config
            request.state.branding = get_branding_config().to_dict()

        response = await call_next(request)
        return response

    def _resolve_tenant(self, request: Request) -> tuple[Optional[Tenant], str]:
        """
        Resolve tenant from request.

        Returns:
            Tuple of (Tenant or None, source string)
            Source indicates how tenant was resolved for audit logging.
        """

        # Strategy 1: URL parameter (user-controlled - must validate access)
        tenant_id = request.query_params.get('tenant_id')
        if tenant_id:
            # Sanitize tenant_id - only allow alphanumeric, dash, underscore
            import re
            if re.match(r'^[a-zA-Z0-9_-]+$', tenant_id):
                tenant = self.persistence.get_tenant(tenant_id)
                if tenant:
                    return tenant, "query_param"
            else:
                logger.warning(
                    f"Invalid tenant_id format in query param: {tenant_id[:50]}",
                    extra={"event": "invalid_tenant_id", "source": "query_param"}
                )

        # Strategy 2: Header (user-controlled - must validate access)
        tenant_id = request.headers.get('X-Tenant-ID')
        if tenant_id:
            import re
            if re.match(r'^[a-zA-Z0-9_-]+$', tenant_id):
                tenant = self.persistence.get_tenant(tenant_id)
                if tenant:
                    return tenant, "header"
            else:
                logger.warning(
                    f"Invalid tenant_id format in header: {tenant_id[:50]}",
                    extra={"event": "invalid_tenant_id", "source": "header"}
                )

        # Strategy 3: Custom domain (trusted - domain ownership verified)
        host = request.headers.get('host', '').split(':')[0]
        if host:
            tenant = self.persistence.get_tenant_by_domain(host)
            if tenant:
                return tenant, "domain"

        # Strategy 4: Default tenant (trusted)
        if self.default_tenant_id:
            tenant = self.persistence.get_tenant(self.default_tenant_id)
            if tenant:
                return tenant, "default"

        return None, "none"

    def _tenant_branding_to_dict(self, tenant: Tenant) -> dict:
        """Convert tenant branding to dictionary"""
        branding = tenant.branding.to_dict()
        branding['tenant_id'] = tenant.tenant_id
        branding['features'] = tenant.features.to_dict()
        return branding


def get_tenant_from_request(request: Request) -> Optional[Tenant]:
    """Get tenant from request state"""
    return getattr(request.state, 'tenant', None)


def get_tenant_branding(request: Request) -> dict:
    """Get branding from request state"""
    return getattr(request.state, 'branding', {})
