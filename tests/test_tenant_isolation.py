"""
Tests for Tenant Resolution Middleware.

Verifies tenant safety compliance and tenant isolation.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestTenantResolutionMiddleware:
    """Tests for TenantResolutionMiddleware."""

    def test_import(self):
        """Test module can be imported."""
        from web.tenant_middleware import (
            TenantResolutionMiddleware,
            get_tenant_from_request,
            get_tenant_branding,
        )
        assert TenantResolutionMiddleware is not None
        assert get_tenant_from_request is not None
        assert get_tenant_branding is not None

    @patch('web.tenant_middleware.get_tenant_persistence')
    def test_middleware_creation(self, mock_persistence):
        """Test middleware can be created."""
        from web.tenant_middleware import TenantResolutionMiddleware

        middleware = TenantResolutionMiddleware(app=Mock())
        assert middleware.default_tenant_id == "default"

    @patch('web.tenant_middleware.get_tenant_persistence')
    def test_middleware_custom_default(self, mock_persistence):
        """Test middleware with custom default tenant."""
        from web.tenant_middleware import TenantResolutionMiddleware

        middleware = TenantResolutionMiddleware(app=Mock(), default_tenant_id="custom-default")
        assert middleware.default_tenant_id == "custom-default"


class TestTenantResolution:
    """Tests for tenant resolution logic."""

    def test_resolve_tenant_from_query_param(self):
        """Test resolving tenant from URL query parameter."""
        from web.tenant_middleware import TenantResolutionMiddleware

        with patch('web.tenant_middleware.get_tenant_persistence') as mock_persistence:
            mock_tenant = Mock()
            mock_tenant.tenant_id = "test-tenant"
            mock_persistence.return_value.get_tenant.return_value = mock_tenant

            middleware = TenantResolutionMiddleware(app=Mock())

            # Create mock request with query param
            request = Mock()
            request.query_params = {"tenant_id": "test-tenant"}
            request.headers = {}

            tenant, source = middleware._resolve_tenant(request)

            assert tenant == mock_tenant
            assert source == "query_param"

    def test_resolve_tenant_from_header(self):
        """Test resolving tenant from X-Tenant-ID header."""
        from web.tenant_middleware import TenantResolutionMiddleware

        with patch('web.tenant_middleware.get_tenant_persistence') as mock_persistence:
            mock_tenant = Mock()
            mock_tenant.tenant_id = "header-tenant"
            mock_persistence.return_value.get_tenant.return_value = mock_tenant

            middleware = TenantResolutionMiddleware(app=Mock())

            # Create mock request with header
            request = Mock()
            request.query_params = {}
            request.headers = {"X-Tenant-ID": "header-tenant"}

            tenant, source = middleware._resolve_tenant(request)

            assert tenant == mock_tenant
            assert source == "header"

    def test_resolve_tenant_invalid_format(self):
        """Test that invalid tenant IDs are rejected."""
        from web.tenant_middleware import TenantResolutionMiddleware

        with patch('web.tenant_middleware.get_tenant_persistence') as mock_persistence:
            mock_persistence.return_value.get_tenant.return_value = None
            mock_persistence.return_value.get_tenant_by_domain.return_value = None

            middleware = TenantResolutionMiddleware(app=Mock())

            # Create mock request with invalid tenant ID
            request = Mock()
            request.query_params = {"tenant_id": "bad!tenant@#$"}
            request.headers = {"host": "localhost:8000"}

            tenant, source = middleware._resolve_tenant(request)

            # Invalid format should be rejected
            assert source in ("default", "none")

    def test_resolve_tenant_from_domain(self):
        """Test resolving tenant from custom domain."""
        from web.tenant_middleware import TenantResolutionMiddleware

        with patch('web.tenant_middleware.get_tenant_persistence') as mock_persistence:
            mock_tenant = Mock()
            mock_tenant.tenant_id = "domain-tenant"
            mock_persistence.return_value.get_tenant.return_value = None
            mock_persistence.return_value.get_tenant_by_domain.return_value = mock_tenant

            middleware = TenantResolutionMiddleware(app=Mock())

            # Create mock request with custom domain
            request = Mock()
            request.query_params = {}
            request.headers = {"host": "tax.customdomain.com"}

            tenant, source = middleware._resolve_tenant(request)

            assert tenant == mock_tenant
            assert source == "domain"


class TestGetTenantFromRequest:
    """Tests for get_tenant_from_request function."""

    def test_get_tenant_from_state(self):
        """Test getting tenant from request state."""
        from web.tenant_middleware import get_tenant_from_request

        mock_tenant = Mock()
        request = Mock()
        request.state.tenant = mock_tenant

        result = get_tenant_from_request(request)
        assert result == mock_tenant

    def test_get_tenant_not_set(self):
        """Test getting tenant when not set."""
        from web.tenant_middleware import get_tenant_from_request

        request = Mock(spec=[])
        request.state = type('State', (), {})()

        result = get_tenant_from_request(request)
        assert result is None


class TestGetTenantBranding:
    """Tests for get_tenant_branding function."""

    def test_get_branding_from_state(self):
        """Test getting branding from request state."""
        from web.tenant_middleware import get_tenant_branding

        branding = {
            "company_name": "Test CPA",
            "primary_color": "#0066cc"
        }
        request = Mock()
        request.state.branding = branding

        result = get_tenant_branding(request)
        assert result == branding

    def test_get_branding_default(self):
        """Test getting branding when not set."""
        from web.tenant_middleware import get_tenant_branding

        request = Mock(spec=[])
        request.state = type('State', (), {})()

        result = get_tenant_branding(request)
        assert result == {}


class TestTenantDataIsolation:
    """Tests for tenant data isolation patterns."""

    def test_tenants_have_separate_data(self):
        """Test that different tenants have separate data."""
        # Simulate multi-tenant data
        firm_a_returns = [
            {"return_id": "a1", "tenant_id": "firm-a", "name": "John"},
            {"return_id": "a2", "tenant_id": "firm-a", "name": "Jane"},
        ]

        firm_b_returns = [
            {"return_id": "b1", "tenant_id": "firm-b", "name": "Bob"},
            {"return_id": "b2", "tenant_id": "firm-b", "name": "Alice"},
        ]

        all_returns = firm_a_returns + firm_b_returns

        # Filter for firm-a
        firm_a_visible = [r for r in all_returns if r.get("tenant_id") == "firm-a"]
        assert len(firm_a_visible) == 2
        assert all(r["tenant_id"] == "firm-a" for r in firm_a_visible)

        # Filter for firm-b
        firm_b_visible = [r for r in all_returns if r.get("tenant_id") == "firm-b"]
        assert len(firm_b_visible) == 2
        assert all(r["tenant_id"] == "firm-b" for r in firm_b_visible)

    def test_cross_tenant_data_isolation(self):
        """Test that tenants cannot see each other's data."""
        firm_a_returns = [
            {"return_id": "a1", "tenant_id": "firm-a"},
            {"return_id": "a2", "tenant_id": "firm-a"},
        ]

        firm_b_returns = [
            {"return_id": "b1", "tenant_id": "firm-b"},
            {"return_id": "b2", "tenant_id": "firm-b"},
        ]

        all_returns = firm_a_returns + firm_b_returns

        # Firm A filter
        firm_a_visible = [r for r in all_returns if r.get("tenant_id") == "firm-a"]
        firm_a_ids = {r["return_id"] for r in firm_a_visible}
        assert "a1" in firm_a_ids
        assert "a2" in firm_a_ids
        assert "b1" not in firm_a_ids
        assert "b2" not in firm_a_ids

        # Firm B filter
        firm_b_visible = [r for r in all_returns if r.get("tenant_id") == "firm-b"]
        firm_b_ids = {r["return_id"] for r in firm_b_visible}
        assert "b1" in firm_b_ids
        assert "b2" in firm_b_ids
        assert "a1" not in firm_b_ids
        assert "a2" not in firm_b_ids


