"""
Payment Module

CPA-to-Client payment processing via Stripe Connect.

Features:
- Invoice creation and management
- Payment link generation
- Online payment processing (Stripe)
- Offline payment tracking
- Revenue analytics

Usage:
    from cpa_panel.payments import payment_service

    # Create an invoice
    invoice = payment_service.create_invoice(
        firm_id=firm_id,
        cpa_id=cpa_id,
        cpa_name="Jane CPA",
        firm_name="Tax Pros LLC",
        client_name="John Client",
        client_email="john@example.com",
        line_items=[
            {"description": "Tax Preparation - 1040", "amount": 350.00},
            {"description": "State Return", "amount": 75.00},
        ],
    )

    # Create a payment link
    link = payment_service.create_payment_link(
        firm_id=firm_id,
        cpa_id=cpa_id,
        name="Tax Preparation",
        description="Standard tax preparation fee",
        amount=350.00,
    )
"""

from .payment_models import (
    Invoice,
    InvoiceStatus,
    LineItem,
    Payment,
    PaymentStatus,
    PaymentMethod,
    PaymentLink,
)
from .payment_service import (
    PaymentService,
    payment_service,
    PLATFORM_FEE_PERCENT,
    PLATFORM_FEE_FIXED,
)

__all__ = [
    # Models
    "Invoice",
    "InvoiceStatus",
    "LineItem",
    "Payment",
    "PaymentStatus",
    "PaymentMethod",
    "PaymentLink",
    # Service
    "PaymentService",
    "payment_service",
    "PLATFORM_FEE_PERCENT",
    "PLATFORM_FEE_FIXED",
]
