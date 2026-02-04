"""
Core Documents API Routes

Unified document management endpoints for all user types:
- Document upload/download
- Document categorization
- Document requests
- Document sharing

Access control is automatically applied based on UserContext.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, status
from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from uuid import uuid4
import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, OperationalError

from .auth_routes import get_current_user
from ..models.user import UserContext, UserType
from database.async_engine import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Core Documents"])


# =============================================================================
# MODELS
# =============================================================================

class DocumentCategory(str, Enum):
    TAX_FORM = "tax_form"
    W2 = "w2"
    FORM_1099 = "1099"
    RECEIPT = "receipt"
    BANK_STATEMENT = "bank_statement"
    INVESTMENT = "investment"
    PROPERTY = "property"
    MEDICAL = "medical"
    CHARITABLE = "charitable"
    BUSINESS = "business"
    IDENTITY = "identity"
    OTHER = "other"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Document(BaseModel):
    """Document model."""
    id: str
    user_id: str
    firm_id: Optional[str] = None
    tax_return_id: Optional[str] = None

    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    category: DocumentCategory
    status: DocumentStatus

    # Metadata
    description: Optional[str] = None
    tax_year: Optional[int] = None
    notes: Optional[str] = None

    # Access tracking
    uploaded_by: str
    uploaded_at: datetime
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None

    # Storage
    storage_path: str
    thumbnail_path: Optional[str] = None


class DocumentSummary(BaseModel):
    """Summary view of document."""
    id: str
    filename: str
    category: DocumentCategory
    status: DocumentStatus
    file_size: int
    uploaded_at: datetime
    tax_year: Optional[int]


class DocumentRequest(BaseModel):
    """Request for a document from a user."""
    id: str
    user_id: str  # Who should provide the document
    requested_by: str  # Who is requesting
    firm_id: Optional[str] = None
    tax_return_id: Optional[str] = None

    category: DocumentCategory
    description: str
    required: bool = True
    due_date: Optional[datetime] = None

    status: str  # pending, uploaded, expired
    document_id: Optional[str] = None  # Linked document when uploaded

    created_at: datetime
    updated_at: datetime


class CreateDocumentRequestInput(BaseModel):
    """Input for creating a document request."""
    user_id: str
    category: DocumentCategory
    description: str
    required: bool = True
    due_date: Optional[datetime] = None
    tax_return_id: Optional[str] = None


class UploadDocumentRequest(BaseModel):
    """Metadata for document upload."""
    category: DocumentCategory
    description: Optional[str] = None
    tax_year: Optional[int] = None
    tax_return_id: Optional[str] = None
    request_id: Optional[str] = None  # If fulfilling a document request


# =============================================================================
# DATABASE HELPER FUNCTIONS
# =============================================================================

def _parse_dt(val) -> Optional[datetime]:
    """Parse datetime from database value."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _category_to_db(category: DocumentCategory) -> str:
    """Map API category to database document_type."""
    mapping = {
        DocumentCategory.TAX_FORM: "unknown",
        DocumentCategory.W2: "w2",
        DocumentCategory.FORM_1099: "1099-int",
        DocumentCategory.RECEIPT: "unknown",
        DocumentCategory.BANK_STATEMENT: "unknown",
        DocumentCategory.INVESTMENT: "1099-b",
        DocumentCategory.PROPERTY: "1098",
        DocumentCategory.MEDICAL: "unknown",
        DocumentCategory.CHARITABLE: "unknown",
        DocumentCategory.BUSINESS: "unknown",
        DocumentCategory.IDENTITY: "unknown",
        DocumentCategory.OTHER: "unknown",
    }
    return mapping.get(category, "unknown")


