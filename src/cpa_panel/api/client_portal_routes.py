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

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from pydantic import BaseModel, Field

import logging

logger = logging.getLogger(__name__)

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
async def client_login(request: ClientLoginRequest):
    """
    Client login via magic link.

    In production, this would:
    1. Verify the email exists in the client database
    2. Send a magic link email with a secure token
    3. Client clicks link, token is validated, and they're logged in

    For demo purposes, returns a mock token immediately.
    """
    import secrets

    # Mock: Check if email exists (in production: query database)
    # For demo, accept any email
    if not request.email or "@" not in request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address"
        )

    # Generate client token
    client_token = f"client_{secrets.token_urlsafe(32)}"

    return {
        "success": True,
        "message": "Login successful. In production, a magic link would be sent to your email.",
        "token": client_token
    }


@router.post("/verify-token")
async def verify_client_token(token: str = Query(...)):
    """
    Verify a client token is valid.

    Returns client info if token is valid.
    """
    # Mock: Accept any token starting with "client_"
    if not token or not token.startswith("client_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    return {
        "valid": True,
        "client_id": "client-001",
        "name": "John Smith",
        "email": "john.smith@example.com"
    }


# =============================================================================
# MOCK AUTH - Replace with real auth in production
# =============================================================================

class ClientContext(BaseModel):
    """Authenticated client context."""
    client_id: str
    name: str
    email: str
    firm_id: str
    cpa_id: str


async def get_current_client() -> ClientContext:
    """
    Get current authenticated client from JWT token.
    In production, this would validate the JWT and extract client info.
    """
    # Mock client for development
    return ClientContext(
        client_id="client-001",
        name="John Smith",
        email="john.smith@example.com",
        firm_id="firm-001",
        cpa_id="cpa-001"
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
    client: ClientContext = Depends(get_current_client)
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
    # Mock data - in production, fetch from database
    return {
        "client_id": client.client_id,
        "name": client.name,
        "cpa": {
            "id": "cpa-001",
            "name": "Jane Doe, CPA",
            "email": "jane.doe@taxfirm.com",
            "phone": "(555) 123-4567"
        },
        "returns": [
            {
                "id": "return-2024",
                "tax_year": 2024,
                "return_type": "1040 Individual",
                "status": "review",
                "status_label": "In Review",
                "refund_amount": None,
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "return-2023",
                "tax_year": 2023,
                "return_type": "1040 Individual",
                "status": "filed",
                "status_label": "Filed",
                "refund_amount": 2847.00,
                "updated_at": (datetime.utcnow() - timedelta(days=270)).isoformat()
            }
        ],
        "current_return": {
            "id": "return-2024",
            "tax_year": 2024,
            "return_type": "1040 Individual",
            "status": "review",
            "status_label": "In Review",
            "refund_amount": None,
            "updated_at": datetime.utcnow().isoformat()
        },
        "document_requests": [
            {
                "id": "doc-req-1",
                "name": "W-2 Forms",
                "description": "From all employers for 2024",
                "urgent": True,
                "fulfilled": False,
                "requested_at": (datetime.utcnow() - timedelta(days=2)).isoformat()
            },
            {
                "id": "doc-req-2",
                "name": "1099-INT",
                "description": "Interest income statements from banks",
                "urgent": False,
                "fulfilled": False,
                "requested_at": (datetime.utcnow() - timedelta(days=1)).isoformat()
            }
        ],
        "uploaded_documents": [
            {
                "id": "doc-1",
                "filename": "W2_Employer1_2024.pdf",
                "size": 245000,
                "uploaded_at": (datetime.utcnow() - timedelta(hours=5)).isoformat(),
                "status": "received",
                "status_label": "Received"
            }
        ],
        "messages": [
            {
                "id": "msg-1",
                "content": "Hi! I've started reviewing your documents. Quick question - did you have any additional 1099 income this year?",
                "sender_type": "cpa",
                "created_at": (datetime.utcnow() - timedelta(days=1, hours=14)).isoformat(),
                "read": True
            },
            {
                "id": "msg-2",
                "content": "Yes, I had some freelance work. I'll upload those 1099s now.",
                "sender_type": "client",
                "created_at": (datetime.utcnow() - timedelta(days=1, hours=13)).isoformat(),
                "read": True
            },
            {
                "id": "msg-3",
                "content": "Perfect! Once I receive those, I should have your return ready for review within 2-3 business days.",
                "sender_type": "cpa",
                "created_at": (datetime.utcnow() - timedelta(days=1, hours=12, minutes=45)).isoformat(),
                "read": False
            }
        ],
        "invoices": [
            {
                "id": "inv-1",
                "date": datetime.utcnow().isoformat(),
                "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "description": "2024 Tax Return Preparation",
                "amount": 350.00,
                "status": "pending"
            },
            {
                "id": "inv-2",
                "date": (datetime.utcnow() - timedelta(days=270)).isoformat(),
                "due_date": (datetime.utcnow() - timedelta(days=240)).isoformat(),
                "description": "2023 Tax Return Preparation",
                "amount": 300.00,
                "status": "paid"
            }
        ],
        "balance": 350.00,
        "unread_messages": 1
    }


# =============================================================================
# RETURNS ENDPOINTS
# =============================================================================

@router.get("/returns", response_model=List[ReturnInfo])
async def get_client_returns(
    client: ClientContext = Depends(get_current_client)
):
    """Get all tax returns for the client."""
    return [
        {
            "id": "return-2024",
            "tax_year": 2024,
            "return_type": "1040 Individual",
            "status": "review",
            "status_label": "In Review",
            "refund_amount": None,
            "updated_at": datetime.utcnow().isoformat()
        },
        {
            "id": "return-2023",
            "tax_year": 2023,
            "return_type": "1040 Individual",
            "status": "filed",
            "status_label": "Filed",
            "refund_amount": 2847.00,
            "updated_at": (datetime.utcnow() - timedelta(days=270)).isoformat()
        }
    ]


@router.get("/returns/{return_id}")
async def get_return_details(
    return_id: str,
    client: ClientContext = Depends(get_current_client)
):
    """Get detailed information about a specific return."""
    return {
        "id": return_id,
        "tax_year": 2024,
        "return_type": "1040 Individual",
        "status": "review",
        "status_label": "In Review",
        "refund_amount": None,
        "updated_at": datetime.utcnow().isoformat(),
        "timeline": [
            {"stage": "received", "date": (datetime.utcnow() - timedelta(days=3)).isoformat(), "completed": True},
            {"stage": "review", "date": datetime.utcnow().isoformat(), "completed": False},
            {"stage": "ready", "date": None, "completed": False},
            {"stage": "filed", "date": None, "completed": False}
        ]
    }


@router.get("/returns/{return_id}/download")
async def download_return(
    return_id: str,
    client: ClientContext = Depends(get_current_client)
):
    """Get download URL for a filed return."""
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
    client: ClientContext = Depends(get_current_client)
):
    """Get all document requests for the client."""
    return [
        {
            "id": "doc-req-1",
            "name": "W-2 Forms",
            "description": "From all employers for 2024",
            "urgent": True,
            "fulfilled": False,
            "requested_at": (datetime.utcnow() - timedelta(days=2)).isoformat()
        },
        {
            "id": "doc-req-2",
            "name": "1099-INT",
            "description": "Interest income statements from banks",
            "urgent": False,
            "fulfilled": False,
            "requested_at": (datetime.utcnow() - timedelta(days=1)).isoformat()
        }
    ]


