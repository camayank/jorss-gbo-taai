"""
Admin User Management API

Platform admin endpoints for managing users, roles, and permissions.
Provides complete control over user access and security.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from ..rbac.dependencies import require_auth, AuthContext
from ..rbac.enhanced_permissions import Permissions, get_permissions_for_role, Permission
from ..rbac.permission_enforcement import require_permission
from ..rbac.roles import Role
from ..audit.audit_logger import (
    get_audit_logger,
    AuditEventType,
    AuditSeverity,
    audit_permission_change
)
from ..database.async_engine import get_db_connection

router = APIRouter(prefix="/api/admin/users", tags=["admin-user-management"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class UserListItem(BaseModel):
    """User summary for list view"""
    user_id: str
    email: str
    full_name: str
    role: str
    tenant_id: Optional[str]
    tenant_name: Optional[str]
    status: UserStatus
    created_at: str
    last_login: Optional[str]
    is_verified: bool


class UserDetailResponse(BaseModel):
    """Complete user details"""
    user_id: str
    email: str
    full_name: str
    role: str
    tenant_id: Optional[str]
    tenant_name: Optional[str]
    status: UserStatus
    created_at: str
    updated_at: str
    last_login: Optional[str]
    is_verified: bool

    # Permission info
    permissions: List[str]  # List of permission codes
    permission_overrides: Optional[Dict[str, bool]]  # Custom grants/revokes

    # Activity summary
    total_returns: int
    recent_activity_count: int
    failed_login_attempts: int


class UpdateUserRoleRequest(BaseModel):
    """Request to change user's role"""
    new_role: str = Field(..., description="New role name (PLATFORM_ADMIN, PARTNER, etc.)")
    reason: str = Field(..., description="Reason for role change (for audit log)")


class PermissionOverride(BaseModel):
    """Override specific permission for a user"""
    permission_code: str
    granted: bool  # True = grant, False = revoke
    reason: str


class UpdateUserStatusRequest(BaseModel):
    """Update user account status"""
    status: UserStatus
    reason: str


class UserFilters(BaseModel):
    """Filters for user list"""
    role: Optional[str] = None
    tenant_id: Optional[str] = None
    status: Optional[UserStatus] = None
    search: Optional[str] = None  # Search email or name


class UserListResponse(BaseModel):
    """Paginated user list"""
    users: List[UserListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserActivityLogEntry(BaseModel):
    """User activity log entry"""
    event_id: str
    event_type: str
    action: str
    timestamp: str
    resource_type: str
    resource_id: Optional[str]
    success: bool
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]


class UserActivityLogResponse(BaseModel):
    """User activity log"""
    user_id: str
    entries: List[UserActivityLogEntry]
    total: int


# =============================================================================
# USER MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/", response_model=UserListResponse)
@require_permission(Permissions.PLATFORM_USERS_VIEW_ALL)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    role: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    ctx: AuthContext = Depends(require_auth)
):
    """
    List all users with filtering and pagination.

    Platform admins can see all users.
    Tenant partners can only see users in their tenant.
    """
    async with get_db_connection() as conn:
        cursor = await conn.cursor()

        # Build query with filters
        query = """
            SELECT
                u.user_id,
                u.email,
                u.full_name,
                u.role,
                u.tenant_id,
                t.tenant_name,
                u.status,
                u.created_at,
                u.last_login,
                u.is_verified
            FROM users u
            LEFT JOIN tenants t ON u.tenant_id = t.tenant_id
            WHERE 1=1
        """
        params = []

        # Apply filters
        if role:
            query += " AND u.role = ?"
            params.append(role)

        if tenant_id:
            query += " AND u.tenant_id = ?"
            params.append(tenant_id)
        elif ctx.role.name != 'PLATFORM_ADMIN':
            # Non-platform admins can only see their tenant
            query += " AND u.tenant_id = ?"
            params.append(ctx.tenant_id)

        if status:
            query += " AND u.status = ?"
            params.append(status)

        if search:
            query += " AND (u.email LIKE ? OR u.full_name LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])

        # Count total
        count_query = f"SELECT COUNT(*) FROM ({query}) AS filtered"
        cursor.execute(count_query, params)
        total = (await cursor.fetchone())[0]

        # Add pagination
        query += " ORDER BY u.created_at DESC LIMIT ? OFFSET ?"
        params.extend([page_size, (page - 1) * page_size])

        # Execute
        cursor.execute(query, params)
        rows = await cursor.fetchall()

        users = [
            UserListItem(
                user_id=row[0],
                email=row[1],
                full_name=row[2],
                role=row[3],
                tenant_id=row[4],
                tenant_name=row[5],
                status=UserStatus(row[6]),
                created_at=row[7],
                last_login=row[8],
                is_verified=bool(row[9])
            )
            for row in rows
        ]

        return UserListResponse(
            users=users,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size
        )


