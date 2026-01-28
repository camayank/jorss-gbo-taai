"""
Subscription Models - Billing and subscription management.

Supports tiered pricing (Starter, Professional, Enterprise) with
monthly/annual billing cycles.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Numeric, Text, ForeignKey, Index, CheckConstraint, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.models import Base, JSONB


class BillingCycle(str, PyEnum):
    """Billing cycle options."""
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(str, PyEnum):
    """Subscription status."""
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class InvoiceStatus(str, PyEnum):
    """Invoice status."""
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class SubscriptionPlan(Base):
    """
    Subscription Plan - Defines pricing tiers and features.

    Plans:
    - Starter: $199/month - 3 team members, 100 clients, basic features
    - Professional: $499/month - 10 team members, 500 clients, full features
    - Enterprise: $999/month - unlimited team/clients, API access, white-label
    """
    __tablename__ = "subscription_plans"

    # Primary Key
    plan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Plan Identity
    name = Column(String(50), nullable=False, comment="Display name")
    code = Column(String(20), unique=True, nullable=False, comment="starter, professional, enterprise")
    description = Column(Text, nullable=True)

    # Pricing
    monthly_price = Column(Numeric(10, 2), nullable=False)
    annual_price = Column(Numeric(10, 2), nullable=False, comment="Annual total (not monthly)")
    currency = Column(String(3), default="USD")

    # Limits
    max_team_members = Column(Integer, nullable=True, comment="NULL = unlimited")
    max_clients = Column(Integer, nullable=True)
    max_scenarios_per_month = Column(Integer, nullable=True)
    max_api_calls_per_month = Column(Integer, nullable=True)
    max_document_storage_gb = Column(Integer, default=10)

    # Features (JSON for flexibility)
    features = Column(JSONB, nullable=False, default=dict)
    # Example features:
    # {
    #     "scenario_analysis": true,
    #     "multi_state": true,
    #     "api_access": false,
    #     "white_label": false,
    #     "priority_support": false,
    #     "custom_domain": false,
    #     "sso": false,
    #     "audit_log_export": true
    # }

    # Display
    is_active = Column(Boolean, default=True, index=True)
    is_public = Column(Boolean, default=True, comment="Visible on pricing page")
    display_order = Column(Integer, default=0)
    highlight_text = Column(String(50), nullable=True, comment="e.g., 'Most Popular'")

    # Stripe Integration
    stripe_price_id_monthly = Column(String(255), nullable=True)
    stripe_price_id_annual = Column(String(255), nullable=True)
    stripe_product_id = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")

    __table_args__ = (
        Index("ix_plan_code", "code"),
        Index("ix_plan_active_public", "is_active", "is_public"),
        CheckConstraint("monthly_price >= 0", name="ck_plan_monthly_price"),
        CheckConstraint("annual_price >= 0", name="ck_plan_annual_price"),
    )

    def __repr__(self):
        return f"<SubscriptionPlan(code={self.code}, price=${self.monthly_price}/mo)>"

    @property
    def annual_monthly_price(self) -> Decimal:
        """Calculate monthly equivalent of annual price."""
        return self.annual_price / 12

    @property
    def annual_savings(self) -> Decimal:
        """Calculate savings from annual vs monthly."""
        return (self.monthly_price * 12) - self.annual_price

    @property
    def annual_savings_percent(self) -> int:
        """Calculate savings percentage from annual vs monthly."""
        monthly_total = self.monthly_price * 12
        if monthly_total == 0:
            return 0
        return int((self.annual_savings / monthly_total) * 100)

    def has_feature(self, feature_key: str) -> bool:
        """Check if plan includes a feature."""
        return self.features.get(feature_key, False)


class Subscription(Base):
    """
    Subscription - Active subscription for a firm.

    Tracks billing period, status, and payment information.
    """
    __tablename__ = "subscriptions"

    # Primary Key
    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Keys
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.plan_id"),
        nullable=False
    )

    # Billing
    billing_cycle = Column(
        Enum(BillingCycle),
        default=BillingCycle.MONTHLY,
        nullable=False
    )
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    next_billing_date = Column(DateTime, nullable=True)

    # Status
    status = Column(
        Enum(SubscriptionStatus),
        default=SubscriptionStatus.TRIALING,
        nullable=False,
        index=True
    )
    trial_end = Column(DateTime, nullable=True)

    # Cancellation
    cancelled_at = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    cancel_reason = Column(Text, nullable=True)
    cancelled_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)

    # Payment Method
    payment_method_type = Column(String(20), nullable=True, comment="card, bank_account")
    payment_method_last4 = Column(String(4), nullable=True)
    payment_method_brand = Column(String(20), nullable=True, comment="visa, mastercard, etc.")

    # Stripe Integration
    stripe_subscription_id = Column(String(255), nullable=True, unique=True)
    stripe_customer_id = Column(String(255), nullable=True)

    # Extra Data
    extra_data = Column(JSONB, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    firm = relationship("Firm", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    invoices = relationship("Invoice", back_populates="subscription", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_subscription_firm_status", "firm_id", "status"),
        Index("ix_subscription_next_billing", "next_billing_date"),
        Index("ix_subscription_stripe", "stripe_subscription_id"),
        Index("ix_subscription_plan_id", "plan_id"),
        Index("ix_subscription_cancelled_by", "cancelled_by"),
    )

    def __repr__(self):
        return f"<Subscription(firm_id={self.firm_id}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)

    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial."""
        return self.status == SubscriptionStatus.TRIALING

    @property
    def days_until_billing(self) -> Optional[int]:
        """Calculate days until next billing."""
        if self.next_billing_date is None:
            return None
        delta = self.next_billing_date - datetime.utcnow()
        return max(0, delta.days)


