"""
PII Field Encryption Module

Provides field-level encryption for Personally Identifiable Information (PII)
such as email, phone, SSN stored in the database.

SECURITY REQUIREMENTS:
- ENCRYPTION_MASTER_KEY must be set in production (min 32 chars hex)
- Key rotation is supported via versioned encryption
- Uses AES-256-GCM for authenticated encryption

Usage:
    from database.encrypted_fields import encrypt_pii, decrypt_pii

    # Encrypt before storing
    encrypted_email = encrypt_pii(user_email, field_type="email")

    # Decrypt when reading
    decrypted_email = decrypt_pii(encrypted_email, field_type="email")
"""

import os
import base64
import hashlib
import logging
from typing import Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# Environment detection
_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "development")
_IS_PRODUCTION = _ENVIRONMENT in ("production", "prod", "staging")


# =============================================================================
# KEY MANAGEMENT
# =============================================================================

class EncryptionKeyError(Exception):
    """Raised when encryption key is missing or invalid."""
    pass


def _get_encryption_key() -> bytes:
    """
    Get the encryption master key from environment.

    Returns:
        32-byte encryption key

    Raises:
        EncryptionKeyError: If key is missing in production
    """
    key_hex = os.environ.get("ENCRYPTION_MASTER_KEY")

    if not key_hex:
        if _IS_PRODUCTION:
            raise EncryptionKeyError(
                "CRITICAL: ENCRYPTION_MASTER_KEY is required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Development fallback - deterministic for testing
        import warnings
        warnings.warn(
            "ENCRYPTION_MASTER_KEY not set - using insecure development key. "
            "PII will NOT be securely encrypted.",
            UserWarning
        )
        # Use a deterministic dev key so data can be read across restarts
        key_hex = hashlib.sha256(b"DEV-ONLY-INSECURE-KEY").hexdigest()

    # Convert hex string to bytes
    try:
        key_bytes = bytes.fromhex(key_hex)
    except ValueError:
        raise EncryptionKeyError("ENCRYPTION_MASTER_KEY must be a valid hex string")

    if len(key_bytes) < 32:
        raise EncryptionKeyError("ENCRYPTION_MASTER_KEY must be at least 32 bytes (64 hex chars)")

    # Use first 32 bytes for AES-256
    return key_bytes[:32]


@lru_cache(maxsize=1)
def get_encryption_key() -> bytes:
    """Get cached encryption key."""
    return _get_encryption_key()


# =============================================================================
# ENCRYPTION IMPLEMENTATION
# =============================================================================

# Current encryption version (for key rotation support)
ENCRYPTION_VERSION = 1

# Field-specific context for domain separation
FIELD_CONTEXTS = {
    "email": b"pii:email:v1",
    "phone": b"pii:phone:v1",
    "ssn": b"pii:ssn:v1",
    "name": b"pii:name:v1",
    "address": b"pii:address:v1",
    "generic": b"pii:generic:v1",
}


def _derive_field_key(master_key: bytes, field_type: str) -> bytes:
    """
    Derive a field-specific key from the master key.

    This provides domain separation - different keys for different field types.
    """
    context = FIELD_CONTEXTS.get(field_type, FIELD_CONTEXTS["generic"])
    return hashlib.sha256(master_key + context).digest()


def encrypt_pii(
    plaintext: str,
    field_type: str = "generic",
    associated_data: Optional[bytes] = None
) -> str:
    """
    Encrypt a PII field value.

    Uses AES-256-GCM for authenticated encryption with:
    - Random 12-byte nonce for each encryption
    - Field-type specific key derivation
    - Optional associated data for context binding

    Args:
        plaintext: The PII value to encrypt
        field_type: Type of field (email, phone, ssn, name, address, generic)
        associated_data: Optional context data to bind to ciphertext

    Returns:
        Base64-encoded encrypted string with format:
        v{version}:{nonce}:{ciphertext}:{tag}

    Raises:
        EncryptionKeyError: If encryption key is not configured
    """
    if not plaintext:
        return ""

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        logger.warning("cryptography not installed - using fallback encoding (NOT SECURE)")
        return _fallback_encode(plaintext, field_type)

    # Get field-specific key
    master_key = get_encryption_key()
    field_key = _derive_field_key(master_key, field_type)

    # Generate random nonce
    nonce = os.urandom(12)

    # Encrypt with AES-GCM
    aesgcm = AESGCM(field_key)
    ciphertext = aesgcm.encrypt(
        nonce,
        plaintext.encode('utf-8'),
        associated_data
    )

    # Separate tag from ciphertext (last 16 bytes)
    encrypted_data = ciphertext[:-16]
    tag = ciphertext[-16:]

    # Encode as versioned string
    result = "v{}:{}:{}:{}".format(
        ENCRYPTION_VERSION,
        base64.urlsafe_b64encode(nonce).decode('ascii'),
        base64.urlsafe_b64encode(encrypted_data).decode('ascii'),
        base64.urlsafe_b64encode(tag).decode('ascii')
    )

    return result


def decrypt_pii(
    ciphertext: str,
    field_type: str = "generic",
    associated_data: Optional[bytes] = None
) -> str:
    """
    Decrypt a PII field value.

    Args:
        ciphertext: The encrypted value from encrypt_pii()
        field_type: Type of field (must match encryption)
        associated_data: Optional context data (must match encryption)

    Returns:
        Decrypted plaintext string

    Raises:
        ValueError: If ciphertext format is invalid
        EncryptionKeyError: If encryption key is not configured
    """
    if not ciphertext:
        return ""

    # Check for fallback encoding
    if ciphertext.startswith("fallback:"):
        return _fallback_decode(ciphertext, field_type)

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        logger.error("cryptography not installed - cannot decrypt")
        raise ImportError("cryptography package required for decryption")

    # Parse versioned format
    try:
        parts = ciphertext.split(":")
        if len(parts) != 4:
            raise ValueError("Invalid ciphertext format")

        version = int(parts[0][1:])  # Remove 'v' prefix
        nonce = base64.urlsafe_b64decode(parts[1])
        encrypted_data = base64.urlsafe_b64decode(parts[2])
        tag = base64.urlsafe_b64decode(parts[3])

    except Exception as e:
        raise ValueError(f"Failed to parse ciphertext: {e}")

    # Get field-specific key
    master_key = get_encryption_key()
    field_key = _derive_field_key(master_key, field_type)

    # Reconstruct ciphertext with tag
    full_ciphertext = encrypted_data + tag

    # Decrypt
    aesgcm = AESGCM(field_key)
    try:
        plaintext = aesgcm.decrypt(nonce, full_ciphertext, associated_data)
        return plaintext.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise ValueError("Decryption failed - invalid key or corrupted data")


# =============================================================================
# FALLBACK ENCODING (for development without cryptography)
# =============================================================================

def _fallback_encode(plaintext: str, field_type: str) -> str:
    """
    Fallback encoding when cryptography is not available.

    WARNING: This is NOT secure encryption - only for development!
    """
    encoded = base64.urlsafe_b64encode(plaintext.encode('utf-8')).decode('ascii')
    return f"fallback:{field_type}:{encoded}"


def _fallback_decode(ciphertext: str, field_type: str) -> str:
    """Decode fallback-encoded data."""
    parts = ciphertext.split(":", 2)
    if len(parts) != 3 or parts[0] != "fallback":
        raise ValueError("Invalid fallback encoding")
    return base64.urlsafe_b64decode(parts[2]).decode('utf-8')


# =============================================================================
# FIELD HELPERS
# =============================================================================

def encrypt_email(email: str, tenant_id: Optional[str] = None) -> str:
    """Encrypt an email address with optional tenant binding."""
    associated_data = tenant_id.encode() if tenant_id else None
    return encrypt_pii(email, field_type="email", associated_data=associated_data)


def decrypt_email(encrypted: str, tenant_id: Optional[str] = None) -> str:
    """Decrypt an email address."""
    associated_data = tenant_id.encode() if tenant_id else None
    return decrypt_pii(encrypted, field_type="email", associated_data=associated_data)


def encrypt_phone(phone: str, tenant_id: Optional[str] = None) -> str:
    """Encrypt a phone number with optional tenant binding."""
    associated_data = tenant_id.encode() if tenant_id else None
    return encrypt_pii(phone, field_type="phone", associated_data=associated_data)


def decrypt_phone(encrypted: str, tenant_id: Optional[str] = None) -> str:
    """Decrypt a phone number."""
    associated_data = tenant_id.encode() if tenant_id else None
    return decrypt_pii(encrypted, field_type="phone", associated_data=associated_data)


def encrypt_ssn(ssn: str, tenant_id: Optional[str] = None) -> str:
    """
    Encrypt a Social Security Number.

    SECURITY: SSN is highly sensitive - always use tenant binding if available.
    """
    associated_data = tenant_id.encode() if tenant_id else None
    return encrypt_pii(ssn, field_type="ssn", associated_data=associated_data)


def decrypt_ssn(encrypted: str, tenant_id: Optional[str] = None) -> str:
    """Decrypt a Social Security Number."""
    associated_data = tenant_id.encode() if tenant_id else None
    return decrypt_pii(encrypted, field_type="ssn", associated_data=associated_data)


def mask_email(email: str) -> str:
    """
    Mask an email for display (e.g., j***n@example.com).

    Use this for UI display instead of decrypting when full email isn't needed.
    """
    if not email or "@" not in email:
        return "***@***.***"

    local, domain = email.rsplit("@", 1)

    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]

    domain_parts = domain.split(".")
    if len(domain_parts) >= 2:
        masked_domain = domain_parts[0][:2] + "***." + domain_parts[-1]
    else:
        masked_domain = "***." + domain_parts[-1] if domain_parts else "***.***"

    return f"{masked_local}@{masked_domain}"


