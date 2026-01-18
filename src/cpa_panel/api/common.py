"""
Common utilities for CPA Panel API routes.

Shared helpers, dependency injection, error formatting, and database utilities.
"""

from typing import Dict, Any, Optional, Callable, TypeVar
from datetime import datetime
from enum import Enum
from contextlib import contextmanager
from functools import wraps
import logging
import sqlite3
import os
import time
import uuid
import re

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# ERROR CODES - Consistent API Error Classification
# =============================================================================

class ErrorCode(str, Enum):
    """Standard error codes for API responses."""
    SUCCESS = "SUCCESS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    DB_QUERY_ERROR = "DB_QUERY_ERROR"
    DB_TIMEOUT = "DB_TIMEOUT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BAD_REQUEST = "BAD_REQUEST"


# =============================================================================
# ERROR FORMATTING
# =============================================================================

def format_error_response(
    message: str,
    code: str = "CPA_ERROR",
    details: Optional[Dict] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Format a standard error response with optional details."""
    response = {
        "success": False,
        "error": True,
        "code": code,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if details:
        response["details"] = details
    if request_id:
        response["request_id"] = request_id
    return response


def format_success_response(data: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
    """Format a standard success response."""
    response = {
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
        **data,
    }
    if request_id:
        response["request_id"] = request_id
    return response


def generate_request_id() -> str:
    """Generate a unique request ID for tracing."""
    return f"req_{uuid.uuid4().hex[:12]}"


# =============================================================================
# DATABASE CONNECTION MANAGEMENT
# =============================================================================

def _get_db_path() -> str:
    """Get the database path, checking multiple possible locations."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    paths_to_try = [
        os.path.join(base_dir, "database", "jorss_gbo.db"),
        os.path.join(base_dir, "..", "data", "tax_returns.db"),
        os.path.join(base_dir, "database", "tax_returns.db"),
    ]
    for path in paths_to_try:
        if os.path.exists(path):
            return path
    return paths_to_try[0]


DB_PATH = _get_db_path()


