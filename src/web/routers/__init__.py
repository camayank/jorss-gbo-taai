"""
FastAPI Routers - Modular endpoint organization.

This package contains modular routers extracted from the monolithic app.py
for better maintainability, testing, and separation of concerns.
"""

from .scenarios import router as scenarios_router

__all__ = [
    "scenarios_router",
]
