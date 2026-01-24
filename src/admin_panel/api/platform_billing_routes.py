"""
Platform Billing Routes - Super admin billing management.

Provides:
- Platform payment method configuration
- Subscription tier management
- Revenue tracking
- Bank account settings (Mercury/India)
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.rbac import get_current_user, TenantContext, require_platform_admin
from ..services.platform_billing_config import (
    get_platform_billing_config,
    PaymentMethod,
)
from database.async_engine import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platform-billing", tags=["Platform Billing"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class PaymentMethodInfo(BaseModel):
    """Payment method information."""
    method: str
    name: str
    description: str
    automated: bool
    enabled: bool
    bank_details: Optional[dict] = None


class PlatformBillingSettings(BaseModel):
    """Platform billing settings."""
    stripe_enabled: bool
    mercury_enabled: bool
    india_bank_enabled: bool
    platform_fee_percent: float
    platform_fee_fixed: float
    payment_methods: List[PaymentMethodInfo]


class RevenueMetrics(BaseModel):
    """Platform revenue metrics."""
    mrr: float
    arr: float
    mrr_growth_percent: float
    total_cpas: int
    active_subscriptions: int
    churn_rate: float
    by_tier: dict
    by_payment_method: dict


class SubscriptionTier(BaseModel):
    """Subscription tier definition."""
    tier: str
    name: str
    price_monthly: float
    price_annual: float
    features: dict


# =============================================================================
# ROUTES
# =============================================================================

@router.get("/settings", response_model=PlatformBillingSettings)
@require_platform_admin
async def get_billing_settings(
    user: TenantContext = Depends(get_current_user),
):
    """
    Get platform billing settings.

    Super admin only. Shows all payment method configurations.
    """
    config = get_platform_billing_config()

    methods = []
    for m in config.get_available_payment_methods():
        methods.append(PaymentMethodInfo(
            method=m["method"],
            name=m["name"],
            description=m["description"],
            automated=m["automated"],
            enabled=True,
            bank_details=m.get("bank_details"),
        ))

    return PlatformBillingSettings(
        stripe_enabled=config.stripe_enabled,
        mercury_enabled=config.mercury_enabled,
        india_bank_enabled=config.india_bank_enabled,
        platform_fee_percent=config.platform_fee_percent,
        platform_fee_fixed=config.platform_fee_fixed,
        payment_methods=methods,
    )


@router.get("/tiers", response_model=List[SubscriptionTier])
@require_platform_admin
async def get_subscription_tiers(
    user: TenantContext = Depends(get_current_user),
):
    """Get all subscription tiers."""
    config = get_platform_billing_config()

    tiers = []
    for t in config.get_subscription_tiers():
        tiers.append(SubscriptionTier(
            tier=t["tier"],
            name=t["name"],
            price_monthly=t["price_monthly"],
            price_annual=t["price_annual"],
            features=t["features"],
        ))

    return tiers


@router.get("/revenue", response_model=RevenueMetrics)
@require_platform_admin
async def get_revenue_metrics(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get platform revenue metrics.

    Includes MRR, ARR, churn rate, and breakdown by tier.
    """
    # Get subscription stats from database
    stats_query = text("""
        SELECT
            COALESCE(SUM(
                CASE
                    WHEN s.billing_cycle = 'monthly' THEN sp.monthly_price
                    WHEN s.billing_cycle = 'yearly' THEN sp.annual_price / 12
                    ELSE sp.monthly_price
                END
            ), 0) as mrr,
            COUNT(DISTINCT s.subscription_id) as active_subs,
            COUNT(DISTINCT f.firm_id) as total_cpas
        FROM subscriptions s
        JOIN subscription_plans sp ON s.plan_id = sp.plan_id
        JOIN firms f ON s.firm_id = f.firm_id
        WHERE s.status = 'active'
    """)

    try:
        result = await session.execute(stats_query)
        row = result.fetchone()
        mrr = float(row[0] or 0)
        active_subs = row[1] or 0
        total_cpas = row[2] or 0
    except Exception:
        mrr = 0
        active_subs = 0
        total_cpas = 0

    # Get tier breakdown
    tier_query = text("""
        SELECT
            COALESCE(sp.name, 'starter') as tier,
            COUNT(*) as count,
            COALESCE(SUM(
                CASE
                    WHEN s.billing_cycle = 'monthly' THEN sp.monthly_price
                    ELSE sp.annual_price / 12
                END
            ), 0) as tier_mrr
        FROM subscriptions s
        JOIN subscription_plans sp ON s.plan_id = sp.plan_id
        WHERE s.status = 'active'
        GROUP BY sp.name
    """)

    by_tier = {}
    try:
        tier_result = await session.execute(tier_query)
        for row in tier_result.fetchall():
            by_tier[row[0]] = {
                "count": row[1],
                "mrr": float(row[2] or 0),
            }
    except Exception:
        by_tier = {"starter": {"count": 0, "mrr": 0}}

    # Calculate growth (mock for now)
    previous_mrr = mrr * 0.95  # Assume 5% growth
    mrr_growth = ((mrr - previous_mrr) / previous_mrr * 100) if previous_mrr > 0 else 0

    # Calculate churn (mock)
    churn_rate = 2.5

    return RevenueMetrics(
        mrr=mrr,
        arr=mrr * 12,
        mrr_growth_percent=round(mrr_growth, 1),
        total_cpas=total_cpas,
        active_subscriptions=active_subs,
        churn_rate=churn_rate,
        by_tier=by_tier,
        by_payment_method={
            "stripe": {"count": active_subs, "mrr": mrr},
            "bank_transfer": {"count": 0, "mrr": 0},
        },
    )


