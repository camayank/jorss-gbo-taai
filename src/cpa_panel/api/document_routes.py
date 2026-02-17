"""
CPA Panel Document Routes

API endpoints for document upload, OCR processing, and extraction
management in the CPA panel.

SECURITY: All endpoints require authentication via get_current_user dependency.
"""

from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional
import logging

# Import authentication dependency
from core.api.auth_routes import get_current_user
from core.models.user import UserContext

logger = logging.getLogger(__name__)

document_router = APIRouter(tags=["Document Processing"])


def get_document_adapter():
    """Get the document adapter singleton."""
    from cpa_panel.adapters.document_adapter import get_document_adapter
    return get_document_adapter()


# =============================================================================
# DOCUMENT UPLOAD
# =============================================================================

@document_router.post("/session/{session_id}/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    tax_year: Optional[int] = Form(None),
    user: UserContext = Depends(get_current_user),
):
    """
    Upload a document for OCR processing.

    Form data:
        - file: The document file (PDF, PNG, JPG)
        - document_type: Optional type override (w2, 1099-int, etc.)
        - tax_year: Optional tax year override

    Returns:
        Processing result with extracted data
    """
    # Validate file type
    allowed_types = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
    ]

    content_type = file.content_type or ""
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type}. Allowed: PDF, PNG, JPG, TIFF",
        )

    try:
        # Read file data
        file_data = await file.read()

        adapter = get_document_adapter()
        result = adapter.upload_document(
            session_id=session_id,
            file_data=file_data,
            filename=file.filename or "document",
            mime_type=content_type,
            document_type=document_type,
            tax_year=tax_year,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Upload failed")
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload error for {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the document"
        )


# =============================================================================
# DOCUMENT LISTING
# =============================================================================

@document_router.get("/session/{session_id}/documents")
async def get_documents(
    session_id: str,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    Get all documents for a session.

    Returns list of documents with their processing status.
    Requires authentication.
    """
    try:
        adapter = get_document_adapter()
        result = adapter.get_documents(session_id)

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Get documents error for {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving documents"
        )


@document_router.get("/session/{session_id}/documents/{document_id}")
async def get_document(
    session_id: str,
    document_id: str,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    Get a specific document's details.

    Returns document info including processing result.
    Requires authentication.
    """
    try:
        adapter = get_document_adapter()
        result = adapter.get_document(session_id, document_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "Document not found")
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error for {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the document"
        )


# =============================================================================
# EXTRACTED DATA
# =============================================================================

@document_router.get("/session/{session_id}/documents/{document_id}/extracted")
async def get_extracted_data(
    session_id: str,
    document_id: str,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    Get extracted data from a processed document.

    Returns the structured data extracted by OCR.
    Requires authentication.
    """
    try:
        adapter = get_document_adapter()
        result = adapter.get_extracted_data(session_id, document_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "Document not found")
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get extracted data error for {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving extracted data"
        )


# =============================================================================
# APPLY TO RETURN
# =============================================================================

@document_router.post("/session/{session_id}/documents/{document_id}/apply")
async def apply_to_return(
    session_id: str,
    document_id: str,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    Apply extracted document data to the tax return.

    Takes the OCR-extracted data and populates the appropriate
    fields in the client's tax return.
    Requires authentication.
    """
    try:
        adapter = get_document_adapter()
        result = adapter.apply_to_return(session_id, document_id)

        if not result.get("success"):
            error_msg = result.get("error", "").lower()
            if "not found" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result.get("error", "Document not found"),
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result.get("error", "Apply failed"),
                )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apply document error for {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while applying document data"
        )


# =============================================================================
# SUPPORTED TYPES
# =============================================================================

@document_router.get("/documents/supported-types")
async def get_supported_types(
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    Get list of supported document types.

    Returns:
        - Supported document types for OCR
        - Types that can be auto-applied to returns
        - Types that require manual entry

    Requires authentication.
    """
    try:
        adapter = get_document_adapter()
        result = adapter.get_supported_types()

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Get supported types error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving supported types"
        )
