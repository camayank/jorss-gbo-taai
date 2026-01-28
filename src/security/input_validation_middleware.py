"""
Input Validation Middleware.

Provides comprehensive input validation for all API requests:
- Query parameter validation (bounds, format, injection prevention)
- Path parameter validation (UUID format, SQL injection prevention)
- Request body size limits
- Content-Type enforcement
- Injection attack prevention

This middleware runs BEFORE request handlers, providing defense-in-depth.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import unquote

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from security.api_errors import APIError, ErrorCode

logger = logging.getLogger(__name__)


# =============================================================================
# VALIDATION PATTERNS
# =============================================================================

# UUID pattern for path parameters
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

# Common SQL injection patterns
SQL_INJECTION_PATTERNS = [
    re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)", re.IGNORECASE),
    re.compile(r"('|\")\s*(OR|AND)\s*('|\"|\d)", re.IGNORECASE),
    re.compile(r";\s*(DROP|DELETE|UPDATE|INSERT)", re.IGNORECASE),
    re.compile(r"--\s*$"),  # SQL comment
    re.compile(r"/\*.*\*/"),  # SQL block comment
    re.compile(r"WAITFOR\s+DELAY", re.IGNORECASE),  # Time-based injection
    re.compile(r"BENCHMARK\s*\(", re.IGNORECASE),  # MySQL benchmark
]

# XSS patterns
XSS_PATTERNS = [
    re.compile(r"<script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),  # onclick=, onload=, etc.
    re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    re.compile(r"<object[^>]*>", re.IGNORECASE),
    re.compile(r"<embed[^>]*>", re.IGNORECASE),
]

# Path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\.(/|\\)"),
    re.compile(r"%2e%2e[/\\]", re.IGNORECASE),
    re.compile(r"\.\.%2f", re.IGNORECASE),
    re.compile(r"%252e%252e", re.IGNORECASE),  # Double-encoded
]

# Command injection patterns
COMMAND_INJECTION_PATTERNS = [
    re.compile(r"[;&|`$]"),
    re.compile(r"\$\("),  # Command substitution
    re.compile(r"`[^`]+`"),  # Backtick execution
]


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def is_valid_uuid(value: str) -> bool:
    """Check if string is a valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def check_sql_injection(value: str) -> Optional[str]:
    """
    Check for SQL injection patterns.

    Returns the matched pattern if found, None otherwise.
    """
    decoded = unquote(value)
    for pattern in SQL_INJECTION_PATTERNS:
        match = pattern.search(decoded)
        if match:
            return match.group(0)
    return None


def check_xss(value: str) -> Optional[str]:
    """
    Check for XSS patterns.

    Returns the matched pattern if found, None otherwise.
    """
    decoded = unquote(value)
    for pattern in XSS_PATTERNS:
        match = pattern.search(decoded)
        if match:
            return match.group(0)
    return None


def check_path_traversal(value: str) -> Optional[str]:
    """
    Check for path traversal patterns.

    Returns the matched pattern if found, None otherwise.
    """
    decoded = unquote(value)
    for pattern in PATH_TRAVERSAL_PATTERNS:
        match = pattern.search(decoded)
        if match:
            return match.group(0)
    return None


def check_command_injection(value: str) -> Optional[str]:
    """
    Check for command injection patterns.

    Returns the matched pattern if found, None otherwise.
    """
    for pattern in COMMAND_INJECTION_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(0)
    return None