@contextmanager
def get_db_connection(timeout: int = 30, retries: int = 3):
    """
    Context manager for database connections with retry logic.

    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)

    Features:
    - Automatic connection cleanup
    - Retry with exponential backoff on failure
    - Configurable timeout
    - Proper error categorization
    """
    conn = None
    last_error = None

    for attempt in range(retries):
        try:
            if not os.path.exists(DB_PATH):
                raise FileNotFoundError(f"Database not found: {DB_PATH}")

            conn = sqlite3.connect(DB_PATH, timeout=timeout)
            conn.row_factory = sqlite3.Row
            # Enable busy timeout for concurrent access
            conn.execute(f"PRAGMA busy_timeout = {timeout * 1000}")

            yield conn
            return

        except sqlite3.OperationalError as e:
            last_error = e
            if "locked" in str(e).lower() and attempt < retries - 1:
                wait_time = (2 ** attempt) * 0.1  # Exponential backoff: 0.1s, 0.2s, 0.4s
                logger.warning(f"Database locked, retrying in {wait_time}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait_time)
                continue
            raise
        except Exception as e:
            last_error = e
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # If we exhausted retries
    raise last_error or sqlite3.OperationalError("Failed to connect to database")


def with_db_retry(retries: int = 3, base_delay: float = 0.1):
    """
    Decorator for database operations with automatic retry.

    Usage:
        @with_db_retry(retries=3)
        def fetch_clients():
            with get_db_connection() as conn:
                ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error = None
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                    last_error = e
                    if attempt < retries - 1:
                        wait_time = (2 ** attempt) * base_delay
                        logger.warning(
                            f"DB operation failed, retry {attempt + 1}/{retries}",
                            extra={"error": str(e), "wait_time": wait_time}
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"DB operation failed after {retries} retries",
                            extra={"error": str(e), "function": func.__name__}
                        )
            raise last_error
        return wrapper
    return decorator


# =============================================================================
# INPUT VALIDATION HELPERS
# =============================================================================

def validate_session_id(session_id: str) -> tuple[bool, str]:
    """
    Validate session ID format.

    Returns (is_valid, error_message)
    """
    if not session_id:
        return False, "Session ID is required"
    if len(session_id) > 100:
        return False, "Session ID too long (max 100 characters)"
    # Allow alphanumeric, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
        return False, "Session ID contains invalid characters"
    return True, ""


def validate_pagination(limit: int, offset: int, max_limit: int = 500) -> tuple[bool, str]:
    """
    Validate pagination parameters.

    Returns (is_valid, error_message)
    """
    if limit < 1:
        return False, "Limit must be at least 1"
    if limit > max_limit:
        return False, f"Limit cannot exceed {max_limit}"
    if offset < 0:
        return False, "Offset cannot be negative"
    return True, ""


def sanitize_search_query(query: str, max_length: int = 100) -> str:
    """
    Sanitize search query for safe database use.

    - Truncates to max length
    - Removes dangerous characters
    - Escapes SQL wildcards if needed
    """
    if not query:
        return ""
    # Truncate
    query = query[:max_length]
    # Remove potentially dangerous characters
    query = re.sub(r'[;\'"\\]', '', query)
    return query.strip()


def validate_enum_value(value: str, allowed_values: list[str], field_name: str) -> tuple[bool, str]:
    """
    Validate that a value is in an allowed list.

    Returns (is_valid, error_message)
    """
    if not value:
        return True, ""  # Empty is allowed (optional)
    if value not in allowed_values:
        return False, f"Invalid {field_name}: must be one of {allowed_values}"
    return True, ""


# =============================================================================
# STRUCTURED LOGGING HELPER
# =============================================================================

def log_api_event(
    event_type: str,
    message: str,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    **extra
):
    """
    Log an API event with structured context.

    Example:
        log_api_event(
            "API_REQUEST",
            "Fetched client data",
            request_id="req_abc123",
            session_id="session-001",
            duration_ms=45.2
        )
    """
    log_data = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if request_id:
        log_data["request_id"] = request_id
    if session_id:
        log_data["session_id"] = session_id
    if tenant_id:
        log_data["tenant_id"] = tenant_id
    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)
    log_data.update(extra)

    logger.info(message, extra=log_data)


# =============================================================================
# HTTP STATUS CODES (REST API Standards)
# =============================================================================

class HTTPStatus:
    """Standard HTTP status codes for REST API responses."""
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503


# =============================================================================
# SECURITY HEADERS (OWASP Standards)
# =============================================================================

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}


def get_security_headers() -> Dict[str, str]:
    """Get standard security headers for API responses."""
    return SECURITY_HEADERS.copy()


# =============================================================================
# RATE LIMITING SUPPORT
# =============================================================================

_rate_limit_store: Dict[str, list] = {}


def check_rate_limit(
    identifier: str,
    max_requests: int = 100,
    window_seconds: int = 60
) -> tuple[bool, int]:
    """
    Simple in-memory rate limiting.

    Args:
        identifier: Unique identifier (e.g., tenant_id, IP)
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds

    Returns:
        (allowed, remaining_requests)
    """
    import time as t
    now = t.time()
    window_start = now - window_seconds

    # Clean old entries
    if identifier in _rate_limit_store:
        _rate_limit_store[identifier] = [
            ts for ts in _rate_limit_store[identifier]
            if ts > window_start
        ]
    else:
        _rate_limit_store[identifier] = []

    current_count = len(_rate_limit_store[identifier])

    if current_count >= max_requests:
        return False, 0

    _rate_limit_store[identifier].append(now)
    return True, max_requests - current_count - 1


# =============================================================================
# HATEOAS LINKS (REST API Standards)
# =============================================================================

def build_hateoas_links(
    base_url: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    page: Optional[int] = None,
    total_pages: Optional[int] = None,
) -> Dict[str, str]:
    """
    Build HATEOAS links for REST API responses.

    Example:
        links = build_hateoas_links("/api/cpa", "clients", "client-001")
        # Returns: {"self": "/api/cpa/clients/client-001", ...}
    """
    links = {}

    if resource_id:
        links["self"] = f"{base_url}/{resource_type}/{resource_id}"
    else:
        links["self"] = f"{base_url}/{resource_type}"

    # Pagination links
    if page is not None and total_pages is not None:
        if page > 1:
            links["first"] = f"{base_url}/{resource_type}?page=1"
            links["prev"] = f"{base_url}/{resource_type}?page={page - 1}"
        if page < total_pages:
            links["next"] = f"{base_url}/{resource_type}?page={page + 1}"
            links["last"] = f"{base_url}/{resource_type}?page={total_pages}"

    return links


# =============================================================================
# I18N SUPPORT (Internationalization Readiness)
# =============================================================================

# Default messages (English) - can be overridden by locale files
_i18n_messages = {
    "en": {
        "error.validation": "Validation error",
        "error.not_found": "Resource not found",
        "error.db_connection": "Database connection error",
        "error.db_query": "Database query error",
        "error.rate_limit": "Too many requests. Please try again later.",
        "error.unauthorized": "Authentication required",
        "error.forbidden": "You don't have permission to access this resource",
        "error.internal": "An internal error occurred",
        "success.created": "Resource created successfully",
        "success.updated": "Resource updated successfully",
        "success.deleted": "Resource deleted successfully",
    }
}

_current_locale = "en"


def set_locale(locale: str):
    """Set the current locale for i18n messages."""
    global _current_locale
    _current_locale = locale


def t(key: str, locale: Optional[str] = None, **kwargs) -> str:
    """
    Translate a message key to the current locale.

    Usage:
        t("error.not_found")  # Returns: "Resource not found"
        t("error.validation", field="email")  # With interpolation
    """
    loc = locale or _current_locale
    messages = _i18n_messages.get(loc, _i18n_messages["en"])
    message = messages.get(key, key)

    # Simple string interpolation
    if kwargs:
        for k, v in kwargs.items():
            message = message.replace(f"{{{k}}}", str(v))

    return message


def format_number(value: float, locale: str = "en-US") -> str:
    """Format a number according to locale conventions."""
    # Basic implementation - in production, use babel or similar
    if locale.startswith("en"):
        return f"{value:,.2f}"
    elif locale.startswith("de"):
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{value:.2f}"


def format_date(dt: datetime, locale: str = "en-US", format_type: str = "short") -> str:
    """Format a datetime according to locale conventions."""
    if format_type == "iso":
        return dt.isoformat()
    elif format_type == "short":
        if locale.startswith("en-US"):
            return dt.strftime("%m/%d/%Y")
        elif locale.startswith("en-GB") or locale.startswith("de"):
            return dt.strftime("%d/%m/%Y")
    return dt.isoformat()


# =============================================================================
# ENHANCED ERROR RESPONSE WITH STANDARDS
# =============================================================================

def format_api_error(
    message: str,
    code: str = "INTERNAL_ERROR",
    status: int = 500,
    request_id: Optional[str] = None,
    details: Optional[Dict] = None,
    links: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Format a standardized API error response (RFC 7807 inspired).

    Includes:
    - Standard error structure
    - Request ID for tracing
    - HATEOAS links
    - Timestamp
    """
    response = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "status": status,
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "api_version": "1.0",
    }

    if request_id:
        response["request_id"] = request_id
    if details:
        response["error"]["details"] = details
    if links:
        response["_links"] = links

    return response


