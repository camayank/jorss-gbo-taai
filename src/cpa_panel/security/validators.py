"""
Security validators and sanitizers for CPA Panel.

Prevents:
- Path traversal attacks
- File upload vulnerabilities
- Information leakage through error messages
- Invalid session ID injection
"""

import re
import os
import logging
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_FILE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
}

# Magic bytes for file type validation
FILE_SIGNATURES = {
    b"%PDF": "application/pdf",
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"II*\x00": "image/tiff",  # Little-endian TIFF
    b"MM\x00*": "image/tiff",  # Big-endian TIFF
}


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitize a filename to prevent path traversal and other attacks.

    Args:
        filename: The original filename from user input

    Returns:
        A safe filename with only alphanumeric, dash, underscore, and dot characters.
        Path components are stripped.
    """
    if not filename:
        return "unnamed_file"

    # Extract just the filename (remove any path components)
    # This prevents path traversal attacks like "../../../etc/passwd"
    filename = os.path.basename(filename)

    # Remove any null bytes
    filename = filename.replace("\x00", "")

    # Only allow safe characters: alphanumeric, dash, underscore, dot
    # Replace anything else with underscore
    safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

    # Prevent double extensions that could bypass filters (e.g., file.php.jpg)
    # Keep only the last extension
    parts = safe_filename.rsplit(".", 1)
    if len(parts) == 2:
        name = re.sub(r"[.]", "_", parts[0])  # Replace dots in name portion
        safe_filename = f"{name}.{parts[1]}"

    # Ensure filename isn't empty or just dots
    if not safe_filename or safe_filename.strip(".") == "":
        safe_filename = "unnamed_file"

    # Limit filename length
    if len(safe_filename) > 255:
        name, ext = os.path.splitext(safe_filename)
        safe_filename = name[:250] + ext

    return safe_filename


def validate_session_id(session_id: Optional[str]) -> Tuple[bool, str]:
    """
    Validate a session ID to ensure it's safe for use in file paths and queries.

    Args:
        session_id: The session ID to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not session_id:
        return False, "Session ID is required"

    # Session IDs should be UUID-like or alphanumeric with dashes/underscores
    # Max reasonable length is 64 characters
    if len(session_id) > 64:
        return False, "Invalid session ID format"

    # Only allow alphanumeric, dash, and underscore
    if not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
        return False, "Invalid session ID format"

    # Prevent path traversal
    if ".." in session_id or "/" in session_id or "\\" in session_id:
        return False, "Invalid session ID format"

    return True, ""


def validate_file_upload(
    content: bytes,
    filename: Optional[str],
    content_type: Optional[str],
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Comprehensive file upload validation.

    Args:
        content: The file content bytes
        filename: The original filename
        content_type: The declared MIME type

    Returns:
        Tuple of (is_valid, error_message, metadata)
        metadata includes: safe_filename, detected_mime_type, file_size
    """
    metadata = {
        "safe_filename": sanitize_filename(filename),
        "detected_mime_type": None,
        "file_size": len(content) if content else 0,
    }

    # Check file size
    if not content:
        return False, "File is empty", metadata

    if len(content) > MAX_FILE_SIZE:
        return False, f"File exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)}MB", metadata

    # Validate extension
    ext = os.path.splitext(metadata["safe_filename"])[1].lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        return False, f"File type not allowed. Allowed: {', '.join(ALLOWED_FILE_EXTENSIONS)}", metadata

    # Validate MIME type if provided
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        # Don't reject immediately - check magic bytes
        logger.warning(f"Unexpected MIME type: {content_type} for file {filename}")

    # Validate magic bytes (file signature)
    detected_type = None
    for signature, mime_type in FILE_SIGNATURES.items():
        if content[:len(signature)] == signature:
            detected_type = mime_type
            break

    if not detected_type:
        return False, "Unable to verify file type. Please ensure the file is a valid PDF or image.", metadata

    metadata["detected_mime_type"] = detected_type

    # Verify magic bytes match claimed extension
    extension_mime_map = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }

    expected_mime = extension_mime_map.get(ext)
    if expected_mime and detected_type != expected_mime:
        logger.warning(
            f"MIME type mismatch: extension {ext} suggests {expected_mime}, "
            f"but magic bytes indicate {detected_type}"
        )
        # Allow the upload but log the mismatch - could be renamed file

    return True, "", metadata


def get_safe_error_message(exception: Exception, include_type: bool = False) -> str:
    """
    Get a safe error message that doesn't leak implementation details.

    Args:
        exception: The exception that occurred
        include_type: Whether to include the exception type name

    Returns:
        A generic, safe error message
    """
    # Map specific exception types to user-friendly messages
    error_messages = {
        "FileNotFoundError": "The requested resource was not found",
        "PermissionError": "Access denied",
        "ValueError": "Invalid input provided",
        "KeyError": "Missing required field",
        "TypeError": "Invalid data format",
        "ConnectionError": "Service temporarily unavailable",
        "TimeoutError": "Request timed out. Please try again.",
    }

    exception_name = type(exception).__name__

    # Log the full error for debugging
    logger.error(f"Error occurred: {exception_name}: {str(exception)}", exc_info=True)

    # Return safe message
    safe_message = error_messages.get(
        exception_name,
        "An error occurred. Please try again or contact support."
    )

    if include_type:
        return f"{safe_message} ({exception_name})"

    return safe_message


def validate_email(email: Optional[str]) -> Tuple[bool, str]:
    """
    Validate an email address format.

    Args:
        email: The email address to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"

    # Basic email validation - RFC 5322 simplified
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if len(email) > 254:  # RFC 5321 limit
        return False, "Email address too long"

    if not re.match(email_pattern, email):
        return False, "Invalid email format"

    return True, ""


def validate_phone(phone: Optional[str]) -> Tuple[bool, str]:
    """
    Validate a phone number format.

    Args:
        phone: The phone number to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone:
        return True, ""  # Phone is optional

    # Remove common formatting characters
    cleaned = re.sub(r"[\s\-\.\(\)]", "", phone)

    # Check for reasonable length (with or without country code)
    if not re.match(r"^\+?[0-9]{10,15}$", cleaned):
        return False, "Invalid phone number format"

    return True, ""
