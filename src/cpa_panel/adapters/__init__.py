"""
CPA Panel Data Adapters

Provides a clean interface between the CPA panel and the core tax platform.
This allows the CPA panel to function independently while still accessing
core platform data.
"""

from .tax_return_adapter import TaxReturnAdapter, TaxReturnSummary
from .session_adapter import SessionAdapter

__all__ = [
    "TaxReturnAdapter",
    "TaxReturnSummary",
    "SessionAdapter",
]