def mask_phone(phone: str) -> str:
    """Mask a phone number for display (e.g., ***-***-1234)."""
    if not phone:
        return "***-***-****"

    # Extract digits
    digits = ''.join(c for c in phone if c.isdigit())

    if len(digits) >= 4:
        return "***-***-" + digits[-4:]
    return "***-***-****"


def mask_ssn(ssn: str) -> str:
    """Mask an SSN for display (e.g., ***-**-1234)."""
    if not ssn:
        return "***-**-****"

    # Extract digits
    digits = ''.join(c for c in ssn if c.isdigit())

    if len(digits) >= 4:
        return "***-**-" + digits[-4:]
    return "***-**-****"


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

def encrypt_lead_pii(lead_data: dict, tenant_id: str) -> dict:
    """
    Encrypt all PII fields in a lead record.

    Args:
        lead_data: Dictionary with lead data
        tenant_id: Tenant ID for key binding

    Returns:
        Copy of lead_data with PII fields encrypted
    """
    encrypted = lead_data.copy()

    pii_fields = {
        "email": encrypt_email,
        "phone": encrypt_phone,
        "ssn": encrypt_ssn,
    }

    for field, encrypt_fn in pii_fields.items():
        if field in encrypted and encrypted[field]:
            encrypted[field] = encrypt_fn(encrypted[field], tenant_id)
            encrypted[f"{field}_masked"] = globals()[f"mask_{field}"](lead_data[field])

    return encrypted


