"""
Feature Flags for UX v2 Rollout

Provides configuration and utilities for gradual UX migration.
Uses cookie-based consistency to ensure users see the same version across sessions.

Configuration:
- UX_V2_ENABLED: Master switch for v2 templates (default: False)
- UX_V2_PERCENTAGE: Rollout percentage 0-100 (default: 0)

Usage:
    from web.feature_flags import should_use_ux_v2, get_template_path

    # In route handler:
    if should_use_ux_v2(request):
        return templates.TemplateResponse("v2/dashboard.html", context)
    else:
        return templates.TemplateResponse("dashboard.html", context)

    # Or use the resolver:
    template_path = get_template_path(request, "dashboard.html")
    return templates.TemplateResponse(template_path, context)
"""

import os
import hashlib
from typing import Optional
from fastapi import Request, Response


# =============================================================================
# CONFIGURATION
# =============================================================================

# Master switch - must be True for any v2 features
UX_V2_ENABLED = os.environ.get("UX_V2_ENABLED", "false").lower() == "true"

# Percentage of users to show v2 (0-100)
# Set to 0 for internal testing only, 100 for full rollout
UX_V2_PERCENTAGE = int(os.environ.get("UX_V2_PERCENTAGE", "0"))

# Cookie name for version consistency
UX_VERSION_COOKIE = "ux_version"

# Query parameter for admin override
UX_OVERRIDE_PARAM = "ux_v2"


# =============================================================================
# FEATURE FLAG LOGIC
# =============================================================================

def should_use_ux_v2(request: Request) -> bool:
    """
    Determine if the request should use UX v2 templates.

    Priority order:
    1. Query parameter override (?ux_v2=1 or ?ux_v2=0)
    2. Existing cookie (for session consistency)
    3. Percentage-based rollout (uses client IP hash for consistency)

    Args:
        request: FastAPI request object

    Returns:
        True if v2 should be used, False otherwise
    """
    # Master switch must be on
    if not UX_V2_ENABLED:
        return False

    # Check for admin override in query params
    override = request.query_params.get(UX_OVERRIDE_PARAM)
    if override is not None:
        return override in ("1", "true", "yes")

    # Check for existing cookie (session consistency)
    cookie_value = request.cookies.get(UX_VERSION_COOKIE)
    if cookie_value == "v2":
        return True
    elif cookie_value == "v1":
        return False

    # No cookie - use percentage rollout
    if UX_V2_PERCENTAGE >= 100:
        return True
    elif UX_V2_PERCENTAGE <= 0:
        return False

    # Hash-based bucketing for consistent assignment
    # Uses client IP or session ID for stability
    client_id = _get_client_identifier(request)
    bucket = _hash_to_bucket(client_id)

    return bucket < UX_V2_PERCENTAGE


def set_ux_version_cookie(response: Response, use_v2: bool) -> None:
    """
    Set the UX version cookie for session consistency.

    Args:
        response: FastAPI response object
        use_v2: Whether to set v2 version
    """
    version = "v2" if use_v2 else "v1"
    response.set_cookie(
        key=UX_VERSION_COOKIE,
        value=version,
        max_age=60 * 60 * 24 * 30,  # 30 days
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT", "production").lower() in ("production", "prod", "staging"),
    )


def get_template_path(request: Request, template_name: str) -> str:
    """
    Resolve template path based on UX version.

    If using v2, checks if v2 version exists and returns it.
    Falls back to original template if v2 doesn't exist.

    Args:
        request: FastAPI request object
        template_name: Original template name (e.g., "dashboard.html")

    Returns:
        Resolved template path (e.g., "v2/dashboard.html" or "dashboard.html")
    """
    if should_use_ux_v2(request):
        # Check if v2 template exists
        v2_path = f"v2/{template_name}"
        # Return v2 path - Jinja2 will raise error if not found,
        # which is intentional to catch missing migrations
        return v2_path

    return template_name


def get_template_path_with_fallback(
    request: Request,
    template_name: str,
    templates_dir: str
) -> str:
    """
    Resolve template path with fallback to original if v2 doesn't exist.

    Use this for gradual migration where not all templates have v2 versions.

    Args:
        request: FastAPI request object
        template_name: Original template name
        templates_dir: Path to templates directory

    Returns:
        Resolved template path with fallback
    """
    import os.path

    if should_use_ux_v2(request):
        v2_path = f"v2/{template_name}"
        full_path = os.path.join(templates_dir, v2_path)
        if os.path.exists(full_path):
            return v2_path

    return template_name


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_client_identifier(request: Request) -> str:
    """
    Get a stable identifier for the client.

    Uses X-Forwarded-For header if available (behind proxy),
    otherwise falls back to client IP.
    """
    # Try to get real IP behind proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take first IP in chain (original client)
        return forwarded.split(",")[0].strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    # Last resort - use a random but consistent value
    return "unknown-client"


def _hash_to_bucket(identifier: str) -> int:
    """
    Hash an identifier to a bucket 0-99.

    Uses MD5 for speed and uniform distribution.
    The same identifier always maps to the same bucket.
    """
    hash_bytes = hashlib.md5(identifier.encode()).digest()
    # Use first 4 bytes as integer, mod 100 for bucket
    hash_int = int.from_bytes(hash_bytes[:4], byteorder="big")
    return hash_int % 100


# =============================================================================
# TEMPLATE HELPERS (for use in Jinja2)
# =============================================================================

def get_ux_version(request: Request) -> str:
    """Get current UX version string for template context."""
    return "v2" if should_use_ux_v2(request) else "v1"


def ux_v2_enabled() -> bool:
    """Check if UX v2 is globally enabled."""
    return UX_V2_ENABLED


def ux_v2_percentage() -> int:
    """Get current rollout percentage."""
    return UX_V2_PERCENTAGE
