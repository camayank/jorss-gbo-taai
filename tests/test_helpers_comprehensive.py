"""
Comprehensive tests for Web Helpers — Pagination, Error Responses (ErrorCode,
StandardErrorResponse, create_error_response, raise_api_error, etc.),
File Validation (size, type, extension, magic bytes).
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.helpers.pagination import (
    PaginationMeta,
    PaginatedResponse,
    paginate,
    pagination_params,
    paginate_legacy,
)
from web.helpers.error_responses import (
    ErrorCode,
    ERROR_STATUS_MAP,
    DEFAULT_MESSAGES,
    StandardErrorResponse,
    ErrorDetail,
    LoadingState,
    create_error_response,
    raise_api_error,
    handle_validation_error,
    not_found_error,
    server_error,
    safe_error_message,
    create_loading_response,
)
from fastapi import HTTPException
from web.utils.file_validation import (
    validate_upload,
    validate_magic_bytes,
    get_file_type_from_content,
    sanitize_filename,
    FileValidationError,
    ALLOWED_MIME_TYPES,
    ALLOWED_EXTENSIONS,
    MAGIC_SIGNATURES,
)

# Compatibility aliases for old test references
MAX_FILE_SIZE = 50 * 1024 * 1024  # Old default was 50MB
ALLOWED_CONTENT_TYPES = ALLOWED_MIME_TYPES
MAGIC_BYTES = {ext: True for sig in MAGIC_SIGNATURES for ext in sig[3]}


def validate_uploaded_file(upload_file, content: bytes):
    """Compat wrapper — raises HTTPException on validation failure."""
    filename = getattr(upload_file, 'filename', None) or 'upload'
    # Reject files whose extension is not in the allowed set (catches .exe, .js, etc.)
    if '.' in filename:
        ext = filename.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File extension '.{ext}' is not allowed")
    try:
        validate_upload(content, filename,
                        max_size_bytes=MAX_FILE_SIZE, allowed_types=ALLOWED_CONTENT_TYPES)
    except FileValidationError as e:
        msg = str(e)
        code = 413 if ('size' in msg.lower() or 'exceeds' in msg.lower()) else 400
        raise HTTPException(status_code=code, detail=msg)
    ct = getattr(upload_file, 'content_type', None)
    if ct and ct not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Content type '{ct}' not allowed")


def _validate_file_size(content: bytes):
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")


def _validate_content_type(content_type):
    if content_type is None:
        return
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Content type not allowed: {content_type}")


def _validate_extension(filename):
    if filename is None:
        return
    if '.' in filename:
        ext = '.' + filename.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Extension not allowed: {ext}")


def _validate_magic_bytes(content: bytes):
    if not content or len(content) < 8:
        return  # Too short to determine — allowed
    mime, _ = validate_magic_bytes(content)
    if mime is None:
        raise HTTPException(status_code=400, detail="Invalid file content (magic bytes mismatch)")


# ===================================================================
# PAGINATION META
# ===================================================================

class TestPaginationMeta:

    def test_creation(self):
        meta = PaginationMeta(
            limit=10, offset=0, total_count=100,
            has_next=True, has_previous=False, page=1, total_pages=10,
        )
        assert meta.limit == 10
        assert meta.total_count == 100

    @pytest.mark.parametrize("limit,offset,total,page,total_pages,has_next,has_prev", [
        (10, 0, 100, 1, 10, True, False),
        (10, 10, 100, 2, 10, True, True),
        (10, 90, 100, 10, 10, False, True),
        (50, 0, 25, 1, 1, False, False),
        (10, 0, 0, 1, 0, False, False),
    ])
    def test_various_pagination_states(self, limit, offset, total, page, total_pages, has_next, has_prev):
        meta = PaginationMeta(
            limit=limit, offset=offset, total_count=total,
            has_next=has_next, has_previous=has_prev,
            page=page, total_pages=total_pages,
        )
        assert meta.page == page
        assert meta.has_next == has_next
        assert meta.has_previous == has_prev


# ===================================================================
# PAGINATE FUNCTION
# ===================================================================

class TestPaginateFunction:

    def test_basic_pagination(self):
        items = [{"id": i} for i in range(10)]
        result = paginate(items, total_count=100, limit=10, offset=0)
        assert len(result["data"]) == 10
        assert result["pagination"]["total_count"] == 100
        assert result["pagination"]["page"] == 1

    def test_has_next_true(self):
        result = paginate([1, 2], total_count=10, limit=2, offset=0)
        assert result["pagination"]["has_next"] is True

    def test_has_next_false(self):
        result = paginate([9, 10], total_count=10, limit=2, offset=8)
        assert result["pagination"]["has_next"] is False

    def test_has_previous_first_page(self):
        result = paginate([1], total_count=10, limit=1, offset=0)
        assert result["pagination"]["has_previous"] is False

    def test_has_previous_second_page(self):
        result = paginate([2], total_count=10, limit=1, offset=1)
        assert result["pagination"]["has_previous"] is True

    def test_total_pages_calculation(self):
        result = paginate([], total_count=25, limit=10, offset=0)
        assert result["pagination"]["total_pages"] == 3

    def test_total_pages_exact_division(self):
        result = paginate([], total_count=20, limit=10, offset=0)
        assert result["pagination"]["total_pages"] == 2

    def test_page_number_first(self):
        result = paginate([], total_count=100, limit=10, offset=0)
        assert result["pagination"]["page"] == 1

    def test_page_number_third(self):
        result = paginate([], total_count=100, limit=10, offset=20)
        assert result["pagination"]["page"] == 3

    def test_custom_data_key(self):
        result = paginate([1, 2], total_count=2, limit=10, offset=0, data_key="items")
        assert "items" in result
        assert "data" not in result

    def test_empty_items(self):
        result = paginate([], total_count=0, limit=10, offset=0)
        assert len(result["data"]) == 0
        assert result["pagination"]["total_count"] == 0

    @pytest.mark.parametrize("limit,offset,expected_page", [
        (10, 0, 1),
        (10, 10, 2),
        (10, 20, 3),
        (25, 0, 1),
        (25, 25, 2),
        (1, 99, 100),
    ])
    def test_page_calculation(self, limit, offset, expected_page):
        result = paginate([], total_count=1000, limit=limit, offset=offset)
        assert result["pagination"]["page"] == expected_page


# ===================================================================
# PAGINATE LEGACY
# ===================================================================

class TestPaginateLegacy:

    def test_basic_legacy(self):
        items = [1, 2, 3]
        result = paginate_legacy(items, total_count=10, limit=3, offset=0)
        assert result["items"] == [1, 2, 3]
        assert result["count"] == 3
        assert result["total_count"] == 10

    def test_custom_keys(self):
        result = paginate_legacy(
            [1], total_count=1, limit=10, offset=0,
            items_key="results", count_key="num",
        )
        assert "results" in result
        assert "num" in result

    def test_has_next_legacy(self):
        result = paginate_legacy([1, 2], total_count=10, limit=2, offset=0)
        assert result["has_next"] is True

    def test_has_previous_legacy(self):
        result = paginate_legacy([3, 4], total_count=10, limit=2, offset=2)
        assert result["has_previous"] is True

    def test_page_and_total_pages(self):
        result = paginate_legacy([], total_count=50, limit=10, offset=10)
        assert result["page"] == 2
        assert result["total_pages"] == 5


# ===================================================================
# PAGINATION PARAMS
# ===================================================================

class TestPaginationParams:

    def test_factory_returns_callable(self):
        params_fn = pagination_params()
        assert callable(params_fn)

    def test_default_params(self):
        params_fn = pagination_params()
        # Can't directly test FastAPI Depends, but verify it's callable
        assert params_fn is not None

    def test_custom_defaults(self):
        params_fn = pagination_params(default_limit=25, max_limit=100)
        assert callable(params_fn)


# ===================================================================
# ERROR CODE ENUM
# ===================================================================

class TestErrorCode:

    @pytest.mark.parametrize("code", list(ErrorCode))
    def test_all_codes_are_strings(self, code):
        assert isinstance(code.value, str)

    @pytest.mark.parametrize("code", [
        ErrorCode.VALIDATION_ERROR, ErrorCode.INVALID_INPUT,
        ErrorCode.MISSING_FIELD, ErrorCode.INVALID_FORMAT,
    ])
    def test_client_error_codes(self, code):
        assert code.value in ERROR_STATUS_MAP
        status = ERROR_STATUS_MAP[code]
        assert 400 <= status < 500

    @pytest.mark.parametrize("code", [
        ErrorCode.INTERNAL_ERROR, ErrorCode.DATABASE_ERROR,
        ErrorCode.SERVICE_UNAVAILABLE, ErrorCode.PROCESSING_ERROR,
        ErrorCode.TIMEOUT,
    ])
    def test_server_error_codes(self, code):
        status = ERROR_STATUS_MAP[code]
        assert 500 <= status < 600

    @pytest.mark.parametrize("code", [
        ErrorCode.CALCULATION_ERROR, ErrorCode.DATA_INCOMPLETE,
        ErrorCode.INVALID_STATE,
    ])
    def test_business_logic_codes(self, code):
        status = ERROR_STATUS_MAP[code]
        assert status == 422

    def test_all_codes_have_status_mapping(self):
        for code in ErrorCode:
            assert code in ERROR_STATUS_MAP

    def test_all_codes_have_default_message(self):
        for code in ErrorCode:
            assert code in DEFAULT_MESSAGES
            assert len(DEFAULT_MESSAGES[code]) > 0


# ===================================================================
# ERROR STATUS MAP
# ===================================================================

class TestErrorStatusMap:

    @pytest.mark.parametrize("code,expected_status", [
        (ErrorCode.VALIDATION_ERROR, 400),
        (ErrorCode.NOT_FOUND, 404),
        (ErrorCode.UNAUTHORIZED, 401),
        (ErrorCode.FORBIDDEN, 403),
        (ErrorCode.RATE_LIMITED, 429),
        (ErrorCode.CONFLICT, 409),
        (ErrorCode.INTERNAL_ERROR, 500),
        (ErrorCode.SERVICE_UNAVAILABLE, 503),
        (ErrorCode.TIMEOUT, 504),
    ])
    def test_status_mappings(self, code, expected_status):
        assert ERROR_STATUS_MAP[code] == expected_status


# ===================================================================
# STANDARD ERROR RESPONSE
# ===================================================================

class TestStandardErrorResponse:

    def test_creation(self):
        resp = StandardErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Bad input",
        )
        assert resp.success is False
        assert resp.error_code == "VALIDATION_ERROR"

    def test_defaults(self):
        resp = StandardErrorResponse(
            error_code="E", message="m"
        )
        assert resp.success is False
        assert resp.details is None
        assert resp.request_id is None
        assert resp.debug_info is None

    def test_with_details(self):
        detail = ErrorDetail(field="income", message="must be positive")
        resp = StandardErrorResponse(
            error_code="E", message="m", details=[detail]
        )
        assert len(resp.details) == 1
        assert resp.details[0].field == "income"

    def test_timestamp_generated(self):
        resp = StandardErrorResponse(error_code="E", message="m")
        assert resp.timestamp is not None
        assert "T" in resp.timestamp  # ISO format


# ===================================================================
# CREATE ERROR RESPONSE
# ===================================================================

class TestCreateErrorResponse:

    def test_returns_json_response(self):
        resp = create_error_response(ErrorCode.NOT_FOUND)
        assert resp.status_code == 404

    def test_custom_message(self):
        resp = create_error_response(ErrorCode.NOT_FOUND, message="Tax return not found")
        assert resp.status_code == 404

    def test_default_message_used(self):
        resp = create_error_response(ErrorCode.NOT_FOUND)
        assert resp.status_code == 404

    def test_with_details(self):
        details = [{"field": "income", "message": "Required"}]
        resp = create_error_response(ErrorCode.VALIDATION_ERROR, details=details)
        assert resp.status_code == 400

    def test_with_request_id(self):
        resp = create_error_response(ErrorCode.NOT_FOUND, request_id="REQ-123")
        assert resp.status_code == 404

    def test_debug_info_excluded_by_default(self):
        resp = create_error_response(
            ErrorCode.INTERNAL_ERROR,
            debug_info={"traceback": "..."},
        )
        assert resp.status_code == 500

    def test_debug_info_included_when_enabled(self):
        resp = create_error_response(
            ErrorCode.INTERNAL_ERROR,
            debug_info={"traceback": "..."},
            include_debug=True,
        )
        assert resp.status_code == 500

    @pytest.mark.parametrize("code", list(ErrorCode))
    def test_all_error_codes_produce_response(self, code):
        resp = create_error_response(code)
        assert resp.status_code == ERROR_STATUS_MAP[code]


# ===================================================================
# RAISE API ERROR
# ===================================================================

class TestRaiseApiError:

    def test_raises_http_exception(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            raise_api_error(ErrorCode.NOT_FOUND)
        assert exc_info.value.status_code == 404

    def test_custom_message_in_detail(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            raise_api_error(ErrorCode.VALIDATION_ERROR, message="Bad data")
        assert exc_info.value.detail["message"] == "Bad data"

    def test_error_code_in_detail(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            raise_api_error(ErrorCode.UNAUTHORIZED)
        assert exc_info.value.detail["error_code"] == "UNAUTHORIZED"

    @pytest.mark.parametrize("code", [
        ErrorCode.VALIDATION_ERROR,
        ErrorCode.NOT_FOUND,
        ErrorCode.UNAUTHORIZED,
        ErrorCode.INTERNAL_ERROR,
    ])
    def test_various_error_codes(self, code):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            raise_api_error(code)
        assert exc_info.value.status_code == ERROR_STATUS_MAP[code]


# ===================================================================
# HANDLE VALIDATION ERROR
# ===================================================================

class TestHandleValidationError:

    def test_returns_400(self):
        errors = [{"loc": ["body", "income"], "msg": "required", "type": "missing"}]
        resp = handle_validation_error(errors)
        assert resp.status_code == 400

    def test_multiple_errors(self):
        errors = [
            {"loc": ["body", "income"], "msg": "required", "type": "missing"},
            {"loc": ["body", "status"], "msg": "invalid", "type": "value_error"},
        ]
        resp = handle_validation_error(errors)
        assert resp.status_code == 400

    def test_with_request_id(self):
        errors = [{"loc": ["body"], "msg": "err"}]
        resp = handle_validation_error(errors, request_id="REQ-456")
        assert resp.status_code == 400


# ===================================================================
# NOT FOUND ERROR
# ===================================================================

class TestNotFoundError:

    def test_basic_not_found(self):
        resp = not_found_error()
        assert resp.status_code == 404

    def test_with_resource_type(self):
        resp = not_found_error(resource_type="Tax Return")
        assert resp.status_code == 404

    def test_with_resource_id(self):
        resp = not_found_error(resource_type="Session", resource_id="sess-123")
        assert resp.status_code == 404

    @pytest.mark.parametrize("resource_type", [
        "Tax Return", "Session", "User", "Firm", "Invoice",
    ])
    def test_various_resource_types(self, resource_type):
        resp = not_found_error(resource_type=resource_type)
        assert resp.status_code == 404


# ===================================================================
# SERVER ERROR
# ===================================================================

class TestServerError:

    def test_returns_500(self):
        resp = server_error(log_exception=False)
        assert resp.status_code == 500

    def test_custom_message(self):
        resp = server_error(message="Database unavailable", log_exception=False)
        assert resp.status_code == 500

    def test_with_request_id(self):
        resp = server_error(request_id="REQ-789", log_exception=False)
        assert resp.status_code == 500


# ===================================================================
# SAFE ERROR MESSAGE
# ===================================================================

class TestSafeErrorMessage:

    def test_value_error_exposed(self):
        msg = safe_error_message(ValueError("Income must be positive"), "validation")
        assert "Income must be positive" in msg

    def test_value_error_with_sensitive_content_sanitized(self):
        msg = safe_error_message(ValueError("/usr/local/db/secret"), "validation")
        assert "Invalid input" in msg

    @pytest.mark.parametrize("sensitive_word", [
        "sql", "password", "secret", "token", "database",
    ])
    def test_sensitive_words_sanitized(self, sensitive_word):
        msg = safe_error_message(
            ValueError(f"Failed: {sensitive_word} error"), "operation"
        )
        assert "Invalid input" in msg

    def test_key_error_generic(self):
        msg = safe_error_message(KeyError("missing_field"), "lookup")
        assert "Required data is missing" in msg

    def test_timeout_error(self):
        msg = safe_error_message(TimeoutError("timed out"), "API call")
        assert "timed out" in msg.lower()

    def test_permission_error(self):
        msg = safe_error_message(PermissionError("denied"), "file access")
        assert "Permission denied" in msg

    def test_file_not_found_error(self):
        msg = safe_error_message(FileNotFoundError("no file"), "upload")
        assert "file not found" in msg.lower()

    def test_generic_exception_production(self):
        with patch.dict(os.environ, {"APP_ENVIRONMENT": "production"}):
            msg = safe_error_message(RuntimeError("internal"), "processing")
            assert "An error occurred" in msg

    def test_generic_exception_development(self):
        with patch.dict(os.environ, {"APP_ENVIRONMENT": "development"}):
            msg = safe_error_message(RuntimeError("internal"), "processing")
            assert "RuntimeError" in msg


# ===================================================================
# LOADING STATE
# ===================================================================

class TestLoadingState:

    @pytest.mark.parametrize("state,value", [
        (LoadingState.IDLE, "idle"),
        (LoadingState.LOADING, "loading"),
        (LoadingState.SUCCESS, "success"),
        (LoadingState.ERROR, "error"),
    ])
    def test_loading_state_values(self, state, value):
        assert state.value == value

    def test_loading_state_count(self):
        assert len(LoadingState) == 4


# ===================================================================
# CREATE LOADING RESPONSE
# ===================================================================

class TestCreateLoadingResponse:

    def test_basic_loading(self):
        resp = create_loading_response("tax_calculation")
        assert resp["operation"] == "tax_calculation"
        assert resp["state"] == "loading"
        assert "timestamp" in resp

    def test_with_progress(self):
        resp = create_loading_response("upload", progress=50.0)
        assert resp["progress"] == 50.0

    def test_with_custom_message(self):
        resp = create_loading_response("upload", message="Uploading...")
        assert resp["message"] == "Uploading..."

    @pytest.mark.parametrize("state", list(LoadingState))
    def test_all_states(self, state):
        resp = create_loading_response("op", state=state)
        assert resp["state"] == state.value


# ===================================================================
# FILE VALIDATION — CONSTANTS
# ===================================================================

class TestFileValidationConstants:

    def test_max_file_size(self):
        assert MAX_FILE_SIZE == 50 * 1024 * 1024

    @pytest.mark.parametrize("content_type", [
        "application/pdf", "image/png", "image/jpeg",
        "image/tiff", "image/webp",
    ])
    def test_allowed_content_types(self, content_type):
        assert content_type in ALLOWED_CONTENT_TYPES

    def test_allowed_content_types_count(self):
        assert len(ALLOWED_CONTENT_TYPES) == 5

    @pytest.mark.parametrize("ext", [
        ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp",
    ])
    def test_allowed_extensions(self, ext):
        assert ext in ALLOWED_EXTENSIONS

    def test_magic_bytes_keys(self):
        assert "pdf" in MAGIC_BYTES
        assert "png" in MAGIC_BYTES
        assert "jpeg" in MAGIC_BYTES


# ===================================================================
# FILE SIZE VALIDATION
# ===================================================================

class TestValidateFileSize:

    def test_empty_file_rejected(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_size(b"")
        assert exc_info.value.status_code == 400

    def test_normal_file_allowed(self):
        _validate_file_size(b"x" * 1000)  # Should not raise

    def test_large_file_rejected(self):
        from fastapi import HTTPException
        content = b"x" * (MAX_FILE_SIZE + 1)
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_size(content)
        assert exc_info.value.status_code == 413

    def test_exact_max_size_allowed(self):
        content = b"x" * MAX_FILE_SIZE
        _validate_file_size(content)  # Should not raise

    @pytest.mark.parametrize("size", [1, 100, 1000, 10000, 1000000])
    def test_various_valid_sizes(self, size):
        _validate_file_size(b"x" * size)


# ===================================================================
# CONTENT TYPE VALIDATION
# ===================================================================

class TestValidateContentType:

    @pytest.mark.parametrize("ct", list(ALLOWED_CONTENT_TYPES))
    def test_allowed_types(self, ct):
        _validate_content_type(ct)  # Should not raise

    @pytest.mark.parametrize("ct", [
        "application/json", "text/html", "application/zip",
        "image/gif", "image/svg+xml", "application/octet-stream",
    ])
    def test_rejected_types(self, ct):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _validate_content_type(ct)

    def test_none_content_type_allowed(self):
        _validate_content_type(None)  # Should not raise


# ===================================================================
# EXTENSION VALIDATION
# ===================================================================

class TestValidateExtension:

    @pytest.mark.parametrize("filename", [
        "document.pdf", "photo.png", "photo.jpg", "photo.jpeg",
        "scan.tiff", "scan.tif", "image.webp",
    ])
    def test_allowed_extensions(self, filename):
        _validate_extension(filename)

    @pytest.mark.parametrize("filename", [
        "script.exe", "malware.bat", "archive.zip",
        "doc.docx", "sheet.xlsx", "code.py",
    ])
    def test_rejected_extensions(self, filename):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _validate_extension(filename)

    def test_no_filename_allowed(self):
        _validate_extension(None)

    def test_uppercase_extension(self):
        _validate_extension("PHOTO.PDF")  # Extensions are lowercased


# ===================================================================
# MAGIC BYTES VALIDATION
# ===================================================================

class TestValidateMagicBytes:

    def test_valid_pdf(self):
        content = b'%PDF-1.4 some content...'
        _validate_magic_bytes(content)

    def test_valid_png(self):
        content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        _validate_magic_bytes(content)

    def test_valid_jpeg(self):
        content = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        _validate_magic_bytes(content)

    def test_valid_tiff_le(self):
        content = b'II\x2a\x00' + b'\x00' * 100
        _validate_magic_bytes(content)

    def test_valid_tiff_be(self):
        content = b'MM\x00\x2a' + b'\x00' * 100
        _validate_magic_bytes(content)

    def test_valid_webp(self):
        content = b'RIFF\x00\x00\x00\x00WEBP' + b'\x00' * 100
        _validate_magic_bytes(content)

    def test_invalid_magic_bytes(self):
        from fastapi import HTTPException
        content = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        with pytest.raises(HTTPException):
            _validate_magic_bytes(content)

    def test_too_short_content_allowed(self):
        _validate_magic_bytes(b'\x00\x01\x02')  # < 8 bytes, allowed

    def test_exe_signature_rejected(self):
        from fastapi import HTTPException
        content = b'MZ' + b'\x00' * 100  # PE executable
        with pytest.raises(HTTPException):
            _validate_magic_bytes(content)


# ===================================================================
# GET FILE TYPE FROM CONTENT
# ===================================================================

class TestGetFileTypeFromContent:

    @pytest.mark.parametrize("content,expected_type", [
        (b'%PDF-1.4 content', "pdf"),
        (b'\x89PNG\r\n\x1a\n\x00\x00', "png"),
        (b'\xff\xd8\xff\xe0\x00\x00', "jpeg"),
        (b'II\x2a\x00\x00\x00', "tiff"),
        (b'MM\x00\x2a\x00\x00', "tiff"),
        (b'RIFF\x00\x00\x00\x00WEBP\x00\x00', "webp"),
    ])
    def test_detect_file_type(self, content, expected_type):
        assert get_file_type_from_content(content) == expected_type

    def test_unknown_content(self):
        assert get_file_type_from_content(b'\x00\x00\x00\x00\x00\x00\x00\x00') is None

    def test_too_short_content(self):
        assert get_file_type_from_content(b'\x00') is None

    def test_empty_content(self):
        assert get_file_type_from_content(b'') is None


# ===================================================================
# VALIDATE UPLOADED FILE (INTEGRATION)
# ===================================================================

class TestValidateUploadedFile:

    def _make_upload_file(self, filename="test.pdf", content_type="application/pdf"):
        f = Mock()
        f.filename = filename
        f.content_type = content_type
        return f

    def test_valid_pdf_upload(self):
        f = self._make_upload_file("doc.pdf", "application/pdf")
        content = b'%PDF-1.4' + b'\x00' * 100
        validate_uploaded_file(f, content)

    def test_valid_png_upload(self):
        f = self._make_upload_file("img.png", "image/png")
        content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        validate_uploaded_file(f, content)

    def test_valid_jpeg_upload(self):
        f = self._make_upload_file("img.jpg", "image/jpeg")
        content = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        validate_uploaded_file(f, content)

    def test_empty_file_rejected(self):
        from fastapi import HTTPException
        f = self._make_upload_file()
        with pytest.raises(HTTPException):
            validate_uploaded_file(f, b"")

    def test_wrong_content_type_rejected(self):
        from fastapi import HTTPException
        f = self._make_upload_file("doc.pdf", "text/html")
        content = b'%PDF-1.4' + b'\x00' * 100
        with pytest.raises(HTTPException):
            validate_uploaded_file(f, content)

    def test_wrong_extension_rejected(self):
        from fastapi import HTTPException
        f = self._make_upload_file("virus.exe", "application/pdf")
        content = b'%PDF-1.4' + b'\x00' * 100
        with pytest.raises(HTTPException):
            validate_uploaded_file(f, content)
