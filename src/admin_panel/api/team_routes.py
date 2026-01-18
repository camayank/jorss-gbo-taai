"""
Team Routes - Team member management endpoints.

Provides:
- Team member CRUD operations
- Invitation management
- Role and permission management
- Performance metrics (bounded)
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, EmailStr

from ..auth.rbac import (
    get_current_user,
    get_current_firm,
    TenantContext,
    require_permission,
    require_firm_admin,
)
from ..models.user import UserRole, UserPermission

router = APIRouter(prefix="/team", tags=["Team Management"])


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
):
    """
    List all team members in the firm.

    Returns team members with pagination and filtering options.
    """
    # TODO: Implement actual database query
    # This is mock data for API structure demonstration
    team_members = [
        TeamMemberResponse(
            user_id="user-1",
            email="sarah.chen@example.com",
            first_name="Sarah",
            last_name="Chen",
            full_name="Sarah Chen",
            phone="555-0101",
            job_title="Senior Tax Preparer",
            avatar_url=None,
            role=UserRole.SENIOR_PREPARER.value,
            credentials=["CPA"],
            license_state="CA",
            is_active=True,
            is_email_verified=True,
            mfa_enabled=True,
            last_login_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
        TeamMemberResponse(
            user_id="user-2",
            email="mike.thompson@example.com",
            first_name="Mike",
            last_name="Thompson",
            full_name="Mike Thompson",
            phone="555-0102",
            job_title="Tax Reviewer",
            avatar_url=None,
            role=UserRole.REVIEWER.value,
            credentials=["CPA", "EA"],
            license_state="CA",
            is_active=True,
            is_email_verified=True,
            mfa_enabled=False,
            last_login_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
    ]

    # Filter by role if specified
    if role:
        team_members = [m for m in team_members if m.role == role.value]

    # Filter inactive
    if not include_inactive:
        team_members = [m for m in team_members if m.is_active]

    return TeamListResponse(
        team_members=team_members,
        total_count=len(team_members),
        active_count=sum(1 for m in team_members if m.is_active),
        max_allowed=10,  # Based on subscription tier
        can_add_more=len(team_members) < 10,
    )


@router.post("", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
@require_permission(UserPermission.MANAGE_TEAM)
async def add_team_member(
    member: TeamMemberCreate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    Add a new team member to the firm.

    If send_invitation is true, an email invitation will be sent.
    """
    # TODO: Implement actual user creation
    # - Check if email already exists
    # - Check if firm has reached max team members
    # - Create user record
    # - Send invitation email if requested

    return TeamMemberResponse(
        user_id="user-new",
        email=member.email,
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
        created_at=datetime.utcnow(),
    )


@router.get("/{user_id}", response_model=TeamMemberResponse)
async def get_team_member(
    user_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Get details of a specific team member."""
    # TODO: Implement actual database query
    # Verify user belongs to the same firm

    return TeamMemberResponse(
        user_id=user_id,
        email="sarah.chen@example.com",
        first_name="Sarah",
        last_name="Chen",
        full_name="Sarah Chen",
        phone="555-0101",
        job_title="Senior Tax Preparer",
        avatar_url=None,
        role=UserRole.SENIOR_PREPARER.value,
        credentials=["CPA"],
        license_state="CA",
        is_active=True,
        is_email_verified=True,
        mfa_enabled=True,
        last_login_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )


@router.put("/{user_id}", response_model=TeamMemberResponse)
@require_permission(UserPermission.MANAGE_TEAM)
async def update_team_member(
    user_id: str,
    update: TeamMemberUpdate,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Update a team member's details."""
    # TODO: Implement actual update
    # - Verify user belongs to firm
    # - Apply updates
    # - Log changes in audit trail

    return TeamMemberResponse(
        user_id=user_id,
        email="sarah.chen@example.com",
        first_name=update.first_name or "Sarah",
        last_name=update.last_name or "Chen",
        full_name=f"{update.first_name or 'Sarah'} {update.last_name or 'Chen'}",
        phone=update.phone,
        job_title=update.job_title,
        avatar_url=None,
        role=update.role.value if update.role else UserRole.SENIOR_PREPARER.value,
        credentials=update.credentials or ["CPA"],
        license_state=update.license_state,
        is_active=update.is_active if update.is_active is not None else True,
        is_email_verified=True,
        mfa_enabled=True,
        last_login_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_firm_admin
async def deactivate_team_member(
    user_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    Deactivate a team member.

    This soft-deletes the user (sets is_active=False).
    User data is retained for audit purposes.
    """
    # TODO: Implement actual deactivation
    # - Verify user belongs to firm
    # - Cannot deactivate self
    # - Cannot deactivate last firm admin
    # - Set is_active=False
    # - Log in audit trail

    if user_id == user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

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
):
    """
    Send an invitation to join the firm.

    The invitation will be sent via email and expire after 7 days.
    """
    # TODO: Implement actual invitation creation
    # - Check if email already has pending invitation
    # - Check if email is already a team member
    # - Create invitation record
    # - Send email

    return InvitationResponse(
        invitation_id="inv-new",
        email=invitation.email,
        role=invitation.role.value,
        status="pending",
        expires_at=datetime.utcnow(),  # + 7 days
        invited_by_name=user.email,
        created_at=datetime.utcnow(),
    )


@router.get("/invitations", response_model=List[InvitationResponse])
@require_permission(UserPermission.INVITE_USERS)
async def list_invitations(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List all pending invitations for the firm."""
    # TODO: Implement actual query
    return [
        InvitationResponse(
            invitation_id="inv-1",
            email="new.member@example.com",
            role=UserRole.PREPARER.value,
            status="pending",
            expires_at=datetime.utcnow(),
            invited_by_name="Admin User",
            created_at=datetime.utcnow(),
        ),
    ]


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission(UserPermission.INVITE_USERS)
async def revoke_invitation(
    invitation_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Revoke a pending invitation."""
    # TODO: Implement actual revocation
    return None


@router.post("/invitations/{invitation_id}/resend")
@require_permission(UserPermission.INVITE_USERS)
async def resend_invitation(
    invitation_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Resend an invitation email and extend expiration."""
    # TODO: Implement actual resend
    return {"status": "success", "message": "Invitation resent"}


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
    # TODO: Implement actual performance query
    return TeamPerformance(
        user_id=user_id,
        user_name="Sarah Chen",
        period=period,
        returns_processed=15,
        complexity_handled={
            "tier1": 5,
            "tier2": 6,
            "tier3": 3,
            "tier4": 1,
            "tier5": 0,
        },
        review_acceptance_rate=92.5,
        avg_complexity=2.1,
    )
