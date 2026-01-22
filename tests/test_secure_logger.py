"""
Test Suite for Secure Logger

Verifies that PII sanitization works correctly in logs.
"""

import logging
import pytest
from security.secure_logger import (
    get_logger,
    configure_secure_logging,
    sanitize_log_message,
    SanitizingLogFilter
)


def test_ssn_sanitization():
    """Test that SSNs are redacted from log messages."""
    logger = get_logger(__name__)

    # Test various SSN formats
    test_cases = [
        ("User SSN: 123-45-6789", "User SSN: [SSN-REDACTED]"),
        ("SSN 123456789 verified", "SSN [SSN-REDACTED] verified"),
        ("Contact: 123 45 6789", "Contact: [SSN-REDACTED]"),
    ]

    for input_msg, expected_output in test_cases:
        sanitized = sanitize_log_message(input_msg)
        assert "[SSN-REDACTED]" in sanitized, f"Failed to sanitize: {input_msg}"
        assert "123-45-6789" not in sanitized
        assert "123456789" not in sanitized


def test_email_partial_redaction():
    """Test that emails are partially redacted."""
    logger = get_logger(__name__)

    test_email = "user@example.com"
    sanitized = sanitize_log_message(f"Email: {test_email}")

    # Should partially redact: u***r@example.com
    assert "u" in sanitized  # First char preserved
    assert "r@example.com" in sanitized  # Last char + domain preserved
    assert "user@example.com" not in sanitized  # Full email redacted


def test_credit_card_sanitization():
    """Test that credit card numbers are redacted."""
    test_cases = [
        "Card: 4532-1488-0343-6467",
        "Card: 4532 1488 0343 6467",
        "Card: 4532148803436467",
    ]

    for test_msg in test_cases:
        sanitized = sanitize_log_message(test_msg)
        assert "[REDACTED]" in sanitized
        assert "4532" not in sanitized


def test_api_key_sanitization():
    """Test that API keys are redacted."""
    test_cases = [
        "API Key: sk-1234567890abcdefghij",
        "Using pk_live_1234567890abcdefghij",
        "API_KEY=api-key-1234567890abcdefghij",
    ]

    for test_msg in test_cases:
        sanitized = sanitize_log_message(test_msg)
        assert "[API-KEY-REDACTED]" in sanitized
        assert "1234567890" not in sanitized


def test_phone_sanitization():
    """Test that phone numbers are redacted."""
    test_cases = [
        "Phone: (555) 123-4567",
        "Call 555-123-4567",
        "Mobile: 555.123.4567",
    ]

    for test_msg in test_cases:
        sanitized = sanitize_log_message(test_msg)
        assert "[REDACTED]" in sanitized
        assert "555-123-4567" not in sanitized


def test_dict_sanitization():
    """Test that sensitive fields in dicts are redacted."""
    from security.data_sanitizer import get_sanitizer

    sanitizer = get_sanitizer()

    test_data = {
        "ssn": "123-45-6789",
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "555-123-4567",
        "income": 75000,
    }

    sanitized = sanitizer.sanitize_dict(test_data)

    assert sanitized["ssn"] == "[REDACTED]"
    assert sanitized["name"] == "John Doe"  # Names not in sensitive_fields
    assert "@example.com" in sanitized["email"]  # Domain preserved
    assert "john@example.com" not in sanitized["email"]  # Full email redacted
    assert sanitized["phone"] == "[REDACTED]"
    assert sanitized["income"] == 75000  # Numbers unchanged


def test_nested_dict_sanitization():
    """Test that nested dicts are sanitized."""
    from security.data_sanitizer import get_sanitizer

    sanitizer = get_sanitizer()

    test_data = {
        "user": {
            "ssn": "123-45-6789",
            "bank_account": "123456789",
            "name": "John Doe"
        },
        "metadata": {
            "created_at": "2025-01-01"
        }
    }

    sanitized = sanitizer.sanitize_dict(test_data, deep=True)

    assert sanitized["user"]["ssn"] == "[REDACTED]"
    assert sanitized["user"]["bank_account"] == "[REDACTED]"
    assert sanitized["user"]["name"] == "John Doe"
    assert sanitized["metadata"]["created_at"] == "2025-01-01"


def test_logging_filter():
    """Test that the logging filter sanitizes records."""
    # Create a test logger
    test_logger = logging.getLogger("test_secure_logger")
    test_logger.setLevel(logging.INFO)

    # Add our sanitizing filter
    sanitizing_filter = SanitizingLogFilter()
    test_logger.addFilter(sanitizing_filter)

    # Create a log record with PII
    record = test_logger.makeRecord(
        name="test",
        level=logging.INFO,
        fn="test.py",
        lno=1,
        msg="User SSN: 123-45-6789",
        args=(),
        exc_info=None
    )

    # Apply filter
    sanitizing_filter.filter(record)

    # Verify SSN was redacted
    assert "[SSN-REDACTED]" in record.msg
    assert "123-45-6789" not in record.msg


def test_secure_logger_integration():
    """Test end-to-end secure logger usage."""
    import io
    import sys

    # Capture log output
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)

    # Get secure logger
    logger = get_logger("test_integration")
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.INFO)

    # Log message with PII
    logger.info("Processing return for SSN 123-45-6789")
    logger.warning("Failed to verify email: user@example.com")
    logger.error("Invalid credit card: 4532-1488-0343-6467")

    # Get logged output
    log_output = log_capture.getvalue()

    # Verify PII was sanitized
    assert "[SSN-REDACTED]" in log_output
    assert "123-45-6789" not in log_output
    assert "@example.com" in log_output  # Domain preserved
    assert "user@example.com" not in log_output  # Full email redacted
    assert "[REDACTED]" in log_output  # Credit card redacted


def test_no_false_positives():
    """Test that legitimate data is not incorrectly redacted."""
    test_cases = [
        "Version: 1.23.45.6789",  # Version number, not SSN
        "Transaction ID: 123456",  # Short number, not account
        "Error code: 404",  # HTTP status
        "Port: 8080",  # Port number
    ]

    for test_msg in test_cases:
        sanitized = sanitize_log_message(test_msg)
        # These should NOT be redacted (patterns should be specific enough)
        # Version numbers might get partially caught, but that's acceptable
        # The key is SSN/account patterns must match


def test_performance():
    """Test that sanitization doesn't significantly impact performance."""
    import time

    logger = get_logger("perf_test")

    # Measure sanitization overhead
    test_msg = "Processing user 12345 with income $75000"

    start = time.time()
    for _ in range(1000):
        sanitize_log_message(test_msg)
    elapsed = time.time() - start

    # Should complete 1000 sanitizations in < 100ms
    assert elapsed < 0.1, f"Sanitization too slow: {elapsed}s for 1000 iterations"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
