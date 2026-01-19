"""
Core Platform Models

Unified data models used across all user types:
- Consumers (B2C direct)
- CPA Clients (B2B2C)
- CPA Team Members (B2B)
- Platform Admins (Internal)
"""

from .user import (
    UserType,
    CPARole,
    UnifiedUser,
    UserProfile,
    UserPreferences,
    UserContext,
)

__all__ = [
    "UserType",
    "CPARole",
    "UnifiedUser",
    "UserProfile",
    "UserPreferences",
    "UserContext",
]
