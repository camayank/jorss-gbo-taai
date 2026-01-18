"""
State-Based Email Notifications

Sends email notifications on key state transitions.

SCOPE BOUNDARIES (ENFORCED - 3 TRIGGERS ONLY):
1. ready_for_review - When return is submitted for CPA review
2. approved - When CPA approves the return
3. delivered - When return is delivered to client

NOT IN SCOPE:
- General messaging
- Custom notification workflows
- SMS/push notifications
- Client-to-CPA communication
"""

from .notification_service import (
    NotificationService,
    NotificationTrigger,
    NotificationEvent,
)

__all__ = [
    "NotificationService",
    "NotificationTrigger",
    "NotificationEvent",
]
