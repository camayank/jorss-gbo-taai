"""
Password Utilities - Secure password hashing and validation.

Uses bcrypt for password hashing with configurable work factor.
"""

import os
import re
from typing import Tuple, List
import logging

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    import hashlib

logger = logging.getLogger(__name__)

_IS_PRODUCTION = os.environ.get("APP_ENVIRONMENT", "").lower() in ("production", "prod", "staging")

# bcrypt work factor (12 is a good balance of security and performance)
BCRYPT_ROUNDS = 12

# Password policy
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_DIGIT = True
REQUIRE_SPECIAL = True
SPECIAL_CHARACTERS = "!@#$%^&*()_+-=[]{}|;':\",./<>?"


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string

    Raises:
        ValueError: If password is empty or too long
    """
    if not password:
        raise ValueError("Password cannot be empty")

    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password exceeds maximum length of {MAX_PASSWORD_LENGTH}")

    if BCRYPT_AVAILABLE:
        # Use bcrypt for secure hashing
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")
    else:
        if _IS_PRODUCTION:
            raise RuntimeError(
                "CRITICAL: bcrypt is required in production for password hashing. "
                "Install with: pip install bcrypt"
            )
        # Development-only fallback to SHA-256 with salt
        logger.warning("bcrypt not available, using SHA-256 fallback (DEVELOPMENT ONLY)")
        import secrets
        salt = secrets.token_hex(16)
        hash_input = f"{salt}:{password}"
        hashed = hashlib.sha256(hash_input.encode()).hexdigest()
        return f"sha256:{salt}:{hashed}"


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: Plain text password to verify
        hashed: Stored password hash

    Returns:
        True if password matches
    """
    if not password or not hashed:
        return False

    try:
        if BCRYPT_AVAILABLE and not hashed.startswith("sha256:"):
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        elif hashed.startswith("sha256:"):
            # Fallback verification
            parts = hashed.split(":")
            if len(parts) != 3:
                return False
            _, salt, stored_hash = parts
            hash_input = f"{salt}:{password}"
            computed = hashlib.sha256(hash_input.encode()).hexdigest()
            return computed == stored_hash
        else:
            return False
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password meets security requirements.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    if not password:
        return False, ["Password is required"]

    # Length checks
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    if len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters")

    # Character type checks
    if REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    if REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

    if REQUIRE_DIGIT and not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")

    if REQUIRE_SPECIAL and not any(c in SPECIAL_CHARACTERS for c in password):
        errors.append(f"Password must contain at least one special character ({SPECIAL_CHARACTERS[:10]}...)")

    # Common patterns to reject
    common_patterns = [
        r"^(.)\1+$",  # All same character
        r"^(012|123|234|345|456|567|678|789|890)+$",  # Sequential numbers
        r"^(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)+$",  # Sequential letters
    ]

    for pattern in common_patterns:
        if re.match(pattern, password.lower()):
            errors.append("Password contains a common pattern")
            break

    # Check against common passwords (simplified list)
    common_passwords = {
        "password", "password123", "123456789", "qwerty123",
        "letmein123", "welcome123", "admin123", "changeme",
    }

    if password.lower() in common_passwords:
        errors.append("Password is too common")

    return len(errors) == 0, errors


def generate_temporary_password(length: int = 16) -> str:
    """
    Generate a secure temporary password.

    Args:
        length: Password length (minimum 12)

    Returns:
        Random password meeting all requirements
    """
    import secrets
    import string

    length = max(length, 12)

    # Ensure at least one of each required type
    password_chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(SPECIAL_CHARACTERS),
    ]

    # Fill remaining length with random characters
    all_chars = string.ascii_letters + string.digits + SPECIAL_CHARACTERS
    password_chars.extend(
        secrets.choice(all_chars) for _ in range(length - len(password_chars))
    )

    # Shuffle to avoid predictable positions using cryptographically secure sort
    password_chars.sort(key=lambda _: secrets.randbelow(len(password_chars) * 10))

    return "".join(password_chars)


def is_password_expired(
    password_changed_at,
    expiry_days: int = 90,
) -> bool:
    """
    Check if password has expired.

    Args:
        password_changed_at: DateTime of last password change
        expiry_days: Number of days until expiry

    Returns:
        True if password has expired
    """
    if password_changed_at is None:
        return True

    from datetime import datetime, timedelta
    expiry_date = password_changed_at + timedelta(days=expiry_days)
    return datetime.utcnow() > expiry_date