def validate_integer_param(
    value: str,
    param_name: str,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    """
    Validate and convert integer parameter.

    Raises APIError if validation fails.
    """
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise APIError(
            code=ErrorCode.VALIDATION_INVALID_FORMAT,
            message=f"Parameter '{param_name}' must be an integer",
            details={"param": param_name, "value": value}
        )

    if min_value is not None and int_value < min_value:
        raise APIError(
            code=ErrorCode.VALIDATION_OUT_OF_RANGE,
            message=f"Parameter '{param_name}' must be at least {min_value}",
            details={"param": param_name, "value": int_value, "min": min_value}
        )

    if max_value is not None and int_value > max_value:
        raise APIError(
            code=ErrorCode.VALIDATION_OUT_OF_RANGE,
            message=f"Parameter '{param_name}' must be at most {max_value}",
            details={"param": param_name, "value": int_value, "max": max_value}
        )

    return int_value


# =============================================================================
# VALIDATION MIDDLEWARE
# =============================================================================


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for comprehensive input validation.

    Features:
    - Query parameter validation (bounds, format)
    - Path parameter validation (UUID format)
    - Injection attack prevention (SQL, XSS, command)
    - Path traversal prevention
    - Request size limits
    """

    # Default configuration
    DEFAULT_MAX_QUERY_PARAMS = 50
    DEFAULT_MAX_PARAM_LENGTH = 1000
    DEFAULT_MAX_PATH_LENGTH = 2048
    DEFAULT_MAX_LIMIT = 1000
    DEFAULT_MIN_OFFSET = 0

    # Common pagination parameters with their bounds
    PAGINATION_PARAMS = {
        "limit": {"min": 1, "max": 1000, "default": 50},
        "offset": {"min": 0, "max": 1000000, "default": 0},
        "page": {"min": 1, "max": 10000, "default": 1},
        "page_size": {"min": 1, "max": 1000, "default": 50},
        "per_page": {"min": 1, "max": 1000, "default": 50},
    }

    # Parameters that should be UUIDs
    UUID_PARAMS = {
        "id", "user_id", "firm_id", "client_id", "return_id", "session_id",
        "document_id", "ticket_id", "key_id", "refund_id", "report_id",
        "tenant_id", "organization_id", "workspace_id",
    }

    # Paths to skip validation (health checks, etc.)
    EXEMPT_PATHS = {"/health", "/healthz", "/ready", "/metrics", "/favicon.ico"}

    def __init__(
        self,
        app,
        max_query_params: int = DEFAULT_MAX_QUERY_PARAMS,
        max_param_length: int = DEFAULT_MAX_PARAM_LENGTH,
        max_path_length: int = DEFAULT_MAX_PATH_LENGTH,
        check_injections: bool = True,
        strict_uuid_params: bool = True,
        validate_pagination: bool = True,
        exempt_paths: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.max_query_params = max_query_params
        self.max_param_length = max_param_length
        self.max_path_length = max_path_length
        self.check_injections = check_injections
        self.strict_uuid_params = strict_uuid_params
        self.validate_pagination = validate_pagination
        self.exempt_paths = exempt_paths or self.EXEMPT_PATHS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process and validate the request."""
        path = request.url.path

        # Skip exempt paths
        if path in self.exempt_paths or path.startswith("/static"):
            return await call_next(request)

        # Validate path length
        if len(path) > self.max_path_length:
            logger.warning(f"Path too long: {len(path)} chars from {request.client.host}")
            return self._error_response(
                ErrorCode.VALIDATION_ERROR,
                "Request path too long",
                400
            )

        # Validate path for traversal attacks
        traversal = check_path_traversal(path)
        if traversal:
            logger.warning(
                f"Path traversal attempt: {traversal} from {request.client.host}"
            )
            return self._error_response(
                ErrorCode.VALIDATION_MALICIOUS_CONTENT,
                "Invalid request path",
                400
            )

        # Validate query parameters
        query_params = dict(request.query_params)

        # Check query param count
        if len(query_params) > self.max_query_params:
            logger.warning(
                f"Too many query params: {len(query_params)} from {request.client.host}"
            )
            return self._error_response(
                ErrorCode.VALIDATION_ERROR,
                f"Too many query parameters (max: {self.max_query_params})",
                400
            )

        # Validate each query parameter
        for param_name, param_value in query_params.items():
            # Check length
            if len(param_value) > self.max_param_length:
                return self._error_response(
                    ErrorCode.VALIDATION_ERROR,
                    f"Parameter '{param_name}' too long",
                    400
                )

            # Check for injection attacks
            if self.check_injections:
                # SQL injection
                sql_match = check_sql_injection(param_value)
                if sql_match:
                    logger.warning(
                        f"SQL injection attempt in '{param_name}': {sql_match} "
                        f"from {request.client.host}"
                    )
                    return self._error_response(
                        ErrorCode.VALIDATION_MALICIOUS_CONTENT,
                        "Invalid characters in request",
                        400
                    )

                # XSS
                xss_match = check_xss(param_value)
                if xss_match:
                    logger.warning(
                        f"XSS attempt in '{param_name}': {xss_match} "
                        f"from {request.client.host}"
                    )
                    return self._error_response(
                        ErrorCode.VALIDATION_MALICIOUS_CONTENT,
                        "Invalid characters in request",
                        400
                    )

            # Validate UUID parameters
            if self.strict_uuid_params and param_name.lower() in self.UUID_PARAMS:
                if param_value and not is_valid_uuid(param_value):
                    return self._error_response(
                        ErrorCode.VALIDATION_INVALID_FORMAT,
                        f"Parameter '{param_name}' must be a valid UUID",
                        400
                    )

            # Validate pagination parameters
            if self.validate_pagination and param_name.lower() in self.PAGINATION_PARAMS:
                bounds = self.PAGINATION_PARAMS[param_name.lower()]
                try:
                    int_value = int(param_value)
                    if int_value < bounds["min"] or int_value > bounds["max"]:
                        return self._error_response(
                            ErrorCode.VALIDATION_OUT_OF_RANGE,
                            f"Parameter '{param_name}' must be between "
                            f"{bounds['min']} and {bounds['max']}",
                            400
                        )
                except ValueError:
                    return self._error_response(
                        ErrorCode.VALIDATION_INVALID_FORMAT,
                        f"Parameter '{param_name}' must be an integer",
                        400
                    )

        # Validate path parameters (from URL)
        path_params = request.path_params
        for param_name, param_value in path_params.items():
            if isinstance(param_value, str):
                # Check for injection in path params
                if self.check_injections:
                    sql_match = check_sql_injection(param_value)
                    if sql_match:
                        logger.warning(
                            f"SQL injection in path '{param_name}': {sql_match} "
                            f"from {request.client.host}"
                        )
                        return self._error_response(
                            ErrorCode.VALIDATION_MALICIOUS_CONTENT,
                            "Invalid request",
                            400
                        )

                # Validate UUID path params
                if self.strict_uuid_params and param_name.lower() in self.UUID_PARAMS:
                    if not is_valid_uuid(param_value):
                        return self._error_response(
                            ErrorCode.VALIDATION_INVALID_FORMAT,
                            f"Invalid {param_name} format",
                            400
                        )

        # All validations passed
        return await call_next(request)

    def _error_response(
        self,
        code: ErrorCode,
        message: str,
        status_code: int
    ) -> JSONResponse:
        """Create a standardized error response."""
        from datetime import datetime
        import uuid as uuid_module

        return JSONResponse(
            status_code=status_code,
            content={
                "error": True,
                "code": code.value,
                "message": message,
                "status_code": status_code,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_id": str(uuid_module.uuid4()),
            }
        )


# =============================================================================
# CONTENT TYPE VALIDATION MIDDLEWARE
# =============================================================================


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce Content-Type headers for POST/PUT/PATCH requests.

    Prevents content-type confusion attacks.
    """

    ALLOWED_CONTENT_TYPES = {
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    }

    METHODS_REQUIRING_CONTENT_TYPE = {"POST", "PUT", "PATCH"}

    EXEMPT_PATHS = {"/health", "/healthz", "/ready", "/metrics"}

    def __init__(
        self,
        app,
        allowed_content_types: Optional[Set[str]] = None,
        exempt_paths: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.allowed_content_types = allowed_content_types or self.ALLOWED_CONTENT_TYPES
        self.exempt_paths = exempt_paths or self.EXEMPT_PATHS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate Content-Type header."""
        path = request.url.path

        # Skip exempt paths
        if path in self.exempt_paths:
            return await call_next(request)

        # Only check methods that send body
        if request.method in self.METHODS_REQUIRING_CONTENT_TYPE:
            content_type = request.headers.get("content-type", "")

            # Extract base content type (without charset, boundary, etc.)
            base_content_type = content_type.split(";")[0].strip().lower()

            # Check if content type is allowed
            if base_content_type and base_content_type not in self.allowed_content_types:
                logger.warning(
                    f"Invalid Content-Type: {content_type} from {request.client.host}"
                )
                return JSONResponse(
                    status_code=415,
                    content={
                        "error": True,
                        "code": "VALIDATION_ERROR",
                        "message": f"Unsupported Content-Type: {base_content_type}",
                        "status_code": 415,
                    }
                )

        return await call_next(request)


# =============================================================================
# REQUEST SIZE LIMIT MIDDLEWARE
# =============================================================================


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request body size limits.

    Prevents DoS attacks via large payloads.
    """

    DEFAULT_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    UPLOAD_MAX_SIZE = 50 * 1024 * 1024  # 50 MB for file uploads

    UPLOAD_PATHS = {"/api/upload", "/api/documents", "/api/files"}

    def __init__(
        self,
        app,
        max_size: int = DEFAULT_MAX_SIZE,
        upload_max_size: int = UPLOAD_MAX_SIZE,
        upload_paths: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.max_size = max_size
        self.upload_max_size = upload_max_size
        self.upload_paths = upload_paths or self.UPLOAD_PATHS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request body size."""
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)

                # Determine max size based on path
                is_upload = any(
                    request.url.path.startswith(p) for p in self.upload_paths
                )
                max_allowed = self.upload_max_size if is_upload else self.max_size

                if size > max_allowed:
                    logger.warning(
                        f"Request too large: {size} bytes from {request.client.host}"
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": True,
                            "code": "VALIDATION_FILE_TOO_LARGE",
                            "message": f"Request body too large (max: {max_allowed // (1024*1024)} MB)",
                            "status_code": 413,
                        }
                    )
            except ValueError:
                pass  # Invalid content-length, let FastAPI handle it

        return await call_next(request)
