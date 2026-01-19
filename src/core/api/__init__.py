"""
Core Platform API

Unified API endpoints used by all user types:
- Authentication (/api/core/auth)
- Users & Profiles (/api/core/users)
- Tax Returns (/api/core/tax-returns)
- Documents (/api/core/documents)
- Scenarios (/api/core/scenarios)
- Recommendations (/api/core/recommendations)
- Billing (/api/core/billing)
- Messaging (/api/core/messages)

All endpoints implement role-based access control,
allowing the same API to serve:
- Direct B2C consumers
- CPA clients
- CPA team members
- Platform administrators
"""

from .router import core_router, API_TAGS

__all__ = ["core_router", "API_TAGS"]
