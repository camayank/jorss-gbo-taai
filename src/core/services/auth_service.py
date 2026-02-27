"""
Core Authentication Service

Unified authentication for all user types:
- Email/password login
- Magic link authentication (for consumers)
- JWT token generation and validation
- Password hashing and verification
- MFA support

This service is the single source of truth for authentication
across Consumer Portal, CPA Panel, and Admin Panel.
"""

import json
import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from uuid import uuid4
import logging

import jwt as pyjwt

from pydantic import BaseModel, EmailStr, Field

from ..models.user import UnifiedUser, UserType, UserContext, CPARole
from admin_panel.auth.password import hash_password as bcrypt_hash, verify_password as bcrypt_verify

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis availability check (used for refresh-token and magic-link storage)
# ---------------------------------------------------------------------------
try:
    import redis.asyncio as _aioredis
    _REDIS_LIB_AVAILABLE = True
except ImportError:
    _aioredis = None  # type: ignore[assignment]
    _REDIS_LIB_AVAILABLE = False


def _get_redis_url() -> str:
    """Return the configured Redis URL."""
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


# =============================================================================
# CONFIGURATION
# =============================================================================

# Environment detection
_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "development")
_IS_PRODUCTION = _ENVIRONMENT in ("production", "prod", "staging")

# Database mode flag
# In production, default to database mode; in dev, default to mock mode
_USE_DB_DEFAULT = "true" if _IS_PRODUCTION else "false"
USE_DATABASE = os.environ.get("AUTH_USE_DATABASE", _USE_DB_DEFAULT).lower() == "true"


def _get_password_salt() -> str:
    """
    Get password salt from environment.

    SECURITY: In production, PASSWORD_SALT must be set.
    """
    salt = os.environ.get("PASSWORD_SALT")

    if not salt:
        if _IS_PRODUCTION:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: PASSWORD_SALT environment variable is required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(16))\""
            )
        # Development fallback
        import warnings
        warnings.warn(
            "PASSWORD_SALT not set - using insecure development default.",
            UserWarning
        )
        return "DEV-SALT-INSECURE-" + str(os.getpid())

    if len(salt) < 16:
        raise ValueError("PASSWORD_SALT must be at least 16 characters")

    return salt


def _get_auth_secret() -> str:
    """
    Get auth secret from environment.

    SECURITY: In production, AUTH_SECRET_KEY must be set.
    """
    secret = os.environ.get("AUTH_SECRET_KEY")

    if not secret:
        if _IS_PRODUCTION:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: AUTH_SECRET_KEY environment variable is required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        import warnings
        warnings.warn(
            "AUTH_SECRET_KEY not set - using insecure development default.",
            UserWarning
        )
        return "DEV-AUTH-SECRET-INSECURE-" + str(os.getpid())

    if len(secret) < 32:
        raise ValueError("AUTH_SECRET_KEY must be at least 32 characters")

    return secret


class AuthConfig:
    """Authentication configuration."""
    # JWT Settings - now loaded from environment
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Magic Link Settings
    MAGIC_LINK_EXPIRE_MINUTES: int = 15

    # Password Settings
    MIN_PASSWORD_LENGTH: int = 8
    BCRYPT_ROUNDS: int = 12

    # Rate Limiting
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    @classmethod
    def get_jwt_secret(cls) -> str:
        """Get JWT secret key (validates on first access in production)."""
        return _get_auth_secret()

    @classmethod
    def get_password_salt(cls) -> str:
        """Get password salt (validates on first access in production)."""
        return _get_password_salt()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class LoginRequest(BaseModel):
    """Email/password login request."""
    email: str
    password: str
    remember_me: bool = False


class MagicLinkRequest(BaseModel):
    """Magic link login request (for consumers)."""
    email: str


class RegisterRequest(BaseModel):
    """User registration request."""
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""
    phone: Optional[str] = None
    user_type: UserType = UserType.CONSUMER
    # For CPA team registration
    firm_id: Optional[str] = None
    cpa_role: Optional[CPARole] = None
    # For CPA client registration
    assigned_cpa_id: Optional[str] = None


class AuthResponse(BaseModel):
    """Authentication response with tokens."""
    success: bool
    message: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = 3600  # seconds
    user: Optional[Dict[str, Any]] = None


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # user_id
    email: str
    user_type: str
    firm_id: Optional[str] = None
    permissions: list = []
    exp: datetime
    iat: datetime
    jti: str  # unique token ID


