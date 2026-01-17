"""
Security module for the tax platform.

Provides secure serialization, encryption, authentication, and data protection.
"""

from .secure_serializer import SecureSerializer, get_serializer
from .encryption import DataEncryptor, get_encryptor
from .authentication import (
    AuthenticationManager,
    get_auth_manager,
    require_auth,
    JWTClaims,
)
from .data_sanitizer import DataSanitizer, sanitize_for_logging, sanitize_for_api

__all__ = [
    "SecureSerializer",
    "get_serializer",
    "DataEncryptor",
    "get_encryptor",
    "AuthenticationManager",
    "get_auth_manager",
    "require_auth",
    "JWTClaims",
    "DataSanitizer",
    "sanitize_for_logging",
    "sanitize_for_api",
]
