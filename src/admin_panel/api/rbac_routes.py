"""
RBAC Management API Routes - Role and permission administration.

Endpoints:
- GET/POST /api/v1/admin/rbac/roles - List/create roles
- GET/PUT/DELETE /api/v1/admin/rbac/roles/{role_id} - Role CRUD
- PUT /api/v1/admin/rbac/roles/{role_id}/permissions - Update role permissions
- GET /api/v1/admin/rbac/permissions - List available permissions
- GET/PUT /api/v1/admin/rbac/users/{user_id}/roles - User role management
- POST /api/v1/admin/rbac/users/{user_id}/permissions - Permission overrides
"""

from datetime import datetime
from typing import Optional, List, Set
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from core.rbac import (
    RBACContext,
    get_rbac_context,
    RequirePermission,
    RequireSubscriptionTier,
    require_firm_admin,
    require_platform_admin,
    PermissionService,
    RoleService,
    get_permission_service,
    get_role_service,
    PermissionCategory,
    HierarchyLevel,
    OverrideAction,
)
from database import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/rbac", tags=["RBAC Management"])


# =============================================================================
# SCHEMAS
# =============================================================================

class PermissionResponse(BaseModel):
    """Permission detail response."""
    permission_id: str
    code: str
    name: str
    description: Optional[str]
    category: str
    min_hierarchy_level: int
    tier_restriction: List[str]
    is_enabled: bool
    is_system: bool


class RoleResponse(BaseModel):
    """Role detail response."""
    role_id: str
    code: str
    name: str
    description: Optional[str]
    hierarchy_level: int
    firm_id: Optional[str]
    partner_id: Optional[str]
    parent_role_id: Optional[str]
    is_system: bool
    is_active: bool
    is_assignable: bool
    display_order: int
    permissions: List[str]  # Permission codes
    created_at: datetime


class CreateRoleRequest(BaseModel):
    """Request to create a custom role."""
    code: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    permission_codes: List[str] = Field(..., min_items=1)
    parent_role_code: Optional[str] = None


class UpdateRolePermissionsRequest(BaseModel):
    """Request to update role permissions."""
    permission_codes: List[str] = Field(..., min_items=0)


class UserRoleAssignmentResponse(BaseModel):
    """User role assignment detail."""
    role_id: str
    role_code: str
    role_name: str
    is_primary: bool
    assigned_at: datetime
    expires_at: Optional[datetime]


class AssignRoleRequest(BaseModel):
    """Request to assign a role to a user."""
    role_id: str
    is_primary: bool = False
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None


class PermissionOverrideRequest(BaseModel):
    """Request to create a permission override."""
    permission_code: str
    action: str = Field(..., pattern=r"^(grant|revoke)$")
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    reason: Optional[str] = None


class RoleListResponse(BaseModel):
    """Paginated role list response."""
    roles: List[RoleResponse]
    total: int
    has_more: bool


class PermissionListResponse(BaseModel):
    """Paginated permission list response."""
    permissions: List[PermissionResponse]
    total: int
    categories: List[str]


# =============================================================================
# PERMISSION ENDPOINTS
# =============================================================================

@router.get("/permissions", response_model=PermissionListResponse)
async def list_permissions(
    category: Optional[str] = Query(None, description="Filter by category"),
    ctx: RBACContext = Depends(get_rbac_context),
):
    """
    List all available permissions.

    Filtered by the user's subscription tier - only shows permissions
    available in their tier.
    """
    ctx.require_authenticated()

    async with get_async_session() as db:
        perm_service = get_permission_service(db)

        # Filter by category if specified
        cat = PermissionCategory(category) if category else None

        permissions = await perm_service.get_all_permissions(
            category=cat,
            enabled_only=True,
        )

        # Filter by tier
        tier = ctx.subscription_tier
        filtered = [
            p for p in permissions
            if tier in (p.tier_restriction or ["starter", "professional", "enterprise"])
        ]

        # Build response
        responses = [
            PermissionResponse(
                permission_id=str(p.permission_id),
                code=p.code,
                name=p.name,
                description=p.description,
                category=p.category.value if p.category else "unknown",
                min_hierarchy_level=p.min_hierarchy_level,
                tier_restriction=p.tier_restriction or [],
                is_enabled=p.is_enabled,
                is_system=p.is_system,
            )
            for p in filtered
        ]

        # Get unique categories
        categories = sorted(set(p.category for p in responses))

        return PermissionListResponse(
            permissions=responses,
            total=len(responses),
            categories=categories,
        )


# =============================================================================
# ROLE ENDPOINTS
# =============================================================================

