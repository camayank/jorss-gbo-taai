"""
Pytest fixtures for notification tests.

Provides mock data for testing:
- Email providers
- Email messages
- Notification triggers
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class NotificationType(str, Enum):
    """Types of notifications."""
    APPOINTMENT_REMINDER = "appointment_reminder"
    DEADLINE_ALERT = "deadline_alert"
    TASK_ASSIGNED = "task_assigned"
    DOCUMENT_UPLOADED = "document_uploaded"
    RETURN_STATUS_CHANGED = "return_status_changed"
    PAYMENT_RECEIVED = "payment_received"
    INVITATION_SENT = "invitation_sent"


@dataclass
class MockEmailMessage:
    """Mock email message for testing."""
    message_id: str
    to_email: str
    to_name: str
    from_email: str
    from_name: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    reply_to: Optional[str] = None
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    attachments: List[Dict] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    scheduled_at: Optional[datetime] = None


@dataclass
class MockEmailProvider:
    """Mock email provider for testing."""
    provider_name: str
    is_configured: bool = True
    api_key: Optional[str] = None
    from_email: str = "noreply@example.com"
    from_name: str = "Tax Platform"
    sent_messages: List[MockEmailMessage] = field(default_factory=list)

    def send(self, message: MockEmailMessage) -> Dict[str, Any]:
        """Mock send method."""
        if not self.is_configured:
            raise RuntimeError("Email provider not configured")

        self.sent_messages.append(message)
        return {
            "status": "sent",
            "message_id": message.message_id,
            "provider": self.provider_name,
        }


@pytest.fixture
def mock_email_provider():
    """Create a mock email provider."""
    return MockEmailProvider(
        provider_name="sendgrid",
        is_configured=True,
        api_key="SG.test_api_key",
        from_email="notifications@taxplatform.com",
        from_name="Tax Filing Platform",
    )


@pytest.fixture
def mock_smtp_provider():
    """Create a mock SMTP provider."""
    return MockEmailProvider(
        provider_name="smtp",
        is_configured=True,
        from_email="noreply@cpa-firm.com",
        from_name="Smith & Associates CPAs",
    )


@pytest.fixture
def mock_unconfigured_provider():
    """Create an unconfigured email provider."""
    return MockEmailProvider(
        provider_name="null",
        is_configured=False,
    )


@pytest.fixture
def sample_email_message():
    """Create a sample email message."""
    return MockEmailMessage(
        message_id=str(uuid4()),
        to_email="client@example.com",
        to_name="John Smith",
        from_email="notifications@taxplatform.com",
        from_name="Tax Filing Platform",
        subject="Your Tax Return is Ready for Review",
        body_text="Dear John, Your 2025 tax return is ready for your review.",
        body_html="<html><body><p>Dear John,</p><p>Your 2025 tax return is ready for your review.</p></body></html>",
        reply_to="support@taxplatform.com",
    )


@pytest.fixture
def sample_appointment_notification():
    """Create a sample appointment reminder notification."""
    appointment_time = datetime.utcnow() + timedelta(days=1)
    return {
        "notification_type": NotificationType.APPOINTMENT_REMINDER,
        "recipient_email": "client@example.com",
        "recipient_name": "John Smith",
        "subject": f"Reminder: Tax Consultation Tomorrow",
        "data": {
            "appointment_date": appointment_time.strftime("%B %d, %Y"),
            "appointment_time": appointment_time.strftime("%I:%M %p"),
            "preparer_name": "Jane Doe, CPA",
            "meeting_link": "https://meet.example.com/abc123",
            "notes": "Please bring your W-2s and 1099s.",
        },
    }


@pytest.fixture
def sample_deadline_notification():
    """Create a sample deadline alert notification."""
    deadline = datetime(2026, 4, 15)
    return {
        "notification_type": NotificationType.DEADLINE_ALERT,
        "recipient_email": "client@example.com",
        "recipient_name": "John Smith",
        "subject": "Tax Filing Deadline Approaching",
        "data": {
            "deadline_date": deadline.strftime("%B %d, %Y"),
            "days_until": (deadline - datetime.utcnow()).days,
            "deadline_type": "Federal Tax Return",
            "action_required": "File your return or request an extension",
        },
    }


@pytest.fixture
def sample_task_notification():
    """Create a sample task assigned notification."""
    return {
        "notification_type": NotificationType.TASK_ASSIGNED,
        "recipient_email": "preparer@firm.com",
        "recipient_name": "Tax Preparer",
        "subject": "New Task Assigned: Review John Smith's Return",
        "data": {
            "task_id": str(uuid4()),
            "task_title": "Review 2025 Tax Return",
            "client_name": "John Smith",
            "assigned_by": "Jane Doe, Manager",
            "due_date": (datetime.utcnow() + timedelta(days=3)).strftime("%B %d, %Y"),
            "priority": "high",
        },
    }


@pytest.fixture
def sample_document_notification():
    """Create a sample document uploaded notification."""
    return {
        "notification_type": NotificationType.DOCUMENT_UPLOADED,
        "recipient_email": "preparer@firm.com",
        "recipient_name": "Tax Preparer",
        "subject": "New Document Uploaded by John Smith",
        "data": {
            "document_id": str(uuid4()),
            "document_type": "W-2",
            "uploaded_by": "John Smith",
            "uploaded_at": datetime.utcnow().isoformat(),
            "file_name": "w2_acme_corp_2025.pdf",
        },
    }


@pytest.fixture
def sample_status_change_notification():
    """Create a sample return status changed notification."""
    return {
        "notification_type": NotificationType.RETURN_STATUS_CHANGED,
        "recipient_email": "client@example.com",
        "recipient_name": "John Smith",
        "subject": "Your Tax Return Status Has Been Updated",
        "data": {
            "return_id": str(uuid4()),
            "tax_year": 2025,
            "old_status": "in_review",
            "new_status": "ready_for_signature",
            "updated_by": "Jane Doe, CPA",
            "updated_at": datetime.utcnow().isoformat(),
            "action_required": "Please review and sign your return",
        },
    }
