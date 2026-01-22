"""
Session Management API

Endpoints for managing user filing sessions:
- List all user sessions
- Resume existing sessions
- Transfer anonymous sessions after login
- Check for active sessions
- Delete sessions

These endpoints support the "resume banner" and session recovery features.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from src.database.unified_session import FilingState, WorkflowType
from src.database.session_persistence import get_session_persistence

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["session-management"])

# Import auth dependency (adjust path as needed)
try:
    from src.auth.auth_context import AuthContext, require_auth
except ImportError:
    # Fallback for testing
    class AuthContext:
        user_id: str
        role: Any

    def require_auth():
        pass


# =============================================================================
# Request/Response Models
# =============================================================================

class SessionSummary(BaseModel):
    """Summary of a filing session"""
    session_id: str
    workflow_type: str
    state: str
    tax_year: int
    completeness_score: float
    created_at: str
    updated_at: str


class CheckActiveResponse(BaseModel):
    """Response for active session check"""
    has_active_session: bool
    session_id: Optional[str] = None
    workflow_type: Optional[str] = None
    state: Optional[str] = None
    tax_year: Optional[int] = None
    completeness_score: Optional[float] = None


class TransferSessionRequest(BaseModel):
    """Request to transfer anonymous session to authenticated user"""
    anonymous_session_id: str


# =============================================================================
# Session Listing & Discovery
# =============================================================================

@router.get("/my-sessions", response_model=List[SessionSummary])
async def list_my_sessions(
    tax_year: Optional[int] = None,
    workflow_type: Optional[str] = None,
    ctx: AuthContext = Depends(require_auth)
):
    """
    List all active sessions for the current user.

    Query Parameters:
        - tax_year: Filter by tax year
        - workflow_type: Filter by workflow (express, smart, chat, guided)
    """
    try:
        persistence = get_session_persistence()
        sessions = persistence.get_user_sessions(
            str(ctx.user_id),
            workflow_type=workflow_type,
            tax_year=tax_year
        )

        return [
            SessionSummary(
                session_id=s.session_id,
                workflow_type=s.workflow_type.value,
                state=s.state.value,
                tax_year=s.tax_year,
                completeness_score=s.completeness_score,
                created_at=s.created_at,
                updated_at=s.updated_at
            )
            for s in sessions
        ]

    except Exception as e:
        logger.error(f"Failed to list sessions for user {ctx.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SessionListFailed", "message": str(e)}
        )


@router.get("/check-active", response_model=CheckActiveResponse)
async def check_active_session(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Check if user has an active session.

    Used for the "resume banner" on landing page.

    Query Parameters:
        - user_id: Check for authenticated user (optional)
        - session_id: Check specific session (for anonymous users)
    """
    try:
        persistence = get_session_persistence()
        result = persistence.check_active_session(
            user_id=user_id,
            session_id=session_id
        )

        if result:
            return CheckActiveResponse(
                has_active_session=True,
                session_id=result["session_id"],
                workflow_type=result.get("workflow_type"),
                state=result.get("state"),
                tax_year=result.get("tax_year"),
                completeness_score=result.get("completeness_score")
            )
        else:
            return CheckActiveResponse(has_active_session=False)

    except Exception as e:
        logger.error(f"Failed to check active session: {e}")
        # Don't fail the request, just return no active session
        return CheckActiveResponse(has_active_session=False)


# =============================================================================
# Session Resume & Recovery
# =============================================================================

@router.post("/{session_id}/resume")
async def resume_session(
    session_id: str,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Resume a previous filing session.

    Extends session expiry and returns current state.
    """
    try:
        persistence = get_session_persistence()
        session = persistence.load_unified_session(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "SessionNotFound", "message": f"Session {session_id} not found"}
            )

        # Verify ownership
        if session.user_id != str(ctx.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "AccessDenied", "message": "You don't own this session"}
            )

        # Touch session to extend expiry
        persistence.touch_session(session_id)

        logger.info(f"User {ctx.user_id} resumed session {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "redirect": f"/file?session_id={session_id}",
            "state": session.state.value,
            "completeness_score": session.completeness_score
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ResumeFailed", "message": str(e)}
        )


# =============================================================================
# Anonymous → Authenticated Transfer
# =============================================================================

@router.post("/transfer-anonymous")
async def transfer_anonymous_session(
    request: TransferSessionRequest,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Claim an anonymous session after logging in.

    This allows users to:
    1. Start filing anonymously
    2. Login later
    3. Continue with the same session

    Usage:
        User starts filing → session_id saved in browser
        User logs in → frontend calls this endpoint
        Session transferred to user account
    """
    try:
        persistence = get_session_persistence()

        success = persistence.transfer_session_to_user(
            session_id=request.anonymous_session_id,
            user_id=str(ctx.user_id)
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "TransferFailed",
                    "message": "Session not found or already claimed"
                }
            )

        logger.info(f"Transferred session {request.anonymous_session_id} to user {ctx.user_id}")

        return {
            "success": True,
            "message": "Session transferred successfully",
            "session_id": request.anonymous_session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to transfer session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TransferFailed", "message": str(e)}
        )


