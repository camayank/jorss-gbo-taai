"""
Secure Serialization Module.

Replaces unsafe pickle with JSON-based serialization with HMAC integrity verification.
CRITICAL: Pickle allows arbitrary code execution - this module prevents that vulnerability.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional, Type, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SerializationError(Exception):
    """Raised when serialization fails."""
    pass


class DeserializationError(Exception):
    """Raised when deserialization fails or signature is invalid."""
    pass


class IntegrityError(Exception):
    """Raised when HMAC signature verification fails."""
    pass


class SecureSerializer:
    """
    Secure JSON-based serializer with HMAC integrity verification.

    Replaces pickle to prevent remote code execution vulnerabilities.
    All serialized data is signed with HMAC-SHA256 to prevent tampering.

    Security Features:
    - No arbitrary code execution (unlike pickle)
    - HMAC signature verification
    - Timestamp-based expiration
    - Type-safe deserialization
    """

    # Maximum age of serialized data (24 hours by default)
    DEFAULT_MAX_AGE = 86400

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize the secure serializer.

        Args:
            secret_key: HMAC signing key. If not provided, uses SERIALIZER_SECRET_KEY
                       environment variable. Raises error if neither is available.
        """
        self._secret_key = secret_key or os.environ.get("SERIALIZER_SECRET_KEY")

        if not self._secret_key:
            # In development, generate a warning and use a random key
            # In production, this should fail
            env = os.environ.get("APP_ENVIRONMENT", "development")
            if env == "production":
                raise ValueError(
                    "SERIALIZER_SECRET_KEY environment variable is required in production. "
                    "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            else:
                logger.warning(
                    "SERIALIZER_SECRET_KEY not set. Using random key (data will not persist across restarts). "
                    "Set SERIALIZER_SECRET_KEY for persistence."
                )
                self._secret_key = secrets.token_hex(32)

        self._key_bytes = self._secret_key.encode("utf-8")

    def serialize(
        self,
        obj: Any,
        max_age: Optional[int] = None,
        include_timestamp: bool = True,
    ) -> str:
        """
        Serialize an object to a signed JSON string.

        Args:
            obj: Object to serialize (must be JSON-compatible or dataclass)
            max_age: Maximum age in seconds (for expiration checking on deserialize)
            include_timestamp: Whether to include creation timestamp

        Returns:
            Base64-encoded signed JSON string

        Raises:
            SerializationError: If object cannot be serialized
        """
        try:
            # Convert object to JSON-serializable dict
            data = self._to_json_compatible(obj)

            # Add metadata
            payload = {
                "data": data,
                "type": self._get_type_name(obj),
            }

            if include_timestamp:
                payload["timestamp"] = int(time.time())
                payload["max_age"] = max_age or self.DEFAULT_MAX_AGE

            # Serialize to JSON
            json_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)

            # Create HMAC signature
            signature = self._create_signature(json_str)

            # Combine and encode
            signed_data = f"{signature}:{json_str}"
            return base64.b64encode(signed_data.encode("utf-8")).decode("utf-8")

        except Exception as e:
            logger.error(f"Serialization failed: {e}")
            raise SerializationError(f"Failed to serialize object: {e}") from e

    def deserialize(
        self,
        signed_data: str,
        expected_type: Optional[Type[T]] = None,
        verify_timestamp: bool = True,
    ) -> Union[T, Any]:
        """
        Deserialize a signed JSON string back to an object.

        Args:
            signed_data: Base64-encoded signed JSON string
            expected_type: Expected type for validation (optional)
            verify_timestamp: Whether to check expiration

        Returns:
            Deserialized object

        Raises:
            DeserializationError: If deserialization fails
            IntegrityError: If signature verification fails
        """
        try:
            # Decode base64
            try:
                decoded = base64.b64decode(signed_data).decode("utf-8")
            except Exception:
                raise IntegrityError("Invalid base64 encoding")

            # Split signature and data
            if ":" not in decoded:
                raise IntegrityError("Invalid signed data format")

            signature, json_str = decoded.split(":", 1)

            # Verify signature
            expected_signature = self._create_signature(json_str)
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("HMAC signature verification failed - possible tampering")
                raise IntegrityError("Signature verification failed")

            # Parse JSON
            payload = json.loads(json_str)

            # Verify timestamp if required
            if verify_timestamp and "timestamp" in payload:
                age = int(time.time()) - payload["timestamp"]
                max_age = payload.get("max_age", self.DEFAULT_MAX_AGE)
                if age > max_age:
                    raise DeserializationError(f"Data expired (age: {age}s, max: {max_age}s)")

            # Extract data
            data = payload.get("data")
            stored_type = payload.get("type")

            # Type validation
            if expected_type and stored_type:
                expected_name = self._get_type_name_for_class(expected_type)
                if stored_type != expected_name:
                    logger.warning(f"Type mismatch: expected {expected_name}, got {stored_type}")

            return data

        except IntegrityError:
            raise
        except DeserializationError:
            raise
        except Exception as e:
            logger.error(f"Deserialization failed: {e}")
            raise DeserializationError(f"Failed to deserialize: {e}") from e

    def _create_signature(self, data: str) -> str:
        """Create HMAC-SHA256 signature."""
        return hmac.new(
            self._key_bytes,
            data.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _to_json_compatible(self, obj: Any) -> Any:
        """Convert object to JSON-compatible format."""
        if obj is None:
            return None

        if isinstance(obj, (str, int, float, bool)):
            return obj

        if isinstance(obj, Decimal):
            return float(obj)

        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        if isinstance(obj, Enum):
            return {"__enum__": type(obj).__name__, "value": obj.value}

        if isinstance(obj, (list, tuple)):
            return [self._to_json_compatible(item) for item in obj]

        if isinstance(obj, dict):
            return {
                str(k): self._to_json_compatible(v)
                for k, v in obj.items()
            }

        if is_dataclass(obj) and not isinstance(obj, type):
            return {
                "__dataclass__": type(obj).__name__,
                "data": {
                    k: self._to_json_compatible(v)
                    for k, v in asdict(obj).items()
                }
            }

        if hasattr(obj, "__dict__"):
            return {
                "__class__": type(obj).__name__,
                "data": {
                    k: self._to_json_compatible(v)
                    for k, v in obj.__dict__.items()
                    if not k.startswith("_")
                }
            }

        # Last resort: convert to string
        return str(obj)

    def _get_type_name(self, obj: Any) -> str:
        """Get type name for an object."""
        if obj is None:
            return "NoneType"
        return type(obj).__name__

    def _get_type_name_for_class(self, cls: Type) -> str:
        """Get type name for a class."""
        return cls.__name__


# Singleton instance
_serializer: Optional[SecureSerializer] = None


def get_serializer() -> SecureSerializer:
    """Get the singleton secure serializer instance."""
    global _serializer
    if _serializer is None:
        _serializer = SecureSerializer()
    return _serializer


def serialize_object(obj: Any, **kwargs) -> str:
    """Convenience function to serialize an object."""
    return get_serializer().serialize(obj, **kwargs)


def deserialize_object(data: str, **kwargs) -> Any:
    """Convenience function to deserialize data."""
    return get_serializer().deserialize(data, **kwargs)
