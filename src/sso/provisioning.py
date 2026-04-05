"""
JIT (Just-In-Time) User Provisioning for SSO.

Creates or updates a User record when a CPA firm member authenticates via SSO
for the first time. No local password is set for SSO-provisioned users.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from admin_panel.models.user import User


class JITProvisioningService:
    def __init__(self, db: Session):
        self.db = db

    def provision_or_update(
        self,
        firm_id: UUID,
        email: str,
        first_name: str,
        last_name: str,
        role: str,
        sso_provider: str,
        sso_subject_id: str,
    ) -> User:
        """
        Find or create a User for the given SSO identity.

        - Existing user (matched by email + firm): update name and role from IdP.
        - New user: create with no password_hash (SSO-only login).

        The IdP is authoritative for name and role changes.
        """
        user = (
            self.db.query(User)
            .filter(User.email == email, User.firm_id == firm_id)
            .first()
        )

        if user is None:
            user = User(
                firm_id=firm_id,
                email=email,
                first_name=first_name or email.split("@")[0],
                last_name=last_name or "",
                role=role,
                password_hash=None,  # SSO-only, no local password
                is_active=True,
                is_email_verified=True,  # IdP has already verified the email
            )
            self.db.add(user)
        else:
            # Sync profile from IdP on every login
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.role = role
            user.is_active = True

        user.last_login_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)
        return user
