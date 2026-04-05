"""
QuickBooks OAuth2 Configuration Module.

This module defines OAuth2 constants and configuration for QuickBooks Online
integration, including authorization endpoints, token management, and scopes.

OAuth2 Flow:
1. Client initiates authorization at auth_endpoint
2. User logs in and grants scopes
3. QB redirects to redirect_uri with auth code
4. Client exchanges code for access token
5. Client uses access token for API requests
6. Client refreshes token before expiration
"""

from typing import Set, Final


class QuickBooksConfig:
    """QuickBooks OAuth2 Configuration Constants."""

    # Authorization Endpoints
    AUTH_ENDPOINT: Final[str] = "https://appcenter.intuit.com/connect/oauth2"
    TOKEN_ENDPOINT: Final[str] = "https://oauth.platform.intuit.com/oauth2/tokens/introspect"
    API_BASE_URL: Final[str] = "https://quickbooks.api.intuit.com"

    # API Version
    QUICKBOOKS_REALM_ID: Final[str] = "realm_id"  # Placeholder - set per client connection
    QB_API_VERSION: Final[str] = "v2"

    # OAuth2 Scopes for QuickBooks Online
    SCOPES: Final[Set[str]] = {
        "com.intuit.quickbooks.accounting",  # Full accounting access
    }

    # Token Configuration
    TOKEN_LIFETIME_SECONDS: Final[int] = 3600  # 1 hour (QB default)
    REFRESH_BUFFER_SECONDS: Final[int] = 300  # Refresh 5 min before expiration

    # Request Configuration
    REQUEST_TIMEOUT_SECONDS: Final[int] = 30
    MAX_RETRIES: Final[int] = 3
    RETRY_DELAY_SECONDS: Final[int] = 2

    # Validation Rules
    MIN_TOKEN_LENGTH: Final[int] = 50
    MAX_REALM_ID_LENGTH: Final[int] = 20

    @classmethod
    def get_scopes_string(cls) -> str:
        """Return OAuth scopes as space-separated string."""
        return " ".join(cls.SCOPES)

    @classmethod
    def get_authorization_url(cls, client_id: str, redirect_uri: str, state: str) -> str:
        """
        Build QuickBooks authorization URL.

        Args:
            client_id: OAuth client ID from QB app
            redirect_uri: Callback URI for authorization code
            state: CSRF protection token

        Returns:
            Full authorization URL
        """
        params = {
            "client_id": client_id,
            "response_type": "code",
            "scope": cls.get_scopes_string(),
            "redirect_uri": redirect_uri,
            "state": state,
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cls.AUTH_ENDPOINT}?{query_string}"


# OAuth Configuration Instance
QB_CONFIG = QuickBooksConfig()
