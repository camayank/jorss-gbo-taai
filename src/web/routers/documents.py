"""
Document Routes - Document Upload and Management

SPEC-005: Extracted from app.py for modularity.

Routes:
- POST /api/upload - Synchronous document upload
- POST /api/upload/async - Async document upload (Celery)
- GET /api/upload/status/{task_id} - Check async upload status
- POST /api/upload/cancel/{task_id} - Cancel async upload
- GET /api/documents - List documents
- GET /api/documents/{document_id} - Get document details
- GET /api/documents/{document_id}/status - Get processing status
- POST /api/documents/{document_id}/apply - Apply document to return
- DELETE /api/documents/{document_id} - Delete document
- GET /api/supported-documents - List supported document types
"""

from fastapi import APIRouter, Request, Response, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import uuid
import logging
from datetime import datetime

# File upload security validation
from web.utils.file_validation import (
    validate_upload,
    FileValidationError,
    ALLOWED_MIME_TYPES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Documents"])

# These will be injected from the main app
_document_processor = None
_session_persistence = None


def set_dependencies(document_processor, session_persistence):
    """Set dependencies from the main app."""
    global _document_processor, _session_persistence
    _document_processor = document_processor
    _session_persistence = session_persistence


def _get_document_processor():
    """Get document processor, importing lazily if needed."""
    global _document_processor
    if _document_processor is None:
        from services.ocr import DocumentProcessor
        _document_processor = DocumentProcessor()
    return _document_processor


def _get_session_persistence():
    """Get session persistence, importing lazily if needed."""
    global _session_persistence
    if _session_persistence is None:
        from database.session_persistence import get_session_persistence
        _session_persistence = get_session_persistence()
    return _session_persistence


# =============================================================================
# DOCUMENT UPLOAD ROUTES
# =============================================================================

@router.post("/upload")
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
):
    """
    Upload and process a tax document synchronously.

    Supports: W-2, 1099-INT, 1099-DIV, 1099-MISC, 1099-NEC, 1099-R, 1098
    """
    try:
        # Get or create session
        if not session_id:
            session_id = request.cookies.get("tax_session_id") or str(uuid.uuid4())

        # Validate file
        if not file.filename:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "No file provided"}
            )

        # Read file content
        content = await file.read()

        # Validate file using magic bytes (prevents .exe renamed to .pdf attacks)
        try:
            safe_filename, mime_type, extension = validate_upload(
                content=content,
                filename=file.filename or "document",
                max_size_bytes=20 * 1024 * 1024,  # 20MB limit
            )
        except FileValidationError as e:
            logger.warning(f"File validation failed: {e}")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": str(e)}
            )

        processor = _get_document_processor()
        result = processor.process_bytes(content, mime_type, safe_filename)

        # Check if processing succeeded (status is "success" or "completed_with_warnings")
        if result.status in ("success", "completed_with_warnings", "needs_review"):
            # Generate document ID
            document_id = str(uuid.uuid4())

            # Store result
            persistence = _get_session_persistence()
            persistence.save_document_result(
                document_id=document_id,
                session_id=session_id,
                document_type=result.document_type,
                status="completed",
                result=result.get_extracted_data()
            )

            # Set session cookie
            response.set_cookie(
                key="tax_session_id",
                value=session_id,
                httponly=True,
                samesite="lax",
                max_age=86400 * 7  # 7 days
            )

            return JSONResponse({
                "status": "success",
                "document_id": document_id,
                "session_id": session_id,
                "document_type": result.document_type,
                "extracted_data": result.get_extracted_data(),
                "confidence": result.extraction_confidence,
                "warnings": result.warnings if result.warnings else None,
            })
        else:
            error_msg = result.errors[0] if result.errors else "Document processing failed"
            return JSONResponse(
                status_code=422,
                content={
                    "status": "error",
                    "error": error_msg,
                }
            )

    except Exception as e:
        logger.exception(f"Document upload error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/upload/async")
