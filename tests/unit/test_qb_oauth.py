"""Tests for QuickBooks OAuth2 authorization code flow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from urllib.parse import urlparse, parse_qs

from integrations.quickbooks.oauth import QuickBooksOAuthClient
from integrations.quickbooks.config import QB_CONFIG


class TestQuickBooksOAuthClient:
    """Test suite for QuickBooks OAuth2 client."""

    @pytest.fixture
    def oauth_client(self):
        """Create OAuth client for testing."""
        return QuickBooksOAuthClient(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://example.com/callback"
        )

    # =========================================================================
    # Authorization URL Generation Tests
    # =========================================================================

    def test_get_authorization_url_returns_tuple(self, oauth_client):
        """get_authorization_url returns (url, state) tuple."""
        url, state = oauth_client.get_authorization_url()
        assert isinstance(url, str)
        assert isinstance(state, str)

    def test_get_authorization_url_includes_client_id(self, oauth_client):
        """Authorization URL includes required client_id parameter."""
        url, state = oauth_client.get_authorization_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "client_id" in params
        assert params["client_id"][0] == "test-client-id"

    def test_get_authorization_url_includes_redirect_uri(self, oauth_client):
        """Authorization URL includes required redirect_uri parameter."""
        url, state = oauth_client.get_authorization_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "redirect_uri" in params
        assert params["redirect_uri"][0] == "https://example.com/callback"

    def test_get_authorization_url_includes_state(self, oauth_client):
        """Authorization URL includes state parameter for CSRF protection."""
        url, state = oauth_client.get_authorization_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "state" in params
        assert params["state"][0] == state

    def test_get_authorization_url_includes_response_type(self, oauth_client):
        """Authorization URL includes response_type=code parameter."""
        url, state = oauth_client.get_authorization_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "response_type" in params
        assert params["response_type"][0] == "code"

    def test_get_authorization_url_includes_scope(self, oauth_client):
        """Authorization URL includes required scope parameter."""
        url, state = oauth_client.get_authorization_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "scope" in params
        assert "com.intuit.quickbooks.accounting" in params["scope"][0]

    def test_get_authorization_url_base_is_correct(self, oauth_client):
        """Authorization URL uses correct QB authorization endpoint."""
        url, state = oauth_client.get_authorization_url()
        assert url.startswith(QB_CONFIG.AUTHORIZATION_URI)

    # =========================================================================
    # State Token Tests
    # =========================================================================

    def test_state_token_is_32_characters(self, oauth_client):
        """Generated state token is 32 characters."""
        _, state = oauth_client.get_authorization_url()
        assert len(state) == 32

    def test_state_token_is_random(self, oauth_client):
        """Generated state tokens are different each time."""
        _, state1 = oauth_client.get_authorization_url()
        _, state2 = oauth_client.get_authorization_url()
        assert state1 != state2

    def test_state_token_is_alphanumeric(self, oauth_client):
        """State token contains only alphanumeric characters."""
        _, state = oauth_client.get_authorization_url()
        assert state.isalnum()

    def test_state_is_stored_in_cache(self, oauth_client):
        """State token is cached for later validation."""
        _, state = oauth_client.get_authorization_url()
        # State should be retrievable for validation
        assert oauth_client._is_state_valid(state)

    # =========================================================================
    # State Validation Tests (CSRF Protection)
    # =========================================================================

    def test_validate_state_accepts_valid_state(self, oauth_client):
        """Valid state token passes validation."""
        _, state = oauth_client.get_authorization_url()
        # Should not raise
        oauth_client.validate_state(state)

    def test_validate_state_rejects_invalid_state(self, oauth_client):
        """Invalid state token raises ValueError."""
        _, state = oauth_client.get_authorization_url()
        with pytest.raises(ValueError, match="Invalid state"):
            oauth_client.validate_state("wrong-state-value")

    def test_validate_state_rejects_reused_state(self, oauth_client):
        """State token can only be used once (CSRF protection)."""
        _, state = oauth_client.get_authorization_url()
        # First validation should pass
        oauth_client.validate_state(state)
        # Second validation with same state should fail
        with pytest.raises(ValueError, match="Invalid state"):
            oauth_client.validate_state(state)

    def test_validate_state_empty_string_raises(self, oauth_client):
        """Empty state string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid state"):
            oauth_client.validate_state("")

    def test_validate_state_none_raises(self, oauth_client):
        """None state raises ValueError."""
        with pytest.raises(ValueError, match="Invalid state"):
            oauth_client.validate_state(None)

    # =========================================================================
    # Token Exchange Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_validates_state(self, oauth_client):
        """exchange_code_for_token validates CSRF state before token exchange."""
        with pytest.raises(ValueError, match="Invalid state"):
            await oauth_client.exchange_code_for_token(
                auth_code="some-code",
                state="invalid-state"
            )

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_posts_to_token_uri(self, oauth_client):
        """exchange_code_for_token POSTs to QB TOKEN_URI."""
        _, state = oauth_client.get_authorization_url()

        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await oauth_client.exchange_code_for_token(
                auth_code="test-code",
                state=state
            )

            # Verify POST was made to token endpoint
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert QB_CONFIG.TOKEN_URI in str(call_args)

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_uses_basic_auth(self, oauth_client):
        """exchange_code_for_token uses Basic auth (client_id:client_secret)."""
        _, state = oauth_client.get_authorization_url()

        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await oauth_client.exchange_code_for_token(
                auth_code="test-code",
                state=state
            )

            # Verify Basic auth header was set
            call_kwargs = mock_post.call_args.kwargs
            assert "headers" in call_kwargs
            headers = call_kwargs["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"].startswith("Basic ")

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_returns_token_response(self, oauth_client):
        """exchange_code_for_token returns token_response dict."""
        _, state = oauth_client.get_authorization_url()

        token_data = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

        mock_response = MagicMock()
        mock_response.json.return_value = token_data
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await oauth_client.exchange_code_for_token(
                auth_code="test-code",
                state=state
            )

            assert result["access_token"] == "test-access-token"
            assert result["refresh_token"] == "test-refresh-token"
            assert result["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_raises_on_api_error(self, oauth_client):
        """exchange_code_for_token raises exception on API error."""
        _, state = oauth_client.get_authorization_url()

        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(Exception):  # Could be specific exception type
                await oauth_client.exchange_code_for_token(
                    auth_code="test-code",
                    state=state
                )

    # =========================================================================
    # Token Refresh Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_refresh_token_posts_to_token_uri(self, oauth_client):
        """refresh_token POSTs to QB TOKEN_URI."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await oauth_client.refresh_token("test-refresh-token")

            # Verify POST was made to token endpoint
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert QB_CONFIG.TOKEN_URI in str(call_args)

    @pytest.mark.asyncio
    async def test_refresh_token_uses_basic_auth(self, oauth_client):
        """refresh_token uses Basic auth."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await oauth_client.refresh_token("test-refresh-token")

            # Verify Basic auth header was set
            call_kwargs = mock_post.call_args.kwargs
            assert "headers" in call_kwargs
            headers = call_kwargs["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"].startswith("Basic ")

    @pytest.mark.asyncio
    async def test_refresh_token_returns_new_token(self, oauth_client):
        """refresh_token returns new access token."""
        token_data = {
            "access_token": "new-access-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

        mock_response = MagicMock()
        mock_response.json.return_value = token_data
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await oauth_client.refresh_token("test-refresh-token")

            assert result["access_token"] == "new-access-token"
            assert result["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_refresh_token_raises_on_api_error(self, oauth_client):
        """refresh_token raises exception on API error."""
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(Exception):  # Could be specific exception type
                await oauth_client.refresh_token("invalid-refresh-token")