def _db_type_to_category(db_type: str) -> DocumentCategory:
    """Map database document_type to API category."""
    mapping = {
        "w2": DocumentCategory.W2,
        "1099-int": DocumentCategory.FORM_1099,
        "1099-div": DocumentCategory.FORM_1099,
        "1099-misc": DocumentCategory.FORM_1099,
        "1099-nec": DocumentCategory.FORM_1099,
        "1099-b": DocumentCategory.INVESTMENT,
        "1099-r": DocumentCategory.FORM_1099,
        "1099-g": DocumentCategory.FORM_1099,
        "1098": DocumentCategory.PROPERTY,
        "1098-e": DocumentCategory.OTHER,
        "1098-t": DocumentCategory.OTHER,
        "k1": DocumentCategory.BUSINESS,
        "1095-a": DocumentCategory.MEDICAL,
        "1095-b": DocumentCategory.MEDICAL,
        "1095-c": DocumentCategory.MEDICAL,
    }
    return mapping.get(db_type, DocumentCategory.OTHER)


def _status_to_db(status: DocumentStatus) -> str:
    """Map API status to database status."""
    mapping = {
        DocumentStatus.PENDING: "processing",
        DocumentStatus.UPLOADED: "uploaded",
        DocumentStatus.VERIFIED: "verified",
        DocumentStatus.REJECTED: "rejected",
        DocumentStatus.EXPIRED: "failed",
    }
    return mapping.get(status, "uploaded")


def _db_status_to_api(db_status: str) -> DocumentStatus:
    """Map database status to API status."""
    mapping = {
        "uploaded": DocumentStatus.UPLOADED,
        "processing": DocumentStatus.PENDING,
        "ocr_complete": DocumentStatus.PENDING,
        "extraction_complete": DocumentStatus.PENDING,
        "verified": DocumentStatus.VERIFIED,
        "applied": DocumentStatus.VERIFIED,
        "failed": DocumentStatus.REJECTED,
        "rejected": DocumentStatus.REJECTED,
    }
    return mapping.get(db_status, DocumentStatus.UPLOADED)


def _row_to_document(row) -> Document:
    """Convert database row to Document model."""
    # Row order: document_id, return_id, taxpayer_id, document_type, tax_year, status,
    #            original_filename, file_size_bytes, mime_type, storage_path, thumbnail_path,
    #            created_at, updated_at, uploaded_by, user_verified, additional_data
    additional_data = json.loads(row[15]) if row[15] else {}

    return Document(
        id=str(row[0]),
        user_id=str(row[2]) if row[2] else additional_data.get("user_id", ""),
        firm_id=additional_data.get("firm_id"),
        tax_return_id=str(row[1]) if row[1] else None,
        filename=row[6] or "document.pdf",
        original_filename=row[6] or "document.pdf",
        file_size=row[7] or 0,
        mime_type=row[8] or "application/pdf",
        category=_db_type_to_category(row[3]),
        status=_db_status_to_api(row[5]),
        description=additional_data.get("description"),
        tax_year=row[4],
        notes=additional_data.get("notes"),
        uploaded_by=str(row[13]) if row[13] else additional_data.get("uploaded_by", ""),
        uploaded_at=_parse_dt(row[11]) or datetime.utcnow(),
        verified_by=additional_data.get("verified_by"),
        verified_at=_parse_dt(additional_data.get("verified_at")),
        storage_path=row[9] or "",
        thumbnail_path=row[10],
    )


async def _build_access_conditions(context: UserContext) -> tuple:
    """Build SQL conditions for role-based document access."""
    conditions = []
    params = {}

    if context.user_type == UserType.PLATFORM_ADMIN:
        conditions.append("1=1")
    elif context.user_type == UserType.CPA_TEAM:
        # CPA team sees documents for their firm
        conditions.append(
            "(d.additional_data->>'firm_id' = :firm_id OR d.taxpayer_id IN "
            "(SELECT client_id FROM clients WHERE preparer_id IN "
            "(SELECT user_id FROM users WHERE firm_id = :firm_id)))"
        )
        params["firm_id"] = context.firm_id
    else:
        # Consumers see only their own documents
        conditions.append("(d.taxpayer_id = :user_id OR d.uploaded_by = :user_id)")
        params["user_id"] = context.user_id

    return " AND ".join(conditions) if conditions else "1=1", params


