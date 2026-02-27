"""
Core Billing API Routes

Unified billing management endpoints for all user types:
- Subscriptions and plans
- Invoices and payments
- Payment methods
- Billing history

Access control is automatically applied based on UserContext.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel
import logging

from .auth_routes import get_current_user
from ..models.user import UserContext, UserType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Core Billing"])


# =============================================================================
# MODELS
# =============================================================================

class PlanTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Plan(BaseModel):
    """Subscription plan model."""
    id: str
    name: str
    tier: PlanTier
    description: str
    price_monthly: float
    price_annual: float
    features: List[str]
    limits: dict  # e.g., {"tax_returns": 5, "documents": 100}
    is_popular: bool = False


class Subscription(BaseModel):
    """User subscription model."""
    id: str
    user_id: str
    firm_id: Optional[str] = None
    plan_id: str
    plan_name: str
    plan_tier: PlanTier
    status: SubscriptionStatus
    billing_cycle: BillingCycle
    current_period_start: datetime
    current_period_end: datetime
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    created_at: datetime


class Invoice(BaseModel):
    """Invoice model."""
    id: str
    user_id: str
    firm_id: Optional[str] = None
    subscription_id: Optional[str] = None
    invoice_number: str
    status: InvoiceStatus
    subtotal: float
    tax: float
    total: float
    currency: str = "USD"
    due_date: datetime
    paid_at: Optional[datetime] = None
    created_at: datetime
    line_items: List[dict] = []


class PaymentMethod(BaseModel):
    """Payment method model."""
    id: str
    user_id: str
    type: str  # card, bank_account
    brand: Optional[str] = None  # visa, mastercard, etc.
    last_four: str
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    is_default: bool = False
    created_at: datetime


class CreateSubscriptionRequest(BaseModel):
    """Request to create a subscription."""
    plan_id: str
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    payment_method_id: Optional[str] = None


class AddPaymentMethodRequest(BaseModel):
    """Request to add a payment method."""
    type: str  # card, bank_account
    token: str  # Payment processor token


# =============================================================================
# MOCK DATA
# =============================================================================

_plans_db: dict = {}
_subscriptions_db: dict = {}
_invoices_db: dict = {}
_payment_methods_db: dict = {}


def _create_mock_data():
    """Create mock billing data for development."""
    import uuid

    now = datetime.utcnow()

    # Plans
    plans = [
        Plan(
            id="plan_free",
            name="Free",
            tier=PlanTier.FREE,
            description="Get started with basic tax tools",
            price_monthly=0,
            price_annual=0,
            features=[
                "1 tax return per year",
                "Basic document storage (100MB)",
                "Email support"
            ],
            limits={"tax_returns": 1, "documents": 10, "storage_mb": 100}
        ),
        Plan(
            id="plan_basic",
            name="Basic",
            tier=PlanTier.BASIC,
            description="Perfect for individual filers",
            price_monthly=14.99,
            price_annual=149.99,
            features=[
                "3 tax returns per year",
                "Document storage (1GB)",
                "Tax scenario modeling",
                "AI-powered recommendations",
                "Priority email support"
            ],
            limits={"tax_returns": 3, "documents": 50, "storage_mb": 1024},
            is_popular=True
        ),
        Plan(
            id="plan_professional",
            name="Professional",
            tier=PlanTier.PROFESSIONAL,
            description="For self-employed and small businesses",
            price_monthly=29.99,
            price_annual=299.99,
            features=[
                "Unlimited tax returns",
                "Document storage (10GB)",
                "Advanced scenario modeling",
                "Priority AI recommendations",
                "Phone & chat support",
                "Audit assistance"
            ],
            limits={"tax_returns": -1, "documents": 500, "storage_mb": 10240}
        ),
        Plan(
            id="plan_enterprise",
            name="Enterprise",
            tier=PlanTier.ENTERPRISE,
            description="For CPA firms and large organizations",
            price_monthly=99.99,
            price_annual=999.99,
            features=[
                "Unlimited everything",
                "Custom integrations",
                "Dedicated account manager",
                "SLA guarantee",
                "API access",
                "White-label options"
            ],
            limits={"tax_returns": -1, "documents": -1, "storage_mb": -1}
        )
    ]

    for plan in plans:
        _plans_db[plan.id] = plan

    # Subscriptions
    subscriptions = [
        Subscription(
            id=str(uuid.uuid4()),
            user_id="consumer-001",
            plan_id="plan_basic",
            plan_name="Basic",
            plan_tier=PlanTier.BASIC,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now - timedelta(days=15),
            current_period_end=now + timedelta(days=15),
            created_at=now - timedelta(days=45)
        ),
        Subscription(
            id=str(uuid.uuid4()),
            user_id="client-001",
            firm_id="firm-001",
            plan_id="plan_professional",
            plan_name="Professional",
            plan_tier=PlanTier.PROFESSIONAL,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.ANNUAL,
            current_period_start=now - timedelta(days=60),
            current_period_end=now + timedelta(days=305),
            created_at=now - timedelta(days=90)
        )
    ]

    for sub in subscriptions:
        _subscriptions_db[sub.id] = sub

    # Invoices
    invoices = [
        Invoice(
            id=str(uuid.uuid4()),
            user_id="consumer-001",
            invoice_number="INV-2024-0001",
            status=InvoiceStatus.PAID,
            subtotal=14.99,
            tax=1.20,
            total=16.19,
            due_date=now - timedelta(days=15),
            paid_at=now - timedelta(days=15),
            created_at=now - timedelta(days=20),
            line_items=[
                {"description": "Basic Plan - Monthly", "quantity": 1, "amount": 14.99}
            ]
        ),
        Invoice(
            id=str(uuid.uuid4()),
            user_id="consumer-001",
            invoice_number="INV-2024-0002",
            status=InvoiceStatus.SENT,
            subtotal=14.99,
            tax=1.20,
            total=16.19,
            due_date=now + timedelta(days=15),
            created_at=now,
            line_items=[
                {"description": "Basic Plan - Monthly", "quantity": 1, "amount": 14.99}
            ]
        )
    ]

    for inv in invoices:
        _invoices_db[inv.id] = inv

    # Payment methods
    payment_methods = [
        PaymentMethod(
            id=str(uuid.uuid4()),
            user_id="consumer-001",
            type="card",
            brand="visa",
            last_four="4242",
            exp_month=12,
            exp_year=2027,
            is_default=True,
            created_at=now - timedelta(days=60)
        )
    ]

    for pm in payment_methods:
        _payment_methods_db[pm.id] = pm


# Only populate mock data in development environments
import os as _os
_billing_env = _os.environ.get("APP_ENVIRONMENT", "").lower().strip()
if _billing_env in {"development", "dev", "local", "test", "testing"}:
    _create_mock_data()
else:
    logger.info(
        "Billing: skipping mock data in %s environment. "
        "Connect to billing provider for real plan/subscription data.",
        _billing_env or "unknown"
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _can_access_billing(context: UserContext, user_id: str, firm_id: Optional[str] = None) -> bool:
    """Check if user can access billing for a user/firm."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    if context.user_id == user_id:
        return True

    if context.user_type == UserType.CPA_TEAM and firm_id:
        if context.firm_id == firm_id and context.has_permission("manage_billing"):
            return True

    return False


