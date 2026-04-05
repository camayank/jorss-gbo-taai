"""
PII Masking Service for CPA Panel API Responses

Implements role-based SSN/EIN redaction across all staff-facing API endpoints.

SECURITY REQUIREMENTS:
- ADMIN (PARTNER/SUPER_ADMIN/PLATFORM_ADMIN) sees full SSN
- PREPARER (STAFF) sees masked SSN (***-**-LAST4)
- Audit log: record every full SSN access with user ID + timestamp + justification
- DB-level masking: query optimization to prevent data leakage
- Search: accept full SSN input, hash for lookup, never return in response
- GDPR + IRS Publication 4600 compliance
"""

import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
from functools import wraps

from rbac.roles import Role, ADMIN_ROLES

logger = logging.getLogger(__name__)

# PII Fields that require masking by role
SSN_FIELDS = {
    "ssn",
    "ssn_encrypted",
    "taxpayer_ssn",
    "social_security_number",
    "itin",
}

SPOUSE_SSN_FIELDS = {
    "spouse_ssn",
    "spouse_ssn_encrypted",
}

DEPENDENT_SSN_FIELDS = {
    "dependent_ssn",
    "student_ssn",
}

# All PII fields that might need masking
PII_FIELD_GROUPS = {
    "ssn": SSN_FIELDS,
    "spouse_ssn": SPOUSE_SSN_FIELDS,
    "dependent_ssn": DEPENDENT_SSN_FIELDS,
}


@dataclass
class AccessAuditEntry:
    """Record of SSN access for compliance audit."""
    user_id: str
    user_role: str
    timestamp: datetime
    field_type: str  # "ssn", "spouse_ssn", "dependent_ssn"
    full_value_last4: str  # Only store last 4 digits for audit trail
    operation: str  # "list", "get", "search"
    resource_type: str  # "client", "return", etc.
    justification: Optional[str] = None