@router.get("/documents/uploaded", response_model=List[UploadedDocument])
async def get_uploaded_documents(
    client: ClientContext = Depends(get_current_client)
):
    """Get all documents uploaded by the client."""
    return [
        {
            "id": "doc-1",
            "filename": "W2_Employer1_2024.pdf",
            "size": 245000,
            "uploaded_at": (datetime.utcnow() - timedelta(hours=5)).isoformat(),
            "status": "received",
            "status_label": "Received"
        }
    ]


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    request_id: Optional[str] = None,
    doc_type: Optional[str] = None,
    client: ClientContext = Depends(get_current_client)
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

    # In production: save file to storage, create database record
    doc_id = str(uuid4())

    return {
        "id": doc_id,
        "filename": file.filename,
        "size": len(contents),
        "uploaded_at": datetime.utcnow().isoformat(),
        "status": "processing",
        "status_label": "Processing",
        "request_fulfilled": request_id is not None
    }


# =============================================================================
# MESSAGING ENDPOINTS
# =============================================================================

@router.get("/messages", response_model=List[Message])
async def get_messages(
    client: ClientContext = Depends(get_current_client),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Get messages between client and CPA."""
    return [
        {
            "id": "msg-1",
            "content": "Hi! I've started reviewing your documents. Quick question - did you have any additional 1099 income this year?",
            "sender_type": "cpa",
            "created_at": (datetime.utcnow() - timedelta(days=1, hours=14)).isoformat(),
            "read": True
        },
        {
            "id": "msg-2",
            "content": "Yes, I had some freelance work. I'll upload those 1099s now.",
            "sender_type": "client",
            "created_at": (datetime.utcnow() - timedelta(days=1, hours=13)).isoformat(),
            "read": True
        },
        {
            "id": "msg-3",
            "content": "Perfect! Once I receive those, I should have your return ready for review within 2-3 business days.",
            "sender_type": "cpa",
            "created_at": (datetime.utcnow() - timedelta(days=1, hours=12, minutes=45)).isoformat(),
            "read": False
        }
    ]


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    content: str = Field(..., min_length=1, max_length=5000)


@router.post("/messages")
async def send_message(
    request: SendMessageRequest,
    client: ClientContext = Depends(get_current_client)
):
    """Send a message to the CPA."""
    msg_id = str(uuid4())

    # In production: save to database, notify CPA
    return {
        "id": msg_id,
        "content": request.content,
        "sender_type": "client",
        "created_at": datetime.utcnow().isoformat(),
        "read": False
    }


@router.post("/messages/read")
async def mark_messages_read(
    client: ClientContext = Depends(get_current_client)
):
    """Mark all messages as read."""
    # In production: update database
    return {"marked_read": True, "count": 1}


# =============================================================================
# BILLING ENDPOINTS
# =============================================================================

class BillingResponse(BaseModel):
    """Billing summary response."""
    balance: float
    invoices: List[Invoice]


@router.get("/billing", response_model=BillingResponse)
async def get_billing(
    client: ClientContext = Depends(get_current_client)
):
    """Get billing summary and invoices."""
    return {
        "balance": 350.00,
        "invoices": [
            {
                "id": "inv-1",
                "date": datetime.utcnow().isoformat(),
                "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "description": "2024 Tax Return Preparation",
                "amount": 350.00,
                "status": "pending"
            },
            {
                "id": "inv-2",
                "date": (datetime.utcnow() - timedelta(days=270)).isoformat(),
                "due_date": (datetime.utcnow() - timedelta(days=240)).isoformat(),
                "description": "2023 Tax Return Preparation",
                "amount": 300.00,
                "status": "paid"
            }
        ]
    }


@router.get("/billing/invoices/{invoice_id}")
async def get_invoice_details(
    invoice_id: str,
    client: ClientContext = Depends(get_current_client)
):
    """Get detailed invoice information."""
    return {
        "id": invoice_id,
        "date": datetime.utcnow().isoformat(),
        "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "description": "2024 Tax Return Preparation",
        "amount": 350.00,
        "status": "pending",
        "line_items": [
            {"description": "Federal Return Preparation", "amount": 200.00},
            {"description": "State Return Preparation", "amount": 100.00},
            {"description": "Schedule C (Self-Employment)", "amount": 50.00}
        ]
    }


@router.post("/billing/invoices/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: str,
    client: ClientContext = Depends(get_current_client)
):
    """
    Initiate payment for an invoice.

    Returns a payment URL to redirect the client to.
    """
    # In production: create payment session with Stripe/payment processor
    return {
        "payment_url": f"/pay?invoice={invoice_id}&client={client.client_id}",
        "payment_id": str(uuid4()),
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
    }


@router.get("/billing/invoices/{invoice_id}/receipt")
async def get_receipt(
    invoice_id: str,
    client: ClientContext = Depends(get_current_client)
):
    """Get download URL for a payment receipt."""
    return {
        "download_url": f"/api/cpa/client/billing/invoices/{invoice_id}/receipt-file",
        "filename": f"Receipt_{invoice_id}.pdf",
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
    }


# =============================================================================
# PROFILE ENDPOINTS
# =============================================================================

@router.get("/profile")
async def get_client_profile(
    client: ClientContext = Depends(get_current_client)
):
    """Get client profile information."""
    return {
        "id": client.client_id,
        "name": client.name,
        "email": client.email,
        "phone": "(555) 987-6543",
        "address": {
            "street": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip": "90210"
        },
        "cpa": {
            "id": "cpa-001",
            "name": "Jane Doe, CPA",
            "firm_name": "Doe Tax Services",
            "email": "jane.doe@taxfirm.com",
            "phone": "(555) 123-4567"
        }
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
    client: ClientContext = Depends(get_current_client)
):
    """Update client profile information."""
    # In production: update database
    return {
        "updated": True,
        "fields_updated": [k for k, v in request.dict().items() if v is not None]
    }


# =============================================================================
# NOTIFICATIONS ENDPOINTS
# =============================================================================

@router.get("/notifications")
async def get_notifications(
    client: ClientContext = Depends(get_current_client),
    unread_only: bool = Query(False)
):
    """Get notifications for the client."""
    return {
        "notifications": [
            {
                "id": "notif-1",
                "type": "message",
                "title": "New message from Jane Doe",
                "content": "Perfect! Once I receive those...",
                "read": False,
                "created_at": (datetime.utcnow() - timedelta(days=1)).isoformat()
            },
            {
                "id": "notif-2",
                "type": "document_request",
                "title": "Document requested",
                "content": "Your CPA needs your W-2 forms",
                "read": True,
                "created_at": (datetime.utcnow() - timedelta(days=2)).isoformat()
            }
        ],
        "unread_count": 1
    }


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    client: ClientContext = Depends(get_current_client)
):
    """Mark a notification as read."""
    return {"marked_read": True}