@router.get("/{user_id}", response_model=UserDetailResponse)
@require_permission(Permissions.PLATFORM_USERS_VIEW_ALL)
async def get_user_details(
    user_id: str,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Get complete details for a specific user.

    Includes role, permissions, activity summary, and security info.
    """
    async with get_db_connection() as conn:
        cursor = await conn.cursor()

        # Get user
        cursor.execute("""
            SELECT
                u.user_id,
                u.email,
                u.full_name,
                u.role,
                u.tenant_id,
                t.tenant_name,
                u.status,
                u.created_at,
                u.updated_at,
                u.last_login,
                u.is_verified,
                u.permission_overrides
            FROM users u
            LEFT JOIN tenants t ON u.tenant_id = t.tenant_id
            WHERE u.user_id = ?
        """, (user_id,))

        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "User not found")

        # Check tenant access for non-platform admins
        if ctx.role.name != 'PLATFORM_ADMIN' and row[4] != ctx.tenant_id:
            raise HTTPException(403, "Access denied to this user")

        # Get permissions for role
        permissions = get_permissions_for_role(row[3])
        permission_codes = [p.code for p in permissions]

        # Get permission overrides
        import json
        permission_overrides = json.loads(row[11]) if row[11] else None

        # Get activity stats
        cursor.execute("""
            SELECT COUNT(*) FROM tax_returns WHERE user_id = ?
        """, (user_id,))
        total_returns = (await cursor.fetchone())[0]

        # Get recent activity count (last 7 days)
        from datetime import timedelta
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        audit_logger = get_audit_logger()
        recent_activity = audit_logger.query(
            user_id=user_id,
            start_date=datetime.fromisoformat(week_ago)
        )

        # Get failed login attempts (last 24 hours)
        failed_logins = audit_logger.get_failed_logins(hours=24)
        user_failed_logins = [log for log in failed_logins if log.get('resource_id') == user_id]

        return UserDetailResponse(
            user_id=row[0],
            email=row[1],
            full_name=row[2],
            role=row[3],
            tenant_id=row[4],
            tenant_name=row[5],
            status=UserStatus(row[6]),
            created_at=row[7],
            updated_at=row[8],
            last_login=row[9],
            is_verified=bool(row[10]),
            permissions=permission_codes,
            permission_overrides=permission_overrides,
            total_returns=total_returns,
            recent_activity_count=len(recent_activity),
            failed_login_attempts=len(user_failed_logins)
        )


@router.patch("/{user_id}/role")
@require_permission(Permissions.PLATFORM_USERS_EDIT_ALL)
async def update_user_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Change a user's role.

    This affects all permissions derived from the role.
    Logs the change to audit log.
    """
    # Validate role
    try:
        new_role = Role[request.new_role]
    except KeyError:
        raise HTTPException(400, f"Invalid role: {request.new_role}")

    async with get_db_connection() as conn:
        cursor = await conn.cursor()

        # Get current user
        cursor.execute("SELECT role, email FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "User not found")

        old_role = row[0]
        user_email = row[1]

        if old_role == request.new_role:
            raise HTTPException(400, "User already has this role")

        # Update role
        cursor.execute("""
            UPDATE users
            SET role = ?, updated_at = ?
            WHERE user_id = ?
        """, (request.new_role, datetime.now().isoformat(), user_id))

        await conn.commit()

    # Audit log
    old_permissions = [p.code for p in get_permissions_for_role(old_role)]
    new_permissions = [p.code for p in get_permissions_for_role(request.new_role)]

    audit_permission_change(
        user_id=user_id,
        changed_by=str(ctx.user_id),
        role=ctx.role.name,
        action=f"Role changed from {old_role} to {request.new_role}",
        old_permissions=old_permissions,
        new_permissions=new_permissions
    )

    return {
        "success": True,
        "message": f"User {user_email} role changed from {old_role} to {request.new_role}",
        "old_role": old_role,
        "new_role": request.new_role
    }


@router.patch("/{user_id}/status")
@require_permission(Permissions.PLATFORM_USERS_EDIT_ALL)
async def update_user_status(
    user_id: str,
    request: UpdateUserStatusRequest,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Update user account status (active, suspended, etc.).

    Suspended users cannot log in.
    """
    async with get_db_connection() as conn:
        cursor = await conn.cursor()

        # Get current status
        cursor.execute("SELECT status, email FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "User not found")

        old_status = row[0]
        user_email = row[1]

        # Update status
        cursor.execute("""
            UPDATE users
            SET status = ?, updated_at = ?
            WHERE user_id = ?
        """, (request.status.value, datetime.now().isoformat(), user_id))

        await conn.commit()

    # Audit log
    audit_logger = get_audit_logger()
    audit_logger.log(
        event_type=AuditEventType.USER_UPDATE,
        action="status_change",
        resource_type="user",
        resource_id=user_id,
        user_id=str(ctx.user_id),
        user_role=ctx.role.name,
        old_value={"status": old_status},
        new_value={"status": request.status.value},
        details={"reason": request.reason},
        severity=AuditSeverity.WARNING if request.status == UserStatus.SUSPENDED else AuditSeverity.INFO
    )

    return {
        "success": True,
        "message": f"User {user_email} status changed to {request.status.value}",
        "old_status": old_status,
        "new_status": request.status.value
    }


@router.post("/{user_id}/permissions/override")
@require_permission(Permissions.PLATFORM_USERS_EDIT_ALL)
async def override_user_permission(
    user_id: str,
    request: PermissionOverride,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Grant or revoke a specific permission for a user.

    This overrides the default permissions from their role.
    Use sparingly - role changes are preferred.
    """
    # Validate permission
    from ..rbac.enhanced_permissions import ALL_PERMISSIONS
    perm = next((p for p in ALL_PERMISSIONS if p.code == request.permission_code), None)
    if not perm:
        raise HTTPException(400, f"Invalid permission code: {request.permission_code}")

    async with get_db_connection() as conn:
        cursor = await conn.cursor()

        # Get current overrides
        cursor.execute("SELECT permission_overrides FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "User not found")

        import json
        overrides = json.loads(row[0]) if row[0] else {}

        # Update override
        overrides[request.permission_code] = request.granted

        # Save
        cursor.execute("""
            UPDATE users
            SET permission_overrides = ?, updated_at = ?
            WHERE user_id = ?
        """, (json.dumps(overrides), datetime.now().isoformat(), user_id))

        await conn.commit()

    # Audit log
    audit_logger = get_audit_logger()
    audit_logger.log(
        event_type=AuditEventType.PERMISSION_GRANTED if request.granted else AuditEventType.PERMISSION_REVOKED,
        action="permission_override",
        resource_type="user_permissions",
        resource_id=user_id,
        user_id=str(ctx.user_id),
        user_role=ctx.role.name,
        details={
            "permission_code": request.permission_code,
            "permission_name": perm.name,
            "granted": request.granted,
            "reason": request.reason
        },
        severity=AuditSeverity.WARNING
    )

    return {
        "success": True,
        "message": f"Permission {perm.name} {'granted' if request.granted else 'revoked'}",
        "permission": perm.code,
        "granted": request.granted
    }


@router.delete("/{user_id}/permissions/override/{permission_code}")
@require_permission(Permissions.PLATFORM_USERS_EDIT_ALL)
async def remove_permission_override(
    user_id: str,
    permission_code: str,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Remove a permission override, reverting to role-based permission.
    """
    async with get_db_connection() as conn:
        cursor = await conn.cursor()

        # Get current overrides
        cursor.execute("SELECT permission_overrides FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "User not found")

        import json
        overrides = json.loads(row[0]) if row[0] else {}

        if permission_code not in overrides:
            raise HTTPException(404, "No override exists for this permission")

        # Remove override
        del overrides[permission_code]

        # Save
        cursor.execute("""
            UPDATE users
            SET permission_overrides = ?, updated_at = ?
            WHERE user_id = ?
        """, (json.dumps(overrides) if overrides else None, datetime.now().isoformat(), user_id))

        await conn.commit()

    return {
        "success": True,
        "message": f"Permission override removed for {permission_code}"
    }


@router.get("/{user_id}/activity", response_model=UserActivityLogResponse)
@require_permission(Permissions.PLATFORM_USERS_VIEW_ALL)
async def get_user_activity_log(
    user_id: str,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000),
    ctx: AuthContext = Depends(require_auth)
):
    """
    Get audit log for a specific user.

    Shows all actions performed by this user.
    """
    audit_logger = get_audit_logger()
    entries = audit_logger.get_user_activity(user_id, days=days)

    # Limit results
    entries = entries[:limit]

    activity_entries = [
        UserActivityLogEntry(
            event_id=entry['event_id'],
            event_type=entry['event_type'],
            action=entry['action'],
            timestamp=entry['timestamp'],
            resource_type=entry['resource_type'],
            resource_id=entry['resource_id'],
            success=entry['success'],
            details=entry.get('details'),
            ip_address=entry.get('ip_address')
        )
        for entry in entries
    ]

    return UserActivityLogResponse(
        user_id=user_id,
        entries=activity_entries,
        total=len(entries)
    )


@router.get("/{user_id}/permissions/effective")
@require_permission(Permissions.PLATFORM_USERS_VIEW_ALL)
async def get_effective_permissions(
    user_id: str,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Get the effective permissions for a user.

    Combines role-based permissions with any overrides.
    """
    async with get_db_connection() as conn:
        cursor = await conn.cursor()

        cursor.execute("""
            SELECT role, permission_overrides
            FROM users
            WHERE user_id = ?
        """, (user_id,))

        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "User not found")

        role = row[0]
        import json
        overrides = json.loads(row[1]) if row[1] else {}

    # Get base permissions from role
    base_permissions = get_permissions_for_role(role)
    base_codes = {p.code for p in base_permissions}

    # Apply overrides
    effective_codes = base_codes.copy()

    for perm_code, granted in overrides.items():
        if granted:
            effective_codes.add(perm_code)
        else:
            effective_codes.discard(perm_code)

    return {
        "user_id": user_id,
        "role": role,
        "base_permissions": list(base_codes),
        "overrides": overrides,
        "effective_permissions": list(effective_codes),
        "total_permissions": len(effective_codes)
    }
