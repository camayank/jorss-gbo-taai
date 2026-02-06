"""
API Versioning Module

Provides consistent API versioning across all endpoints.
Current version: v1

Usage:
    from core.api.versioning import API_V1_PREFIX, create_versioned_router

    router = create_versioned_router(prefix="/users", tags=["users"])
    # Creates router with prefix "/api/v1/users"
"""

from fastapi import APIRouter
from typing import Optional, List

# API Version Constants
API_VERSION = "v1"
API_PREFIX = "/api"
API_V1_PREFIX = f"{API_PREFIX}/{API_VERSION}"

# Deprecated version (for migration path)
API_LEGACY_PREFIX = "/api"


def create_versioned_router(
    prefix: str = "",
    tags: Optional[List[str]] = None,
    version: str = API_VERSION,
    deprecated: bool = False,
    **kwargs
) -> APIRouter:
    """
    Create an APIRouter with consistent versioned prefix.

    Args:
        prefix: Route prefix after version (e.g., "/users" -> "/api/v1/users")
        tags: OpenAPI tags for this router
        version: API version (default: v1)
        deprecated: Mark all routes as deprecated
        **kwargs: Additional APIRouter arguments

    Returns:
        APIRouter with versioned prefix
    """
    full_prefix = f"{API_PREFIX}/{version}{prefix}"

    return APIRouter(
        prefix=full_prefix,
        tags=tags,
        deprecated=deprecated,
        **kwargs
    )


def create_legacy_router(
    prefix: str = "",
    tags: Optional[List[str]] = None,
    **kwargs
) -> APIRouter:
    """
    Create an APIRouter with legacy (unversioned) prefix.

    Use this only for backward compatibility during migration.
    New endpoints should use create_versioned_router().

    Args:
        prefix: Route prefix after /api (e.g., "/users" -> "/api/users")
        tags: OpenAPI tags for this router
        **kwargs: Additional APIRouter arguments

    Returns:
        APIRouter with legacy prefix
    """
    full_prefix = f"{API_LEGACY_PREFIX}{prefix}"

    return APIRouter(
        prefix=full_prefix,
        tags=tags,
        deprecated=True,  # Mark legacy routes as deprecated
        **kwargs
    )


def get_versioned_path(path: str, version: str = API_VERSION) -> str:
    """
    Convert a path to its versioned form.

    Args:
        path: Original path (e.g., "/users/123")
        version: API version

    Returns:
        Versioned path (e.g., "/api/v1/users/123")
    """
    # Remove leading /api if present
    if path.startswith(API_PREFIX):
        path = path[len(API_PREFIX):]

    # Remove existing version prefix if present
    if path.startswith(f"/{API_VERSION}"):
        path = path[len(f"/{API_VERSION}"):]

    return f"{API_PREFIX}/{version}{path}"


# Version info for API documentation
VERSION_INFO = {
    "version": API_VERSION,
    "prefix": API_V1_PREFIX,
    "supported_versions": ["v1"],
    "deprecated_versions": [],
    "changelog": {
        "v1": "Initial stable API release",
    }
}


def get_version_info() -> dict:
    """Get API version information for documentation."""
    return VERSION_INFO
