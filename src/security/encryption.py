"""
Data Encryption Module.

Provides AES-256-GCM encryption for sensitive data (SSN, financial info).
CRITICAL: PII must be encrypted at rest and in transit.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Try to import cryptography library
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography library not installed. Install with: pip install cryptography"
    )


class EncryptionError(Exception):
    """Raised when encryption fails."""
    pass


class DecryptionError(Exception):
    """Raised when decryption fails."""
    pass


class DataEncryptor:
    """
    AES-256-GCM encryptor for sensitive data.

    Provides authenticated encryption with:
    - AES-256 encryption (256-bit key)
    - GCM mode (provides authentication)
    - Unique nonce per encryption
    - PBKDF2 key derivation from password

    Security Features:
    - Authenticated encryption (tampering detected)
    - Unique random nonce for each encryption
    - Key derived from master key using PBKDF2
    - No plaintext exposure in memory longer than necessary
    """

    # Nonce size for GCM (96 bits recommended)
    NONCE_SIZE = 12
    # Salt size for key derivation
    SALT_SIZE = 16
    # Key size (256 bits for AES-256)
    KEY_SIZE = 32
    # PBKDF2 iterations
    ITERATIONS = 100000

    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize the encryptor.

        Args:
            master_key: Master encryption key. If not provided, uses
                       ENCRYPTION_MASTER_KEY environment variable.
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "cryptography library required. Install with: pip install cryptography"
            )

        self._master_key = master_key or os.environ.get("ENCRYPTION_MASTER_KEY")

        if not self._master_key:
            env = os.environ.get("APP_ENVIRONMENT", "development")
            if env == "production":
                raise ValueError(
                    "ENCRYPTION_MASTER_KEY environment variable is required in production. "
                    "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            else:
                logger.warning(
                    "ENCRYPTION_MASTER_KEY not set. Using random key (encrypted data will not persist). "
                    "Set ENCRYPTION_MASTER_KEY for persistence."
                )
                self._master_key = secrets.token_hex(32)

    def encrypt(self, plaintext: Union[str, bytes], associated_data: Optional[bytes] = None) -> str:
        """
        Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt (string or bytes)
            associated_data: Optional authenticated but unencrypted data

        Returns:
            Base64-encoded encrypted data (format: salt:nonce:ciphertext)

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Convert string to bytes
            if isinstance(plaintext, str):
                plaintext = plaintext.encode("utf-8")

            # Generate random salt and nonce
            salt = secrets.token_bytes(self.SALT_SIZE)
            nonce = secrets.token_bytes(self.NONCE_SIZE)

            # Derive key from master key
            key = self._derive_key(salt)

            # Encrypt with AES-GCM
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

            # Combine salt, nonce, and ciphertext
            combined = salt + nonce + ciphertext

            # Return base64 encoded
            return base64.b64encode(combined).decode("utf-8")

        except Exception as e:
            logger.error(f"Encryption failed: {type(e).__name__}")
            raise EncryptionError("Failed to encrypt data") from e

    def decrypt(self, encrypted_data: str, associated_data: Optional[bytes] = None) -> str:
        """
        Decrypt data encrypted with encrypt().

        Args:
            encrypted_data: Base64-encoded encrypted data
            associated_data: Must match data used during encryption

        Returns:
            Decrypted plaintext string

        Raises:
            DecryptionError: If decryption fails or data is tampered
        """
        try:
            # Decode base64
            combined = base64.b64decode(encrypted_data)

            # Extract salt, nonce, and ciphertext
            salt = combined[:self.SALT_SIZE]
            nonce = combined[self.SALT_SIZE:self.SALT_SIZE + self.NONCE_SIZE]
            ciphertext = combined[self.SALT_SIZE + self.NONCE_SIZE:]

            # Derive key from master key
            key = self._derive_key(salt)

            # Decrypt with AES-GCM
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)

            return plaintext.decode("utf-8")

        except Exception as e:
            logger.error(f"Decryption failed: {type(e).__name__}")
            raise DecryptionError("Failed to decrypt data - possible tampering") from e

    def encrypt_ssn(self, ssn: str) -> str:
        """
        Encrypt an SSN with additional validation.

        Args:
            ssn: Social Security Number (with or without dashes)

        Returns:
            Encrypted SSN

        Raises:
            ValueError: If SSN format is invalid
            EncryptionError: If encryption fails
        """
        # Clean SSN
        clean_ssn = "".join(c for c in ssn if c.isdigit())

        if len(clean_ssn) != 9:
            raise ValueError("SSN must be 9 digits")

        # Encrypt with SSN-specific associated data
        return self.encrypt(clean_ssn, associated_data=b"ssn")

    def decrypt_ssn(self, encrypted_ssn: str, format_output: bool = True) -> str:
        """
        Decrypt an SSN.

        Args:
            encrypted_ssn: Encrypted SSN from encrypt_ssn()
            format_output: If True, returns XXX-XX-XXXX format

        Returns:
            Decrypted SSN

        Raises:
            DecryptionError: If decryption fails
        """
        ssn = self.decrypt(encrypted_ssn, associated_data=b"ssn")

        if format_output:
            return f"{ssn[:3]}-{ssn[3:5]}-{ssn[5:]}"
        return ssn

    def hash_ssn(self, ssn: str, salt: Optional[str] = None) -> str:
        """
        Create a salted hash of SSN for lookups.

        This is a one-way hash - cannot be reversed to get the SSN.
        Use encrypt_ssn() if you need to recover the SSN.

        Args:
            ssn: Social Security Number
            salt: Optional salt (uses derived salt if not provided)

        Returns:
            Salted SHA-256 hash of SSN
        """
        clean_ssn = "".join(c for c in ssn if c.isdigit())

        if len(clean_ssn) != 9:
            raise ValueError("SSN must be 9 digits")

        # Use provided salt or derive from master key
        if salt:
            salt_bytes = salt.encode("utf-8")
        else:
            salt_bytes = hashlib.sha256(self._master_key.encode()).digest()[:16]

        # Create salted hash
        combined = salt_bytes + clean_ssn.encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive encryption key from master key using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.ITERATIONS,
        )
        return kdf.derive(self._master_key.encode("utf-8"))


# Singleton instance
_encryptor: Optional[DataEncryptor] = None


def get_encryptor() -> DataEncryptor:
    """Get the singleton encryptor instance."""
    global _encryptor
    if _encryptor is None:
        _encryptor = DataEncryptor()
    return _encryptor


def encrypt_sensitive_field(value: str) -> str:
    """Convenience function to encrypt a sensitive field."""
    return get_encryptor().encrypt(value)


def decrypt_sensitive_field(encrypted_value: str) -> str:
    """Convenience function to decrypt a sensitive field."""
    return get_encryptor().decrypt(encrypted_value)
