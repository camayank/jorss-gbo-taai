"""
CPA Engagement Letter Module

Generates professional engagement letters for CPA-client relationships.
Supports e-signature integration via webhook for DocuSign/HelloSign.

NOT a contract management system. NOT a CRM.
Purpose: Legal protection + enterprise credibility signal.
"""

from .letter_generator import (
    EngagementLetterGenerator,
    EngagementLetterType,
    EngagementLetter,
)
from .esign_hooks import ESignWebhookHandler, ESignProvider

__all__ = [
    "EngagementLetterGenerator",
    "EngagementLetterType",
    "EngagementLetter",
    "ESignWebhookHandler",
    "ESignProvider",
]
