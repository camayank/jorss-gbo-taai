"""
Role Service - Role management and assignment.

Provides:
- System role definitions (seeded from code)
- Custom role creation (per tier limits)
- Role assignment management
- Privilege escalation prevention
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Set, Dict, Any
from uuid import UUID, uuid4
import logging

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session, selectinload

from .models import (
    RoleTemplate,
    RolePermission,
    UserRoleAssignment,
    Permission,
    HierarchyLevel,
    PermissionCacheVersion,
)
from .permissions import get_permission_catalog, PermissionDefinition

logger = logging.getLogger(__name__)


# =============================================================================
# SYSTEM ROLE CATALOG
# =============================================================================

@dataclass
class RoleDefinition:
    """Definition of a system role."""
    code: str
    name: str
    description: str
    hierarchy_level: HierarchyLevel
    permissions: List[str]  # Permission codes
    parent_role: Optional[str] = None
    display_order: int = 100


# System roles - matches existing UserRole enum + platform/partner roles
SYSTEM_ROLES: List[RoleDefinition] = [
    # Platform Level (0)
    RoleDefinition(
        code="super_admin",
        name="Super Admin",
        description="Full platform access with all administrative capabilities",
        hierarchy_level=HierarchyLevel.PLATFORM,
        permissions=[
            "manage_firms", "manage_partners", "view_platform_metrics",
            "manage_subscriptions", "impersonate_user", "manage_feature_flags",
            # All other permissions inherited
        ],
        display_order=1,
    ),
    RoleDefinition(
        code="support",
        name="Support",
        description="Platform support staff with limited admin access",
        hierarchy_level=HierarchyLevel.PLATFORM,
        permissions=[
            "view_platform_metrics", "view_audit_logs", "view_compliance",
        ],
        display_order=2,
    ),
    RoleDefinition(
        code="billing",
        name="Billing",
        description="Platform billing administration",
        hierarchy_level=HierarchyLevel.PLATFORM,
        permissions=[
            "manage_subscriptions", "view_billing", "view_platform_metrics",
        ],
        display_order=3,
    ),
    RoleDefinition(
        code="compliance",
        name="Compliance",
        description="Platform compliance and audit access",
        hierarchy_level=HierarchyLevel.PLATFORM,
        permissions=[
            "view_compliance", "view_audit_logs", "export_audit_trail",
            "gdpr_requests", "view_platform_metrics",
        ],
        display_order=4,
    ),
    RoleDefinition(
        code="engineering",
        name="Engineering",
        description="Platform engineering access for debugging",
        hierarchy_level=HierarchyLevel.PLATFORM,
        permissions=[
            "view_platform_metrics", "manage_feature_flags", "view_audit_logs",
        ],
        display_order=5,
    ),

    # Partner Level (1)
    RoleDefinition(
        code="partner_admin",
        name="Partner Admin",
        description="Full partner organization administration",
        hierarchy_level=HierarchyLevel.PARTNER,
        permissions=[
            "manage_partner_firms", "view_partner_reports", "manage_partner_branding",
            # Inherits firm_admin permissions for partner's firms
        ],
        display_order=10,
    ),
    RoleDefinition(
        code="partner_manager",
        name="Partner Manager",
        description="Partner organization manager",
        hierarchy_level=HierarchyLevel.PARTNER,
        permissions=[
            "view_partner_reports", "manage_partner_firms",
        ],
        parent_role="partner_admin",
        display_order=11,
    ),
    RoleDefinition(
        code="partner_support",
        name="Partner Support",
        description="Partner organization support staff",
        hierarchy_level=HierarchyLevel.PARTNER,
        permissions=[
            "view_partner_reports",
        ],
        display_order=12,
    ),

    # Firm Level (2)
    RoleDefinition(
        code="firm_admin",
        name="Firm Admin",
        description="Full firm administration with team and billing management",
        hierarchy_level=HierarchyLevel.FIRM,
        permissions=[
            # Team Management
            "manage_team", "invite_users", "view_team_performance",
            "assign_roles", "manage_custom_roles",
            # Client Management
            "view_client", "view_all_clients", "create_client",
            "edit_client", "manage_client", "archive_client", "assign_clients",
            # Return Operations
            "view_returns", "create_return", "edit_returns", "edit_return",
            "manage_returns", "review_returns", "approve_return", "reject_return",
            # Scenarios & Analysis
            "run_scenarios", "view_optimization", "generate_reports",
            # Compliance & Audit
            "view_compliance", "view_audit_logs", "export_audit_trail", "gdpr_requests",
            # Billing & Admin
            "view_billing", "update_payment", "change_plan",
            "update_branding", "manage_api_keys", "configure_integrations",
            # Workflow
            "manage_workflow", "reassign_work",
            # Documents
            "upload_documents", "view_documents", "delete_documents",
        ],
        display_order=20,
    ),
    RoleDefinition(
        code="senior_preparer",
        name="Senior Preparer",
        description="Experienced preparer with expanded client access",
        hierarchy_level=HierarchyLevel.FIRM,
        permissions=[
            "view_team_performance",
            "view_client", "view_all_clients", "create_client",
            "edit_client", "manage_client", "assign_clients",
            "view_returns", "create_return", "edit_returns", "edit_return",
            "manage_returns", "submit_for_review",
            "run_scenarios", "view_optimization", "generate_reports",
            "view_compliance", "view_audit_logs",
            "upload_documents", "view_documents",
            "reassign_work",
        ],
        parent_role="firm_admin",
        display_order=21,
    ),
    RoleDefinition(
        code="preparer",
        name="Preparer",
        description="Tax return preparer with assigned client access",
        hierarchy_level=HierarchyLevel.FIRM,
        permissions=[
            "view_client", "create_client",
            "view_returns", "create_return", "edit_returns", "edit_return",
            "submit_for_review",
            "run_scenarios", "view_optimization", "generate_reports",
            "upload_documents", "view_documents",
        ],
        parent_role="senior_preparer",
        display_order=22,
    ),
    RoleDefinition(
        code="reviewer",
        name="Reviewer",
        description="Quality reviewer with approval authority",
        hierarchy_level=HierarchyLevel.FIRM,
        permissions=[
            "view_team_performance",
            "view_client",
            "view_returns", "review_returns", "approve_return", "reject_return",
            "view_compliance", "view_audit_logs",
            "view_optimization",
            "view_documents",
        ],
        display_order=23,
    ),
]


class RoleCatalog:
    """
    In-memory catalog of role definitions.

    Used for quick lookups without database queries.
    """

    def __init__(self):
        self._roles: Dict[str, RoleDefinition] = {
            r.code: r for r in SYSTEM_ROLES
        }
        self._by_level: Dict[HierarchyLevel, List[RoleDefinition]] = {}
        for r in SYSTEM_ROLES:
            if r.hierarchy_level not in self._by_level:
                self._by_level[r.hierarchy_level] = []
            self._by_level[r.hierarchy_level].append(r)

    def get(self, code: str) -> Optional[RoleDefinition]:
        """Get role definition by code."""
        return self._roles.get(code)

    def get_by_level(self, level: HierarchyLevel) -> List[RoleDefinition]:
        """Get all roles at a hierarchy level."""
        return self._by_level.get(level, [])

    def get_all(self) -> List[RoleDefinition]:
        """Get all role definitions."""
        return list(self._roles.values())

    def exists(self, code: str) -> bool:
        """Check if role code exists."""
        return code in self._roles


# Singleton instance
_role_catalog: Optional[RoleCatalog] = None


def get_role_catalog() -> RoleCatalog:
    """Get singleton role catalog."""
    global _role_catalog
    if _role_catalog is None:
        _role_catalog = RoleCatalog()
    return _role_catalog


# =============================================================================
# TIER LIMITS FOR CUSTOM ROLES
# =============================================================================

CUSTOM_ROLE_LIMITS = {
    "starter": 1,
    "professional": 5,
    "enterprise": None,  # Unlimited
}


# =============================================================================
# ROLE SERVICE
# =============================================================================

@dataclass
class RoleAssignmentResult:
    """Result of a role assignment operation."""
    success: bool
    message: str
    role_id: Optional[UUID] = None
    errors: List[str] = field(default_factory=list)


class RoleService:
    """
    Role management service.

    Handles:
    - Role CRUD operations
    - Role assignment to users
    - Custom role limits by tier
    - Privilege escalation prevention
    """

    def __init__(self, db: Session):
        self.db = db
        self.catalog = get_role_catalog()
        self.perm_catalog = get_permission_catalog()

    # -------------------------------------------------------------------------
    # Role Queries
    # -------------------------------------------------------------------------

    async def get_role_by_id(self, role_id: UUID) -> Optional[RoleTemplate]:
        """Get role by ID."""
        stmt = (
            select(RoleTemplate)
            .options(
                selectinload(RoleTemplate.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(RoleTemplate.role_id == role_id)
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_role_by_code(
        self,
        code: str,
        firm_id: Optional[UUID] = None,
        partner_id: Optional[UUID] = None,
    ) -> Optional[RoleTemplate]:
        """Get role by code within scope (system, firm, or partner)."""
        conditions = [RoleTemplate.code == code]

        if firm_id:
            conditions.append(
                or_(
                    RoleTemplate.firm_id == firm_id,
                    and_(RoleTemplate.firm_id.is_(None), RoleTemplate.is_system == True)
                )
            )
        elif partner_id:
            conditions.append(
                or_(
                    RoleTemplate.partner_id == partner_id,
                    and_(RoleTemplate.partner_id.is_(None), RoleTemplate.is_system == True)
                )
            )
        else:
            # System roles only
            conditions.append(RoleTemplate.is_system == True)

        stmt = (
            select(RoleTemplate)
            .options(
                selectinload(RoleTemplate.role_permissions)
                .selectinload(RolePermission.permission)
            )
            .where(and_(*conditions))
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_roles(
        self,
        firm_id: Optional[UUID] = None,
        hierarchy_level: Optional[HierarchyLevel] = None,
        include_system: bool = True,
        active_only: bool = True,
    ) -> List[RoleTemplate]:
        """List roles available to a firm."""
        conditions = []

        if active_only:
            conditions.append(RoleTemplate.is_active == True)

        if hierarchy_level:
            conditions.append(RoleTemplate.hierarchy_level == hierarchy_level.value)

        if firm_id:
            # Firm sees: system roles at firm level + their custom roles
            if include_system:
                conditions.append(
                    or_(
                        and_(
                            RoleTemplate.is_system == True,
                            RoleTemplate.hierarchy_level >= HierarchyLevel.FIRM.value
                        ),
                        RoleTemplate.firm_id == firm_id
                    )
                )
            else:
                conditions.append(RoleTemplate.firm_id == firm_id)
        elif include_system:
            conditions.append(RoleTemplate.is_system == True)

        stmt = (
            select(RoleTemplate)
            .where(and_(*conditions))
            .order_by(RoleTemplate.hierarchy_level, RoleTemplate.display_order)
        )
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_firm_custom_role_count(self, firm_id: UUID) -> int:
        """Get count of custom roles for a firm."""
        stmt = (
            select(func.count(RoleTemplate.role_id))
            .where(
                and_(
                    RoleTemplate.firm_id == firm_id,
                    RoleTemplate.is_system == False
                )
            )
        )
        result = self.db.execute(stmt)
        return result.scalar() or 0

    # -------------------------------------------------------------------------
    # Role CRUD
    # -------------------------------------------------------------------------

    async def create_custom_role(
        self,
        code: str,
        name: str,
        description: str,
        permission_codes: List[str],
        firm_id: UUID,
        subscription_tier: str,
        created_by: UUID,
        parent_role_code: Optional[str] = None,
    ) -> RoleAssignmentResult:
        """
        Create a custom role for a firm.

        Validates:
        - Tier allows custom roles
        - Not exceeding tier limit
        - Code is unique within firm
        - All permissions exist and are grantable
        """
        # Check tier allows custom roles
        limit = CUSTOM_ROLE_LIMITS.get(subscription_tier, 0)
        if limit == 0:
            return RoleAssignmentResult(
                success=False,
                message="Custom roles not available in this tier",
                errors=["Upgrade to Professional or Enterprise for custom roles"],
            )

        # Check count limit
        if limit is not None:
            current_count = await self.get_firm_custom_role_count(firm_id)
            if current_count >= limit:
                return RoleAssignmentResult(
                    success=False,
                    message=f"Custom role limit reached ({limit} roles)",
                    errors=[f"Your tier allows {limit} custom roles. Upgrade for more."],
                )

        # Check code uniqueness
        existing = await self.get_role_by_code(code, firm_id=firm_id)
        if existing:
            return RoleAssignmentResult(
                success=False,
                message=f"Role code '{code}' already exists",
                errors=["Choose a different role code"],
            )

        # Validate permissions
        invalid_perms = []
        for perm_code in permission_codes:
            perm_def = self.perm_catalog.get(perm_code)
            if not perm_def:
                invalid_perms.append(f"Unknown permission: {perm_code}")
            elif perm_def.min_hierarchy_level.value < HierarchyLevel.FIRM.value:
                invalid_perms.append(f"Cannot grant platform permission: {perm_code}")
            elif subscription_tier not in perm_def.tier_restriction:
                invalid_perms.append(f"Permission not available in tier: {perm_code}")

        if invalid_perms:
            return RoleAssignmentResult(
                success=False,
                message="Invalid permissions",
                errors=invalid_perms,
            )

        # Get parent role ID if specified
        parent_role_id = None
        if parent_role_code:
            parent = await self.get_role_by_code(parent_role_code, firm_id=firm_id)
            if parent:
                parent_role_id = parent.role_id

        # Create role
        role = RoleTemplate(
            code=code,
            name=name,
            description=description,
            hierarchy_level=HierarchyLevel.FIRM.value,
            firm_id=firm_id,
            parent_role_id=parent_role_id,
            is_system=False,
            is_active=True,
            is_assignable=True,
            created_by=created_by,
        )
        self.db.add(role)
        self.db.flush()  # Get role_id

        # Add permissions
        for perm_code in permission_codes:
            perm = await self._get_permission_by_code(perm_code)
            if perm:
                rp = RolePermission(
                    role_id=role.role_id,
                    permission_id=perm.permission_id,
                    granted_by=created_by,
                )
                self.db.add(rp)

        # Invalidate cache for firm
        await self._invalidate_firm_cache(firm_id, created_by)

        self.db.commit()

        return RoleAssignmentResult(
            success=True,
            message=f"Custom role '{name}' created successfully",
            role_id=role.role_id,
        )

    async def update_role_permissions(
        self,
        role_id: UUID,
        permission_codes: List[str],
        updated_by: UUID,
        firm_id: Optional[UUID] = None,
        subscription_tier: str = "starter",
    ) -> RoleAssignmentResult:
        """
        Update permissions for a role.

        Only custom roles (non-system) can be updated.
        """
        role = await self.get_role_by_id(role_id)
        if not role:
            return RoleAssignmentResult(
                success=False,
                message="Role not found",
                errors=["Invalid role ID"],
            )

        if role.is_system:
            return RoleAssignmentResult(
                success=False,
                message="Cannot modify system role permissions",
                errors=["System roles are read-only"],
            )

        # Validate ownership
        if firm_id and role.firm_id != firm_id:
            return RoleAssignmentResult(
                success=False,
                message="Cannot modify roles from other firms",
                errors=["Access denied"],
            )

        # Validate permissions
        invalid_perms = []
        for perm_code in permission_codes:
            perm_def = self.perm_catalog.get(perm_code)
            if not perm_def:
                invalid_perms.append(f"Unknown permission: {perm_code}")
            elif subscription_tier not in perm_def.tier_restriction:
                invalid_perms.append(f"Permission not available in tier: {perm_code}")

        if invalid_perms:
            return RoleAssignmentResult(
                success=False,
                message="Invalid permissions",
                errors=invalid_perms,
            )

        # Remove existing permissions
        self.db.execute(
            RolePermission.__table__.delete().where(
                RolePermission.role_id == role_id
            )
        )

        # Add new permissions
        for perm_code in permission_codes:
            perm = await self._get_permission_by_code(perm_code)
            if perm:
                rp = RolePermission(
                    role_id=role.role_id,
                    permission_id=perm.permission_id,
                    granted_by=updated_by,
                )
                self.db.add(rp)

        # Invalidate cache
        if role.firm_id:
            await self._invalidate_firm_cache(role.firm_id, updated_by)

        self.db.commit()

        return RoleAssignmentResult(
            success=True,
            message="Role permissions updated",
            role_id=role.role_id,
        )

    async def delete_role(
        self,
        role_id: UUID,
        deleted_by: UUID,
        firm_id: Optional[UUID] = None,
    ) -> RoleAssignmentResult:
        """Delete a custom role."""
        role = await self.get_role_by_id(role_id)
        if not role:
            return RoleAssignmentResult(
                success=False,
                message="Role not found",
            )

        if role.is_system:
            return RoleAssignmentResult(
                success=False,
                message="Cannot delete system roles",
            )

        if firm_id and role.firm_id != firm_id:
            return RoleAssignmentResult(
                success=False,
                message="Cannot delete roles from other firms",
            )

        # Check if role is assigned to any users
        stmt = (
            select(func.count(UserRoleAssignment.user_id))
            .where(UserRoleAssignment.role_id == role_id)
        )
        result = self.db.execute(stmt)
        assignment_count = result.scalar() or 0

        if assignment_count > 0:
            return RoleAssignmentResult(
                success=False,
                message=f"Role is assigned to {assignment_count} users",
                errors=["Remove all user assignments before deleting"],
            )

        # Delete the role (cascades to role_permissions)
        self.db.delete(role)

        # Invalidate cache
        if role.firm_id:
            await self._invalidate_firm_cache(role.firm_id, deleted_by)

        self.db.commit()

        return RoleAssignmentResult(
            success=True,
            message="Role deleted",
        )

    # -------------------------------------------------------------------------
    # Role Assignment
    # -------------------------------------------------------------------------

    async def assign_role(
        self,
        user_id: UUID,
        role_id: UUID,
        assigned_by: UUID,
        assigner_hierarchy_level: int,
        is_primary: bool = False,
        expires_at: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> RoleAssignmentResult:
        """
        Assign a role to a user.

        Validates:
        - Role exists and is active
        - Assigner has sufficient privilege level
        - Prevents privilege escalation
        """
        role = await self.get_role_by_id(role_id)
        if not role:
            return RoleAssignmentResult(
                success=False,
                message="Role not found",
            )

        if not role.is_active:
            return RoleAssignmentResult(
                success=False,
                message="Role is not active",
            )

        if not role.is_assignable:
            return RoleAssignmentResult(
                success=False,
                message="Role cannot be assigned",
            )

        # Privilege escalation check
        # Users can only assign roles at their level or below
        if role.hierarchy_level < assigner_hierarchy_level:
            return RoleAssignmentResult(
                success=False,
                message="Cannot assign higher-privilege role",
                errors=[f"Your level ({assigner_hierarchy_level}) cannot assign level {role.hierarchy_level} roles"],
            )

        # Check if already assigned
        existing = self.db.execute(
            select(UserRoleAssignment).where(
                and_(
                    UserRoleAssignment.user_id == user_id,
                    UserRoleAssignment.role_id == role_id
                )
            )
        ).scalar_one_or_none()

        if existing:
            # Update existing assignment
            existing.is_primary = is_primary
            existing.expires_at = expires_at
            existing.notes = notes
        else:
            # Create new assignment
            assignment = UserRoleAssignment(
                user_id=user_id,
                role_id=role_id,
                is_primary=is_primary,
                assigned_at=datetime.utcnow(),
                assigned_by=assigned_by,
                expires_at=expires_at,
                notes=notes,
            )
            self.db.add(assignment)

        # If primary, unset other primary flags
        if is_primary:
            self.db.execute(
                UserRoleAssignment.__table__.update()
                .where(
                    and_(
                        UserRoleAssignment.user_id == user_id,
                        UserRoleAssignment.role_id != role_id
                    )
                )
                .values(is_primary=False)
            )

        # Invalidate user cache
        await self._invalidate_user_cache(user_id, assigned_by)

        self.db.commit()

        return RoleAssignmentResult(
            success=True,
            message=f"Role '{role.name}' assigned",
            role_id=role_id,
        )

    async def remove_role(
        self,
        user_id: UUID,
        role_id: UUID,
        removed_by: UUID,
    ) -> RoleAssignmentResult:
        """Remove a role from a user."""
        existing = self.db.execute(
            select(UserRoleAssignment).where(
                and_(
                    UserRoleAssignment.user_id == user_id,
                    UserRoleAssignment.role_id == role_id
                )
            )
        ).scalar_one_or_none()

        if not existing:
            return RoleAssignmentResult(
                success=False,
                message="Role assignment not found",
            )

        was_primary = existing.is_primary

        self.db.delete(existing)

        # If was primary, assign another role as primary
        if was_primary:
            other = self.db.execute(
                select(UserRoleAssignment)
                .where(UserRoleAssignment.user_id == user_id)
                .limit(1)
            ).scalar_one_or_none()

            if other:
                other.is_primary = True

        # Invalidate cache
        await self._invalidate_user_cache(user_id, removed_by)

        self.db.commit()

        return RoleAssignmentResult(
            success=True,
            message="Role removed",
        )

    async def get_user_roles(self, user_id: UUID) -> List[UserRoleAssignment]:
        """Get all role assignments for a user."""
        stmt = (
            select(UserRoleAssignment)
            .options(selectinload(UserRoleAssignment.role))
            .where(UserRoleAssignment.user_id == user_id)
            .order_by(UserRoleAssignment.is_primary.desc())
        )
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # System Role Seeding
    # -------------------------------------------------------------------------

    async def seed_system_roles(self) -> int:
        """
        Seed system roles from catalog.

        Creates or updates roles based on SYSTEM_ROLES.
        Returns count of roles seeded.
        """
        count = 0

        for role_def in SYSTEM_ROLES:
            # Check if exists
            existing = await self.get_role_by_code(role_def.code)

            if existing:
                # Update existing
                existing.name = role_def.name
                existing.description = role_def.description
                existing.hierarchy_level = role_def.hierarchy_level.value
                existing.display_order = role_def.display_order
                existing.is_system = True
                role = existing
            else:
                # Create new
                role = RoleTemplate(
                    code=role_def.code,
                    name=role_def.name,
                    description=role_def.description,
                    hierarchy_level=role_def.hierarchy_level.value,
                    is_system=True,
                    is_active=True,
                    is_assignable=True,
                    display_order=role_def.display_order,
                )
                self.db.add(role)
                self.db.flush()

            # Update permissions for the role
            await self._sync_role_permissions(role, role_def.permissions)

            # Handle parent role
            if role_def.parent_role:
                parent = await self.get_role_by_code(role_def.parent_role)
                if parent:
                    role.parent_role_id = parent.role_id

            count += 1

        self.db.commit()
        logger.info(f"Seeded {count} system roles")
        return count

    async def _sync_role_permissions(
        self,
        role: RoleTemplate,
        permission_codes: List[str]
    ) -> None:
        """Sync role permissions with definition."""
        # Get current permissions
        current_perms = {
            rp.permission.code for rp in role.role_permissions
            if rp.permission
        }
        target_perms = set(permission_codes)

        # Add new permissions
        for code in target_perms - current_perms:
            perm = await self._get_permission_by_code(code)
            if perm:
                rp = RolePermission(
                    role_id=role.role_id,
                    permission_id=perm.permission_id,
                )
                self.db.add(rp)

        # Remove old permissions (for system roles only - keep in sync)
        for code in current_perms - target_perms:
            perm = await self._get_permission_by_code(code)
            if perm:
                self.db.execute(
                    RolePermission.__table__.delete().where(
                        and_(
                            RolePermission.role_id == role.role_id,
                            RolePermission.permission_id == perm.permission_id
                        )
                    )
                )

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def _get_permission_by_code(self, code: str) -> Optional[Permission]:
        """Get permission by code."""
        stmt = select(Permission).where(Permission.code == code)
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _invalidate_user_cache(self, user_id: UUID, updated_by: UUID) -> None:
        """Invalidate permission cache for a user."""
        scope = f"user:{user_id}"
        await self._increment_cache_version(scope, updated_by, "User role changed")

    async def _invalidate_firm_cache(self, firm_id: UUID, updated_by: UUID) -> None:
        """Invalidate permission cache for all users in a firm."""
        scope = f"firm:{firm_id}"
        await self._increment_cache_version(scope, updated_by, "Firm role updated")

    async def _increment_cache_version(
        self,
        scope: str,
        updated_by: UUID,
        reason: str
    ) -> None:
        """Increment cache version for a scope."""
        existing = self.db.execute(
            select(PermissionCacheVersion).where(PermissionCacheVersion.scope == scope)
        ).scalar_one_or_none()

        if existing:
            existing.version += 1
            existing.updated_at = datetime.utcnow()
            existing.updated_by = updated_by
            existing.update_reason = reason
        else:
            version = PermissionCacheVersion(
                scope=scope,
                version=1,
                updated_by=updated_by,
                update_reason=reason,
            )
            self.db.add(version)


# =============================================================================
# SERVICE FACTORY
# =============================================================================

def get_role_service(db: Session) -> RoleService:
    """Get role service instance."""
    return RoleService(db)
