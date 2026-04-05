"""
QuickBooks OAuth2 Authorization Code Flow Implementation.

This module implements the OAuth2 authorization code flow for QuickBooks Online,
including authorization URL generation, code exchange, CSRF protection via state
tokens, and token refresh functionality.

OAuth2 Flow:
1. get_authorization_url() - Generate authorization URL with state token
2. validate_state() - Validate state token for CSRF protection
3. exchange_code_for_token() - Exchange auth code for access/refresh tokens
4. refresh_token() - Refresh access token before expiration
"""

import secrets
import base64
import asyncio
import logging
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timezone

from .config import QB_CONFIG


logger = logging.getLogger(__name__)


class QuickBooksOAuthClient:
    """
    QuickBooks OAuth2 Client.

    Implements the OAuth2 authorization code flow with CSRF protection.
    State tokens are cached and validated to prevent replay attacks.

    Attributes:
        client_id: OAuth client ID from QB app
        client_secret: OAuth client secret from QB app
        redirect_uri: Callback URI for authorization code
        _state_cache: Set of valid state tokens (cleared after use)
    """

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """
        Initialize QuickBooks OAuth Client.

        Args:
            client_id: OAuth client ID from QB app
            client_secret: OAuth client secret from QB app
            redirect_uri: Callback URI for authorization code
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._state_cache: Dict[str, bool] = {}  # state -> is_valid

    def get_authorization_url(self) -> Tuple[str, str]:
        """
        Generate QuickBooks authorization URL with CSRF protection state token.

        Returns:
            Tuple of (authorization_url, state_token)
                - authorization_url: Full URL to redirect user to QB login
                - state_token: Random 32-char alphanumeric token for CSRF validation

        Example:
            url, state = client.get_authorization_url()
            redirect(url)  # Send user to QB login
            # After user authorizes, QB redirects to redirect_uri with code and state
        """
        # Generate random 32-character state token for CSRF protection
        state = secrets.token_hex(16)  # 32 hex chars = 16 bytes

        # Store state in cache for validation
        self._state_cache[state] = True

        # Build authorization URL using config
        url = QB_CONFIG.get_authorization_url(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            state=state
        )

        logger.debug(f"Generated authorization URL with state: {state[:8]}...")
        return url, state

    def validate_state(self, state: Optional[str]) -> None:
        """
        Validate state token for CSRF protection.

        State tokens are single-use: once validated, they are removed from
        the cache to prevent replay attacks.

        Args:
            state: State token from authorization callback

        Raises:
            ValueError: If state is invalid, expired, or already used
        """
        if not state:
            raise ValueError("Invalid state: state token is required")

        if state not in self._state_cache:
            raise ValueError("Invalid state: state token not recognized or already used")

        # State is valid - remove from cache (single-use)
        del self._state_cache[state]
        logger.debug(f"State validated and consumed: {state[:8]}...")

    def _is_state_valid(self, state: str) -> bool:
        """
        Check if state token is valid (internal use only).

        Args:
            state: State token to check

        Returns:
            True if state is in cache and valid, False otherwise
        """
        return state in self._state_cache

    async def exchange_code_for_token(
        self,
        auth_code: str,
        state: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.

        Validates state token for CSRF protection, then exchanges the
        authorization code for OAuth tokens using Basic authentication.

        Args:
            auth_code: Authorization code from QB callback
            state: State token from QB callback (must match original)

        Returns:
            Dictionary with token response:
                {
                    "access_token": "...",
                    "refresh_token": "...",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "x_refresh_token_expires_in": ...
                }

        Raises:
            ValueError: If state token is invalid
            Exception: If token exchange fails

        Example:
            try:
                tokens = await client.exchange_code_for_token(
                    auth_code=request.code,
                    state=request.state
                )
                access_token = tokens["access_token"]
            except ValueError:
                # CSRF attack detected
                return error_response(400, "Invalid request")
        """
        # Validate state for CSRF protection
        self.validate_state(state)

        logger.debug("State validated, exchanging code for token...")

        # Prepare Basic Auth header (client_id:client_secret in base64)
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(
            credentials.encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self.redirect_uri,
        }

        # Exchange code for token
        import httpx

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(QB_CONFIG.REQUEST_TIMEOUT_SECONDS, connect=10.0)
            ) as client:
                response = await client.post(
                    QB_CONFIG.TOKEN_URI,
                    headers=headers,
                    data=data,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Token exchange failed: {response.status_code} - {response.text}"
                    )
                    raise Exception(
                        f"Token exchange failed: {response.status_code} - {response.text}"
                    )

                token_response = response.json()
                logger.info("Token exchange successful")
                return token_response

        except httpx.TimeoutException:
            logger.error("Token exchange request timed out")
            raise Exception("Token exchange request timed out")
        except Exception as e:
            logger.error(f"Token exchange error: {str(e)}")
            raise

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh OAuth access token using refresh token.

        Posts refresh_token to QB token endpoint to get a new access token.
        Uses Basic authentication (client_id:client_secret).

        Args:
            refresh_token: Refresh token from previous token response

        Returns:
            Dictionary with new token response:
                {
                    "access_token": "...",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    ...
                }

        Raises:
            Exception: If token refresh fails

        Example:
            try:
                new_tokens = await client.refresh_token(old_refresh_token)
                access_token = new_tokens["access_token"]
                # Update stored token
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                # Handle refresh failure
        """
        logger.debug("Refreshing access token...")

        # Prepare Basic Auth header
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(
            credentials.encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        # Refresh token
        import httpx

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(QB_CONFIG.REQUEST_TIMEOUT_SECONDS, connect=10.0)
            ) as client:
                response = await client.post(
                    QB_CONFIG.TOKEN_URI,
                    headers=headers,
                    data=data,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Token refresh failed: {response.status_code} - {response.text}"
                    )
                    raise Exception(
                        f"Token refresh failed: {response.status_code} - {response.text}"
                    )

                token_response = response.json()
                logger.info("Token refresh successful")
                return token_response

        except httpx.TimeoutException:
            logger.error("Token refresh request timed out")
            raise Exception("Token refresh request timed out")
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise
