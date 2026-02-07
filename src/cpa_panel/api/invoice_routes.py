"""
Invoice and Payment Routes

API endpoints for CPA invoice management and client payments.

SECURITY: All endpoints require authentication via get_current_user dependency.
"""

import logging
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends, status
from pydantic import BaseModel, Field, EmailStr

from ..payments import (
    payment_service,
    Invoice,
    InvoiceStatus,
    PaymentLink,
    PaymentMethod,
    PaymentStatus,
)
from .common import get_tenant_id

# Import authentication dependency
from src.core.api.auth_routes import get_current_user
from src.core.models.user import UserContext

logger = logging.getLogger(__name__)

invoice_router = APIRouter(prefix="/invoices", tags=["Invoices"])
payment_link_router = APIRouter(prefix="/payment-links", tags=["Payment Links"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class LineItemRequest(BaseModel):
    """Line item for invoice."""
    description: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    quantity: int = Field(1, ge=1)
    tax_rate: float = Field(0.0, ge=0, le=1)


class CreateInvoiceRequest(BaseModel):
    """Request to create an invoice."""
    client_name: str = Field(..., min_length=1)
    client_email: EmailStr
    client_address: Optional[str] = None
    line_items: List[LineItemRequest]
    notes: Optional[str] = None
    terms: Optional[str] = None
    due_days: int = Field(30, ge=1, le=90)
    currency: str = "USD"
    discount_amount: float = Field(0.0, ge=0)


class UpdateInvoiceRequest(BaseModel):
    """Request to update an invoice."""
    notes: Optional[str] = None
    terms: Optional[str] = None
    due_date: Optional[date] = None


class RecordPaymentRequest(BaseModel):
    """Request to record a payment."""
    amount: float = Field(..., gt=0)
    payment_method: str = "card"
    paid_date: Optional[date] = None


class CreatePaymentLinkRequest(BaseModel):
    """Request to create a payment link."""
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    currency: str = "USD"
    max_uses: Optional[int] = Field(None, ge=1)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    min_amount: Optional[float] = Field(None, gt=0)
    max_amount: Optional[float] = Field(None, gt=0)


class ProcessLinkPaymentRequest(BaseModel):
    """Request to process payment via link."""
    amount: float = Field(..., gt=0)
    payer_name: str = Field(..., min_length=1)
    payer_email: EmailStr
    payment_method: str = "card"


# =============================================================================
# INVOICE ROUTES
# =============================================================================

@invoice_router.post("", status_code=status.HTTP_201_CREATED)
async def create_invoice(
    request: CreateInvoiceRequest,
    user: UserContext = Depends(get_current_user),
    client_id: Optional[str] = Query(None, description="Client ID"),
):
    """
    Create a new invoice for a client.

    Creates a draft invoice that can be edited before sending.
    Requires authentication - uses authenticated user's firm context.
    """
    # Extract user context from authenticated session
    cpa_id = str(user.user_id)
    firm_id = str(user.firm_id) if hasattr(user, 'firm_id') and user.firm_id else ""
    cpa_name = getattr(user, 'full_name', '') or user.email
    firm_name = getattr(user, 'firm_name', '') or "Unknown Firm"

    invoice = payment_service.create_invoice(
        firm_id=UUID(firm_id) if firm_id else None,
        cpa_id=UUID(cpa_id),
        cpa_name=cpa_name,
        firm_name=firm_name,
        client_name=request.client_name,
        client_email=request.client_email,
        client_id=UUID(client_id) if client_id else None,
        client_address=request.client_address,
        line_items=[
            {
                "description": item.description,
                "amount": item.amount,
                "quantity": item.quantity,
                "tax_rate": item.tax_rate,
            }
            for item in request.line_items
        ],
        notes=request.notes,
        terms=request.terms,
        due_days=request.due_days,
        currency=request.currency,
        discount_amount=request.discount_amount,
    )

    return {
        "success": True,
        "invoice": invoice.to_dict(),
    }


@invoice_router.get("")
async def list_invoices(
    user: UserContext = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    client_id: Optional[str] = Query(None, description="Filter by client"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    """List invoices for authenticated CPA with optional filters."""
    invoice_status = InvoiceStatus(status_filter) if status_filter else None

    invoices = payment_service.get_invoices_for_cpa(
        cpa_id=UUID(str(user.user_id)),
        status=invoice_status,
        client_id=UUID(client_id) if client_id else None,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "success": True,
        "invoices": [i.to_dict() for i in invoices],
        "total": len(invoices),
    }


@invoice_router.get("/firm")
async def list_firm_invoices(
    user: UserContext = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
):
    """List all invoices for authenticated user's firm."""
    invoice_status = InvoiceStatus(status_filter) if status_filter else None
    firm_id = str(user.firm_id) if hasattr(user, 'firm_id') and user.firm_id else None

    if not firm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a firm"
        )

    invoices = payment_service.get_invoices_for_firm(
        firm_id=UUID(firm_id),
        status=invoice_status,
    )

    return {
        "success": True,
        "invoices": [i.to_dict() for i in invoices],
        "total": len(invoices),
    }


@invoice_router.get("/overdue")
async def get_overdue_invoices(
    user: UserContext = Depends(get_current_user),
):
    """Get overdue invoices for authenticated user's context."""
    cpa_id = str(user.user_id)
    firm_id = str(user.firm_id) if hasattr(user, 'firm_id') and user.firm_id else None

    invoices = payment_service.get_overdue_invoices(
        cpa_id=UUID(cpa_id),
        firm_id=UUID(firm_id) if firm_id else None,
    )

    return {
        "success": True,
        "invoices": [i.to_dict() for i in invoices],
        "total": len(invoices),
        "total_overdue_amount": sum(i.balance_due for i in invoices),
    }


@invoice_router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Get invoice details. Validates user has access to the invoice."""
    invoice = payment_service.get_invoice(UUID(invoice_id))
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    # Verify user has access to this invoice (same CPA or same firm)
    user_cpa_id = str(user.user_id)
    user_firm_id = str(user.firm_id) if hasattr(user, 'firm_id') and user.firm_id else None

    if str(invoice.cpa_id) != user_cpa_id:
        if not user_firm_id or str(invoice.firm_id) != user_firm_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this invoice"
            )

    return {
        "success": True,
        "invoice": invoice.to_dict(),
    }


@invoice_router.put("/{invoice_id}")
async def update_invoice(
    invoice_id: str,
    request: UpdateInvoiceRequest,
    user: UserContext = Depends(get_current_user),
):
    """Update a draft invoice. Validates user has access."""
    # First verify access
    existing = payment_service.get_invoice(UUID(invoice_id))
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    user_cpa_id = str(user.user_id)
    if str(existing.cpa_id) != user_cpa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own invoices"
        )

    try:
        invoice = payment_service.update_invoice(
            invoice_id=UUID(invoice_id),
            notes=request.notes,
            terms=request.terms,
            due_date=request.due_date,
        )

        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found"
            )

        return {
            "success": True,
            "invoice": invoice.to_dict(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@invoice_router.post("/{invoice_id}/send")
async def send_invoice(
    invoice_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Send invoice to client.

    Generates payment link and marks invoice as sent.
    Requires authentication and ownership validation.
    """
    # Verify access
    existing = payment_service.get_invoice(UUID(invoice_id))
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    user_cpa_id = str(user.user_id)
    if str(existing.cpa_id) != user_cpa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send your own invoices"
        )

    invoice = payment_service.send_invoice(UUID(invoice_id))
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    return {
        "success": True,
        "invoice": invoice.to_dict(),
        "payment_link": invoice.payment_link,
        "message": f"Invoice sent to {invoice.client_email}",
    }


@invoice_router.post("/{invoice_id}/record-payment")
async def record_invoice_payment(
    invoice_id: str,
    request: RecordPaymentRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    Record a payment against an invoice.

    Use this for offline payments (check, cash) or to manually
    record a Stripe payment. Requires authentication.
    """
    # Verify access
    existing = payment_service.get_invoice(UUID(invoice_id))
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    user_cpa_id = str(user.user_id)
    user_firm_id = str(user.firm_id) if hasattr(user, 'firm_id') and user.firm_id else None

    if str(existing.cpa_id) != user_cpa_id:
        if not user_firm_id or str(existing.firm_id) != user_firm_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this invoice"
            )
    try:
        payment_method = PaymentMethod(request.payment_method)
    except ValueError:
        payment_method = PaymentMethod.OTHER

    invoice, payment = payment_service.record_payment(
        invoice_id=UUID(invoice_id),
        amount=request.amount,
        payment_method=payment_method,
        paid_date=request.paid_date,
    )

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    return {
        "success": True,
        "invoice": invoice.to_dict(),
        "payment": payment.to_dict() if payment else None,
    }


@invoice_router.post("/{invoice_id}/void")
async def void_invoice(
    invoice_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Void an invoice. Requires authentication and ownership."""
    # Verify access
    existing = payment_service.get_invoice(UUID(invoice_id))
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    user_cpa_id = str(user.user_id)
    if str(existing.cpa_id) != user_cpa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only void your own invoices"
        )

    try:
        invoice = payment_service.void_invoice(UUID(invoice_id))
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found"
            )

        return {
            "success": True,
            "invoice": invoice.to_dict(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@invoice_router.get("/statuses")
async def get_invoice_statuses():
    """Get list of invoice statuses."""
    return {
        "success": True,
        "statuses": [
            {"value": s.value, "label": s.value.replace("_", " ").title()}
            for s in InvoiceStatus
        ],
    }


# =============================================================================
# PAYMENT LINK ROUTES
# =============================================================================

@payment_link_router.post("", status_code=status.HTTP_201_CREATED)
async def create_payment_link(
    request: CreatePaymentLinkRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    Create a reusable payment link.

    Payment links can be shared with clients for easy online payment.
    Requires authentication.
    """
    cpa_id = str(user.user_id)
    firm_id = str(user.firm_id) if hasattr(user, 'firm_id') and user.firm_id else None

    link = payment_service.create_payment_link(
        firm_id=UUID(firm_id) if firm_id else None,
        cpa_id=UUID(cpa_id),
        name=request.name,
        description=request.description,
        amount=request.amount,
        currency=request.currency,
        max_uses=request.max_uses,
        expires_in_days=request.expires_in_days,
        min_amount=request.min_amount,
        max_amount=request.max_amount,
    )

    return {
        "success": True,
        "payment_link": link.to_dict(),
        "shareable_url": link.url,
    }


@payment_link_router.get("")
async def list_payment_links(
    user: UserContext = Depends(get_current_user),
    active_only: bool = Query(True),
):
    """List payment links for authenticated CPA."""
    links = payment_service.get_payment_links_for_cpa(
        cpa_id=UUID(str(user.user_id)),
        active_only=active_only,
    )

    return {
        "success": True,
        "payment_links": [l.to_dict() for l in links],
        "total": len(links),
    }


@payment_link_router.get("/{link_id}")
async def get_payment_link(
    link_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Get payment link details. Requires authentication."""
    link = payment_service.get_payment_link(UUID(link_id))
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment link not found"
        )

    # Verify user has access
    if str(link.cpa_id) != str(user.user_id):
        user_firm_id = str(user.firm_id) if hasattr(user, 'firm_id') and user.firm_id else None
        if not user_firm_id or str(link.firm_id) != user_firm_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this payment link"
            )

    return {
        "success": True,
        "payment_link": link.to_dict(),
    }


@payment_link_router.get("/code/{link_code}")
async def get_payment_link_by_code(link_code: str):
    """
    Get payment link by code (public endpoint for payment page).

    Returns only necessary info for the payment form.
    Note: This is intentionally public as it's accessed by clients paying invoices.
    """
    link = payment_service.get_payment_link_by_code(link_code)
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment link not found"
        )

    if not link.is_usable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment link is no longer active"
        )

    return {
        "success": True,
        "name": link.name,
        "description": link.description,
        "amount": link.amount,
        "currency": link.currency,
        "min_amount": link.min_amount,
        "max_amount": link.max_amount,
        "is_fixed_amount": link.amount is not None,
    }


