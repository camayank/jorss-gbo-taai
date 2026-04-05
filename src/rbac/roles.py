"""
CA4CPA GLOBAL LLC - Role Definitions

8 roles organized in a clear hierarchy:

    PLATFORM (Level 0) - CA4CPA Internal Team
    ├── super_admin     - Full platform access
    ├── platform_admin  - Platform operations
    ├── support         - Customer support
    └── billing         - Finance operations

    CPA FIRM (Level 1A) - B2B Customers
    ├── partner         - CPA firm owner
    └── staff           - CPA firm employee

    DIRECT CLIENT (Level 1B) - B2C Customers
    └── direct_client   - Self-service taxpayer

    FIRM CLIENT (Level 2) - B2B2C End Users
    └── firm_client     - CPA's taxpayer client
"""

from enum import Enum
from dataclasses import dataclass
from typing import Set, Optional


class Role(str, Enum):
    """
    All 8 roles in the system.

    Naming convention: UPPER_SNAKE_CASE for enum, lower_snake_case for value.
    """

    # =========================================================================
    # LEVEL 0: PLATFORM (CA4CPA Internal)
    # =========================================================================

    SUPER_ADMIN = "super_admin"
    """
    Full platform access. Can do anything.
    Who: Founders, CTO, Principal Engineers
    """

    PLATFORM_ADMIN = "platform_admin"
    """
    Platform operations. Manage firms, users, features.
    Who: Operations Manager, Senior Staff
    """

    SUPPORT = "support"
    """
    Customer support. View data, impersonate for troubleshooting.
    Who: Support Team, Help Desk
    """

    BILLING = "billing"
    """
    Finance operations. Manage subscriptions, invoices, refunds.
    Who: Finance Team, Billing Support
    """

    # =========================================================================
    # LEVEL 1A: CPA FIRM (B2B Customers)
    # =========================================================================

    PARTNER = "partner"
    """
    CPA firm owner/admin. Full access to their firm.
    Who: CPA Firm Owner, Managing Partner
    """

    STAFF = "staff"
    """
    CPA firm employee. Prepare returns, manage assigned clients.
    Who: CPAs, Tax Preparers, Associates
    """

    # =========================================================================
    # LEVEL 2: CLIENT (B2B2C - All clients are CPA's clients)
    # =========================================================================

    FIRM_CLIENT = "firm_client"
    """
    Taxpayer who is a client of a CPA firm.

    NOTE: This platform is B2B only. All clients belong to CPA firms.
    There is no direct B2C channel - all clients access through their CPA's
    white-labeled portal.

    Who: Clients of CPA practices
    """

    # DEPRECATED: Use FIRM_CLIENT instead
    # Kept for backward compatibility only - treated identically to FIRM_CLIENT
    DIRECT_CLIENT = "direct_client"
    """
    DEPRECATED: Legacy role - use FIRM_CLIENT instead.

    All clients are now treated the same regardless of how they access
    the platform. This role exists only for backward compatibility.
    """


class Level(int, Enum):
    """
    Hierarchy levels for access control.

    Lower number = higher privilege (can access data at lower levels).
    """
    PLATFORM = 0   # CA4CPA internal (super_admin, platform_admin, support, billing)
    FIRM = 1       # CPA firm level (partner, staff) and direct_client
    CLIENT = 2     # End user level (firm_client)


@dataclass(frozen=True)
class RoleInfo:
    """Complete information about a role."""
    role: Role
    name: str
    description: str
    level: Level
    is_platform: bool      # Is this a CA4CPA internal role?
    is_firm: bool          # Is this a CPA firm role?
    is_client: bool        # Is this an end-user/client role?
    can_impersonate: bool  # Can impersonate lower-level users?


# =============================================================================
# ROLE REGISTRY
# =============================================================================

