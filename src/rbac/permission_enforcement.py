"""
Permission Enforcement System

Decorators and utilities for enforcing permissions in API endpoints and UI.
Crystal-clear enforcement with helpful error messages.
"""

from fastapi import HTTPException, Depends, Request
from functools import wraps
from typing import Callable, Optional, Set
import inspect

from .enhanced_permissions import (
    Permission,
    Permissions,
    get_permissions_for_role,
    has_permission
)
from .dependencies import require_auth, AuthContext
from database.tenant_persistence import get_tenant_persistence


class PermissionDeniedError(HTTPException):
    """Custom exception for permission denials with clear messages"""

    def __init__(
        self,
        required_permission: Permission,
        reason: str = None,
        upgrade_tier: str = None
    ):
        detail = {
            "error": "Permission Denied",
            "required_permission": {
                "code": required_permission.code,
                "name": required_permission.name,
                "description": required_permission.description,
            },
            "reason": reason or "You do not have permission to perform this action",
        }

        if upgrade_tier:
            detail["upgrade_hint"] = f"Upgrade to {upgrade_tier} tier to access this feature"

        super().__init__(status_code=403, detail=detail)


def require_permission(*required_permissions: Permission):
    """
    Decorator to require specific permissions for an endpoint.

    Usage:
        @require_permission(Permissions.CPA_CLIENTS_VIEW)
        async def get_clients(...):
            ...

    Multiple permissions (all required):
        @require_permission(
            Permissions.CPA_RETURNS_VIEW,
            Permissions.CPA_RETURNS_EDIT
        )
        async def edit_return(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get auth context from kwargs
            ctx: Optional[AuthContext] = kwargs.get('ctx')

            if not ctx:
                # Try to get from args if not in kwargs
                for arg in args:
                    if isinstance(arg, AuthContext):
                        ctx = arg
                        break

            if not ctx:
                raise HTTPException(401, "Authentication required")

            # Get user's permissions
            user_permissions = get_permissions_for_role(ctx.role.name)

            # Check each required permission
            for perm in required_permissions:
                # Check basic permission
                if perm not in user_permissions:
                    # Check if it's a tenant feature that's disabled
                    if perm.code.startswith('feature.'):
                        feature_check = _check_tenant_feature(ctx, perm)
                        if not feature_check['allowed']:
                            raise PermissionDeniedError(
                                perm,
                                reason=feature_check['reason'],
                                upgrade_tier=feature_check.get('upgrade_tier')
                            )

                    raise PermissionDeniedError(
                        perm,
                        reason=f"Your role ({ctx.role.name}) does not have permission: {perm.name}"
                    )

                # Check ownership if required
                if perm.requires_ownership:
                    resource_id = kwargs.get('id') or kwargs.get('user_id') or kwargs.get('client_id')
                    if str(ctx.user_id) != str(resource_id):
                        raise PermissionDeniedError(
                            perm,
                            reason="You can only access your own resources"
                        )

                # Check assignment if required
                if perm.requires_assignment:
                    # TODO: Implement assignment check
                    pass

            # Call original function
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_permission(*required_permissions: Permission):
    """
    Decorator to require ANY ONE of the specified permissions.

    Usage:
        @require_any_permission(
            Permissions.PLATFORM_TENANT_VIEW_ALL,
            Permissions.TENANT_USERS_VIEW
        )
        async def view_users(...):
            # Can be accessed by platform admin OR tenant partner
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx: Optional[AuthContext] = kwargs.get('ctx')

            if not ctx:
                raise HTTPException(401, "Authentication required")

            user_permissions = get_permissions_for_role(ctx.role.name)

            # Check if user has ANY of the required permissions
            has_any = False
            for perm in required_permissions:
                if perm in user_permissions:
                    has_any = True
                    break

            if not has_any:
                perm_names = [p.name for p in required_permissions]
                raise PermissionDeniedError(
                    required_permissions[0],  # Show first permission
                    reason=f"Requires one of: {', '.join(perm_names)}"
                )

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper
    return decorator


