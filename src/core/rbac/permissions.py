"""
Permission Service - Permission catalog and resolution.

Provides:
- System permission definitions (seeded from code)
- Permission resolution algorithm
- Tier-based filtering
- User override processing
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Set, Dict, Any, Union
from uuid import UUID
import logging

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session, selectinload

from .models import (
    Permission,
    RoleTemplate,
    RolePermission,
    UserRoleAssignment,
    UserPermissionOverride,
    PermissionCategory,
    HierarchyLevel,
    OverrideAction,
)

logger = logging.getLogger(__name__)


# =============================================================================
# SYSTEM PERMISSION CATALOG
# =============================================================================

@dataclass
class PermissionDefinition:
    """Definition of a system permission."""
    code: str
    name: str
    description: str
    category: PermissionCategory
    min_hierarchy_level: HierarchyLevel = HierarchyLevel.FIRM
    tier_restriction: List[str] = field(default_factory=lambda: ["starter", "professional", "enterprise"])


# System permissions - matches existing UserPermission enum + new ones
SYSTEM_PERMISSIONS: List[PermissionDefinition] = [
    # Team Management
    PermissionDefinition(
        code="manage_team",
        name="Manage Team",
        description="Create, edit, and deactivate team members",
        category=PermissionCategory.TEAM,
    ),
    PermissionDefinition(
        code="invite_users",
        name="Invite Users",
        description="Send invitations to new team members",
        category=PermissionCategory.TEAM,
    ),
    PermissionDefinition(
        code="view_team_performance",
        name="View Team Performance",
        description="View team member activity and performance metrics",
        category=PermissionCategory.TEAM,
    ),
    PermissionDefinition(
        code="assign_roles",
        name="Assign Roles",
        description="Assign roles to team members",
        category=PermissionCategory.TEAM,
    ),
    PermissionDefinition(
        code="manage_custom_roles",
        name="Manage Custom Roles",
        description="Create and modify custom roles",
        category=PermissionCategory.TEAM,
        tier_restriction=["professional", "enterprise"],
    ),

    # Client Management
    PermissionDefinition(
        code="view_client",
        name="View Client",
        description="View assigned client information",
        category=PermissionCategory.CLIENT,
    ),
    PermissionDefinition(
        code="view_all_clients",
        name="View All Clients",
        description="View all clients in the firm",
        category=PermissionCategory.CLIENT,
    ),
    PermissionDefinition(
        code="create_client",
        name="Create Client",
        description="Add new clients to the firm",
        category=PermissionCategory.CLIENT,
    ),
    PermissionDefinition(
        code="edit_client",
        name="Edit Client",
        description="Update client information",
        category=PermissionCategory.CLIENT,
    ),
    PermissionDefinition(
        code="manage_client",
        name="Manage Client",
        description="Full client management including status changes",
        category=PermissionCategory.CLIENT,
    ),
    PermissionDefinition(
        code="archive_client",
        name="Archive Client",
        description="Archive or unarchive clients",
        category=PermissionCategory.CLIENT,
    ),
    PermissionDefinition(
        code="assign_clients",
        name="Assign Clients",
        description="Assign clients to team members",
        category=PermissionCategory.CLIENT,
    ),

    # Return Operations
    PermissionDefinition(
        code="view_returns",
        name="View Returns",
        description="View tax returns",
        category=PermissionCategory.RETURN,
    ),
    PermissionDefinition(
        code="create_return",
        name="Create Return",
        description="Create new tax returns",
        category=PermissionCategory.RETURN,
    ),
    PermissionDefinition(
        code="edit_returns",
        name="Edit Returns",
        description="Edit tax return data",
        category=PermissionCategory.RETURN,
    ),
    PermissionDefinition(
        code="edit_return",
        name="Edit Return",
        description="Edit individual tax return",
        category=PermissionCategory.RETURN,
    ),
    PermissionDefinition(
        code="manage_returns",
        name="Manage Returns",
        description="Full return management including deletion",
        category=PermissionCategory.RETURN,
    ),
    PermissionDefinition(
        code="submit_for_review",
        name="Submit for Review",
        description="Submit returns for review",
        category=PermissionCategory.RETURN,
    ),
    PermissionDefinition(
        code="review_returns",
        name="Review Returns",
        description="Review submitted returns",
        category=PermissionCategory.RETURN,
    ),
    PermissionDefinition(
        code="approve_return",
        name="Approve Return",
        description="Approve returns for filing",
        category=PermissionCategory.RETURN,
    ),
    PermissionDefinition(
        code="reject_return",
        name="Reject Return",
        description="Reject returns with feedback",
        category=PermissionCategory.RETURN,
    ),

    # Scenarios & Analysis
    PermissionDefinition(
        code="run_scenarios",
        name="Run Scenarios",
        description="Run tax scenario analysis",
        category=PermissionCategory.SCENARIO,
    ),
    PermissionDefinition(
        code="view_optimization",
        name="View Optimization",
        description="View tax optimization recommendations",
        category=PermissionCategory.SCENARIO,
    ),
    PermissionDefinition(
        code="generate_reports",
        name="Generate Reports",
        description="Generate tax reports and summaries",
        category=PermissionCategory.REPORT,
    ),

    # Compliance & Audit
    PermissionDefinition(
        code="view_compliance",
        name="View Compliance",
        description="View compliance status and reports",
        category=PermissionCategory.COMPLIANCE,
    ),
    PermissionDefinition(
        code="view_audit_logs",
        name="View Audit Logs",
        description="View audit trail and activity logs",
        category=PermissionCategory.COMPLIANCE,
    ),
    PermissionDefinition(
        code="export_audit_trail",
        name="Export Audit Trail",
        description="Export audit logs for external review",
        category=PermissionCategory.COMPLIANCE,
    ),
    PermissionDefinition(
        code="gdpr_requests",
        name="GDPR Requests",
        description="Process GDPR data requests",
        category=PermissionCategory.COMPLIANCE,
    ),

    # Billing & Admin
    PermissionDefinition(
        code="view_billing",
        name="View Billing",
        description="View subscription and billing information",
        category=PermissionCategory.BILLING,
    ),
    PermissionDefinition(
        code="update_payment",
        name="Update Payment",
        description="Update payment methods",
        category=PermissionCategory.BILLING,
    ),
    PermissionDefinition(
        code="change_plan",
        name="Change Plan",
        description="Upgrade or downgrade subscription plan",
        category=PermissionCategory.BILLING,
    ),
    PermissionDefinition(
        code="update_branding",
        name="Update Branding",
        description="Update firm branding settings",
        category=PermissionCategory.SETTINGS,
    ),
    PermissionDefinition(
        code="manage_api_keys",
        name="Manage API Keys",
        description="Create and manage API keys",
        category=PermissionCategory.SETTINGS,
        tier_restriction=["enterprise"],
    ),
    PermissionDefinition(
        code="configure_integrations",
        name="Configure Integrations",
        description="Configure third-party integrations",
        category=PermissionCategory.SETTINGS,
        tier_restriction=["professional", "enterprise"],
    ),

    # Workflow Operations
    PermissionDefinition(
        code="manage_workflow",
        name="Manage Workflow",
        description="Configure workflow settings and queues",
        category=PermissionCategory.WORKFLOW,
    ),
    PermissionDefinition(
        code="reassign_work",
        name="Reassign Work",
        description="Reassign work items to other team members",
        category=PermissionCategory.WORKFLOW,
    ),

    # Document Management
    PermissionDefinition(
        code="upload_documents",
        name="Upload Documents",
        description="Upload client documents",
        category=PermissionCategory.DOCUMENT,
    ),
    PermissionDefinition(
        code="view_documents",
        name="View Documents",
        description="View uploaded documents",
        category=PermissionCategory.DOCUMENT,
    ),
    PermissionDefinition(
        code="delete_documents",
        name="Delete Documents",
        description="Delete uploaded documents",
        category=PermissionCategory.DOCUMENT,
    ),

    # Platform Administration (Level 0 only)
    PermissionDefinition(
        code="manage_firms",
        name="Manage Firms",
        description="Create and manage firm accounts",
        category=PermissionCategory.PLATFORM,
        min_hierarchy_level=HierarchyLevel.PLATFORM,
    ),
    PermissionDefinition(
        code="manage_partners",
        name="Manage Partners",
        description="Create and manage partner organizations",
        category=PermissionCategory.PLATFORM,
        min_hierarchy_level=HierarchyLevel.PLATFORM,
    ),
    PermissionDefinition(
        code="view_platform_metrics",
        name="View Platform Metrics",
        description="View platform-wide analytics and metrics",
        category=PermissionCategory.PLATFORM,
        min_hierarchy_level=HierarchyLevel.PLATFORM,
    ),
    PermissionDefinition(
        code="manage_subscriptions",
        name="Manage Subscriptions",
        description="Manage firm subscriptions and billing",
        category=PermissionCategory.PLATFORM,
        min_hierarchy_level=HierarchyLevel.PLATFORM,
    ),
    PermissionDefinition(
        code="impersonate_user",
        name="Impersonate User",
        description="Login as another user for support",
        category=PermissionCategory.PLATFORM,
        min_hierarchy_level=HierarchyLevel.PLATFORM,
    ),
    PermissionDefinition(
        code="manage_feature_flags",
        name="Manage Feature Flags",
        description="Toggle platform feature flags",
        category=PermissionCategory.PLATFORM,
        min_hierarchy_level=HierarchyLevel.PLATFORM,
    ),

    # Partner Administration (Level 1)
    PermissionDefinition(
        code="manage_partner_firms",
        name="Manage Partner Firms",
        description="Manage firms under partner organization",
        category=PermissionCategory.PARTNER,
        min_hierarchy_level=HierarchyLevel.PARTNER,
    ),
    PermissionDefinition(
        code="view_partner_reports",
        name="View Partner Reports",
        description="View cross-firm reports for partner",
        category=PermissionCategory.PARTNER,
        min_hierarchy_level=HierarchyLevel.PARTNER,
    ),
    PermissionDefinition(
        code="manage_partner_branding",
        name="Manage Partner Branding",
        description="Update partner white-label branding",
        category=PermissionCategory.PARTNER,
        min_hierarchy_level=HierarchyLevel.PARTNER,
    ),
]


class PermissionCatalog:
    """
    In-memory catalog of permission definitions.

    Used for quick lookups without database queries.
    """

    def __init__(self):
        self._permissions: Dict[str, PermissionDefinition] = {
            p.code: p for p in SYSTEM_PERMISSIONS
        }
        self._by_category: Dict[PermissionCategory, List[PermissionDefinition]] = {}
        for p in SYSTEM_PERMISSIONS:
            if p.category not in self._by_category:
                self._by_category[p.category] = []
            self._by_category[p.category].append(p)

    def get(self, code: str) -> Optional[PermissionDefinition]:
        """Get permission definition by code."""
        return self._permissions.get(code)

    def get_by_category(self, category: PermissionCategory) -> List[PermissionDefinition]:
        """Get all permissions in a category."""
        return self._by_category.get(category, [])

    def get_all(self) -> List[PermissionDefinition]:
        """Get all permission definitions."""
        return list(self._permissions.values())

    def get_for_tier(self, tier: str) -> List[PermissionDefinition]:
        """Get permissions available for a subscription tier."""
        return [
            p for p in self._permissions.values()
            if tier in p.tier_restriction
        ]

    def exists(self, code: str) -> bool:
        """Check if permission code exists."""
        return code in self._permissions


# Singleton instance
_permission_catalog: Optional[PermissionCatalog] = None


def get_permission_catalog() -> PermissionCatalog:
    """Get singleton permission catalog."""
    global _permission_catalog
    if _permission_catalog is None:
        _permission_catalog = PermissionCatalog()
    return _permission_catalog


# =============================================================================
# PERMISSION RESOLUTION SERVICE
# =============================================================================

@dataclass
class ResolvedPermissions:
    """Result of permission resolution."""
    permissions: Set[str]
    roles: List[str]
    primary_role: Optional[str]
    hierarchy_level: int
    grants: Set[str]  # Permissions added via overrides
    revokes: Set[str]  # Permissions removed via overrides
    tier_filtered: Set[str]  # Permissions removed due to tier
    cache_key: str
    resolved_at: datetime


class PermissionService:
    """
    Permission resolution and management service.

    Resolution Algorithm:
    1. Collect permissions from all assigned roles (with inheritance)
    2. Apply firm-level defaults
    3. Apply user-level overrides (grants add, revokes remove)
    4. Filter by subscription tier limits
    5. Check resource-level grants for specific resources
    """

    def __init__(self, db: Session):
        self.db = db
        self.catalog = get_permission_catalog()

    async def resolve_user_permissions(
        self,
        user_id: UUID,
        firm_id: Optional[UUID] = None,
        subscription_tier: str = "starter",
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
    ) -> ResolvedPermissions:
        """
        Resolve effective permissions for a user.

        Args:
            user_id: User ID
            firm_id: Firm ID for context
            subscription_tier: Firm's subscription tier
            resource_type: Optional resource type for resource-level checks
            resource_id: Optional resource ID for resource-level checks

        Returns:
            ResolvedPermissions with all effective permissions
        """
        now = datetime.utcnow()

        # Step 1: Get user's role assignments
        role_assignments = await self._get_user_roles(user_id)

        if not role_assignments:
            # No roles - return empty permissions
            return ResolvedPermissions(
                permissions=set(),
                roles=[],
                primary_role=None,
                hierarchy_level=HierarchyLevel.USER.value,
                grants=set(),
                revokes=set(),
                tier_filtered=set(),
                cache_key=f"user:{user_id}:v0",
                resolved_at=now,
            )

        # Step 2: Collect permissions from roles (with inheritance)
        base_permissions: Set[str] = set()
        role_codes: List[str] = []
        primary_role: Optional[str] = None
        min_hierarchy = HierarchyLevel.USER.value

        for assignment in role_assignments:
            role = assignment.role
            role_codes.append(role.code)

            if assignment.is_primary:
                primary_role = role.code

            # Track minimum hierarchy level
            if role.hierarchy_level < min_hierarchy:
                min_hierarchy = role.hierarchy_level

            # Get role permissions (with inheritance)
            role_perms = await self._get_role_permissions_with_inheritance(role.role_id)
            base_permissions.update(role_perms)

        # Step 3: Get user permission overrides
        overrides = await self._get_user_overrides(user_id, resource_type, resource_id)

        grants: Set[str] = set()
        revokes: Set[str] = set()

        for override in overrides:
            perm_code = await self._get_permission_code(override.permission_id)
            if perm_code:
                if override.action == OverrideAction.GRANT:
                    grants.add(perm_code)
                else:
                    revokes.add(perm_code)

        # Apply overrides
        effective_permissions = (base_permissions | grants) - revokes

        # Step 4: Filter by subscription tier
        tier_filtered: Set[str] = set()
        final_permissions: Set[str] = set()

        for perm_code in effective_permissions:
            perm_def = self.catalog.get(perm_code)
            if perm_def and subscription_tier in perm_def.tier_restriction:
                final_permissions.add(perm_code)
            else:
                tier_filtered.add(perm_code)

        # Generate cache key
        cache_key = f"user:{user_id}:firm:{firm_id}:tier:{subscription_tier}"

        return ResolvedPermissions(
            permissions=final_permissions,
            roles=role_codes,
            primary_role=primary_role,
            hierarchy_level=min_hierarchy,
            grants=grants,
            revokes=revokes,
            tier_filtered=tier_filtered,
            cache_key=cache_key,
            resolved_at=now,
        )

    async def _get_user_roles(self, user_id: UUID) -> List[UserRoleAssignment]:
        """Get active role assignments for a user."""
        stmt = (
            select(UserRoleAssignment)
            .options(selectinload(UserRoleAssignment.role))
            .where(
                and_(
                    UserRoleAssignment.user_id == user_id,
                    or_(
                        UserRoleAssignment.expires_at.is_(None),
                        UserRoleAssignment.expires_at > datetime.utcnow()
                    )
                )
            )
        )
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_role_permissions_with_inheritance(
        self,
        role_id: UUID,
        visited: Optional[Set[UUID]] = None
    ) -> Set[str]:
        """
        Get all permissions for a role, including inherited permissions.

        Handles circular inheritance by tracking visited roles.
        """
        if visited is None:
            visited = set()

        if role_id in visited:
            logger.warning(f"Circular role inheritance detected: {role_id}")
            return set()

        visited.add(role_id)

        permissions: Set[str] = set()

        # Get role with permissions
        stmt = (
            select(RoleTemplate)
            .options(
                selectinload(RoleTemplate.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(
                and_(
                    RoleTemplate.role_id == role_id,
                    RoleTemplate.is_active == True
                )
            )
        )
        result = self.db.execute(stmt)
        role = result.scalar_one_or_none()

        if not role:
            return permissions

        # Add direct permissions
        for rp in role.role_permissions:
            if rp.permission and rp.permission.is_enabled:
                permissions.add(rp.permission.code)

        # Add inherited permissions from parent
        if role.parent_role_id:
            parent_perms = await self._get_role_permissions_with_inheritance(
                role.parent_role_id, visited
            )
            permissions.update(parent_perms)

        return permissions

    async def _get_user_overrides(
        self,
        user_id: UUID,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
    ) -> List[UserPermissionOverride]:
        """Get active permission overrides for a user."""
        conditions = [
            UserPermissionOverride.user_id == user_id,
            or_(
                UserPermissionOverride.expires_at.is_(None),
                UserPermissionOverride.expires_at > datetime.utcnow()
            ),
        ]

        # Include global overrides (no resource) and specific resource overrides
        if resource_type and resource_id:
            conditions.append(
                or_(
                    and_(
                        UserPermissionOverride.resource_type.is_(None),
                        UserPermissionOverride.resource_id.is_(None)
                    ),
                    and_(
                        UserPermissionOverride.resource_type == resource_type,
                        UserPermissionOverride.resource_id == resource_id
                    )
                )
            )
        else:
            # Only global overrides
            conditions.append(UserPermissionOverride.resource_type.is_(None))

        stmt = select(UserPermissionOverride).where(and_(*conditions))
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_permission_code(self, permission_id: UUID) -> Optional[str]:
        """Get permission code by ID."""
        stmt = select(Permission.code).where(Permission.permission_id == permission_id)
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    def check_permission(
        self,
        resolved: ResolvedPermissions,
        permission: str,
    ) -> bool:
        """Check if resolved permissions include a specific permission."""
        return permission in resolved.permissions

    def check_any_permission(
        self,
        resolved: ResolvedPermissions,
        permissions: List[str],
    ) -> bool:
        """Check if resolved permissions include any of the specified permissions."""
        return bool(resolved.permissions.intersection(permissions))

    def check_all_permissions(
        self,
        resolved: ResolvedPermissions,
        permissions: List[str],
    ) -> bool:
        """Check if resolved permissions include all specified permissions."""
        return all(p in resolved.permissions for p in permissions)

    async def get_permission_by_code(self, code: str) -> Optional[Permission]:
        """Get permission database record by code."""
        stmt = select(Permission).where(Permission.code == code)
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_permissions(
        self,
        category: Optional[PermissionCategory] = None,
        enabled_only: bool = True,
    ) -> List[Permission]:
        """Get all permissions, optionally filtered by category."""
        conditions = []

        if category:
            conditions.append(Permission.category == category)
        if enabled_only:
            conditions.append(Permission.is_enabled == True)

        stmt = select(Permission)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Permission.category, Permission.code)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    async def seed_system_permissions(self) -> int:
        """
        Seed system permissions from catalog.

        Creates or updates permissions based on SYSTEM_PERMISSIONS.
        Returns count of permissions seeded.
        """
        count = 0

        for perm_def in SYSTEM_PERMISSIONS:
            # Check if exists
            existing = await self.get_permission_by_code(perm_def.code)

            if existing:
                # Update existing
                existing.name = perm_def.name
                existing.description = perm_def.description
                existing.category = perm_def.category
                existing.min_hierarchy_level = perm_def.min_hierarchy_level.value
                existing.tier_restriction = perm_def.tier_restriction
                existing.is_system = True
            else:
                # Create new
                permission = Permission(
                    code=perm_def.code,
                    name=perm_def.name,
                    description=perm_def.description,
                    category=perm_def.category,
                    min_hierarchy_level=perm_def.min_hierarchy_level.value,
                    tier_restriction=perm_def.tier_restriction,
                    is_system=True,
                    is_enabled=True,
                )
                self.db.add(permission)

            count += 1

        self.db.commit()
        logger.info(f"Seeded {count} system permissions")
        return count


# =============================================================================
# SERVICE FACTORY
# =============================================================================

_permission_service: Optional[PermissionService] = None


def get_permission_service(db: Session) -> PermissionService:
    """Get permission service instance."""
    return PermissionService(db)
