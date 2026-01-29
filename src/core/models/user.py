"""
Unified User Model

Single user model that supports all user types in the platform:
- CONSUMER: Direct B2C users using the core platform
- CPA_CLIENT: Clients of CPA firms (B2B2C)
- CPA_TEAM: CPA firm team members (preparers, reviewers, admins)
- PLATFORM_ADMIN: Internal platform administrators

This unified model enables:
1. Single authentication flow
2. Role-based access to shared core APIs
3. Consistent user experience across all portals
4. Proper data isolation via firm_id and user_type
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from uuid import uuid4


class UserType(str, Enum):
    """User type discriminator for the unified user model."""
    CONSUMER = "consumer"           # Direct B2C user
    CPA_CLIENT = "cpa_client"       # Client of a CPA firm
    CPA_TEAM = "cpa_team"           # CPA firm team member
    PLATFORM_ADMIN = "platform_admin"  # Internal admin


class CPARole(str, Enum):
    """Roles for CPA team members within a firm."""
    FIRM_ADMIN = "firm_admin"
    SENIOR_PREPARER = "senior_preparer"
    PREPARER = "preparer"
    REVIEWER = "reviewer"
    SUPPORT = "support"


class UnifiedUser(BaseModel):
    """
    Unified user model for all platform users.

    This is the single source of truth for user identity across:
    - Consumer Portal (B2C)
    - CPA Panel (B2B)
    - Admin Panel (Internal)
    """
    # Core Identity
    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str
    user_type: UserType

    # Profile Information
    first_name: str = ""
    last_name: str = ""
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

    # Multi-tenancy (NULL for consumers & platform admins)
    firm_id: Optional[str] = None
    firm_name: Optional[str] = None

    # CPA Team specific (NULL for others)
    cpa_role: Optional[CPARole] = None
    ptin: Optional[str] = None  # Preparer Tax ID Number
    credentials: Optional[str] = None  # "CPA", "EA", etc.

    # CPA Client specific (NULL for others)
    assigned_cpa_id: Optional[str] = None
    assigned_cpa_name: Optional[str] = None

    # Consumer specific
    is_self_service: bool = True  # True for B2C, False for CPA clients

    # Security
    password_hash: Optional[str] = None
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    email_verified: bool = False

    # OAuth (for social login)
    oauth_provider: Optional[str] = None  # 'google', 'microsoft'
    oauth_provider_id: Optional[str] = None  # Provider's user ID

    # Status
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    # Permissions (computed from role + overrides)
    permissions: List[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def initials(self) -> str:
        """Get user's initials for avatar display."""
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        return self.email[0:2].upper()

    @property
    def is_consumer(self) -> bool:
        """Check if user is a direct B2C consumer."""
        return self.user_type == UserType.CONSUMER

    @property
    def is_cpa_client(self) -> bool:
        """Check if user is a CPA's client."""
        return self.user_type == UserType.CPA_CLIENT

    @property
    def is_cpa_team(self) -> bool:
        """Check if user is a CPA team member."""
        return self.user_type == UserType.CPA_TEAM

    @property
    def is_platform_admin(self) -> bool:
        """Check if user is a platform administrator."""
        return self.user_type == UserType.PLATFORM_ADMIN

    @property
    def can_view_all_firms(self) -> bool:
        """Check if user can access all firms (platform admin only)."""
        return self.user_type == UserType.PLATFORM_ADMIN

    @property
    def can_manage_firm(self) -> bool:
        """Check if user can manage their firm."""
        return (
            self.user_type == UserType.CPA_TEAM and
            self.cpa_role == CPARole.FIRM_ADMIN
        )

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Platform admins have all permissions
        if self.is_platform_admin:
            return True
        return permission in self.permissions


class UserProfile(BaseModel):
    """Public user profile for display purposes."""
    id: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    initials: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    user_type: UserType
    firm_name: Optional[str] = None
    credentials: Optional[str] = None
    is_verified: bool = False

    @classmethod
    def from_user(cls, user: UnifiedUser) -> "UserProfile":
        """Create profile from full user object."""
        return cls(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            initials=user.initials,
            phone=user.phone,
            avatar_url=user.avatar_url,
            user_type=user.user_type,
            firm_name=user.firm_name,
            credentials=user.credentials,
            is_verified=user.email_verified
        )


