"""
Auto-Save API Endpoints

Provides manual trigger for auto-save and status information.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.web.auto_save import get_auto_save_manager
from src.database.session_persistence import get_session_persistence
from src.database.unified_session import UnifiedFilingSession

router = APIRouter(prefix="/api/auto-save", tags=["auto-save"])


class AutoSaveRequest(BaseModel):
    """Request to manually trigger auto-save for a session"""
    session_id: str


class AutoSaveResponse(BaseModel):
    """Response from auto-save operation"""
    success: bool
    message: str
    last_save_time: Optional[str] = None


class AutoSaveStatsResponse(BaseModel):
    """Auto-save manager statistics"""
    running: bool
    pending_count: int
    total_saves: int
    failed_saves: int
    save_interval_seconds: int


@router.post("/trigger", response_model=AutoSaveResponse)
async def trigger_auto_save(request: AutoSaveRequest):
    """
    Manually trigger auto-save for a specific session.

    This is useful for providing immediate user feedback ("Saving...").
    The background auto-save will still run on its normal schedule.

    Args:
        request: Contains session_id to save

    Returns:
        Success status and last save time
    """
    try:
        # Load session
        persistence = get_session_persistence()
        session = persistence.load_unified_session(request.session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Mark for auto-save (will be picked up on next flush)
        auto_save = get_auto_save_manager()
        auto_save.mark_dirty(session)

        # Force immediate flush
        saved_count = await auto_save.flush(force_all=False)

        return AutoSaveResponse(
            success=True,
            message=f"Session {request.session_id} saved successfully",
            last_save_time=auto_save.get_stats().get("last_save_time")
        )

    except HTTPException:
        raise
    except Exception as e:
        return AutoSaveResponse(
            success=False,
            message=f"Auto-save failed: {str(e)}"
        )


@router.get("/stats", response_model=AutoSaveStatsResponse)
async def get_auto_save_stats():
    """
    Get auto-save manager statistics.

    Useful for monitoring and debugging.

    Returns:
        Statistics including pending count, total saves, failures
    """
    auto_save = get_auto_save_manager()
    stats = auto_save.get_stats()

    return AutoSaveStatsResponse(**stats)


@router.post("/flush")
async def flush_auto_save():
    """
    Force immediate flush of all pending auto-saves.

    This is an admin/maintenance endpoint.

    Returns:
        Number of sessions saved
    """
    auto_save = get_auto_save_manager()
    saved_count = await auto_save.flush(force_all=True)

    return {
        "success": True,
        "message": f"Flushed {saved_count} pending saves",
        "saved_count": saved_count
    }