# =============================================================================
# PLANS ENDPOINTS
# =============================================================================

@router.get("/plans", response_model=List[Plan])
async def list_plans():
    """
    Get all available subscription plans.

    Public endpoint - no authentication required.
    """
    return list(_plans_db.values())


@router.get("/plans/{plan_id}", response_model=Plan)
async def get_plan(plan_id: str):
    """Get a specific plan."""
    plan = _plans_db.get(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    return plan


# =============================================================================
# SUBSCRIPTION ENDPOINTS
# =============================================================================

@router.get("/subscription", response_model=Optional[Subscription])
async def get_my_subscription(
    context: UserContext = Depends(get_current_user)
):
    """
    Get current user's subscription.

    Returns the active subscription if one exists.
    """
    for sub in _subscriptions_db.values():
        if sub.user_id == context.user_id and sub.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]:
            return sub
    return None


@router.post("/subscription", response_model=Subscription)
async def create_subscription(
    request: CreateSubscriptionRequest,
    context: UserContext = Depends(get_current_user)
):
    """
    Create a new subscription.

    Upgrades user to the selected plan.
    """
    import uuid

    plan = _plans_db.get(request.plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    # Check for existing active subscription
    for sub in _subscriptions_db.values():
        if sub.user_id == context.user_id and sub.status == SubscriptionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active subscription already exists. Use upgrade/downgrade endpoint."
            )

    now = datetime.utcnow()
    period_days = 30 if request.billing_cycle == BillingCycle.MONTHLY else 365

    subscription = Subscription(
        id=str(uuid.uuid4()),
        user_id=context.user_id,
        firm_id=context.firm_id,
        plan_id=plan.id,
        plan_name=plan.name,
        plan_tier=plan.tier,
        status=SubscriptionStatus.TRIAL if plan.tier != PlanTier.FREE else SubscriptionStatus.ACTIVE,
        billing_cycle=request.billing_cycle,
        current_period_start=now,
        current_period_end=now + timedelta(days=period_days),
        trial_end=now + timedelta(days=14) if plan.tier != PlanTier.FREE else None,
        created_at=now
    )

    _subscriptions_db[subscription.id] = subscription

    logger.info(f"Subscription created: {subscription.id} for {context.user_id}")

    return subscription


