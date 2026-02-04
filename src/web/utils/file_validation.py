"""
File Upload Security Validation

Provides magic byte validation to prevent file type spoofing attacks.
Extension-only validation is insecure - attackers can rename malicious
files (e.g., .exe → .pdf) to bypass filters.

This module validates actual file content signatures (magic bytes).
"""

import os
import re
import logging
from typing import Optional, Tuple, Set

logger = logging.getLogger(__name__)


class FileValidationError(Exception):
    """Raised when file validation fails."""
    pass


# Magic byte signatures for allowed file types
# Format: (signature_bytes, offset, mime_type, extensions)
MAGIC_SIGNATURES = [
    # PDF: %PDF-
    (b'%PDF-', 0, 'application/pdf', {'pdf'}),

    # PNG: 89 50 4E 47 0D 0A 1A 0A
    (b'\x89PNG\r\n\x1a\n', 0, 'image/png', {'png'}),

    # JPEG: FF D8 FF (various subtypes follow)
    (b'\xff\xd8\xff', 0, 'image/jpeg', {'jpg', 'jpeg'}),

    # TIFF Little Endian: 49 49 2A 00
    (b'II*\x00', 0, 'image/tiff', {'tif', 'tiff'}),

    # TIFF Big Endian: 4D 4D 00 2A
    (b'MM\x00*', 0, 'image/tiff', {'tif', 'tiff'}),

    # GIF87a
    (b'GIF87a', 0, 'image/gif', {'gif'}),

    # GIF89a
    (b'GIF89a', 0, 'image/gif', {'gif'}),
]

# Allowed MIME types for document upload
ALLOWED_MIME_TYPES: Set[str] = {
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/tiff',
    'image/gif',
}

# Allowed extensions (lowercase)
ALLOWED_EXTENSIONS: Set[str] = {
    'pdf', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'gif'
}

# Dangerous patterns in filenames
DANGEROUS_FILENAME_PATTERNS = [
    r'\.\.',           # Path traversal
    r'[<>:"|?*]',      # Windows reserved characters
    r'[\x00-\x1f]',    # Control characters
    r'^\.+$',          # Only dots
    r'^\s+|\s+$',      # Leading/trailing whitespace
]

# Maximum filename length
MAX_FILENAME_LENGTH = 255


