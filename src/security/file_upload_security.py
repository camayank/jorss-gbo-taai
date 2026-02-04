"""
File Upload Security.

Comprehensive file upload validation and security:
- File type validation (extension + magic bytes)
- File size limits
- Malicious content detection
- Filename sanitization
- Path traversal prevention

Usage:
    from security.file_upload_security import validate_upload, SecureUpload
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

    # In your endpoint
    @app.post("/api/upload")
    async def upload_file(file: UploadFile):
        secure_file = await validate_upload(
            file,
            allowed_types={"pdf", "png", "jpg"},
            max_size_mb=10
        )
        # secure_file.safe_filename, secure_file.content_type, etc.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import uuid
from dataclasses import dataclass
from typing import BinaryIO, Dict, List, Optional, Set, Union

from fastapi import UploadFile

from security.api_errors import APIError, ErrorCode

logger = logging.getLogger(__name__)


# =============================================================================
# FILE TYPE DEFINITIONS
# =============================================================================

# Magic bytes (file signatures) for common file types
MAGIC_BYTES: Dict[str, List[bytes]] = {
    # Images
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "gif": [b"GIF87a", b"GIF89a"],
    "webp": [b"RIFF", b"WEBP"],  # RIFF....WEBP
    "bmp": [b"BM"],
    "ico": [b"\x00\x00\x01\x00"],
    # SVG removed - XSS risk via embedded scripts/event handlers

    # Documents
    "pdf": [b"%PDF"],
    "doc": [b"\xd0\xcf\x11\xe0"],  # MS Compound File
    "docx": [b"PK\x03\x04"],  # ZIP-based (Office Open XML)
    "xls": [b"\xd0\xcf\x11\xe0"],
    "xlsx": [b"PK\x03\x04"],
    "ppt": [b"\xd0\xcf\x11\xe0"],
    "pptx": [b"PK\x03\x04"],
    "odt": [b"PK\x03\x04"],  # OpenDocument
    "ods": [b"PK\x03\x04"],
    "odp": [b"PK\x03\x04"],

    # Archives
    "zip": [b"PK\x03\x04", b"PK\x05\x06"],
    "rar": [b"Rar!\x1a\x07"],
    "7z": [b"7z\xbc\xaf\x27\x1c"],
    "tar": [b"ustar"],  # At offset 257
    "gz": [b"\x1f\x8b"],

    # Text/Data
    "txt": [],  # No magic bytes for plain text
    "csv": [],
    "json": [],
    "xml": [b"<?xml"],
    "html": [b"<!DOCTYPE", b"<html"],

    # Tax-specific formats
    "irs": [b"<?xml"],  # IRS XML format
    "txf": [],  # TXF tax exchange format
}

# MIME type mappings
MIME_TYPES: Dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "ico": "image/x-icon",
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "csv": "text/csv",
    "json": "application/json",
    "xml": "application/xml",
    "html": "text/html",
    "zip": "application/zip",
}

# Dangerous file types that should never be allowed
DANGEROUS_EXTENSIONS = {
    "svg",  # XSS risk - contains executable scripts/event handlers
    "exe", "com", "bat", "cmd", "sh", "bash", "ps1", "psm1",
    "vbs", "vbe", "js", "jse", "ws", "wsf", "wsc", "wsh",
    "msi", "msp", "scr", "pif", "hta", "cpl", "msc", "jar",
    "dll", "sys", "drv", "ocx", "inf", "reg", "lnk", "url",
    "php", "php3", "php4", "php5", "phtml", "asp", "aspx",
    "jsp", "cgi", "pl", "py", "pyc", "rb", "swf",
}

# Patterns that indicate malicious content
MALICIOUS_PATTERNS = [
    # Script tags
    re.compile(rb"<script[^>]*>", re.IGNORECASE),
    # PHP tags
    re.compile(rb"<\?php", re.IGNORECASE),
    # ASP tags
    re.compile(rb"<%", re.IGNORECASE),
    # Shell commands
    re.compile(rb"#!/bin/(ba)?sh"),
    # Windows batch
    re.compile(rb"@echo\s+off", re.IGNORECASE),
    # PowerShell
    re.compile(rb"-ExecutionPolicy\s+Bypass", re.IGNORECASE),
    # Eval/exec (common in exploits)
    re.compile(rb"\beval\s*\(", re.IGNORECASE),
    re.compile(rb"\bexec\s*\(", re.IGNORECASE),
]


# =============================================================================
# SECURE UPLOAD RESULT
# =============================================================================


@dataclass
class SecureUpload:
    """Result of secure file upload validation."""
    original_filename: str
    safe_filename: str
    extension: str
    content_type: str
    size_bytes: int
    file_hash: str
    content: bytes

    @property
    def size_mb(self) -> float:
        """File size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    @property
    def size_kb(self) -> float:
        """File size in kilobytes."""
        return self.size_bytes / 1024


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.

    - Removes path separators
    - Removes null bytes
    - Removes Unicode tricks
    - Limits length
    - Generates safe name if original is invalid
    """
    if not filename:
        return f"upload_{uuid.uuid4().hex[:8]}"

    # Remove path components (prevent traversal)
    filename = os.path.basename(filename)

    # Remove null bytes and control characters
    filename = filename.replace('\x00', '')
    filename = ''.join(c for c in filename if ord(c) >= 32)

    # Remove potentially dangerous characters
    # Keep only alphanumeric, dots, underscores, hyphens
    safe_chars = re.sub(r'[^\w\.\-]', '_', filename)

    # Prevent multiple dots (extension confusion)
    while ".." in safe_chars:
        safe_chars = safe_chars.replace("..", ".")

    # Don't allow hidden files (starting with .)
    safe_chars = safe_chars.lstrip(".")

    # Limit length (keep extension)
    if len(safe_chars) > 200:
        name, ext = os.path.splitext(safe_chars)
        safe_chars = name[:200 - len(ext)] + ext

    # If nothing left, generate a safe name
    if not safe_chars or safe_chars == ".":
        return f"upload_{uuid.uuid4().hex[:8]}"

    return safe_chars


def get_extension(filename: str) -> str:
    """Extract and normalize file extension."""
    if not filename:
        return ""

    _, ext = os.path.splitext(filename)
    return ext.lstrip(".").lower()


def verify_magic_bytes(content: bytes, expected_type: str) -> bool:
    """
    Verify file content matches expected type via magic bytes.

    Returns True if magic bytes match or type has no defined signature.
    """
    expected_signatures = MAGIC_BYTES.get(expected_type.lower(), [])

    # If no signatures defined, can't verify (allow by default)
    if not expected_signatures:
        return True

    # Check if content starts with any expected signature
    for signature in expected_signatures:
        if content.startswith(signature):
            return True

    # Special case: tar files have signature at offset 257
    if expected_type.lower() == "tar" and len(content) > 262:
        if content[257:262] == b"ustar":
            return True

    return False


def detect_malicious_content(content: bytes) -> Optional[str]:
    """
    Scan content for malicious patterns.

    Returns description of detected threat, or None if clean.
    """
    # Check for malicious patterns
    for pattern in MALICIOUS_PATTERNS:
        match = pattern.search(content[:10000])  # Only scan first 10KB
        if match:
            return f"Suspicious pattern detected: {match.group(0)[:50]}"

    # Check for double extensions (file.pdf.exe trick)
    # This is checked via filename, not content

    return None


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


# =============================================================================
# MAIN VALIDATION FUNCTION
# =============================================================================


async def validate_upload(
    file: UploadFile,
    allowed_types: Optional[Set[str]] = None,
    max_size_mb: float = 10.0,
    verify_content: bool = True,
    scan_malicious: bool = True,
    generate_hash: bool = True,
) -> SecureUpload:
    """
    Comprehensively validate an uploaded file.

    Args:
        file: FastAPI UploadFile object
        allowed_types: Set of allowed file extensions (e.g., {"pdf", "png"})
        max_size_mb: Maximum file size in megabytes
        verify_content: Verify file content matches claimed type
        scan_malicious: Scan for malicious content patterns
        generate_hash: Generate SHA-256 hash of content

    Returns:
        SecureUpload object with validated file info

    Raises:
        APIError: If validation fails
    """
    # Get original filename
    original_filename = file.filename or "unknown"

    # Sanitize filename
    safe_filename = sanitize_filename(original_filename)

    # Get extension
    extension = get_extension(safe_filename)

    # Check for dangerous extensions
    if extension.lower() in DANGEROUS_EXTENSIONS:
        logger.warning(f"Dangerous file type rejected: {extension}")
        raise APIError(
            code=ErrorCode.VALIDATION_FILE_TYPE_NOT_ALLOWED,
            message=f"File type '{extension}' is not allowed",
            details={"filename": original_filename, "extension": extension}
        )

    # Check allowed types
    if allowed_types and extension.lower() not in allowed_types:
        raise APIError(
            code=ErrorCode.VALIDATION_FILE_TYPE_NOT_ALLOWED,
            message=f"File type '{extension}' is not allowed. "
                    f"Allowed types: {', '.join(sorted(allowed_types))}",
            details={"filename": original_filename, "allowed": list(allowed_types)}
        )

    # Read file content
    content = await file.read()
    size_bytes = len(content)

    # Check file size
    max_size_bytes = int(max_size_mb * 1024 * 1024)
    if size_bytes > max_size_bytes:
        raise APIError(
            code=ErrorCode.VALIDATION_FILE_TOO_LARGE,
            message=f"File too large. Maximum size: {max_size_mb} MB",
            details={
                "filename": original_filename,
                "size_mb": float(money(size_bytes / (1024 * 1024))),
                "max_size_mb": max_size_mb
            }
        )

    # Check for empty files
    if size_bytes == 0:
        raise APIError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Empty file uploaded",
            details={"filename": original_filename}
        )

    # Verify content matches claimed type
    if verify_content and extension:
        if not verify_magic_bytes(content, extension):
            logger.warning(
                f"File content mismatch: claimed {extension}, "
                f"content doesn't match signature"
            )
            raise APIError(
                code=ErrorCode.VALIDATION_MALICIOUS_CONTENT,
                message="File content does not match its extension",
                details={"filename": original_filename, "extension": extension}
            )

    # Scan for malicious content
    if scan_malicious:
        threat = detect_malicious_content(content)
        if threat:
            logger.warning(f"Malicious content detected in {original_filename}: {threat}")
            raise APIError(
                code=ErrorCode.VALIDATION_MALICIOUS_CONTENT,
                message="File contains potentially malicious content",
                details={"filename": original_filename}
            )

    # Determine content type
    content_type = MIME_TYPES.get(extension.lower(), "application/octet-stream")

    # Generate hash if requested
    file_hash = compute_file_hash(content) if generate_hash else ""

    # Reset file position for potential re-reading
    await file.seek(0)

    logger.info(
        f"File validated: {safe_filename} ({size_bytes} bytes, {extension})"
    )

    return SecureUpload(
        original_filename=original_filename,
        safe_filename=safe_filename,
        extension=extension,
        content_type=content_type,
        size_bytes=size_bytes,
        file_hash=file_hash,
        content=content,
    )


# =============================================================================
# BULK VALIDATION
# =============================================================================


async def validate_uploads(
    files: List[UploadFile],
    allowed_types: Optional[Set[str]] = None,
    max_size_mb: float = 10.0,
    max_files: int = 10,
    max_total_size_mb: float = 50.0,
    **kwargs
) -> List[SecureUpload]:
    """
    Validate multiple uploaded files.

    Args:
        files: List of UploadFile objects
        allowed_types: Set of allowed extensions
        max_size_mb: Max size per file
        max_files: Maximum number of files
        max_total_size_mb: Maximum total size of all files

    Returns:
        List of SecureUpload objects

    Raises:
        APIError: If any validation fails
    """
    if len(files) > max_files:
        raise APIError(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Too many files. Maximum: {max_files}",
            details={"count": len(files), "max": max_files}
        )

    results = []
    total_size = 0

    for file in files:
        secure_file = await validate_upload(
            file,
            allowed_types=allowed_types,
            max_size_mb=max_size_mb,
            **kwargs
        )
        results.append(secure_file)
        total_size += secure_file.size_bytes

    # Check total size
    max_total_bytes = int(max_total_size_mb * 1024 * 1024)
    if total_size > max_total_bytes:
        raise APIError(
            code=ErrorCode.VALIDATION_FILE_TOO_LARGE,
            message=f"Total upload size too large. Maximum: {max_total_size_mb} MB",
            details={
                "total_size_mb": float(money(total_size / (1024 * 1024))),
                "max_total_size_mb": max_total_size_mb
            }
        )

    return results


# =============================================================================
# PREDEFINED ALLOWED TYPES
# =============================================================================

# Common document types for tax uploads
TAX_DOCUMENT_TYPES = {"pdf", "png", "jpg", "jpeg", "gif", "tiff", "tif"}

# Image types only
IMAGE_TYPES = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}

# Office documents
OFFICE_TYPES = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"}

# Data files
DATA_TYPES = {"csv", "json", "xml", "txt"}

# All safe types
ALL_SAFE_TYPES = TAX_DOCUMENT_TYPES | OFFICE_TYPES | DATA_TYPES | {"zip"}
