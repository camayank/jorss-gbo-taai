"""
Auto-Save Manager

Prevents data loss by automatically saving session state to database at regular intervals.

Features:
- Background auto-save loop
- Batched saves for efficiency
- Conflict detection via optimistic locking
- Error recovery

Usage in FastAPI:
    from src.web.auto_save import get_auto_save_manager

    @app.on_event("startup")
    async def startup():
        auto_save = get_auto_save_manager()
        asyncio.create_task(auto_save.start())

    # In your endpoint:
    auto_save = get_auto_save_manager()
    auto_save.mark_dirty(session_id, session_data)
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.database.unified_session import UnifiedFilingSession
from src.database.session_persistence import get_session_persistence

logger = logging.getLogger(__name__)


@dataclass
class PendingSave:
    """Represents a session waiting to be saved"""
    session: UnifiedFilingSession
    marked_at: datetime
    attempt_count: int = 0


class AutoSaveManager:
    """
    Manages automatic saving of filing sessions to prevent data loss.

    This runs as a background task and periodically flushes dirty sessions
    to the database.
    """

    def __init__(
        self,
        save_interval_seconds: int = 30,
        max_retry_attempts: int = 3,
        batch_size: int = 10
    ):
        """
        Initialize auto-save manager.

        Args:
            save_interval_seconds: How often to flush saves (default: 30s)
            max_retry_attempts: Max retry attempts for failed saves
            batch_size: Max sessions to save per batch
        """
        self.save_interval = save_interval_seconds
        self.max_retry_attempts = max_retry_attempts
        self.batch_size = batch_size

        # Pending saves: session_id -> PendingSave
        self._pending: Dict[str, PendingSave] = {}

        # Stats
        self._total_saves = 0
        self._failed_saves = 0
        self._running = False

        logger.info(f"AutoSaveManager initialized (interval={save_interval_seconds}s)")

    def mark_dirty(self, session: UnifiedFilingSession) -> None:
        """
        Mark a session as needing to be saved.

        This is called by API endpoints after modifying session data.

        Args:
            session: Session to save
        """
        self._pending[session.session_id] = PendingSave(
            session=session,
            marked_at=datetime.utcnow()
        )

        logger.debug(f"Session {session.session_id} marked for auto-save ({len(self._pending)} pending)")

    async def start(self) -> None:
        """
        Start the auto-save background loop.

        This should be called on application startup.
        """
        if self._running:
            logger.warning("AutoSaveManager already running")
            return

        self._running = True
        logger.info("AutoSaveManager started")

        try:
            while self._running:
                await asyncio.sleep(self.save_interval)
                await self.flush()
        except Exception as e:
            logger.error(f"AutoSaveManager crashed: {e}")
            self._running = False

    def stop(self) -> None:
        """Stop the auto-save loop."""
        self._running = False
        logger.info("AutoSaveManager stopped")

    async def flush(self, force_all: bool = False) -> int:
        """
        Flush pending saves to database.

        Args:
            force_all: If True, save all pending sessions (ignore batch size)

        Returns:
            Number of sessions saved
        """
        if not self._pending:
            return 0

        persistence = get_session_persistence()
        saved_count = 0
        failed_sessions = []

        # Get sessions to save (respect batch size unless forced)
        to_save = list(self._pending.items())
        if not force_all:
            to_save = to_save[:self.batch_size]

        logger.debug(f"Flushing {len(to_save)} sessions to database")

        for session_id, pending_save in to_save:
            try:
                # Save with optimistic locking
                success = persistence.save_with_version(
                    session=pending_save.session,
                    expected_version=pending_save.session.version,
                    tenant_id="default"
                )

                if success:
                    # Remove from pending
                    del self._pending[session_id]
                    saved_count += 1
                    self._total_saves += 1
                else:
                    # Version conflict - retry on next flush
                    logger.warning(f"Version conflict saving session {session_id}, will retry")
                    pending_save.attempt_count += 1

                    if pending_save.attempt_count >= self.max_retry_attempts:
                        logger.error(f"Max retries exceeded for session {session_id}, dropping")
                        del self._pending[session_id]
                        self._failed_saves += 1

            except Exception as e:
                logger.error(f"Failed to save session {session_id}: {e}")
                pending_save.attempt_count += 1

                if pending_save.attempt_count >= self.max_retry_attempts:
                    logger.error(f"Max retries exceeded for session {session_id}, dropping")
                    del self._pending[session_id]
                    self._failed_saves += 1

        if saved_count > 0:
            logger.info(f"Auto-saved {saved_count} sessions ({len(self._pending)} still pending)")

        return saved_count

    def get_stats(self) -> Dict[str, any]:
        """Get auto-save statistics."""
        return {
            "running": self._running,
            "pending_count": len(self._pending),
            "total_saves": self._total_saves,
            "failed_saves": self._failed_saves,
            "save_interval_seconds": self.save_interval
        }

    def get_pending_session_ids(self) -> list[str]:
        """Get list of session IDs waiting to be saved."""
        return list(self._pending.keys())


# Global instance
_auto_save_manager: Optional[AutoSaveManager] = None


def get_auto_save_manager() -> AutoSaveManager:
    """Get the global auto-save manager instance."""
    global _auto_save_manager
    if _auto_save_manager is None:
        _auto_save_manager = AutoSaveManager()
    return _auto_save_manager


def initialize_auto_save(
    save_interval_seconds: int = 30,
    max_retry_attempts: int = 3,
    batch_size: int = 10
) -> AutoSaveManager:
    """
    Initialize the global auto-save manager with custom settings.

    Call this on application startup before starting the manager.

    Args:
        save_interval_seconds: How often to flush saves
        max_retry_attempts: Max retry attempts for failed saves
        batch_size: Max sessions to save per batch

    Returns:
        AutoSaveManager instance
    """
    global _auto_save_manager
    _auto_save_manager = AutoSaveManager(
        save_interval_seconds=save_interval_seconds,
        max_retry_attempts=max_retry_attempts,
        batch_size=batch_size
    )
    return _auto_save_manager


# Convenience function for marking sessions dirty from API endpoints
def mark_session_for_auto_save(session: UnifiedFilingSession) -> None:
    """
    Mark a session for auto-save.

    Call this from API endpoints after modifying session data.

    Example:
        session.extracted_data.update(new_data)
        mark_session_for_auto_save(session)
    """
    manager = get_auto_save_manager()
    manager.mark_dirty(session)
