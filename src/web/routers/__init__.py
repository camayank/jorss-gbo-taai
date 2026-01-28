"""
FastAPI Routers - Modular endpoint organization.

This package contains modular routers extracted from the monolithic app.py
for better maintainability, testing, and separation of concerns.

SPEC-005: Router modules:
- scenarios: Tax scenario comparison and "what-if" analysis
- health: System health checks and metrics
- pages: HTML UI page routes
- documents: Document upload and management
- returns: Tax return CRUD and workflow
- calculations: Tax calculations and optimization
- validation: Field and form validation
"""

from .scenarios import router as scenarios_router
from .health import router as health_router
from .pages import router as pages_router
from .documents import router as documents_router
from .returns import router as returns_router
from .calculations import router as calculations_router
from .validation import router as validation_router

__all__ = [
    "scenarios_router",
    "health_router",
    "pages_router",
    "documents_router",
    "returns_router",
    "calculations_router",
    "validation_router",
]