def format_api_success(
    data: Dict[str, Any],
    status: int = 200,
    request_id: Optional[str] = None,
    links: Optional[Dict] = None,
    meta: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Format a standardized API success response.

    Includes:
    - Standard success structure
    - HATEOAS links
    - Pagination metadata
    - API version
    """
    response = {
        "success": True,
        "data": data,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "api_version": "1.0",
    }

    if request_id:
        response["request_id"] = request_id
    if links:
        response["_links"] = links
    if meta:
        response["meta"] = meta

    return response


# =============================================================================
# DEPENDENCY INJECTION HELPERS
# =============================================================================

def get_tax_return_adapter():
    """Get the tax return adapter instance."""
    from cpa_panel.adapters import TaxReturnAdapter
    return TaxReturnAdapter()


def get_session_adapter():
    """Get the session adapter instance."""
    from cpa_panel.adapters import SessionAdapter
    return SessionAdapter()


def get_workflow_manager():
    """Get the workflow manager instance."""
    from cpa_panel.workflow import CPAWorkflowManager
    return CPAWorkflowManager()


def get_approval_manager():
    """Get the approval manager instance."""
    from cpa_panel.workflow import ApprovalManager
    return ApprovalManager()


def get_notes_manager():
    """Get the notes manager instance."""
    from cpa_panel.workflow import NotesManager
    return NotesManager()


_lead_state_engine = None


def get_lead_state_engine():
    """
    Get the lead state engine instance with persistence.

    Returns a singleton engine with database-backed persistence.
    """
    global _lead_state_engine
    if _lead_state_engine is None:
        from cpa_panel.lead_state import LeadStateEngine
        from src.database.lead_state_persistence import get_lead_state_persistence

        persistence = get_lead_state_persistence()
        _lead_state_engine = LeadStateEngine(persistence=persistence)

    return _lead_state_engine


# =============================================================================
# TENANT EXTRACTION
# =============================================================================

def get_tenant_id(request) -> str:
    """
    Extract tenant ID from request.

    Checks headers, query params, or defaults to 'default'.
    """
    # Check header first
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        return tenant_id

    # Check query params
    tenant_id = request.query_params.get("tenant_id")
    if tenant_id:
        return tenant_id

    return "default"


# =============================================================================
# UNIFIED AUTH CONTEXT (RBAC Integration)
# =============================================================================

def get_cpa_auth_context(request):
    """
    Get CPA authentication context from request.

    Integrates with the global RBAC system when available.
    Returns a context object with user permissions for CPA operations.

    Usage:
        @router.get("/cpa/clients")
        async def list_clients(request: Request):
            auth = get_cpa_auth_context(request)
            if not auth.is_cpa:
                raise HTTPException(403, "CPA access required")
    """
    from dataclasses import dataclass, field
    from typing import Set

    @dataclass
    class CPAAuthContext:
        """CPA-specific authentication context."""
        user_id: Optional[str] = None
        firm_id: Optional[str] = None
        email: Optional[str] = None
        role: Optional[str] = None
        is_cpa: bool = False
        is_authenticated: bool = False
        permissions: Set[str] = field(default_factory=set)
        staff_role: Optional[str] = None  # "preparer", "reviewer", "partner"

        def has_permission(self, permission: str) -> bool:
            """Check if user has permission."""
            return permission in self.permissions

        def can_access_client(self, client_id: str, assigned_clients: list = None) -> bool:
            """Check if user can access a specific client."""
            if not self.is_authenticated:
                return False
            if self.role in ("firm_admin", "senior_preparer"):
                return True
            if assigned_clients and client_id in assigned_clients:
                return True
            return False

    # Try to get from new RBAC system
    try:
        from core.rbac.dependencies import RBACContext

        rbac_ctx = getattr(request.state, "rbac", None)
        if rbac_ctx and isinstance(rbac_ctx, RBACContext) and rbac_ctx.is_authenticated:
            # Determine staff role from RBAC role
            staff_role = None
            if rbac_ctx.primary_role in ("preparer", "senior_preparer"):
                staff_role = "preparer"
            elif rbac_ctx.primary_role == "reviewer":
                staff_role = "reviewer"
            elif rbac_ctx.primary_role in ("firm_admin", "partner_admin"):
                staff_role = "partner"

            return CPAAuthContext(
                user_id=str(rbac_ctx.user_id) if rbac_ctx.user_id else None,
                firm_id=str(rbac_ctx.firm_id) if rbac_ctx.firm_id else None,
                email=rbac_ctx.email,
                role=rbac_ctx.primary_role,
                is_cpa=rbac_ctx.firm_id is not None,
                is_authenticated=True,
                permissions=rbac_ctx.permissions,
                staff_role=staff_role,
            )
    except ImportError:
        pass

    # Try legacy admin panel auth
    try:
        from admin_panel.auth.rbac import TenantContext

        tenant_ctx = getattr(request.state, "user", None)
        if tenant_ctx and isinstance(tenant_ctx, TenantContext):
            staff_role = None
            if tenant_ctx.role in ("preparer", "senior_preparer"):
                staff_role = "preparer"
            elif tenant_ctx.role == "reviewer":
                staff_role = "reviewer"
            elif tenant_ctx.role == "firm_admin":
                staff_role = "partner"

            return CPAAuthContext(
                user_id=tenant_ctx.user_id,
                firm_id=tenant_ctx.firm_id,
                email=tenant_ctx.email,
                role=tenant_ctx.role,
                is_cpa=tenant_ctx.firm_id is not None,
                is_authenticated=True,
                permissions=tenant_ctx.permissions,
                staff_role=staff_role,
            )
    except ImportError:
        pass

    # Check headers for basic CPA identification
    is_cpa = request.headers.get("X-Is-CPA", "").lower() == "true"
    staff_role = request.headers.get("X-Staff-Role")

    return CPAAuthContext(
        is_cpa=is_cpa,
        staff_role=staff_role,
    )


def require_cpa_permission(permission: str):
    """
    Decorator to require a specific CPA permission.

    Usage:
        @router.post("/cpa/clients")
        @require_cpa_permission("create_client")
        async def create_client(request: Request):
            ...
    """
    from functools import wraps
    from fastapi import HTTPException

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if hasattr(arg, "headers"):
                        request = arg
                        break

            if request:
                auth = get_cpa_auth_context(request)
                if not auth.is_authenticated:
                    raise HTTPException(
                        status_code=401,
                        detail="Authentication required",
                    )
                if not auth.has_permission(permission):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Permission denied: {permission} required",
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def map_staff_role_to_rbac(staff_role: str) -> str:
    """
    Map CPA Panel staff role to RBAC role code.

    Staff roles: "preparer", "reviewer", "partner"
    RBAC roles: "preparer", "reviewer", "senior_preparer", "firm_admin"
    """
    mapping = {
        "preparer": "preparer",
        "reviewer": "reviewer",
        "partner": "firm_admin",
        "senior": "senior_preparer",
    }
    return mapping.get(staff_role, "preparer")