# =============================================================================
# Session Deletion
# =============================================================================

@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    ctx: AuthContext = Depends(require_auth)
):
    """
    Delete a filing session.

    WARNING: This permanently deletes all session data.
    """
    try:
        persistence = get_session_persistence()
        session = persistence.load_unified_session(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "SessionNotFound"}
            )

        # Verify ownership
        if session.user_id != str(ctx.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "AccessDenied"}
            )

        # Don't allow deleting completed returns
        if session.state == FilingState.COMPLETE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "CannotDelete",
                    "message": "Cannot delete completed returns"
                }
            )

        # Delete
        persistence.delete_session(session_id)

        logger.info(f"User {ctx.user_id} deleted session {session_id}")

        return {"success": True, "message": "Session deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "DeleteFailed", "message": str(e)}
        )


# =============================================================================
# Session Cleanup (Background Task)
# =============================================================================

@router.post("/cleanup-expired")
async def cleanup_expired_sessions():
    """
    Cleanup expired sessions.

    This endpoint should be called by a background job periodically
    (e.g., cron job every hour).

    No auth required - can be called from internal scheduler.
    """
    try:
        persistence = get_session_persistence()
        deleted_count = persistence.cleanup_expired_sessions()

        logger.info(f"Cleaned up {deleted_count} expired sessions")

        return {
            "success": True,
            "deleted_count": deleted_count,
            "cleaned_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Session cleanup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "CleanupFailed", "message": str(e)}
        )


# =============================================================================
# Session Analytics (Optional)
# =============================================================================

@router.get("/stats")
async def get_session_stats(ctx: AuthContext = Depends(require_auth)):
    """
    Get session statistics for the current user.

    Returns:
        - Total sessions
        - Sessions by workflow type
        - Sessions by state
        - Completion rate
    """
    try:
        persistence = get_session_persistence()
        sessions = persistence.get_user_sessions(str(ctx.user_id))

        # Calculate stats
        total = len(sessions)
        by_workflow = {}
        by_state = {}
        completed = 0

        for session in sessions:
            # Count by workflow
            workflow = session.workflow_type.value
            by_workflow[workflow] = by_workflow.get(workflow, 0) + 1

            # Count by state
            state = session.state.value
            by_state[state] = by_state.get(state, 0) + 1

            # Count completed
            if session.state == FilingState.COMPLETE:
                completed += 1

        completion_rate = (completed / total * 100) if total > 0 else 0

        return {
            "total_sessions": total,
            "by_workflow": by_workflow,
            "by_state": by_state,
            "completed": completed,
            "completion_rate": round(completion_rate, 1)
        }

    except Exception as e:
        logger.error(f"Failed to get session stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "StatsFailed", "message": str(e)}
        )


# =============================================================================
# Session Creation Endpoint (for UI compatibility)
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new filing session"""
    workflow_type: Optional[str] = "guided"
    tax_year: Optional[int] = 2025


@router.post("/create-session")
async def create_filing_session(request: CreateSessionRequest = CreateSessionRequest()):
    """
    Create a new filing session.

    This endpoint is called by the UI when a user starts a new tax return.
    Returns a session_id that the UI uses to track the filing session.
    """
    try:
        import uuid
        persistence = get_session_persistence()

        # Generate session ID
        session_id = str(uuid.uuid4())

        # Create session data
        session_data = {
            "session_id": session_id,
            "workflow_type": request.workflow_type or "guided",
            "state": "entry",
            "tax_year": request.tax_year or 2025,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "completeness_score": 0.0,
            "confidence_score": 0.0,
            "user_id": None,  # Anonymous for now
            "is_anonymous": True,
            "data": {}  # Empty data dict for now
        }

        # Save session
        persistence.save_session(session_id, session_data)

        logger.info(f"Created new filing session: {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "workflow_type": session_data["workflow_type"],
            "tax_year": session_data["tax_year"],
            "message": "Session created successfully"
        }

    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SessionCreationFailed", "message": str(e)}
        )
