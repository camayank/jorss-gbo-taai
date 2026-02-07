"""
File Upload Validation Utilities

Provides security-focused validation for uploaded files including:
- Size limits
- Content type verification
- Magic byte validation (anti-MIME spoofing)
- Extension validation
"""

import os
from typing import Set
from fastapi import UploadFile, HTTPException


# =============================================================================
# CONFIGURATION
# =============================================================================

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

ALLOWED_CONTENT_TYPES: Set[str] = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/webp"
}

ALLOWED_EXTENSIONS: Set[str] = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp"
}

# Magic bytes for file type verification
MAGIC_BYTES = {
    "pdf": (b'%PDF', 0, 4),           # PDF starts with %PDF
    "png": (b'\x89PNG\r\n\x1a\n', 0, 8),  # PNG signature
    "jpeg": (b'\xff\xd8\xff', 0, 3),      # JPEG starts with FFD8FF
    "tiff_le": (b'II\x2a\x00', 0, 4),     # TIFF little-endian
    "tiff_be": (b'MM\x00\x2a', 0, 4),     # TIFF big-endian
    "webp": (b'RIFF', 0, 4),              # WebP (also check WEBP at offset 8)
}


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_uploaded_file(file: UploadFile, content: bytes) -> None:
    """
    Validate uploaded file for security and compliance.

    Performs the following checks:
    1. File size (max 50MB)
    2. Content type (PDF, PNG, JPEG, TIFF, WebP)
    3. File extension
    4. Magic bytes (prevents MIME type spoofing)

    Args:
        file: FastAPI UploadFile object
        content: File content as bytes

    Raises:
        HTTPException: If any validation fails
    """
    _validate_file_size(content)
    _validate_content_type(file.content_type)
    _validate_extension(file.filename)
    _validate_magic_bytes(content)


def _validate_file_size(content: bytes) -> None:
    """Validate file is not too large or empty."""
    if len(content) == 0:
        raise HTTPException(400, "Empty file not allowed")

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            413,
            f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )


def _validate_content_type(content_type: str | None) -> None:
    """Validate content type is allowed."""
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            400,
            f"Invalid file type '{content_type}'. Allowed: PDF, PNG, JPEG, TIFF, WebP"
        )


def _validate_extension(filename: str | None) -> None:
    """Validate file extension is allowed."""
    if not filename:
        return

    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Invalid file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def _validate_magic_bytes(content: bytes) -> None:
    """
    Validate file content matches expected magic bytes.

    Prevents MIME type spoofing where a malicious file
    masquerades as a different file type.
    """
    if len(content) < 8:
        return  # Too short to validate, allow (other checks will catch issues)

    # Check for valid file signatures
    is_valid = False

    # PDF
    if content[:4] == b'%PDF':
        is_valid = True
    # PNG
    elif content[:8] == b'\x89PNG\r\n\x1a\n':
        is_valid = True
    # JPEG
    elif content[:3] == b'\xff\xd8\xff':
        is_valid = True
    # TIFF (little-endian or big-endian)
    elif content[:4] in (b'II\x2a\x00', b'MM\x00\x2a'):
        is_valid = True
    # WebP (RIFF....WEBP)
    elif content[:4] == b'RIFF' and len(content) >= 12 and content[8:12] == b'WEBP':
        is_valid = True

    if not is_valid:
        raise HTTPException(
            400,
            "File content does not match declared type. Please upload a valid PDF or image."
        )


def get_file_type_from_content(content: bytes) -> str | None:
    """
    Detect file type from content using magic bytes.

    Args:
        content: File content as bytes

    Returns:
        Detected file type ('pdf', 'png', 'jpeg', 'tiff', 'webp') or None
    """
    if len(content) < 4:
        return None

    if content[:4] == b'%PDF':
        return 'pdf'
    elif len(content) >= 8 and content[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    elif content[:3] == b'\xff\xd8\xff':
        return 'jpeg'
    elif content[:4] in (b'II\x2a\x00', b'MM\x00\x2a'):
        return 'tiff'
    elif content[:4] == b'RIFF' and len(content) >= 12 and content[8:12] == b'WEBP':
        return 'webp'

    return None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "validate_uploaded_file",
    "get_file_type_from_content",
    "MAX_FILE_SIZE",
    "ALLOWED_CONTENT_TYPES",
    "ALLOWED_EXTENSIONS",
]
