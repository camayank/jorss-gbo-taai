"""
Team Service - Team member management operations.

Handles:
- User CRUD within a firm
- Invitations workflow
- Role and permission management
- Performance metrics
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
import secrets
import logging

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User, UserRole, UserPermission, ROLE_PERMISSIONS
from ..models.invitation import Invitation, InvitationStatus
from ..models.firm import Firm


logger = logging.getLogger(__name__)


class TeamService:
    """Service for team management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # TEAM MEMBERS
    # =========================================================================

    async def list_team_members(
        self,
        firm_id: str,
        include_inactive: bool = False,
        role_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all team members for a firm."""
        query = select(User).where(User.firm_id == firm_id)

        if not include_inactive:
            query = query.where(User.is_active == True)

        if role_filter:
            query = query.where(User.role == role_filter)

        query = query.order_by(User.created_at.desc())

        result = await self.db.execute(query)
        users = result.scalars().all()

        return [self._user_to_dict(u) for u in users]

    async def get_team_member(
        self,
        firm_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a specific team member."""
        result = await self.db.execute(
            select(User).where(
                and_(User.firm_id == firm_id, User.user_id == user_id)
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        return self._user_to_dict(user, include_details=True)

    async def update_team_member(
        self,
        firm_id: str,
        user_id: str,
        **updates,
    ) -> Optional[Dict[str, Any]]:
        """Update a team member."""
        result = await self.db.execute(
            select(User).where(
                and_(User.firm_id == firm_id, User.user_id == user_id)
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        allowed_fields = {"name", "phone", "title", "department"}

        for field, value in updates.items():
            if field in allowed_fields and hasattr(user, field):
                setattr(user, field, value)

        user.updated_at = datetime.utcnow()
        await self.db.commit()

        return self._user_to_dict(user)

    async def update_role(
        self,
        firm_id: str,
        user_id: str,
        new_role: str,
        custom_permissions: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a team member's role."""
        result = await self.db.execute(
            select(User).where(
                and_(User.firm_id == firm_id, User.user_id == user_id)
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Validate role
        try:
            role_enum = UserRole(new_role)
        except ValueError:
            logger.warning(f"Invalid role: {new_role}")
            return None

        user.role = new_role

        # Handle custom permissions override
        if custom_permissions is not None:
            valid_permissions = []
            for perm in custom_permissions:
                try:
                    UserPermission(perm)
                    valid_permissions.append(perm)
                except ValueError:
                    continue
            user.custom_permissions = valid_permissions
        else:
            user.custom_permissions = None

        user.updated_at = datetime.utcnow()
        await self.db.commit()

        logger.info(f"Updated role for user {user_id} to {new_role}")

        return self._user_to_dict(user, include_details=True)

    async def deactivate_member(
        self,
        firm_id: str,
        user_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Deactivate a team member."""
        result = await self.db.execute(
            select(User).where(
                and_(User.firm_id == firm_id, User.user_id == user_id)
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return False

        # Prevent deactivating the last admin
        admin_count_result = await self.db.execute(
            select(func.count(User.user_id)).where(
                and_(
                    User.firm_id == firm_id,
                    User.role == "firm_admin",
                    User.is_active == True,
                )
            )
        )
        admin_count = admin_count_result.scalar() or 0

        if user.role == "firm_admin" and admin_count <= 1:
            logger.warning(f"Cannot deactivate last admin {user_id}")
            return False

        user.is_active = False
        user.deactivated_at = datetime.utcnow()
        user.deactivation_reason = reason
        user.updated_at = datetime.utcnow()

        await self.db.commit()
        logger.info(f"Deactivated user {user_id}")

        return True

    async def reactivate_member(
        self,
        firm_id: str,
        user_id: str,
    ) -> bool:
        """Reactivate a deactivated team member."""
        result = await self.db.execute(
            select(User).where(
                and_(User.firm_id == firm_id, User.user_id == user_id)
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return False

        user.is_active = True
        user.deactivated_at = None
        user.deactivation_reason = None
        user.updated_at = datetime.utcnow()

        await self.db.commit()
        logger.info(f"Reactivated user {user_id}")

        return True

    # =========================================================================
    # INVITATIONS
    # =========================================================================

    async def create_invitation(
        self,
        firm_id: str,
        inviter_id: str,
        email: str,
        role: str,
        custom_permissions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create an invitation for a new team member."""
        # Check if email already exists in firm
        existing = await self.db.execute(
            select(User).where(
                and_(User.firm_id == firm_id, User.email == email)
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "User with this email already exists in the firm"}

        # Check for pending invitation
        pending = await self.db.execute(
            select(Invitation).where(
                and_(
                    Invitation.firm_id == firm_id,
                    Invitation.email == email,
                    Invitation.status == InvitationStatus.PENDING.value,
                )
            )
        )
        if pending.scalar_one_or_none():
            return {"error": "Pending invitation already exists for this email"}

        # Check firm limits
        from .firm_service import FirmService
        firm_service = FirmService(self.db)
        limit_check = await firm_service.check_limit(firm_id, "team_members")
        if not limit_check.get("allowed"):
            return {"error": limit_check.get("reason")}

        # Generate secure token
        token = secrets.token_urlsafe(32)
        invitation_id = str(uuid4())
        now = datetime.utcnow()

        invitation = Invitation(
            invitation_id=invitation_id,
            firm_id=firm_id,
            email=email,
            role=role,
            custom_permissions=custom_permissions,
            token=token,
            invited_by=inviter_id,
            status=InvitationStatus.PENDING.value,
            expires_at=now + timedelta(days=7),
            created_at=now,
        )
        self.db.add(invitation)
        await self.db.commit()

        logger.info(f"Created invitation {invitation_id} for {email}")

        return {
            "invitation_id": invitation_id,
            "email": email,
            "role": role,
            "token": token,
            "expires_at": invitation.expires_at.isoformat(),
        }

    async def list_invitations(
        self,
        firm_id: str,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all invitations for a firm."""
        query = select(Invitation).where(Invitation.firm_id == firm_id)

        if status_filter:
            query = query.where(Invitation.status == status_filter)

        query = query.order_by(Invitation.created_at.desc())

        result = await self.db.execute(query)
        invitations = result.scalars().all()

        return [
            {
                "invitation_id": str(inv.invitation_id),
                "email": inv.email,
                "role": inv.role,
                "status": inv.status,
                "invited_at": inv.created_at.isoformat() if inv.created_at else None,
                "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            }
            for inv in invitations
        ]

    async def accept_invitation(
        self,
        token: str,
        name: str,
        password_hash: str,
    ) -> Dict[str, Any]:
        """Accept an invitation and create user account."""
        result = await self.db.execute(
            select(Invitation).where(
                and_(
                    Invitation.token == token,
                    Invitation.status == InvitationStatus.PENDING.value,
                )
            )
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            return {"error": "Invalid or expired invitation"}

        if invitation.expires_at < datetime.utcnow():
            invitation.status = InvitationStatus.EXPIRED.value
            await self.db.commit()
            return {"error": "Invitation has expired"}

        # Create user
        user_id = str(uuid4())
        now = datetime.utcnow()

        user = User(
            user_id=user_id,
            firm_id=str(invitation.firm_id),
            email=invitation.email,
            name=name,
            password_hash=password_hash,
            role=invitation.role,
            custom_permissions=invitation.custom_permissions,
            is_active=True,
            email_verified=True,  # Verified via invitation
            created_at=now,
        )
        self.db.add(user)

        # Update invitation
        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = now

        await self.db.commit()
        logger.info(f"User {user_id} created from invitation {invitation.invitation_id}")

        return {
            "user_id": user_id,
            "firm_id": str(invitation.firm_id),
            "email": invitation.email,
            "role": invitation.role,
        }

    async def revoke_invitation(
        self,
        firm_id: str,
        invitation_id: str,
    ) -> bool:
        """Revoke a pending invitation."""
        result = await self.db.execute(
            select(Invitation).where(
                and_(
                    Invitation.firm_id == firm_id,
                    Invitation.invitation_id == invitation_id,
                    Invitation.status == InvitationStatus.PENDING.value,
                )
            )
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            return False

        invitation.status = InvitationStatus.REVOKED.value
        await self.db.commit()

        return True

    async def resend_invitation(
        self,
        firm_id: str,
        invitation_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Resend an invitation with new token and expiry."""
        result = await self.db.execute(
            select(Invitation).where(
                and_(
                    Invitation.firm_id == firm_id,
                    Invitation.invitation_id == invitation_id,
                )
            )
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            return None

        # Generate new token
        invitation.token = secrets.token_urlsafe(32)
        invitation.expires_at = datetime.utcnow() + timedelta(days=7)
        invitation.status = InvitationStatus.PENDING.value

        await self.db.commit()

        return {
            "invitation_id": str(invitation.invitation_id),
            "email": invitation.email,
            "token": invitation.token,
            "expires_at": invitation.expires_at.isoformat(),
        }

    # =========================================================================
    # PERMISSIONS
    # =========================================================================

    def get_effective_permissions(self, user: User) -> List[str]:
        """Get effective permissions for a user."""
        # Start with role defaults
        try:
            role = UserRole(user.role)
            permissions = set(ROLE_PERMISSIONS.get(role, set()))
        except ValueError:
            permissions = set()

        # Apply custom permissions if set
        if user.custom_permissions:
            permissions = set(user.custom_permissions)

        return [p.value if hasattr(p, "value") else p for p in permissions]

    async def get_role_permissions(self, role: str) -> Dict[str, Any]:
        """Get default permissions for a role."""
        try:
            role_enum = UserRole(role)
            permissions = ROLE_PERMISSIONS.get(role_enum, set())
            return {
                "role": role,
                "permissions": [p.value for p in permissions],
            }
        except ValueError:
            return {"role": role, "permissions": []}

    # =========================================================================
    # PERFORMANCE METRICS
    # =========================================================================

    async def get_team_stats(self, firm_id: str) -> Dict[str, Any]:
        """Get team statistics for a firm."""
        # Count by role
        role_counts_result = await self.db.execute(
            select(User.role, func.count(User.user_id)).where(
                and_(User.firm_id == firm_id, User.is_active == True)
            ).group_by(User.role)
        )
        role_counts = dict(role_counts_result.all())

        # Total active
        total = sum(role_counts.values())

        # Pending invitations
        pending_result = await self.db.execute(
            select(func.count(Invitation.invitation_id)).where(
                and_(
                    Invitation.firm_id == firm_id,
                    Invitation.status == InvitationStatus.PENDING.value,
                )
            )
        )
        pending_invitations = pending_result.scalar() or 0

        return {
            "total_active": total,
            "by_role": role_counts,
            "pending_invitations": pending_invitations,
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _user_to_dict(
        self,
        user: User,
        include_details: bool = False,
    ) -> Dict[str, Any]:
        """Convert user model to dictionary."""
        data = {
            "user_id": str(user.user_id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        }

        if include_details:
            data["permissions"] = self.get_effective_permissions(user)
            data["custom_permissions"] = user.custom_permissions
            data["email_verified"] = user.email_verified
            data["mfa_enabled"] = user.mfa_enabled
            data["phone"] = user.phone
            data["title"] = user.title
            data["department"] = user.department

        return data
