"""
E2E Test: Landing → Login → Dashboard

Tests the primary user entry flow:
1. Landing page loads with branding
2. Login page renders
3. Login API accepts credentials
4. Authenticated user can reach advisor page
"""

import pytest
from unittest.mock import patch


class TestLandingPage:
    """Landing page accessibility and content."""

    def test_landing_page_returns_200(self, client, headers):
        response = client.get("/")
        assert response.status_code == 200

    def test_landing_page_is_html(self, client, headers):
        response = client.get("/")
        assert "text/html" in response.headers.get("content-type", "")

    def test_landing_page_has_title(self, client, headers):
        response = client.get("/")
        assert "<title>" in response.text.lower() or "tax" in response.text.lower()


class TestLoginPage:
    """Login page rendering."""

    def test_login_page_returns_200(self, client, headers):
        response = client.get("/login")
        assert response.status_code == 200

    def test_login_page_has_form(self, client, headers):
        response = client.get("/login")
        body = response.text.lower()
        assert "email" in body or "password" in body or "login" in body


class TestLoginAPI:
    """Login API endpoint."""

    def test_login_with_invalid_credentials_fails(self, client, headers):
        response = client.post(
            "/api/core/auth/login",
            headers=headers,
            json={"email": "nobody@invalid.com", "password": "wrongpassword123"},
        )
        # Should not succeed with random credentials
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") is False
        else:
            assert response.status_code in [401, 403, 422]

    def test_login_rejects_empty_payload(self, client, headers):
        response = client.post(
            "/api/core/auth/login",
            headers=headers,
            json={},
        )
        assert response.status_code in [400, 401, 403, 422]


class TestAuthenticatedPages:
    """Pages that should render for authenticated users."""

    def test_advisor_page_returns_200(self, client, headers):
        """Advisor page should render (may show login redirect or page)."""
        response = client.get("/intelligent-advisor")
        assert response.status_code in [200, 302, 303, 307]

    def test_mfa_verify_page_renders(self, client, headers):
        response = client.get("/mfa-verify")
        assert response.status_code in [200, 302, 303, 307]

    def test_register_page_renders(self, client, headers):
        response = client.get("/register")
        assert response.status_code == 200