ROLES: dict[Role, RoleInfo] = {
    # -------------------------------------------------------------------------
    # Platform Roles (Level 0)
    # -------------------------------------------------------------------------
    Role.SUPER_ADMIN: RoleInfo(
        role=Role.SUPER_ADMIN,
        name="Super Admin",
        description="Full platform access - Founders, CTO",
        level=Level.PLATFORM,
        is_platform=True,
        is_firm=False,
        is_client=False,
        can_impersonate=True,
    ),
    Role.PLATFORM_ADMIN: RoleInfo(
        role=Role.PLATFORM_ADMIN,
        name="Platform Admin",
        description="Platform operations - Operations Manager",
        level=Level.PLATFORM,
        is_platform=True,
        is_firm=False,
        is_client=False,
        can_impersonate=True,
    ),
    Role.SUPPORT: RoleInfo(
        role=Role.SUPPORT,
        name="Support",
        description="Customer support - Help Desk",
        level=Level.PLATFORM,
        is_platform=True,
        is_firm=False,
        is_client=False,
        can_impersonate=True,
    ),
    Role.BILLING: RoleInfo(
        role=Role.BILLING,
        name="Billing",
        description="Finance operations - Finance Team",
        level=Level.PLATFORM,
        is_platform=True,
        is_firm=False,
        is_client=False,
        can_impersonate=False,
    ),

    # -------------------------------------------------------------------------
    # CPA Firm Roles (Level 1A)
    # -------------------------------------------------------------------------
    Role.PARTNER: RoleInfo(
        role=Role.PARTNER,
        name="Partner",
        description="CPA firm owner - Managing Partner",
        level=Level.FIRM,
        is_platform=False,
        is_firm=True,
        is_client=False,
        can_impersonate=False,
    ),
    Role.STAFF: RoleInfo(
        role=Role.STAFF,
        name="Staff",
        description="CPA firm employee - Tax Preparers",
        level=Level.FIRM,
        is_platform=False,
        is_firm=True,
        is_client=False,
        can_impersonate=False,
    ),

    # -------------------------------------------------------------------------
    # Client Role (Level 2) - All clients are CPA's clients
    # -------------------------------------------------------------------------
    Role.FIRM_CLIENT: RoleInfo(
        role=Role.FIRM_CLIENT,
        name="Client",
        description="CPA's taxpayer client - All clients access via CPA's portal",
        level=Level.CLIENT,
        is_platform=False,
        is_firm=False,
        is_client=True,
        can_impersonate=False,
    ),

    # -------------------------------------------------------------------------
    # DEPRECATED: Direct Client (kept for backward compatibility)
    # Treated identically to FIRM_CLIENT
    # -------------------------------------------------------------------------
    Role.DIRECT_CLIENT: RoleInfo(
        role=Role.DIRECT_CLIENT,
        name="Client (Legacy)",
        description="DEPRECATED: Use FIRM_CLIENT - All clients treated the same",
        level=Level.CLIENT,  # Same as FIRM_CLIENT
        is_platform=False,
        is_firm=False,
        is_client=True,
        can_impersonate=False,
    ),
}


def get_role_info(role: Role) -> RoleInfo:
    """Get information about a role."""
    return ROLES[role]


def get_platform_roles() -> Set[Role]:
    """Get all platform-level roles (CA4CPA internal)."""
    return {role for role, info in ROLES.items() if info.is_platform}


def get_firm_roles() -> Set[Role]:
    """Get all firm-level roles (CPA firm employees)."""
    return {role for role, info in ROLES.items() if info.is_firm}


def get_client_roles() -> Set[Role]:
    """Get all client-level roles (end users)."""
    return {role for role, info in ROLES.items() if info.is_client}


def can_access_level(actor_role: Role, target_level: Level) -> bool:
    """
    Check if actor can access data at target level.

    Platform roles can access all levels.
    Firm roles can access firm and client levels.
    Client roles can only access their own level.
    """
    actor_level = ROLES[actor_role].level
    return actor_level.value <= target_level.value


# =============================================================================
# ROLE SETS (for quick checks)
# =============================================================================

PLATFORM_ROLES = frozenset({
    Role.SUPER_ADMIN,
    Role.PLATFORM_ADMIN,
    Role.SUPPORT,
    Role.BILLING,
})

FIRM_ROLES = frozenset({
    Role.PARTNER,
    Role.STAFF,
})

CLIENT_ROLES = frozenset({
    Role.DIRECT_CLIENT,
    Role.FIRM_CLIENT,
})

# Roles that can manage other users
ADMIN_ROLES = frozenset({
    Role.SUPER_ADMIN,
    Role.PLATFORM_ADMIN,
    Role.PARTNER,
})

# Roles that can impersonate
IMPERSONATE_ROLES = frozenset({
    Role.SUPER_ADMIN,
    Role.PLATFORM_ADMIN,
    Role.SUPPORT,
})
