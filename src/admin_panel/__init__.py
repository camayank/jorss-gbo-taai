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

from .api.router import admin_router

__all__ = ["admin_router"]