def decrypt_lead_pii(encrypted_data: dict, tenant_id: str, audit_context: Optional[dict] = None) -> dict:
    """
    Decrypt all PII fields in a lead record.

    Args:
        encrypted_data: Dictionary with encrypted lead data
        tenant_id: Tenant ID for key binding
        audit_context: Optional dict with user_id, reason for audit logging

    Returns:
        Copy of data with PII fields decrypted
    """
    decrypted = encrypted_data.copy()

    pii_fields = {
        "email": decrypt_email,
        "phone": decrypt_phone,
        "ssn": decrypt_ssn,
    }

    decrypted_fields = []
    for field, decrypt_fn in pii_fields.items():
        if field in decrypted and decrypted[field]:
            try:
                decrypted[field] = decrypt_fn(decrypted[field], tenant_id)
                decrypted_fields.append(field)
            except Exception as e:
                logger.error(f"Failed to decrypt {field}: {e}")
                decrypted[field] = None

    # Audit log PII access
    if decrypted_fields:
        _log_pii_access(
            action="decrypt",
            fields=decrypted_fields,
            tenant_id=tenant_id,
            context=audit_context
        )

    return decrypted


# =============================================================================
# PII ACCESS AUDIT LOGGING
# =============================================================================

_pii_access_log: list = []  # In-memory buffer for batch writes


