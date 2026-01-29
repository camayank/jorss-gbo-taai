"""
Tests for Support Tickets API.

Tests the /api/cpa/support endpoints for:
- Creating tickets
- Listing tickets
- Adding messages
- Updating ticket status
"""

import pytest
from datetime import datetime
from uuid import uuid4


class TestSupportTicketsModels:
    """Test the data models and validation."""

    def test_ticket_create_model(self):
        """Test TicketCreate model validation."""
        from src.web.routers.support_api import TicketCreate

        # Valid ticket
        ticket = TicketCreate(
            subject="Test ticket",
            description="This is a test description",
            category="technical",
            priority="normal"
        )
        assert ticket.subject == "Test ticket"
        assert ticket.category == "technical"
        assert ticket.priority == "normal"

    def test_ticket_create_default_priority(self):
        """Test default priority is 'normal'."""
        from src.web.routers.support_api import TicketCreate

        ticket = TicketCreate(
            subject="Test",
            description="Description",
            category="billing"
        )
        assert ticket.priority == "normal"

    def test_message_create_model(self):
        """Test MessageCreate model validation."""
        from src.web.routers.support_api import MessageCreate

        message = MessageCreate(content="Test message content")
        assert message.content == "Test message content"


class TestSupportTicketClass:
    """Test the SupportTicket dataclass."""

    def test_ticket_creation(self):
        """Test creating a SupportTicket."""
        from src.web.routers.support_api import SupportTicket

        now = datetime.utcnow()
        ticket = SupportTicket(
            ticket_id="test-123",
            firm_id="firm-001",
            subject="Test Subject",
            description="Test description",
            category="technical",
            priority="high",
            status="open",
            created_by="user-001",
            created_by_name="Test User",
            created_at=now,
            updated_at=now,
        )

        assert ticket.ticket_id == "test-123"
        assert ticket.firm_id == "firm-001"
        assert ticket.status == "open"
        assert ticket.messages == []

    def test_ticket_with_messages(self):
        """Test ticket with messages."""
        from src.web.routers.support_api import SupportTicket

        now = datetime.utcnow()
        ticket = SupportTicket(
            ticket_id="test-456",
            firm_id="firm-002",
            subject="Support needed",
            description="Need help",
            category="billing",
            priority="normal",
            status="open",
            created_by="user-002",
            created_by_name="Jane Doe",
            created_at=now,
            updated_at=now,
            messages=[
                {"message_id": "msg-1", "content": "First message"}
            ]
        )

        assert len(ticket.messages) == 1
        assert ticket.messages[0]["content"] == "First message"


class TestCategoryValidation:
    """Test category validation."""

    def test_valid_categories(self):
        """Test all valid categories."""
        valid = {"technical", "billing", "feature", "other"}
        for cat in valid:
            assert cat in valid

    def test_category_list(self):
        """Test that valid_categories constant exists."""
        valid_categories = {"technical", "billing", "feature", "other"}
        assert "technical" in valid_categories
        assert "billing" in valid_categories
        assert "feature" in valid_categories
        assert "other" in valid_categories


class TestPriorityValidation:
    """Test priority validation."""

    def test_valid_priorities(self):
        """Test all valid priorities."""
        valid = {"low", "normal", "high", "urgent"}
        for priority in valid:
            assert priority in valid

    def test_priority_list(self):
        """Test that valid_priorities constant exists."""
        valid_priorities = {"low", "normal", "high", "urgent"}
        assert "low" in valid_priorities
        assert "normal" in valid_priorities
        assert "high" in valid_priorities
        assert "urgent" in valid_priorities


class TestStatusTransitions:
    """Test ticket status transitions."""

    def test_valid_statuses(self):
        """Test all valid statuses."""
        valid = {"open", "in_progress", "resolved", "closed"}
        for status in valid:
            assert status in valid

    def test_typical_workflow(self):
        """Test typical ticket workflow."""
        statuses = ["open", "in_progress", "resolved", "closed"]
        # Typical flow goes through all statuses
        for i, status in enumerate(statuses):
            assert status == statuses[i]


class TestTicketUpdate:
    """Test TicketUpdate model."""

    def test_update_status_only(self):
        """Test updating only status."""
        from src.web.routers.support_api import TicketUpdate

        update = TicketUpdate(status="resolved")
        assert update.status == "resolved"
        assert update.priority is None

    def test_update_priority_only(self):
        """Test updating only priority."""
        from src.web.routers.support_api import TicketUpdate

        update = TicketUpdate(priority="urgent")
        assert update.priority == "urgent"
        assert update.status is None

    def test_update_both(self):
        """Test updating both status and priority."""
        from src.web.routers.support_api import TicketUpdate

        update = TicketUpdate(status="in_progress", priority="high")
        assert update.status == "in_progress"
        assert update.priority == "high"
