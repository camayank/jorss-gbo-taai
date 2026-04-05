"""
Document upload and management routes extracted from app.py.

Contains endpoints for:
- POST /api/upload (synchronous document upload)
- POST /api/upload/async (async Celery-based upload)
- GET  /api/upload/status/{task_id}
- POST /api/upload/cancel/{task_id}
- GET  /api/documents
- GET  /api/documents/{document_id}
- GET  /api/documents/{document_id}/status
- GET  /api/documents/{document_id}/download
- POST /api/documents/{document_id}/apply
- DELETE /api/documents/{document_id}
- GET  /api/supported-documents
"""

import os
import uuid
import logging
import threading
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from security.auth_decorators import require_auth, rate_limit, Role

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documents"])


def _get_app_deps():
    """Lazy import app-level dependencies to avoid circular imports."""
    from web.app import (
        _get_persistence,
        _document_processor,
        _DOCUMENTS,
        _DOCUMENTS_LOCK,
        _get_or_create_tax_return,
        _persist_tax_return,
        _log_audit_event,
        _request_user_dict,
        _build_extracted_data,
    )
    from audit.audit_trail import AuditEventType
    return {
        "_get_persistence": _get_persistence,
        "_document_processor": _document_processor,
        "_DOCUMENTS": _DOCUMENTS,
        "_DOCUMENTS_LOCK": _DOCUMENTS_LOCK,
        "_get_or_create_tax_return": _get_or_create_tax_return,
        "_persist_tax_return": _persist_tax_return,
        "_log_audit_event": _log_audit_event,
        "_request_user_dict": _request_user_dict,
        "_build_extracted_data": _build_extracted_data,
        "AuditEventType": AuditEventType,
    }


def _get_or_create_session_id(request: Request) -> str:
    """Get or create a session ID without initializing TaxAgent."""
    session_id = request.cookies.get("tax_session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id


@router.post("/api/upload")
@require_auth(roles=[Role.TAXPAYER, Role.CPA, Role.PREPARER])
@rate_limit(requests_per_minute=10)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    tax_year: Optional[int] = Form(None),
):
    """Upload a tax document for OCR processing."""
    deps = _get_app_deps()
    session_id = _get_or_create_session_id(request)

    allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/tiff"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, PNG, JPEG, TIFF"
        )

    try:
        content = await file.read()
    except Exception as e:
        logger.warning(f"Failed to read uploaded file: {e}")
        raise HTTPException(status_code=400, detail="Failed to read the uploaded file. Please try again with a different file.")

    # Validate file content (magic bytes) — not just the client-supplied MIME type
    try:
        from web.utils.file_validation import validate_upload, FileValidationError
        validate_upload(content, file.filename or "upload")
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = deps["_document_processor"].process_bytes(
            data=content,
            mime_type=file.content_type,
            original_filename=file.filename,
            document_type=document_type,
            tax_year=tax_year,
        )
    except Exception as e:
        logger.exception(f"OCR processing failed: {e}")
        raise HTTPException(status_code=500, detail="Document processing failed. Please ensure the file is a clear image or PDF.")

    doc_id = str(result.document_id)
    result_dict = {
        "document_id": doc_id,
        "document_type": result.document_type,
        "tax_year": result.tax_year,
        "status": result.status,
        "ocr_confidence": result.ocr_confidence,
        "extraction_confidence": result.extraction_confidence,
        "extracted_fields": [f.to_dict() for f in result.extracted_fields],
        "warnings": result.warnings,
        "errors": result.errors,
        "filename": file.filename,
    }
    deps["_get_persistence"]().save_document_result(
        document_id=doc_id,
        session_id=session_id,
        document_type=result.document_type,
        status=result.status,
        result=result_dict,
    )

    json_response = JSONResponse({
        "document_id": doc_id,
        "document_type": result.document_type,
        "tax_year": result.tax_year,
        "status": result.status,
        "ocr_confidence": result.ocr_confidence,
        "extraction_confidence": result.extraction_confidence,
        "extracted_fields": [f.to_dict() for f in result.extracted_fields],
        "warnings": result.warnings,
        "errors": result.errors,
    })
    json_response.set_cookie(
        "tax_session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("APP_ENVIRONMENT") == "production",
        max_age=86400,
    )
    return json_response


