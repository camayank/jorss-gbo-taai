"""
Payment Models

Data models for CPA-to-Client payment processing via Stripe Connect.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID, uuid4


class PaymentStatus(str, Enum):
    """Status of a payment."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    CANCELLED = "cancelled"


class InvoiceStatus(str, Enum):
    """Status of an invoice."""
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    VOID = "void"


class PaymentMethod(str, Enum):
    """Payment methods."""
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    CHECK = "check"
    CASH = "cash"
    OTHER = "other"


@dataclass
class LineItem:
    """Invoice line item."""
    description: str
    amount: float
    quantity: int = 1
    tax_rate: float = 0.0

    @property
    def subtotal(self) -> float:
        """Calculate subtotal before tax."""
        return self.amount * self.quantity

    @property
    def tax_amount(self) -> float:
        """Calculate tax amount."""
        return self.subtotal * self.tax_rate

    @property
    def total(self) -> float:
        """Calculate total including tax."""
        return self.subtotal + self.tax_amount

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "amount": self.amount,
            "quantity": self.quantity,
            "tax_rate": self.tax_rate,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "total": self.total,
        }


@dataclass
class Invoice:
    """
    Invoice for CPA services.

    CPAs can create invoices for their clients which can be paid
    online via Stripe or tracked for offline payments.
    """
    id: UUID = field(default_factory=uuid4)
    invoice_number: str = ""

    # Firm/CPA
    firm_id: UUID = None
    cpa_id: UUID = None
    cpa_name: str = ""
    firm_name: str = ""

    # Client
    client_id: Optional[UUID] = None
    client_name: str = ""
    client_email: str = ""
    client_address: Optional[str] = None

    # Invoice details
    line_items: List[LineItem] = field(default_factory=list)
    notes: Optional[str] = None
    terms: Optional[str] = None

    # Amounts
    subtotal: float = 0.0
    tax_total: float = 0.0
    discount_amount: float = 0.0
    total_amount: float = 0.0
    amount_paid: float = 0.0
    currency: str = "USD"

    # Dates
    issue_date: date = field(default_factory=date.today)
    due_date: date = None
    paid_date: Optional[date] = None

    # Status
    status: InvoiceStatus = InvoiceStatus.DRAFT

    # Payment
    payment_link: Optional[str] = None
    stripe_invoice_id: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None

    def __post_init__(self):
        """Generate invoice number and set defaults."""
        if not self.invoice_number:
            prefix = datetime.now().strftime("%Y%m")
            self.invoice_number = f"INV-{prefix}-{str(uuid4())[:8].upper()}"

        if self.due_date is None:
            from datetime import timedelta
            self.due_date = self.issue_date + timedelta(days=30)

        self.recalculate_totals()

    def add_line_item(
        self,
        description: str,
        amount: float,
        quantity: int = 1,
        tax_rate: float = 0.0,
    ):
        """Add a line item to the invoice."""
        item = LineItem(
            description=description,
            amount=amount,
            quantity=quantity,
            tax_rate=tax_rate,
        )
        self.line_items.append(item)
        self.recalculate_totals()

    def recalculate_totals(self):
        """Recalculate invoice totals from line items."""
        self.subtotal = sum(item.subtotal for item in self.line_items)
        self.tax_total = sum(item.tax_amount for item in self.line_items)
        self.total_amount = self.subtotal + self.tax_total - self.discount_amount

    @property
    def balance_due(self) -> float:
        """Calculate balance due."""
        return max(0, self.total_amount - self.amount_paid)

    @property
    def is_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.amount_paid >= self.total_amount

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        return (
            self.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.VOID]
            and date.today() > self.due_date
        )

    @property
    def days_overdue(self) -> int:
        """Get number of days overdue."""
        if not self.is_overdue:
            return 0
        return (date.today() - self.due_date).days

    def mark_sent(self):
        """Mark invoice as sent."""
        self.status = InvoiceStatus.SENT
        self.sent_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_paid(self, amount: float = None, paid_date: date = None):
        """Mark invoice as paid."""
        self.amount_paid = amount or self.total_amount
        self.paid_date = paid_date or date.today()
        self.status = InvoiceStatus.PAID
        self.updated_at = datetime.utcnow()

    def void(self):
        """Void the invoice."""
        self.status = InvoiceStatus.VOID
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "invoice_number": self.invoice_number,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "cpa_id": str(self.cpa_id) if self.cpa_id else None,
            "cpa_name": self.cpa_name,
            "firm_name": self.firm_name,
            "client_id": str(self.client_id) if self.client_id else None,
            "client_name": self.client_name,
            "client_email": self.client_email,
            "client_address": self.client_address,
            "line_items": [item.to_dict() for item in self.line_items],
            "notes": self.notes,
            "terms": self.terms,
            "subtotal": self.subtotal,
            "tax_total": self.tax_total,
            "discount_amount": self.discount_amount,
            "total_amount": self.total_amount,
            "amount_paid": self.amount_paid,
            "balance_due": self.balance_due,
            "currency": self.currency,
            "issue_date": self.issue_date.isoformat(),
            "due_date": self.due_date.isoformat(),
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "status": self.status.value,
            "is_paid": self.is_paid,
            "is_overdue": self.is_overdue,
            "days_overdue": self.days_overdue,
            "payment_link": self.payment_link,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }


