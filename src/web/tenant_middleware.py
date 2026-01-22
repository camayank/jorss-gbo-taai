"""
Tenant Resolution Middleware

Automatically determines the tenant for each request based on:
1. Custom domain (e.g., tax.yourfirm.com)
2. Subdomain (e.g., yourfirm.taxplatform.com)
3. URL parameter (e.g., ?tenant_id=xxx)
4. Header (e.g., X-Tenant-ID)
5. Default tenant

Injects tenant branding into request state for template rendering.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional

from src.database.tenant_persistence import get_tenant_persistence
from src.database.tenant_models import Tenant


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to resolve tenant from request and inject branding.
    """

    def __init__(self, app, default_tenant_id: Optional[str] = None):
        super().__init__(app)
        self.default_tenant_id = default_tenant_id or "default"
        self.persistence = get_tenant_persistence()

    async def dispatch(self, request: Request, call_next):
        """Resolve tenant and inject into request state"""

        tenant = self._resolve_tenant(request)

        # Inject tenant into request state
        request.state.tenant = tenant
        request.state.tenant_id = tenant.tenant_id if tenant else None

        # Inject branding into request state for templates
        if tenant:
            request.state.branding = self._tenant_branding_to_dict(tenant)
        else:
            # Use default branding from environment
            from src.config.branding import get_branding_config
            request.state.branding = get_branding_config().to_dict()

        response = await call_next(request)
        return response

    def _resolve_tenant(self, request: Request) -> Optional[Tenant]:
        """Resolve tenant from request"""

        # Strategy 1: URL parameter
        tenant_id = request.query_params.get('tenant_id')
        if tenant_id:
            tenant = self.persistence.get_tenant(tenant_id)
            if tenant:
                return tenant

        # Strategy 2: Header
        tenant_id = request.headers.get('X-Tenant-ID')
        if tenant_id:
            tenant = self.persistence.get_tenant(tenant_id)
            if tenant:
                return tenant

        # Strategy 3: Custom domain
        host = request.headers.get('host', '').split(':')[0]
        if host:
            tenant = self.persistence.get_tenant_by_domain(host)
            if tenant:
                return tenant

        # Strategy 5: Default tenant
        if self.default_tenant_id:
            tenant = self.persistence.get_tenant(self.default_tenant_id)
            if tenant:
                return tenant

        return None

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
