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

# PDF generation (optional - requires reportlab)
try:
    from .pdf_generator import EngagementLetterPDFGenerator, get_pdf_generator
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    EngagementLetterPDFGenerator = None
    get_pdf_generator = None

__all__ = [
    "EngagementLetterGenerator",
    "EngagementLetterType",
    "EngagementLetter",
    "ESignWebhookHandler",
    "ESignProvider",
    "EngagementLetterPDFGenerator",
    "get_pdf_generator",
    "PDF_AVAILABLE",
]