def _can_access_document_data(context: UserContext, user_id: str, firm_id: Optional[str]) -> bool:
    """Check if user can access a document based on data."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    if user_id == context.user_id:
        return True

    if context.user_type == UserType.CPA_TEAM:
        if firm_id == context.firm_id:
            return True

    return False


def _can_modify_document_data(context: UserContext, user_id: str, firm_id: Optional[str], status: DocumentStatus) -> bool:
    """Check if user can modify a document."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    if user_id == context.user_id:
        return status != DocumentStatus.VERIFIED

    if context.user_type == UserType.CPA_TEAM:
        if firm_id == context.firm_id:
            return True

    return False


# =============================================================================
# DOCUMENT REQUESTS TABLE HELPERS
# =============================================================================

# Document requests are stored in a separate table that may not exist yet
# We'll create document_requests table queries here

async def _get_document_request(session: AsyncSession, request_id: str) -> Optional[dict]:
    """Get a document request by ID."""
    query = text("""
        SELECT dr.request_id, dr.user_id, dr.requested_by, dr.firm_id, dr.return_id,
               dr.category, dr.description, dr.required, dr.due_date, dr.status,
               dr.document_id, dr.created_at, dr.updated_at
        FROM document_requests dr
        WHERE dr.request_id = :request_id
    """)
    try:
        result = await session.execute(query, {"request_id": request_id})
        row = result.fetchone()
        if row:
            return {
                "id": str(row[0]),
                "user_id": str(row[1]) if row[1] else "",
                "requested_by": str(row[2]) if row[2] else "",
                "firm_id": str(row[3]) if row[3] else None,
                "tax_return_id": str(row[4]) if row[4] else None,
                "category": row[5],
                "description": row[6],
                "required": row[7],
                "due_date": _parse_dt(row[8]),
                "status": row[9],
                "document_id": str(row[10]) if row[10] else None,
                "created_at": _parse_dt(row[11]) or datetime.utcnow(),
                "updated_at": _parse_dt(row[12]) or datetime.utcnow(),
            }
    except (ProgrammingError, OperationalError) as e:
        # Table may not exist yet
        logger.debug(f"document_requests table query failed (may not exist): {e}")
    except SQLAlchemyError as e:
        logger.warning(f"Database error fetching document request {request_id}: {e}")
    return None


# =============================================================================
# LIST & SEARCH ENDPOINTS
# =============================================================================

