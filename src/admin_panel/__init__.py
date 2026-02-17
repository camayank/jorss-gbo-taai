"""
Admin Panel Module

This module provides the administrative interface for the Tax Advisory Platform:
- Platform Super Admin: Multi-firm oversight, subscriptions, feature flags
- Firm Admin: Team management, client portfolio, billing, branding

Architecture follows the design in docs/ADMIN_PANEL_ARCHITECTURE.md

Key Components:
- models/: Database models for firms, users, subscriptions, permissions
- api/: REST API routes for admin operations
- auth/: Authentication and RBAC middleware
- services/: Business logic services

Integration:
- Uses existing database infrastructure from src/database
- Integrates with CPA Panel for client/return data access
- Shares security utilities from src/cpa_panel/security
"""

__all__ = ["admin_router"]


def __getattr__(name):
    """
    Lazily expose admin_router to avoid import-time side effects.

    Importing submodules like admin_panel.auth.password should not initialize
    the full admin API router tree (which can create circular imports during
    package bootstrap paths such as database/alembic helpers).
    """
    if name == "admin_router":
        from .api.router import admin_router

        return admin_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
