"""
Standardized Error Responses - Consistent API error handling.

Provides:
- Standard error response structure
- Error codes for common scenarios
- User-friendly error messages
- HTTP status code mapping

Resolves Audit Finding: "Inconsistent error handling"
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Client errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"

    NOT_FOUND = "NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"

    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"

    CONFLICT = "CONFLICT"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"

    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    TIMEOUT = "TIMEOUT"

    # Business logic errors
    CALCULATION_ERROR = "CALCULATION_ERROR"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    INVALID_STATE = "INVALID_STATE"


# Map error codes to HTTP status codes
ERROR_STATUS_MAP = {
    ErrorCode.VALIDATION_ERROR: status.HTTP_400_BAD_REQUEST,
    ErrorCode.INVALID_INPUT: status.HTTP_400_BAD_REQUEST,
    ErrorCode.MISSING_FIELD: status.HTTP_400_BAD_REQUEST,
    ErrorCode.INVALID_FORMAT: status.HTTP_400_BAD_REQUEST,

    ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.SESSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.RESOURCE_NOT_FOUND: status.HTTP_404_NOT_FOUND,

    ErrorCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
    ErrorCode.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,

    ErrorCode.CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.DUPLICATE_ENTRY: status.HTTP_409_CONFLICT,

    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.DATABASE_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.SERVICE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.PROCESSING_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,

    ErrorCode.CALCULATION_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.DATA_INCOMPLETE: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.INVALID_STATE: status.HTTP_422_UNPROCESSABLE_ENTITY,
}

# User-friendly default messages
DEFAULT_MESSAGES = {
    ErrorCode.VALIDATION_ERROR: "The provided data is invalid. Please check your input.",
    ErrorCode.INVALID_INPUT: "Invalid input provided.",
    ErrorCode.MISSING_FIELD: "Required field is missing.",
    ErrorCode.INVALID_FORMAT: "Data format is invalid.",

    ErrorCode.NOT_FOUND: "The requested resource was not found.",
    ErrorCode.SESSION_NOT_FOUND: "Your session has expired. Please start a new session.",
    ErrorCode.RESOURCE_NOT_FOUND: "The requested item could not be found.",

    ErrorCode.UNAUTHORIZED: "Authentication is required to access this resource.",
    ErrorCode.FORBIDDEN: "You don't have permission to access this resource.",
    ErrorCode.RATE_LIMITED: "Too many requests. Please wait a moment before trying again.",

    ErrorCode.CONFLICT: "A conflict occurred with the current state.",
    ErrorCode.DUPLICATE_ENTRY: "This item already exists.",

    ErrorCode.INTERNAL_ERROR: "An unexpected error occurred. Please try again later.",
    ErrorCode.DATABASE_ERROR: "A database error occurred. Please try again.",
    ErrorCode.SERVICE_UNAVAILABLE: "The service is temporarily unavailable.",
    ErrorCode.PROCESSING_ERROR: "Failed to process your request.",
    ErrorCode.TIMEOUT: "The request took too long. Please try again.",

    ErrorCode.CALCULATION_ERROR: "Failed to calculate tax values. Please verify your data.",
    ErrorCode.DATA_INCOMPLETE: "More information is needed to complete this action.",
    ErrorCode.INVALID_STATE: "This action cannot be performed in the current state.",
}


class ErrorDetail(BaseModel):
    """Detailed error information."""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class StandardErrorResponse(BaseModel):
    """
    Standardized error response structure.

    All API errors should use this format for consistency.
    """
    success: bool = False
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="User-friendly error message")
    details: Optional[List[ErrorDetail]] = Field(
        None, description="Additional error details"
    )
    request_id: Optional[str] = Field(
        None, description="Request ID for tracking"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Error timestamp"
    )

    # Optional fields for debugging (only in development)
    debug_info: Optional[Dict[str, Any]] = None


def create_error_response(
    error_code: ErrorCode,
    message: Optional[str] = None,
    details: Optional[List[Dict[str, Any]]] = None,
    request_id: Optional[str] = None,
    debug_info: Optional[Dict[str, Any]] = None,
    include_debug: bool = False,
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        error_code: The error code enum
        message: Optional custom message (uses default if not provided)
        details: Optional list of detailed error information
        request_id: Optional request ID for tracking
        debug_info: Optional debug information (only included if include_debug=True)
        include_debug: Whether to include debug info in response

    Returns:
        JSONResponse with standardized error format

    Example:
        >>> from web.helpers.error_responses import create_error_response, ErrorCode
        >>> response = create_error_response(
        ...     ErrorCode.NOT_FOUND,
        ...     message="Tax return not found",
        ...     request_id="REQ-123"
        ... )
    """
    status_code = ERROR_STATUS_MAP.get(
        error_code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    user_message = message or DEFAULT_MESSAGES.get(
        error_code, "An error occurred."
    )

    error_details = None
    if details:
        error_details = [
            ErrorDetail(
                field=d.get("field"),
                message=d.get("message", ""),
                code=d.get("code")
            )
            for d in details
        ]

    response_data = StandardErrorResponse(
        error_code=error_code.value,
        message=user_message,
        details=error_details,
        request_id=request_id,
        debug_info=debug_info if include_debug else None,
    )

    return JSONResponse(
        status_code=status_code,
        content=response_data.model_dump(exclude_none=True)
    )


def raise_api_error(
    error_code: ErrorCode,
    message: Optional[str] = None,
    details: Optional[List[Dict[str, Any]]] = None,
    request_id: Optional[str] = None,
):
    """
    Raise an HTTPException with standardized error format.

    Args:
        error_code: The error code enum
        message: Optional custom message
        details: Optional list of detailed errors
        request_id: Optional request ID

    Raises:
        HTTPException with standardized detail format
    """
    status_code = ERROR_STATUS_MAP.get(
        error_code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    user_message = message or DEFAULT_MESSAGES.get(
        error_code, "An error occurred."
    )

    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error_code": error_code.value,
            "message": user_message,
            "details": details,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }
    )


