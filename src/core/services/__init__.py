"""
Core Platform Services

Shared services used by all user types:
- Authentication
- User management
- Tax returns
- Documents
- Scenarios
- Recommendations
- Billing
- Messaging
"""

from .auth_service import CoreAuthService, get_auth_service
from .user_service import CoreUserService, get_user_service

__all__ = [
    "CoreAuthService",
    "get_auth_service",
    "CoreUserService",
    "get_user_service",
]