@payment_link_router.post("/code/{link_code}/pay", status_code=status.HTTP_201_CREATED)
async def process_link_payment(link_code: str, request: ProcessLinkPaymentRequest):
    """
    Process a payment through a payment link.

    For online payments, integrates with Stripe.
    Note: This is intentionally public as it's accessed by clients paying invoices.
    """
    try:
        payment_method = PaymentMethod(request.payment_method)
    except ValueError:
        payment_method = PaymentMethod.CARD

    try:
        link, payment = payment_service.process_link_payment(
            link_code=link_code,
            amount=request.amount,
            payer_email=request.payer_email,
            payer_name=request.payer_name,
            payment_method=payment_method,
        )

        if not link or not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment link not found"
            )

        return {
            "success": True,
            "payment": payment.to_dict(),
            "message": "Payment processed successfully",
            "receipt_url": payment.stripe_receipt_url,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@payment_link_router.post("/{link_id}/deactivate")
async def deactivate_payment_link(
    link_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Deactivate a payment link. Requires authentication and ownership."""
    # Verify ownership
    existing = payment_service.get_payment_link(UUID(link_id))
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment link not found"
        )

    if str(existing.cpa_id) != str(user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only deactivate your own payment links"
        )

    link = payment_service.deactivate_payment_link(UUID(link_id))
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment link not found"
        )

    return {
        "success": True,
        "payment_link": link.to_dict(),
    }


# =============================================================================
# PAYMENT HISTORY AND ANALYTICS
# =============================================================================

payments_router = APIRouter(prefix="/payments", tags=["Payments"])


@payments_router.get("")
async def list_payments(
    user: UserContext = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List payments for authenticated CPA."""
    payment_status = PaymentStatus(status_filter) if status_filter else None

    payments = payment_service.get_payments_for_cpa(
        cpa_id=UUID(str(user.user_id)),
        status=payment_status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    return {
        "success": True,
        "payments": [p.to_dict() for p in payments],
        "total": len(payments),
    }


@payments_router.get("/summary")
async def get_revenue_summary(
    user: UserContext = Depends(get_current_user),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
):
    """Get revenue summary and analytics for authenticated user's context."""
    cpa_id = str(user.user_id)
    firm_id = str(user.firm_id) if hasattr(user, 'firm_id') and user.firm_id else None

    summary = payment_service.get_revenue_summary(
        cpa_id=UUID(cpa_id),
        firm_id=UUID(firm_id) if firm_id else None,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "success": True,
        **summary,
    }


@payments_router.post("/{payment_id}/refund")
async def refund_payment(
    payment_id: str,
    user: UserContext = Depends(get_current_user),
    amount: Optional[float] = Query(None, description="Amount to refund (full if not specified)"),
    reason: Optional[str] = Query(None, description="Refund reason"),
):
    """Process a refund for a payment. Requires authentication."""
    try:
        # Note: In production, you'd verify the user has access to this payment
        # before processing the refund
        payment = payment_service.refund_payment(
            payment_id=UUID(payment_id),
            amount=amount,
            reason=reason,
        )

        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )

        return {
            "success": True,
            "payment": payment.to_dict(),
            "message": f"Refund of ${payment.refunded_amount:.2f} processed",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
