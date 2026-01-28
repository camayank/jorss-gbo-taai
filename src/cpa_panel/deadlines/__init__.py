"""
Deadline Management Module for CPA Panel

Provides comprehensive deadline tracking for tax practice:
- Filing deadlines (April 15, October 15)
- Extension deadlines
- Quarterly estimated tax payment deadlines
- Custom client-specific deadlines
- Automated reminders and alerts
"""

from .deadline_service import DeadlineService, DeadlineType, DeadlineStatus
from .deadline_models import Deadline, DeadlineReminder, DeadlineAlert

__all__ = [
    "DeadlineService",
    "DeadlineType",
    "DeadlineStatus",
    "Deadline",
    "DeadlineReminder",
    "DeadlineAlert",
]