def validate_magic_bytes(content: bytes) -> Tuple[Optional[str], Optional[Set[str]]]:
    """
    Validate file content against known magic byte signatures.

    Args:
        content: File content bytes (at least first 16 bytes needed)

    Returns:
        Tuple of (mime_type, allowed_extensions) if valid signature found,
        (None, None) if no matching signature.

    Example:
        >>> mime, exts = validate_magic_bytes(pdf_content)
        >>> if mime:
        ...     print(f"Valid {mime} file")
    """
    if not content or len(content) < 4:
        return None, None

    for signature, offset, mime_type, extensions in MAGIC_SIGNATURES:
        sig_end = offset + len(signature)
        if len(content) >= sig_end:
            if content[offset:sig_end] == signature:
                return mime_type, extensions

    return None, None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and injection attacks.

    Args:
        filename: Original filename from upload

    Returns:
        Sanitized filename safe for filesystem operations

    Raises:
        FileValidationError: If filename is malformed beyond repair

    Example:
        >>> sanitize_filename("../../../etc/passwd")
        'passwd'
        >>> sanitize_filename("my document.pdf")
        'my_document.pdf'
    """
    if not filename:
        raise FileValidationError("Filename cannot be empty")

    # Remove path components (handle both Unix and Windows paths)
    filename = os.path.basename(filename.replace('\\', '/'))

    if not filename:
        raise FileValidationError("Filename invalid after path sanitization")

    # Check for dangerous patterns
    for pattern in DANGEROUS_FILENAME_PATTERNS:
        if re.search(pattern, filename):
            # Remove or replace dangerous characters
            filename = re.sub(pattern, '_', filename)

    # Replace spaces with underscores for consistency
    filename = filename.replace(' ', '_')

    # Remove consecutive underscores
    while '__' in filename:
        filename = filename.replace('__', '_')

    # Ensure filename doesn't start with a dot (hidden file)
    filename = filename.lstrip('.')

    if not filename:
        raise FileValidationError("Filename invalid after sanitization")

    # Truncate if too long (preserve extension)
    if len(filename) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(filename)
        max_name_len = MAX_FILENAME_LENGTH - len(ext)
        filename = name[:max_name_len] + ext

    return filename


def get_extension(filename: str) -> str:
    """
    Get lowercase extension from filename.

    Args:
        filename: Filename to extract extension from

    Returns:
        Lowercase extension without dot, or empty string if none
    """
    if '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[-1].lower()


def validate_upload(
    content: bytes,
    filename: str,
    max_size_bytes: int = 20 * 1024 * 1024,
    allowed_types: Optional[Set[str]] = None,
) -> Tuple[str, str, str]:
    """
    Comprehensive file upload validation.

    Validates:
    1. File size
    2. Magic bytes match allowed types
    3. Extension matches magic byte signature
    4. Filename is sanitized

    Args:
        content: File content bytes
        filename: Original filename
        max_size_bytes: Maximum allowed file size (default 20MB)
        allowed_types: Optional set of allowed MIME types (defaults to ALLOWED_MIME_TYPES)

    Returns:
        Tuple of (sanitized_filename, detected_mime_type, extension)

    Raises:
        FileValidationError: If validation fails

    Example:
        >>> safe_name, mime, ext = validate_upload(content, "document.pdf")
        >>> print(f"Validated {mime} file: {safe_name}")
    """
    if allowed_types is None:
        allowed_types = ALLOWED_MIME_TYPES

    # 1. Check file size
    if len(content) > max_size_bytes:
        size_mb = len(content) / (1024 * 1024)
        max_mb = max_size_bytes / (1024 * 1024)
        raise FileValidationError(
            f"File size ({size_mb:.1f}MB) exceeds maximum ({max_mb:.1f}MB)"
        )

    # 2. Check file is not empty
    if len(content) == 0:
        raise FileValidationError("File is empty")

    # 3. Validate magic bytes
    detected_mime, valid_extensions = validate_magic_bytes(content)

    if detected_mime is None:
        raise FileValidationError(
            "File type could not be determined from content. "
            "Supported types: PDF, PNG, JPEG, TIFF, GIF"
        )

    if detected_mime not in allowed_types:
        raise FileValidationError(
            f"File type '{detected_mime}' is not allowed. "
            f"Supported types: {', '.join(sorted(allowed_types))}"
        )

    # 4. Sanitize filename
    safe_filename = sanitize_filename(filename)

    # 5. Validate extension matches content
    extension = get_extension(safe_filename)

    if extension and valid_extensions and extension not in valid_extensions:
        # Extension doesn't match content - this could be an attack
        # Log as warning and correct the extension
        logger.warning(
            f"File extension mismatch: '{extension}' for content type '{detected_mime}'. "
            f"Expected one of: {valid_extensions}. "
            "This may indicate a file spoofing attempt."
        )
        # Correct the extension based on detected type
        correct_ext = sorted(valid_extensions)[0]  # Pick first alphabetically for consistency
        name_without_ext = safe_filename.rsplit('.', 1)[0] if '.' in safe_filename else safe_filename
        safe_filename = f"{name_without_ext}.{correct_ext}"
        extension = correct_ext

    if not extension:
        # No extension - add one based on detected type
        correct_ext = sorted(valid_extensions)[0]
        safe_filename = f"{safe_filename}.{correct_ext}"
        extension = correct_ext

    logger.debug(
        f"File validated: {safe_filename}, type: {detected_mime}, size: {len(content)} bytes"
    )

    return safe_filename, detected_mime, extension


def is_safe_content_type(content: bytes, claimed_mime: str) -> bool:
    """
    Check if file content matches claimed MIME type.

    Args:
        content: File content bytes
        claimed_mime: MIME type claimed by client

    Returns:
        True if content matches claimed type, False otherwise

    Example:
        >>> is_safe_content_type(pdf_bytes, "application/pdf")
        True
        >>> is_safe_content_type(exe_bytes, "application/pdf")
        False
    """
    detected_mime, _ = validate_magic_bytes(content)

    if detected_mime is None:
        return False

    # Normalize MIME types for comparison
    claimed_normalized = claimed_mime.lower().strip()
    detected_normalized = detected_mime.lower().strip()

    # Direct match
    if claimed_normalized == detected_normalized:
        return True

    # Handle JPEG variations
    jpeg_types = {'image/jpeg', 'image/jpg', 'image/pjpeg'}
    if claimed_normalized in jpeg_types and detected_normalized in jpeg_types:
        return True

    return False