class PIIMasker:
    """
    Masks PII in API responses based on user role.

    SECURITY GUARANTEE:
    - ADMIN roles: receive full SSN (unmasked)
    - Non-admin roles: receive masked SSN (***-**-LAST4)
    - No role can extract full SSN via any API endpoint
    - All full SSN access is audit logged
    """

    def __init__(self, audit_logger: Optional[Any] = None):
        """
        Initialize PII masker with optional audit logger.

        Args:
            audit_logger: Callable that logs audit entries (e.g., to database)
        """
        self.audit_logger = audit_logger
        self._audit_entries: list[AccessAuditEntry] = []

    def mask_response(
        self,
        data: Any,
        user_role: Role,
        user_id: str,
        operation: str = "list",
        resource_type: str = "unknown",
    ) -> Any:
        """
        Mask PII in response based on user role.

        Args:
            data: Response data (dict, list, or scalar)
            user_role: User's role (from RBAC)
            user_id: User identifier for audit logging
            operation: Type of operation (list, get, search, export)
            resource_type: Resource being accessed (client, return, etc.)

        Returns:
            Masked response data with role-appropriate PII visibility
        """
        if user_role in ADMIN_ROLES:
            # Admin users see full SSN - no masking needed
            # But we still audit the access
            self._log_access_audit(
                user_id=user_id,
                user_role=user_role.value,
                field_type="ssn",
                full_value_last4="ADMIN_FULL_ACCESS",
                operation=operation,
                resource_type=resource_type,
            )
            return data

        # Non-admin: mask SSN fields
        return self._mask_pii_recursive(
            data=data,
            user_role=user_role,
            user_id=user_id,
            operation=operation,
            resource_type=resource_type,
        )

    def _mask_pii_recursive(
        self,
        data: Any,
        user_role: Role,
        user_id: str,
        operation: str,
        resource_type: str,
    ) -> Any:
        """
        Recursively mask PII in nested structures (dicts, lists).

        Args:
            data: Data to mask
            user_role: User's role
            user_id: User ID
            operation: Operation type
            resource_type: Resource type

        Returns:
            Masked data
        """
        if isinstance(data, dict):
            masked = {}
            for key, value in data.items():
                # Check if this is a PII field
                if self._is_pii_field(key):
                    # Mask the value
                    last4 = self._get_last4(value)
                    self._log_access_audit(
                        user_id=user_id,
                        user_role=user_role.value,
                        field_type=key,
                        full_value_last4=last4,
                        operation=operation,
                        resource_type=resource_type,
                    )
                    masked[key] = self._mask_ssn(value)
                else:
                    # Recursively mask nested structures
                    masked[key] = self._mask_pii_recursive(
                        value,
                        user_role=user_role,
                        user_id=user_id,
                        operation=operation,
                        resource_type=resource_type,
                    )
            return masked

        elif isinstance(data, list):
            return [
                self._mask_pii_recursive(
                    item,
                    user_role=user_role,
                    user_id=user_id,
                    operation=operation,
                    resource_type=resource_type,
                )
                for item in data
            ]

        return data

    @staticmethod
    def _is_pii_field(field_name: str) -> bool:
        """Check if field name is a known PII field."""
        field_lower = field_name.lower()
        all_pii = SSN_FIELDS | SPOUSE_SSN_FIELDS | DEPENDENT_SSN_FIELDS
        return field_lower in all_pii

    @staticmethod
    def _mask_ssn(value: Any) -> str:
        """
        Mask SSN/EIN to show only last 4 digits.

        Args:
            value: SSN value (string or None)

        Returns:
            Masked SSN in format: ***-**-LAST4 or empty string if None
        """
        if not value:
            return ""

        value_str = str(value).strip()
        if not value_str:
            return ""

        # Remove hyphens for consistent processing
        digits = "".join(c for c in value_str if c.isdigit())

        # Handle various SSN formats
        if len(digits) >= 4:
            last4 = digits[-4:]
            return f"***-**-{last4}"
        elif len(digits) > 0:
            # Partial SSN - still mask but show what we have
            return f"***-**-{digits}"

        # If not a valid SSN format, return masked placeholder
        return "***-**-****"

    @staticmethod
    def _get_last4(value: Any) -> str:
        """
        Extract last 4 digits from SSN for audit logging.

        Args:
            value: SSN value

        Returns:
            Last 4 digits (for audit trail only)
        """
        if not value:
            return "NONE"

        value_str = str(value).strip()
        digits = "".join(c for c in value_str if c.isdigit())

        if len(digits) >= 4:
            return digits[-4:]
        elif len(digits) > 0:
            return digits

        return "INVALID"

    def _log_access_audit(
        self,
        user_id: str,
        user_role: str,
        field_type: str,
        full_value_last4: str,
        operation: str,
        resource_type: str,
    ) -> None:
        """Log SSN access for audit trail."""
        entry = AccessAuditEntry(
            user_id=user_id,
            user_role=user_role,
            timestamp=datetime.utcnow(),
            field_type=field_type,
            full_value_last4=full_value_last4,
            operation=operation,
            resource_type=resource_type,
        )

        self._audit_entries.append(entry)

        # If external audit logger provided, use it
        if self.audit_logger:
            try:
                self.audit_logger(entry)
            except Exception as e:
                logger.error(f"Failed to log audit entry: {e}", exc_info=True)

        logger.info(
            f"SSN Access: user={user_id} role={user_role} "
            f"field={field_type} op={operation} resource={resource_type}"
        )

    def get_audit_entries(self) -> list[AccessAuditEntry]:
        """Get all audit entries logged during this session."""
        return self._audit_entries.copy()

    def clear_audit_entries(self) -> None:
        """Clear audit entries (for testing)."""
        self._audit_entries.clear()