@router.get("/bank-details/{method}")
@require_platform_admin
async def get_bank_transfer_details(
    method: str,
    user: TenantContext = Depends(get_current_user),
):
    """
    Get full bank transfer details for a payment method.

    Only accessible to super admins for sharing with CPAs.
    """
    config = get_platform_billing_config()

    try:
        payment_method = PaymentMethod(method)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payment method: {method}"
        )

    details = config.get_bank_transfer_details(payment_method)

    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bank details not configured for {method}"
        )

    return details


@router.post("/calculate-fee")
@require_platform_admin
async def calculate_platform_fee(
    amount: float = Query(..., gt=0),
    user: TenantContext = Depends(get_current_user),
):
    """Calculate platform fee for a given amount."""
    config = get_platform_billing_config()
    return config.calculate_platform_fee(amount)


@router.get("/pending-payments")
@require_platform_admin
async def get_pending_payments(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get pending subscription payments.

    Shows CPAs with outstanding invoices.
    """
    query = text("""
        SELECT
            i.invoice_id,
            i.invoice_number,
            i.amount_due,
            i.currency,
            i.status,
            i.due_date,
            f.firm_id,
            f.name as firm_name,
            f.email as firm_email
        FROM invoices i
        JOIN firms f ON i.firm_id = f.firm_id
        WHERE i.status IN ('open', 'past_due')
        ORDER BY i.due_date ASC
        LIMIT :limit
    """)

    try:
        result = await session.execute(query, {"limit": limit})
        rows = result.fetchall()

        pending = []
        for row in rows:
            pending.append({
                "invoice_id": row[0],
                "invoice_number": row[1],
                "amount_due": float(row[2] or 0),
                "currency": row[3] or "USD",
                "status": row[4],
                "due_date": row[5],
                "firm_id": row[6],
                "firm_name": row[7],
                "firm_email": row[8],
            })

        return {
            "pending_payments": pending,
            "total_pending": len(pending),
            "total_amount": sum(p["amount_due"] for p in pending),
        }

    except Exception as e:
        logger.error(f"Error fetching pending payments: {e}")
        return {
            "pending_payments": [],
            "total_pending": 0,
            "total_amount": 0,
        }


@router.post("/record-manual-payment")
@require_platform_admin
async def record_manual_payment(
    invoice_id: str,
    amount: float,
    payment_method: str = Query(..., description="bank_transfer_us, bank_transfer_india, or manual"),
    reference: Optional[str] = None,
    notes: Optional[str] = None,
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Record a manual payment (bank transfer, check, etc.).

    Used when CPA pays via Mercury or Indian bank account.
    """
    # Get invoice
    invoice_query = text("""
        SELECT invoice_id, amount_due, status, firm_id
        FROM invoices
        WHERE invoice_id = :invoice_id
    """)

    result = await session.execute(invoice_query, {"invoice_id": invoice_id})
    invoice = result.fetchone()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )

    if invoice[2] == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice already paid"
        )

    # Update invoice
    now = datetime.utcnow()
    update_query = text("""
        UPDATE invoices
        SET status = 'paid',
            paid_at = :paid_at,
            amount_paid = :amount,
            payment_method = :payment_method,
            payment_reference = :reference,
            payment_notes = :notes,
            updated_at = :updated_at
        WHERE invoice_id = :invoice_id
    """)

    await session.execute(update_query, {
        "invoice_id": invoice_id,
        "paid_at": now.isoformat(),
        "amount": amount,
        "payment_method": payment_method,
        "reference": reference,
        "notes": notes,
        "updated_at": now.isoformat(),
    })

    # Log admin action
    from uuid import uuid4
    log_query = text("""
        INSERT INTO admin_audit_log (
            log_id, admin_id, action, resource_type, resource_id,
            details, created_at
        ) VALUES (
            :log_id, :admin_id, 'manual_payment_recorded', 'invoice', :invoice_id,
            :details, :created_at
        )
    """)

    import json
    try:
        await session.execute(log_query, {
            "log_id": str(uuid4()),
            "admin_id": user.user_id,
            "invoice_id": invoice_id,
            "details": json.dumps({
                "amount": amount,
                "payment_method": payment_method,
                "reference": reference,
            }),
            "created_at": now.isoformat(),
        })
    except Exception:
        pass  # Log table may not exist

    await session.commit()

    logger.info(f"Manual payment recorded for invoice {invoice_id} by {user.email}")

    return {
        "status": "success",
        "invoice_id": invoice_id,
        "amount_paid": amount,
        "payment_method": payment_method,
        "recorded_by": user.email,
        "recorded_at": now.isoformat(),
    }