@router.post("/api/upload/async")
@require_auth(roles=[Role.TAXPAYER, Role.CPA, Role.PREPARER])
@rate_limit(requests_per_minute=10)
async def upload_document_async(
    request: Request,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    tax_year: Optional[int] = Form(None),
    callback_url: Optional[str] = Form(None),
):
    """Upload a tax document for asynchronous OCR processing."""
    deps = _get_app_deps()
    session_id = _get_or_create_session_id(request)

    allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/tiff"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, PNG, JPEG, TIFF"
        )

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")

    document_id = str(uuid.uuid4())
    persistence = deps["_get_persistence"]()

    persistence.save_document_result(
        document_id=document_id,
        session_id=session_id,
        document_type=document_type,
        status="processing",
        result={"filename": file.filename, "task_id": None},
    )

    try:
        from tasks.ocr_tasks import submit_document_bytes_for_processing

        task_result = submit_document_bytes_for_processing(
            data=content,
            mime_type=file.content_type,
            original_filename=file.filename,
            document_id=document_id,
            document_type=document_type,
            tax_year=tax_year,
            callback_url=callback_url,
        )

        persistence.save_document_result(
            document_id=document_id,
            session_id=session_id,
            document_type=document_type,
            status="processing",
            result={"filename": file.filename, "task_id": task_result["task_id"]},
        )

        json_response = JSONResponse({
            "document_id": document_id,
            "task_id": task_result["task_id"],
            "status": "processing",
            "message": "Document submitted for processing. Use GET /api/upload/status/{task_id} to check status.",
        })
        json_response.set_cookie(
            "tax_session_id", session_id, httponly=True, samesite="lax",
            secure=os.environ.get("APP_ENVIRONMENT") == "production", max_age=86400,
        )
        return json_response

    except ImportError:
        logger.warning("Celery not available, falling back to synchronous processing")
        try:
            result = deps["_document_processor"].process_bytes(
                data=content,
                mime_type=file.content_type,
                original_filename=file.filename,
                document_type=document_type,
                tax_year=tax_year,
            )
            result_dict = {
                "document_id": document_id,
                "document_type": result.document_type,
                "tax_year": result.tax_year,
                "status": "completed",
                "ocr_confidence": result.ocr_confidence,
                "extraction_confidence": result.extraction_confidence,
                "extracted_fields": [f.to_dict() for f in result.extracted_fields],
                "warnings": result.warnings,
                "errors": result.errors,
                "filename": file.filename,
                "task_id": None,
            }
            persistence.save_document_result(
                document_id=document_id,
                session_id=session_id,
                document_type=result.document_type,
                status="completed",
                result=result_dict,
            )
            json_response = JSONResponse({
                "document_id": document_id,
                "task_id": None,
                "status": "completed",
                "message": "Document processed synchronously (async processing unavailable).",
                "document_type": result.document_type,
                "extraction_confidence": result.extraction_confidence,
            })
            json_response.set_cookie(
                "tax_session_id", session_id, httponly=True, samesite="lax",
                secure=os.environ.get("APP_ENVIRONMENT") == "production", max_age=86400,
            )
            return json_response
        except Exception as e:
            persistence.delete_document(document_id)
            logger.exception(f"OCR processing failed for document {document_id}: {e}")
            raise HTTPException(status_code=500, detail="Document processing failed.")

    except Exception as e:
        persistence.delete_document(document_id)
        logger.exception(f"Failed to submit document {document_id} for processing: {e}")
        raise HTTPException(status_code=500, detail="Failed to process document. Please try again later.")


# NOTE: /api/upload/status/{task_id} and /api/upload/cancel/{task_id} are
# defined in src/web/app.py so that the launch-blocker auth guard test
# (which does AST analysis of app.py) can verify their @require_auth decorators.


@router.get("/api/supported-documents")
async def supported_documents():
    """List supported document types for upload."""
    return JSONResponse({
        "supported_types": [
            {"type": "W-2", "description": "Wage and Tax Statement"},
            {"type": "1099-INT", "description": "Interest Income"},
            {"type": "1099-DIV", "description": "Dividends and Distributions"},
            {"type": "1099-NEC", "description": "Nonemployee Compensation"},
            {"type": "1099-MISC", "description": "Miscellaneous Income"},
            {"type": "1099-R", "description": "Retirement Distributions"},
            {"type": "1099-G", "description": "Government Payments"},
            {"type": "1098", "description": "Mortgage Interest Statement"},
            {"type": "1098-T", "description": "Tuition Statement"},
            {"type": "1095-A", "description": "Health Insurance Marketplace"},
        ],
        "supported_file_types": ["application/pdf", "image/png", "image/jpeg", "image/tiff"],
        "max_file_size_mb": 50,
    })