class UserPreferences(BaseModel):
    """User preferences and settings."""
    user_id: str

    # Notification preferences
    email_notifications: bool = True
    sms_notifications: bool = False
    push_notifications: bool = True

    # Communication preferences
    marketing_emails: bool = False
    product_updates: bool = True

    # Display preferences
    theme: str = "light"  # "light", "dark", "system"
    language: str = "en"
    timezone: str = "America/New_York"
    date_format: str = "MM/DD/YYYY"

    # Privacy preferences
    show_profile_publicly: bool = False
    allow_analytics: bool = True


class UserContext(BaseModel):
    """
    Request context containing authenticated user information.

    This is injected into every authenticated API request and provides:
    - User identity and type
    - Firm context for multi-tenancy
    - Permissions for authorization
    - Request metadata
    """
    # User identity
    user_id: str
    email: str
    user_type: UserType
    full_name: str

    # Multi-tenancy context
    firm_id: Optional[str] = None
    firm_name: Optional[str] = None

    # For CPA clients - their assigned CPA
    assigned_cpa_id: Optional[str] = None

    # For CPA team - their role
    cpa_role: Optional[CPARole] = None

    # Permissions (flat list for fast checking)
    permissions: List[str] = Field(default_factory=list)

    # Request metadata
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Config:
        use_enum_values = True

    @classmethod
    def from_user(cls, user: UnifiedUser, request_id: str = None) -> "UserContext":
        """Create context from user object."""
        return cls(
            user_id=user.id,
            email=user.email,
            user_type=user.user_type,
            full_name=user.full_name,
            firm_id=user.firm_id,
            firm_name=user.firm_name,
            assigned_cpa_id=user.assigned_cpa_id,
            cpa_role=user.cpa_role,
            permissions=user.permissions,
            request_id=request_id
        )

    def has_permission(self, permission: str) -> bool:
        """Check if context has a specific permission."""
        if self.user_type == UserType.PLATFORM_ADMIN:
            return True
        return permission in self.permissions

    def can_access_firm(self, firm_id: str) -> bool:
        """Check if context can access a specific firm."""
        if self.user_type == UserType.PLATFORM_ADMIN:
            return True  # Admins can access all firms
        return self.firm_id == firm_id

    def can_access_user(self, target_user_id: str, target_firm_id: Optional[str]) -> bool:
        """Check if context can access a specific user's data."""
        # Can always access own data
        if self.user_id == target_user_id:
            return True

        # Platform admins can access all
        if self.user_type == UserType.PLATFORM_ADMIN:
            return True

        # CPA team can access users in their firm
        if self.user_type == UserType.CPA_TEAM and target_firm_id:
            return self.firm_id == target_firm_id

        # Consumers can only access own data (already checked above)
        return False


# =============================================================================
# DATABASE TABLE DEFINITION (for SQLAlchemy/reference)
# =============================================================================

"""
SQL Table Definition:

CREATE TABLE unified_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('consumer', 'cpa_client', 'cpa_team', 'platform_admin')),

    -- Profile
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    avatar_url VARCHAR(500),

    -- Multi-tenancy
    firm_id UUID REFERENCES firms(id),

    -- CPA Team specific
    cpa_role VARCHAR(30),
    ptin VARCHAR(20),
    credentials VARCHAR(50),

    -- CPA Client specific
    assigned_cpa_id UUID REFERENCES unified_users(id),

    -- Consumer specific
    is_self_service BOOLEAN DEFAULT TRUE,

    -- Security
    password_hash VARCHAR(255),
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(100),
    email_verified BOOLEAN DEFAULT FALSE,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,

    -- Indexes
    INDEX idx_users_email (email),
    INDEX idx_users_firm_id (firm_id),
    INDEX idx_users_user_type (user_type),
    INDEX idx_users_assigned_cpa (assigned_cpa_id)
);

-- Trigger to update updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON unified_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""
