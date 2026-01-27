"""
Tests for Rate Limiter Utility.
"""

import pytest
import time
from utils.rate_limiter import RateLimiter, RateLimitConfig, RateLimitExceeded


class TestRateLimiter:
    """Tests for rate limiting functionality."""

    def test_allows_requests_under_limit(self):
        """Test that requests under limit are allowed."""
        limiter = RateLimiter(RateLimitConfig(
            max_requests=5,
            window_seconds=60,
            per_session=True,
        ))

        # First 5 requests should be allowed
        for i in range(5):
            assert limiter.is_allowed("test-session") is True
            limiter.record_request("test-session")

    def test_blocks_requests_over_limit(self):
        """Test that requests over limit are blocked."""
        limiter = RateLimiter(RateLimitConfig(
            max_requests=3,
            window_seconds=60,
            cooldown_seconds=5,
            per_session=True,
        ))

        # Use up the limit
        for i in range(3):
            assert limiter.is_allowed("test-session") is True
            limiter.record_request("test-session")

        # Next request should be blocked
        assert limiter.is_allowed("test-session") is False

    def test_remaining_count_accurate(self):
        """Test that remaining count is accurate."""
        limiter = RateLimiter(RateLimitConfig(
            max_requests=5,
            window_seconds=60,
            per_session=True,
        ))

        assert limiter.get_remaining("test-session") == 5

        limiter.record_request("test-session")
        assert limiter.get_remaining("test-session") == 4

        limiter.record_request("test-session")
        assert limiter.get_remaining("test-session") == 3

    def test_per_session_isolation(self):
        """Test that per-session limits are isolated."""
        limiter = RateLimiter(RateLimitConfig(
            max_requests=2,
            window_seconds=60,
            per_session=True,
        ))

        # Session 1 uses up its limit
        limiter.record_request("session-1")
        limiter.record_request("session-1")
        assert limiter.is_allowed("session-1") is False

        # Session 2 should still have its limit
        assert limiter.is_allowed("session-2") is True
        assert limiter.get_remaining("session-2") == 2

    def test_global_limit_shared(self):
        """Test that global limits are shared across sessions."""
        limiter = RateLimiter(RateLimitConfig(
            max_requests=3,
            window_seconds=60,
            per_session=False,
        ))

        # Different sessions share the same limit
        limiter.record_request("session-1")
        limiter.record_request("session-2")
        limiter.record_request("session-3")

        # All sessions should be blocked now
        assert limiter.is_allowed("session-1") is False
        assert limiter.is_allowed("session-4") is False

    def test_reset_clears_state(self):
        """Test that reset clears rate limit state."""
        limiter = RateLimiter(RateLimitConfig(
            max_requests=2,
            window_seconds=60,
            per_session=True,
        ))

        # Use up limit
        limiter.record_request("test-session")
        limiter.record_request("test-session")
        assert limiter.is_allowed("test-session") is False

        # Reset
        limiter.reset("test-session")

        # Should be allowed again
        assert limiter.is_allowed("test-session") is True
        assert limiter.get_remaining("test-session") == 2

    def test_window_expiration(self):
        """Test that old requests expire from window."""
        limiter = RateLimiter(RateLimitConfig(
            max_requests=2,
            window_seconds=1,  # 1 second window
            cooldown_seconds=0,
            per_session=True,
        ))

        # Use up limit
        limiter.record_request("test-session")
        limiter.record_request("test-session")

        # Wait for window to expire
        time.sleep(1.5)

        # Should be allowed again
        assert limiter.is_allowed("test-session") is True

    def test_cooldown_period(self):
        """Test that cooldown period is enforced."""
        limiter = RateLimiter(RateLimitConfig(
            max_requests=1,
            window_seconds=60,
            cooldown_seconds=2,
            per_session=True,
        ))

        # Use up limit
        limiter.record_request("test-session")

        # Trigger cooldown
        assert limiter.is_allowed("test-session") is False

        # Wait partial cooldown
        time.sleep(1)
        assert limiter.is_allowed("test-session") is False

        # Wait full cooldown
        time.sleep(1.5)
        # After cooldown, requests in window still exist, so still blocked
        # until window expires

    def test_get_reset_time(self):
        """Test that reset time is calculated correctly."""
        limiter = RateLimiter(RateLimitConfig(
            max_requests=5,
            window_seconds=60,
            per_session=True,
        ))

        # No requests, no reset time
        assert limiter.get_reset_time("test-session") == 0

        # After request, reset time should be close to window
        limiter.record_request("test-session")
        reset_time = limiter.get_reset_time("test-session")
        assert 59 <= reset_time <= 60


class TestRateLimitConfig:
    """Tests for rate limit configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()

        assert config.max_requests == 10
        assert config.window_seconds == 60
        assert config.cooldown_seconds == 30
        assert config.per_session is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            max_requests=100,
            window_seconds=300,
            cooldown_seconds=60,
            per_session=False,
        )

        assert config.max_requests == 100
        assert config.window_seconds == 300
        assert config.cooldown_seconds == 60
        assert config.per_session is False
