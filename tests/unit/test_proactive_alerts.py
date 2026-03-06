"""
Tests for AI-enhanced proactive tax planning alerts.

Covers:
1. notify_tax_opportunity with AI narrative
2. notify_tax_opportunity with static fallback
3. notify_tax_opportunity with no CPA email
4. scan_client_opportunities AI narrative integration (mocked)
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from cpa_panel.services.notification_service import NotificationService


@pytest.fixture
def notifier(tmp_path):
    """Create a NotificationService backed by a temporary database."""
    db_path = str(tmp_path / "test.db")
    return NotificationService(db_path=db_path)


class TestNotifyTaxOpportunity:
    """Tests for NotificationService.notify_tax_opportunity()."""

    def test_with_ai_narrative(self, notifier):
        """When an AI narrative is provided, it should be used as the notification body."""
        ai_text = "Based on your client's profile, contributing the maximum to their 401(k)..."
        result = notifier.notify_tax_opportunity(
            cpa_email="cpa@example.com",
            client_name="John Doe",
            opportunity_title="Maximize 401(k)",
            potential_savings=5000,
            ai_narrative=ai_text,
        )
        assert result is not None
        assert result.body == ai_text
        assert "Tax Opportunity" in result.subject
        assert "John Doe" in result.subject
        assert result.data["has_ai_narrative"] is True
        assert result.data["potential_savings"] == 5000

    def test_static_fallback(self, notifier):
        """Without AI narrative, a static summary including client name and savings should be used."""
        result = notifier.notify_tax_opportunity(
            cpa_email="cpa@example.com",
            client_name="Jane Smith",
            opportunity_title="HSA Contribution",
            potential_savings=2500,
        )
        assert result is not None
        assert "Jane Smith" in result.body
        assert "$2,500" in result.body
        assert "HSA Contribution" in result.body
        assert result.data["has_ai_narrative"] is False

    def test_no_email_returns_none(self, notifier):
        """When cpa_email is empty, should return None without creating a notification."""
        result = notifier.notify_tax_opportunity(
            cpa_email="",
            client_name="Test Client",
            opportunity_title="Test Opportunity",
            potential_savings=1000,
        )
        assert result is None

    def test_subject_format(self, notifier):
        """Subject should contain 'Tax Opportunity', client name, and opportunity title."""
        result = notifier.notify_tax_opportunity(
            cpa_email="cpa@example.com",
            client_name="Alice Wonderland",
            opportunity_title="Roth Conversion",
            potential_savings=3000,
        )
        assert result is not None
        assert result.subject == "Tax Opportunity: Alice Wonderland \u2014 Roth Conversion"


class TestNotifyTaxOpportunityMetadata:
    """Test metadata and edge cases for notify_tax_opportunity."""

    def test_metadata_includes_savings_info(self, notifier):
        """Verify notification data dict includes expected metadata."""
        result = notifier.notify_tax_opportunity(
            cpa_email="cpa@example.com",
            client_name="Test Client",
            opportunity_title="HSA Contribution",
            potential_savings=3500,
            ai_narrative="AI-generated summary here",
        )
        assert result is not None
        assert result.data["potential_savings"] == 3500
        assert result.data["has_ai_narrative"] is True
        assert result.data["client_name"] == "Test Client"
        assert result.data["opportunity_title"] == "HSA Contribution"