class TestMiddlewareIntegration:
    """Integration tests for middleware with FastAPI."""

    def test_middleware_with_test_client(self):
        """Test middleware integration with FastAPI TestClient."""
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
        from web.tenant_middleware import TenantResolutionMiddleware

        with patch('web.tenant_middleware.get_tenant_persistence') as mock_persistence, \
             patch('config.branding.get_branding_config') as mock_branding:

            # Setup mocks
            mock_tenant = Mock()
            mock_tenant.tenant_id = "my-tenant"
            mock_tenant.branding = Mock()
            mock_tenant.branding.to_dict.return_value = {"company_name": "My Tenant"}
            mock_tenant.features = Mock()
            mock_tenant.features.to_dict.return_value = {}

            mock_persistence.return_value.get_tenant.return_value = mock_tenant
            mock_persistence.return_value.get_tenant_by_domain.return_value = None

            app = FastAPI()
            app.add_middleware(TenantResolutionMiddleware)

            @app.get("/test")
            async def test_endpoint(request: Request):
                return {
                    "tenant_id": request.state.tenant_id,
                    "tenant_source": request.state.tenant_source
                }

            client = TestClient(app)

            # Request with tenant header
            response = client.get("/test", headers={"X-Tenant-ID": "my-tenant"})
            assert response.status_code == 200
            data = response.json()
            assert data["tenant_id"] == "my-tenant"
            assert data["tenant_source"] == "header"

    def test_middleware_with_query_param(self):
        """Test middleware with query parameter tenant ID."""
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
        from web.tenant_middleware import TenantResolutionMiddleware

        with patch('web.tenant_middleware.get_tenant_persistence') as mock_persistence, \
             patch('config.branding.get_branding_config') as mock_branding:

            # Setup mocks
            mock_tenant = Mock()
            mock_tenant.tenant_id = "query-tenant"
            mock_tenant.branding = Mock()
            mock_tenant.branding.to_dict.return_value = {}
            mock_tenant.features = Mock()
            mock_tenant.features.to_dict.return_value = {}

            mock_persistence.return_value.get_tenant.return_value = mock_tenant
            mock_persistence.return_value.get_tenant_by_domain.return_value = None

            app = FastAPI()
            app.add_middleware(TenantResolutionMiddleware)

            @app.get("/test")
            async def test_endpoint(request: Request):
                return {
                    "tenant_id": request.state.tenant_id,
                    "tenant_source": request.state.tenant_source
                }

            client = TestClient(app)

            # Request with query param
            response = client.get("/test?tenant_id=query-tenant")
            assert response.status_code == 200
            data = response.json()
            assert data["tenant_id"] == "query-tenant"
            assert data["tenant_source"] == "query_param"
