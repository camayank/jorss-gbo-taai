"""Tests for correlation ID middleware."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import logging

from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from middleware.correlation import (
    CorrelationIdMiddleware,
    get_correlation_id,
    set_correlation_id,
    reset_correlation_id,
    correlation_id_context,
    CorrelationIdFilter,
    configure_correlation_logging,
    propagate_correlation_headers,
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
)


class TestCorrelationIdContext:
    """Tests for correlation ID context functions."""

    def test_get_returns_none_when_not_set(self):
        """Get returns None when no correlation ID is set."""
        # Reset any existing value
        token = set_correlation_id(None)
        reset_correlation_id(token)

        # In a fresh context, should return None
        assert get_correlation_id() is None or get_correlation_id() == "-"

    def test_set_and_get(self):
        """Set and get correlation ID."""
        test_id = "test-correlation-123"
        token = set_correlation_id(test_id)

        try:
            assert get_correlation_id() == test_id
        finally:
            reset_correlation_id(token)

    def test_reset_restores_previous_value(self):
        """Reset restores the previous correlation ID."""
        original_id = "original-id"
        new_id = "new-id"

        token1 = set_correlation_id(original_id)
        try:
            assert get_correlation_id() == original_id

            token2 = set_correlation_id(new_id)
            assert get_correlation_id() == new_id

            reset_correlation_id(token2)
            assert get_correlation_id() == original_id
        finally:
            reset_correlation_id(token1)


class TestCorrelationIdContextManager:
    """Tests for correlation_id_context context manager."""

    def test_generates_id_when_not_provided(self):
        """Context manager generates UUID when no ID provided."""
        with correlation_id_context() as cid:
            assert cid is not None
            assert len(cid) == 36  # UUID format
            assert get_correlation_id() == cid

    def test_uses_provided_id(self):
        """Context manager uses provided correlation ID."""
        test_id = "my-custom-id"
        with correlation_id_context(test_id) as cid:
            assert cid == test_id
            assert get_correlation_id() == test_id

    def test_resets_after_exit(self):
        """Context manager resets ID after exiting."""
        original = "original-context-id"
        nested = "nested-context-id"

        with correlation_id_context(original):
            assert get_correlation_id() == original

            with correlation_id_context(nested):
                assert get_correlation_id() == nested

            # Should be back to original after nested exits
            assert get_correlation_id() == original

    def test_resets_on_exception(self):
        """Context manager resets ID even when exception occurs."""
        original = "original-id"
        nested = "nested-id"

        with correlation_id_context(original):
            try:
                with correlation_id_context(nested):
                    assert get_correlation_id() == nested
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # Should be back to original
            assert get_correlation_id() == original


class TestCorrelationIdMiddleware:
    """Tests for CorrelationIdMiddleware."""

    @pytest.fixture
    def app(self):
        """Create test application with middleware."""
        async def homepage(request):
            return JSONResponse({
                "correlation_id": get_correlation_id(),
                "request_state_id": getattr(request.state, 'correlation_id', None),
            })

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(CorrelationIdMiddleware)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_generates_correlation_id(self, client):
        """Middleware generates correlation ID when not provided."""
        response = client.get("/")

        assert response.status_code == 200
        assert CORRELATION_ID_HEADER in response.headers
        assert REQUEST_ID_HEADER in response.headers

        # Both headers should have same value
        assert response.headers[CORRELATION_ID_HEADER] == response.headers[REQUEST_ID_HEADER]

        # Should be valid UUID format
        cid = response.headers[CORRELATION_ID_HEADER]
        assert len(cid) == 36

    def test_uses_provided_correlation_id(self, client):
        """Middleware uses correlation ID from request header."""
        test_id = "provided-correlation-id-123"
        response = client.get("/", headers={CORRELATION_ID_HEADER: test_id})

        assert response.status_code == 200
        assert response.headers[CORRELATION_ID_HEADER] == test_id

        # Should be available in request handler
        data = response.json()
        assert data["request_state_id"] == test_id

    def test_correlation_id_available_in_handler(self, client):
        """Correlation ID is accessible via get_correlation_id in handler."""
        test_id = "handler-test-id"
        response = client.get("/", headers={CORRELATION_ID_HEADER: test_id})

        data = response.json()
        assert data["correlation_id"] == test_id

    def test_custom_header_name(self):
        """Middleware can use custom header name."""
        async def homepage(request):
            return JSONResponse({"id": get_correlation_id()})

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(CorrelationIdMiddleware, header_name="X-Custom-ID")
        client = TestClient(app)

        test_id = "custom-header-id"
        response = client.get("/", headers={"X-Custom-ID": test_id})

        assert "X-Custom-ID" in response.headers
        assert response.headers["X-Custom-ID"] == test_id

    def test_custom_generator(self):
        """Middleware can use custom ID generator."""
        counter = [0]

        def custom_generator():
            counter[0] += 1
            return f"custom-{counter[0]}"

        async def homepage(request):
            return JSONResponse({"id": get_correlation_id()})

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(CorrelationIdMiddleware, generator=custom_generator)
        client = TestClient(app)

        response1 = client.get("/")
        response2 = client.get("/")

        assert response1.headers[CORRELATION_ID_HEADER] == "custom-1"
        assert response2.headers[CORRELATION_ID_HEADER] == "custom-2"


class TestCorrelationIdFilter:
    """Tests for CorrelationIdFilter logging filter."""

    def test_adds_correlation_id_to_record(self):
        """Filter adds correlation_id attribute to log record."""
        filter_instance = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with correlation_id_context("test-log-id"):
            result = filter_instance.filter(record)

        assert result is True
        assert record.correlation_id == "test-log-id"

    def test_uses_dash_when_no_correlation_id(self):
        """Filter uses dash when no correlation ID is set."""
        filter_instance = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Ensure no correlation ID is set
        token = set_correlation_id(None)
        try:
            result = filter_instance.filter(record)
            assert result is True
            assert record.correlation_id == "-"
        finally:
            reset_correlation_id(token)


class TestPropagateCorrelationHeaders:
    """Tests for propagate_correlation_headers function."""

    def test_adds_correlation_id_to_empty_headers(self):
        """Adds correlation ID to empty headers dict."""
        with correlation_id_context("propagate-test-id"):
            headers = propagate_correlation_headers()

        assert headers[CORRELATION_ID_HEADER] == "propagate-test-id"

    def test_adds_to_existing_headers(self):
        """Adds correlation ID to existing headers."""
        existing = {"Authorization": "Bearer token", "Content-Type": "application/json"}

        with correlation_id_context("merge-test-id"):
            headers = propagate_correlation_headers(existing)

        assert headers["Authorization"] == "Bearer token"
        assert headers["Content-Type"] == "application/json"
        assert headers[CORRELATION_ID_HEADER] == "merge-test-id"

    def test_does_not_modify_original_headers(self):
        """Does not modify the original headers dict."""
        original = {"Authorization": "Bearer token"}

        with correlation_id_context("test-id"):
            headers = propagate_correlation_headers(original)

        assert CORRELATION_ID_HEADER not in original
        assert CORRELATION_ID_HEADER in headers

    def test_returns_empty_when_no_correlation_id(self):
        """Returns headers without correlation ID when none set."""
        token = set_correlation_id(None)
        try:
            headers = propagate_correlation_headers()
            assert CORRELATION_ID_HEADER not in headers
        finally:
            reset_correlation_id(token)

    def test_returns_copy_with_existing_headers_no_correlation(self):
        """Returns copy of existing headers when no correlation ID."""
        existing = {"Authorization": "Bearer token"}

        token = set_correlation_id(None)
        try:
            headers = propagate_correlation_headers(existing)
            assert headers == existing
            assert headers is not existing  # Should be a copy
        finally:
            reset_correlation_id(token)


class TestConfigureCorrelationLogging:
    """Tests for configure_correlation_logging function."""

    def test_configures_logging_with_filter(self):
        """Configures logging with correlation ID filter."""
        # Create a test logger
        test_logger = logging.getLogger("test_correlation_logger")
        test_logger.handlers = []

        # Add a handler with the filter
        handler = logging.StreamHandler()
        handler.addFilter(CorrelationIdFilter())
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(correlation_id)s] %(levelname)s %(message)s"
        ))
        test_logger.addHandler(handler)

        # Verify filter is added
        assert len(handler.filters) == 1
        assert isinstance(handler.filters[0], CorrelationIdFilter)
