"""
QuickBooks Online Integration Package.

This package provides OAuth2 authentication, token management, and API
integration with QuickBooks Online for syncing financial data.
"""

from .config import QB_CONFIG, QuickBooksConfig

__all__ = [
    "QB_CONFIG",
    "QuickBooksConfig",
]
