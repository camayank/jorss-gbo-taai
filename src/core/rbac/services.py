"""
Core RBAC services (database-backed).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import selectinload

from rbac.permissions import Category, PERMISSIONS, ROLE_PERMISSIONS
from rbac.roles import PLATFORM_ROLES, ROLES, Role
from database.models import Base

from .models import (
    ClientAccessGrant,
    HierarchyLevel,
    OverrideAction,
    Partner,
    PartnerAdmin,
    PartnerFirm,
    Permission,
    PermissionCacheVersion,
    RBACAuditLog,
    PermissionCategory,
    RolePermission,
    RoleTemplate,
    UserPermissionOverride,
    UserRoleAssignment,
)


@dataclass
class ServiceResult:
    """Generic service operation result."""

    success: bool
    message: str
    errors: list[str] = field(default_factory=list)
    role_id: Optional[UUID] = None
    override_id: Optional[UUID] = None


_TIER_RANK = {"starter": 0, "professional": 1, "enterprise": 2}
_SCHEMA_READY_KEYS: set[str] = set()
_RBAC_TABLES = [
    Permission.__table__,
    RoleTemplate.__table__,
    RolePermission.__table__,
    UserRoleAssignment.__table__,
    UserPermissionOverride.__table__,
    RBACAuditLog.__table__,
    PermissionCacheVersion.__table__,
    Partner.__table__,
    PartnerFirm.__table__,
    PartnerAdmin.__table__,
    ClientAccessGrant.__table__,
]


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _exec(db, stmt):
    return await _maybe_await(db.execute(stmt))


async def _commit(db) -> None:
    await _maybe_await(db.commit())


async def _ensure_schema(db) -> None:
    """Create RBAC tables when missing."""
    bind = getattr(db, "bind", None)
    if bind is None and hasattr(db, "get_bind"):
        bind = db.get_bind()

    if bind is None:
        return

    bind_key = _get_bind_key(bind)
    if bind_key in _SCHEMA_READY_KEYS:
        return

    def _create(sync_bind):
        Base.metadata.create_all(sync_bind, tables=_RBAC_TABLES, checkfirst=True)

    # AsyncEngine
    if hasattr(bind, "sync_engine"):
        async with bind.begin() as conn:
            await conn.run_sync(_create)
        _SCHEMA_READY_KEYS.add(bind_key)
        return

    # AsyncConnection
    if hasattr(bind, "run_sync"):
        await bind.run_sync(_create)
        _SCHEMA_READY_KEYS.add(bind_key)
        return

    # Sync engine/connection
    _create(bind)
    _SCHEMA_READY_KEYS.add(bind_key)


def _get_bind_key(bind) -> str:
    """Build a stable key for schema bootstrap state per database target."""
    sync_engine = getattr(bind, "sync_engine", None)
    if sync_engine is not None:
        sync_url = getattr(sync_engine, "url", None)
        if sync_url is not None:
            return str(sync_url)

    url = getattr(bind, "url", None)
    if url is not None:
        return str(url)

    engine = getattr(bind, "engine", None)
    if engine is not None:
        engine_url = getattr(engine, "url", None)
        if engine_url is not None:
            return str(engine_url)

    return f"bind:{id(bind)}"


def _category_to_core(category: Category) -> PermissionCategory:
    return PermissionCategory(category.value)


def _min_level_for_category(category: Category) -> int:
    if category == Category.PLATFORM:
        return HierarchyLevel.PLATFORM.value
    if category in {Category.FIRM, Category.TEAM, Category.CLIENT, Category.RETURN, Category.DOCUMENT}:
        return HierarchyLevel.FIRM.value
    return HierarchyLevel.CLIENT.value


def _tier_restriction_for_category(category: Category) -> list[str]:
    if category == Category.PLATFORM:
        return ["enterprise"]
    if category in {Category.FIRM, Category.TEAM, Category.CLIENT, Category.RETURN, Category.DOCUMENT}:
        return ["professional", "enterprise"]
    return ["starter", "professional", "enterprise"]


def _normalize_tier(value: Optional[str]) -> str:
    tier = (value or "starter").strip().lower()
    if tier not in _TIER_RANK:
        return "starter"
    return tier


def _tier_allows_permission(subscription_tier: str, permission: Permission) -> bool:
    required = permission.tier_restriction or ["starter", "professional", "enterprise"]
    rank = _TIER_RANK[_normalize_tier(subscription_tier)]
    required_ranks = [_TIER_RANK.get(_normalize_tier(tier), 0) for tier in required]
    return rank >= min(required_ranks)


class PermissionService:
    """DB-backed permission service."""

    def __init__(self, db):
        self.db = db

    async def get_all_permissions(
        self,
        category: Optional[PermissionCategory] = None,
        enabled_only: bool = True,
    ) -> list[Permission]:
        await _ensure_schema(self.db)
        stmt = select(Permission)
        if category is not None:
            stmt = stmt.where(Permission.category == category.value)
        if enabled_only:
            stmt = stmt.where(Permission.is_enabled.is_(True))
        stmt = stmt.order_by(Permission.code)
        result = await _exec(self.db, stmt)
        return list(result.scalars().all())

    async def get_permission_by_code(self, code: str) -> Optional[Permission]:
        await _ensure_schema(self.db)
        stmt = select(Permission).where(Permission.code == code)
        result = await _exec(self.db, stmt)
        return result.scalar_one_or_none()

    async def seed_system_permissions(self) -> int:
        await _ensure_schema(self.db)
        created_or_updated = 0
        for permission_enum, info in PERMISSIONS.items():
            stmt = select(Permission).where(Permission.code == permission_enum.value)
            existing_result = await _exec(self.db, stmt)
            permission = existing_result.scalar_one_or_none()

            if permission is None:
                permission = Permission(code=permission_enum.value)
                self.db.add(permission)

            permission.name = info.name
            permission.description = info.description
            permission.category = _category_to_core(info.category).value
            permission.min_hierarchy_level = _min_level_for_category(info.category)
            permission.tier_restriction = _tier_restriction_for_category(info.category)
            permission.is_enabled = True
            permission.is_system = True
            permission.updated_at = datetime.utcnow()
            created_or_updated += 1

        await _commit(self.db)
        return created_or_updated

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
    ) -> ServiceResult:
        await _ensure_schema(self.db)
        permission = await self.get_permission_by_code(permission_code)
        if not permission:
            return ServiceResult(
                success=False,
                message="Unknown permission",
                errors=[f"Unknown permission: {permission_code}"],
            )

        stmt = select(UserPermissionOverride).where(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.permission_id == permission.permission_id,
            UserPermissionOverride.resource_type == resource_type,
            UserPermissionOverride.resource_id == resource_id,
        )
        existing_result = await _exec(self.db, stmt)
        override = existing_result.scalar_one_or_none()

        if override is None:
            override = UserPermissionOverride(
                user_id=user_id,
                permission_id=permission.permission_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            self.db.add(override)

        override.action = action.value if hasattr(action, "value") else str(action)
        override.expires_at = expires_at
        override.reason = reason
        override.created_by = created_by
        override.created_at = datetime.utcnow()

        await _commit(self.db)
        return ServiceResult(
            success=True,
            message=f"Permission {override.action}ed for user",
            override_id=override.override_id,
        )


class RoleService:
    """DB-backed role service."""

    def __init__(self, db):
        self.db = db

    async def list_roles(
        self,
        *,
        firm_id: Optional[UUID],
        include_system: bool,
        active_only: bool,
    ) -> list[RoleTemplate]:
        await _ensure_schema(self.db)
        stmt = (
            select(RoleTemplate)
            .options(
                selectinload(RoleTemplate.role_permissions).selectinload(RolePermission.permission),
            )
        )

        conditions = []
        if active_only:
            conditions.append(RoleTemplate.is_active.is_(True))

        if firm_id is not None:
            if include_system:
                conditions.append(or_(RoleTemplate.is_system.is_(True), RoleTemplate.firm_id == firm_id))
            else:
                conditions.append(RoleTemplate.firm_id == firm_id)
        elif not include_system:
            conditions.append(RoleTemplate.is_system.is_(False))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(
            RoleTemplate.hierarchy_level.asc(),
            RoleTemplate.display_order.asc(),
            RoleTemplate.code.asc(),
        )
        result = await _exec(self.db, stmt)
        return list(result.scalars().all())

    async def create_custom_role(
        self,
        *,
        code: str,
        name: str,
        description: Optional[str],
        permission_codes: list[str],
        firm_id: Optional[UUID],
        subscription_tier: str,
        created_by: UUID,
        parent_role_code: Optional[str],
    ) -> ServiceResult:
        await _ensure_schema(self.db)
        if not firm_id:
            return ServiceResult(
                success=False,
                message="Firm context required",
                errors=["Custom roles must be scoped to a firm"],
            )

        existing_stmt = select(RoleTemplate).where(
            RoleTemplate.code == code,
            RoleTemplate.firm_id == firm_id,
            RoleTemplate.partner_id.is_(None),
        )
        existing_result = await _exec(self.db, existing_stmt)
        if existing_result.scalar_one_or_none():
            return ServiceResult(
                success=False,
                message="Role code already exists",
                errors=[f"Role code '{code}' already exists in this firm"],
            )

        perms_stmt = select(Permission).where(Permission.code.in_(permission_codes))
        perms_result = await _exec(self.db, perms_stmt)
        permissions = list(perms_result.scalars().all())
        permission_map = {permission.code: permission for permission in permissions}

        missing = [code for code in permission_codes if code not in permission_map]
        if missing:
            return ServiceResult(
                success=False,
                message="Invalid permissions",
                errors=[f"Unknown permissions: {', '.join(sorted(missing))}"],
            )

        disallowed = [
            permission.code
            for permission in permissions
            if not _tier_allows_permission(_normalize_tier(subscription_tier), permission)
        ]
        if disallowed:
            return ServiceResult(
                success=False,
                message="Permissions not available in subscription tier",
                errors=[f"Tier disallows permissions: {', '.join(sorted(disallowed))}"],
            )

        parent_role_id = None
        if parent_role_code:
            parent_stmt = select(RoleTemplate).where(
                RoleTemplate.code == parent_role_code,
                or_(RoleTemplate.firm_id == firm_id, RoleTemplate.is_system.is_(True)),
            )
            parent_result = await _exec(self.db, parent_stmt)
            parent = parent_result.scalar_one_or_none()
            if parent:
                parent_role_id = parent.role_id

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
            display_order=100,
            created_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(role)
        await _maybe_await(self.db.flush())

        for permission in permissions:
            self.db.add(
                RolePermission(
                    role_id=role.role_id,
                    permission_id=permission.permission_id,
                    granted_by=created_by,
                    granted_at=datetime.utcnow(),
                )
            )

        await _commit(self.db)
        return ServiceResult(
            success=True,
            message="Role created",
            role_id=role.role_id,
        )

    async def get_role_by_id(self, role_id: UUID) -> Optional[RoleTemplate]:
        await _ensure_schema(self.db)
        stmt = (
            select(RoleTemplate)
            .where(RoleTemplate.role_id == role_id)
            .options(
                selectinload(RoleTemplate.role_permissions).selectinload(RolePermission.permission),
            )
        )
        result = await _exec(self.db, stmt)
        return result.scalar_one_or_none()

    async def update_role_permissions(
        self,
        *,
        role_id: UUID,
        permission_codes: list[str],
        updated_by: UUID,
        firm_id: Optional[UUID],
        subscription_tier: str,
    ) -> ServiceResult:
        await _ensure_schema(self.db)
        role = await self.get_role_by_id(role_id)
        if not role:
            return ServiceResult(
                success=False,
                message="Role not found",
                errors=["Role does not exist"],
            )
        if role.is_system:
            return ServiceResult(
                success=False,
                message="System role cannot be modified",
                errors=["Only custom roles can be updated"],
            )
        if firm_id and role.firm_id and role.firm_id != firm_id:
            return ServiceResult(
                success=False,
                message="Access denied",
                errors=["Cannot modify role from another firm"],
            )

        perms_stmt = select(Permission).where(Permission.code.in_(permission_codes))
        perms_result = await _exec(self.db, perms_stmt)
        permissions = list(perms_result.scalars().all())
        permission_map = {permission.code: permission for permission in permissions}
        missing = [code for code in permission_codes if code not in permission_map]
        if missing:
            return ServiceResult(
                success=False,
                message="Invalid permissions",
                errors=[f"Unknown permissions: {', '.join(sorted(missing))}"],
            )

        disallowed = [
            permission.code
            for permission in permissions
            if not _tier_allows_permission(_normalize_tier(subscription_tier), permission)
        ]
        if disallowed:
            return ServiceResult(
                success=False,
                message="Permissions not available in subscription tier",
                errors=[f"Tier disallows permissions: {', '.join(sorted(disallowed))}"],
            )

        await _exec(self.db, delete(RolePermission).where(RolePermission.role_id == role_id))
        for permission in permissions:
            self.db.add(
                RolePermission(
                    role_id=role_id,
                    permission_id=permission.permission_id,
                    granted_by=updated_by,
                    granted_at=datetime.utcnow(),
                )
            )
        role.updated_at = datetime.utcnow()
        await _commit(self.db)
        return ServiceResult(success=True, message="Role permissions updated")

    async def delete_role(
        self,
        *,
        role_id: UUID,
        deleted_by: UUID,
        firm_id: Optional[UUID],
    ) -> ServiceResult:
        await _ensure_schema(self.db)
        _ = deleted_by
        role = await self.get_role_by_id(role_id)
        if not role:
            return ServiceResult(
                success=False,
                message="Role not found",
                errors=["Role does not exist"],
            )
        if role.is_system:
            return ServiceResult(
                success=False,
                message="System role cannot be deleted",
                errors=["Only custom roles can be deleted"],
            )
        if firm_id and role.firm_id and role.firm_id != firm_id:
            return ServiceResult(
                success=False,
                message="Access denied",
                errors=["Cannot delete role from another firm"],
            )

        assignment_count_stmt = (
            select(func.count())
            .select_from(UserRoleAssignment)
            .where(UserRoleAssignment.role_id == role_id)
        )
        assignment_count_result = await _exec(self.db, assignment_count_stmt)
        assignment_count = assignment_count_result.scalar() or 0
        if assignment_count > 0:
            return ServiceResult(
                success=False,
                message="Role is in use",
                errors=["Role has active user assignments"],
            )

        await _exec(self.db, delete(RolePermission).where(RolePermission.role_id == role_id))
        await _exec(self.db, delete(RoleTemplate).where(RoleTemplate.role_id == role_id))
        await _commit(self.db)
        return ServiceResult(success=True, message="Role deleted")

    async def get_user_roles(self, user_id: UUID) -> list[UserRoleAssignment]:
        await _ensure_schema(self.db)
        stmt = (
            select(UserRoleAssignment)
            .where(UserRoleAssignment.user_id == user_id)
            .options(selectinload(UserRoleAssignment.role))
            .order_by(UserRoleAssignment.assigned_at.desc())
        )
        result = await _exec(self.db, stmt)
        return list(result.scalars().all())

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
    ) -> ServiceResult:
        await _ensure_schema(self.db)
        role = await self.get_role_by_id(role_id)
        if not role:
            return ServiceResult(
                success=False,
                message="Role not found",
                errors=["Invalid role_id"],
            )

        if role.hierarchy_level < assigner_hierarchy_level:
            return ServiceResult(
                success=False,
                message="Hierarchy violation",
                errors=["Cannot assign role above your hierarchy level"],
            )

        if is_primary:
            existing_primary_stmt = select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.is_primary.is_(True),
            )
            existing_primary_result = await _exec(self.db, existing_primary_stmt)
            for assignment in existing_primary_result.scalars().all():
                assignment.is_primary = False

        existing_stmt = select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id,
        )
        existing_result = await _exec(self.db, existing_stmt)
        assignment = existing_result.scalar_one_or_none()

        if assignment is None:
            assignment = UserRoleAssignment(
                user_id=user_id,
                role_id=role_id,
            )
            self.db.add(assignment)

        assignment.is_primary = is_primary
        assignment.assigned_by = assigned_by
        assignment.assigned_at = datetime.utcnow()
        assignment.expires_at = expires_at
        assignment.notes = notes

        await _commit(self.db)
        return ServiceResult(success=True, message="Role assigned")

    async def remove_role(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        removed_by: UUID,
    ) -> ServiceResult:
        await _ensure_schema(self.db)
        _ = removed_by
        stmt = select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id,
        )
        result = await _exec(self.db, stmt)
        assignment = result.scalar_one_or_none()
        if assignment is None:
            return ServiceResult(
                success=False,
                message="Role assignment not found",
                errors=["No matching assignment"],
            )

        await _maybe_await(self.db.delete(assignment))
        await _commit(self.db)
        return ServiceResult(success=True, message="Role removed")

    async def seed_system_roles(self) -> int:
        await _ensure_schema(self.db)
        perms_stmt = select(Permission)
        perms_result = await _exec(self.db, perms_stmt)
        permission_map = {permission.code: permission for permission in perms_result.scalars().all()}

        seeded_count = 0
        for role_enum, role_info in ROLES.items():
            role_stmt = select(RoleTemplate).where(
                RoleTemplate.code == role_enum.value,
                RoleTemplate.is_system.is_(True),
            )
            role_result = await _exec(self.db, role_stmt)
            role = role_result.scalar_one_or_none()

            if role is None:
                role = RoleTemplate(
                    code=role_enum.value,
                    name=role_info.name,
                    description=role_info.description,
                    hierarchy_level=role_info.level.value,
                    is_system=True,
                    is_active=True,
                    is_assignable=role_enum not in PLATFORM_ROLES,
                    display_order=10 + role_info.level.value,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                self.db.add(role)
                await _maybe_await(self.db.flush())
            else:
                role.name = role_info.name
                role.description = role_info.description
                role.hierarchy_level = role_info.level.value
                role.is_active = True
                role.is_assignable = role_enum not in PLATFORM_ROLES
                role.updated_at = datetime.utcnow()

            await _exec(self.db, delete(RolePermission).where(RolePermission.role_id == role.role_id))
            for permission_enum in ROLE_PERMISSIONS.get(role_enum, frozenset()):
                permission = permission_map.get(permission_enum.value)
                if not permission:
                    continue
                self.db.add(
                    RolePermission(
                        role_id=role.role_id,
                        permission_id=permission.permission_id,
                        granted_at=datetime.utcnow(),
                    )
                )

            seeded_count += 1

        await _commit(self.db)
        return seeded_count


def get_permission_service(db) -> PermissionService:
    """Get permission service."""
    return PermissionService(db)


def get_role_service(db) -> RoleService:
    """Get role service."""
    return RoleService(db)
