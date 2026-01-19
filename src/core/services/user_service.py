"""
Core User Service

Unified user management for all user types:
- Profile management
- Preferences
- User lookup with role-based filtering

This service provides user operations that work consistently
across Consumer Portal, CPA Panel, and Admin Panel.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from ..models.user import UnifiedUser, UserType, UserProfile, UserPreferences, UserContext
from .auth_service import get_auth_service

logger = logging.getLogger(__name__)


class CoreUserService:
    """
    Unified user management service.

    Provides:
    - User profile retrieval and updates
    - User preferences management
    - User search with role-based filtering
    """

    def __init__(self):
        self._auth_service = get_auth_service()
        self._preferences_db: Dict[str, UserPreferences] = {}  # user_id -> preferences

    # =========================================================================
    # PROFILE MANAGEMENT
    # =========================================================================

    async def get_profile(self, user_id: str, context: UserContext) -> Optional[UserProfile]:
        """
        Get user profile.

        Access control:
        - Users can always see their own profile
        - CPA team can see clients in their firm
        - Platform admins can see all profiles
        """
        # Check access
        user = self._auth_service.get_user_by_id(user_id)
        if not user:
            return None

        if not context.can_access_user(user_id, user.firm_id):
            logger.warning(f"Access denied: {context.user_id} cannot view {user_id}")
            return None

        return UserProfile.from_user(user)

    async def get_my_profile(self, context: UserContext) -> Optional[UserProfile]:
        """Get current user's profile."""
        return await self.get_profile(context.user_id, context)

    async def update_profile(
        self,
        user_id: str,
        context: UserContext,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Optional[UserProfile]:
        """
        Update user profile.

        Access control:
        - Users can update their own profile
        - Firm admins can update users in their firm
        - Platform admins can update any profile
        """
        user = self._auth_service.get_user_by_id(user_id)
        if not user:
            return None

        # Check access
        can_update = (
            context.user_id == user_id or  # Own profile
            context.user_type == UserType.PLATFORM_ADMIN or  # Platform admin
            (
                context.user_type == UserType.CPA_TEAM and
                context.has_permission("manage_team") and
                context.firm_id == user.firm_id
            )
        )

        if not can_update:
            logger.warning(f"Update denied: {context.user_id} cannot update {user_id}")
            return None

        # Update fields
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if phone is not None:
            user.phone = phone
        if avatar_url is not None:
            user.avatar_url = avatar_url

        user.updated_at = datetime.utcnow()

        logger.info(f"Profile updated: {user_id} by {context.user_id}")

        return UserProfile.from_user(user)

    # =========================================================================
    # PREFERENCES MANAGEMENT
    # =========================================================================

    async def get_preferences(self, context: UserContext) -> UserPreferences:
        """Get current user's preferences."""
        if context.user_id in self._preferences_db:
            return self._preferences_db[context.user_id]

        # Return defaults
        return UserPreferences(user_id=context.user_id)

    async def update_preferences(
        self,
        context: UserContext,
        **updates
    ) -> UserPreferences:
        """Update current user's preferences."""
        prefs = await self.get_preferences(context)

        # Update fields
        for key, value in updates.items():
            if hasattr(prefs, key) and value is not None:
                setattr(prefs, key, value)

        # Save
        self._preferences_db[context.user_id] = prefs

        logger.info(f"Preferences updated: {context.user_id}")

        return prefs

    # =========================================================================
    # USER SEARCH
    # =========================================================================

    async def search_users(
        self,
        context: UserContext,
        query: Optional[str] = None,
        user_type: Optional[UserType] = None,
        firm_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserProfile]:
        """
        Search users with role-based filtering.

        Access control:
        - Consumers: Can only see themselves
        - CPA clients: Can only see themselves and their assigned CPA
        - CPA team: Can see users in their firm
        - Platform admins: Can see all users
        """
        results = []

        # Get all users from auth service (in production: database query)
        all_users = [
            u for u in self._auth_service._users_db.values()
            if isinstance(u, UnifiedUser)
        ]

        # Remove duplicates (email keys)
        seen_ids = set()
        unique_users = []
        for user in all_users:
            if user.id not in seen_ids:
                seen_ids.add(user.id)
                unique_users.append(user)

        for user in unique_users:
            # Apply role-based filtering
            if context.user_type == UserType.CONSUMER:
                # Consumers can only see themselves
                if user.id != context.user_id:
                    continue

            elif context.user_type == UserType.CPA_CLIENT:
                # CPA clients can see themselves and their CPA
                if user.id != context.user_id and user.id != context.assigned_cpa_id:
                    continue

            elif context.user_type == UserType.CPA_TEAM:
                # CPA team can see users in their firm
                if user.firm_id != context.firm_id:
                    continue

            # Platform admins see all (no filter)

            # Apply search filters
            if user_type and user.user_type != user_type:
                continue

            if firm_id and user.firm_id != firm_id:
                continue

            if query:
                query_lower = query.lower()
                if not (
                    query_lower in user.email.lower() or
                    query_lower in user.first_name.lower() or
                    query_lower in user.last_name.lower()
                ):
                    continue

            results.append(UserProfile.from_user(user))

        # Apply pagination
        return results[offset:offset + limit]

    async def get_firm_users(
        self,
        firm_id: str,
        context: UserContext,
        user_type: Optional[UserType] = None
    ) -> List[UserProfile]:
        """
        Get all users in a firm.

        Access control:
        - CPA team: Can see users in their own firm
        - Platform admins: Can see users in any firm
        """
        if not context.can_access_firm(firm_id):
            logger.warning(f"Firm access denied: {context.user_id} cannot view firm {firm_id}")
            return []

        return await self.search_users(
            context=context,
            firm_id=firm_id,
            user_type=user_type
        )

    async def get_cpa_clients(
        self,
        cpa_id: str,
        context: UserContext
    ) -> List[UserProfile]:
        """
        Get all clients assigned to a CPA.

        Access control:
        - CPAs can see their own clients
        - Firm admins can see all clients in firm
        - Platform admins can see all
        """
        # Verify access
        if context.user_type == UserType.CPA_TEAM:
            if context.user_id != cpa_id and not context.has_permission("manage_team"):
                logger.warning(f"Access denied: {context.user_id} cannot view clients of {cpa_id}")
                return []

        results = []
        all_users = [
            u for u in self._auth_service._users_db.values()
            if isinstance(u, UnifiedUser)
        ]

        seen_ids = set()
        for user in all_users:
            if user.id in seen_ids:
                continue
            seen_ids.add(user.id)

            if user.user_type == UserType.CPA_CLIENT and user.assigned_cpa_id == cpa_id:
                results.append(UserProfile.from_user(user))

        return results

    # =========================================================================
    # USER STATISTICS
    # =========================================================================

    async def get_user_stats(self, context: UserContext) -> Dict[str, Any]:
        """
        Get user statistics.

        Access control:
        - CPA team: Stats for their firm
        - Platform admins: Platform-wide stats
        """
        all_users = [
            u for u in self._auth_service._users_db.values()
            if isinstance(u, UnifiedUser)
        ]

        # Remove duplicates
        seen_ids = set()
        unique_users = []
        for user in all_users:
            if user.id not in seen_ids:
                seen_ids.add(user.id)
                unique_users.append(user)

        # Filter by firm for CPA team
        if context.user_type == UserType.CPA_TEAM:
            unique_users = [u for u in unique_users if u.firm_id == context.firm_id]

        # Calculate stats
        stats = {
            "total_users": len(unique_users),
            "by_type": {
                "consumers": len([u for u in unique_users if u.user_type == UserType.CONSUMER]),
                "cpa_clients": len([u for u in unique_users if u.user_type == UserType.CPA_CLIENT]),
                "cpa_team": len([u for u in unique_users if u.user_type == UserType.CPA_TEAM]),
                "platform_admins": len([u for u in unique_users if u.user_type == UserType.PLATFORM_ADMIN])
            },
            "active_users": len([u for u in unique_users if u.is_active]),
            "verified_users": len([u for u in unique_users if u.email_verified])
        }

        return stats


# =============================================================================
# SERVICE SINGLETON
# =============================================================================

_user_service: Optional[CoreUserService] = None


def get_user_service() -> CoreUserService:
    """Get the singleton user service instance."""
    global _user_service
    if _user_service is None:
        _user_service = CoreUserService()
    return _user_service
