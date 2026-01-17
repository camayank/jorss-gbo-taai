"""Configuration module for the tax platform."""

from .database import DatabaseSettings, get_database_settings
from .settings import Settings, get_settings

__all__ = [
    "DatabaseSettings",
    "get_database_settings",
    "Settings",
    "get_settings",
]
