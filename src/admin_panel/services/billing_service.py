"""
Billing Service - Subscription and invoice management.

Handles:
- Subscription lifecycle
- Plan upgrades/downgrades
- Invoice generation
- Usage-based billing
- Payment processing integration
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
from decimal import Decimal
import logging

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.subscription import (
    Subscription,
    SubscriptionPlan,
    Invoice,
    SubscriptionStatus,
    BillingCycle,
    InvoiceStatus,
)
from ..models.firm import Firm
from ..models.usage import UsageMetrics


logger = logging.getLogger(__name__)


class BillingService:
    """Service for billing and subscription management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # SUBSCRIPTION PLANS
    # =========================================================================

    async def list_plans(self) -> List[Dict[str, Any]]:
        """List all available subscription plans."""
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
            .order_by(SubscriptionPlan.monthly_price)
        )
        plans = result.scalars().all()

        return [self._plan_to_dict(p) for p in plans]

    async def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific plan by ID."""
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.plan_id == plan_id)
        )
        plan = result.scalar_one_or_none()

        if not plan:
            return None

        return self._plan_to_dict(plan)

    async def get_plan_by_tier(self, tier: str) -> Optional[Dict[str, Any]]:
        """Get plan by tier name."""
        result = await self.db.execute(
            select(SubscriptionPlan).where(
                and_(
                    SubscriptionPlan.tier == tier,
                    SubscriptionPlan.is_active == True,
                )
            )
        )
        plan = result.scalar_one_or_none()

        if not plan:
            return None

        return self._plan_to_dict(plan)

    # =========================================================================
    # SUBSCRIPTIONS
    # =========================================================================

    async def get_subscription(self, firm_id: str) -> Optional[Dict[str, Any]]:
        """Get current subscription for a firm."""
        result = await self.db.execute(
            select(Subscription).where(
                and_(
                    Subscription.firm_id == firm_id,
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.TRIALING.value,
                        SubscriptionStatus.PAST_DUE.value,
                    ])
                )
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            return None

        # Get plan details
        plan = await self.get_plan(str(subscription.plan_id))

        return {
            "subscription_id": str(subscription.subscription_id),
            "firm_id": str(subscription.firm_id),
            "plan": plan,
            "status": subscription.status,
            "billing_cycle": subscription.billing_cycle,
            "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "trial_ends_at": subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "canceled_at": subscription.canceled_at.isoformat() if subscription.canceled_at else None,
        }

    async def create_subscription(
        self,
        firm_id: str,
        plan_id: str,
        billing_cycle: str = "monthly",
        trial_days: int = 14,
    ) -> Dict[str, Any]:
        """Create a new subscription for a firm."""
        now = datetime.utcnow()
        subscription_id = str(uuid4())

        # Get plan
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.plan_id == plan_id)
        )
        plan = plan_result.scalar_one_or_none()

        if not plan:
            return {"error": "Invalid plan"}

        subscription = Subscription(
            subscription_id=subscription_id,
            firm_id=firm_id,
            plan_id=plan_id,
            status=SubscriptionStatus.TRIALING.value,
            billing_cycle=billing_cycle,
            current_period_start=now,
            current_period_end=now + timedelta(days=trial_days),
            trial_ends_at=now + timedelta(days=trial_days),
            created_at=now,
        )
        self.db.add(subscription)

        # Update firm subscription info
        firm_result = await self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        )
        firm = firm_result.scalar_one_or_none()
        if firm:
            firm.subscription_tier = plan.tier
            firm.subscription_status = "trial"
            firm.max_team_members = plan.max_team_members
            firm.max_clients = plan.max_clients

        await self.db.commit()
        logger.info(f"Created subscription {subscription_id} for firm {firm_id}")

        return await self.get_subscription(firm_id)

    async def change_plan(
        self,
        firm_id: str,
        new_plan_id: str,
        immediate: bool = False,
    ) -> Dict[str, Any]:
        """Change subscription plan (upgrade/downgrade)."""
        # Get current subscription
        sub_result = await self.db.execute(
            select(Subscription).where(
                and_(
                    Subscription.firm_id == firm_id,
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.TRIALING.value,
                    ])
                )
            )
        )
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            return {"error": "No active subscription found"}

        # Get new plan
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.plan_id == new_plan_id)
        )
        new_plan = plan_result.scalar_one_or_none()

        if not new_plan:
            return {"error": "Invalid plan"}

        old_plan_id = subscription.plan_id

        if immediate:
            # Apply immediately with prorated billing
            subscription.plan_id = new_plan_id
            subscription.updated_at = datetime.utcnow()

            # Update firm limits
            firm_result = await self.db.execute(
                select(Firm).where(Firm.firm_id == firm_id)
            )
            firm = firm_result.scalar_one_or_none()
            if firm:
                firm.subscription_tier = new_plan.tier
                firm.max_team_members = new_plan.max_team_members
                firm.max_clients = new_plan.max_clients

            await self.db.commit()

            logger.info(f"Immediately changed plan for firm {firm_id} from {old_plan_id} to {new_plan_id}")

            return {
                "status": "changed",
                "effective": "immediate",
                "new_plan": self._plan_to_dict(new_plan),
            }
        else:
            # Schedule change at period end
            subscription.scheduled_plan_id = new_plan_id
            subscription.updated_at = datetime.utcnow()

            await self.db.commit()

            logger.info(f"Scheduled plan change for firm {firm_id} at period end")

            return {
                "status": "scheduled",
                "effective": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                "new_plan": self._plan_to_dict(new_plan),
            }

    async def cancel_subscription(
        self,
        firm_id: str,
        immediate: bool = False,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel a subscription."""
        sub_result = await self.db.execute(
            select(Subscription).where(
                and_(
                    Subscription.firm_id == firm_id,
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.TRIALING.value,
                    ])
                )
            )
        )
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            return {"error": "No active subscription found"}

        now = datetime.utcnow()

        if immediate:
            subscription.status = SubscriptionStatus.CANCELED.value
            subscription.canceled_at = now
            subscription.cancellation_reason = reason

            # Update firm
            firm_result = await self.db.execute(
                select(Firm).where(Firm.firm_id == firm_id)
            )
            firm = firm_result.scalar_one_or_none()
            if firm:
                firm.subscription_status = "canceled"

            await self.db.commit()

            return {
                "status": "canceled",
                "effective": "immediate",
            }
        else:
            subscription.cancel_at_period_end = True
            subscription.cancellation_reason = reason
            subscription.updated_at = now

            await self.db.commit()

            return {
                "status": "scheduled_cancellation",
                "effective": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            }

    async def reactivate_subscription(self, firm_id: str) -> Dict[str, Any]:
        """Reactivate a canceled subscription."""
        sub_result = await self.db.execute(
            select(Subscription).where(
                and_(
                    Subscription.firm_id == firm_id,
                    or_(
                        Subscription.cancel_at_period_end == True,
                        Subscription.status == SubscriptionStatus.CANCELED.value,
                    )
                )
            )
        )
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            return {"error": "No canceled subscription found"}

        subscription.cancel_at_period_end = False
        subscription.cancellation_reason = None

        if subscription.status == SubscriptionStatus.CANCELED.value:
            # Reactivate with new period
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.current_period_start = datetime.utcnow()
            subscription.current_period_end = datetime.utcnow() + timedelta(days=30)

        subscription.updated_at = datetime.utcnow()

        # Update firm
        firm_result = await self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        )
        firm = firm_result.scalar_one_or_none()
        if firm:
            firm.subscription_status = "active"

        await self.db.commit()

        return {"status": "reactivated"}

    # =========================================================================
    # INVOICES
    # =========================================================================

    async def list_invoices(
        self,
        firm_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List invoices for a firm."""
        result = await self.db.execute(
            select(Invoice).where(Invoice.firm_id == firm_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        invoices = result.scalars().all()

        return [self._invoice_to_dict(inv) for inv in invoices]

    async def get_invoice(
        self,
        firm_id: str,
        invoice_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a specific invoice."""
        result = await self.db.execute(
            select(Invoice).where(
                and_(Invoice.firm_id == firm_id, Invoice.invoice_id == invoice_id)
            )
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            return None

        return self._invoice_to_dict(invoice, include_line_items=True)

    async def generate_invoice(
        self,
        firm_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Dict[str, Any]:
        """Generate an invoice for a billing period."""
        # Get subscription
        sub_result = await self.db.execute(
            select(Subscription).where(
                and_(
                    Subscription.firm_id == firm_id,
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
            )
        )
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            return {"error": "No active subscription"}

        # Get plan pricing
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.plan_id == subscription.plan_id
            )
        )
        plan = plan_result.scalar_one_or_none()

        if not plan:
            return {"error": "Invalid plan"}

        # Calculate amount
        if subscription.billing_cycle == BillingCycle.MONTHLY.value:
            subtotal = float(plan.monthly_price)
        else:
            subtotal = float(plan.annual_price)

        # Get usage for overage (if any)
        usage_charges = await self._calculate_usage_charges(firm_id, period_start, period_end)

        subtotal += usage_charges
        tax = subtotal * 0.0  # Tax calculation would go here
        total = subtotal + tax

        # Create invoice
        invoice_id = str(uuid4())
        invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m')}-{invoice_id[:8].upper()}"

        invoice = Invoice(
            invoice_id=invoice_id,
            firm_id=firm_id,
            subscription_id=str(subscription.subscription_id),
            invoice_number=invoice_number,
            status=InvoiceStatus.PENDING.value,
            subtotal=Decimal(str(subtotal)),
            tax=Decimal(str(tax)),
            total=Decimal(str(total)),
            currency="USD",
            period_start=period_start,
            period_end=period_end,
            due_date=datetime.utcnow() + timedelta(days=30),
            line_items=[
                {
                    "description": f"{plan.name} - {subscription.billing_cycle}",
                    "amount": float(plan.monthly_price if subscription.billing_cycle == BillingCycle.MONTHLY.value else plan.annual_price),
                    "quantity": 1,
                }
            ],
            created_at=datetime.utcnow(),
        )

        if usage_charges > 0:
            invoice.line_items.append({
                "description": "Usage overage charges",
                "amount": usage_charges,
                "quantity": 1,
            })

        self.db.add(invoice)
        await self.db.commit()

        logger.info(f"Generated invoice {invoice_number} for firm {firm_id}")

        return self._invoice_to_dict(invoice)

    async def mark_invoice_paid(
        self,
        invoice_id: str,
        payment_id: Optional[str] = None,
    ) -> bool:
        """Mark an invoice as paid."""
        result = await self.db.execute(
            select(Invoice).where(Invoice.invoice_id == invoice_id)
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            return False

        invoice.status = InvoiceStatus.PAID.value
        invoice.paid_at = datetime.utcnow()
        invoice.payment_id = payment_id

        await self.db.commit()
        return True

    # =========================================================================
    # USAGE TRACKING
    # =========================================================================

    async def get_usage_summary(
        self,
        firm_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get usage summary for billing period."""
        if not period_start:
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        if not period_end:
            period_end = datetime.utcnow()

        # Get firm limits
        firm_result = await self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        )
        firm = firm_result.scalar_one_or_none()

        if not firm:
            return {}

        # Get usage metrics
        usage_result = await self.db.execute(
            select(UsageMetrics).where(
                and_(
                    UsageMetrics.firm_id == firm_id,
                    UsageMetrics.period_start >= period_start,
                    UsageMetrics.period_end <= period_end,
                )
            )
        )
        metrics = usage_result.scalars().all()

        # Aggregate
        totals = {
            "returns_processed": 0,
            "scenarios_run": 0,
            "documents_uploaded": 0,
            "api_calls": 0,
        }

        for m in metrics:
            totals["returns_processed"] += m.returns_processed or 0
            totals["scenarios_run"] += m.scenarios_run or 0
            totals["documents_uploaded"] += m.documents_uploaded or 0
            totals["api_calls"] += m.api_calls or 0

        return {
            "firm_id": firm_id,
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
            "usage": totals,
            "limits": {
                "team_members": firm.max_team_members,
                "clients": firm.max_clients,
            },
        }

    async def _calculate_usage_charges(
        self,
        firm_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> float:
        """Calculate overage charges for usage."""
        # For now, return 0 - can be expanded for usage-based pricing
        return 0.0

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _plan_to_dict(self, plan: SubscriptionPlan) -> Dict[str, Any]:
        """Convert plan model to dictionary."""
        return {
            "plan_id": str(plan.plan_id),
            "tier": plan.tier,
            "name": plan.name,
            "description": plan.description,
            "monthly_price": float(plan.monthly_price),
            "annual_price": float(plan.annual_price),
            "max_team_members": plan.max_team_members,
            "max_clients": plan.max_clients,
            "features": plan.features or [],
            "is_active": plan.is_active,
        }

    def _invoice_to_dict(
        self,
        invoice: Invoice,
        include_line_items: bool = False,
    ) -> Dict[str, Any]:
        """Convert invoice model to dictionary."""
        data = {
            "invoice_id": str(invoice.invoice_id),
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "subtotal": float(invoice.subtotal),
            "tax": float(invoice.tax),
            "total": float(invoice.total),
            "currency": invoice.currency,
            "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
            "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        }

        if include_line_items:
            data["line_items"] = invoice.line_items or []

        return data