@router.post("/subscription/cancel")
async def cancel_subscription(
    immediate: bool = False,
    context: UserContext = Depends(get_current_user)
):
    """
    Cancel current subscription.

    By default, cancels at end of current billing period.
    Set immediate=True to cancel immediately.
    """
    subscription = None
    for sub in _subscriptions_db.values():
        if sub.user_id == context.user_id and sub.status == SubscriptionStatus.ACTIVE:
            subscription = sub
            break

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )

    if immediate:
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.current_period_end = datetime.utcnow()
    else:
        subscription.cancel_at_period_end = True

    logger.info(f"Subscription cancelled: {subscription.id} immediate={immediate}")

    return {
        "success": True,
        "message": "Subscription cancelled" if immediate else "Subscription will cancel at end of billing period",
        "ends_at": subscription.current_period_end.isoformat()
    }


@router.post("/subscription/reactivate")
async def reactivate_subscription(
    context: UserContext = Depends(get_current_user)
):
    """Reactivate a cancelled subscription."""
    subscription = None
    for sub in _subscriptions_db.values():
        if sub.user_id == context.user_id:
            subscription = sub
            break

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found"
        )

    if subscription.status == SubscriptionStatus.ACTIVE and not subscription.cancel_at_period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is already active"
        )

    subscription.cancel_at_period_end = False
    if subscription.status == SubscriptionStatus.CANCELLED:
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.current_period_end = datetime.utcnow() + timedelta(days=30)

    logger.info(f"Subscription reactivated: {subscription.id}")

    return {"success": True, "message": "Subscription reactivated"}


@router.post("/subscription/change-plan")
async def change_subscription_plan(
    new_plan_id: str,
    context: UserContext = Depends(get_current_user)
):
    """
    Change subscription plan (upgrade/downgrade).

    Prorates the billing for the current period.
    """
    new_plan = _plans_db.get(new_plan_id)
    if not new_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    subscription = None
    for sub in _subscriptions_db.values():
        if sub.user_id == context.user_id and sub.status == SubscriptionStatus.ACTIVE:
            subscription = sub
            break

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )

    old_plan = subscription.plan_name
    subscription.plan_id = new_plan.id
    subscription.plan_name = new_plan.name
    subscription.plan_tier = new_plan.tier

    logger.info(f"Plan changed: {subscription.id} from {old_plan} to {new_plan.name}")

    return {
        "success": True,
        "message": f"Plan changed from {old_plan} to {new_plan.name}",
        "new_plan": new_plan
    }


# =============================================================================
# INVOICES ENDPOINTS
# =============================================================================

