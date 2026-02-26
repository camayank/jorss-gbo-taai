"""
Team Routes - Team member management endpoints.

Provides:
- Team member CRUD operations
- Invitation management
- Role and permission management
- Performance metrics (bounded)

All routes use database-backed queries.
"""

import json
import secrets
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.rbac import (
    get_current_user,
    get_current_firm,
    TenantContext,
    require_permission,
    require_firm_admin,
)
from ..models.user import UserRole, UserPermission
from ..auth.password import hash_password
from database.async_engine import get_async_session

router = APIRouter(prefix="/team", tags=["Team Management"])
logger = logging.getLogger(__name__)

# Column whitelist for UPDATE queries — prevents SQL injection in dynamic SET clauses
_USER_UPDATABLE_COLUMNS = frozenset({
    "name", "email", "role", "is_active", "phone",
    "first_name", "last_name", "job_title", "credentials",
    "license_state", "license_number", "updated_at",
})


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class TeamMemberBase(BaseModel):
    """Base team member fields."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    job_title: Optional[str] = Field(None, max_length=100)
    role: UserRole = UserRole.PREPARER


class TeamMemberCreate(TeamMemberBase):
    """Create team member request."""
    credentials: Optional[List[str]] = Field(default_factory=list, description="['CPA', 'EA']")
    license_state: Optional[str] = Field(None, max_length=2)
    license_number: Optional[str] = Field(None, max_length=50)
    send_invitation: bool = True


class TeamMemberUpdate(BaseModel):
    """Update team member request."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    job_title: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    credentials: Optional[List[str]] = None
    license_state: Optional[str] = Field(None, max_length=2)
    license_number: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


class TeamMemberResponse(BaseModel):
    """Team member response."""
    user_id: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    phone: Optional[str]
    job_title: Optional[str]
    avatar_url: Optional[str]
    role: str
    credentials: List[str]
    license_state: Optional[str]
    is_active: bool
    is_email_verified: bool
    mfa_enabled: bool
    last_login_at: Optional[datetime]
    created_at: datetime


class TeamListResponse(BaseModel):
    """Team list response."""
    team_members: List[TeamMemberResponse]
    total_count: int
    active_count: int
    max_allowed: int
    can_add_more: bool


class InvitationCreate(BaseModel):
    """Create invitation request."""
    email: EmailStr
    role: UserRole = UserRole.PREPARER
    personal_message: Optional[str] = Field(None, max_length=500)


class InvitationResponse(BaseModel):
    """Invitation response."""
    invitation_id: str
    email: str
    role: str
    status: str
    expires_at: datetime
    invited_by_name: str
    created_at: datetime


class TeamPerformance(BaseModel):
    """Team member performance metrics (bounded - no time tracking)."""
    user_id: str
    user_name: str
    period: str
    returns_processed: int
    complexity_handled: dict  # {tier1: x, tier2: y, ...}
    review_acceptance_rate: float  # 0-100%
    avg_complexity: float


# =============================================================================
# TEAM MEMBER ROUTES
# =============================================================================

