"""
Secure SSN Hashing Module.

Provides HMAC-SHA256 based SSN hashing with proper security measures:
- Uses secret key from environment (SSN_HASH_SECRET)
- Constant-time comparison to prevent timing attacks
- Falls back to legacy SHA256 for migration compatibility

SECURITY: This module addresses the H3 limitation documented in database/models.py
by using HMAC-SHA256 instead of plain SHA256 for SSN hashing.

Usage:
    from security.ssn_hash import secure_hash_ssn, verify_ssn_hash

    # Hash an SSN
    hashed = secure_hash_ssn("123-45-6789")

    # Verify an SSN against a hash
    is_valid = verify_ssn_hash("123-45-6789", hashed)

Migration from legacy hashes:
    # Check against both legacy and secure hashes
    is_valid = verify_ssn_hash_compat("123-45-6789", stored_hash)
"""

import hashlib
import hmac
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

# Secret key for HMAC-SHA256
# CRITICAL: Must be set via SSN_HASH_SECRET environment variable in production
_ssn_hash_secret: Optional[bytes] = None
_is_production = os.environ.get("APP_ENVIRONMENT", "").lower() in ("production", "prod", "staging")


def _get_ssn_hash_secret() -> bytes:
    """
    Get the SSN hash secret key.

    In production, requires SSN_HASH_SECRET environment variable.
    In development, generates a warning and uses a derived key.

    Returns:
        Secret key bytes for HMAC operations
    """
    global _ssn_hash_secret

    if _ssn_hash_secret is not None:
        return _ssn_hash_secret

    secret = os.environ.get("SSN_HASH_SECRET")

    if secret:
        if len(secret) < 32:
            logger.warning(
                "[SECURITY] SSN_HASH_SECRET should be at least 32 characters. "
                "Current length: %d", len(secret)
            )
        _ssn_hash_secret = secret.encode("utf-8")
    elif _is_production:
        raise RuntimeError(
            "CRITICAL: SSN_HASH_SECRET environment variable is required in production. "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    else:
        # Development fallback - derive from a default
        # This ensures consistent hashing during development but logs a warning
        logger.warning(
            "[SECURITY] SSN_HASH_SECRET not set. Using derived development key. "
            "Set SSN_HASH_SECRET for production security."
        )
        # Derive from common dev secrets to maintain consistency
        app_secret = os.environ.get("APP_SECRET_KEY", "dev-only-insecure-key")
        _ssn_hash_secret = hashlib.sha256(
            f"ssn-hash-dev:{app_secret}".encode()
        ).digest()

    return _ssn_hash_secret


def clean_ssn(ssn: str) -> str:
    """
    Normalize SSN by removing formatting.

    Args:
        ssn: SSN with optional formatting (dashes, spaces)

    Returns:
        9-digit SSN string

    Raises:
        ValueError: If SSN doesn't contain exactly 9 digits
    """
    # Extract only digits
    clean = "".join(c for c in ssn if c.isdigit())

    if len(clean) != 9:
        raise ValueError(f"SSN must contain exactly 9 digits, got {len(clean)}")

    return clean


def secure_hash_ssn(ssn: str) -> str:
    """
    Create HMAC-SHA256 hash of SSN for secure lookup.

    This is the recommended function for new code. Uses HMAC with a secret
    key to prevent rainbow table attacks.

    Args:
        ssn: Social Security Number (with or without dashes)

    Returns:
        64-character hexadecimal hash string

    Raises:
        ValueError: If SSN format is invalid
        RuntimeError: If secret key not configured in production

    Security properties:
    - Uses HMAC-SHA256 (keyed hash) to prevent rainbow table attacks
    - Secret key from environment prevents offline brute force
    - Constant-time hash output

    Example:
        hash1 = secure_hash_ssn("123-45-6789")
        hash2 = secure_hash_ssn("123456789")
        assert hash1 == hash2  # Same SSN = same hash
    """
    clean = clean_ssn(ssn)
    secret = _get_ssn_hash_secret()

    # HMAC-SHA256 with secret key
    return hmac.new(secret, clean.encode("utf-8"), hashlib.sha256).hexdigest()


def legacy_hash_ssn(ssn: str) -> str:
    """
    Create legacy SHA256 hash of SSN (for compatibility only).

    WARNING: This function exists only for backward compatibility during
    migration. It should NOT be used for new code.

    Args:
        ssn: Social Security Number

    Returns:
        64-character SHA256 hash

    See:
        secure_hash_ssn() for the recommended approach
    """
    clean = clean_ssn(ssn)
    return hashlib.sha256(clean.encode()).hexdigest()


def verify_ssn_hash(ssn: str, hash_to_verify: str) -> bool:
    """
    Verify an SSN against a secure hash using constant-time comparison.

    Args:
        ssn: SSN to verify
        hash_to_verify: Hash to compare against

    Returns:
        True if SSN matches hash, False otherwise

    Security:
        Uses constant-time comparison to prevent timing attacks
    """
    try:
        computed_hash = secure_hash_ssn(ssn)
        return secrets.compare_digest(computed_hash, hash_to_verify)
    except ValueError:
        return False


def verify_ssn_hash_compat(ssn: str, hash_to_verify: str) -> bool:
    """
    Verify an SSN against both secure and legacy hash formats.

    This function supports migration from legacy SHA256 hashes to
    HMAC-SHA256 hashes. Check against secure hash first, then legacy.

    Args:
        ssn: SSN to verify
        hash_to_verify: Hash to compare against (secure or legacy)

    Returns:
        True if SSN matches either hash format, False otherwise

    Migration note:
        When this returns True for a legacy hash, the calling code should
        rehash the SSN using secure_hash_ssn() and update the stored hash.
    """
    try:
        # Try secure hash first
        if verify_ssn_hash(ssn, hash_to_verify):
            return True

        # Fall back to legacy hash
        legacy = legacy_hash_ssn(ssn)
        if secrets.compare_digest(legacy, hash_to_verify):
            logger.info(
                "[SECURITY] SSN matched legacy hash. Consider rehashing with secure_hash_ssn()"
            )
            return True

        return False
    except ValueError:
        return False


def needs_rehash(stored_hash: str, ssn: Optional[str] = None) -> bool:
    """
    Check if a stored hash needs to be upgraded to secure format.

    Args:
        stored_hash: The currently stored hash
        ssn: Optional SSN to verify (if provided, confirms match)

    Returns:
        True if hash should be rehashed with secure_hash_ssn()
    """
    if ssn is None:
        # Can't verify without SSN - assume needs rehash if it matches legacy pattern
        # Legacy hashes are 64 hex chars and start with predictable patterns
        # (This is a heuristic, not foolproof)
        return len(stored_hash) == 64

    # Check if it matches legacy but not secure
    try:
        secure = secure_hash_ssn(ssn)
        if secrets.compare_digest(secure, stored_hash):
            return False  # Already using secure hash

        legacy = legacy_hash_ssn(ssn)
        if secrets.compare_digest(legacy, stored_hash):
            return True  # Matches legacy, needs upgrade

    except (ValueError, RuntimeError):
        pass

    return False


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

def _validate_configuration() -> None:
    """Validate SSN hash configuration at import time."""
    try:
        _get_ssn_hash_secret()
    except RuntimeError:
        # Will be raised again when actually used
        pass


# Validate on import
_validate_configuration()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "secure_hash_ssn",
    "legacy_hash_ssn",
    "verify_ssn_hash",
    "verify_ssn_hash_compat",
    "needs_rehash",
    "clean_ssn",
]
