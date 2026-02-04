"""
Payment Service

Handles CPA-to-Client payment processing via Stripe Connect.
Provides invoice management, payment links, and payment tracking.
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from .payment_models import (
    Invoice,
    InvoiceStatus,
    LineItem,
    Payment,
    PaymentStatus,
    PaymentMethod,
    PaymentLink,
)
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)


# Platform fee configuration
PLATFORM_FEE_PERCENT = 0.029  # 2.9%
PLATFORM_FEE_FIXED = 0.30     # $0.30 per transaction


class PaymentService:
    """
    Service for managing CPA-to-client payments.

    Features:
    - Invoice creation and management
    - Payment link generation
    - Stripe Connect payment processing
    - Offline payment tracking
    - Revenue analytics
    """

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._invoices: Dict[UUID, Invoice] = {}
        self._payments: Dict[UUID, Payment] = {}
        self._payment_links: Dict[UUID, PaymentLink] = {}
        self._links_by_code: Dict[str, UUID] = {}

        # Stripe configuration
        self._stripe_configured = bool(os.environ.get("STRIPE_SECRET_KEY"))

    # =========================================================================
    # INVOICE MANAGEMENT
    # =========================================================================

    def create_invoice(
        self,
        firm_id: UUID,
        cpa_id: UUID,
        cpa_name: str,
        firm_name: str,
        client_name: str,
        client_email: str,
        line_items: List[Dict[str, Any]],
        client_id: Optional[UUID] = None,
        client_address: Optional[str] = None,
        notes: Optional[str] = None,
        terms: Optional[str] = None,
        due_days: int = 30,
        currency: str = "USD",
        discount_amount: float = 0.0,
    ) -> Invoice:
        """
        Create a new invoice.

        Args:
            firm_id: Firm UUID
            cpa_id: CPA UUID
            cpa_name: CPA display name
            firm_name: Firm name
            client_name: Client name
            client_email: Client email
            line_items: List of line item dicts with description, amount, quantity, tax_rate
            client_id: Optional client UUID
            client_address: Optional client address
            notes: Optional invoice notes
            terms: Optional payment terms
            due_days: Days until due
            currency: Currency code
            discount_amount: Discount to apply

        Returns:
            Created Invoice
        """
        invoice = Invoice(
            firm_id=firm_id,
            cpa_id=cpa_id,
            cpa_name=cpa_name,
            firm_name=firm_name,
            client_id=client_id,
            client_name=client_name,
            client_email=client_email,
            client_address=client_address,
            notes=notes,
            terms=terms or "Payment due within 30 days of invoice date.",
            due_date=date.today() + timedelta(days=due_days),
            currency=currency,
            discount_amount=discount_amount,
        )

        # Add line items
        for item in line_items:
            invoice.add_line_item(
                description=item["description"],
                amount=item["amount"],
                quantity=item.get("quantity", 1),
                tax_rate=item.get("tax_rate", 0.0),
            )

        self._invoices[invoice.id] = invoice

        logger.info(
            f"Invoice {invoice.invoice_number} created: "
            f"${invoice.total_amount:.2f} for {client_name}"
        )

        return invoice

    def get_invoice(self, invoice_id: UUID) -> Optional[Invoice]:
        """Get invoice by ID."""
        return self._invoices.get(invoice_id)

    def get_invoice_by_number(self, invoice_number: str) -> Optional[Invoice]:
        """Get invoice by number."""
        for invoice in self._invoices.values():
            if invoice.invoice_number == invoice_number:
                return invoice
        return None

    def get_invoices_for_cpa(
        self,
        cpa_id: UUID,
        status: Optional[InvoiceStatus] = None,
        client_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Invoice]:
        """Get invoices for a CPA with optional filters."""
        invoices = []
        for invoice in self._invoices.values():
            if invoice.cpa_id != cpa_id:
                continue
            if status and invoice.status != status:
                continue
            if client_id and invoice.client_id != client_id:
                continue
            if start_date and invoice.issue_date < start_date:
                continue
            if end_date and invoice.issue_date > end_date:
                continue
            invoices.append(invoice)

        return sorted(invoices, key=lambda i: i.created_at, reverse=True)

    def get_invoices_for_firm(
        self,
        firm_id: UUID,
        status: Optional[InvoiceStatus] = None,
    ) -> List[Invoice]:
        """Get all invoices for a firm."""
        invoices = []
        for invoice in self._invoices.values():
            if invoice.firm_id != firm_id:
                continue
            if status and invoice.status != status:
                continue
            invoices.append(invoice)

        return sorted(invoices, key=lambda i: i.created_at, reverse=True)

    def update_invoice(
        self,
        invoice_id: UUID,
        notes: Optional[str] = None,
        terms: Optional[str] = None,
        due_date: Optional[date] = None,
    ) -> Optional[Invoice]:
        """Update invoice details (only for draft invoices)."""
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            return None

        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only update draft invoices")

        if notes is not None:
            invoice.notes = notes
        if terms is not None:
            invoice.terms = terms
        if due_date is not None:
            invoice.due_date = due_date

        invoice.updated_at = datetime.utcnow()
        return invoice

    def send_invoice(self, invoice_id: UUID) -> Optional[Invoice]:
        """
        Mark invoice as sent and generate payment link.

        In production, this would also send an email to the client.
        """
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            return None

        # Generate payment link
        payment_link = self._generate_invoice_payment_link(invoice)
        invoice.payment_link = payment_link

        invoice.mark_sent()

        logger.info(f"Invoice {invoice.invoice_number} sent to {invoice.client_email}")

        return invoice

    def record_payment(
        self,
        invoice_id: UUID,
        amount: float,
        payment_method: PaymentMethod = PaymentMethod.CARD,
        paid_date: Optional[date] = None,
    ) -> Tuple[Optional[Invoice], Optional[Payment]]:
        """Record a payment against an invoice."""
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            return None, None

        # Calculate platform fee
        platform_fee = self._calculate_platform_fee(amount)

        # Create payment record
        payment = Payment(
            firm_id=invoice.firm_id,
            cpa_id=invoice.cpa_id,
            client_id=invoice.client_id,
            client_name=invoice.client_name,
            client_email=invoice.client_email,
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            amount=amount,
            currency=invoice.currency,
            description=f"Payment for {invoice.invoice_number}",
            payment_method=payment_method,
            platform_fee=platform_fee,
            net_amount=amount - platform_fee,
            status=PaymentStatus.SUCCEEDED,
            completed_at=datetime.utcnow(),
        )

        self._payments[payment.id] = payment

        # Update invoice
        invoice.amount_paid += amount
        if invoice.is_paid:
            invoice.mark_paid(invoice.amount_paid, paid_date)

        invoice.updated_at = datetime.utcnow()

        return invoice, payment

    def void_invoice(self, invoice_id: UUID) -> Optional[Invoice]:
        """Void an invoice."""
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            return None

        if invoice.status == InvoiceStatus.PAID:
            raise ValueError("Cannot void a paid invoice")

        invoice.void()
        return invoice

    # =========================================================================
    # PAYMENT LINK MANAGEMENT
    # =========================================================================

    def create_payment_link(
        self,
        firm_id: UUID,
        cpa_id: UUID,
        name: str,
        description: Optional[str] = None,
        amount: Optional[float] = None,
        currency: str = "USD",
        max_uses: Optional[int] = None,
        expires_in_days: Optional[int] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
    ) -> PaymentLink:
        """
        Create a reusable payment link.

        Args:
            firm_id: Firm UUID
            cpa_id: CPA UUID
            name: Link name
            description: Link description
            amount: Fixed amount (None for variable)
            currency: Currency code
            max_uses: Maximum number of uses
            expires_in_days: Days until expiration
            min_amount: Minimum payment amount
            max_amount: Maximum payment amount

        Returns:
            Created PaymentLink
        """
        link = PaymentLink(
            firm_id=firm_id,
            cpa_id=cpa_id,
            name=name,
            description=description,
            amount=amount,
            currency=currency,
            max_uses=max_uses,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None,
            min_amount=min_amount,
            max_amount=max_amount,
        )

        self._payment_links[link.id] = link
        self._links_by_code[link.link_code] = link.id

        logger.info(f"Payment link created: {link.name} ({link.link_code})")

        return link

    def get_payment_link(self, link_id: UUID) -> Optional[PaymentLink]:
        """Get payment link by ID."""
        return self._payment_links.get(link_id)

    def get_payment_link_by_code(self, code: str) -> Optional[PaymentLink]:
        """Get payment link by code."""
        link_id = self._links_by_code.get(code)
        if link_id:
            return self._payment_links.get(link_id)
        return None

    def get_payment_links_for_cpa(
        self,
        cpa_id: UUID,
        active_only: bool = True,
    ) -> List[PaymentLink]:
        """Get payment links for a CPA."""
        links = []
        for link in self._payment_links.values():
            if link.cpa_id != cpa_id:
                continue
            if active_only and not link.is_usable:
                continue
            links.append(link)

        return sorted(links, key=lambda l: l.created_at, reverse=True)

    def deactivate_payment_link(self, link_id: UUID) -> Optional[PaymentLink]:
        """Deactivate a payment link."""
        link = self._payment_links.get(link_id)
        if link:
            link.is_active = False
        return link

    # =========================================================================
    # PAYMENT PROCESSING
    # =========================================================================

    def process_link_payment(
        self,
        link_code: str,
        amount: float,
        payer_email: str,
        payer_name: str,
        payment_method: PaymentMethod = PaymentMethod.CARD,
        stripe_payment_intent_id: Optional[str] = None,
    ) -> Tuple[Optional[PaymentLink], Optional[Payment]]:
        """
        Process a payment through a payment link.

        Args:
            link_code: Payment link code
            amount: Payment amount
            payer_email: Payer email
            payer_name: Payer name
            payment_method: Payment method used
            stripe_payment_intent_id: Stripe payment intent ID (for online payments)

        Returns:
            Tuple of (PaymentLink, Payment) or (None, None) if failed
        """
        link = self.get_payment_link_by_code(link_code)
        if not link:
            return None, None

        if not link.is_usable:
            raise ValueError("Payment link is no longer active")

        # Validate amount
        if link.amount and amount != link.amount:
            raise ValueError(f"Payment must be ${link.amount}")
        if link.min_amount and amount < link.min_amount:
            raise ValueError(f"Minimum payment is ${link.min_amount}")
        if link.max_amount and amount > link.max_amount:
            raise ValueError(f"Maximum payment is ${link.max_amount}")

        # Calculate platform fee
        platform_fee = self._calculate_platform_fee(amount)

        # Create payment record
        payment = Payment(
            firm_id=link.firm_id,
            cpa_id=link.cpa_id,
            client_name=payer_name,
            client_email=payer_email,
            amount=amount,
            currency=link.currency,
            description=f"Payment via link: {link.name}",
            payment_method=payment_method,
            platform_fee=platform_fee,
            net_amount=amount - platform_fee,
            stripe_payment_intent_id=stripe_payment_intent_id,
            status=PaymentStatus.SUCCEEDED,
            completed_at=datetime.utcnow(),
            metadata={"link_id": str(link.id), "link_code": link_code},
        )

        self._payments[payment.id] = payment

        # Update link usage
        link.record_use(amount)

        logger.info(
            f"Payment processed via link {link_code}: "
            f"${amount:.2f} from {payer_email}"
        )

        return link, payment

    def get_payments_for_cpa(
        self,
        cpa_id: UUID,
        status: Optional[PaymentStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Payment]:
        """Get payments for a CPA."""
        payments = []
        for payment in self._payments.values():
            if payment.cpa_id != cpa_id:
                continue
            if status and payment.status != status:
                continue
            if start_date and payment.created_at < start_date:
                continue
            if end_date and payment.created_at > end_date:
                continue
            payments.append(payment)

        # Sort by created_at descending and limit
        payments = sorted(payments, key=lambda p: p.created_at, reverse=True)
        return payments[:limit]

    def refund_payment(
        self,
        payment_id: UUID,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> Optional[Payment]:
        """
        Process a refund for a payment.

        Args:
            payment_id: Payment UUID
            amount: Amount to refund (full refund if None)
            reason: Reason for refund

        Returns:
            Updated Payment or None if not found
        """
        payment = self._payments.get(payment_id)
        if not payment:
            return None

        if payment.status not in [PaymentStatus.SUCCEEDED, PaymentStatus.PARTIALLY_REFUNDED]:
            raise ValueError("Can only refund successful payments")

        refund_amount = amount or payment.amount
        max_refundable = payment.amount - payment.refunded_amount

        if refund_amount > max_refundable:
            raise ValueError(f"Maximum refundable amount is ${max_refundable:.2f}")

        # In production, process refund via Stripe
        # stripe.Refund.create(payment_intent=payment.stripe_payment_intent_id, amount=int(refund_amount*100))

        payment.refund(refund_amount, reason)

        logger.info(
            f"Refund processed for payment {payment_id}: ${refund_amount:.2f}"
        )

        return payment

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_revenue_summary(
        self,
        cpa_id: Optional[UUID] = None,
        firm_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get revenue summary for CPA or firm.

        Returns aggregated payment statistics.
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        total_revenue = 0.0
        total_fees = 0.0
        net_revenue = 0.0
        payment_count = 0
        refund_total = 0.0

        for payment in self._payments.values():
            if cpa_id and payment.cpa_id != cpa_id:
                continue
            if firm_id and payment.firm_id != firm_id:
                continue
            if payment.created_at < start_date or payment.created_at > end_date:
                continue
            if payment.status == PaymentStatus.SUCCEEDED:
                total_revenue += payment.amount
                total_fees += payment.platform_fee
                net_revenue += payment.net_amount
                payment_count += 1
            if payment.refunded_amount > 0:
                refund_total += payment.refunded_amount

        # Invoice stats
        outstanding_invoices = 0
        outstanding_amount = 0.0
        overdue_invoices = 0
        overdue_amount = 0.0

        invoices = self._invoices.values()
        if cpa_id:
            invoices = [i for i in invoices if i.cpa_id == cpa_id]
        if firm_id:
            invoices = [i for i in invoices if i.firm_id == firm_id]

        for invoice in invoices:
            if invoice.status not in [InvoiceStatus.PAID, InvoiceStatus.VOID, InvoiceStatus.CANCELLED]:
                outstanding_invoices += 1
                outstanding_amount += invoice.balance_due
                if invoice.is_overdue:
                    overdue_invoices += 1
                    overdue_amount += invoice.balance_due

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "payments": {
                "count": payment_count,
                "total": total_revenue,
                "fees": total_fees,
                "net": net_revenue,
                "refunds": refund_total,
            },
            "invoices": {
                "outstanding_count": outstanding_invoices,
                "outstanding_amount": outstanding_amount,
                "overdue_count": overdue_invoices,
                "overdue_amount": overdue_amount,
            },
            "avg_payment": total_revenue / payment_count if payment_count > 0 else 0,
        }

    def get_overdue_invoices(
        self,
        cpa_id: Optional[UUID] = None,
        firm_id: Optional[UUID] = None,
    ) -> List[Invoice]:
        """Get list of overdue invoices."""
        overdue = []
        for invoice in self._invoices.values():
            if cpa_id and invoice.cpa_id != cpa_id:
                continue
            if firm_id and invoice.firm_id != firm_id:
                continue
            if invoice.is_overdue:
                overdue.append(invoice)

        return sorted(overdue, key=lambda i: i.due_date)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _calculate_platform_fee(self, amount: float) -> float:
        """Calculate platform fee for a payment."""
        return float(money(amount * PLATFORM_FEE_PERCENT + PLATFORM_FEE_FIXED))

    def _generate_invoice_payment_link(self, invoice: Invoice) -> str:
        """Generate a payment link for an invoice."""
        # In production, this would create a Stripe Checkout session
        # or Stripe Invoice with hosted payment page
        return f"/pay/invoice/{invoice.invoice_number}"


# Singleton instance
payment_service = PaymentService()
