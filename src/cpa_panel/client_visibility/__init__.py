"""
Client Visibility Surface

Read-only client view of their tax return status.
NOT a full client portal. NOT a messaging system. NOT a CRM.

Purpose: Reduce CPA back-and-forth by giving clients visibility into:
- Current status of their return
- Next steps they need to take
- How to contact their CPA
- Document upload capability

SCOPE BOUNDARIES (ENFORCED - DO NOT EXPAND):
- Status display: YES
- Next steps: YES
- CPA contact info: YES
- Document upload: YES
- Messaging: NO
- Task management: NO
- Comments: NO
- Client account management: NO
"""

from .visibility_service import (
    ClientVisibilityService,
    ClientVisibilityData,
    ReturnStatusDisplay,
    NextStep,
)

__all__ = [
    "ClientVisibilityService",
    "ClientVisibilityData",
    "ReturnStatusDisplay",
    "NextStep",
]
