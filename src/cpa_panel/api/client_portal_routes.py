"""
Client Portal Routes - B2C Client Dashboard API

Endpoints for authenticated clients to:
- View their tax returns and status
- Upload/download documents
- Send/receive messages with their CPA
- View invoices and make payments
- Access their dashboard data

All endpoints require client authentication via JWT token.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from uuid import uuid4
import json
import jwt as pyjwt

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, Header
from pydantic import BaseModel, Field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from database.connection import get_async_session
except ImportError:
    async def _mock_session():
        yield None
    get_async_session = _mock_session

import logging

logger = logging.getLogger(__name__)

try:
    from rbac.jwt import decode_token_safe, get_jwt_secret, JWT_ALGORITHM
except Exception:  # pragma: no cover - guarded for deployments without RBAC package wiring
    decode_token_safe = None
    get_jwt_secret = None
    JWT_ALGORITHM = "HS256"

# =============================================================================
# LEGACY CLIENT TOKEN STORAGE (backward compatibility only)
# =============================================================================

_client_tokens: dict = {}  # token -> {client_id, email, expires_at}

router = APIRouter(prefix="/client", tags=["Client Portal"])


# =============================================================================
# CLIENT AUTHENTICATION - Login / Magic Link
# =============================================================================

class ClientLoginRequest(BaseModel):
    """Client login request."""
    email: str = Field(..., description="Client email address")


class ClientLoginResponse(BaseModel):
    """Client login response."""
    success: bool
    message: str
    token: Optional[str] = None


@router.post("/login", response_model=ClientLoginResponse)
async def client_login(
    request: ClientLoginRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Client login via magic link.

    1. Verifies the email exists in the client database
    2. Generates a secure token
    3. In production, would send magic link email

    Returns a token for immediate access (demo mode).
    """
    if not request.email or "@" not in request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address"
        )

    email_lower = request.email.lower()

    # Check if client exists in database
    query = text("""
        SELECT c.client_id, c.first_name, c.last_name, c.email, c.preparer_id, c.is_active
        FROM clients c
        WHERE LOWER(c.email) = :email
        LIMIT 1
    """)
    result = await session.execute(query, {"email": email_lower})
    client_row = result.fetchone()

    if not client_row:
        # For security, don't reveal if email exists or not
        # In production, still return success but don't send email
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address"
        )

    if not client_row[5]:  # is_active
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact your CPA."
        )

    if get_jwt_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )

    # Generate signed JWT token for client portal session.
    expires_at = datetime.utcnow() + timedelta(hours=24)
    issued_at = datetime.utcnow()
    payload = {
        "sub": str(client_row[0]),
        "client_id": str(client_row[0]),
        "email": client_row[3],
        "name": f"{client_row[1]} {client_row[2]}".strip(),
        "user_type": "client",
        "role": "firm_client",
        "type": "client_portal",
        "preparer_id": str(client_row[4]) if client_row[4] else None,
        "iat": issued_at,
        "exp": expires_at,
    }
    client_token = pyjwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

    logger.info(f"Client login: {email_lower}")

    return {
        "success": True,
        "message": "Login successful. In production, a magic link would be sent to your email.",
        "token": client_token
    }


