"""
OAuth Service - Social Login Support

Provides OAuth 2.0 authentication for:
- Google Sign-In
- Microsoft Sign-In

Handles the OAuth flow:
1. Generate authorization URL
2. Handle callback with auth code
3. Exchange code for tokens
4. Fetch user profile
5. Create or link user account
"""

import asyncio
import json
import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode
from uuid import uuid4

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis availability check (for OAuth state token persistence)
# ---------------------------------------------------------------------------
try:
    import redis.asyncio as _aioredis
    _REDIS_LIB_AVAILABLE = True
except ImportError:
    _aioredis = None  # type: ignore[assignment]
    _REDIS_LIB_AVAILABLE = False

_IS_PRODUCTION = os.environ.get("APP_ENVIRONMENT", "development").lower() in (
    "production", "prod", "staging"
)

_OAUTH_STATE_TTL = 600  # 10 minutes — matches OAuth flow timeout


# =============================================================================
# CONFIGURATION
# =============================================================================

class OAuthConfig:
    """OAuth provider configuration."""

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    GOOGLE_SCOPES = ["openid", "email", "profile"]

    # Microsoft OAuth
    MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_TENANT = os.environ.get("MICROSOFT_TENANT", "common")  # 'common' for multi-tenant
    MICROSOFT_AUTH_URL = f"https://login.microsoftonline.com/{MICROSOFT_TENANT}/oauth2/v2.0/authorize"
    MICROSOFT_TOKEN_URL = f"https://login.microsoftonline.com/{MICROSOFT_TENANT}/oauth2/v2.0/token"
    MICROSOFT_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"
    MICROSOFT_SCOPES = ["openid", "email", "profile", "User.Read"]

    # Callback URL base (set from environment or request)
    CALLBACK_BASE_URL = os.environ.get("OAUTH_CALLBACK_URL", "http://localhost:8000")

    @classmethod
    def is_google_configured(cls) -> bool:
        """Check if Google OAuth is configured."""
        return bool(cls.GOOGLE_CLIENT_ID and cls.GOOGLE_CLIENT_SECRET)

    @classmethod
    def is_microsoft_configured(cls) -> bool:
        """Check if Microsoft OAuth is configured."""
        return bool(cls.MICROSOFT_CLIENT_ID and cls.MICROSOFT_CLIENT_SECRET)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class OAuthStartResponse(BaseModel):
    """Response when starting OAuth flow."""
    authorization_url: str
    state: str
    provider: str


class OAuthCallbackRequest(BaseModel):
    """Request from OAuth callback."""
    code: str
    state: str
    provider: str


class OAuthUserInfo(BaseModel):
    """Normalized user info from OAuth provider."""
    provider: str
    provider_user_id: str
    email: str
    email_verified: bool
    first_name: str
    last_name: str
    full_name: str
    picture_url: Optional[str] = None
    locale: Optional[str] = None


# =============================================================================
# OAUTH SERVICE
# =============================================================================

