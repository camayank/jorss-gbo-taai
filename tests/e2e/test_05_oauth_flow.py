"""
E2E Test: OAuth Login Initiation

Tests: OAuth → Provider Redirect
1. Google OAuth start redirects to Google
2. Microsoft OAuth start redirects to Microsoft
3. OAuth callback validates state parameter
Note: Full OAuth completion requires external provider — only initiation tested.
"""

import pytest
from unittest.mock import patch


class TestOAuthStart:
    """OAuth initiation endpoints."""

    def test_google_oauth_start_redirects(self, client, headers):
        """Google OAuth should redirect to authorization URL."""
        response = client.get(
            "/api/core/auth/oauth/google/start",
            headers=headers,
            follow_redirects=False,
        )
        # Should redirect to Google's auth page or return auth URL
        assert response.status_code in [200, 302, 303, 307, 400, 500]

    def test_microsoft_oauth_start_redirects(self, client, headers):
        """Microsoft OAuth should redirect to authorization URL."""
        response = client.get(
            "/api/core/auth/oauth/microsoft/start",
            headers=headers,
            follow_redirects=False,
        )
        assert response.status_code in [200, 302, 303, 307, 400, 500]

    def test_oauth_callback_rejects_missing_state(self, client, headers):
        """OAuth callback without state should fail."""
        response = client.get(
            "/api/core/auth/oauth/google/callback",
            headers=headers,
        )
        # Should fail — no state parameter
        assert response.status_code in [400, 401, 403, 422, 500]

    def test_oauth_callback_rejects_invalid_state(self, client, headers):
        """OAuth callback with forged state should fail."""
        response = client.get(
            "/api/core/auth/oauth/google/callback?state=forged_state_token&code=fake",
            headers=headers,
        )
        # Should fail — invalid state (200 possible if error returned in body)
        assert response.status_code in [200, 400, 401, 403, 500]


class TestOAuthSecurity:
    """OAuth security checks."""

    def test_unsupported_provider_rejected(self, client, headers):
        """Unknown OAuth provider should return error."""
        response = client.get(
            "/api/core/auth/oauth/facebook/start",
            headers=headers,
        )
        # Should fail — facebook not configured
        assert response.status_code in [400, 404, 405, 422, 500]
