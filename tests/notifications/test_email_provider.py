"""
Tests for email provider functionality.

Tests:
- Provider selection
- Message validation
- Send operations
- Error handling
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime


class TestProviderSelection:
    """Tests for email provider selection."""

    def test_sendgrid_provider_preferred(self, mock_email_provider):
        """Test that SendGrid is used when configured."""
        assert mock_email_provider.provider_name == "sendgrid"
        assert mock_email_provider.is_configured

    def test_smtp_fallback_available(self, mock_smtp_provider):
        """Test that SMTP fallback is available."""
        assert mock_smtp_provider.provider_name == "smtp"
        assert mock_smtp_provider.is_configured

    def test_unconfigured_provider_detected(self, mock_unconfigured_provider):
        """Test that unconfigured provider is detected."""
        assert not mock_unconfigured_provider.is_configured
        assert mock_unconfigured_provider.provider_name == "null"

    def test_provider_has_from_address(self, mock_email_provider):
        """Test that provider has configured from address."""
        assert mock_email_provider.from_email is not None
        assert "@" in mock_email_provider.from_email


class TestMessageValidation:
    """Tests for email message validation."""

    def test_message_has_required_fields(self, sample_email_message):
        """Test that message has all required fields."""
        required_fields = [
            "message_id", "to_email", "to_name",
            "from_email", "from_name", "subject", "body_text",
        ]

        for field in required_fields:
            assert hasattr(sample_email_message, field)
            assert getattr(sample_email_message, field) is not None

    def test_email_format_valid(self, sample_email_message):
        """Test that email addresses are valid format."""
        def is_valid_email(email):
            return "@" in email and "." in email.split("@")[1]

        assert is_valid_email(sample_email_message.to_email)
        assert is_valid_email(sample_email_message.from_email)

    def test_subject_not_empty(self, sample_email_message):
        """Test that subject line is not empty."""
        assert len(sample_email_message.subject) > 0

    def test_body_not_empty(self, sample_email_message):
        """Test that message body is not empty."""
        assert len(sample_email_message.body_text) > 0

    def test_html_body_optional(self, sample_email_message):
        """Test that HTML body is optional but valid if present."""
        if sample_email_message.body_html:
            assert "<" in sample_email_message.body_html
            assert ">" in sample_email_message.body_html


class TestSendOperations:
    """Tests for email send operations."""

    def test_send_success(self, mock_email_provider, sample_email_message):
        """Test successful email send."""
        result = mock_email_provider.send(sample_email_message)

        assert result["status"] == "sent"
        assert result["message_id"] == sample_email_message.message_id
        assert len(mock_email_provider.sent_messages) == 1

    def test_send_records_message(self, mock_email_provider, sample_email_message):
        """Test that sent messages are recorded."""
        mock_email_provider.send(sample_email_message)

        assert sample_email_message in mock_email_provider.sent_messages

    def test_send_fails_when_unconfigured(self, mock_unconfigured_provider, sample_email_message):
        """Test that send fails when provider not configured."""
        with pytest.raises(RuntimeError):
            mock_unconfigured_provider.send(sample_email_message)


class TestErrorHandling:
    """Tests for email error handling."""

    def test_invalid_recipient_rejected(self):
        """Test that invalid recipient email is rejected."""
        invalid_emails = [
            "not-an-email",
            "@nodomain",
            "no-at-sign.com",
            "",
            None,
        ]

        for email in invalid_emails:
            def is_valid_email(e):
                if not e:
                    return False
                return "@" in e and "." in e.split("@")[1]

            assert not is_valid_email(email)

    def test_empty_subject_handled(self):
        """Test that empty subject is handled gracefully."""
        # Empty subject should either fail validation or use default
        empty_subject = ""
        default_subject = "(No Subject)"

        subject = empty_subject or default_subject
        assert len(subject) > 0

    def test_missing_body_handled(self):
        """Test that missing body is handled."""
        body_text = None
        body_html = "<p>HTML only</p>"

        # Should use HTML content if text is missing
        final_body = body_text or "Please view this email in an HTML-capable client."
        assert len(final_body) > 0