class OAuthService:
    """
    Handles OAuth authentication with Google and Microsoft.

    Flow:
    1. Client calls /auth/oauth/{provider}/start to get authorization URL
    2. Client redirects user to authorization URL
    3. User authenticates with provider
    4. Provider redirects back with code
    5. Client calls /auth/oauth/{provider}/callback with code
    6. Service exchanges code for tokens and user info
    7. Service creates/links user and returns session tokens
    """

    def __init__(self, config: OAuthConfig = None):
        self.config = config or OAuthConfig()
        # In-memory fallback for development (no Redis)
        self._state_tokens: Dict[str, Dict] = {}
        self._state_lock = asyncio.Lock()
        # Redis client (lazy-initialized)
        self._redis = None

    # =========================================================================
    # STATE TOKEN PERSISTENCE (Redis with in-memory fallback)
    # =========================================================================

    async def _get_redis(self):
        """Get or create async Redis connection for OAuth state tokens."""
        if self._redis is not None:
            return self._redis

        if not _REDIS_LIB_AVAILABLE:
            if _IS_PRODUCTION:
                raise RuntimeError(
                    "Redis library is required in production for OAuth state token storage."
                )
            return None

        try:
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            client = _aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            await client.ping()
            self._redis = client
            logger.info("Redis connected for OAuth state token storage")
            return self._redis
        except Exception as exc:
            if _IS_PRODUCTION:
                raise RuntimeError(
                    f"Redis is required in production for OAuth state tokens but unavailable: {exc}"
                ) from exc
            logger.warning(
                "Redis unavailable — using in-memory OAuth state tokens (dev only): %s", exc
            )
            return None

    async def _store_state_token(self, state: str, data: Dict[str, Any]) -> None:
        """Store an OAuth state token in Redis (TTL 10 min) or in-memory fallback."""
        r = await self._get_redis()
        if r is not None:
            # Serialize datetime for JSON storage
            serializable = {
                "provider": data["provider"],
                "created_at": data["created_at"].isoformat(),
                "redirect_uri": data.get("redirect_uri"),
            }
            await r.setex(
                f"oauth_state:{state}",
                _OAUTH_STATE_TTL,
                json.dumps(serializable),
            )
        else:
            # Development fallback — in-memory with lock
            async with self._state_lock:
                self._state_tokens[state] = data

    async def _pop_state_token(self, state: str) -> Optional[Dict[str, Any]]:
        """Retrieve and delete an OAuth state token (atomic pop)."""
        r = await self._get_redis()
        if r is not None:
            # GET + DELETE atomically via pipeline
            pipe = r.pipeline()
            pipe.get(f"oauth_state:{state}")
            pipe.delete(f"oauth_state:{state}")
            results = await pipe.execute()
            raw = results[0]
            if raw is None:
                return None
            data = json.loads(raw)
            # Deserialize created_at back to datetime
            data["created_at"] = datetime.fromisoformat(data["created_at"])
            return data
        else:
            # Development fallback — in-memory with lock
            async with self._state_lock:
                return self._state_tokens.pop(state, None)

    # =========================================================================
    # AUTHORIZATION URL GENERATION
    # =========================================================================

    async def start_oauth(self, provider: str, redirect_uri: str = None) -> OAuthStartResponse:
        """
        Generate authorization URL for OAuth provider.

        Args:
            provider: 'google' or 'microsoft'
            redirect_uri: Custom redirect URI (optional)

        Returns:
            OAuthStartResponse with authorization URL and state token
        """
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state token in Redis (or in-memory fallback)
        await self._store_state_token(state, {
            "provider": provider,
            "created_at": datetime.utcnow(),
            "redirect_uri": redirect_uri,
        })

        if provider == "google":
            return self._start_google_oauth(state, redirect_uri)
        elif provider == "microsoft":
            return self._start_microsoft_oauth(state, redirect_uri)
        else:
            raise ValueError(f"Unknown OAuth provider: {provider}")

    def _start_google_oauth(self, state: str, redirect_uri: str = None) -> OAuthStartResponse:
        """Generate Google OAuth authorization URL."""
        if not self.config.is_google_configured():
            raise ValueError("Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")

        callback_url = redirect_uri or f"{self.config.CALLBACK_BASE_URL}/api/core/auth/oauth/google/callback"

        params = {
            "client_id": self.config.GOOGLE_CLIENT_ID,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": " ".join(self.config.GOOGLE_SCOPES),
            "state": state,
            "access_type": "offline",  # Get refresh token
            "prompt": "select_account"  # Always show account chooser
        }

        auth_url = f"{self.config.GOOGLE_AUTH_URL}?{urlencode(params)}"

        return OAuthStartResponse(
            authorization_url=auth_url,
            state=state,
            provider="google"
        )

    def _start_microsoft_oauth(self, state: str, redirect_uri: str = None) -> OAuthStartResponse:
        """Generate Microsoft OAuth authorization URL."""
        if not self.config.is_microsoft_configured():
            raise ValueError("Microsoft OAuth not configured. Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET.")

        callback_url = redirect_uri or f"{self.config.CALLBACK_BASE_URL}/api/core/auth/oauth/microsoft/callback"

        params = {
            "client_id": self.config.MICROSOFT_CLIENT_ID,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": " ".join(self.config.MICROSOFT_SCOPES),
            "state": state,
            "response_mode": "query"
        }

        auth_url = f"{self.config.MICROSOFT_AUTH_URL}?{urlencode(params)}"

        return OAuthStartResponse(
            authorization_url=auth_url,
            state=state,
            provider="microsoft"
        )

    # =========================================================================
    # CALLBACK HANDLING
    # =========================================================================

    async def handle_callback(
        self,
        provider: str,
        code: str,
        state: str,
        redirect_uri: str = None
    ) -> OAuthUserInfo:
        """
        Handle OAuth callback and exchange code for user info.

        Args:
            provider: 'google' or 'microsoft'
            code: Authorization code from provider
            state: State token for CSRF validation
            redirect_uri: Redirect URI used in authorization

        Returns:
            OAuthUserInfo with normalized user data
        """
        # Validate state token (atomic pop from Redis or in-memory)
        state_data = await self._pop_state_token(state)
        if not state_data:
            raise ValueError("Invalid or expired state token")

        # Check state hasn't expired (10 minute max)
        if datetime.utcnow() - state_data["created_at"] > timedelta(minutes=10):
            raise ValueError("State token expired")

        # Exchange code for tokens
        if provider == "google":
            return await self._handle_google_callback(code, redirect_uri or state_data.get("redirect_uri"))
        elif provider == "microsoft":
            return await self._handle_microsoft_callback(code, redirect_uri or state_data.get("redirect_uri"))
        else:
            raise ValueError(f"Unknown OAuth provider: {provider}")

    async def _handle_google_callback(self, code: str, redirect_uri: str = None) -> OAuthUserInfo:
        """Exchange Google auth code for user info."""
        import httpx

        callback_url = redirect_uri or f"{self.config.CALLBACK_BASE_URL}/api/core/auth/oauth/google/callback"

        # SECURITY FIX: Add timeout to prevent hanging requests
        # OAuth token exchanges should complete within 30 seconds
        OAUTH_TIMEOUT = 30.0

        # Exchange code for tokens
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(OAUTH_TIMEOUT, connect=10.0)) as client:
                token_response = await client.post(
                    self.config.GOOGLE_TOKEN_URL,
                    data={
                        "client_id": self.config.GOOGLE_CLIENT_ID,
                        "client_secret": self.config.GOOGLE_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": callback_url
                    }
                )

                if token_response.status_code != 200:
                    logger.error(f"Google token exchange failed: {token_response.text}")
                    raise ValueError("Failed to exchange authorization code")

                tokens = token_response.json()
                access_token = tokens.get("access_token")

                if not access_token:
                    logger.error("Google token response missing access_token")
                    raise ValueError("Invalid token response from Google")

                # Fetch user info
                userinfo_response = await client.get(
                    self.config.GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"}
                )

                if userinfo_response.status_code != 200:
                    logger.error(f"Google userinfo failed: {userinfo_response.text}")
                    raise ValueError("Failed to fetch user information")

                userinfo = userinfo_response.json()

        except httpx.TimeoutException:
            logger.error("Google OAuth request timed out")
            raise ValueError("OAuth request timed out. Please try again.")
        except httpx.ConnectError as e:
            logger.error(f"Google OAuth connection error: {e}")
            raise ValueError("Failed to connect to Google. Please try again.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Google OAuth HTTP error: {e}")
            raise ValueError("Google authentication failed. Please try again.")

        # Normalize user info
        return OAuthUserInfo(
            provider="google",
            provider_user_id=userinfo.get("id"),
            email=userinfo.get("email", ""),
            email_verified=userinfo.get("verified_email", False),
            first_name=userinfo.get("given_name", ""),
            last_name=userinfo.get("family_name", ""),
            full_name=userinfo.get("name", ""),
            picture_url=userinfo.get("picture"),
            locale=userinfo.get("locale")
        )

    async def _handle_microsoft_callback(self, code: str, redirect_uri: str = None) -> OAuthUserInfo:
        """Exchange Microsoft auth code for user info."""
        import httpx

        callback_url = redirect_uri or f"{self.config.CALLBACK_BASE_URL}/api/core/auth/oauth/microsoft/callback"

        # SECURITY FIX: Add timeout to prevent hanging requests
        OAUTH_TIMEOUT = 30.0

        # Exchange code for tokens
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(OAUTH_TIMEOUT, connect=10.0)) as client:
                token_response = await client.post(
                    self.config.MICROSOFT_TOKEN_URL,
                    data={
                        "client_id": self.config.MICROSOFT_CLIENT_ID,
                        "client_secret": self.config.MICROSOFT_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": callback_url,
                        "scope": " ".join(self.config.MICROSOFT_SCOPES)
                    }
                )

                if token_response.status_code != 200:
                    logger.error(f"Microsoft token exchange failed: {token_response.text}")
                    raise ValueError("Failed to exchange authorization code")

                tokens = token_response.json()
                access_token = tokens.get("access_token")

                if not access_token:
                    logger.error("Microsoft token response missing access_token")
                    raise ValueError("Invalid token response from Microsoft")

                # Fetch user info from Microsoft Graph
                userinfo_response = await client.get(
                    self.config.MICROSOFT_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"}
                )

                if userinfo_response.status_code != 200:
                    logger.error(f"Microsoft userinfo failed: {userinfo_response.text}")
                    raise ValueError("Failed to fetch user information")

                userinfo = userinfo_response.json()

        except httpx.TimeoutException:
            logger.error("Microsoft OAuth request timed out")
            raise ValueError("OAuth request timed out. Please try again.")
        except httpx.ConnectError as e:
            logger.error(f"Microsoft OAuth connection error: {e}")
            raise ValueError("Failed to connect to Microsoft. Please try again.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Microsoft OAuth HTTP error: {e}")
            raise ValueError("Microsoft authentication failed. Please try again.")

        # Parse name parts
        display_name = userinfo.get("displayName", "")
        given_name = userinfo.get("givenName", "")
        surname = userinfo.get("surname", "")

        # Normalize user info
        return OAuthUserInfo(
            provider="microsoft",
            provider_user_id=userinfo.get("id"),
            email=userinfo.get("mail") or userinfo.get("userPrincipalName", ""),
            email_verified=True,  # Microsoft emails are verified
            first_name=given_name,
            last_name=surname,
            full_name=display_name or f"{given_name} {surname}".strip(),
            picture_url=None,  # Requires separate API call
            locale=userinfo.get("preferredLanguage")
        )

    # =========================================================================
    # USER CREATION/LINKING
    # =========================================================================

    async def create_or_link_user(self, oauth_info: OAuthUserInfo) -> Dict[str, Any]:
        """
        Create a new user or link OAuth to existing user.

        Args:
            oauth_info: Normalized user info from OAuth provider

        Returns:
            Dict with user_id, is_new_user, and auth tokens
        """
        from .auth_service import get_auth_service, RegisterRequest, AuthResponse
        from ..models.user import UserType, UnifiedUser

        auth_service = get_auth_service()

        # Check if user with this email already exists
        existing_user = auth_service.get_user_by_email(oauth_info.email)

        if existing_user:
            # Link OAuth provider to existing user (store provider info)
            # For now, just log them in
            logger.info(f"OAuth login: existing user {oauth_info.email} via {oauth_info.provider}")

            # Generate tokens for existing user
            access_token = auth_service._generate_access_token(existing_user)
            refresh_token = auth_service._generate_refresh_token(existing_user)

            return {
                "user_id": existing_user.id,
                "is_new_user": False,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": existing_user.id,
                    "email": existing_user.email,
                    "full_name": existing_user.full_name,
                    "user_type": existing_user.user_type.value if hasattr(existing_user.user_type, 'value') else existing_user.user_type
                }
            }

        # Create new user
        logger.info(f"OAuth registration: new user {oauth_info.email} via {oauth_info.provider}")

        # Generate a random password (user won't need it for OAuth login)
        random_password = secrets.token_urlsafe(32)

        new_user = UnifiedUser(
            id=str(uuid4()),
            email=oauth_info.email.lower(),
            user_type=UserType.CONSUMER,
            first_name=oauth_info.first_name,
            last_name=oauth_info.last_name,
            password_hash=auth_service._hash_password(random_password),
            email_verified=oauth_info.email_verified,
            is_self_service=True,
            oauth_provider=oauth_info.provider,
            oauth_provider_id=oauth_info.provider_user_id
        )

        # Save to mock DB
        auth_service._users_db[new_user.id] = new_user
        auth_service._users_db[new_user.email] = new_user

        # Generate tokens
        access_token = auth_service._generate_access_token(new_user)
        refresh_token = auth_service._generate_refresh_token(new_user)

        return {
            "user_id": new_user.id,
            "is_new_user": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "user_type": new_user.user_type.value if hasattr(new_user.user_type, 'value') else new_user.user_type
            }
        }


# =============================================================================
# SERVICE SINGLETON
# =============================================================================

_oauth_service: Optional[OAuthService] = None


def get_oauth_service() -> OAuthService:
    """Get the singleton OAuth service instance."""
    global _oauth_service
    if _oauth_service is None:
        _oauth_service = OAuthService()
    return _oauth_service
