"""
CPA Notification API Routes

Endpoints for managing CPA notifications:
1. List notifications (read/unread)
2. Mark as read
3. Get notification preferences
4. Update notification preferences
5. Get due follow-up reminders
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from .common import get_tenant_id, get_cpa_auth_context

logger = logging.getLogger(__name__)


def _get_authenticated_cpa_email(request: Request) -> str:
    """
    Get authenticated CPA email from request.

    SECURITY: Does NOT trust headers - uses proper authentication.
    Raises HTTPException if not authenticated.
    """
    auth = get_cpa_auth_context(request)

    if not auth.is_authenticated:
        logger.warning(
            f"[SECURITY] Unauthenticated notification access attempt | "
            f"ip={request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access notifications"
        )

    if not auth.email:
        raise HTTPException(
            status_code=401,
            detail="CPA email not found in authentication context"
        )

    return auth.email

notification_router = APIRouter(tags=["CPA Notifications"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class NotificationPreferences(BaseModel):
    """CPA notification preferences."""
    email_new_leads: bool = Field(True, description="Email on new lead capture")
    email_hot_leads: bool = Field(True, description="Immediate email for hot leads (score > 80)")
    email_daily_digest: bool = Field(True, description="Daily summary email")
    email_follow_up_reminders: bool = Field(True, description="Follow-up reminder emails")
    in_app_enabled: bool = Field(True, description="Show in-app notifications")
    digest_time: str = Field("08:00", description="Daily digest time (HH:MM)")


class MarkReadRequest(BaseModel):
    """Request to mark notifications as read."""
    notification_ids: List[str] = Field(..., description="List of notification IDs to mark as read")


# =============================================================================
# NOTIFICATION ENDPOINTS
# =============================================================================

@notification_router.get("/notifications")
async def list_notifications(
    request: Request,
    unread_only: bool = Query(False, description="Only return unread notifications"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List notifications for the current CPA.

    Returns recent notifications with read/unread status.
    """
    try:
        from cpa_panel.services.notification_service import get_notification_service
        service = get_notification_service()

        cpa_email = _get_authenticated_cpa_email(request)

        # Get notifications from database
        conn = service._get_db_connection()
        cursor = conn.cursor()

        if unread_only:
            cursor.execute("""
                SELECT * FROM notifications
                WHERE recipient_email = ? AND status != 'read'
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (cpa_email, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM notifications
                WHERE recipient_email = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (cpa_email, limit, offset))

        rows = cursor.fetchall()

        # Get total count
        cursor.execute("""
            SELECT COUNT(*) as count FROM notifications
            WHERE recipient_email = ?
        """, (cpa_email,))
        total_count = cursor.fetchone()["count"]

        # Get unread count
        cursor.execute("""
            SELECT COUNT(*) as count FROM notifications
            WHERE recipient_email = ? AND status != 'read'
        """, (cpa_email,))
        unread_count = cursor.fetchone()["count"]

        conn.close()

        notifications = []
        for row in rows:
            notifications.append({
                "notification_id": row["notification_id"],
                "type": row["notification_type"],
                "subject": row["subject"],
                "body_preview": (row["body"] or "")[:150] + "..." if row["body"] and len(row["body"]) > 150 else row["body"],
                "status": row["status"],
                "created_at": row["created_at"],
                "is_unread": row["status"] != "read",
            })

        return JSONResponse({
            "notifications": notifications,
            "total_count": total_count,
            "unread_count": unread_count,
            "limit": limit,
            "offset": offset,
        })

    except Exception as e:
        logger.error(f"Failed to list notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@notification_router.post("/notifications/mark-read")
async def mark_notifications_read(request: Request, data: MarkReadRequest):
    """
    Mark notifications as read.

    Can mark multiple notifications at once.
    """
    try:
        from cpa_panel.services.notification_service import get_notification_service
        service = get_notification_service()

        conn = service._get_db_connection()
        cursor = conn.cursor()

        for notification_id in data.notification_ids:
            cursor.execute("""
                UPDATE notifications
                SET status = 'read'
                WHERE notification_id = ?
            """, (notification_id,))

        conn.commit()
        conn.close()

        return JSONResponse({
            "success": True,
            "marked_count": len(data.notification_ids),
        })

    except Exception as e:
        logger.error(f"Failed to mark notifications as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@notification_router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(request: Request):
    """
    Mark all notifications as read for the current CPA.
    """
    try:
        from cpa_panel.services.notification_service import get_notification_service
        service = get_notification_service()

        cpa_email = _get_authenticated_cpa_email(request)

        conn = service._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notifications
            SET status = 'read'
            WHERE recipient_email = ? AND status != 'read'
        """, (cpa_email,))
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()

        return JSONResponse({
            "success": True,
            "marked_count": updated_count,
        })

    except Exception as e:
        logger.error(f"Failed to mark all notifications as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# NOTIFICATION PREFERENCES
# =============================================================================

@notification_router.get("/notifications/preferences")
async def get_notification_preferences(request: Request):
    """
    Get notification preferences for the current CPA.

    Returns stored preferences from database, or defaults if none set.
    """
    try:
        from cpa_panel.services.notification_service import get_notification_service

        cpa_email = _get_authenticated_cpa_email(request)
        service = get_notification_service()

        # Fetch from database
        stored_preferences = service.get_notification_preferences(cpa_email)

        return JSONResponse({
            "preferences": stored_preferences,
            "cpa_email": cpa_email,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve notification preferences")


@notification_router.put("/notifications/preferences")
async def update_notification_preferences(request: Request, preferences: NotificationPreferences):
    """
    Update notification preferences for the current CPA.

    Persists preferences to database.
    """
    try:
        from cpa_panel.services.notification_service import get_notification_service

        cpa_email = _get_authenticated_cpa_email(request)
        service = get_notification_service()

        # Persist to database
        success = service.update_notification_preferences(
            cpa_email=cpa_email,
            preferences=preferences.model_dump()
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save preferences")

        logger.info(f"Updated notification preferences for {cpa_email}")

        return JSONResponse({
            "success": True,
            "preferences": preferences.model_dump(),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to update notification preferences")


# =============================================================================
# FOLLOW-UP REMINDERS
# =============================================================================

@notification_router.get("/reminders")
async def get_follow_up_reminders(
    request: Request,
    include_completed: bool = Query(False, description="Include completed reminders"),
):
    """
    Get follow-up reminders for the current CPA.

    Returns reminders sorted by due date, with overdue reminders first.
    """
    try:
        from cpa_panel.services.notification_service import get_notification_service
        service = get_notification_service()

        cpa_email = _get_authenticated_cpa_email(request)

        conn = service._get_db_connection()
        cursor = conn.cursor()

        if include_completed:
            cursor.execute("""
                SELECT r.*, l.first_name, l.email as lead_email
                FROM follow_up_reminders r
                LEFT JOIN lead_magnet_leads l ON r.lead_id = l.lead_id
                WHERE r.cpa_email = ?
                ORDER BY r.completed ASC, r.due_date ASC
            """, (cpa_email,))
        else:
            cursor.execute("""
                SELECT r.*, l.first_name, l.email as lead_email
                FROM follow_up_reminders r
                LEFT JOIN lead_magnet_leads l ON r.lead_id = l.lead_id
                WHERE r.cpa_email = ? AND r.completed = 0
                ORDER BY r.due_date ASC
            """, (cpa_email,))

        rows = cursor.fetchall()
        conn.close()

        now = datetime.utcnow()
        reminders = []
        overdue_count = 0

        for row in rows:
            due_date = datetime.fromisoformat(row["due_date"]) if row["due_date"] else None
            is_overdue = due_date and due_date < now and not row["completed"]

            if is_overdue:
                overdue_count += 1

            reminders.append({
                "reminder_id": row["reminder_id"],
                "lead_id": row["lead_id"],
                "lead_name": row["first_name"] if "first_name" in row.keys() else None,
                "lead_email": row["lead_email"] if "lead_email" in row.keys() else None,
                "due_date": row["due_date"],
                "reminder_type": row["reminder_type"],
                "completed": bool(row["completed"]),
                "completed_at": row["completed_at"],
                "is_overdue": is_overdue,
            })

        return JSONResponse({
            "reminders": reminders,
            "total_count": len(reminders),
            "overdue_count": overdue_count,
        })

    except Exception as e:
        logger.error(f"Failed to get reminders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@notification_router.post("/reminders/{reminder_id}/complete")
async def complete_reminder(request: Request, reminder_id: str):
    """
    Mark a follow-up reminder as completed.
    """
    try:
        from cpa_panel.services.notification_service import get_notification_service
        service = get_notification_service()

        success = service.complete_reminder(reminder_id)

        if not success:
            raise HTTPException(status_code=404, detail="Reminder not found")

        return JSONResponse({
            "success": True,
            "reminder_id": reminder_id,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@notification_router.post("/reminders/{reminder_id}/snooze")
async def snooze_reminder(
    request: Request,
    reminder_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours to snooze"),
):
    """
    Snooze a reminder for specified hours.
    """
    try:
        from cpa_panel.services.notification_service import get_notification_service
        from datetime import timedelta
        service = get_notification_service()

        new_due = datetime.utcnow() + timedelta(hours=hours)

        conn = service._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE follow_up_reminders
            SET due_date = ?
            WHERE reminder_id = ?
        """, (new_due.isoformat(), reminder_id))
        conn.commit()
        conn.close()

        return JSONResponse({
            "success": True,
            "reminder_id": reminder_id,
            "new_due_date": new_due.isoformat(),
        })

    except Exception as e:
        logger.error(f"Failed to snooze reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# NOTIFICATION STATS
# =============================================================================

@notification_router.get("/notifications/stats")
async def get_notification_stats(request: Request):
    """
    Get notification statistics for the current CPA.
    """
    try:
        from cpa_panel.services.notification_service import get_notification_service
        service = get_notification_service()

        stats = service.get_notification_stats()

        cpa_email = _get_authenticated_cpa_email(request)

        # Get CPA-specific unread count
        conn = service._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM notifications
            WHERE recipient_email = ? AND status != 'read'
        """, (cpa_email,))
        unread_count = cursor.fetchone()["count"]

        # Get overdue reminders count
        cursor.execute("""
            SELECT COUNT(*) as count FROM follow_up_reminders
            WHERE cpa_email = ? AND completed = 0 AND due_date < ?
        """, (cpa_email, datetime.utcnow().isoformat()))
        overdue_reminders = cursor.fetchone()["count"]

        conn.close()

        return JSONResponse({
            "unread_notifications": unread_count,
            "overdue_reminders": overdue_reminders,
            "global_stats": stats,
        })

    except Exception as e:
        logger.error(f"Failed to get notification stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