@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    include_system: bool = Query(True, description="Include system roles"),
    active_only: bool = Query(True, description="Only active roles"),
    ctx: RBACContext = Depends(get_rbac_context),
):
    """
    List roles available to the user's firm.

    Firm admins see system roles and their custom roles.
    Platform admins see all roles.
    """
    ctx.require_authenticated()

    async with get_async_session() as db:
        role_service = get_role_service(db)

        # Determine scope
        firm_id = ctx.firm_id if not ctx.is_platform_admin else None

        roles = await role_service.list_roles(
            firm_id=firm_id,
            include_system=include_system,
            active_only=active_only,
        )

        responses = []
        for role in roles:
            # Get permission codes for this role
            perm_codes = [
                rp.permission.code
                for rp in role.role_permissions
                if rp.permission
            ]

            responses.append(RoleResponse(
                role_id=str(role.role_id),
                code=role.code,
                name=role.name,
                description=role.description,
                hierarchy_level=role.hierarchy_level,
                firm_id=str(role.firm_id) if role.firm_id else None,
                partner_id=str(role.partner_id) if role.partner_id else None,
                parent_role_id=str(role.parent_role_id) if role.parent_role_id else None,
                is_system=role.is_system,
                is_active=role.is_active,
                is_assignable=role.is_assignable,
                display_order=role.display_order,
                permissions=perm_codes,
                created_at=role.created_at,
            ))

        return RoleListResponse(
            roles=responses,
            total=len(responses),
            has_more=False,
        )


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    request: CreateRoleRequest,
    ctx: RBACContext = Depends(require_firm_admin),
    _tier: None = Depends(RequireSubscriptionTier("professional")),
    _perm: None = Depends(RequirePermission("manage_custom_roles")),
):
    """
    Create a custom role.

    Requires:
    - Firm admin role
    - Professional or Enterprise subscription tier
    - manage_custom_roles permission
    """
    async with get_async_session() as db:
        role_service = get_role_service(db)

        result = await role_service.create_custom_role(
            code=request.code,
            name=request.name,
            description=request.description,
            permission_codes=request.permission_codes,
            firm_id=ctx.firm_id,
            subscription_tier=ctx.subscription_tier,
            created_by=ctx.user_id,
            parent_role_code=request.parent_role_code,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": result.message,
                    "errors": result.errors,
                },
            )

        # Fetch created role
        role = await role_service.get_role_by_id(result.role_id)
        perm_codes = [
            rp.permission.code
            for rp in role.role_permissions
            if rp.permission
        ]

        return RoleResponse(
            role_id=str(role.role_id),
            code=role.code,
            name=role.name,
            description=role.description,
            hierarchy_level=role.hierarchy_level,
            firm_id=str(role.firm_id) if role.firm_id else None,
            partner_id=str(role.partner_id) if role.partner_id else None,
            parent_role_id=str(role.parent_role_id) if role.parent_role_id else None,
            is_system=role.is_system,
            is_active=role.is_active,
            is_assignable=role.is_assignable,
            display_order=role.display_order,
            permissions=perm_codes,
            created_at=role.created_at,
        )


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    ctx: RBACContext = Depends(get_rbac_context),
):
    """Get role details by ID."""
    ctx.require_authenticated()

    async with get_async_session() as db:
        role_service = get_role_service(db)
        role = await role_service.get_role_by_id(role_id)

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )

        # Check access
        if not ctx.is_platform_admin:
            if role.firm_id and role.firm_id != ctx.firm_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this role",
                )

        perm_codes = [
            rp.permission.code
            for rp in role.role_permissions
            if rp.permission
        ]

        return RoleResponse(
            role_id=str(role.role_id),
            code=role.code,
            name=role.name,
            description=role.description,
            hierarchy_level=role.hierarchy_level,
            firm_id=str(role.firm_id) if role.firm_id else None,
            partner_id=str(role.partner_id) if role.partner_id else None,
            parent_role_id=str(role.parent_role_id) if role.parent_role_id else None,
            is_system=role.is_system,
            is_active=role.is_active,
            is_assignable=role.is_assignable,
            display_order=role.display_order,
            permissions=perm_codes,
            created_at=role.created_at,
        )


@router.put("/roles/{role_id}/permissions", response_model=RoleResponse)
async def update_role_permissions(
    role_id: UUID,
    request: UpdateRolePermissionsRequest,
    ctx: RBACContext = Depends(require_firm_admin),
    _perm: None = Depends(RequirePermission("manage_custom_roles")),
):
    """
    Update permissions for a custom role.

    System roles cannot be modified.
    """
    async with get_async_session() as db:
        role_service = get_role_service(db)

        result = await role_service.update_role_permissions(
            role_id=role_id,
            permission_codes=request.permission_codes,
            updated_by=ctx.user_id,
            firm_id=ctx.firm_id,
            subscription_tier=ctx.subscription_tier,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": result.message,
                    "errors": result.errors,
                },
            )

        # Fetch updated role
        role = await role_service.get_role_by_id(role_id)
        perm_codes = [
            rp.permission.code
            for rp in role.role_permissions
            if rp.permission
        ]

        return RoleResponse(
            role_id=str(role.role_id),
            code=role.code,
            name=role.name,
            description=role.description,
            hierarchy_level=role.hierarchy_level,
            firm_id=str(role.firm_id) if role.firm_id else None,
            partner_id=str(role.partner_id) if role.partner_id else None,
            parent_role_id=str(role.parent_role_id) if role.parent_role_id else None,
            is_system=role.is_system,
            is_active=role.is_active,
            is_assignable=role.is_assignable,
            display_order=role.display_order,
            permissions=perm_codes,
            created_at=role.created_at,
        )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    ctx: RBACContext = Depends(require_firm_admin),
    _perm: None = Depends(RequirePermission("manage_custom_roles")),
):
    """
    Delete a custom role.

    System roles cannot be deleted.
    Role must not be assigned to any users.
    """
    async with get_async_session() as db:
        role_service = get_role_service(db)

        result = await role_service.delete_role(
            role_id=role_id,
            deleted_by=ctx.user_id,
            firm_id=ctx.firm_id,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": result.message,
                    "errors": result.errors,
                },
            )


