"""
Compatibility backend for admin RBAC routes.

This module is used when ``core.rbac`` is not available in this workspace.
It preserves route importability and provides a safe, deterministic
fallback implementation for RBAC admin APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4, uuid5

from fastapi import Depends, HTTPException, status

from rbac import AuthContext, Role, require_auth
from rbac.permissions import Category, PERMISSIONS, ROLE_PERMISSIONS
from rbac.roles import PLATFORM_ROLES, ROLES


class PermissionCategory(str, Enum):
    """Permission category enum expected by admin RBAC routes."""

    PLATFORM = "platform"
    FIRM = "firm"
    TEAM = "team"
    CLIENT = "client"
    RETURN = "return"
    DOCUMENT = "document"
    SELF = "self"


class HierarchyLevel(int, Enum):
    """Hierarchy levels for RBAC context and role checks."""

    PLATFORM = 0
    FIRM = 1
    CLIENT = 2


class OverrideAction(str, Enum):
    """Action for user permission override."""

    GRANT = "grant"
    REVOKE = "revoke"


@dataclass
class RBACContext:
    """Compat RBAC context projected from current AuthContext."""

    user_id: UUID
    role: Role
    firm_id: Optional[UUID]
    permission_codes: set[str]
    subscription_tier: str
    hierarchy_level: int

    @property
    def is_platform_admin(self) -> bool:
        return self.role in PLATFORM_ROLES

    def require_authenticated(self) -> None:
        if (
            not self.user_id
            or str(self.user_id) == "00000000-0000-0000-0000-000000000000"
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )


@dataclass
class _CompatPermission:
    permission_id: UUID
    code: str
    name: str
    description: Optional[str]
    category: PermissionCategory
    min_hierarchy_level: int
    tier_restriction: List[str]
    is_enabled: bool
    is_system: bool


@dataclass
class _CompatRolePermission:
    permission: _CompatPermission


@dataclass
class _CompatRole:
    role_id: UUID
    code: str
    name: str
    description: Optional[str]
    hierarchy_level: int
    firm_id: Optional[UUID]
    partner_id: Optional[UUID]
    parent_role_id: Optional[UUID]
    is_system: bool
    is_active: bool
    is_assignable: bool
    display_order: int
    role_permissions: List[_CompatRolePermission]
    created_at: datetime


@dataclass
class _CompatUserRoleAssignment:
    role_id: UUID
    role: _CompatRole
    is_primary: bool
    assigned_at: datetime
    expires_at: Optional[datetime]


@dataclass
class _ServiceResult:
    success: bool
    message: str
    errors: List[str] = field(default_factory=list)
    role_id: Optional[UUID] = None
    override_id: Optional[UUID] = None


_PERM_NS = UUID("b6f3a3ed-39ba-49ba-8f9f-b4c98f0cf4c0")
_ROLE_NS = UUID("6f98f0b4-d4f0-45a3-8f90-08ed23928ddd")

_CUSTOM_ROLES: Dict[UUID, _CompatRole] = {}
_USER_ROLE_ASSIGNMENTS: Dict[UUID, List[_CompatUserRoleAssignment]] = {}
_USER_PERMISSION_OVERRIDES: Dict[UUID, List[dict]] = {}

_PERMISSION_ALIAS_MAP = {
    "manage_custom_roles": {"team_manage", "platform_manage_admins"},
    "assign_roles": {"team_manage", "team_invite", "platform_manage_admins"},
    "view_team_performance": {"team_view", "firm_view_analytics", "platform_view_metrics"},
}
_TIER_RANK = {"starter": 0, "professional": 1, "enterprise": 2}


def _permission_uuid(code: str) -> UUID:
    return uuid5(_PERM_NS, code)


def _role_uuid(code: str) -> UUID:
    return uuid5(_ROLE_NS, code)


def _category_to_compat(category: Category) -> PermissionCategory:
    return PermissionCategory(category.value)


def _minimum_level_for_category(category: Category) -> int:
    if category == Category.PLATFORM:
        return HierarchyLevel.PLATFORM.value
    if category in {
        Category.FIRM,
        Category.TEAM,
        Category.CLIENT,
        Category.RETURN,
        Category.DOCUMENT,
    }:
        return HierarchyLevel.FIRM.value
    return HierarchyLevel.CLIENT.value


def _tier_restriction_for_category(category: Category) -> List[str]:
    if category == Category.PLATFORM:
        return ["enterprise"]
    if category in {Category.FIRM, Category.TEAM, Category.CLIENT, Category.RETURN, Category.DOCUMENT}:
        return ["professional", "enterprise"]
    return ["starter", "professional", "enterprise"]


def _build_permission(code: str) -> Optional[_CompatPermission]:
    for permission_enum, info in PERMISSIONS.items():
        if permission_enum.value != code:
            continue
        return _CompatPermission(
            permission_id=_permission_uuid(code),
            code=code,
            name=info.name,
            description=info.description,
            category=_category_to_compat(info.category),
            min_hierarchy_level=_minimum_level_for_category(info.category),
            tier_restriction=_tier_restriction_for_category(info.category),
            is_enabled=True,
            is_system=True,
        )
    return None


def _all_permissions() -> List[_CompatPermission]:
    result: List[_CompatPermission] = []
    for permission_enum in PERMISSIONS:
        permission = _build_permission(permission_enum.value)
        if permission:
            result.append(permission)
    result.sort(key=lambda p: p.code)
    return result


def _system_roles() -> List[_CompatRole]:
    permissions_by_code = {p.code: p for p in _all_permissions()}
    roles: List[_CompatRole] = []

    for role_enum, role_info in ROLES.items():
        role_permissions = []
        for permission_enum in ROLE_PERMISSIONS.get(role_enum, frozenset()):
            permission = permissions_by_code.get(permission_enum.value)
            if permission:
                role_permissions.append(_CompatRolePermission(permission=permission))

        roles.append(
            _CompatRole(
                role_id=_role_uuid(role_enum.value),
                code=role_enum.value,
                name=role_info.name,
                description=role_info.description,
                hierarchy_level=role_info.level.value,
                firm_id=None,
                partner_id=None,
                parent_role_id=None,
                is_system=True,
                is_active=True,
                is_assignable=role_enum not in PLATFORM_ROLES,
                display_order=10 + role_info.level.value,
                role_permissions=role_permissions,
                created_at=datetime(2026, 1, 1),
            )
        )

    roles.sort(key=lambda role: (role.hierarchy_level, role.code))
    return roles


def _roles_for_scope(firm_id: Optional[UUID]) -> List[_CompatRole]:
    roles = list(_system_roles())
    for role in _CUSTOM_ROLES.values():
        if firm_id and role.firm_id and role.firm_id != firm_id:
            continue
        roles.append(role)
    return roles


def _has_permission(ctx: RBACContext, required_code: str) -> bool:
    if ctx.is_platform_admin:
        return True
    if required_code in ctx.permission_codes:
        return True
    aliases = _PERMISSION_ALIAS_MAP.get(required_code, set())
    if aliases & ctx.permission_codes:
        return True
    return False


async def get_rbac_context(
    user: AuthContext = Depends(require_auth),
) -> RBACContext:
    """Project AuthContext into RBACContext expected by admin routes."""
    role = user.role if isinstance(user.role, Role) else Role(str(user.role))

    permission_codes = {
        permission.value if hasattr(permission, "value") else str(permission)
        for permission in getattr(user, "permissions", set())
    }

    if role == Role.PARTNER:
        permission_codes.update({"manage_custom_roles", "assign_roles", "view_team_performance"})
    elif role == Role.STAFF:
        permission_codes.update({"view_team_performance"})
    elif role in PLATFORM_ROLES:
        permission_codes.update({"manage_custom_roles", "assign_roles", "view_team_performance"})

    if role in PLATFORM_ROLES:
        subscription_tier = "enterprise"
    elif role in {Role.PARTNER, Role.STAFF}:
        subscription_tier = "professional"
    else:
        subscription_tier = "starter"

    hierarchy_level = ROLES[role].level.value if role in ROLES else HierarchyLevel.CLIENT.value

    return RBACContext(
        user_id=user.user_id,
        role=role,
        firm_id=user.firm_id,
        permission_codes=permission_codes,
        subscription_tier=subscription_tier,
        hierarchy_level=hierarchy_level,
    )


async def require_firm_admin(
    ctx: RBACContext = Depends(get_rbac_context),
) -> RBACContext:
    """Require partner role (or platform role for operational override)."""
    ctx.require_authenticated()
    if ctx.role not in {Role.PARTNER} and not ctx.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firm admin access required",
        )
    return ctx


async def require_platform_admin(
    ctx: RBACContext = Depends(get_rbac_context),
) -> RBACContext:
    """Require platform role."""
    ctx.require_authenticated()
    if not ctx.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return ctx


class RequirePermission:
    """Dependency factory to enforce permission-like checks."""

    def __init__(self, permission_code: str):
        self.permission_code = permission_code

    async def __call__(self, ctx: RBACContext = Depends(get_rbac_context)) -> None:
        if not _has_permission(ctx, self.permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required permission: {self.permission_code}",
            )


class RequireSubscriptionTier:
    """Dependency factory to enforce minimum subscription tier."""

    def __init__(self, minimum_tier: str):
        self.minimum_tier = minimum_tier

    async def __call__(self, ctx: RBACContext = Depends(get_rbac_context)) -> None:
        required_rank = _TIER_RANK.get(self.minimum_tier, 0)
        actual_rank = _TIER_RANK.get(ctx.subscription_tier, 0)
        if actual_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {self.minimum_tier} tier",
            )


class PermissionService:
    """Compatibility permission service."""

    def __init__(self, _db):
        self._db = _db

    async def get_all_permissions(
        self,
        category: Optional[PermissionCategory] = None,
        enabled_only: bool = True,
    ) -> List[_CompatPermission]:
        permissions = _all_permissions()
        if category is not None:
            permissions = [p for p in permissions if p.category == category]
        if enabled_only:
            permissions = [p for p in permissions if p.is_enabled]
        return permissions

    async def get_permission_by_code(self, code: str) -> Optional[_CompatPermission]:
        return _build_permission(code)

    async def seed_system_permissions(self) -> int:
        return len(_all_permissions())

    async def create_permission_override(
        self,
        *,
        user_id: UUID,
        permission_code: str,
        action: OverrideAction,
        resource_type: Optional[str],
        resource_id: Optional[UUID],
        expires_at: Optional[datetime],
        reason: Optional[str],
        created_by: UUID,
    ) -> _ServiceResult:
        permission = await self.get_permission_by_code(permission_code)
        if not permission:
            return _ServiceResult(
                success=False,
                message="Unknown permission",
                errors=[f"Unknown permission: {permission_code}"],
            )

        override_id = uuid4()
        _USER_PERMISSION_OVERRIDES.setdefault(user_id, []).append(
            {
                "override_id": override_id,
                "permission_id": permission.permission_id,
                "action": action.value,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "expires_at": expires_at,
                "reason": reason,
                "created_by": created_by,
                "created_at": datetime.utcnow(),
            }
        )

        return _ServiceResult(
            success=True,
            message=f"Permission {action.value}ed for user",
            override_id=override_id,
        )


class RoleService:
    """Compatibility role service."""

    def __init__(self, _db):
        self._db = _db

    async def list_roles(
        self,
        *,
        firm_id: Optional[UUID],
        include_system: bool,
        active_only: bool,
    ) -> List[_CompatRole]:
        roles = _roles_for_scope(firm_id)
        if not include_system:
            roles = [r for r in roles if not r.is_system]
        if active_only:
            roles = [r for r in roles if r.is_active]
        roles.sort(key=lambda r: (r.hierarchy_level, r.code))
        return roles

    async def create_custom_role(
        self,
        *,
        code: str,
        name: str,
        description: Optional[str],
        permission_codes: List[str],
        firm_id: Optional[UUID],
        subscription_tier: str,
        created_by: UUID,
        parent_role_code: Optional[str],
    ) -> _ServiceResult:
        _ = subscription_tier
        _ = created_by
        _ = parent_role_code

        if any(role.code == code for role in _roles_for_scope(None)):
            return _ServiceResult(
                success=False,
                message="Role code already exists",
                errors=[f"Role code '{code}' already exists"],
            )

        known_permissions = {permission.code: permission for permission in _all_permissions()}
        unknown = [code for code in permission_codes if code not in known_permissions]
        if unknown:
            return _ServiceResult(
                success=False,
                message="Invalid permissions",
                errors=[f"Unknown permissions: {', '.join(sorted(unknown))}"],
            )

        role_id = uuid4()
        role_permissions = [
            _CompatRolePermission(permission=known_permissions[code])
            for code in permission_codes
        ]

        role = _CompatRole(
            role_id=role_id,
            code=code,
            name=name,
            description=description,
            hierarchy_level=HierarchyLevel.FIRM.value,
            firm_id=firm_id,
            partner_id=None,
            parent_role_id=None,
            is_system=False,
            is_active=True,
            is_assignable=True,
            display_order=100,
            role_permissions=role_permissions,
            created_at=datetime.utcnow(),
        )
        _CUSTOM_ROLES[role_id] = role

        return _ServiceResult(
            success=True,
            message="Role created",
            role_id=role_id,
        )

    async def get_role_by_id(self, role_id: UUID) -> Optional[_CompatRole]:
        for role in _system_roles():
            if role.role_id == role_id:
                return role
        return _CUSTOM_ROLES.get(role_id)

    async def update_role_permissions(
        self,
        *,
        role_id: UUID,
        permission_codes: List[str],
        updated_by: UUID,
        firm_id: Optional[UUID],
        subscription_tier: str,
    ) -> _ServiceResult:
        _ = updated_by
        _ = subscription_tier

        role = _CUSTOM_ROLES.get(role_id)
        if not role:
            return _ServiceResult(
                success=False,
                message="Role not found or is system role",
                errors=["Only custom roles can be updated"],
            )

        if firm_id and role.firm_id and role.firm_id != firm_id:
            return _ServiceResult(
                success=False,
                message="Access denied",
                errors=["Cannot update roles from another firm"],
            )

        known_permissions = {permission.code: permission for permission in _all_permissions()}
        unknown = [code for code in permission_codes if code not in known_permissions]
        if unknown:
            return _ServiceResult(
                success=False,
                message="Invalid permissions",
                errors=[f"Unknown permissions: {', '.join(sorted(unknown))}"],
            )

        role.role_permissions = [
            _CompatRolePermission(permission=known_permissions[code])
            for code in permission_codes
        ]
        return _ServiceResult(success=True, message="Role permissions updated")

    async def delete_role(
        self,
        *,
        role_id: UUID,
        deleted_by: UUID,
        firm_id: Optional[UUID],
    ) -> _ServiceResult:
        _ = deleted_by

        role = _CUSTOM_ROLES.get(role_id)
        if not role:
            return _ServiceResult(
                success=False,
                message="Role not found or is system role",
                errors=["Only custom roles can be deleted"],
            )

        if firm_id and role.firm_id and role.firm_id != firm_id:
            return _ServiceResult(
                success=False,
                message="Access denied",
                errors=["Cannot delete roles from another firm"],
            )

        for assignments in _USER_ROLE_ASSIGNMENTS.values():
            if any(assignment.role_id == role_id for assignment in assignments):
                return _ServiceResult(
                    success=False,
                    message="Role is in use",
                    errors=["Remove user assignments before deleting role"],
                )

        del _CUSTOM_ROLES[role_id]
        return _ServiceResult(success=True, message="Role deleted")

    async def get_user_roles(self, user_id: UUID) -> List[_CompatUserRoleAssignment]:
        return list(_USER_ROLE_ASSIGNMENTS.get(user_id, []))

    async def assign_role(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        assigned_by: UUID,
        assigner_hierarchy_level: int,
        is_primary: bool,
        expires_at: Optional[datetime],
        notes: Optional[str],
    ) -> _ServiceResult:
        _ = assigned_by
        _ = notes

        role = await self.get_role_by_id(role_id)
        if not role:
            return _ServiceResult(
                success=False,
                message="Role not found",
                errors=["Invalid role_id"],
            )

        if role.hierarchy_level < assigner_hierarchy_level:
            return _ServiceResult(
                success=False,
                message="Hierarchy violation",
                errors=["Cannot assign role above your hierarchy level"],
            )

        assignments = _USER_ROLE_ASSIGNMENTS.setdefault(user_id, [])

        # Replace existing assignment for same role_id.
        assignments = [assignment for assignment in assignments if assignment.role_id != role_id]
        if is_primary:
            assignments = [
                _CompatUserRoleAssignment(
                    role_id=assignment.role_id,
                    role=assignment.role,
                    is_primary=False,
                    assigned_at=assignment.assigned_at,
                    expires_at=assignment.expires_at,
                )
                for assignment in assignments
            ]

        assignments.append(
            _CompatUserRoleAssignment(
                role_id=role_id,
                role=role,
                is_primary=is_primary,
                assigned_at=datetime.utcnow(),
                expires_at=expires_at,
            )
        )
        _USER_ROLE_ASSIGNMENTS[user_id] = assignments

        return _ServiceResult(success=True, message="Role assigned")

    async def remove_role(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        removed_by: UUID,
    ) -> _ServiceResult:
        _ = removed_by
        assignments = _USER_ROLE_ASSIGNMENTS.get(user_id, [])
        updated = [assignment for assignment in assignments if assignment.role_id != role_id]
        if len(updated) == len(assignments):
            return _ServiceResult(
                success=False,
                message="Role assignment not found",
                errors=["No matching assignment"],
            )
        _USER_ROLE_ASSIGNMENTS[user_id] = updated
        return _ServiceResult(success=True, message="Role removed")

    async def seed_system_roles(self) -> int:
        return len(_system_roles())


def get_permission_service(db) -> PermissionService:
    """Factory for permission service."""
    return PermissionService(db)


def get_role_service(db) -> RoleService:
    """Factory for role service."""
    return RoleService(db)