# =============================================================================
# CORE AUTH SERVICE
# =============================================================================

class CoreAuthService:
    """
    Unified authentication service for all user types.

    Provides:
    - Email/password authentication
    - Magic link authentication
    - JWT token management
    - Password hashing
    - User registration

    Supports two modes:
    - Database mode (AUTH_USE_DATABASE=true): Uses real database via UserAuthRepository
    - Mock mode (default): Uses in-memory data for development
    """

    def __init__(self, config: AuthConfig = None, use_database: bool = None):
        self.config = config or AuthConfig()
        self._use_database = use_database if use_database is not None else USE_DATABASE

        # In-memory storage (development fallback for magic links, refresh tokens)
        self._users_db: Dict[str, UnifiedUser] = {}  # Mock DB - used when not using database
        self._magic_links: Dict[str, Dict] = {}  # token -> {user_id, expires_at}
        self._refresh_tokens: Dict[str, Dict] = {}  # token -> {user_id, expires_at}

        # Redis client for token storage (lazy-initialized)
        self._redis = None

        # Database repository (lazy-initialized)
        self._user_repo = None

        # In production, Redis is REQUIRED for token storage
        if _IS_PRODUCTION and not _REDIS_LIB_AVAILABLE:
            raise RuntimeError(
                "CRITICAL: redis package is required in production for token storage. "
                "Install with: pip install redis[hiredis]"
            )

        # Initialize with mock users for development (when not using database)
        if not self._use_database:
            env = os.environ.get("APP_ENVIRONMENT", "").lower()
            if env in ("production", "prod", "staging"):
                raise RuntimeError(
                    "FATAL: AUTH_USE_DATABASE must be 'true' in production. "
                    "Cannot use mock authentication users."
                )
            self._init_mock_users()
            logger.info("Auth service initialized in MOCK mode (in-memory users)")
        else:
            logger.info("Auth service initialized in DATABASE mode")

    def _init_mock_users(self):
        """Initialize mock users for development."""
        # Consumer user
        consumer = UnifiedUser(
            id="user-consumer-001",
            email="consumer@example.com",
            user_type=UserType.CONSUMER,
            first_name="John",
            last_name="Consumer",
            password_hash=self._hash_password("password123"),
            email_verified=True,
            is_self_service=True
        )
        self._users_db[consumer.id] = consumer
        self._users_db[consumer.email] = consumer

        # CPA Client user
        cpa_client = UnifiedUser(
            id="user-client-001",
            email="client@example.com",
            user_type=UserType.CPA_CLIENT,
            first_name="Jane",
            last_name="Client",
            password_hash=self._hash_password("password123"),
            email_verified=True,
            firm_id="firm-001",
            assigned_cpa_id="user-cpa-001",
            assigned_cpa_name="Mike Preparer",
            is_self_service=False
        )
        self._users_db[cpa_client.id] = cpa_client
        self._users_db[cpa_client.email] = cpa_client

        # CPA Team user
        cpa_team = UnifiedUser(
            id="user-cpa-001",
            email="cpa@example.com",
            user_type=UserType.CPA_TEAM,
            first_name="Mike",
            last_name="Preparer",
            password_hash=self._hash_password("password123"),
            email_verified=True,
            firm_id="firm-001",
            firm_name="Best Tax Services",
            cpa_role=CPARole.SENIOR_PREPARER,
            ptin="P12345678",
            credentials="CPA",
            permissions=["view_clients", "edit_returns", "create_scenarios", "send_messages"]
        )
        self._users_db[cpa_team.id] = cpa_team
        self._users_db[cpa_team.email] = cpa_team

        # Firm Admin user
        firm_admin = UnifiedUser(
            id="user-admin-001",
            email="firmadmin@example.com",
            user_type=UserType.CPA_TEAM,
            first_name="Sarah",
            last_name="Admin",
            password_hash=self._hash_password("password123"),
            email_verified=True,
            firm_id="firm-001",
            firm_name="Best Tax Services",
            cpa_role=CPARole.FIRM_ADMIN,
            credentials="CPA",
            permissions=["manage_team", "manage_billing", "view_clients", "edit_returns", "approve_returns"]
        )
        self._users_db[firm_admin.id] = firm_admin
        self._users_db[firm_admin.email] = firm_admin

        # Platform Admin user
        platform_admin = UnifiedUser(
            id="user-platform-001",
            email="platform@example.com",
            user_type=UserType.PLATFORM_ADMIN,
            first_name="Platform",
            last_name="Admin",
            password_hash=self._hash_password("password123"),
            email_verified=True,
            permissions=["*"]  # All permissions
        )
        self._users_db[platform_admin.id] = platform_admin
        self._users_db[platform_admin.email] = platform_admin

    # =========================================================================
    # REDIS TOKEN STORAGE HELPERS
    # =========================================================================

    async def _get_redis(self):
        """
        Get or create the async Redis connection for token storage.

        In production, raises RuntimeError if Redis is unreachable.
        In development, returns None (caller falls back to in-memory).
        """
        if self._redis is not None:
            return self._redis

        if not _REDIS_LIB_AVAILABLE:
            if _IS_PRODUCTION:
                raise RuntimeError(
                    "Redis library is required in production for token storage."
                )
            return None

        try:
            client = _aioredis.from_url(
                _get_redis_url(),
                decode_responses=True,
                socket_connect_timeout=5,
            )
            await client.ping()
            self._redis = client
            logger.info("Redis connected for auth token storage")
            return self._redis
        except Exception as exc:
            if _IS_PRODUCTION:
                raise RuntimeError(
                    f"Redis is required in production but unavailable: {exc}"
                ) from exc
            logger.warning(
                "Redis unavailable — using in-memory token storage (dev only): %s", exc
            )
            return None

    # -- Refresh tokens -------------------------------------------------------

    async def _store_refresh_token_redis(
        self, token: str, data: Dict[str, Any], ttl: int
    ) -> None:
        """Store a refresh token in Redis with TTL."""
        r = await self._get_redis()
        if r is not None:
            await r.setex(
                f"refresh_token:{token}",
                ttl,
                json.dumps(data, default=str),
            )
        else:
            # Development fallback
            self._refresh_tokens[token] = data

    async def _get_refresh_token_redis(self, token: str) -> Optional[Dict]:
        """Retrieve a refresh token from Redis (or in-memory fallback)."""
        r = await self._get_redis()
        if r is not None:
            raw = await r.get(f"refresh_token:{token}")
            if raw is None:
                return None
            return json.loads(raw)
        else:
            return self._refresh_tokens.get(token)

    async def _delete_refresh_token_redis(self, token: str) -> None:
        """Delete a refresh token from Redis (or in-memory fallback)."""
        r = await self._get_redis()
        if r is not None:
            await r.delete(f"refresh_token:{token}")
        else:
            self._refresh_tokens.pop(token, None)

    # -- Magic link tokens ----------------------------------------------------

    async def _store_magic_link_redis(
        self, token: str, data: Dict[str, Any], ttl: int
    ) -> None:
        """Store a magic link token in Redis with TTL."""
        r = await self._get_redis()
        if r is not None:
            await r.setex(
                f"magic_link:{token}",
                ttl,
                json.dumps(data, default=str),
            )
        else:
            self._magic_links[token] = data

    async def _get_magic_link_redis(self, token: str) -> Optional[Dict]:
        """Retrieve a magic link token from Redis (or in-memory fallback)."""
        r = await self._get_redis()
        if r is not None:
            raw = await r.get(f"magic_link:{token}")
            if raw is None:
                return None
            return json.loads(raw)
        else:
            return self._magic_links.get(token)

    async def _delete_magic_link_redis(self, token: str) -> None:
        """Delete a magic link token from Redis (or in-memory fallback)."""
        r = await self._get_redis()
        if r is not None:
            await r.delete(f"magic_link:{token}")
        else:
            self._magic_links.pop(token, None)

    # =========================================================================
    # PASSWORD MANAGEMENT
    # =========================================================================

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt via admin_panel.auth.password."""
        return bcrypt_hash(password)

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.

        Supports bcrypt (preferred) and legacy SHA-256 hashes for migration.
        On successful SHA-256 verification, the caller should rehash with bcrypt.
        """
        # Try bcrypt first (new format)
        if bcrypt_verify(password, password_hash):
            return True

        # Fallback: try legacy SHA-256 for migration
        salt = AuthConfig.get_password_salt()
        legacy_hash = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        if legacy_hash == password_hash:
            logger.info("Legacy SHA-256 password matched - should be rehashed to bcrypt")
            return True

        return False

    def _validate_password(self, password: str) -> Tuple[bool, str]:
        """Validate password meets requirements."""
        if len(password) < self.config.MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {self.config.MIN_PASSWORD_LENGTH} characters"
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        return True, ""

    # =========================================================================
    # TOKEN MANAGEMENT
    # =========================================================================

    def _generate_access_token(self, user: UnifiedUser) -> str:
        """Generate a properly signed JWT access token."""
        now = datetime.utcnow()
        payload = {
            "sub": user.id,
            "email": user.email,
            "user_type": user.user_type.value if isinstance(user.user_type, UserType) else user.user_type,
            "firm_id": user.firm_id,
            "permissions": user.permissions,
            "exp": now + timedelta(minutes=self.config.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": now,
            "jti": str(uuid4()),
        }

        return pyjwt.encode(payload, AuthConfig.get_jwt_secret(), algorithm="HS256")

    async def _generate_refresh_token(self, user: UnifiedUser) -> str:
        """Generate refresh token and store in Redis (or in-memory fallback)."""
        token = f"refresh_{secrets.token_urlsafe(32)}"
        ttl_seconds = self.config.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        expires_at = datetime.utcnow() + timedelta(days=self.config.REFRESH_TOKEN_EXPIRE_DAYS)

        await self._store_refresh_token_redis(
            token,
            {"user_id": user.id, "expires_at": expires_at.isoformat()},
            ttl=ttl_seconds,
        )

        return token

    async def _generate_magic_link_token(self, user: UnifiedUser) -> str:
        """Generate magic link token and store in Redis (or in-memory fallback)."""
        token = f"magic_{secrets.token_urlsafe(32)}"
        ttl_seconds = self.config.MAGIC_LINK_EXPIRE_MINUTES * 60
        expires_at = datetime.utcnow() + timedelta(minutes=self.config.MAGIC_LINK_EXPIRE_MINUTES)

        await self._store_magic_link_redis(
            token,
            {
                "user_id": user.id,
                "email": user.email,
                "expires_at": expires_at.isoformat(),
            },
            ttl=ttl_seconds,
        )

        return token

    def validate_access_token(self, token: str) -> Optional[UserContext]:
        """Validate a signed JWT access token and return user context."""
        if not token:
            return None

        # Support legacy "core_" prefixed tokens during migration
        if token.startswith("core_"):
            token = token[5:]

        try:
            payload = pyjwt.decode(
                token, AuthConfig.get_jwt_secret(), algorithms=["HS256"]
            )

            # Get user
            user = self._users_db.get(payload["sub"])
            if not user:
                return None

            return UserContext.from_user(user, request_id=payload.get("jti"))

        except pyjwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except pyjwt.InvalidTokenError as e:
            logger.warning(f"Token validation failed: {e}")
            return None

    # =========================================================================
    # AUTHENTICATION METHODS
    # =========================================================================

    async def login(self, request: LoginRequest) -> AuthResponse:
        """
        Authenticate user with email and password.

        Works for all user types: consumer, CPA client, CPA team, platform admin.
        """
        # Find user by email
        user = self._users_db.get(request.email.lower())

        if not user:
            logger.warning(f"Login failed: user not found - {request.email}")
            return AuthResponse(
                success=False,
                message="Invalid email or password"
            )

        # Verify password
        if not self._verify_password(request.password, user.password_hash):
            logger.warning(f"Login failed: invalid password - {request.email}")
            return AuthResponse(
                success=False,
                message="Invalid email or password"
            )

        # Rehash legacy SHA-256 passwords to bcrypt on successful login
        if not user.password_hash.startswith("$2"):
            user.password_hash = self._hash_password(request.password)
            logger.info(f"Rehashed legacy password to bcrypt for {request.email}")

        # Check if user is active
        if not user.is_active:
            return AuthResponse(
                success=False,
                message="Account is disabled"
            )

        # Generate tokens
        access_token = self._generate_access_token(user)
        refresh_token = (await self._generate_refresh_token(user)) if request.remember_me else None

        # Update last login
        user.last_login_at = datetime.utcnow()

        logger.info(f"Login successful: {user.email} ({user.user_type})")

        return AuthResponse(
            success=True,
            message="Login successful",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type.value if isinstance(user.user_type, UserType) else user.user_type,
                "firm_id": user.firm_id,
                "firm_name": user.firm_name
            }
        )

    async def request_magic_link(self, request: MagicLinkRequest) -> AuthResponse:
        """
        Request a magic link for passwordless login.

        Primarily used for consumer users.
        """
        user = self._users_db.get(request.email.lower())

        if not user:
            # Don't reveal if user exists
            return AuthResponse(
                success=True,
                message="If an account exists, a login link has been sent"
            )

        # Generate magic link token
        token = await self._generate_magic_link_token(user)

        # In production: send email with link
        magic_link = f"/auth/magic-link?token={token}"
        logger.info(f"Magic link generated (token_prefix={token[:8]}...)")

        # In dev, include token for testing; in production, token is only sent via email
        _env = os.environ.get("APP_ENVIRONMENT", "development").lower()
        _is_dev = _env in ("development", "dev", "local", "test", "testing")

        return AuthResponse(
            success=True,
            message="If an account exists, a login link has been sent",
            access_token=token if _is_dev else None,
        )

    async def verify_magic_link(self, token: str) -> AuthResponse:
        """Verify magic link and authenticate user."""
        link_data = await self._get_magic_link_redis(token)

        if not link_data:
            return AuthResponse(
                success=False,
                message="Invalid or expired link"
            )

        # Check expiration (handle both datetime and ISO string formats)
        expires_at = link_data["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if datetime.utcnow() > expires_at:
            await self._delete_magic_link_redis(token)
            return AuthResponse(
                success=False,
                message="Link has expired"
            )

        # Get user
        user = self._users_db.get(link_data["user_id"])
        if not user:
            return AuthResponse(
                success=False,
                message="User not found"
            )

        # Generate access token
        access_token = self._generate_access_token(user)
        refresh_token = await self._generate_refresh_token(user)

        # Clean up used magic link
        await self._delete_magic_link_redis(token)

        # Update last login
        user.last_login_at = datetime.utcnow()

        return AuthResponse(
            success=True,
            message="Login successful",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type.value if isinstance(user.user_type, UserType) else user.user_type
            }
        )

    async def refresh_access_token(self, refresh_token: str) -> AuthResponse:
        """Refresh access token using refresh token."""
        token_data = await self._get_refresh_token_redis(refresh_token)

        if not token_data:
            return AuthResponse(
                success=False,
                message="Invalid refresh token"
            )

        # Check expiration (handle both datetime and ISO string formats)
        expires_at = token_data["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if datetime.utcnow() > expires_at:
            await self._delete_refresh_token_redis(refresh_token)
            return AuthResponse(
                success=False,
                message="Refresh token has expired"
            )

        # Get user
        user = self._users_db.get(token_data["user_id"])
        if not user:
            return AuthResponse(
                success=False,
                message="User not found"
            )

        # Generate new access token
        access_token = self._generate_access_token(user)

        return AuthResponse(
            success=True,
            message="Token refreshed",
            access_token=access_token,
            expires_in=self.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    async def register(self, request: RegisterRequest) -> AuthResponse:
        """
        Register a new user.

        Supports all user types with appropriate validation.
        """
        # Check if email already exists
        if request.email.lower() in self._users_db:
            return AuthResponse(
                success=False,
                message="Email already registered"
            )

        # Validate password
        is_valid, error_msg = self._validate_password(request.password)
        if not is_valid:
            return AuthResponse(
                success=False,
                message=error_msg
            )

        # Validate user type specific requirements
        if request.user_type == UserType.CPA_TEAM:
            if not request.firm_id:
                return AuthResponse(
                    success=False,
                    message="Firm ID required for CPA team members"
                )

        if request.user_type == UserType.CPA_CLIENT:
            if not request.assigned_cpa_id:
                return AuthResponse(
                    success=False,
                    message="Assigned CPA required for CPA clients"
                )

        # Create user
        user = UnifiedUser(
            id=str(uuid4()),
            email=request.email.lower(),
            user_type=request.user_type,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            password_hash=self._hash_password(request.password),
            firm_id=request.firm_id,
            cpa_role=request.cpa_role,
            assigned_cpa_id=request.assigned_cpa_id,
            is_self_service=request.user_type == UserType.CONSUMER
        )

        # Save user
        self._users_db[user.id] = user
        self._users_db[user.email] = user

        # Generate tokens
        access_token = self._generate_access_token(user)

        logger.info(f"User registered: {user.email} ({user.user_type})")

        return AuthResponse(
            success=True,
            message="Registration successful",
            access_token=access_token,
            expires_in=self.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type.value if isinstance(user.user_type, UserType) else user.user_type
            }
        )

    async def logout(self, refresh_token: Optional[str] = None) -> AuthResponse:
        """Logout user and invalidate refresh token."""
        if refresh_token:
            await self._delete_refresh_token_redis(refresh_token)

        return AuthResponse(
            success=True,
            message="Logged out successfully"
        )

    # =========================================================================
    # USER RETRIEVAL
    # =========================================================================

    def get_user_by_id(self, user_id: str) -> Optional[UnifiedUser]:
        """Get user by ID."""
        if self._use_database:
            # Database mode - would need async context
            # For sync calls, fall back to cache
            return self._users_db.get(user_id)
        return self._users_db.get(user_id)

    def get_user_by_email(self, email: str) -> Optional[UnifiedUser]:
        """Get user by email."""
        if self._use_database:
            # Database mode - would need async context
            # For sync calls, fall back to cache
            return self._users_db.get(email.lower())
        return self._users_db.get(email.lower())

    async def get_user_by_id_async(self, user_id: str, session=None) -> Optional[UnifiedUser]:
        """
        Get user by ID (async with database support).

        Args:
            user_id: User identifier.
            session: Optional database session for database mode.

        Returns:
            UnifiedUser or None.
        """
        if self._use_database and session:
            from database.repositories.user_auth_repository import UserAuthRepository
            repo = UserAuthRepository(session)
            user_data = await repo.get_user_by_id(user_id)
            if user_data:
                return self._dict_to_unified_user(user_data)
            return None

        return self._users_db.get(user_id)

    async def get_user_by_email_async(self, email: str, session=None) -> Optional[UnifiedUser]:
        """
        Get user by email (async with database support).

        Args:
            email: User email address.
            session: Optional database session for database mode.

        Returns:
            UnifiedUser or None.
        """
        if self._use_database and session:
            from database.repositories.user_auth_repository import UserAuthRepository
            repo = UserAuthRepository(session)
            user_data = await repo.get_user_by_email(email)
            if user_data:
                # Cache the user for sync lookups
                user = self._dict_to_unified_user(user_data)
                self._users_db[user.id] = user
                self._users_db[user.email] = user
                return user
            return None

        return self._users_db.get(email.lower())

    def _dict_to_unified_user(self, data: Dict[str, Any]) -> UnifiedUser:
        """
        Convert a user data dict to UnifiedUser.

        Args:
            data: User data dictionary from repository.

        Returns:
            UnifiedUser instance.
        """
        # Map user_type string to enum
        user_type_map = {
            "platform_admin": UserType.PLATFORM_ADMIN,
            "firm_admin": UserType.CPA_TEAM,
            "firm_owner": UserType.CPA_TEAM,
            "cpa_team": UserType.CPA_TEAM,
            "cpa_client": UserType.CPA_CLIENT,
            "consumer": UserType.CONSUMER,
        }
        user_type = user_type_map.get(data.get("user_type", "consumer"), UserType.CONSUMER)

        # Map role to CPARole if applicable
        cpa_role = None
        if user_type == UserType.CPA_TEAM:
            role_map = {
                "owner": CPARole.FIRM_ADMIN,
                "firm_admin": CPARole.FIRM_ADMIN,
                "manager": CPARole.MANAGER,
                "senior_preparer": CPARole.SENIOR_PREPARER,
                "preparer": CPARole.PREPARER,
                "reviewer": CPARole.REVIEWER,
            }
            cpa_role = role_map.get(data.get("role"))

        return UnifiedUser(
            id=data.get("id"),
            email=data.get("email", ""),
            user_type=user_type,
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            phone=data.get("phone"),
            password_hash=data.get("password_hash"),
            email_verified=True,  # If in DB, assume verified
            is_active=data.get("is_active", True),
            firm_id=data.get("firm_id"),
            firm_name=data.get("firm_name"),
            cpa_role=cpa_role,
            credentials=", ".join(data.get("credentials", [])) if data.get("credentials") else None,
            permissions=data.get("permissions", []),
            mfa_enabled=data.get("mfa_enabled", False),
            last_login_at=data.get("last_login_at"),
            assigned_cpa_id=data.get("assigned_cpa_id"),
        )


# =============================================================================
# SERVICE SINGLETON
# =============================================================================

_auth_service: Optional[CoreAuthService] = None


def get_auth_service() -> CoreAuthService:
    """Get the singleton auth service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = CoreAuthService()
    return _auth_service