@router.get("", response_model=List[DocumentSummary])
async def list_documents(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    category: Optional[DocumentCategory] = None,
    status_filter: Optional[DocumentStatus] = Query(None, alias="status"),
    tax_year: Optional[int] = None,
    user_id: Optional[str] = None,
    tax_return_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """
    List documents with role-based filtering.

    Access control:
    - Consumers/CPA Clients: See only their own documents
    - CPA Team: See documents in their firm
    - Platform Admins: See all documents
    """
    # Build access conditions
    access_where, params = await _build_access_conditions(context)
    conditions = [access_where]

    # Apply filters
    if category:
        conditions.append("d.document_type = :category")
        params["category"] = _category_to_db(category)

    if status_filter:
        conditions.append("d.status = :status")
        params["status"] = _status_to_db(status_filter)

    if tax_year:
        conditions.append("d.tax_year = :tax_year")
        params["tax_year"] = tax_year

    if user_id:
        conditions.append("(d.taxpayer_id = :filter_user_id OR d.uploaded_by = :filter_user_id)")
        params["filter_user_id"] = user_id

    if tax_return_id:
        conditions.append("d.return_id = :return_id")
        params["return_id"] = tax_return_id

    where_clause = " AND ".join(conditions)
    params["limit"] = limit
    params["offset"] = offset

    query = text(f"""
        SELECT d.document_id, d.return_id, d.taxpayer_id, d.document_type, d.tax_year, d.status,
               d.original_filename, d.file_size_bytes, d.mime_type, d.storage_path, d.thumbnail_path,
               d.created_at, d.updated_at, d.uploaded_by, d.user_verified, d.additional_data
        FROM documents d
        WHERE {where_clause}
        ORDER BY d.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    results = []
    for row in rows:
        additional_data = json.loads(row[15]) if row[15] else {}
        results.append(DocumentSummary(
            id=str(row[0]),
            filename=row[6] or "document.pdf",
            category=_db_type_to_category(row[3]),
            status=_db_status_to_api(row[5]),
            file_size=row[7] or 0,
            uploaded_at=_parse_dt(row[11]) or datetime.utcnow(),
            tax_year=row[4]
        ))

    return results


@router.get("/my")
async def get_my_documents(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    category: Optional[DocumentCategory] = None,
    tax_year: Optional[int] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """Get current user's documents."""
    return await list_documents(
        context=context,
        session=session,
        user_id=context.user_id,
        category=category,
        tax_year=tax_year,
        limit=limit,
        offset=offset
    )


# =============================================================================
# CRUD ENDPOINTS
# =============================================================================

@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get a specific document."""
    query = text("""
        SELECT d.document_id, d.return_id, d.taxpayer_id, d.document_type, d.tax_year, d.status,
               d.original_filename, d.file_size_bytes, d.mime_type, d.storage_path, d.thumbnail_path,
               d.created_at, d.updated_at, d.uploaded_by, d.user_verified, d.additional_data
        FROM documents d
        WHERE d.document_id = :document_id
    """)

    result = await session.execute(query, {"document_id": document_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    additional_data = json.loads(row[15]) if row[15] else {}
    user_id = str(row[2]) if row[2] else additional_data.get("user_id", "")
    firm_id = additional_data.get("firm_id")

    if not _can_access_document_data(context, user_id, firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this document"
        )

    return _row_to_document(row)


@router.post("", response_model=Document)
async def upload_document(
    metadata: UploadDocumentRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Upload a document.

    Note: In production, this would handle actual file upload.
    For now, it creates a document record with metadata.
    """
    now = datetime.utcnow()
    document_id = str(uuid4())
    filename = f"doc_{uuid4().hex[:8]}.pdf"
    storage_path = f"/documents/{context.user_id}/{uuid4().hex}.pdf"

    additional_data = {
        "user_id": context.user_id,
        "firm_id": context.firm_id,
        "description": metadata.description,
        "uploaded_by": context.user_id,
    }

    # Insert into database
    query = text("""
        INSERT INTO documents (
            document_id, return_id, taxpayer_id, document_type, tax_year, status,
            original_filename, file_size_bytes, mime_type, storage_path,
            created_at, updated_at, uploaded_by, additional_data
        ) VALUES (
            :document_id, :return_id, :taxpayer_id, :document_type, :tax_year, :status,
            :original_filename, :file_size_bytes, :mime_type, :storage_path,
            :created_at, :updated_at, :uploaded_by, :additional_data
        )
    """)

    await session.execute(query, {
        "document_id": document_id,
        "return_id": metadata.tax_return_id,
        "taxpayer_id": context.user_id,
        "document_type": _category_to_db(metadata.category),
        "tax_year": metadata.tax_year or 2024,
        "status": "uploaded",
        "original_filename": filename,
        "file_size_bytes": 100000,
        "mime_type": "application/pdf",
        "storage_path": storage_path,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "uploaded_by": context.user_id,
        "additional_data": json.dumps(additional_data),
    })

    # If fulfilling a document request, update it
    if metadata.request_id:
        doc_request = await _get_document_request(session, metadata.request_id)
        if doc_request and doc_request["user_id"] == context.user_id:
            update_query = text("""
                UPDATE document_requests SET
                    status = 'uploaded',
                    document_id = :document_id,
                    updated_at = :updated_at
                WHERE request_id = :request_id
            """)
            try:
                await session.execute(update_query, {
                    "request_id": metadata.request_id,
                    "document_id": document_id,
                    "updated_at": now.isoformat(),
                })
            except (ProgrammingError, OperationalError) as e:
                logger.debug(f"Could not update document_requests (table may not exist): {e}")
            except SQLAlchemyError as e:
                logger.warning(f"Failed to update document request {metadata.request_id}: {e}")

    await session.commit()

    document = Document(
        id=document_id,
        user_id=context.user_id,
        firm_id=context.firm_id,
        tax_return_id=metadata.tax_return_id,
        filename=filename,
        original_filename=filename,
        file_size=100000,
        mime_type="application/pdf",
        category=metadata.category,
        status=DocumentStatus.UPLOADED,
        description=metadata.description,
        tax_year=metadata.tax_year,
        uploaded_by=context.user_id,
        uploaded_at=now,
        storage_path=storage_path
    )

    logger.info(f"Document uploaded: {document_id} by {context.user_id}")

    return document


@router.patch("/{document_id}", response_model=Document)
async def update_document(
    document_id: str,
    category: Optional[DocumentCategory] = None,
    description: Optional[str] = None,
    tax_year: Optional[int] = None,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Update document metadata."""
    # Fetch existing document
    query = text("""
        SELECT d.document_id, d.return_id, d.taxpayer_id, d.document_type, d.tax_year, d.status,
               d.original_filename, d.file_size_bytes, d.mime_type, d.storage_path, d.thumbnail_path,
               d.created_at, d.updated_at, d.uploaded_by, d.user_verified, d.additional_data
        FROM documents d
        WHERE d.document_id = :document_id
    """)

    result = await session.execute(query, {"document_id": document_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    additional_data = json.loads(row[15]) if row[15] else {}
    user_id = str(row[2]) if row[2] else additional_data.get("user_id", "")
    firm_id = additional_data.get("firm_id")
    doc_status = _db_status_to_api(row[5])

    if not _can_modify_document_data(context, user_id, firm_id, doc_status):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this document"
        )

    # Build update query
    updates = []
    params = {"document_id": document_id}

    if category:
        updates.append("document_type = :document_type")
        params["document_type"] = _category_to_db(category)
        additional_data["category"] = category.value

    if description is not None:
        additional_data["description"] = description

    if tax_year:
        updates.append("tax_year = :tax_year")
        params["tax_year"] = tax_year

    updates.append("additional_data = :additional_data")
    params["additional_data"] = json.dumps(additional_data)
    updates.append("updated_at = :updated_at")
    params["updated_at"] = datetime.utcnow().isoformat()

    update_query = text(f"UPDATE documents SET {', '.join(updates)} WHERE document_id = :document_id")
    await session.execute(update_query, params)
    await session.commit()

    # Fetch updated document
    result = await session.execute(query, {"document_id": document_id})
    row = result.fetchone()

    logger.info(f"Document updated: {document_id} by {context.user_id}")

    return _row_to_document(row)


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a document."""
    # Fetch existing document
    query = text("""
        SELECT d.document_id, d.taxpayer_id, d.status, d.additional_data
        FROM documents d
        WHERE d.document_id = :document_id
    """)

    result = await session.execute(query, {"document_id": document_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    additional_data = json.loads(row[3]) if row[3] else {}
    user_id = str(row[1]) if row[1] else additional_data.get("user_id", "")
    firm_id = additional_data.get("firm_id")
    doc_status = _db_status_to_api(row[2])

    if not _can_modify_document_data(context, user_id, firm_id, doc_status):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete this document"
        )

    delete_query = text("DELETE FROM documents WHERE document_id = :document_id")
    await session.execute(delete_query, {"document_id": document_id})
    await session.commit()

    logger.info(f"Document deleted: {document_id} by {context.user_id}")

    return {"success": True, "message": "Document deleted"}


# =============================================================================
# VERIFICATION ENDPOINTS (CPA/Admin only)
# =============================================================================

@router.post("/{document_id}/verify")
async def verify_document(
    document_id: str,
    notes: Optional[str] = None,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Verify a document.

    Only CPA team and platform admins can verify documents.
    """
    if context.user_type not in [UserType.CPA_TEAM, UserType.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CPA team or admins can verify documents"
        )

    # Fetch document
    query = text("""
        SELECT d.document_id, d.taxpayer_id, d.additional_data
        FROM documents d
        WHERE d.document_id = :document_id
    """)

    result = await session.execute(query, {"document_id": document_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    additional_data = json.loads(row[2]) if row[2] else {}
    user_id = str(row[1]) if row[1] else additional_data.get("user_id", "")
    firm_id = additional_data.get("firm_id")

    if not _can_access_document_data(context, user_id, firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    now = datetime.utcnow()
    additional_data["verified_by"] = context.user_id
    additional_data["verified_at"] = now.isoformat()
    if notes:
        additional_data["notes"] = notes

    update_query = text("""
        UPDATE documents SET
            status = :status,
            user_verified = true,
            additional_data = :additional_data,
            updated_at = :updated_at
        WHERE document_id = :document_id
    """)

    await session.execute(update_query, {
        "document_id": document_id,
        "status": "verified",
        "additional_data": json.dumps(additional_data),
        "updated_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"Document verified: {document_id} by {context.user_id}")

    return {"success": True, "message": "Document verified"}


@router.post("/{document_id}/reject")
async def reject_document(
    document_id: str,
    reason: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Reject a document.

    Only CPA team and platform admins can reject documents.
    """
    if context.user_type not in [UserType.CPA_TEAM, UserType.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CPA team or admins can reject documents"
        )

    # Fetch document
    query = text("""
        SELECT d.document_id, d.taxpayer_id, d.additional_data
        FROM documents d
        WHERE d.document_id = :document_id
    """)

    result = await session.execute(query, {"document_id": document_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    additional_data = json.loads(row[2]) if row[2] else {}
    user_id = str(row[1]) if row[1] else additional_data.get("user_id", "")
    firm_id = additional_data.get("firm_id")

    if not _can_access_document_data(context, user_id, firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    now = datetime.utcnow()
    additional_data["notes"] = reason
    additional_data["rejected_by"] = context.user_id
    additional_data["rejected_at"] = now.isoformat()

    update_query = text("""
        UPDATE documents SET
            status = :status,
            additional_data = :additional_data,
            updated_at = :updated_at
        WHERE document_id = :document_id
    """)

    await session.execute(update_query, {
        "document_id": document_id,
        "status": "rejected",
        "additional_data": json.dumps(additional_data),
        "updated_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"Document rejected: {document_id} by {context.user_id}")

    return {"success": True, "message": "Document rejected", "reason": reason}


# =============================================================================
# DOCUMENT REQUESTS
# =============================================================================

@router.get("/requests/pending", response_model=List[DocumentRequest])
async def get_pending_document_requests(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get pending document requests for the current user.

    - Users see requests made to them
    - CPAs see requests they made
    """
    # Build access conditions
    conditions = ["dr.status = 'pending'"]
    params = {}

    if context.user_type == UserType.PLATFORM_ADMIN:
        pass  # No additional filter
    elif context.user_type == UserType.CPA_TEAM:
        conditions.append(
            "(dr.user_id = :user_id OR dr.requested_by = :user_id OR dr.firm_id = :firm_id)"
        )
        params["user_id"] = context.user_id
        params["firm_id"] = context.firm_id
    else:
        conditions.append("dr.user_id = :user_id")
        params["user_id"] = context.user_id

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT dr.request_id, dr.user_id, dr.requested_by, dr.firm_id, dr.return_id,
               dr.category, dr.description, dr.required, dr.due_date, dr.status,
               dr.document_id, dr.created_at, dr.updated_at
        FROM document_requests dr
        WHERE {where_clause}
        ORDER BY COALESCE(dr.due_date, dr.created_at) ASC
    """)

    try:
        result = await session.execute(query, params)
        rows = result.fetchall()

        results = []
        for row in rows:
            results.append(DocumentRequest(
                id=str(row[0]),
                user_id=str(row[1]) if row[1] else "",
                requested_by=str(row[2]) if row[2] else "",
                firm_id=str(row[3]) if row[3] else None,
                tax_return_id=str(row[4]) if row[4] else None,
                category=DocumentCategory(row[5]) if row[5] else DocumentCategory.OTHER,
                description=row[6] or "",
                required=row[7] if row[7] is not None else True,
                due_date=_parse_dt(row[8]),
                status=row[9] or "pending",
                document_id=str(row[10]) if row[10] else None,
                created_at=_parse_dt(row[11]) or datetime.utcnow(),
                updated_at=_parse_dt(row[12]) or datetime.utcnow(),
            ))
        return results
    except (ProgrammingError, OperationalError) as e:
        # Table may not exist, return empty list
        logger.debug(f"document_requests table not available: {e}")
        return []
    except SQLAlchemyError as e:
        logger.warning(f"Database error listing document requests: {e}")
        return []


@router.post("/requests", response_model=DocumentRequest)
async def create_document_request(
    request: CreateDocumentRequestInput,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Create a document request.

    Only CPA team and platform admins can request documents.
    """
    if context.user_type not in [UserType.CPA_TEAM, UserType.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CPA team or admins can request documents"
        )

    now = datetime.utcnow()
    request_id = str(uuid4())

    doc_request = DocumentRequest(
        id=request_id,
        user_id=request.user_id,
        requested_by=context.user_id,
        firm_id=context.firm_id,
        tax_return_id=request.tax_return_id,
        category=request.category,
        description=request.description,
        required=request.required,
        due_date=request.due_date,
        status="pending",
        created_at=now,
        updated_at=now
    )

    # Insert into database
    query = text("""
        INSERT INTO document_requests (
            request_id, user_id, requested_by, firm_id, return_id,
            category, description, required, due_date, status,
            created_at, updated_at
        ) VALUES (
            :request_id, :user_id, :requested_by, :firm_id, :return_id,
            :category, :description, :required, :due_date, :status,
            :created_at, :updated_at
        )
    """)

    try:
        await session.execute(query, {
            "request_id": request_id,
            "user_id": request.user_id,
            "requested_by": context.user_id,
            "firm_id": context.firm_id,
            "return_id": request.tax_return_id,
            "category": request.category.value,
            "description": request.description,
            "required": request.required,
            "due_date": request.due_date.isoformat() if request.due_date else None,
            "status": "pending",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })
        await session.commit()
    except Exception as e:
        logger.warning(f"Could not insert document request (table may not exist): {e}")
        # Table may not exist, but we still return the request object

    logger.info(f"Document request created: {request_id} for {request.user_id}")

    return doc_request


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/summary")
async def get_document_analytics(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    tax_year: Optional[int] = None
):
    """Get document analytics with role-based filtering."""
    # Build access conditions
    access_where, params = await _build_access_conditions(context)
    conditions = [access_where]

    if tax_year:
        conditions.append("d.tax_year = :tax_year")
        params["tax_year"] = tax_year

    where_clause = " AND ".join(conditions)

    # Get document counts by category and status
    query = text(f"""
        SELECT d.document_type, d.status, COUNT(*) as count,
               COALESCE(SUM(d.file_size_bytes), 0) as total_size
        FROM documents d
        WHERE {where_clause}
        GROUP BY d.document_type, d.status
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    by_category = {}
    by_status = {}
    total_size = 0
    total_documents = 0

    for row in rows:
        doc_type = row[0]
        doc_status = row[1]
        count = row[2]
        size = row[3] or 0

        # Map to API category
        category = _db_type_to_category(doc_type)
        by_category[category.value] = by_category.get(category.value, 0) + count

        # Map to API status
        api_status = _db_status_to_api(doc_status)
        by_status[api_status.value] = by_status.get(api_status.value, 0) + count

        total_size += size
        total_documents += count

    # Count pending requests
    pending_requests = 0
    try:
        req_conditions = ["dr.status = 'pending'"]
        req_params = {}

        if context.user_type == UserType.PLATFORM_ADMIN:
            pass  # No additional filter
        elif context.user_type == UserType.CPA_TEAM:
            req_conditions.append(
                "(dr.user_id = :user_id OR dr.requested_by = :user_id OR dr.firm_id = :firm_id)"
            )
            req_params["user_id"] = context.user_id
            req_params["firm_id"] = context.firm_id
        else:
            req_conditions.append("dr.user_id = :user_id")
            req_params["user_id"] = context.user_id

        req_where = " AND ".join(req_conditions)
        req_query = text(f"SELECT COUNT(*) FROM document_requests dr WHERE {req_where}")
        req_result = await session.execute(req_query, req_params)
        pending_requests = req_result.scalar() or 0
    except (ProgrammingError, OperationalError) as e:
        # Table may not exist
        logger.debug(f"document_requests table not available for stats: {e}")
    except SQLAlchemyError as e:
        logger.warning(f"Database error counting pending requests: {e}")

    return {
        "total_documents": total_documents,
        "by_category": by_category,
        "by_status": by_status,
        "total_size_bytes": total_size,
        "pending_requests": pending_requests
    }