# =============================================================================
# USER ROLE ASSIGNMENT ENDPOINTS
# =============================================================================

@router.get("/users/{user_id}/roles", response_model=List[UserRoleAssignmentResponse])
async def get_user_roles(
    user_id: UUID,
    ctx: RBACContext = Depends(get_rbac_context),
    _perm: None = Depends(RequirePermission("view_team_performance")),
):
    """
    Get roles assigned to a user.

    Requires view_team_performance permission.
    """
    # Verify user is in same firm (unless platform admin)
    if not ctx.is_platform_admin:
        # Would need to verify user belongs to ctx.firm_id
        pass

    async with get_async_session() as db:
        role_service = get_role_service(db)
        assignments = await role_service.get_user_roles(user_id)

        return [
            UserRoleAssignmentResponse(
                role_id=str(a.role_id),
                role_code=a.role.code,
                role_name=a.role.name,
                is_primary=a.is_primary,
                assigned_at=a.assigned_at,
                expires_at=a.expires_at,
            )
            for a in assignments
        ]


@router.put("/users/{user_id}/roles")
async def assign_user_role(
    user_id: UUID,
    request: AssignRoleRequest,
    ctx: RBACContext = Depends(require_firm_admin),
    _perm: None = Depends(RequirePermission("assign_roles")),
):
    """
    Assign a role to a user.

    Requires:
    - Firm admin role
    - assign_roles permission
    - Cannot assign role with higher hierarchy level than assigner
    """
    async with get_async_session() as db:
        role_service = get_role_service(db)

        result = await role_service.assign_role(
            user_id=user_id,
            role_id=UUID(request.role_id),
            assigned_by=ctx.user_id,
            assigner_hierarchy_level=ctx.hierarchy_level,
            is_primary=request.is_primary,
            expires_at=request.expires_at,
            notes=request.notes,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": result.message,
                    "errors": result.errors,
                },
            )

        return {"success": True, "message": result.message}


@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_user_role(
    user_id: UUID,
    role_id: UUID,
    ctx: RBACContext = Depends(require_firm_admin),
    _perm: None = Depends(RequirePermission("assign_roles")),
):
    """Remove a role from a user."""
    async with get_async_session() as db:
        role_service = get_role_service(db)

        result = await role_service.remove_role(
            user_id=user_id,
            role_id=role_id,
            removed_by=ctx.user_id,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.message,
            )

        return {"success": True, "message": result.message}


# =============================================================================
# USER PERMISSION OVERRIDE ENDPOINTS
# =============================================================================

@router.post("/users/{user_id}/permissions")
async def create_permission_override(
    user_id: UUID,
    request: PermissionOverrideRequest,
    ctx: RBACContext = Depends(require_firm_admin),
    _perm: None = Depends(RequirePermission("assign_roles")),
):
    """
    Create a permission override for a user.

    Allows granting or revoking specific permissions beyond their role defaults.
    """
    from core.rbac.models import UserPermissionOverride

    async with get_async_session() as db:
        perm_service = get_permission_service(db)

        # Validate permission exists
        permission = await perm_service.get_permission_by_code(request.permission_code)
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown permission: {request.permission_code}",
            )

        # Validate permission is available in tier
        if ctx.subscription_tier not in (permission.tier_restriction or []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission not available in {ctx.subscription_tier} tier",
            )

        # Create override
        override = UserPermissionOverride(
            user_id=user_id,
            permission_id=permission.permission_id,
            action=OverrideAction(request.action),
            resource_type=request.resource_type,
            resource_id=UUID(request.resource_id) if request.resource_id else None,
            expires_at=request.expires_at,
            reason=request.reason,
            created_by=ctx.user_id,
        )
        db.add(override)
        db.commit()

        # Invalidate user's permission cache
        from core.rbac import get_permission_cache
        cache = get_permission_cache()
        cache.invalidate_user(user_id)

        return {
            "success": True,
            "message": f"Permission {request.action}ed for user",
            "override_id": str(override.override_id),
        }


# =============================================================================
# ADMIN SEEDING ENDPOINT (Platform Admin Only)
# =============================================================================

@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_rbac_data(
    ctx: RBACContext = Depends(require_platform_admin),
):
    """
    Seed system permissions and roles.

    Platform admin only. Used for initial setup or updates.
    """
    async with get_async_session() as db:
        perm_service = get_permission_service(db)
        role_service = get_role_service(db)

        perm_count = await perm_service.seed_system_permissions()
        role_count = await role_service.seed_system_roles()

        return {
            "success": True,
            "permissions_seeded": perm_count,
            "roles_seeded": role_count,
        }
