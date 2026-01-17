"""Request Correlation ID Middleware.

Provides request tracing across services with unique correlation IDs.
The correlation ID is:
- Generated for each request if not provided
- Propagated to downstream services
- Included in all log messages
- Returned in response headers

Usage:
    from fastapi import FastAPI
    from middleware.correlation import CorrelationIdMiddleware

    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    # Access correlation ID in code:
    from middleware.correlation import get_correlation_id
    correlation_id = get_correlation_id()
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar, Token
from typing import Any, Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


# Context variable for correlation ID (thread-safe for async)
_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar(
    "correlation_id",
    default=None,
)

# Header names
CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID.

    Returns:
        The correlation ID for the current context, or None.
    """
    return _correlation_id_ctx.get()


def set_correlation_id(correlation_id: str) -> Token[Optional[str]]:
    """Set the correlation ID for the current context.

    Args:
        correlation_id: The correlation ID to set.

    Returns:
        Token that can be used to reset the context.
    """
    return _correlation_id_ctx.set(correlation_id)


def reset_correlation_id(token: Token[Optional[str]]) -> None:
    """Reset the correlation ID to its previous value.

    Args:
        token: Token from set_correlation_id.
    """
    _correlation_id_ctx.reset(token)


class correlation_id_context:
    """Context manager for correlation ID.

    Usage:
        with correlation_id_context("my-correlation-id"):
            # Code here has access to the correlation ID
            pass

        # Or generate a new one:
        with correlation_id_context() as cid:
            print(f"Using correlation ID: {cid}")
    """

    def __init__(self, correlation_id: Optional[str] = None):
        """Initialize context.

        Args:
            correlation_id: ID to use, or None to generate one.
        """
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self._token: Optional[Token[Optional[str]]] = None

    def __enter__(self) -> str:
        """Enter context and set correlation ID."""
        self._token = set_correlation_id(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and reset correlation ID."""
        if self._token is not None:
            reset_correlation_id(self._token)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to handle correlation IDs for request tracing.

    Features:
    - Extracts correlation ID from incoming request headers
    - Generates new correlation ID if not present
    - Sets correlation ID in context for the request
    - Adds correlation ID to response headers
    - Configurable header names
    """

    def __init__(
        self,
        app,
        header_name: str = CORRELATION_ID_HEADER,
        generator: Optional[Callable[[], str]] = None,
    ):
        """Initialize middleware.

        Args:
            app: ASGI application.
            header_name: Header name for correlation ID.
            generator: Optional custom ID generator function.
        """
        super().__init__(app)
        self.header_name = header_name
        self.generator = generator or (lambda: str(uuid.uuid4()))

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        """Process request with correlation ID.

        Args:
            request: Incoming request.
            call_next: Next middleware/handler.

        Returns:
            Response with correlation ID header.
        """
        # Get or generate correlation ID
        correlation_id = request.headers.get(self.header_name)
        if not correlation_id:
            correlation_id = self.generator()

        # Set in context
        token = set_correlation_id(correlation_id)

        try:
            # Add to request state for easy access
            request.state.correlation_id = correlation_id

            # Process request
            response = await call_next(request)

            # Add to response headers
            response.headers[self.header_name] = correlation_id
            response.headers[REQUEST_ID_HEADER] = correlation_id

            return response

        finally:
            # Reset context
            reset_correlation_id(token)


class CorrelationIdFilter(logging.Filter):
    """Logging filter that adds correlation ID to log records.

    Usage:
        import logging
        from middleware.correlation import CorrelationIdFilter

        handler = logging.StreamHandler()
        handler.addFilter(CorrelationIdFilter())

        formatter = logging.Formatter(
            '%(asctime)s [%(correlation_id)s] %(levelname)s %(message)s'
        )
        handler.setFormatter(formatter)
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to log record.

        Args:
            record: Log record to process.

        Returns:
            True to include the record.
        """
        record.correlation_id = get_correlation_id() or "-"
        return True


def configure_correlation_logging(
    log_format: Optional[str] = None,
    level: int = logging.INFO,
) -> None:
    """Configure logging with correlation ID support.

    Args:
        log_format: Custom log format (must include %(correlation_id)s).
        level: Logging level.
    """
    if log_format is None:
        log_format = (
            "%(asctime)s [%(correlation_id)s] %(levelname)s "
            "%(name)s: %(message)s"
        )

    # Create handler with filter
    handler = logging.StreamHandler()
    handler.addFilter(CorrelationIdFilter())
    handler.setFormatter(logging.Formatter(log_format))
    handler.setLevel(level)

    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def propagate_correlation_headers(
    headers: Optional[dict] = None,
) -> dict:
    """Get headers dict with correlation ID for downstream calls.

    Useful when making HTTP calls to downstream services.

    Args:
        headers: Existing headers dict to extend.

    Returns:
        Headers dict with correlation ID.

    Usage:
        import httpx
        from middleware.correlation import propagate_correlation_headers

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.example.com/data",
                headers=propagate_correlation_headers()
            )
    """
    result = dict(headers) if headers else {}
    correlation_id = get_correlation_id()
    if correlation_id:
        result[CORRELATION_ID_HEADER] = correlation_id
    return result
