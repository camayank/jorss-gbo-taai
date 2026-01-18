"""
Session Adapter for CPA Panel

Provides access to session persistence and management
from the core platform.
"""

from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class SessionAdapter:
    """
    Adapter for accessing session data from the core platform.

    Provides isolation between CPA panel and core session management.
    """

    def __init__(self):
        """Initialize the adapter."""
        self._persistence = None

    def _get_persistence(self):
        """Get or create persistence layer."""
        if self._persistence is None:
            try:
                from database.session_persistence import get_session_persistence
                self._persistence = get_session_persistence()
            except ImportError:
                logger.warning("Could not import session persistence")
                self._persistence = None
        return self._persistence

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session state from persistence.

        Args:
            session_id: Session identifier

        Returns:
            Session state dict or None
        """
        persistence = self._get_persistence()
        if not persistence:
            return None

        try:
            return persistence.load_session(session_id)
        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return None

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        state = self.get_session_state(session_id)
        return state is not None

    def list_sessions(
        self,
        tenant_id: str = "default",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List sessions for a tenant.

        Args:
            tenant_id: Tenant identifier
            limit: Max results
            offset: Pagination offset

        Returns:
            List of session summaries
        """
        persistence = self._get_persistence()
        if not persistence:
            return []

        try:
            if hasattr(persistence, 'list_sessions'):
                return persistence.list_sessions(tenant_id, limit, offset)
            return []
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []

    def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        """
        Get session metadata (creation time, last update, etc.).

        Args:
            session_id: Session identifier

        Returns:
            Metadata dict
        """
        state = self.get_session_state(session_id)
        if not state:
            return {}

        return {
            "session_id": session_id,
            "created_at": state.get("created_at"),
            "updated_at": state.get("updated_at"),
            "tenant_id": state.get("tenant_id", "default"),
        }