async def upload_document_async(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
):
    """
    Upload a document for async processing via Celery.

    Returns a task_id to check status.
    """
    try:
        # Get or create session
        if not session_id:
            session_id = request.cookies.get("tax_session_id") or str(uuid.uuid4())

        # Validate file
        if not file.filename:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "No file provided"}
            )

        # Read file content
        content = await file.read()

        # Validate file using magic bytes (prevents .exe renamed to .pdf attacks)
        try:
            safe_filename, mime_type, extension = validate_upload(
                content=content,
                filename=file.filename or "document",
                max_size_bytes=20 * 1024 * 1024,  # 20MB limit
            )
        except FileValidationError as e:
            logger.warning(f"File validation failed: {e}")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": str(e)}
            )

        # Submit to Celery
        try:
            from tasks.document_tasks import process_document_task
            import base64

            # Encode content for Celery
            content_b64 = base64.b64encode(content).decode('utf-8')

            task = process_document_task.delay(
                content_b64=content_b64,
                filename=safe_filename,
                session_id=session_id,
            )

            # Set session cookie
            response.set_cookie(
                key="tax_session_id",
                value=session_id,
                httponly=True,
                samesite="lax",
                max_age=86400 * 7
            )

            return JSONResponse({
                "status": "pending",
                "task_id": task.id,
                "session_id": session_id,
                "message": "Document submitted for processing",
            })

        except ImportError:
            # Celery not available, fall back to sync
            logger.warning("Celery not available, falling back to sync processing")
            return await upload_document(request, response, file, session_id)

    except Exception as e:
        logger.exception(f"Async upload error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.get("/upload/status/{task_id}")
async def get_upload_status(task_id: str, request: Request):
    """Check the status of an async document upload task."""
    try:
        from celery.result import AsyncResult
        from tasks.celery_app import celery_app

        result = AsyncResult(task_id, app=celery_app)

        if result.state == "PENDING":
            return JSONResponse({
                "status": "pending",
                "task_id": task_id,
                "message": "Task is waiting to be processed",
            })
        elif result.state == "STARTED":
            return JSONResponse({
                "status": "processing",
                "task_id": task_id,
                "message": "Document is being processed",
            })
        elif result.state == "SUCCESS":
            return JSONResponse({
                "status": "success",
                "task_id": task_id,
                "result": result.result,
            })
        elif result.state == "FAILURE":
            return JSONResponse({
                "status": "error",
                "task_id": task_id,
                "error": str(result.result),
            })
        else:
            return JSONResponse({
                "status": result.state.lower(),
                "task_id": task_id,
            })

    except ImportError:
        return JSONResponse(
            status_code=501,
            content={"status": "error", "error": "Celery not available"}
        )
    except Exception as e:
        logger.exception(f"Status check error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/upload/cancel/{task_id}")
async def cancel_upload_task(task_id: str, request: Request):
    """Cancel an async document upload task."""
    try:
        from celery.result import AsyncResult
        from tasks.celery_app import celery_app

        result = AsyncResult(task_id, app=celery_app)
        result.revoke(terminate=True)

        return JSONResponse({
            "status": "cancelled",
            "task_id": task_id,
            "message": "Task cancellation requested",
        })

    except ImportError:
        return JSONResponse(
            status_code=501,
            content={"status": "error", "error": "Celery not available"}
        )
    except Exception as e:
        logger.exception(f"Cancel error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


# =============================================================================
# DOCUMENT MANAGEMENT ROUTES
# =============================================================================

@router.get("/documents")
async def list_documents(
    request: Request,
    session_id: Optional[str] = None,
):
    """List all documents for a session."""
    try:
        if not session_id:
            session_id = request.cookies.get("tax_session_id")

        if not session_id:
            return JSONResponse({
                "status": "success",
                "documents": [],
                "count": 0,
            })

        persistence = _get_session_persistence()
        documents = persistence.list_session_documents(session_id)

        return JSONResponse({
            "status": "success",
            "documents": [
                {
                    "document_id": doc.document_id,
                    "document_type": doc.document_type,
                    "status": doc.status,
                    "created_at": doc.created_at,
                }
                for doc in documents
            ],
            "count": len(documents),
        })

    except Exception as e:
        logger.exception(f"List documents error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.get("/documents/{document_id}")
async def get_document(document_id: str, request: Request):
    """Get document details by ID."""
    try:
        session_id = request.cookies.get("tax_session_id")

        persistence = _get_session_persistence()
        doc = persistence.load_document_result(document_id, session_id=session_id)

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return JSONResponse({
            "status": "success",
            "document": {
                "document_id": doc.document_id,
                "document_type": doc.document_type,
                "status": doc.status,
                "created_at": doc.created_at,
                "result": doc.result,
                "error_message": doc.error_message,
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get document error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.get("/documents/{document_id}/status")
async def get_document_status(document_id: str, request: Request):
    """Get document processing status."""
    try:
        session_id = request.cookies.get("tax_session_id")

        persistence = _get_session_persistence()
        doc = persistence.load_document_result(document_id, session_id=session_id)

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return JSONResponse({
            "status": "success",
            "document_id": document_id,
            "processing_status": doc.status,
            "document_type": doc.document_type,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get status error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/documents/{document_id}/apply")
async def apply_document(document_id: str, request: Request):
    """Apply extracted document data to the tax return."""
    try:
        session_id = request.cookies.get("tax_session_id")
        if not session_id:
            raise HTTPException(status_code=400, detail="No session found")

        persistence = _get_session_persistence()
        doc = persistence.load_document_result(document_id, session_id=session_id)

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc.status != "completed":
            raise HTTPException(status_code=400, detail="Document not yet processed")

        # Load current return data
        return_data = persistence.load_session_tax_return(session_id)
        if not return_data:
            return_data = {"return_data": {}}

        # Merge extracted data based on document type
        extracted = doc.result
        current = return_data.get("return_data", {})

        if doc.document_type == "W-2":
            # Add W-2 to list
            w2_forms = current.get("income", {}).get("w2_forms", [])
            w2_forms.append(extracted)
            if "income" not in current:
                current["income"] = {}
            current["income"]["w2_forms"] = w2_forms

        elif doc.document_type.startswith("1099"):
            # Add 1099 to list
            forms_1099 = current.get("income", {}).get("forms_1099", [])
            forms_1099.append({"type": doc.document_type, **extracted})
            if "income" not in current:
                current["income"] = {}
            current["income"]["forms_1099"] = forms_1099

        # Save updated return
        persistence.save_session_tax_return(
            session_id=session_id,
            return_data=current,
        )

        return JSONResponse({
            "status": "success",
            "message": f"{doc.document_type} applied to return",
            "document_id": document_id,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Apply document error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, request: Request):
    """Delete a document."""
    try:
        session_id = request.cookies.get("tax_session_id")

        persistence = _get_session_persistence()

        # Verify document belongs to session
        doc = persistence.load_document_result(document_id, session_id=session_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete
        persistence.delete_document(document_id)

        return JSONResponse({
            "status": "success",
            "message": "Document deleted",
            "document_id": document_id,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Delete document error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


# =============================================================================
# DOCUMENT INFO ROUTES
# =============================================================================

@router.get("/supported-documents")
async def get_supported_documents():
    """Get list of supported document types."""
    return JSONResponse({
        "status": "success",
        "supported_documents": [
            {
                "type": "W-2",
                "name": "Wage and Tax Statement",
                "description": "Reports wages and taxes withheld from employment",
            },
            {
                "type": "1099-INT",
                "name": "Interest Income",
                "description": "Reports interest income from banks and investments",
            },
            {
                "type": "1099-DIV",
                "name": "Dividend Income",
                "description": "Reports dividend income from investments",
            },
            {
                "type": "1099-MISC",
                "name": "Miscellaneous Income",
                "description": "Reports miscellaneous income",
            },
            {
                "type": "1099-NEC",
                "name": "Nonemployee Compensation",
                "description": "Reports self-employment/contractor income",
            },
            {
                "type": "1099-R",
                "name": "Retirement Distributions",
                "description": "Reports distributions from retirement accounts",
            },
            {
                "type": "1098",
                "name": "Mortgage Interest",
                "description": "Reports mortgage interest paid",
            },
            {
                "type": "1098-T",
                "name": "Tuition Statement",
                "description": "Reports tuition payments for education credits",
            },
        ]
    })
