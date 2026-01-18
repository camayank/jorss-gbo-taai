"""
CPA Panel Data Adapters

Provides a clean interface between the CPA panel and the core tax platform.
This allows the CPA panel to function independently while still accessing
core platform data.
"""

from .tax_return_adapter import TaxReturnAdapter, TaxReturnSummary
from .session_adapter import SessionAdapter
from .optimizer_adapter import OptimizerAdapter, get_optimizer_adapter
from .document_adapter import DocumentAdapter, get_document_adapter
from .ai_advisory_adapter import AIAdvisoryAdapter, get_ai_advisory_adapter

__all__ = [
    "TaxReturnAdapter",
    "TaxReturnSummary",
    "SessionAdapter",
    "OptimizerAdapter",
    "get_optimizer_adapter",
    "DocumentAdapter",
    "get_document_adapter",
    "AIAdvisoryAdapter",
    "get_ai_advisory_adapter",
]
