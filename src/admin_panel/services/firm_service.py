"""
Firm Service - Core firm management operations.

Handles:
- Firm CRUD operations
- Settings management
- Usage tracking
- Onboarding workflows
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
import logging

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.firm import Firm, FirmSettings
from ..models.user import User
from ..models.subscription import Subscription, SubscriptionPlan


logger = logging.getLogger(__name__)


class FirmService:
    """Service for firm management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # FIRM CRUD
    # =========================================================================

    async def create_firm(
        self,
        name: str,
        admin_email: str,
        admin_name: str,
        password_hash: str,
        subscription_tier: str = "starter",
    ) -> Dict[str, Any]:
        """
        Create a new firm with an admin user.

        This is the main onboarding entry point.
        """
        firm_id = str(uuid4())
        user_id = str(uuid4())
        now = datetime.utcnow()

        # Create firm
        firm = Firm(
            firm_id=firm_id,
            name=name,
            subscription_tier=subscription_tier,
            subscription_status="trial",
            max_team_members=self._get_tier_limits(subscription_tier)["team_members"],
            max_clients=self._get_tier_limits(subscription_tier)["clients"],
            created_at=now,
            updated_at=now,
        )
        self.db.add(firm)

        # Create default settings
        settings = FirmSettings(
            firm_id=firm_id,
            branding_primary_color="#059669",
            email_notifications_enabled=True,
            two_factor_required=False,
            session_timeout_minutes=480,
        )
        self.db.add(settings)

        # Create admin user
        admin = User(
            user_id=user_id,
            firm_id=firm_id,
            email=admin_email,
            name=admin_name,
            password_hash=password_hash,
            role="firm_admin",
            is_active=True,
            email_verified=False,
            created_at=now,
        )
        self.db.add(admin)

        await self.db.commit()

        logger.info(f"Created firm {firm_id} with admin {user_id}")

        return {
            "firm_id": firm_id,
            "user_id": user_id,
            "name": name,
            "subscription_tier": subscription_tier,
            "subscription_status": "trial",
            "trial_ends_at": (now + timedelta(days=14)).isoformat(),
        }

    async def get_firm(self, firm_id: str) -> Optional[Dict[str, Any]]:
        """Get firm details by ID."""
        result = await self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        )
        firm = result.scalar_one_or_none()

        if not firm:
            return None

        return self._firm_to_dict(firm)

    async def update_firm(
        self,
        firm_id: str,
        **updates,
    ) -> Optional[Dict[str, Any]]:
        """Update firm details."""
        result = await self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        )
        firm = result.scalar_one_or_none()

        if not firm:
            return None

        allowed_fields = {
            "name", "legal_name", "ein", "phone", "email",
            "address_line1", "address_line2", "city", "state", "zip_code",
        }

        for field, value in updates.items():
            if field in allowed_fields and hasattr(firm, field):
                setattr(firm, field, value)

        firm.updated_at = datetime.utcnow()
        await self.db.commit()

        return self._firm_to_dict(firm)

    async def delete_firm(self, firm_id: str) -> bool:
        """
        Soft delete a firm.

        Sets status to 'deleted' and anonymizes data after retention period.
        """
        result = await self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        )
        firm = result.scalar_one_or_none()

        if not firm:
            return False

        firm.subscription_status = "deleted"
        firm.deleted_at = datetime.utcnow()
        firm.updated_at = datetime.utcnow()

        await self.db.commit()
        logger.info(f"Soft deleted firm {firm_id}")

        return True

    # =========================================================================
    # SETTINGS
    # =========================================================================

    async def get_settings(self, firm_id: str) -> Optional[Dict[str, Any]]:
        """Get firm settings."""
        result = await self.db.execute(
            select(FirmSettings).where(FirmSettings.firm_id == firm_id)
        )
        settings = result.scalar_one_or_none()

        if not settings:
            return None

        return {
            "firm_id": firm_id,
            "branding": {
                "primary_color": settings.branding_primary_color,
                "logo_url": settings.branding_logo_url,
                "favicon_url": settings.branding_favicon_url,
            },
            "notifications": {
                "email_enabled": settings.email_notifications_enabled,
                "sms_enabled": settings.sms_notifications_enabled,
            },
            "security": {
                "two_factor_required": settings.two_factor_required,
                "session_timeout_minutes": settings.session_timeout_minutes,
                "ip_whitelist": settings.ip_whitelist,
            },
            "integrations": settings.integrations or {},
        }

    async def update_settings(
        self,
        firm_id: str,
        **updates,
    ) -> Optional[Dict[str, Any]]:
        """Update firm settings."""
        result = await self.db.execute(
            select(FirmSettings).where(FirmSettings.firm_id == firm_id)
        )
        settings = result.scalar_one_or_none()

        if not settings:
            return None

        # Handle nested updates
        if "branding" in updates:
            branding = updates["branding"]
            if "primary_color" in branding:
                settings.branding_primary_color = branding["primary_color"]
            if "logo_url" in branding:
                settings.branding_logo_url = branding["logo_url"]
            if "favicon_url" in branding:
                settings.branding_favicon_url = branding["favicon_url"]

        if "notifications" in updates:
            notif = updates["notifications"]
            if "email_enabled" in notif:
                settings.email_notifications_enabled = notif["email_enabled"]
            if "sms_enabled" in notif:
                settings.sms_notifications_enabled = notif["sms_enabled"]

        if "security" in updates:
            sec = updates["security"]
            if "two_factor_required" in sec:
                settings.two_factor_required = sec["two_factor_required"]
            if "session_timeout_minutes" in sec:
                settings.session_timeout_minutes = sec["session_timeout_minutes"]
            if "ip_whitelist" in sec:
                settings.ip_whitelist = sec["ip_whitelist"]

        if "integrations" in updates:
            settings.integrations = updates["integrations"]

        settings.updated_at = datetime.utcnow()
        await self.db.commit()

        return await self.get_settings(firm_id)

    # =========================================================================
    # USAGE & METRICS
    # =========================================================================

    async def get_usage_summary(self, firm_id: str) -> Dict[str, Any]:
        """Get firm usage summary against limits."""
        result = await self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        )
        firm = result.scalar_one_or_none()

        if not firm:
            return {}

        # Count team members
        team_count_result = await self.db.execute(
            select(func.count(User.user_id)).where(
                and_(User.firm_id == firm_id, User.is_active == True)
            )
        )
        team_count = team_count_result.scalar() or 0

        # Count clients (from cpa_panel integration)
        # For now, use stored count or estimate
        client_count = firm.current_client_count or 0

        return {
            "firm_id": firm_id,
            "team_members": {
                "current": team_count,
                "limit": firm.max_team_members,
                "percentage": round((team_count / firm.max_team_members) * 100, 1) if firm.max_team_members > 0 else 0,
            },
            "clients": {
                "current": client_count,
                "limit": firm.max_clients,
                "percentage": round((client_count / firm.max_clients) * 100, 1) if firm.max_clients > 0 else 0,
            },
            "subscription": {
                "tier": firm.subscription_tier,
                "status": firm.subscription_status,
            },
        }

    async def check_limit(
        self,
        firm_id: str,
        resource: str,
    ) -> Dict[str, Any]:
        """Check if firm has capacity for a resource."""
        usage = await self.get_usage_summary(firm_id)

        if resource not in usage:
            return {"allowed": True, "reason": None}

        resource_usage = usage.get(resource, {})
        current = resource_usage.get("current", 0)
        limit = resource_usage.get("limit", 0)

        if current >= limit:
            return {
                "allowed": False,
                "reason": f"Reached {resource} limit ({current}/{limit})",
                "upgrade_suggested": True,
            }

        return {"allowed": True, "remaining": limit - current}

    # =========================================================================
    # ONBOARDING
    # =========================================================================

    async def get_onboarding_status(self, firm_id: str) -> Dict[str, Any]:
        """Get onboarding checklist status."""
        result = await self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        )
        firm = result.scalar_one_or_none()

        if not firm:
            return {}

        settings_result = await self.db.execute(
            select(FirmSettings).where(FirmSettings.firm_id == firm_id)
        )
        settings = settings_result.scalar_one_or_none()

        # Count team members
        team_count_result = await self.db.execute(
            select(func.count(User.user_id)).where(User.firm_id == firm_id)
        )
        team_count = team_count_result.scalar() or 0

        checklist = {
            "profile_completed": bool(firm.phone and firm.email),
            "branding_configured": bool(settings and settings.branding_logo_url),
            "team_invited": team_count > 1,
            "first_client_added": (firm.current_client_count or 0) > 0,
            "payment_configured": firm.subscription_status == "active",
        }

        completed = sum(1 for v in checklist.values() if v)
        total = len(checklist)

        return {
            "checklist": checklist,
            "completed": completed,
            "total": total,
            "percentage": round((completed / total) * 100),
            "is_complete": completed == total,
        }

    async def complete_onboarding(self, firm_id: str) -> bool:
        """Mark firm onboarding as complete."""
        result = await self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        )
        firm = result.scalar_one_or_none()

        if not firm:
            return False

        firm.onboarded_at = datetime.utcnow()
        firm.updated_at = datetime.utcnow()
        await self.db.commit()

        return True

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_tier_limits(self, tier: str) -> Dict[str, int]:
        """Get limits for a subscription tier."""
        limits = {
            "starter": {"team_members": 3, "clients": 100},
            "professional": {"team_members": 10, "clients": 500},
            "enterprise": {"team_members": 50, "clients": 2500},
        }
        return limits.get(tier, limits["starter"])

    def _firm_to_dict(self, firm: Firm) -> Dict[str, Any]:
        """Convert firm model to dictionary."""
        return {
            "firm_id": str(firm.firm_id),
            "name": firm.name,
            "legal_name": firm.legal_name,
            "ein": firm.ein,
            "phone": firm.phone,
            "email": firm.email,
            "address": {
                "line1": firm.address_line1,
                "line2": firm.address_line2,
                "city": firm.city,
                "state": firm.state,
                "zip_code": firm.zip_code,
            },
            "subscription_tier": firm.subscription_tier,
            "subscription_status": firm.subscription_status,
            "limits": {
                "team_members": firm.max_team_members,
                "clients": firm.max_clients,
            },
            "created_at": firm.created_at.isoformat() if firm.created_at else None,
            "onboarded_at": firm.onboarded_at.isoformat() if firm.onboarded_at else None,
        }
