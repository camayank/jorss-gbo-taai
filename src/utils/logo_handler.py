"""
Logo Upload and Management Handler.

Provides secure logo upload, validation, and storage for CPA branding.
"""

import os
import io
import re
import uuid
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple, BinaryIO
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Pattern for safe CPA identifiers (alphanumeric, hyphens, underscores)
_SAFE_CPA_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]+$')


def _validate_cpa_id(cpa_id: str) -> str:
    """Validate cpa_id to prevent path traversal attacks."""
    if not cpa_id or not _SAFE_CPA_ID_RE.match(cpa_id):
        raise ValueError(f"Invalid CPA identifier")
    return cpa_id

# Supported image formats
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
ALLOWED_MIME_TYPES = {
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/webp',
    'image/svg+xml',
}

# Size limits
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_DIMENSION = 2000  # pixels
MIN_DIMENSION = 50    # pixels


@dataclass
class LogoMetadata:
    """Metadata for uploaded logo."""
    logo_id: str
    filename: str
    content_type: str
    file_size: int
    width: Optional[int]
    height: Optional[int]
    uploaded_at: datetime
    file_path: str
    checksum: str


@dataclass
class LogoValidationResult:
    """Result of logo validation."""
    is_valid: bool
    error_message: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None


class LogoHandler:
    """
    Handles logo upload, validation, and storage.

    Usage:
        handler = LogoHandler(storage_path="/app/logos")

        # Upload a logo
        result = handler.upload_logo(
            file_content=file_bytes,
            filename="company_logo.png",
            cpa_id="john-smith-cpa"
        )

        if result.is_valid:
            logo_path = result.logo_path
            # Use logo_path in branding config

        # Get logo path
        logo_path = handler.get_logo_path("john-smith-cpa")
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize logo handler.

        Args:
            storage_path: Directory to store uploaded logos.
                         Defaults to /tmp/cpa_logos or configured path.
        """
        self.storage_path = Path(
            storage_path or
            os.environ.get('LOGO_STORAGE_PATH', '/tmp/cpa_logos')
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory cache of logo metadata
        self._metadata_cache: dict[str, LogoMetadata] = {}

        logger.info(f"Logo handler initialized: {self.storage_path}")

    def validate_logo(
        self,
        file_content: bytes,
        filename: str,
        content_type: Optional[str] = None
    ) -> LogoValidationResult:
        """
        Validate a logo file before upload.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            content_type: MIME type (optional, will be detected)

        Returns:
            LogoValidationResult with validation status
        """
        # Check file size
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE:
            return LogoValidationResult(
                is_valid=False,
                error_message=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB",
                file_size=file_size
            )

        if file_size == 0:
            return LogoValidationResult(
                is_valid=False,
                error_message="File is empty"
            )

        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return LogoValidationResult(
                is_valid=False,
                error_message=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Validate image content
        try:
            width, height = self._get_image_dimensions(file_content, ext)

            if width and height:
                if width > MAX_DIMENSION or height > MAX_DIMENSION:
                    return LogoValidationResult(
                        is_valid=False,
                        error_message=f"Image too large. Maximum dimensions: {MAX_DIMENSION}x{MAX_DIMENSION}",
                        width=width,
                        height=height
                    )

                if width < MIN_DIMENSION or height < MIN_DIMENSION:
                    return LogoValidationResult(
                        is_valid=False,
                        error_message=f"Image too small. Minimum dimensions: {MIN_DIMENSION}x{MIN_DIMENSION}",
                        width=width,
                        height=height
                    )

            return LogoValidationResult(
                is_valid=True,
                width=width,
                height=height,
                file_size=file_size
            )

        except Exception as e:
            logger.error(f"Logo validation error: {e}")
            return LogoValidationResult(
                is_valid=False,
                error_message=f"Invalid image file: {str(e)}"
            )

    def _get_image_dimensions(
        self,
        file_content: bytes,
        extension: str
    ) -> Tuple[Optional[int], Optional[int]]:
        """Get image dimensions without full image library."""
        # SVG doesn't have fixed dimensions
        if extension == '.svg':
            return None, None

        try:
            # Try PIL if available
            from PIL import Image
            img = Image.open(io.BytesIO(file_content))
            return img.size
        except ImportError:
            # Fallback: read dimensions from file header
            return self._read_image_header(file_content)

    def _read_image_header(
        self,
        file_content: bytes
    ) -> Tuple[Optional[int], Optional[int]]:
        """Read image dimensions from file header (no PIL required)."""
        # PNG
        if file_content[:8] == b'\x89PNG\r\n\x1a\n':
            if len(file_content) >= 24:
                width = int.from_bytes(file_content[16:20], 'big')
                height = int.from_bytes(file_content[20:24], 'big')
                return width, height

        # JPEG
        if file_content[:2] == b'\xff\xd8':
            # Search for SOF marker
            i = 2
            while i < len(file_content) - 9:
                if file_content[i] == 0xff:
                    marker = file_content[i+1]
                    if marker in (0xc0, 0xc1, 0xc2):  # SOF markers
                        height = int.from_bytes(file_content[i+5:i+7], 'big')
                        width = int.from_bytes(file_content[i+7:i+9], 'big')
                        return width, height
                    length = int.from_bytes(file_content[i+2:i+4], 'big')
                    i += length + 2
                else:
                    i += 1

        # GIF
        if file_content[:6] in (b'GIF87a', b'GIF89a'):
            if len(file_content) >= 10:
                width = int.from_bytes(file_content[6:8], 'little')
                height = int.from_bytes(file_content[8:10], 'little')
                return width, height

        return None, None

    def upload_logo(
        self,
        file_content: bytes,
        filename: str,
        cpa_id: str,
        content_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Upload and store a logo file.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            cpa_id: CPA identifier for organization
            content_type: MIME type (optional)

        Returns:
            Tuple of (success, logo_path or None, error_message or None)
        """
        # Validate
        validation = self.validate_logo(file_content, filename, content_type)
        if not validation.is_valid:
            return False, None, validation.error_message

        try:
            # Generate unique filename
            ext = Path(filename).suffix.lower()
            logo_id = str(uuid.uuid4())[:8]
            safe_filename = f"{cpa_id}_{logo_id}{ext}"

            # Calculate checksum
            checksum = hashlib.md5(file_content).hexdigest()

            # Create CPA directory (validate to prevent path traversal)
            _validate_cpa_id(cpa_id)
            cpa_dir = self.storage_path / cpa_id
            cpa_dir.mkdir(parents=True, exist_ok=True)

            # Save file
            file_path = cpa_dir / safe_filename
            file_path.write_bytes(file_content)

            # Store metadata
            metadata = LogoMetadata(
                logo_id=logo_id,
                filename=filename,
                content_type=content_type or f"image/{ext[1:]}",
                file_size=len(file_content),
                width=validation.width,
                height=validation.height,
                uploaded_at=datetime.now(),
                file_path=str(file_path),
                checksum=checksum,
            )
            self._metadata_cache[cpa_id] = metadata

            logger.info(f"Logo uploaded for {cpa_id}: {safe_filename}")
            return True, str(file_path), None

        except Exception as e:
            logger.error(f"Logo upload failed: {e}")
            return False, None, f"Upload failed: {str(e)}"

    def get_logo_path(self, cpa_id: str) -> Optional[str]:
        """
        Get the logo path for a CPA.

        Args:
            cpa_id: CPA identifier

        Returns:
            Path to logo file, or None if not found
        """
        # Check cache first
        if cpa_id in self._metadata_cache:
            path = Path(self._metadata_cache[cpa_id].file_path)
            if path.exists():
                return str(path)

        # Search in storage (validate to prevent path traversal)
        _validate_cpa_id(cpa_id)
        cpa_dir = self.storage_path / cpa_id
        if cpa_dir.exists():
            for ext in ALLOWED_EXTENSIONS:
                for logo_file in cpa_dir.glob(f"*{ext}"):
                    return str(logo_file)

        return None

    def delete_logo(self, cpa_id: str) -> bool:
        """
        Delete logo for a CPA.

        Args:
            cpa_id: CPA identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            logo_path = self.get_logo_path(cpa_id)
            if logo_path:
                Path(logo_path).unlink()

                # Clear cache
                if cpa_id in self._metadata_cache:
                    del self._metadata_cache[cpa_id]

                logger.info(f"Logo deleted for {cpa_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Logo deletion failed: {e}")
            return False

    def get_logo_url(self, cpa_id: str, base_url: str = "/api/logos") -> Optional[str]:
        """
        Get the URL for a logo.

        Args:
            cpa_id: CPA identifier
            base_url: Base URL for logo serving

        Returns:
            URL to access logo, or None if not found
        """
        if self.get_logo_path(cpa_id):
            return f"{base_url}/{cpa_id}"
        return None


# =============================================================================
# FASTAPI INTEGRATION
# =============================================================================

def create_logo_upload_endpoint(logo_handler: LogoHandler):
    """
    Create FastAPI endpoint for logo upload.

    Usage:
        from fastapi import APIRouter, UploadFile, File
        from utils.logo_handler import LogoHandler, create_logo_upload_endpoint

        handler = LogoHandler()
        router = APIRouter()

        @router.post("/upload-logo")
        async def upload_logo(
            cpa_id: str,
            file: UploadFile = File(...)
        ):
            return await create_logo_upload_endpoint(handler)(cpa_id, file)
    """
    async def endpoint(cpa_id: str, file):
        from fastapi import HTTPException

        # Read file content
        content = await file.read()

        # Upload
        success, logo_path, error = logo_handler.upload_logo(
            file_content=content,
            filename=file.filename,
            cpa_id=cpa_id,
            content_type=file.content_type,
        )

        if not success:
            raise HTTPException(status_code=400, detail=error)

        return {
            "success": True,
            "logo_path": logo_path,
            "logo_url": logo_handler.get_logo_url(cpa_id),
        }

    return endpoint


# Global instance
logo_handler = LogoHandler()