@router.post("/verify-token")
async def verify_client_token(
    token: str = Query(...),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Verify a client token is valid.

    Returns client info if token is valid.
    """
    _ = session  # Session kept for compatibility and future DB-backed checks.

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    payload = decode_token_safe(token) if decode_token_safe else None
    if payload and payload.get("type") in {"client_portal", "access"}:
        return {
            "valid": True,
            "client_id": str(payload.get("client_id") or payload.get("sub") or ""),
            "name": payload.get("name", "Client"),
            "email": payload.get("email", ""),
        }

    # Legacy compatibility path for old in-memory tokens.
    token_data = _client_tokens.get(token)
    if token_data:
        if datetime.utcnow() > token_data["expires_at"]:
            del _client_tokens[token]
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        return {
            "valid": True,
            "client_id": token_data["client_id"],
            "name": f"{token_data['first_name']} {token_data['last_name']}",
            "email": token_data["email"]
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token"
    )


# =============================================================================
# CLIENT AUTHENTICATION
# =============================================================================

class ClientContext(BaseModel):
    """Authenticated client context."""
    client_id: str
    name: str
    email: str
    firm_id: Optional[str] = None
    cpa_id: Optional[str] = None


async def get_current_client(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_async_session)
) -> ClientContext:
    """
    Get current authenticated client from token.
    Validates the token and extracts client info from database.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )

    # Extract token from Bearer header
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    client_id = None
    payload = decode_token_safe(token) if decode_token_safe else None
    if payload and payload.get("type") in {"client_portal", "access"}:
        role = str(payload.get("role", "")).lower()
        user_type = str(payload.get("user_type", "")).lower()
        if role not in {"firm_client", "direct_client"} and user_type not in {"client", "firm_client", "cpa_client"}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is not valid for client portal"
            )
        client_id = str(payload.get("client_id") or payload.get("sub") or "")

    # Legacy compatibility path for old in-memory tokens.
    if client_id is None:
        token_data = _client_tokens.get(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        if datetime.utcnow() > token_data["expires_at"]:
            del _client_tokens[token]
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        client_id = token_data["client_id"]

    # Get full client info from database
    query = text("""
        SELECT c.client_id, c.first_name, c.last_name, c.email,
               c.preparer_id, u.firm_id
        FROM clients c
        LEFT JOIN users u ON c.preparer_id = u.user_id
        WHERE c.client_id = :client_id
    """)
    result = await session.execute(query, {"client_id": client_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client not found"
        )

    return ClientContext(
        client_id=str(row[0]),
        name=f"{row[1]} {row[2]}",
        email=row[3],
        firm_id=str(row[5]) if row[5] else None,
        cpa_id=str(row[4]) if row[4] else None
    )


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class CPAInfo(BaseModel):
    """CPA information for client display."""
    id: str
    name: str
    email: str
    phone: str


class ReturnInfo(BaseModel):
    """Tax return information."""
    id: str
    tax_year: int
    return_type: str
    status: str
    status_label: str
    refund_amount: Optional[float]
    updated_at: str


class DocumentRequest(BaseModel):
    """Document request from CPA."""
    id: str
    name: str
    description: str
    urgent: bool = False
    fulfilled: bool = False
    requested_at: str


class UploadedDocument(BaseModel):
    """Uploaded document info."""
    id: str
    filename: str
    size: int
    uploaded_at: str
    status: str
    status_label: str


class Message(BaseModel):
    """Chat message."""
    id: str
    content: str
    sender_type: str  # 'client' or 'cpa'
    created_at: str
    read: bool = False


class Invoice(BaseModel):
    """Invoice information."""
    id: str
    date: str
    due_date: str
    description: str
    amount: float
    status: str  # 'pending' or 'paid'


class DashboardResponse(BaseModel):
    """Full dashboard data response."""
    client_id: str
    name: str
    cpa: CPAInfo
    returns: List[ReturnInfo]
    current_return: Optional[ReturnInfo]
    document_requests: List[DocumentRequest]
    uploaded_documents: List[UploadedDocument]
    messages: List[Message]
    invoices: List[Invoice]
    balance: float
    unread_messages: int


# =============================================================================
# DASHBOARD ENDPOINT
# =============================================================================

@router.get("/dashboard", response_model=DashboardResponse)
async def get_client_dashboard(
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get all dashboard data for the authenticated client.

    Returns:
    - Client info
    - CPA info
    - Active and past returns
    - Document requests
    - Messages
    - Billing info
    """
    # Get CPA info
    cpa_info = {"id": "", "name": "Unassigned", "email": "", "phone": ""}
    if client.cpa_id:
        cpa_query = text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.phone, f.name as firm_name
            FROM users u
            LEFT JOIN firms f ON u.firm_id = f.firm_id
            WHERE u.user_id = :cpa_id
        """)
        cpa_result = await session.execute(cpa_query, {"cpa_id": client.cpa_id})
        cpa_row = cpa_result.fetchone()
        if cpa_row:
            cpa_info = {
                "id": str(cpa_row[0]),
                "name": f"{cpa_row[1]} {cpa_row[2]}, CPA",
                "email": cpa_row[3] or "",
                "phone": cpa_row[4] or ""
            }

    # Get tax returns for this client
    returns_query = text("""
        SELECT tr.return_id, tr.tax_year, tr.filing_status, tr.status,
               tr.line_35a_refund, tr.line_37_amount_owed, tr.updated_at
        FROM tax_returns tr
        JOIN taxpayers tp ON tr.return_id = tp.return_id
        JOIN clients c ON tp.email = c.email
        WHERE c.client_id = :client_id
        ORDER BY tr.tax_year DESC
        LIMIT 10
    """)
    returns_result = await session.execute(returns_query, {"client_id": client.client_id})
    returns_rows = returns_result.fetchall()

    status_labels = {
        "draft": "Draft", "in_progress": "In Progress", "pending_review": "Pending Review",
        "reviewed": "Reviewed", "ready_to_file": "Ready to File", "filed": "Filed",
        "accepted": "Accepted", "rejected": "Rejected", "amended": "Amended"
    }

    returns = []
    current_return = None
    for row in returns_rows:
        refund = float(row[4]) if row[4] and float(row[4]) > 0 else None
        return_info = {
            "id": str(row[0]),
            "tax_year": row[1],
            "return_type": "1040 Individual",
            "status": row[3] or "draft",
            "status_label": status_labels.get(row[3], "Draft"),
            "refund_amount": refund,
            "updated_at": row[6].isoformat() if row[6] else datetime.utcnow().isoformat()
        }
        returns.append(return_info)
        if current_return is None and row[3] not in ["filed", "accepted"]:
            current_return = return_info

    if not current_return and returns:
        current_return = returns[0]

    # Get document requests (from document_requests table if exists, or documents with pending status)
    doc_requests_query = text("""
        SELECT document_id, document_type, original_filename, status, created_at
        FROM documents
        WHERE taxpayer_id IN (
            SELECT tp.taxpayer_id FROM taxpayers tp
            JOIN clients c ON tp.email = c.email
            WHERE c.client_id = :client_id
        )
        AND status IN ('uploaded', 'processing')
        ORDER BY created_at DESC
        LIMIT 10
    """)
    doc_requests_result = await session.execute(doc_requests_query, {"client_id": client.client_id})
    doc_rows = doc_requests_result.fetchall()

    # Simulated document requests (in production, use a dedicated document_requests table)
    document_requests = []  # Would be populated from document_requests table

    uploaded_documents = []
    for row in doc_rows:
        uploaded_documents.append({
            "id": str(row[0]),
            "filename": row[2] or "Unknown",
            "size": 0,
            "uploaded_at": row[4].isoformat() if row[4] else datetime.utcnow().isoformat(),
            "status": row[3] or "uploaded",
            "status_label": {"uploaded": "Received", "processing": "Processing", "verified": "Verified"}.get(row[3], "Received")
        })

    # Get messages from conversations table
    messages = []
    unread_count = 0
    messages_query = text("""
        SELECT m.message_id, m.content, m.sender_id, m.created_at, m.read_at,
               CASE WHEN m.sender_id = :client_id THEN 'client' ELSE 'cpa' END as sender_type
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.conversation_id
        WHERE c.participants @> :participant::jsonb
        ORDER BY m.created_at DESC
        LIMIT 20
    """)
    try:
        messages_result = await session.execute(messages_query, {
            "client_id": client.client_id,
            "participant": json.dumps({"id": client.client_id})
        })
        messages_rows = messages_result.fetchall()
        for row in messages_rows:
            is_read = row[4] is not None
            if not is_read and row[5] == "cpa":
                unread_count += 1
            messages.append({
                "id": str(row[0]),
                "content": row[1],
                "sender_type": row[5],
                "created_at": row[3].isoformat() if row[3] else datetime.utcnow().isoformat(),
                "read": is_read
            })
    except Exception as e:
        # Messages table might not exist yet - log but don't fail
        logger.debug(f"Could not fetch messages for client {client.client_id}: {e}")

    # Get invoices
    invoices = []
    balance = 0.0
    invoices_query = text("""
        SELECT i.invoice_id, i.created_at, i.due_date, i.line_items, i.amount_due, i.status
        FROM invoices i
        WHERE i.firm_id = :firm_id
        ORDER BY i.created_at DESC
        LIMIT 10
    """)
    try:
        if client.firm_id:
            invoices_result = await session.execute(invoices_query, {"firm_id": client.firm_id})
            invoices_rows = invoices_result.fetchall()
            for row in invoices_rows:
                line_items = row[3] if row[3] else []
                if isinstance(line_items, str):
                    line_items = json.loads(line_items)
                description = line_items[0].get("description", "Tax Services") if line_items else "Tax Services"
                amount = float(row[4]) if row[4] else 0.0
                inv_status = row[5] or "pending"
                if inv_status == "pending":
                    balance += amount
                invoices.append({
                    "id": str(row[0]),
                    "date": row[1].isoformat() if row[1] else datetime.utcnow().isoformat(),
                    "due_date": row[2].isoformat() if row[2] else (datetime.utcnow() + timedelta(days=30)).isoformat(),
                    "description": description,
                    "amount": amount,
                    "status": "paid" if inv_status == "paid" else "pending"
                })
    except Exception as e:
        # Invoices table might not exist - log but don't fail
        logger.debug(f"Could not fetch invoices for client {client.client_id}: {e}")

    return {
        "client_id": client.client_id,
        "name": client.name,
        "cpa": cpa_info,
        "returns": returns,
        "current_return": current_return,
        "document_requests": document_requests,
        "uploaded_documents": uploaded_documents,
        "messages": messages,
        "invoices": invoices,
        "balance": balance,
        "unread_messages": unread_count
    }


# =============================================================================
# RETURNS ENDPOINTS
# =============================================================================

@router.get("/returns", response_model=List[ReturnInfo])
async def get_client_returns(
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Get all tax returns for the client."""
    query = text("""
        SELECT tr.return_id, tr.tax_year, tr.filing_status, tr.status,
               tr.line_35a_refund, tr.line_37_amount_owed, tr.updated_at
        FROM tax_returns tr
        JOIN taxpayers tp ON tr.return_id = tp.return_id
        JOIN clients c ON tp.email = c.email
        WHERE c.client_id = :client_id
        ORDER BY tr.tax_year DESC
    """)
    result = await session.execute(query, {"client_id": client.client_id})
    rows = result.fetchall()

    status_labels = {
        "draft": "Draft", "in_progress": "In Progress", "pending_review": "Pending Review",
        "reviewed": "Reviewed", "ready_to_file": "Ready to File", "filed": "Filed",
        "accepted": "Accepted", "rejected": "Rejected", "amended": "Amended"
    }

    returns = []
    for row in rows:
        refund = float(row[4]) if row[4] and float(row[4]) > 0 else None
        returns.append({
            "id": str(row[0]),
            "tax_year": row[1],
            "return_type": "1040 Individual",
            "status": row[3] or "draft",
            "status_label": status_labels.get(row[3], "Draft"),
            "refund_amount": refund,
            "updated_at": row[6].isoformat() if row[6] else datetime.utcnow().isoformat()
        })

    return returns


@router.get("/returns/{return_id}")
async def get_return_details(
    return_id: str,
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Get detailed information about a specific return."""
    # Verify client has access to this return
    query = text("""
        SELECT tr.return_id, tr.tax_year, tr.filing_status, tr.status,
               tr.line_35a_refund, tr.line_37_amount_owed, tr.updated_at,
               tr.created_at, tr.submitted_at, tr.accepted_at
        FROM tax_returns tr
        JOIN taxpayers tp ON tr.return_id = tp.return_id
        JOIN clients c ON tp.email = c.email
        WHERE c.client_id = :client_id AND tr.return_id = :return_id
    """)
    result = await session.execute(query, {"client_id": client.client_id, "return_id": return_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    status_labels = {
        "draft": "Draft", "in_progress": "In Progress", "pending_review": "Pending Review",
        "reviewed": "Reviewed", "ready_to_file": "Ready to File", "filed": "Filed",
        "accepted": "Accepted", "rejected": "Rejected"
    }

    current_status = row[3] or "draft"
    refund = float(row[4]) if row[4] and float(row[4]) > 0 else None

    # Build timeline based on actual data
    timeline = [
        {"stage": "received", "date": row[7].isoformat() if row[7] else None, "completed": True},
        {"stage": "review", "date": row[6].isoformat() if row[6] else None,
         "completed": current_status in ["pending_review", "reviewed", "ready_to_file", "filed", "accepted"]},
        {"stage": "ready", "date": None,
         "completed": current_status in ["ready_to_file", "filed", "accepted"]},
        {"stage": "filed", "date": row[8].isoformat() if row[8] else None,
         "completed": current_status in ["filed", "accepted"]}
    ]

    return {
        "id": str(row[0]),
        "tax_year": row[1],
        "return_type": "1040 Individual",
        "status": current_status,
        "status_label": status_labels.get(current_status, "Draft"),
        "refund_amount": refund,
        "updated_at": row[6].isoformat() if row[6] else datetime.utcnow().isoformat(),
        "timeline": timeline
    }


@router.get("/returns/{return_id}/download")
async def download_return(
    return_id: str,
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Get download URL for a filed return."""
    # Verify client has access and return is filed
    query = text("""
        SELECT tr.return_id, tr.status
        FROM tax_returns tr
        JOIN taxpayers tp ON tr.return_id = tp.return_id
        JOIN clients c ON tp.email = c.email
        WHERE c.client_id = :client_id AND tr.return_id = :return_id
    """)
    result = await session.execute(query, {"client_id": client.client_id, "return_id": return_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    if row[1] not in ["filed", "accepted"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Return is not yet filed")

    # In production, generate signed URL for secure download
    return {
        "download_url": f"/api/cpa/client/returns/{return_id}/file",
        "filename": f"TaxReturn_{return_id}.pdf",
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
    }


# =============================================================================
# DOCUMENT ENDPOINTS
# =============================================================================

@router.get("/documents/requests", response_model=List[DocumentRequest])
async def get_document_requests(
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Get all document requests for the client."""
    # Check for document_requests table, if it exists
    query = text("""
        SELECT dr.request_id, dr.document_type, dr.description, dr.is_urgent, dr.is_fulfilled, dr.created_at
        FROM document_requests dr
        WHERE dr.client_id = :client_id AND dr.is_fulfilled = false
        ORDER BY dr.is_urgent DESC, dr.created_at DESC
    """)
    try:
        result = await session.execute(query, {"client_id": client.client_id})
        rows = result.fetchall()
        requests = []
        for row in rows:
            requests.append({
                "id": str(row[0]),
                "name": row[1] or "Document",
                "description": row[2] or "",
                "urgent": row[3] or False,
                "fulfilled": row[4] or False,
                "requested_at": row[5].isoformat() if row[5] else datetime.utcnow().isoformat()
            })
        return requests
    except Exception as e:
        # Table might not exist, return empty list - log the error
        logger.debug(f"Could not fetch document requests: {e}")
        return []


@router.get("/documents/uploaded", response_model=List[UploadedDocument])
async def get_uploaded_documents(
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Get all documents uploaded by the client."""
    query = text("""
        SELECT d.document_id, d.original_filename, d.file_size_bytes, d.status, d.created_at
        FROM documents d
        WHERE d.taxpayer_id IN (
            SELECT tp.taxpayer_id FROM taxpayers tp
            JOIN clients c ON tp.email = c.email
            WHERE c.client_id = :client_id
        )
        OR d.uploaded_by = :client_id
        ORDER BY d.created_at DESC
    """)
    result = await session.execute(query, {"client_id": client.client_id})
    rows = result.fetchall()

    status_labels = {
        "uploaded": "Received", "processing": "Processing", "ocr_complete": "Processing",
        "extraction_complete": "Processing", "verified": "Verified", "applied": "Applied",
        "failed": "Failed", "rejected": "Rejected"
    }

    documents = []
    for row in rows:
        documents.append({
            "id": str(row[0]),
            "filename": row[1] or "Unknown",
            "size": row[2] or 0,
            "uploaded_at": row[4].isoformat() if row[4] else datetime.utcnow().isoformat(),
            "status": row[3] or "uploaded",
            "status_label": status_labels.get(row[3], "Received")
        })

    return documents


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    request_id: Optional[str] = None,
    doc_type: Optional[str] = None,
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Upload a document.

    If request_id is provided, marks that document request as fulfilled.
    """
    # Validate file
    allowed_types = ["application/pdf", "image/jpeg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: PDF, JPG, PNG"
        )

    # Check file size (10MB max)
    max_size = 10 * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB"
        )

    # Get taxpayer_id for this client
    taxpayer_query = text("""
        SELECT tp.taxpayer_id FROM taxpayers tp
        JOIN clients c ON tp.email = c.email
        WHERE c.client_id = :client_id
        ORDER BY tp.created_at DESC
        LIMIT 1
    """)
    taxpayer_result = await session.execute(taxpayer_query, {"client_id": client.client_id})
    taxpayer_row = taxpayer_result.fetchone()

    doc_id = str(uuid4())
    now = datetime.utcnow()

    # Insert document record
    insert_query = text("""
        INSERT INTO documents (
            document_id, taxpayer_id, document_type, tax_year, status,
            original_filename, file_size_bytes, mime_type, uploaded_by, created_at
        ) VALUES (
            :doc_id, :taxpayer_id, :doc_type, :tax_year, 'uploaded',
            :filename, :file_size, :mime_type, :uploaded_by, :created_at
        )
    """)
    await session.execute(insert_query, {
        "doc_id": doc_id,
        "taxpayer_id": str(taxpayer_row[0]) if taxpayer_row else None,
        "doc_type": doc_type or "unknown",
        "tax_year": datetime.utcnow().year,
        "filename": file.filename,
        "file_size": len(contents),
        "mime_type": file.content_type,
        "uploaded_by": client.client_id,
        "created_at": now
    })

    # Mark document request as fulfilled if provided
    if request_id:
        try:
            update_query = text("""
                UPDATE document_requests SET is_fulfilled = true, fulfilled_at = :now
                WHERE request_id = :request_id AND client_id = :client_id
            """)
            await session.execute(update_query, {
                "request_id": request_id,
                "client_id": client.client_id,
                "now": now
            })
        except Exception as e:
            # Document requests table might not exist - log but continue
            logger.debug(f"Could not update document request {request_id}: {e}")

    await session.commit()

    logger.info(f"Document uploaded: {doc_id} by client {client.client_id}")

    return {
        "id": doc_id,
        "filename": file.filename,
        "size": len(contents),
        "uploaded_at": now.isoformat(),
        "status": "uploaded",
        "status_label": "Received",
        "request_fulfilled": request_id is not None
    }


# =============================================================================
# MESSAGING ENDPOINTS
# =============================================================================

@router.get("/messages", response_model=List[Message])
async def get_messages(
    client: ClientContext = Depends(get_current_client),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session)
):
    """Get messages between client and CPA."""
    query = text("""
        SELECT m.message_id, m.content, m.sender_id, m.created_at, m.read_at
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.conversation_id
        WHERE c.participants @> :participant::jsonb
        ORDER BY m.created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    try:
        result = await session.execute(query, {
            "participant": json.dumps({"id": client.client_id}),
            "limit": limit,
            "offset": offset
        })
        rows = result.fetchall()

        messages = []
        for row in rows:
            sender_type = "client" if row[2] == client.client_id else "cpa"
            messages.append({
                "id": str(row[0]),
                "content": row[1],
                "sender_type": sender_type,
                "created_at": row[3].isoformat() if row[3] else datetime.utcnow().isoformat(),
                "read": row[4] is not None
            })
        return messages
    except Exception as e:
        # Messages table might not exist - log error
        logger.debug(f"Could not fetch messages: {e}")
        return []


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    content: str = Field(..., min_length=1, max_length=5000)


@router.post("/messages")
async def send_message(
    request: SendMessageRequest,
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Send a message to the CPA."""
    msg_id = str(uuid4())
    now = datetime.utcnow()

    # Find or create conversation with CPA
    find_conv_query = text("""
        SELECT conversation_id FROM conversations
        WHERE conversation_type = 'direct'
        AND participants @> :client_participant::jsonb
        AND participants @> :cpa_participant::jsonb
        LIMIT 1
    """)
    try:
        conv_result = await session.execute(find_conv_query, {
            "client_participant": json.dumps({"id": client.client_id}),
            "cpa_participant": json.dumps({"id": client.cpa_id}) if client.cpa_id else json.dumps({})
        })
        conv_row = conv_result.fetchone()

        if conv_row:
            conversation_id = str(conv_row[0])
        else:
            # Create new conversation
            conversation_id = str(uuid4())
            participants = [
                {"id": client.client_id, "type": "client", "name": client.name}
            ]
            if client.cpa_id:
                participants.append({"id": client.cpa_id, "type": "cpa"})

            create_conv_query = text("""
                INSERT INTO conversations (conversation_id, conversation_type, participants, created_at)
                VALUES (:conv_id, 'direct', :participants, :created_at)
            """)
            await session.execute(create_conv_query, {
                "conv_id": conversation_id,
                "participants": json.dumps(participants),
                "created_at": now
            })

        # Insert message
        insert_msg_query = text("""
            INSERT INTO messages (message_id, conversation_id, sender_id, content, created_at)
            VALUES (:msg_id, :conv_id, :sender_id, :content, :created_at)
        """)
        await session.execute(insert_msg_query, {
            "msg_id": msg_id,
            "conv_id": conversation_id,
            "sender_id": client.client_id,
            "content": request.content,
            "created_at": now
        })

        await session.commit()
        logger.info(f"Message sent: {msg_id} by client {client.client_id}")

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        # Messages table might not exist, just return success for now

    return {
        "id": msg_id,
        "content": request.content,
        "sender_type": "client",
        "created_at": now.isoformat(),
        "read": False
    }


@router.post("/messages/read")
async def mark_messages_read(
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Mark all messages as read."""
    now = datetime.utcnow()
    try:
        update_query = text("""
            UPDATE messages m
            SET read_at = :now
            FROM conversations c
            WHERE m.conversation_id = c.conversation_id
            AND c.participants @> :participant::jsonb
            AND m.sender_id != :client_id
            AND m.read_at IS NULL
        """)
        result = await session.execute(update_query, {
            "participant": json.dumps({"id": client.client_id}),
            "client_id": client.client_id,
            "now": now
        })
        await session.commit()
        return {"marked_read": True, "count": result.rowcount}
    except Exception as e:
        logger.debug(f"Could not mark messages as read: {e}")
        return {"marked_read": True, "count": 0}


# =============================================================================
# BILLING ENDPOINTS
# =============================================================================

class BillingResponse(BaseModel):
    """Billing summary response."""
    balance: float
    invoices: List[Invoice]


@router.get("/billing", response_model=BillingResponse)
async def get_billing(
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Get billing summary and invoices."""
    invoices = []
    balance = 0.0

    if client.firm_id:
        query = text("""
            SELECT i.invoice_id, i.created_at, i.due_date, i.line_items, i.amount_due, i.status
            FROM invoices i
            WHERE i.firm_id = :firm_id
            ORDER BY i.created_at DESC
            LIMIT 20
        """)
        try:
            result = await session.execute(query, {"firm_id": client.firm_id})
            rows = result.fetchall()

            for row in rows:
                line_items = row[3] if row[3] else []
                if isinstance(line_items, str):
                    line_items = json.loads(line_items)
                description = line_items[0].get("description", "Tax Services") if line_items else "Tax Services"
                amount = float(row[4]) if row[4] else 0.0
                inv_status = row[5] or "pending"

                if inv_status not in ["paid", "voided"]:
                    balance += amount

                invoices.append({
                    "id": str(row[0]),
                    "date": row[1].isoformat() if row[1] else datetime.utcnow().isoformat(),
                    "due_date": row[2].isoformat() if row[2] else (datetime.utcnow() + timedelta(days=30)).isoformat(),
                    "description": description,
                    "amount": amount,
                    "status": "paid" if inv_status == "paid" else "pending"
                })
        except Exception as e:
            logger.debug(f"Could not fetch billing invoices: {e}")

    return {"balance": balance, "invoices": invoices}


@router.get("/billing/invoices/{invoice_id}")
async def get_invoice_details(
    invoice_id: str,
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Get detailed invoice information."""
    query = text("""
        SELECT i.invoice_id, i.created_at, i.due_date, i.line_items, i.amount_due, i.status,
               i.subtotal, i.tax, i.discount
        FROM invoices i
        WHERE i.invoice_id = :invoice_id AND i.firm_id = :firm_id
    """)
    result = await session.execute(query, {"invoice_id": invoice_id, "firm_id": client.firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    line_items_raw = row[3] if row[3] else []
    if isinstance(line_items_raw, str):
        line_items_raw = json.loads(line_items_raw)

    line_items = [{"description": item.get("description", ""), "amount": item.get("amount", 0)}
                  for item in line_items_raw]

    description = line_items[0]["description"] if line_items else "Tax Services"

    return {
        "id": str(row[0]),
        "date": row[1].isoformat() if row[1] else datetime.utcnow().isoformat(),
        "due_date": row[2].isoformat() if row[2] else (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "description": description,
        "amount": float(row[4]) if row[4] else 0.0,
        "status": "paid" if row[5] == "paid" else "pending",
        "line_items": line_items
    }


@router.post("/billing/invoices/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: str,
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Initiate payment for an invoice.

    Returns a payment URL to redirect the client to.
    """
    # Verify invoice exists and is payable
    query = text("""
        SELECT i.invoice_id, i.status, i.hosted_invoice_url
        FROM invoices i
        WHERE i.invoice_id = :invoice_id AND i.firm_id = :firm_id
    """)
    result = await session.execute(query, {"invoice_id": invoice_id, "firm_id": client.firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    if row[1] == "paid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice already paid")

    # In production: create payment session with Stripe
    payment_url = row[2] if row[2] else f"/pay?invoice={invoice_id}&client={client.client_id}"

    return {
        "payment_url": payment_url,
        "payment_id": str(uuid4()),
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
    }


@router.get("/billing/invoices/{invoice_id}/receipt")
async def get_receipt(
    invoice_id: str,
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Get download URL for a payment receipt."""
    # Verify invoice exists and is paid
    query = text("""
        SELECT i.invoice_id, i.status, i.invoice_pdf_url
        FROM invoices i
        WHERE i.invoice_id = :invoice_id AND i.firm_id = :firm_id
    """)
    result = await session.execute(query, {"invoice_id": invoice_id, "firm_id": client.firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    if row[1] != "paid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice not yet paid")

    download_url = row[2] if row[2] else f"/api/cpa/client/billing/invoices/{invoice_id}/receipt-file"

    return {
        "download_url": download_url,
        "filename": f"Receipt_{invoice_id}.pdf",
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
    }


# =============================================================================
# PROFILE ENDPOINTS
# =============================================================================

@router.get("/profile")
async def get_client_profile(
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Get client profile information."""
    # Get full client info
    client_query = text("""
        SELECT c.client_id, c.first_name, c.last_name, c.email, c.phone, c.profile_data
        FROM clients c
        WHERE c.client_id = :client_id
    """)
    result = await session.execute(client_query, {"client_id": client.client_id})
    client_row = result.fetchone()

    profile_data = client_row[5] if client_row and client_row[5] else {}
    if isinstance(profile_data, str):
        profile_data = json.loads(profile_data)

    address = profile_data.get("address", {})

    # Get CPA info
    cpa_info = {"id": "", "name": "Unassigned", "firm_name": "", "email": "", "phone": ""}
    if client.cpa_id:
        cpa_query = text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.phone, f.name as firm_name
            FROM users u
            LEFT JOIN firms f ON u.firm_id = f.firm_id
            WHERE u.user_id = :cpa_id
        """)
        cpa_result = await session.execute(cpa_query, {"cpa_id": client.cpa_id})
        cpa_row = cpa_result.fetchone()
        if cpa_row:
            cpa_info = {
                "id": str(cpa_row[0]),
                "name": f"{cpa_row[1]} {cpa_row[2]}, CPA",
                "firm_name": cpa_row[5] or "",
                "email": cpa_row[3] or "",
                "phone": cpa_row[4] or ""
            }

    return {
        "id": client.client_id,
        "name": client.name,
        "email": client.email,
        "phone": client_row[4] if client_row else "",
        "address": {
            "street": address.get("street", ""),
            "city": address.get("city", ""),
            "state": address.get("state", ""),
            "zip": address.get("zip", "")
        },
        "cpa": cpa_info
    }


class UpdateProfileRequest(BaseModel):
    """Request to update profile."""
    phone: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None


@router.put("/profile")
async def update_client_profile(
    request: UpdateProfileRequest,
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Update client profile information."""
    # Get current profile_data
    query = text("SELECT profile_data FROM clients WHERE client_id = :client_id")
    result = await session.execute(query, {"client_id": client.client_id})
    row = result.fetchone()

    profile_data = row[0] if row and row[0] else {}
    if isinstance(profile_data, str):
        profile_data = json.loads(profile_data)

    # Update fields
    fields_updated = []
    if request.phone is not None:
        await session.execute(
            text("UPDATE clients SET phone = :phone WHERE client_id = :client_id"),
            {"phone": request.phone, "client_id": client.client_id}
        )
        fields_updated.append("phone")

    address = profile_data.get("address", {})
    if request.address_street is not None:
        address["street"] = request.address_street
        fields_updated.append("address_street")
    if request.address_city is not None:
        address["city"] = request.address_city
        fields_updated.append("address_city")
    if request.address_state is not None:
        address["state"] = request.address_state
        fields_updated.append("address_state")
    if request.address_zip is not None:
        address["zip"] = request.address_zip
        fields_updated.append("address_zip")

    if address:
        profile_data["address"] = address
        await session.execute(
            text("UPDATE clients SET profile_data = :profile_data WHERE client_id = :client_id"),
            {"profile_data": json.dumps(profile_data), "client_id": client.client_id}
        )

    await session.commit()

    return {"updated": True, "fields_updated": fields_updated}


# =============================================================================
# NOTIFICATIONS ENDPOINTS
# =============================================================================

@router.get("/notifications")
async def get_notifications(
    client: ClientContext = Depends(get_current_client),
    unread_only: bool = Query(False),
    session: AsyncSession = Depends(get_async_session)
):
    """Get notifications for the client."""
    query = text("""
        SELECT notification_id, notification_type, title, content, is_read, created_at
        FROM notifications
        WHERE user_id = :client_id
        """ + ("AND is_read = false" if unread_only else "") + """
        ORDER BY created_at DESC
        LIMIT 50
    """)
    try:
        result = await session.execute(query, {"client_id": client.client_id})
        rows = result.fetchall()

        notifications = []
        unread_count = 0
        for row in rows:
            is_read = row[4] if row[4] is not None else False
            if not is_read:
                unread_count += 1
            notifications.append({
                "id": str(row[0]),
                "type": row[1] or "general",
                "title": row[2] or "",
                "content": row[3] or "",
                "read": is_read,
                "created_at": row[5].isoformat() if row[5] else datetime.utcnow().isoformat()
            })

        return {"notifications": notifications, "unread_count": unread_count}
    except Exception as e:
        # Notifications table might not exist - log error
        logger.debug(f"Could not fetch notifications: {e}")
        return {"notifications": [], "unread_count": 0}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    client: ClientContext = Depends(get_current_client),
    session: AsyncSession = Depends(get_async_session)
):
    """Mark a notification as read."""
    try:
        query = text("""
            UPDATE notifications SET is_read = true, read_at = :now
            WHERE notification_id = :notification_id AND user_id = :client_id
        """)
        await session.execute(query, {
            "notification_id": notification_id,
            "client_id": client.client_id,
            "now": datetime.utcnow()
        })
        await session.commit()
    except Exception as e:
        logger.debug(f"Could not mark notification {notification_id} as read: {e}")

    return {"marked_read": True}
