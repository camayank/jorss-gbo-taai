"""
Unified API Error Response System.

Provides standardized error responses across all API endpoints for:
- Consistent client-side error handling
- Proper error logging and monitoring
- Security-conscious error messages (no sensitive data leakage)
- Compliance with REST API best practices

Usage:
    from security.api_errors import APIError, ErrorCode, raise_api_error

    # Raise a standardized error
    raise_api_error(ErrorCode.VALIDATION_ERROR, "Invalid email format", field="email")

    # Or create directly
    raise APIError(
        code=ErrorCode.NOT_FOUND,
        message="Resource not found",
        status_code=404
    )
"""

from __future__ import annotations

import logging
import traceback
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# =============================================================================
# ERROR CODES
# =============================================================================


class ErrorCode(str, Enum):
    """
    Standardized error codes for API responses.

    Categories:
    - AUTH_*: Authentication/Authorization errors (401, 403)
    - VALIDATION_*: Input validation errors (400, 422)
    - RESOURCE_*: Resource-related errors (404, 409)
    - RATE_*: Rate limiting errors (429)
    - SERVER_*: Server-side errors (500, 502, 503)
    - BUSINESS_*: Business logic errors (400)
    """

    # Authentication & Authorization (401, 403)
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_INSUFFICIENT_PERMISSIONS"
    AUTH_ACCOUNT_LOCKED = "AUTH_ACCOUNT_LOCKED"
    AUTH_MFA_REQUIRED = "AUTH_MFA_REQUIRED"
    AUTH_SESSION_EXPIRED = "AUTH_SESSION_EXPIRED"

    # Validation Errors (400, 422)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VALIDATION_MISSING_FIELD = "VALIDATION_MISSING_FIELD"
    VALIDATION_INVALID_FORMAT = "VALIDATION_INVALID_FORMAT"
    VALIDATION_OUT_OF_RANGE = "VALIDATION_OUT_OF_RANGE"
    VALIDATION_FILE_TOO_LARGE = "VALIDATION_FILE_TOO_LARGE"
    VALIDATION_FILE_TYPE_NOT_ALLOWED = "VALIDATION_FILE_TYPE_NOT_ALLOWED"
    VALIDATION_MALICIOUS_CONTENT = "VALIDATION_MALICIOUS_CONTENT"

    # Resource Errors (404, 409, 410)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    RESOURCE_GONE = "RESOURCE_GONE"
    RESOURCE_LOCKED = "RESOURCE_LOCKED"

    # Rate Limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    RATE_LIMIT_QUOTA_EXCEEDED = "RATE_LIMIT_QUOTA_EXCEEDED"

    # Server Errors (500, 502, 503)
    SERVER_INTERNAL_ERROR = "SERVER_INTERNAL_ERROR"
    SERVER_DATABASE_ERROR = "SERVER_DATABASE_ERROR"
    SERVER_EXTERNAL_SERVICE_ERROR = "SERVER_EXTERNAL_SERVICE_ERROR"
    SERVER_MAINTENANCE = "SERVER_MAINTENANCE"
    SERVER_OVERLOADED = "SERVER_OVERLOADED"

    # Business Logic Errors (400)
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    BUSINESS_OPERATION_NOT_ALLOWED = "BUSINESS_OPERATION_NOT_ALLOWED"
    BUSINESS_INSUFFICIENT_FUNDS = "BUSINESS_INSUFFICIENT_FUNDS"
    BUSINESS_LIMIT_EXCEEDED = "BUSINESS_LIMIT_EXCEEDED"

    # Tenant/Multi-tenancy Errors (403)
    TENANT_ACCESS_DENIED = "TENANT_ACCESS_DENIED"
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    TENANT_SUSPENDED = "TENANT_SUSPENDED"


# =============================================================================
# ERROR CODE TO HTTP STATUS MAPPING
# =============================================================================