@dataclass
class Payment:
    """
    Payment record for tracking client payments.

    Tracks both online (Stripe) and offline (check, cash) payments.
    """
    id: UUID = field(default_factory=uuid4)

    # Firm/CPA
    firm_id: UUID = None
    cpa_id: UUID = None

    # Client
    client_id: Optional[UUID] = None
    client_name: str = ""
    client_email: str = ""

    # Invoice (optional - payments can be without invoice)
    invoice_id: Optional[UUID] = None
    invoice_number: Optional[str] = None

    # Payment details
    amount: float = 0.0
    currency: str = "USD"
    description: str = ""
    payment_method: PaymentMethod = PaymentMethod.CARD

    # Stripe details (for online payments)
    stripe_payment_intent_id: Optional[str] = None
    stripe_charge_id: Optional[str] = None
    stripe_receipt_url: Optional[str] = None

    # Platform fee
    platform_fee: float = 0.0
    net_amount: float = 0.0

    # Status
    status: PaymentStatus = PaymentStatus.PENDING

    # Refund tracking
    refunded_amount: float = 0.0
    refund_reason: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate net amount."""
        if self.net_amount == 0.0 and self.amount > 0:
            self.net_amount = self.amount - self.platform_fee

    def mark_succeeded(self, charge_id: str = None, receipt_url: str = None):
        """Mark payment as succeeded."""
        self.status = PaymentStatus.SUCCEEDED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if charge_id:
            self.stripe_charge_id = charge_id
        if receipt_url:
            self.stripe_receipt_url = receipt_url

    def mark_failed(self, reason: str = None):
        """Mark payment as failed."""
        self.status = PaymentStatus.FAILED
        self.updated_at = datetime.utcnow()
        if reason:
            self.metadata["failure_reason"] = reason

    def refund(self, amount: float = None, reason: str = None):
        """Process a refund."""
        refund_amount = amount or self.amount
        self.refunded_amount = refund_amount
        self.refund_reason = reason
        self.updated_at = datetime.utcnow()

        if refund_amount >= self.amount:
            self.status = PaymentStatus.REFUNDED
        else:
            self.status = PaymentStatus.PARTIALLY_REFUNDED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "cpa_id": str(self.cpa_id) if self.cpa_id else None,
            "client_id": str(self.client_id) if self.client_id else None,
            "client_name": self.client_name,
            "client_email": self.client_email,
            "invoice_id": str(self.invoice_id) if self.invoice_id else None,
            "invoice_number": self.invoice_number,
            "amount": self.amount,
            "currency": self.currency,
            "description": self.description,
            "payment_method": self.payment_method.value,
            "platform_fee": self.platform_fee,
            "net_amount": self.net_amount,
            "status": self.status.value,
            "refunded_amount": self.refunded_amount,
            "stripe_receipt_url": self.stripe_receipt_url,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class PaymentLink:
    """
    Reusable payment link for clients.

    CPAs can create payment links that clients can use to pay
    for specific services or any amount.
    """
    id: UUID = field(default_factory=uuid4)
    link_code: str = ""

    # Firm/CPA
    firm_id: UUID = None
    cpa_id: UUID = None

    # Link details
    name: str = ""
    description: Optional[str] = None
    amount: Optional[float] = None  # None = client enters amount
    currency: str = "USD"

    # Restrictions
    max_uses: Optional[int] = None
    expires_at: Optional[datetime] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None

    # Status
    is_active: bool = True
    uses_count: int = 0
    total_collected: float = 0.0

    # Stripe
    stripe_price_id: Optional[str] = None
    stripe_payment_link_id: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Generate link code if not provided."""
        if not self.link_code:
            import secrets
            self.link_code = secrets.token_urlsafe(16)

    @property
    def url(self) -> str:
        """Get the payment link URL."""
        # This would be configured based on the platform URL
        return f"/pay/{self.link_code}"

    @property
    def is_expired(self) -> bool:
        """Check if link has expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False

    @property
    def is_at_max_uses(self) -> bool:
        """Check if link has reached max uses."""
        if self.max_uses:
            return self.uses_count >= self.max_uses
        return False

    @property
    def is_usable(self) -> bool:
        """Check if link can still be used."""
        return self.is_active and not self.is_expired and not self.is_at_max_uses

    def record_use(self, amount: float):
        """Record a payment using this link."""
        self.uses_count += 1
        self.total_collected += amount

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "link_code": self.link_code,
            "url": self.url,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "cpa_id": str(self.cpa_id) if self.cpa_id else None,
            "name": self.name,
            "description": self.description,
            "amount": self.amount,
            "currency": self.currency,
            "max_uses": self.max_uses,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "is_active": self.is_active,
            "is_usable": self.is_usable,
            "uses_count": self.uses_count,
            "total_collected": self.total_collected,
            "created_at": self.created_at.isoformat(),
        }