class Invoice(Base):
    """
    Invoice - Billing invoice for a subscription.

    Tracks amount, status, and payment history.
    """
    __tablename__ = "invoices"

    # Primary Key
    invoice_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Keys
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.subscription_id"),
        nullable=True
    )

    # Invoice Number
    invoice_number = Column(String(50), unique=True, nullable=False)

    # Amount
    subtotal = Column(Numeric(10, 2), nullable=False)
    tax = Column(Numeric(10, 2), default=0)
    discount = Column(Numeric(10, 2), default=0)
    amount_due = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), default=0)
    currency = Column(String(3), default="USD")

    # Period
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)

    # Status
    status = Column(
        Enum(InvoiceStatus),
        default=InvoiceStatus.DRAFT,
        nullable=False,
        index=True
    )
    due_date = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    voided_at = Column(DateTime, nullable=True)

    # Line Items
    line_items = Column(JSONB, default=list)
    # Example:
    # [
    #     {"description": "Professional Plan - Monthly", "quantity": 1, "unit_price": 499.00, "amount": 499.00},
    #     {"description": "Additional Team Member", "quantity": 2, "unit_price": 29.00, "amount": 58.00}
    # ]

    # Payment Details
    payment_method = Column(String(50), nullable=True)
    payment_intent_id = Column(String(255), nullable=True)

    # Stripe Integration
    stripe_invoice_id = Column(String(255), nullable=True, unique=True)
    invoice_pdf_url = Column(String(500), nullable=True)
    hosted_invoice_url = Column(String(500), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    firm = relationship("Firm")
    subscription = relationship("Subscription", back_populates="invoices")

    __table_args__ = (
        Index("ix_invoice_firm_status", "firm_id", "status"),
        Index("ix_invoice_due_date", "due_date"),
        Index("ix_invoice_stripe", "stripe_invoice_id"),
        Index("ix_invoice_subscription_id", "subscription_id"),
        CheckConstraint("amount_due >= 0", name="ck_invoice_amount_due"),
        CheckConstraint("amount_paid >= 0", name="ck_invoice_amount_paid"),
    )

    def __repr__(self):
        return f"<Invoice(number={self.invoice_number}, amount=${self.amount_due}, status={self.status})>"

    @property
    def balance_due(self) -> Decimal:
        """Calculate remaining balance."""
        return self.amount_due - self.amount_paid

    @property
    def is_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.status == InvoiceStatus.PAID or self.balance_due <= 0

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        if self.status in (InvoiceStatus.PAID, InvoiceStatus.VOID):
            return False
        if self.due_date is None:
            return False
        return datetime.utcnow() > self.due_date