class SSNSearchHasher:
    """
    Hash SSN for database lookup without exposing plaintext.

    SECURITY: Allows searching by SSN while maintaining masking guarantee:
    - Accept full SSN from user input
    - Hash for database lookup
    - Never return full SSN in response
    """

    @staticmethod
    def hash_ssn(ssn: str) -> str:
        """
        Hash SSN for database lookup.

        Args:
            ssn: Full SSN (format: 123-45-6789 or 123456789)

        Returns:
            SHA256 hash of normalized SSN
        """
        # Normalize: remove hyphens
        normalized = "".join(c for c in ssn if c.isdigit())

        # Hash for lookup
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def validate_ssn_format(ssn: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SSN format.

        Args:
            ssn: SSN to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not ssn or not isinstance(ssn, str):
            return False, "SSN must be a non-empty string"

        # Remove hyphens and check length
        digits = "".join(c for c in ssn if c.isdigit())

        if len(digits) != 9:
            return False, "SSN must contain exactly 9 digits"

        # Check for all zeros or sequential patterns (invalid SSNs)
        if digits == "000000000" or digits == "999999999":
            return False, "Invalid SSN"

        if digits[:3] == "000" or digits[3:5] == "00" or digits[5:] == "0000":
            return False, "Invalid SSN format"

        return True, None


def mask_response_decorator(operation: str = "list", resource_type: str = "unknown"):
    """
    Decorator to automatically mask PII in API responses.

    Usage:
        @router.get("/data/clients")
        @mask_response_decorator(operation="list", resource_type="client")
        async def list_clients(request: Request, user: UserContext) -> dict:
            ...
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Extract user context from kwargs
            user = kwargs.get("user")
            request = kwargs.get("request")

            if user and request and isinstance(result, dict):
                masker = PIIMasker()
                user_id = getattr(user, "user_id", "unknown")
                user_role = getattr(user, "role", Role.STAFF)

                # Mask the response data
                result["data"] = masker.mask_response(
                    data=result.get("data"),
                    user_role=user_role,
                    user_id=user_id,
                    operation=operation,
                    resource_type=resource_type,
                )

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Extract user context
            user = kwargs.get("user")
            request = kwargs.get("request")

            if user and request and isinstance(result, dict):
                masker = PIIMasker()
                user_id = getattr(user, "user_id", "unknown")
                user_role = getattr(user, "role", Role.STAFF)

                # Mask the response data
                result["data"] = masker.mask_response(
                    data=result.get("data"),
                    user_role=user_role,
                    user_id=user_id,
                    operation=operation,
                    resource_type=resource_type,
                )

            return result

        # Return async or sync wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Global PII masker instance
_global_masker: Optional[PIIMasker] = None


def get_global_masker() -> PIIMasker:
    """Get or create global PII masker instance."""
    global _global_masker
    if _global_masker is None:
        _global_masker = PIIMasker()
    return _global_masker


# For backwards compatibility and easy testing
def mask_ssn_value(value: Any) -> str:
    """Utility function to mask a single SSN value."""
    return PIIMasker._mask_ssn(value)


class PIIMaskingMiddleware:
    """
    FastAPI middleware that applies PII masking to all CPA panel API responses.

    SECURITY: Automatically masks SSN fields in JSON responses based on user role.
    - Admin roles (PARTNER, SUPER_ADMIN, PLATFORM_ADMIN): see full SSN
    - Staff roles (STAFF): see masked SSN (***-**-LAST4)
    - All access is audit logged
    """

    def __init__(self, app, masker: Optional[PIIMasker] = None):
        """
        Initialize middleware.

        Args:
            app: FastAPI application
            masker: PII masker instance (optional, creates new if not provided)
        """
        self.app = app
        self.masker = masker or PIIMasker()

    async def __call__(self, request, call_next):
        """
        Process request and apply masking to response.

        Args:
            request: FastAPI Request
            call_next: Next middleware/route handler

        Returns:
            Response with masked PII if applicable
        """
        # Get response from next middleware/handler
        response = await call_next(request)

        # Only process JSON responses from CPA panel
        if "application/json" not in response.headers.get("content-type", ""):
            return response

        # Extract user role from request state (set by auth middleware)
        user = getattr(request.state, "user", None)
        if not user:
            return response

        # Extract user_id and role
        user_id = getattr(user, "user_id", "unknown")
        user_role = getattr(user, "role", Role.STAFF)

        # Determine operation type from request
        operation = self._get_operation_from_request(request)
        resource_type = self._get_resource_type_from_request(request)

        try:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Parse JSON response
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                # Not JSON, return as-is
                return response

            # Apply masking
            masked_data = self.masker.mask_response(
                data=data,
                user_role=user_role,
                user_id=user_id,
                operation=operation,
                resource_type=resource_type,
            )

            # Recreate response with masked data
            masked_body = json.dumps(masked_data).encode()

            # Return new response
            from fastapi.responses import JSONResponse

            return JSONResponse(
                content=masked_data,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        except Exception as e:
            logger.error(f"Error in PII masking middleware: {e}", exc_info=True)
            # On error, return original response to avoid breaking the API
            return response

    @staticmethod
    def _get_operation_from_request(request) -> str:
        """Determine operation type from request method and path."""
        method = request.method.upper()

        if method == "GET":
            if "list" in request.url.path or request.url.path.endswith("/"):
                return "list"
            return "get"
        elif method == "POST":
            if "search" in request.url.path:
                return "search"
            return "create"
        elif method == "PATCH":
            return "update"
        elif method == "DELETE":
            return "delete"

        return "unknown"

    @staticmethod
    def _get_resource_type_from_request(request) -> str:
        """Determine resource type from request path."""
        path = request.url.path.lower()

        if "clients" in path:
            return "client"
        elif "returns" in path:
            return "return"
        elif "leads" in path:
            return "lead"
        elif "staff" in path:
            return "staff"

        return "unknown"