ERROR_CODE_STATUS_MAP: Dict[ErrorCode, int] = {
    # Auth errors
    ErrorCode.AUTH_REQUIRED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTH_INVALID_TOKEN: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTH_TOKEN_EXPIRED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS: status.HTTP_403_FORBIDDEN,
    ErrorCode.AUTH_ACCOUNT_LOCKED: status.HTTP_403_FORBIDDEN,
    ErrorCode.AUTH_MFA_REQUIRED: status.HTTP_403_FORBIDDEN,
    ErrorCode.AUTH_SESSION_EXPIRED: status.HTTP_401_UNAUTHORIZED,

    # Validation errors
    ErrorCode.VALIDATION_ERROR: status.HTTP_400_BAD_REQUEST,
    ErrorCode.VALIDATION_MISSING_FIELD: status.HTTP_400_BAD_REQUEST,
    ErrorCode.VALIDATION_INVALID_FORMAT: status.HTTP_400_BAD_REQUEST,
    ErrorCode.VALIDATION_OUT_OF_RANGE: status.HTTP_400_BAD_REQUEST,
    ErrorCode.VALIDATION_FILE_TOO_LARGE: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    ErrorCode.VALIDATION_FILE_TYPE_NOT_ALLOWED: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    ErrorCode.VALIDATION_MALICIOUS_CONTENT: status.HTTP_400_BAD_REQUEST,

    # Resource errors
    ErrorCode.RESOURCE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.RESOURCE_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
    ErrorCode.RESOURCE_CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.RESOURCE_GONE: status.HTTP_410_GONE,
    ErrorCode.RESOURCE_LOCKED: status.HTTP_423_LOCKED,

    # Rate limiting
    ErrorCode.RATE_LIMIT_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.RATE_LIMIT_QUOTA_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,

    # Server errors
    ErrorCode.SERVER_INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.SERVER_DATABASE_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.SERVER_EXTERNAL_SERVICE_ERROR: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.SERVER_MAINTENANCE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.SERVER_OVERLOADED: status.HTTP_503_SERVICE_UNAVAILABLE,

    # Business errors
    ErrorCode.BUSINESS_RULE_VIOLATION: status.HTTP_400_BAD_REQUEST,
    ErrorCode.BUSINESS_OPERATION_NOT_ALLOWED: status.HTTP_400_BAD_REQUEST,
    ErrorCode.BUSINESS_INSUFFICIENT_FUNDS: status.HTTP_402_PAYMENT_REQUIRED,
    ErrorCode.BUSINESS_LIMIT_EXCEEDED: status.HTTP_400_BAD_REQUEST,

    # Tenant errors
    ErrorCode.TENANT_ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
    ErrorCode.TENANT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.TENANT_SUSPENDED: status.HTTP_403_FORBIDDEN,
}


# =============================================================================
# ERROR RESPONSE MODELS
# =============================================================================


class FieldError(BaseModel):
    """Individual field validation error."""
    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message for this field")
    code: str = Field(default="invalid", description="Error code for this field")


class ErrorResponse(BaseModel):
    """
    Standardized API error response.

    All API errors return this format for consistent client handling.
    """
    error: bool = Field(default=True, description="Always true for errors")
    code: str = Field(..., description="Error code from ErrorCode enum")
    message: str = Field(..., description="Human-readable error message")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    request_id: str = Field(..., description="Unique request identifier for tracking")
    path: Optional[str] = Field(None, description="Request path that caused the error")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    field_errors: Optional[List[FieldError]] = Field(None, description="Field-specific validation errors")

    class Config:
        json_schema_extra = {
            "example": {
                "error": True,
                "code": "VALIDATION_ERROR",
                "message": "Invalid input data",
                "status_code": 400,
                "timestamp": "2026-01-29T12:00:00Z",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "path": "/api/returns",
                "details": {"hint": "Check the email format"},
                "field_errors": [
                    {"field": "email", "message": "Invalid email format", "code": "invalid_format"}
                ]
            }
        }


# =============================================================================
# API ERROR EXCEPTION
# =============================================================================