@router.get("/cpa-stripe-accounts")
@require_platform_admin
async def get_cpa_stripe_accounts(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    connected_only: bool = Query(False, description="Only show CPAs with connected Stripe"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get list of CPA Stripe Connect accounts.

    Shows which CPAs have connected their Stripe accounts.
    """
    conditions = ["1=1"]
    if connected_only:
        conditions.append("stripe_account_id IS NOT NULL")

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT
            cpa_id,
            cpa_slug,
            first_name,
            last_name,
            firm_name,
            email,
            stripe_account_id,
            stripe_connected_at
        FROM cpa_profiles
        WHERE {where_clause}
        ORDER BY stripe_connected_at DESC NULLS LAST
        LIMIT :limit
    """)

    try:
        result = await session.execute(query, {"limit": limit})
        rows = result.fetchall()

        cpas = []
        connected_count = 0
        for row in rows:
            is_connected = bool(row[6])
            if is_connected:
                connected_count += 1

            cpas.append({
                "cpa_id": row[0],
                "cpa_slug": row[1],
                "name": f"{row[2] or ''} {row[3] or ''}".strip() or "Unknown",
                "firm_name": row[4],
                "email": row[5],
                "stripe_connected": is_connected,
                "stripe_account_id": row[6],
                "connected_at": row[7],
            })

        return {
            "cpas": cpas,
            "total": len(cpas),
            "connected_count": connected_count,
        }

    except Exception as e:
        logger.error(f"Error fetching CPA Stripe accounts: {e}")
        return {
            "cpas": [],
            "total": 0,
            "connected_count": 0,
        }
