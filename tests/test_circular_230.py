"""Tests for Circular 230 compliance."""

import pytest
from datetime import datetime


class TestProfessionalAcknowledgment:
    """Tests for professional standards acknowledgment."""

    def test_acknowledgment_model_has_required_fields(self):
        """ProfessionalAcknowledgment should have all required fields."""
        from src.web.intelligent_advisor_api import ProfessionalAcknowledgment

        ack = ProfessionalAcknowledgment(
            acknowledged=True,
            acknowledged_at=datetime.utcnow(),
            session_id="test-123"
        )
        assert ack.acknowledged == True
        assert ack.session_id == "test-123"

    def test_acknowledgment_defaults_to_false(self):
        """Acknowledgment should default to False."""
        from src.web.intelligent_advisor_api import ProfessionalAcknowledgment

        ack = ProfessionalAcknowledgment(session_id="test-123")
        assert ack.acknowledged == False
        assert ack.acknowledged_at is None


class TestAcknowledgmentFunctions:
    """Tests for acknowledgment check and store functions."""

    def test_check_acknowledgment_returns_false_initially(self):
        """New sessions should not be acknowledged."""
        from src.web.intelligent_advisor_api import check_acknowledgment

        result = check_acknowledgment("new-session-unique-123")
        assert result == False

    def test_store_acknowledgment_persists(self):
        """Storing acknowledgment should persist."""
        from src.web.intelligent_advisor_api import (
            store_acknowledgment, check_acknowledgment
        )

        store_acknowledgment("session-unique-456", "127.0.0.1", "TestAgent/1.0")
        result = check_acknowledgment("session-unique-456")
        assert result == True

    def test_get_acknowledgment_returns_details(self):
        """Should be able to retrieve acknowledgment details."""
        from src.web.intelligent_advisor_api import (
            store_acknowledgment, get_acknowledgment
        )

        store_acknowledgment("session-unique-789", "192.168.1.1", "Browser/2.0")
        ack = get_acknowledgment("session-unique-789")
        assert ack is not None
        assert ack.ip_address == "192.168.1.1"
        assert ack.acknowledged_at is not None