def require_tenant_feature(feature_name: str):
    """
    Decorator to check if tenant has a specific feature enabled.

    Usage:
        @require_tenant_feature('ai_chat_enabled')
        async def ai_chat(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx: Optional[AuthContext] = kwargs.get('ctx')

            if not ctx:
                raise HTTPException(401, "Authentication required")

            if not ctx.tenant_id:
                raise HTTPException(400, "Tenant required for this feature")

            # Get tenant
            persistence = get_tenant_persistence()
            tenant = persistence.get_tenant(ctx.tenant_id)

            if not tenant:
                raise HTTPException(404, "Tenant not found")

            # Check if feature is enabled
            feature_value = getattr(tenant.features, feature_name, False)

            if not feature_value:
                # Determine which tier enables this feature
                tier_info = _get_feature_tier_info(feature_name)

                raise HTTPException(
                    403,
                    detail={
                        "error": "Feature Not Enabled",
                        "feature": feature_name,
                        "current_tier": tenant.subscription_tier.value,
                        "required_tier": tier_info['required_tier'],
                        "message": f"Upgrade to {tier_info['required_tier']} to access this feature"
                    }
                )

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper
    return decorator


def check_resource_ownership(ctx: AuthContext, resource_owner_id: str) -> bool:
    """Check if user owns a resource"""
    return str(ctx.user_id) == str(resource_owner_id)


def check_cpa_assignment(ctx: AuthContext, assigned_cpa_id: str) -> bool:
    """Check if user is the assigned CPA"""
    return str(ctx.user_id) == str(assigned_cpa_id)


def check_tenant_membership(ctx: AuthContext, tenant_id: str) -> bool:
    """Check if user belongs to a tenant"""
    return ctx.tenant_id == tenant_id


def _check_tenant_feature(ctx: AuthContext, permission: Permission) -> dict:
    """
    Check if tenant has the feature enabled for a feature permission.

    Returns dict with:
        - allowed: bool
        - reason: str
        - upgrade_tier: str (optional)
    """
    if not ctx.tenant_id:
        return {
            'allowed': False,
            'reason': 'Tenant required for this feature'
        }

    # Get tenant
    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(ctx.tenant_id)

    if not tenant:
        return {
            'allowed': False,
            'reason': 'Tenant not found'
        }

    # Map permission to feature flag
    feature_map = {
        'feature.express_lane.use': 'express_lane_enabled',
        'feature.smart_tax.use': 'smart_tax_enabled',
        'feature.ai_chat.use': 'ai_chat_enabled',
        'feature.scenarios.use': 'scenario_explorer_enabled',
        'feature.projections.use': 'tax_projections_enabled',
        'feature.integrations.configure': 'quickbooks_integration',
        'feature.api.use': 'api_access_enabled',
    }

    feature_name = feature_map.get(permission.code)

    if not feature_name:
        return {'allowed': True}  # Not a feature permission

    feature_enabled = getattr(tenant.features, feature_name, False)

    if not feature_enabled:
        tier_info = _get_feature_tier_info(feature_name)
        return {
            'allowed': False,
            'reason': f'Feature not enabled for {tenant.subscription_tier.value} tier',
            'upgrade_tier': tier_info['required_tier']
        }

    return {'allowed': True}


def _get_feature_tier_info(feature_name: str) -> dict:
    """Get minimum tier required for a feature"""
    tier_requirements = {
        'express_lane_enabled': {'required_tier': 'free', 'tier_level': 0},
        'smart_tax_enabled': {'required_tier': 'starter', 'tier_level': 1},
        'ai_chat_enabled': {'required_tier': 'professional', 'tier_level': 2},
        'scenario_explorer_enabled': {'required_tier': 'starter', 'tier_level': 1},
        'tax_projections_enabled': {'required_tier': 'starter', 'tier_level': 1},
        'quickbooks_integration': {'required_tier': 'professional', 'tier_level': 2},
        'custom_domain_enabled': {'required_tier': 'enterprise', 'tier_level': 3},
        'api_access_enabled': {'required_tier': 'enterprise', 'tier_level': 3},
        'remove_branding': {'required_tier': 'white_label', 'tier_level': 4},
    }

    return tier_requirements.get(feature_name, {'required_tier': 'professional', 'tier_level': 2})


# =============================================================================
# PERMISSION UTILITIES
# =============================================================================

def get_user_permissions_list(ctx: AuthContext) -> list:
    """Get list of permission codes for a user"""
    permissions = get_permissions_for_role(ctx.role.name)
    return [p.code for p in permissions]


def can_user_access_resource(
    ctx: AuthContext,
    permission: Permission,
    resource_owner_id: str = None,
    assigned_cpa_id: str = None
) -> bool:
    """Check if user can access a specific resource"""
    user_permissions = get_permissions_for_role(ctx.role.name)

    return has_permission(
        user_permissions,
        permission,
        user_id=str(ctx.user_id),
        resource_owner_id=resource_owner_id,
        assigned_cpa_id=assigned_cpa_id
    )


def get_accessible_resources(
    ctx: AuthContext,
    resource_type: str,
    all_resources: list
) -> list:
    """
    Filter resources based on user permissions.

    Returns only resources the user can access.
    """
    user_permissions = get_permissions_for_role(ctx.role.name)

    accessible = []

    for resource in all_resources:
        # Platform admins see all
        if ctx.role.name == 'PLATFORM_ADMIN':
            accessible.append(resource)
            continue

        # Check tenant membership
        if hasattr(resource, 'tenant_id'):
            if resource.tenant_id != ctx.tenant_id:
                continue

        # Check ownership
        if hasattr(resource, 'owner_id') or hasattr(resource, 'user_id'):
            owner_id = getattr(resource, 'owner_id', None) or getattr(resource, 'user_id', None)
            if owner_id == str(ctx.user_id):
                accessible.append(resource)
                continue

        # Check assignment (for CPAs)
        if hasattr(resource, 'assigned_cpa_id'):
            if resource.assigned_cpa_id == str(ctx.user_id):
                accessible.append(resource)
                continue

    return accessible


# =============================================================================
# PERMISSION MATRIX GENERATOR (for documentation)
# =============================================================================

def generate_permission_matrix() -> dict:
    """
    Generate a permission matrix showing what each role can do.

    Returns a nested dict structure for documentation.
    """
    from .roles import Role

    matrix = {}

    roles = ['PLATFORM_ADMIN', 'PARTNER', 'STAFF', 'FIRM_CLIENT', 'DIRECT_CLIENT']

    for role_name in roles:
        permissions = get_permissions_for_role(role_name)

        # Group by resource type
        grouped = {}

        for perm in permissions:
            resource = perm.resource.value

            if resource not in grouped:
                grouped[resource] = []

            grouped[resource].append({
                'code': perm.code,
                'name': perm.name,
                'action': perm.action.value,
                'requires_ownership': perm.requires_ownership,
                'requires_assignment': perm.requires_assignment,
            })

        matrix[role_name] = grouped

    return matrix


def get_permission_comparison(role1: str, role2: str) -> dict:
    """Compare permissions between two roles"""
    perms1 = get_permissions_for_role(role1)
    perms2 = get_permissions_for_role(role2)

    return {
        'role1': role1,
        'role2': role2,
        'role1_only': [p.code for p in perms1 - perms2],
        'role2_only': [p.code for p in perms2 - perms1],
        'shared': [p.code for p in perms1 & perms2],
    }
