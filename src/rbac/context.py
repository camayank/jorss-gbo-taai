"""
CA4CPA GLOBAL LLC - Authentication Context

AuthContext is the primary object passed through routes containing
all information about the authenticated user.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Set
from uuid import UUID
from datetime import datetime

from .roles import Role, Level, ROLES, get_role_info
from .permissions import Permission, ROLE_PERMISSIONS


class UserType(str, Enum):
    """
    Types of users in the system.

    Used to determine which table/model the user comes from.
    """
    PLATFORM_ADMIN = "platform_admin"  # CA4CPA internal (platform_admins table)
    FIRM_USER = "firm_user"            # CPA firm employee (users table)
    CLIENT = "client"                  # End user/taxpayer (clients table)


@dataclass
class AuthContext:
    """
    Authentication context for the current request.

    This is the single source of truth for who is making the request
    and what they can do.

    Usage:
        @router.get("/data")
        async def get_data(ctx: AuthContext = Depends(require_auth)):
            if ctx.has_permission(Permission.CLIENT_VIEW_ALL):
                return get_all_clients(ctx.firm_id)
            else:
                return get_assigned_clients(ctx.user_id)
    """

    # =========================================================================
    # Identity
    # =========================================================================

    user_id: UUID
    """Unique identifier for the user."""

    email: str
    """User's email address."""

    name: str
    """User's display name."""

    user_type: UserType
    """Type of user (platform_admin, firm_user, client)."""

    role: Role
    """User's role (one of the 8 roles)."""

    # =========================================================================
    # Context (depends on user_type)
    # =========================================================================

    firm_id: Optional[UUID] = None
    """
    For firm_user: The CPA firm they belong to.
    For client: The CPA firm serving them (or None for direct_client).
    For platform_admin: None.
    """

    firm_name: Optional[str] = None
    """Name of the firm (for display purposes)."""

    # =========================================================================
    # Computed Properties (set during context creation)
    # =========================================================================

    permissions: Set[Permission] = field(default_factory=set)
    """All permissions this user has (based on role)."""

    level: Level = Level.CLIENT
    """Hierarchy level of the user."""

    is_authenticated: bool = False
    """Whether the user is authenticated."""

    # =========================================================================
    # Session Info
    # =========================================================================

    token_id: Optional[str] = None
    """JWT token ID (jti) for session tracking."""

    token_exp: Optional[datetime] = None
    """Token expiration time."""

    # =========================================================================
    # Impersonation
    # =========================================================================

    impersonating: bool = False
    """Whether this is an impersonation session."""

    impersonator_id: Optional[UUID] = None
    """Original user ID if impersonating."""

    impersonator_role: Optional[Role] = None
    """Original user role if impersonating."""

    def __post_init__(self):
        """Populate computed fields after initialization."""
        if self.role:
            role_info = get_role_info(self.role)
            self.level = role_info.level
            self.permissions = set(ROLE_PERMISSIONS.get(self.role, frozenset()))
            self.is_authenticated = True

    # =========================================================================
    # Permission Checks
    # =========================================================================

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def has_any_permission(self, permissions: Set[Permission]) -> bool:
        """Check if user has any of the specified permissions."""
        return bool(self.permissions & permissions)

    def has_all_permissions(self, permissions: Set[Permission]) -> bool:
        """Check if user has all of the specified permissions."""
        return permissions <= self.permissions

    # =========================================================================
    # Role Checks
    # =========================================================================

    def has_role(self, role: Role) -> bool:
        """Check if user has a specific role."""
        return self.role == role

    def has_any_role(self, roles: Set[Role]) -> bool:
        """Check if user has any of the specified roles."""
        return self.role in roles

    # =========================================================================
    # Level Checks
    # =========================================================================

    @property
    def is_platform(self) -> bool:
        """Is this a CA4CPA platform admin?"""
        return self.level == Level.PLATFORM

    @property
    def is_firm(self) -> bool:
        """Is this a CPA firm user?"""
        return self.user_type == UserType.FIRM_USER

    @property
    def is_client(self) -> bool:
        """Is this an end-user/client?"""
        return self.user_type == UserType.CLIENT

    @property
    def is_super_admin(self) -> bool:
        """Is this a super admin?"""
        return self.role == Role.SUPER_ADMIN

    @property
    def is_partner(self) -> bool:
        """Is this a CPA firm partner/owner?"""
        return self.role == Role.PARTNER

    @property
    def is_staff(self) -> bool:
        """Is this a CPA firm staff member?"""
        return self.role == Role.STAFF

    # =========================================================================
    # Access Checks
    # =========================================================================

    def can_access_firm(self, firm_id: UUID) -> bool:
        """
        Check if user can access data for a specific firm.

        Platform admins can access any firm.
        Firm users can only access their own firm.
        """
        if self.is_platform:
            return True
        return self.firm_id == firm_id

    def can_impersonate(self) -> bool:
        """Check if user can impersonate others."""
        return self.has_permission(Permission.PLATFORM_IMPERSONATE)

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def anonymous(cls) -> "AuthContext":
        """Create an anonymous (unauthenticated) context."""
        return cls(
            user_id=UUID("00000000-0000-0000-0000-000000000000"),
            email="",
            name="Anonymous",
            user_type=UserType.CLIENT,
            role=Role.FIRM_CLIENT,
            is_authenticated=False,
            permissions=set(),
        )

    @classmethod
    def for_platform_admin(
        cls,
        user_id: UUID,
        email: str,
        name: str,
        role: Role,
        token_id: Optional[str] = None,
        token_exp: Optional[datetime] = None,
    ) -> "AuthContext":
        """Create context for a platform admin."""
        return cls(
            user_id=user_id,
            email=email,
            name=name,
            user_type=UserType.PLATFORM_ADMIN,
            role=role,
            firm_id=None,
            firm_name=None,
            token_id=token_id,
            token_exp=token_exp,
        )

    @classmethod
    def for_firm_user(
        cls,
        user_id: UUID,
        email: str,
        name: str,
        role: Role,
        firm_id: UUID,
        firm_name: str,
        token_id: Optional[str] = None,
        token_exp: Optional[datetime] = None,
    ) -> "AuthContext":
        """Create context for a CPA firm user (partner or staff)."""
        return cls(
            user_id=user_id,
            email=email,
            name=name,
            user_type=UserType.FIRM_USER,
            role=role,
            firm_id=firm_id,
            firm_name=firm_name,
            token_id=token_id,
            token_exp=token_exp,
        )

    @classmethod
    def for_client(
        cls,
        user_id: UUID,
        email: str,
        name: str,
        is_direct: bool,
        firm_id: Optional[UUID] = None,
        firm_name: Optional[str] = None,
        token_id: Optional[str] = None,
        token_exp: Optional[datetime] = None,
    ) -> "AuthContext":
        """Create context for a client (direct or firm client)."""
        role = Role.DIRECT_CLIENT if is_direct else Role.FIRM_CLIENT
        return cls(
            user_id=user_id,
            email=email,
            name=name,
            user_type=UserType.CLIENT,
            role=role,
            firm_id=firm_id,
            firm_name=firm_name,
            token_id=token_id,
            token_exp=token_exp,
        )

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "user_id": str(self.user_id),
            "email": self.email,
            "name": self.name,
            "user_type": self.user_type.value,
            "role": self.role.value,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "firm_name": self.firm_name,
            "level": self.level.value,
            "is_authenticated": self.is_authenticated,
            "impersonating": self.impersonating,
        }
