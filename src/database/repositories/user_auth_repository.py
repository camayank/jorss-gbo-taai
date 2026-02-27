"""User Authentication Repository Implementation.

Provides database-backed user authentication with support for:
- Firm team members (users table)
- Platform admins (platform_admins table)
- Consumers and CPA clients (taxpayers/clients tables)

This repository abstracts the underlying table structure and provides
a unified interface for user authentication.
"""

from __future__ import annotations

import json
import logging
import hashlib
import hmac
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class UserAuthRepository:
    """
    Repository for user authentication operations.

    Supports multiple user types across different tables:
    - Firm users: users table
    - Platform admins: platform_admins table
    - Consumers/Clients: Uses taxpayer or client records
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with a session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by email from any user table.

        Searches in order:
        1. platform_admins
        2. users (firm team members)
        3. clients

        Args:
            email: User's email address.

        Returns:
            User data dict or None if not found.
        """
        email_lower = email.lower()

        # Check platform admins first
        user = await self._get_platform_admin_by_email(email_lower)
        if user:
            return user

        # Check firm users
        user = await self._get_firm_user_by_email(email_lower)
        if user:
            return user

        # Check clients
        user = await self._get_client_by_email(email_lower)
        if user:
            return user

        return None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by ID from any user table.

        Args:
            user_id: User identifier.

        Returns:
            User data dict or None if not found.
        """
        # Try to determine user type from ID prefix or search all tables
        user = await self._get_platform_admin_by_id(user_id)
        if user:
            return user

        user = await self._get_firm_user_by_id(user_id)
        if user:
            return user

        user = await self._get_client_by_id(user_id)
        if user:
            return user

        return None

    async def verify_password(self, user_id: str, password_hash: str) -> bool:
        """
        Verify a user's password hash matches.

        Args:
            user_id: User identifier.
            password_hash: Hash to verify.

        Returns:
            True if password matches.
        """
        user = await self.get_user_by_id(user_id)
        if user and user.get("password_hash"):
            return hmac.compare_digest(user["password_hash"], password_hash)
        return False

    async def update_last_login(self, user_id: str, ip_address: Optional[str] = None) -> bool:
        """
        Update user's last login timestamp.

        Args:
            user_id: User identifier.
            ip_address: IP address of login.

        Returns:
            True if updated.
        """
        now = datetime.utcnow().isoformat()

        # Try firm users first
        query = text("""
            UPDATE users SET
                last_login_at = :last_login,
                last_login_ip = :ip_address,
                failed_login_attempts = 0
            WHERE user_id = :user_id
        """)
        result = await self._session.execute(
            query,
            {"user_id": user_id, "last_login": now, "ip_address": ip_address}
        )
        if result.rowcount > 0:
            return True

        # Try platform admins
        query = text("""
            UPDATE platform_admins SET
                last_login_at = :last_login
            WHERE admin_id = :user_id
        """)
        result = await self._session.execute(
            query,
            {"user_id": user_id, "last_login": now}
        )
        return result.rowcount > 0

    async def increment_failed_login(self, user_id: str) -> int:
        """
        Increment failed login attempts.

        Args:
            user_id: User identifier.

        Returns:
            New count of failed attempts.
        """
        query = text("""
            UPDATE users SET
                failed_login_attempts = failed_login_attempts + 1
            WHERE user_id = :user_id
            RETURNING failed_login_attempts
        """)
        result = await self._session.execute(query, {"user_id": user_id})
        row = result.fetchone()
        return row[0] if row else 0

    async def lock_user(self, user_id: str, until: datetime) -> bool:
        """
        Lock a user account until a specific time.

        Args:
            user_id: User identifier.
            until: Datetime until which user is locked.

        Returns:
            True if locked.
        """
        query = text("""
            UPDATE users SET
                locked_until = :locked_until
            WHERE user_id = :user_id
        """)
        result = await self._session.execute(
            query,
            {"user_id": user_id, "locked_until": until.isoformat()}
        )
        return result.rowcount > 0

    async def create_user(self, user_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new user.

        Args:
            user_data: User data dict.

        Returns:
            User ID if created.
        """
        user_type = user_data.get("user_type", "consumer")
        user_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        if user_type == "platform_admin":
            query = text("""
                INSERT INTO platform_admins (
                    admin_id, email, password_hash, first_name, last_name,
                    role, is_active, created_at
                ) VALUES (
                    :admin_id, :email, :password_hash, :first_name, :last_name,
                    :role, true, :created_at
                )
            """)
            params = {
                "admin_id": user_id,
                "email": user_data["email"].lower(),
                "password_hash": user_data.get("password_hash"),
                "first_name": user_data.get("first_name", ""),
                "last_name": user_data.get("last_name", ""),
                "role": user_data.get("role", "admin"),
                "created_at": now,
            }
        elif user_type in ("cpa_team", "firm_admin"):
            if not user_data.get("firm_id"):
                raise ValueError("Firm ID required for CPA team members")
            query = text("""
                INSERT INTO users (
                    user_id, firm_id, email, password_hash, first_name, last_name,
                    phone, role, is_active, created_at
                ) VALUES (
                    :user_id, :firm_id, :email, :password_hash, :first_name, :last_name,
                    :phone, :role, true, :created_at
                )
            """)
            params = {
                "user_id": user_id,
                "firm_id": user_data["firm_id"],
                "email": user_data["email"].lower(),
                "password_hash": user_data.get("password_hash"),
                "first_name": user_data.get("first_name", ""),
                "last_name": user_data.get("last_name", ""),
                "phone": user_data.get("phone"),
                "role": user_data.get("role", "preparer"),
                "created_at": now,
            }
        else:
            # Consumer or CPA client - use clients table
            query = text("""
                INSERT INTO clients (
                    client_id, preparer_id, first_name, last_name, email, phone,
                    is_active, created_at
                ) VALUES (
                    :client_id, :preparer_id, :first_name, :last_name, :email, :phone,
                    true, :created_at
                )
            """)
            params = {
                "client_id": user_id,
                "preparer_id": user_data.get("assigned_cpa_id"),
                "first_name": user_data.get("first_name", ""),
                "last_name": user_data.get("last_name", ""),
                "email": user_data["email"].lower(),
                "phone": user_data.get("phone"),
                "created_at": now,
            }

        try:
            await self._session.execute(query, params)
            logger.info(f"Created user: {user_id} ({user_data['email']})")
            return user_id
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None

    async def update_password(self, user_id: str, new_password_hash: str) -> bool:
        """
        Update user's password.

        Args:
            user_id: User identifier.
            new_password_hash: New password hash.

        Returns:
            True if updated.
        """
        now = datetime.utcnow().isoformat()

        # Try firm users
        query = text("""
            UPDATE users SET
                password_hash = :password_hash,
                password_changed_at = :changed_at,
                must_change_password = false
            WHERE user_id = :user_id
        """)
        result = await self._session.execute(
            query,
            {"user_id": user_id, "password_hash": new_password_hash, "changed_at": now}
        )
        if result.rowcount > 0:
            return True

        # Try platform admins
        query = text("""
            UPDATE platform_admins SET
                password_hash = :password_hash
            WHERE admin_id = :user_id
        """)
        result = await self._session.execute(
            query,
            {"user_id": user_id, "password_hash": new_password_hash}
        )
        return result.rowcount > 0

    # =========================================================================
    # PRIVATE METHODS - TABLE-SPECIFIC QUERIES
    # =========================================================================

    async def _get_platform_admin_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get platform admin by email."""
        query = text("""
            SELECT admin_id, email, password_hash, first_name, last_name,
                   role, is_active, mfa_enabled, last_login_at, created_at
            FROM platform_admins
            WHERE email = :email AND is_active = true
        """)
        result = await self._session.execute(query, {"email": email})
        row = result.fetchone()

        if row:
            return {
                "id": str(row[0]),
                "email": row[1],
                "password_hash": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "role": row[5],
                "is_active": row[6],
                "mfa_enabled": row[7],
                "last_login_at": row[8],
                "user_type": "platform_admin",
                "permissions": ["*"],  # Platform admins have all permissions
            }
        return None

    async def _get_platform_admin_by_id(self, admin_id: str) -> Optional[Dict[str, Any]]:
        """Get platform admin by ID."""
        query = text("""
            SELECT admin_id, email, password_hash, first_name, last_name,
                   role, is_active, mfa_enabled, last_login_at, created_at
            FROM platform_admins
            WHERE admin_id = :admin_id
        """)
        result = await self._session.execute(query, {"admin_id": admin_id})
        row = result.fetchone()

        if row:
            return {
                "id": str(row[0]),
                "email": row[1],
                "password_hash": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "role": row[5],
                "is_active": row[6],
                "mfa_enabled": row[7],
                "last_login_at": row[8],
                "user_type": "platform_admin",
                "permissions": ["*"],
            }
        return None

    async def _get_firm_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get firm user by email."""
        query = text("""
            SELECT u.user_id, u.email, u.password_hash, u.first_name, u.last_name,
                   u.phone, u.role, u.custom_permissions, u.credentials,
                   u.is_active, u.mfa_enabled, u.last_login_at, u.locked_until,
                   u.failed_login_attempts, u.firm_id, f.name as firm_name
            FROM users u
            LEFT JOIN firms f ON u.firm_id = f.firm_id
            WHERE u.email = :email
        """)
        result = await self._session.execute(query, {"email": email})
        row = result.fetchone()

        if row:
            return self._map_firm_user_row(row)
        return None

    async def _get_firm_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get firm user by ID."""
        query = text("""
            SELECT u.user_id, u.email, u.password_hash, u.first_name, u.last_name,
                   u.phone, u.role, u.custom_permissions, u.credentials,
                   u.is_active, u.mfa_enabled, u.last_login_at, u.locked_until,
                   u.failed_login_attempts, u.firm_id, f.name as firm_name
            FROM users u
            LEFT JOIN firms f ON u.firm_id = f.firm_id
            WHERE u.user_id = :user_id
        """)
        result = await self._session.execute(query, {"user_id": user_id})
        row = result.fetchone()

        if row:
            return self._map_firm_user_row(row)
        return None

    def _map_firm_user_row(self, row) -> Dict[str, Any]:
        """Map a firm user row to a user dict."""
        # Determine user type based on role
        role = row[6]
        user_type = "cpa_team"
        if role == "firm_admin":
            user_type = "firm_admin"
        elif role == "owner":
            user_type = "firm_owner"

        # Parse permissions
        permissions = json.loads(row[7]) if row[7] else []

        # Add role-based permissions
        role_permissions = self._get_role_permissions(role)
        permissions = list(set(permissions + role_permissions))

        return {
            "id": str(row[0]),
            "email": row[1],
            "password_hash": row[2],
            "first_name": row[3],
            "last_name": row[4],
            "phone": row[5],
            "role": role,
            "permissions": permissions,
            "credentials": json.loads(row[8]) if row[8] else [],
            "is_active": row[9],
            "mfa_enabled": row[10],
            "last_login_at": row[11],
            "locked_until": row[12],
            "failed_login_attempts": row[13],
            "firm_id": str(row[14]) if row[14] else None,
            "firm_name": row[15],
            "user_type": user_type,
        }

    def _get_role_permissions(self, role: str) -> list:
        """Get default permissions for a role."""
        role_permissions = {
            "owner": ["*"],
            "firm_admin": [
                "manage_team", "manage_billing", "manage_settings",
                "view_clients", "edit_returns", "approve_returns",
                "create_scenarios", "send_messages", "view_analytics"
            ],
            "manager": [
                "view_clients", "edit_returns", "approve_returns",
                "create_scenarios", "send_messages", "view_analytics"
            ],
            "senior_preparer": [
                "view_clients", "edit_returns", "create_scenarios",
                "send_messages"
            ],
            "preparer": ["view_clients", "edit_returns", "create_scenarios"],
            "reviewer": ["view_clients", "view_returns", "add_notes"],
            "viewer": ["view_clients", "view_returns"],
        }
        return role_permissions.get(role, [])

    async def _get_client_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get client by email."""
        query = text("""
            SELECT client_id, preparer_id, first_name, last_name, email, phone,
                   is_active, created_at
            FROM clients
            WHERE email = :email
        """)
        result = await self._session.execute(query, {"email": email})
        row = result.fetchone()

        if row:
            return {
                "id": str(row[0]),
                "assigned_cpa_id": str(row[1]) if row[1] else None,
                "first_name": row[2],
                "last_name": row[3],
                "email": row[4],
                "phone": row[5],
                "is_active": row[6],
                "password_hash": None,  # Clients may use magic links
                "user_type": "cpa_client" if row[1] else "consumer",
                "permissions": ["view_own_return", "upload_documents"],
            }
        return None

    async def _get_client_by_id(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get client by ID."""
        query = text("""
            SELECT client_id, preparer_id, first_name, last_name, email, phone,
                   is_active, created_at
            FROM clients
            WHERE client_id = :client_id
        """)
        result = await self._session.execute(query, {"client_id": client_id})
        row = result.fetchone()

        if row:
            return {
                "id": str(row[0]),
                "assigned_cpa_id": str(row[1]) if row[1] else None,
                "first_name": row[2],
                "last_name": row[3],
                "email": row[4],
                "phone": row[5],
                "is_active": row[6],
                "password_hash": None,
                "user_type": "cpa_client" if row[1] else "consumer",
                "permissions": ["view_own_return", "upload_documents"],
            }
        return None