def handle_validation_error(errors: List[Dict[str, Any]], request_id: Optional[str] = None) -> JSONResponse:
    """
    Handle Pydantic validation errors with standardized format.

    Args:
        errors: List of validation errors from Pydantic
        request_id: Optional request ID

    Returns:
        JSONResponse with validation error details
    """
    details = []
    for error in errors:
        field = ".".join(str(loc) for loc in error.get("loc", []))
        details.append({
            "field": field,
            "message": error.get("msg", "Invalid value"),
            "code": error.get("type", "validation_error")
        })

    return create_error_response(
        ErrorCode.VALIDATION_ERROR,
        message="Please check your input and try again.",
        details=details,
        request_id=request_id,
    )


def not_found_error(
    resource_type: str = "Resource",
    resource_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """
    Create a standardized not found error.

    Args:
        resource_type: Type of resource (e.g., "Tax Return", "Session")
        resource_id: Optional ID of the resource
        request_id: Optional request ID

    Returns:
        JSONResponse with not found error
    """
    if resource_id:
        message = f"{resource_type} with ID '{resource_id}' not found."
    else:
        message = f"{resource_type} not found."

    return create_error_response(
        ErrorCode.NOT_FOUND,
        message=message,
        request_id=request_id,
    )


def server_error(
    message: str = "An unexpected error occurred.",
    request_id: Optional[str] = None,
    log_exception: bool = True,
) -> JSONResponse:
    """
    Create a standardized server error response.

    Args:
        message: User-friendly error message
        request_id: Optional request ID
        log_exception: Whether to log the exception

    Returns:
        JSONResponse with server error
    """
    if log_exception:
        logger.exception(f"Server error: {message}")

    return create_error_response(
        ErrorCode.INTERNAL_ERROR,
        message=message,
        request_id=request_id,
    )


# Loading state helpers for frontend
class LoadingState(str, Enum):
    """Loading states for async operations."""
    IDLE = "idle"
    LOADING = "loading"
    SUCCESS = "success"
    ERROR = "error"


def create_loading_response(
    operation: str,
    state: LoadingState = LoadingState.LOADING,
    progress: Optional[float] = None,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a loading state response for async operations.

    Args:
        operation: Name of the operation
        state: Current loading state
        progress: Optional progress percentage (0-100)
        message: Optional status message

    Returns:
        Dict with loading state information
    """
    return {
        "operation": operation,
        "state": state.value,
        "progress": progress,
        "message": message or f"{operation} in progress...",
        "timestamp": datetime.now().isoformat(),
    }


# =============================================================================
# SAFE ERROR HANDLING
# =============================================================================

def safe_error_message(
    exception: Exception,
    context: str = "operation",
    allow_value_errors: bool = True,
) -> str:
    """
    Get a safe, user-friendly error message from an exception.

    SECURITY: This function prevents internal error details from leaking
    to API responses. Use this instead of str(e) in exception handlers.

    Args:
        exception: The caught exception
        context: Description of what failed (e.g., "file upload", "OAuth")
        allow_value_errors: If True, expose ValueError messages (usually validation)

    Returns:
        A user-friendly error message
    """
    import os

    # In development, you may want to see full errors
    is_dev = os.environ.get("APP_ENVIRONMENT", "").lower() in ("development", "dev", "local", "test")

    # Log the full error for debugging
    logger.exception(f"Error during {context}")

    # ValueErrors are usually validation/business logic - safe to expose
    if allow_value_errors and isinstance(exception, ValueError):
        msg = str(exception)
        # Still sanitize - don't expose paths or internal details
        if any(sensitive in msg.lower() for sensitive in ["/", "\\", "sql", "query", "database", "password", "secret", "key", "token"]):
            return f"Invalid input for {context}. Please check your data."
        return msg

    # Known safe exception types
    if isinstance(exception, (KeyError, IndexError)):
        return f"Required data is missing for {context}."

    if isinstance(exception, TimeoutError):
        return f"The {context} timed out. Please try again."

    if isinstance(exception, PermissionError):
        return f"Permission denied for {context}."

    if isinstance(exception, FileNotFoundError):
        return f"Required file not found for {context}."

    # For all other exceptions, return generic message
    # In development, include exception type
    if is_dev:
        return f"{context} failed: {type(exception).__name__}"

    return f"An error occurred during {context}. Please try again later."


def raise_safe_error(
    exception: Exception,
    status_code: int = 500,
    context: str = "operation",
    allow_value_errors: bool = True,
) -> None:
    """
    Raise an HTTPException with a safe error message.

    Usage:
        try:
            do_something()
        except Exception as e:
            raise_safe_error(e, context="processing request")

    Args:
        exception: The caught exception
        status_code: HTTP status code (default 500)
        context: Description of what failed
        allow_value_errors: If True, expose ValueError messages
    """
    raise HTTPException(
        status_code=status_code,
        detail=safe_error_message(exception, context, allow_value_errors)
    )