@router.get("/invoices", response_model=List[Invoice])
async def list_invoices(
    context: UserContext = Depends(get_current_user),
    status_filter: Optional[InvoiceStatus] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """
    List user's invoices.

    Returns invoices for the authenticated user.
    """
    results = []

    for invoice in _invoices_db.values():
        if not _can_access_billing(context, invoice.user_id, invoice.firm_id):
            continue

        if status_filter and invoice.status != status_filter:
            continue

        results.append(invoice)

    results.sort(key=lambda x: x.created_at, reverse=True)
    return results[offset:offset + limit]


@router.get("/invoices/{invoice_id}", response_model=Invoice)
async def get_invoice(
    invoice_id: str,
    context: UserContext = Depends(get_current_user)
):
    """Get a specific invoice."""
    invoice = _invoices_db.get(invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    if not _can_access_billing(context, invoice.user_id, invoice.firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return invoice


@router.post("/invoices/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: str,
    payment_method_id: Optional[str] = None,
    context: UserContext = Depends(get_current_user)
):
    """Pay an invoice."""
    invoice = _invoices_db.get(invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    if not _can_access_billing(context, invoice.user_id, invoice.firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice already paid"
        )

    # In production, this would process the payment
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.utcnow()

    logger.info(f"Invoice paid: {invoice_id}")

    return {"success": True, "message": "Payment successful", "invoice": invoice}


@router.get("/invoices/{invoice_id}/download")
async def download_invoice(
    invoice_id: str,
    context: UserContext = Depends(get_current_user)
):
    """Download invoice as PDF."""
    invoice = _invoices_db.get(invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    if not _can_access_billing(context, invoice.user_id, invoice.firm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # In production, this would generate and return a PDF
    return {
        "download_url": f"/invoices/{invoice_id}/invoice_{invoice.invoice_number}.pdf",
        "expires_in": 3600
    }


# =============================================================================
# PAYMENT METHODS ENDPOINTS
# =============================================================================

@router.get("/payment-methods", response_model=List[PaymentMethod])
async def list_payment_methods(
    context: UserContext = Depends(get_current_user)
):
    """List user's payment methods."""
    return [
        pm for pm in _payment_methods_db.values()
        if pm.user_id == context.user_id
    ]


@router.post("/payment-methods", response_model=PaymentMethod)
async def add_payment_method(
    request: AddPaymentMethodRequest,
    context: UserContext = Depends(get_current_user)
):
    """Add a new payment method."""
    import uuid

    # In production, this would validate the token with payment processor
    payment_method = PaymentMethod(
        id=str(uuid.uuid4()),
        user_id=context.user_id,
        type=request.type,
        brand="visa",  # Would come from processor
        last_four="4242",  # Would come from processor
        exp_month=12,
        exp_year=2027,
        is_default=len([pm for pm in _payment_methods_db.values() if pm.user_id == context.user_id]) == 0,
        created_at=datetime.utcnow()
    )

    _payment_methods_db[payment_method.id] = payment_method

    logger.info(f"Payment method added: {payment_method.id}")

    return payment_method


@router.delete("/payment-methods/{method_id}")
async def remove_payment_method(
    method_id: str,
    context: UserContext = Depends(get_current_user)
):
    """Remove a payment method."""
    pm = _payment_methods_db.get(method_id)
    if not pm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )

    if pm.user_id != context.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if pm.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove default payment method"
        )

    del _payment_methods_db[method_id]

    return {"success": True, "message": "Payment method removed"}


@router.post("/payment-methods/{method_id}/set-default")
async def set_default_payment_method(
    method_id: str,
    context: UserContext = Depends(get_current_user)
):
    """Set a payment method as default."""
    pm = _payment_methods_db.get(method_id)
    if not pm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )

    if pm.user_id != context.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Unset other defaults
    for other_pm in _payment_methods_db.values():
        if other_pm.user_id == context.user_id:
            other_pm.is_default = (other_pm.id == method_id)

    return {"success": True, "message": "Default payment method updated"}


# =============================================================================
# USAGE ENDPOINTS
# =============================================================================

@router.get("/usage")
async def get_usage(
    context: UserContext = Depends(get_current_user)
):
    """
    Get current billing period usage.

    Shows usage against plan limits.
    """
    # Find active subscription
    subscription = None
    for sub in _subscriptions_db.values():
        if sub.user_id == context.user_id and sub.status == SubscriptionStatus.ACTIVE:
            subscription = sub
            break

    if not subscription:
        # Free tier usage
        return {
            "plan": "Free",
            "usage": {
                "tax_returns": {"used": 0, "limit": 1},
                "documents": {"used": 0, "limit": 10},
                "storage_mb": {"used": 0, "limit": 100}
            }
        }

    plan = _plans_db.get(subscription.plan_id)
    limits = plan.limits if plan else {}

    # In production, this would query actual usage
    return {
        "plan": subscription.plan_name,
        "billing_cycle": subscription.billing_cycle,
        "period_start": subscription.current_period_start.isoformat(),
        "period_end": subscription.current_period_end.isoformat(),
        "usage": {
            "tax_returns": {
                "used": 2,
                "limit": limits.get("tax_returns", -1)
            },
            "documents": {
                "used": 15,
                "limit": limits.get("documents", -1)
            },
            "storage_mb": {
                "used": 45,
                "limit": limits.get("storage_mb", -1)
            }
        }
    }