class APIError(Exception):
    """
    Custom exception for API errors.

    Raise this exception anywhere in your code to return a standardized error response.

    Usage:
        raise APIError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Email is required",
            details={"field": "email"}
        )
    """

    def __init__(
        self,
        code: Union[ErrorCode, str],
        message: str,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        field_errors: Optional[List[Dict[str, str]]] = None,
        log_error: bool = True,
    ):
        self.code = code if isinstance(code, ErrorCode) else ErrorCode(code)
        self.message = message
        self.status_code = status_code or ERROR_CODE_STATUS_MAP.get(
            self.code, status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        self.details = details
        self.field_errors = field_errors
        self.log_error = log_error
        super().__init__(message)

    def to_response(self, request_id: str, path: Optional[str] = None) -> ErrorResponse:
        """Convert to ErrorResponse model."""
        field_error_models = None
        if self.field_errors:
            field_error_models = [
                FieldError(
                    field=fe.get("field", "unknown"),
                    message=fe.get("message", "Invalid value"),
                    code=fe.get("code", "invalid"),
                )
                for fe in self.field_errors
            ]

        return ErrorResponse(
            error=True,
            code=self.code.value,
            message=self.message,
            status_code=self.status_code,
            timestamp=datetime.utcnow().isoformat() + "Z",
            request_id=request_id,
            path=path,
            details=self.details,
            field_errors=field_error_models,
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def raise_api_error(
    code: Union[ErrorCode, str],
    message: str,
    status_code: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """
    Helper to raise an APIError with optional field-based details.

    Usage:
        raise_api_error(ErrorCode.VALIDATION_ERROR, "Invalid email", field="email")
        raise_api_error(ErrorCode.NOT_FOUND, "User not found", resource="user", id="123")
    """
    if kwargs:
        details = details or {}
        details.update(kwargs)

    raise APIError(code=code, message=message, status_code=status_code, details=details)


def get_request_id(request: Request) -> str:
    """Get or generate request ID for tracking."""
    # Check for existing request ID from header or middleware
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = str(uuid.uuid4())
    return request_id


# =============================================================================
# GLOBAL EXCEPTION HANDLERS
# =============================================================================


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI app.

    Call this in your app initialization:
        from security.api_errors import register_exception_handlers
        register_exception_handlers(app)
    """

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        """Handle custom APIError exceptions."""
        request_id = get_request_id(request)

        # Log the error
        if exc.log_error:
            log_level = logging.WARNING if exc.status_code < 500 else logging.ERROR
            logger.log(
                log_level,
                f"[{request_id}] APIError: {exc.code.value} - {exc.message}",
                extra={
                    "request_id": request_id,
                    "error_code": exc.code.value,
                    "status_code": exc.status_code,
                    "path": request.url.path,
                    "method": request.method,
                    "details": exc.details,
                }
            )

        response = exc.to_response(request_id, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
            headers={"X-Request-ID": request_id}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle Pydantic validation errors."""
        request_id = get_request_id(request)

        # Convert Pydantic errors to our format
        field_errors = []
        for error in exc.errors():
            field_path = ".".join(str(loc) for loc in error["loc"] if loc != "body")
            field_errors.append({
                "field": field_path or "body",
                "message": error["msg"],
                "code": error["type"],
            })

        logger.warning(
            f"[{request_id}] Validation error: {len(field_errors)} field(s)",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "field_errors": field_errors,
            }
        )

        response = ErrorResponse(
            error=True,
            code=ErrorCode.VALIDATION_ERROR.value,
            message="Request validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            timestamp=datetime.utcnow().isoformat() + "Z",
            request_id=request_id,
            path=request.url.path,
            field_errors=[
                FieldError(field=fe["field"], message=fe["message"], code=fe["code"])
                for fe in field_errors
            ],
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response.model_dump(),
            headers={"X-Request-ID": request_id}
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Handle standard HTTP exceptions."""
        request_id = get_request_id(request)

        # Map HTTP status to error code
        status_to_code = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.AUTH_REQUIRED,
            403: ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            405: ErrorCode.BUSINESS_OPERATION_NOT_ALLOWED,
            409: ErrorCode.RESOURCE_CONFLICT,
            429: ErrorCode.RATE_LIMIT_EXCEEDED,
            500: ErrorCode.SERVER_INTERNAL_ERROR,
            502: ErrorCode.SERVER_EXTERNAL_SERVICE_ERROR,
            503: ErrorCode.SERVER_MAINTENANCE,
        }

        error_code = status_to_code.get(exc.status_code, ErrorCode.SERVER_INTERNAL_ERROR)

        logger.warning(
            f"[{request_id}] HTTP {exc.status_code}: {exc.detail}",
            extra={
                "request_id": request_id,
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
            }
        )

        response = ErrorResponse(
            error=True,
            code=error_code.value,
            message=str(exc.detail) if exc.detail else "An error occurred",
            status_code=exc.status_code,
            timestamp=datetime.utcnow().isoformat() + "Z",
            request_id=request_id,
            path=request.url.path,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
            headers={"X-Request-ID": request_id}
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Global catch-all exception handler.

        SECURITY: Never expose internal error details to clients.
        """
        request_id = get_request_id(request)

        # Log the full error with traceback (internal only)
        logger.error(
            f"[{request_id}] Unhandled exception: {type(exc).__name__}: {str(exc)}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "exception_type": type(exc).__name__,
                "traceback": traceback.format_exc(),
            },
            exc_info=True
        )

        # Return sanitized error to client (no sensitive details)
        response = ErrorResponse(
            error=True,
            code=ErrorCode.SERVER_INTERNAL_ERROR.value,
            message="An unexpected error occurred. Please try again later.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            timestamp=datetime.utcnow().isoformat() + "Z",
            request_id=request_id,
            path=request.url.path,
            details={"support": f"Reference ID: {request_id}"},
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(),
            headers={"X-Request-ID": request_id}
        )


# =============================================================================
# REQUEST ID MIDDLEWARE
# =============================================================================


class RequestIDMiddleware:
    """
    Middleware to add request ID to all requests.

    This allows tracking requests across logs and services.
    """

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Generate or use existing request ID
            headers = dict(scope.get("headers", []))
            request_id = headers.get(b"x-request-id", b"").decode() or str(uuid.uuid4())

            # Store in scope for later use
            scope["state"] = scope.get("state", {})
            scope["state"]["request_id"] = request_id

            # Add to response headers
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"x-request-id", request_id.encode()))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)