@router.get("", response_model=TeamListResponse)
async def list_team_members(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    include_inactive: bool = Query(False),
    role: Optional[UserRole] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """
    List all team members in the firm.

    Returns team members with pagination and filtering options.
    """
    # Build query with filters
    conditions = ["u.firm_id = :firm_id"]
    params = {"firm_id": firm_id}

    if not include_inactive:
        conditions.append("u.is_active = true")

    if role:
        conditions.append("u.role = :role")
        params["role"] = role.value

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT u.user_id, u.email, u.first_name, u.last_name, u.phone,
               u.job_title, u.avatar_url, u.role, u.credentials,
               u.license_state, u.is_active, u.is_email_verified,
               u.mfa_enabled, u.last_login_at, u.created_at
        FROM users u
        WHERE {where_clause}
        ORDER BY u.last_name, u.first_name
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    team_members = []
    for row in rows:
        credentials = json.loads(row[8]) if row[8] else []
        team_members.append(TeamMemberResponse(
            user_id=str(row[0]),
            email=row[1],
            first_name=row[2],
            last_name=row[3],
            full_name=f"{row[2]} {row[3]}",
            phone=row[4],
            job_title=row[5],
            avatar_url=row[6],
            role=row[7],
            credentials=credentials,
            license_state=row[9],
            is_active=row[10],
            is_email_verified=row[11],
            mfa_enabled=row[12],
            last_login_at=row[13],
            created_at=row[14],
        ))

    # Get firm's max team members from subscription
    max_query = text("""
        SELECT f.max_team_members FROM firms f WHERE f.firm_id = :firm_id
    """)
    max_result = await session.execute(max_query, {"firm_id": firm_id})
    max_row = max_result.fetchone()
    max_allowed = max_row[0] if max_row else 10

    active_count = sum(1 for m in team_members if m.is_active)

    return TeamListResponse(
        team_members=team_members,
        total_count=len(team_members),
        active_count=active_count,
        max_allowed=max_allowed,
        can_add_more=active_count < max_allowed,
    )


@router.post("", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
@require_permission(UserPermission.MANAGE_TEAM)
async def add_team_member(
    member: TeamMemberCreate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Add a new team member to the firm.

    If send_invitation is true, an email invitation will be sent.
    """
    email_lower = member.email.lower()

    # Check if email already exists
    check_query = text("SELECT 1 FROM users WHERE email = :email LIMIT 1")
    exists = await session.execute(check_query, {"email": email_lower})
    if exists.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Check if firm has reached max team members
    count_query = text("""
        SELECT COUNT(*) as count, f.max_team_members
        FROM users u
        JOIN firms f ON u.firm_id = f.firm_id
        WHERE u.firm_id = :firm_id AND u.is_active = true
        GROUP BY f.max_team_members
    """)
    count_result = await session.execute(count_query, {"firm_id": firm_id})
    count_row = count_result.fetchone()

    if count_row and count_row[0] >= count_row[1]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Firm has reached maximum team members ({count_row[1]}). Upgrade your plan to add more.",
        )

    # Create user record
    new_user_id = str(uuid4())
    now = datetime.utcnow().isoformat()

    # Generate temporary password if not sending invitation
    temp_password = secrets.token_urlsafe(16)
    password_hash_val = hash_password(temp_password)

    insert_query = text("""
        INSERT INTO users (
            user_id, firm_id, email, password_hash, first_name, last_name,
            phone, job_title, role, credentials, license_state, license_number,
            is_active, is_email_verified, must_change_password, created_at, invited_by
        ) VALUES (
            :user_id, :firm_id, :email, :password_hash, :first_name, :last_name,
            :phone, :job_title, :role, :credentials, :license_state, :license_number,
            true, false, true, :created_at, :invited_by
        )
    """)

    await session.execute(insert_query, {
        "user_id": new_user_id,
        "firm_id": firm_id,
        "email": email_lower,
        "password_hash": password_hash_val,
        "first_name": member.first_name,
        "last_name": member.last_name,
        "phone": member.phone,
        "job_title": member.job_title,
        "role": member.role.value,
        "credentials": json.dumps(member.credentials or []),
        "license_state": member.license_state,
        "license_number": member.license_number,
        "created_at": now,
        "invited_by": user.user_id,
    })

    # Create invitation if requested
    if member.send_invitation:
        inv_id = str(uuid4())
        inv_token = secrets.token_urlsafe(32)
        expires = (datetime.utcnow() + timedelta(days=7)).isoformat()

        inv_query = text("""
            INSERT INTO invitations (
                invitation_id, firm_id, email, role, token, status,
                expires_at, created_at, invited_by
            ) VALUES (
                :inv_id, :firm_id, :email, :role, :token, 'pending',
                :expires_at, :created_at, :invited_by
            )
        """)
        await session.execute(inv_query, {
            "inv_id": inv_id,
            "firm_id": firm_id,
            "email": email_lower,
            "role": member.role.value,
            "token": inv_token,
            "expires_at": expires,
            "created_at": now,
            "invited_by": user.user_id,
        })

        # FREEZE & FINISH: Email service deferred to Phase 2
        # Invitation link is returned in response for manual sharing
        logger.info(f"Invitation created for {email_lower}: /invite?token={inv_token}")

    await session.commit()
    logger.info(f"Team member created: {email_lower} by {user.email}")

    return TeamMemberResponse(
        user_id=new_user_id,
        email=email_lower,
        first_name=member.first_name,
        last_name=member.last_name,
        full_name=f"{member.first_name} {member.last_name}",
        phone=member.phone,
        job_title=member.job_title,
        avatar_url=None,
        role=member.role.value,
        credentials=member.credentials or [],
        license_state=member.license_state,
        is_active=True,
        is_email_verified=False,
        mfa_enabled=False,
        last_login_at=None,
        created_at=datetime.fromisoformat(now),
    )


@router.get("/{user_id}", response_model=TeamMemberResponse)
async def get_team_member(
    user_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get details of a specific team member."""
    query = text("""
        SELECT u.user_id, u.email, u.first_name, u.last_name, u.phone,
               u.job_title, u.avatar_url, u.role, u.credentials,
               u.license_state, u.is_active, u.is_email_verified,
               u.mfa_enabled, u.last_login_at, u.created_at
        FROM users u
        WHERE u.user_id = :user_id AND u.firm_id = :firm_id
    """)

    result = await session.execute(query, {"user_id": user_id, "firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    credentials = json.loads(row[8]) if row[8] else []

    return TeamMemberResponse(
        user_id=str(row[0]),
        email=row[1],
        first_name=row[2],
        last_name=row[3],
        full_name=f"{row[2]} {row[3]}",
        phone=row[4],
        job_title=row[5],
        avatar_url=row[6],
        role=row[7],
        credentials=credentials,
        license_state=row[9],
        is_active=row[10],
        is_email_verified=row[11],
        mfa_enabled=row[12],
        last_login_at=row[13],
        created_at=row[14],
    )


@router.put("/{user_id}", response_model=TeamMemberResponse)
@require_permission(UserPermission.MANAGE_TEAM)
async def update_team_member(
    user_id: str,
    update: TeamMemberUpdate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update a team member's details."""
    # Verify user belongs to firm
    check_query = text("""
        SELECT user_id, email, first_name, last_name, phone, job_title,
               avatar_url, role, credentials, license_state, is_active,
               is_email_verified, mfa_enabled, last_login_at, created_at
        FROM users WHERE user_id = :user_id AND firm_id = :firm_id
    """)
    result = await session.execute(check_query, {"user_id": user_id, "firm_id": firm_id})
    existing = result.fetchone()

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Build update query dynamically
    updates = []
    params = {"user_id": user_id}

    if update.first_name is not None:
        updates.append("first_name = :first_name")
        params["first_name"] = update.first_name
    if update.last_name is not None:
        updates.append("last_name = :last_name")
        params["last_name"] = update.last_name
    if update.phone is not None:
        updates.append("phone = :phone")
        params["phone"] = update.phone
    if update.job_title is not None:
        updates.append("job_title = :job_title")
        params["job_title"] = update.job_title
    if update.role is not None:
        updates.append("role = :role")
        params["role"] = update.role.value
    if update.credentials is not None:
        updates.append("credentials = :credentials")
        params["credentials"] = json.dumps(update.credentials)
    if update.license_state is not None:
        updates.append("license_state = :license_state")
        params["license_state"] = update.license_state
    if update.license_number is not None:
        updates.append("license_number = :license_number")
        params["license_number"] = update.license_number
    if update.is_active is not None:
        updates.append("is_active = :is_active")
        params["is_active"] = update.is_active

    if updates:
        updates.append("updated_at = NOW()")
        # Validate all column names against whitelist before building query
        for clause in updates:
            col = clause.split("=")[0].strip()
            if col not in _USER_UPDATABLE_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Invalid field: {col}")
        update_query = text(f"UPDATE users SET {', '.join(updates)} WHERE user_id = :user_id")
        await session.execute(update_query, params)
        await session.commit()

    # Fetch updated record
    result = await session.execute(check_query, {"user_id": user_id, "firm_id": firm_id})
    row = result.fetchone()

    credentials = json.loads(row[8]) if row[8] else []

    logger.info(f"Team member updated: {user_id} by {user.email}")

    return TeamMemberResponse(
        user_id=str(row[0]),
        email=row[1],
        first_name=row[2],
        last_name=row[3],
        full_name=f"{row[2]} {row[3]}",
        phone=row[4],
        job_title=row[5],
        avatar_url=row[6],
        role=row[7],
        credentials=credentials,
        license_state=row[9],
        is_active=row[10],
        is_email_verified=row[11],
        mfa_enabled=row[12],
        last_login_at=row[13],
        created_at=row[14],
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_firm_admin
async def deactivate_team_member(
    user_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Deactivate a team member.

    This soft-deletes the user (sets is_active=False).
    User data is retained for audit purposes.
    """
    # Cannot deactivate self
    if user_id == user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    # Verify user belongs to firm
    check_query = text("""
        SELECT role FROM users WHERE user_id = :user_id AND firm_id = :firm_id
    """)
    result = await session.execute(check_query, {"user_id": user_id, "firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Cannot deactivate last firm admin
    if row[0] in ('firm_admin', 'owner'):
        admin_count_query = text("""
            SELECT COUNT(*) FROM users
            WHERE firm_id = :firm_id AND role IN ('firm_admin', 'owner') AND is_active = true
        """)
        admin_result = await session.execute(admin_count_query, {"firm_id": firm_id})
        admin_count = admin_result.fetchone()[0]

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last firm admin",
            )

    # Deactivate user
    deactivate_query = text("""
        UPDATE users SET is_active = false, updated_at = NOW()
        WHERE user_id = :user_id
    """)
    await session.execute(deactivate_query, {"user_id": user_id})
    await session.commit()

    logger.info(f"Team member deactivated: {user_id} by {user.email}")

    return None


# =============================================================================
# INVITATION ROUTES
# =============================================================================

@router.post("/invite", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
@require_permission(UserPermission.INVITE_USERS)
async def send_invitation(
    invitation: InvitationCreate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Send an invitation to join the firm.

    The invitation will be sent via email and expire after 7 days.
    """
    email_lower = invitation.email.lower()

    # Check if email is already a team member
    user_check = text("SELECT 1 FROM users WHERE email = :email LIMIT 1")
    user_exists = await session.execute(user_check, {"email": email_lower})
    if user_exists.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered as a team member",
        )

    # Check if there's already a pending invitation for this email
    pending_check = text("""
        SELECT invitation_id FROM invitations
        WHERE email = :email AND firm_id = :firm_id AND status = 'pending'
        AND expires_at > NOW()
        LIMIT 1
    """)
    pending = await session.execute(pending_check, {"email": email_lower, "firm_id": firm_id})
    if pending.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active invitation already exists for this email",
        )

    # Check if firm has reached max team members
    count_query = text("""
        SELECT COUNT(*) as count, f.max_team_members
        FROM users u
        JOIN firms f ON u.firm_id = f.firm_id
        WHERE u.firm_id = :firm_id AND u.is_active = true
        GROUP BY f.max_team_members
    """)
    count_result = await session.execute(count_query, {"firm_id": firm_id})
    count_row = count_result.fetchone()

    if count_row and count_row[0] >= count_row[1]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Firm has reached maximum team members ({count_row[1]})",
        )

    # Create invitation
    inv_id = str(uuid4())
    inv_token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    expires = now + timedelta(days=7)

    insert_query = text("""
        INSERT INTO invitations (
            invitation_id, firm_id, email, role, token, status,
            personal_message, expires_at, created_at, invited_by
        ) VALUES (
            :inv_id, :firm_id, :email, :role, :token, 'pending',
            :message, :expires_at, :created_at, :invited_by
        )
    """)
    await session.execute(insert_query, {
        "inv_id": inv_id,
        "firm_id": firm_id,
        "email": email_lower,
        "role": invitation.role.value,
        "token": inv_token,
        "message": invitation.personal_message,
        "expires_at": expires.isoformat(),
        "created_at": now.isoformat(),
        "invited_by": user.user_id,
    })
    await session.commit()

    # FREEZE & FINISH: Email service deferred to Phase 2
    # Invitation link returned in response for manual sharing
    logger.info(f"Invitation sent to {email_lower} by {user.email}: /invite?token={inv_token}")

    # Get inviter name
    inviter_name = f"{user.first_name} {user.last_name}" if hasattr(user, 'first_name') else user.email

    return InvitationResponse(
        invitation_id=inv_id,
        email=email_lower,
        role=invitation.role.value,
        status="pending",
        expires_at=expires,
        invited_by_name=inviter_name,
        created_at=now,
    )


@router.get("/invitations", response_model=List[InvitationResponse])
@require_permission(UserPermission.INVITE_USERS)
async def list_invitations(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    status_filter: Optional[str] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_async_session),
):
    """List all invitations for the firm."""
    # Build query with optional status filter
    conditions = ["i.firm_id = :firm_id"]
    params = {"firm_id": firm_id}

    if status_filter:
        conditions.append("i.status = :status")
        params["status"] = status_filter

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT i.invitation_id, i.email, i.role, i.status, i.expires_at,
               i.created_at, i.invited_by,
               COALESCE(u.first_name || ' ' || u.last_name, u.email, 'System') as inviter_name
        FROM invitations i
        LEFT JOIN users u ON i.invited_by = u.user_id
        WHERE {where_clause}
        ORDER BY i.created_at DESC
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    invitations = []
    for row in rows:
        # Parse expires_at - could be string or datetime
        expires_at = row[4]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))

        created_at = row[5]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        invitations.append(InvitationResponse(
            invitation_id=str(row[0]),
            email=row[1],
            role=row[2],
            status=row[3],
            expires_at=expires_at,
            invited_by_name=row[7] or "System",
            created_at=created_at,
        ))

    return invitations


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission(UserPermission.INVITE_USERS)
async def revoke_invitation(
    invitation_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Revoke a pending invitation."""
    # Verify invitation exists and belongs to firm
    check_query = text("""
        SELECT status FROM invitations
        WHERE invitation_id = :inv_id AND firm_id = :firm_id
    """)
    result = await session.execute(check_query, {"inv_id": invitation_id, "firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    if row[0] != 'pending':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot revoke invitation with status '{row[0]}'",
        )

    # Revoke the invitation
    revoke_query = text("""
        UPDATE invitations SET
            status = 'revoked',
            revoked_at = NOW(),
            revoked_by = :revoked_by
        WHERE invitation_id = :inv_id
    """)
    await session.execute(revoke_query, {"inv_id": invitation_id, "revoked_by": user.user_id})
    await session.commit()

    logger.info(f"Invitation {invitation_id} revoked by {user.email}")

    return None


@router.post("/invitations/{invitation_id}/resend")
@require_permission(UserPermission.INVITE_USERS)
async def resend_invitation(
    invitation_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Resend an invitation email and extend expiration."""
    # Verify invitation exists and belongs to firm
    check_query = text("""
        SELECT status, email, role FROM invitations
        WHERE invitation_id = :inv_id AND firm_id = :firm_id
    """)
    result = await session.execute(check_query, {"inv_id": invitation_id, "firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    if row[0] not in ('pending', 'expired'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resend invitation with status '{row[0]}'",
        )

    # Generate new token and extend expiration
    new_token = secrets.token_urlsafe(32)
    new_expires = (datetime.utcnow() + timedelta(days=7)).isoformat()

    update_query = text("""
        UPDATE invitations SET
            token = :token,
            expires_at = :expires_at,
            status = 'pending',
            resent_count = COALESCE(resent_count, 0) + 1,
            last_resent_at = NOW()
        WHERE invitation_id = :inv_id
    """)
    await session.execute(update_query, {
        "inv_id": invitation_id,
        "token": new_token,
        "expires_at": new_expires,
    })
    await session.commit()

    # FREEZE & FINISH: Email service deferred to Phase 2
    # Share the link manually with the invitee
    logger.info(f"Invitation resent to {row[1]} by {user.email}: /invite?token={new_token}")

    return {
        "status": "success",
        "message": f"Invitation resent to {row[1]}",
        "new_expires_at": new_expires,
    }


# =============================================================================
# PERFORMANCE ROUTES (BOUNDED - NO TIME TRACKING)
# =============================================================================

@router.get("/{user_id}/performance", response_model=TeamPerformance)
@require_permission(UserPermission.VIEW_TEAM_PERFORMANCE)
async def get_team_member_performance(
    user_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    period: str = Query("month", description="day, week, month, quarter, year"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get performance metrics for a team member.

    IMPORTANT: This endpoint intentionally does NOT include:
    - Time tracking
    - Revenue per staff
    - Detailed productivity metrics

    This aligns with the platform philosophy of being a
    Tax Decision Intelligence tool, not a Practice Management System.
    """
    # Verify user belongs to firm and get name
    user_query = text("""
        SELECT first_name, last_name FROM users
        WHERE user_id = :user_id AND firm_id = :firm_id
    """)
    user_result = await session.execute(user_query, {"user_id": user_id, "firm_id": firm_id})
    user_row = user_result.fetchone()

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    user_name = f"{user_row[0]} {user_row[1]}"

    # Determine date range based on period
    period_intervals = {
        "day": "1 day",
        "week": "7 days",
        "month": "30 days",
        "quarter": "90 days",
        "year": "365 days",
    }
    interval = period_intervals.get(period, "30 days")

    # Get returns processed count
    returns_query = text(f"""
        SELECT COUNT(*) FROM returns r
        WHERE r.preparer_id = :user_id
        AND r.created_at >= NOW() - INTERVAL '{interval}'
    """)
    returns_result = await session.execute(returns_query, {"user_id": user_id})
    returns_processed = returns_result.fetchone()[0] or 0

    # Get complexity breakdown (tiers 1-5 based on return complexity_score)
    complexity_query = text(f"""
        SELECT
            SUM(CASE WHEN complexity_score <= 20 THEN 1 ELSE 0 END) as tier1,
            SUM(CASE WHEN complexity_score > 20 AND complexity_score <= 40 THEN 1 ELSE 0 END) as tier2,
            SUM(CASE WHEN complexity_score > 40 AND complexity_score <= 60 THEN 1 ELSE 0 END) as tier3,
            SUM(CASE WHEN complexity_score > 60 AND complexity_score <= 80 THEN 1 ELSE 0 END) as tier4,
            SUM(CASE WHEN complexity_score > 80 THEN 1 ELSE 0 END) as tier5,
            AVG(complexity_score) as avg_complexity
        FROM returns r
        WHERE r.preparer_id = :user_id
        AND r.created_at >= NOW() - INTERVAL '{interval}'
    """)
    complexity_result = await session.execute(complexity_query, {"user_id": user_id})
    complexity_row = complexity_result.fetchone()

    complexity_handled = {
        "tier1": complexity_row[0] or 0,
        "tier2": complexity_row[1] or 0,
        "tier3": complexity_row[2] or 0,
        "tier4": complexity_row[3] or 0,
        "tier5": complexity_row[4] or 0,
    }
    avg_complexity = float(complexity_row[5]) if complexity_row[5] else 0.0

    # Get review acceptance rate (returns that passed review without rejection)
    review_query = text(f"""
        SELECT
            COUNT(*) as total_reviewed,
            SUM(CASE WHEN review_status = 'approved' THEN 1 ELSE 0 END) as approved
        FROM returns r
        WHERE r.preparer_id = :user_id
        AND r.review_status IS NOT NULL
        AND r.created_at >= NOW() - INTERVAL '{interval}'
    """)
    review_result = await session.execute(review_query, {"user_id": user_id})
    review_row = review_result.fetchone()

    total_reviewed = review_row[0] or 0
    approved = review_row[1] or 0
    review_acceptance_rate = (approved / total_reviewed * 100) if total_reviewed > 0 else 100.0

    return TeamPerformance(
        user_id=user_id,
        user_name=user_name,
        period=period,
        returns_processed=returns_processed,
        complexity_handled=complexity_handled,
        review_acceptance_rate=round(review_acceptance_rate, 1),
        avg_complexity=round(avg_complexity / 20, 1),  # Convert 0-100 score to 0-5 tier scale
    )