def _log_pii_access(
    action: str,
    fields: list,
    tenant_id: str,
    context: Optional[dict] = None
):
    """
    Log PII field access for security audit trail.

    This creates an immutable record of who accessed what PII and when.
    """
    from datetime import datetime

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "fields": fields,
        "tenant_id": tenant_id,
        "user_id": context.get("user_id") if context else None,
        "reason": context.get("reason") if context else None,
        "ip": context.get("ip") if context else None,
    }

    # Log to security logger
    if "ssn" in fields:
        # SSN access is HIGH severity
        logger.warning(f"[PII AUDIT] SSN accessed | {log_entry}")
    else:
        logger.info(f"[PII AUDIT] PII accessed | {log_entry}")

    # Buffer for potential async write to audit table
    _pii_access_log.append(log_entry)
    if len(_pii_access_log) > 100:
        _pii_access_log.pop(0)  # Maintain buffer size


# =============================================================================
# PII VALIDATION & ENFORCEMENT
# =============================================================================

# Patterns that indicate unencrypted PII
_EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
_PHONE_PATTERN = r'^\+?[\d\s\-\(\)]{7,}$'
_SSN_PATTERN = r'^\d{3}-?\d{2}-?\d{4}$'


def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be encrypted.

    Returns True if value looks like our encrypted format (v1:...:...:...)
    """
    if not value or not isinstance(value, str):
        return True  # Empty/None is acceptable

    # Check for our encryption format
    if value.startswith("v1:") or value.startswith("fallback:"):
        return True

    return False


def validate_pii_encryption(data: dict, raise_exception: bool = True) -> Tuple[bool, list]:
    """
    Validate that PII fields in a dictionary are encrypted.

    This function should be called BEFORE storing data to ensure
    PII is not written in plaintext.

    Args:
        data: Dictionary to validate
        raise_exception: If True, raise exception on unencrypted PII

    Returns:
        Tuple of (is_valid, list of unencrypted_fields)

    Raises:
        ValueError: If raise_exception=True and unencrypted PII found
    """
    import re

    unencrypted_fields = []

    pii_patterns = {
        "email": _EMAIL_PATTERN,
        "phone": _PHONE_PATTERN,
        "ssn": _SSN_PATTERN,
        "social_security_number": _SSN_PATTERN,
    }

    for field, pattern in pii_patterns.items():
        value = data.get(field)
        if value and isinstance(value, str):
            # Check if it looks like plaintext PII
            if re.match(pattern, value) and not is_encrypted(value):
                unencrypted_fields.append(field)
                logger.error(
                    f"[SECURITY] Unencrypted PII detected | field={field} | "
                    f"pattern_matched=True | encrypted=False"
                )

    if unencrypted_fields:
        if raise_exception:
            raise ValueError(
                f"SECURITY VIOLATION: Unencrypted PII detected in fields: {unencrypted_fields}. "
                f"Use encrypt_lead_pii() before storing data."
            )
        return False, unencrypted_fields

    return True, []


def enforce_pii_encryption(func):
    """
    Decorator to enforce PII encryption on functions that store data.

    Usage:
        @enforce_pii_encryption
        def save_lead(lead_data: dict):
            # lead_data will be validated before saving
            ...
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Check positional args for dict-like data
        for arg in args:
            if isinstance(arg, dict):
                validate_pii_encryption(arg, raise_exception=True)

        # Check keyword args
        for key, value in kwargs.items():
            if isinstance(value, dict):
                validate_pii_encryption(value, raise_exception=True)

        return func(*args, **kwargs)

    return wrapper
