"""
Billing Routes - Subscription and billing management endpoints.

Provides:
- Current subscription information
- Usage metrics
- Plan upgrade/downgrade
- Invoice history

All routes use database-backed queries.
"""

import json
import logging
import os
from typing import Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.rbac import (
    get_current_user,
    get_current_firm,
    TenantContext,
    require_permission,
)
from ..models.user import UserPermission
from database.async_engine import get_async_session
from calculator.decimal_math import money, to_decimal

router = APIRouter(prefix="/billing", tags=["Billing"])
logger = logging.getLogger(__name__)


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class PlanFeatures(BaseModel):
    """Plan features."""
    scenario_analysis: bool = True
    multi_state: bool = True
    api_access: bool = False
    white_label: bool = False
    priority_support: bool = False
    custom_domain: bool = False
    sso: bool = False
    audit_log_export: bool = True


class SubscriptionPlan(BaseModel):
    """Subscription plan details."""
    plan_id: str
    name: str
    code: str
    monthly_price: float
    annual_price: float
    max_team_members: Optional[int]
    max_clients: Optional[int]
    max_scenarios_per_month: Optional[int]
    features: PlanFeatures
    highlight_text: Optional[str] = None


class CurrentSubscription(BaseModel):
    """Current subscription response."""
    subscription_id: str
    plan: SubscriptionPlan
    status: str
    billing_cycle: str
    current_period_start: datetime
    current_period_end: datetime
    next_billing_date: Optional[datetime]
    trial_end: Optional[datetime]
    payment_method: Optional[dict]


class UsageMetrics(BaseModel):
    """Usage metrics for billing."""
    period_start: datetime
    period_end: datetime
    team_members: dict
    clients: dict
    returns: dict
    scenarios: dict
    api_calls: Optional[dict] = None
    storage: dict


class Invoice(BaseModel):
    """Invoice details."""
    invoice_id: str
    invoice_number: str
    amount_due: float
    amount_paid: float
    currency: str
    status: str
    period_start: datetime
    period_end: datetime
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    pdf_url: Optional[str]
    line_items: List[dict]


class PlanComparison(BaseModel):
    """Plan comparison for upgrade/downgrade."""
    current_plan: SubscriptionPlan
    target_plan: SubscriptionPlan
    price_difference: float
    prorated_amount: float
    effective_date: datetime
    features_gained: List[str]
    features_lost: List[str]
    recommendations: List[str]


# =============================================================================
# ROUTES
# =============================================================================

@router.get("/subscription", response_model=CurrentSubscription)
async def get_current_subscription(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get current subscription details.

    Includes plan details, status, and payment information.
    """
    # Get subscription with plan details
    query = text("""
        SELECT s.subscription_id, s.status, s.billing_cycle,
               s.current_period_start, s.current_period_end, s.next_billing_date,
               s.trial_end, s.payment_method,
               p.plan_id, p.name, p.code, p.monthly_price, p.annual_price,
               p.max_team_members, p.max_clients, p.max_scenarios_per_month,
               p.features, p.highlight_text
        FROM subscriptions s
        JOIN subscription_plans p ON s.plan_id = p.plan_id
        WHERE s.firm_id = :firm_id
        ORDER BY s.created_at DESC
        LIMIT 1
    """)
    result = await session.execute(query, {"firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found for this firm",
        )

    # Parse features from JSONB
    features_data = json.loads(row[16]) if row[16] else {}
    features = PlanFeatures(
        scenario_analysis=features_data.get("scenario_analysis", True),
        multi_state=features_data.get("multi_state", False),
        api_access=features_data.get("api_access", False),
        white_label=features_data.get("white_label", False),
        priority_support=features_data.get("priority_support", False),
        custom_domain=features_data.get("custom_domain", False),
        sso=features_data.get("sso", False),
        audit_log_export=features_data.get("audit_log_export", True),
    )

    # Parse payment method from JSONB
    payment_method = json.loads(row[7]) if row[7] else None

    # Parse dates
    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    return CurrentSubscription(
        subscription_id=str(row[0]),
        plan=SubscriptionPlan(
            plan_id=str(row[8]),
            name=row[9],
            code=row[10],
            monthly_price=float(row[11]) if row[11] else 0.0,
            annual_price=float(row[12]) if row[12] else 0.0,
            max_team_members=row[13],
            max_clients=row[14],
            max_scenarios_per_month=row[15],
            features=features,
            highlight_text=row[17],
        ),
        status=row[1],
        billing_cycle=row[2],
        current_period_start=parse_dt(row[3]) or datetime.utcnow(),
        current_period_end=parse_dt(row[4]) or datetime.utcnow(),
        next_billing_date=parse_dt(row[5]),
        trial_end=parse_dt(row[6]),
        payment_method=payment_method,
    )


@router.get("/usage", response_model=UsageMetrics)
async def get_usage_metrics(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    period: str = Query("current", description="current, previous, or YYYY-MM"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get usage metrics for the billing period.

    Shows current usage vs. plan limits.
    """
    # Get current subscription period and limits
    sub_query = text("""
        SELECT s.current_period_start, s.current_period_end,
               p.max_team_members, p.max_clients, p.max_scenarios_per_month,
               p.features
        FROM subscriptions s
        JOIN subscription_plans p ON s.plan_id = p.plan_id
        WHERE s.firm_id = :firm_id
        ORDER BY s.created_at DESC
        LIMIT 1
    """)
    sub_result = await session.execute(sub_query, {"firm_id": firm_id})
    sub_row = sub_result.fetchone()

    if not sub_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    # Parse dates
    def parse_dt(val):
        if val is None:
            return datetime.utcnow()
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    period_start = parse_dt(sub_row[0])
    period_end = parse_dt(sub_row[1])
    max_team = sub_row[2]
    max_clients = sub_row[3]
    max_scenarios = sub_row[4]
    features = json.loads(sub_row[5]) if sub_row[5] else {}

    # Handle different period selections
    if period == "previous":
        period_end = period_start
        period_start = period_start - timedelta(days=30)
    elif period not in ("current", "previous"):
        # Parse YYYY-MM format
        try:
            year, month = period.split("-")
            period_start = datetime(int(year), int(month), 1)
            if int(month) == 12:
                period_end = datetime(int(year) + 1, 1, 1)
            else:
                period_end = datetime(int(year), int(month) + 1, 1)
        except (ValueError, IndexError):
            pass  # Use current period

    # Get team member count
    team_query = text("""
        SELECT COUNT(*) FROM users
        WHERE firm_id = :firm_id AND is_active = true
    """)
    team_result = await session.execute(team_query, {"firm_id": firm_id})
    team_count = team_result.fetchone()[0] or 0

    # Get client count
    client_query = text("""
        SELECT COUNT(*) FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id AND c.is_active = true
    """)
    client_result = await session.execute(client_query, {"firm_id": firm_id})
    client_count = client_result.fetchone()[0] or 0

    # Get returns count for period
    returns_query = text("""
        SELECT COUNT(*) as period_returns,
               (SELECT COUNT(*) FROM returns r2 JOIN users u2 ON r2.preparer_id = u2.user_id
                WHERE u2.firm_id = :firm_id) as total
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.created_at >= :period_start AND r.created_at < :period_end
    """)
    returns_result = await session.execute(returns_query, {
        "firm_id": firm_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    })
    returns_row = returns_result.fetchone()
    period_returns = returns_row[0] or 0
    total_returns = returns_row[1] or 0

    # Get scenario count for period
    scenario_query = text("""
        SELECT COUNT(*) FROM scenarios s
        JOIN returns r ON s.return_id = r.return_id
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND s.created_at >= :period_start AND s.created_at < :period_end
    """)
    scenario_result = await session.execute(scenario_query, {
        "firm_id": firm_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    })
    scenario_count = scenario_result.fetchone()[0] or 0

    # Calculate storage used (from documents table)
    storage_query = text("""
        SELECT COALESCE(SUM(file_size), 0) / (1024 * 1024 * 1024) as used_gb
        FROM documents d
        JOIN clients c ON d.client_id = c.client_id
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
    """)
    storage_result = await session.execute(storage_query, {"firm_id": firm_id})
    storage_used = float(storage_result.fetchone()[0] or 0)

    # Calculate percentages
    def calc_percent(current, limit):
        if limit is None or limit == 0:
            return 0
        return round((current / limit) * 100, 1)

    storage_limit = 10  # Default 10GB

    return UsageMetrics(
        period_start=period_start,
        period_end=period_end,
        team_members={
            "current": team_count,
            "limit": max_team,
            "percent_used": calc_percent(team_count, max_team),
        },
        clients={
            "current": client_count,
            "limit": max_clients,
            "percent_used": calc_percent(client_count, max_clients),
        },
        returns={
            "this_period": period_returns,
            "total": total_returns,
        },
        scenarios={
            "this_period": scenario_count,
            "limit": max_scenarios,
            "percent_used": calc_percent(scenario_count, max_scenarios),
        },
        api_calls=None if not features.get("api_access") else {"this_period": 0, "limit": None},
        storage={
            "used_gb": float(money(storage_used)),
            "limit_gb": storage_limit,
            "percent_used": calc_percent(storage_used, storage_limit),
        },
    )


@router.get("/plans", response_model=List[SubscriptionPlan])
async def get_available_plans(
    user: TenantContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get all available subscription plans.

    Returns plans for comparison and upgrade decisions.
    """
    query = text("""
        SELECT plan_id, name, code, monthly_price, annual_price,
               max_team_members, max_clients, max_scenarios_per_month,
               features, highlight_text
        FROM subscription_plans
        WHERE is_active = true
        ORDER BY monthly_price ASC
    """)
    result = await session.execute(query)
    rows = result.fetchall()

    plans = []
    for row in rows:
        features_data = json.loads(row[8]) if row[8] else {}
        features = PlanFeatures(
            scenario_analysis=features_data.get("scenario_analysis", True),
            multi_state=features_data.get("multi_state", False),
            api_access=features_data.get("api_access", False),
            white_label=features_data.get("white_label", False),
            priority_support=features_data.get("priority_support", False),
            custom_domain=features_data.get("custom_domain", False),
            sso=features_data.get("sso", False),
            audit_log_export=features_data.get("audit_log_export", True),
        )

        plans.append(SubscriptionPlan(
            plan_id=str(row[0]),
            name=row[1],
            code=row[2],
            monthly_price=float(row[3]) if row[3] else 0.0,
            annual_price=float(row[4]) if row[4] else 0.0,
            max_team_members=row[5],
            max_clients=row[6],
            max_scenarios_per_month=row[7],
            features=features,
            highlight_text=row[9],
        ))

    return plans


@router.post("/upgrade/preview", response_model=PlanComparison)
@require_permission(UserPermission.CHANGE_PLAN)
async def preview_upgrade(
    target_plan_code: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Preview an upgrade to a different plan.

    Shows price difference, prorated amount, and feature changes.
    """
    # Get current subscription and plan
    current_query = text("""
        SELECT s.billing_cycle, s.current_period_end,
               p.plan_id, p.name, p.code, p.monthly_price, p.annual_price,
               p.max_team_members, p.max_clients, p.max_scenarios_per_month,
               p.features, p.highlight_text
        FROM subscriptions s
        JOIN subscription_plans p ON s.plan_id = p.plan_id
        WHERE s.firm_id = :firm_id
        ORDER BY s.created_at DESC
        LIMIT 1
    """)
    current_result = await session.execute(current_query, {"firm_id": firm_id})
    current_row = current_result.fetchone()

    if not current_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current subscription found",
        )

    # Get target plan
    target_query = text("""
        SELECT plan_id, name, code, monthly_price, annual_price,
               max_team_members, max_clients, max_scenarios_per_month,
               features, highlight_text
        FROM subscription_plans
        WHERE code = :code AND is_active = true
    """)
    target_result = await session.execute(target_query, {"code": target_plan_code})
    target_row = target_result.fetchone()

    if not target_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{target_plan_code}' not found",
        )

    # Parse features
    def parse_features(data):
        features_data = json.loads(data) if data else {}
        return PlanFeatures(
            scenario_analysis=features_data.get("scenario_analysis", True),
            multi_state=features_data.get("multi_state", False),
            api_access=features_data.get("api_access", False),
            white_label=features_data.get("white_label", False),
            priority_support=features_data.get("priority_support", False),
            custom_domain=features_data.get("custom_domain", False),
            sso=features_data.get("sso", False),
            audit_log_export=features_data.get("audit_log_export", True),
        )

    current_features = parse_features(current_row[10])
    target_features = parse_features(target_row[8])

    current_plan = SubscriptionPlan(
        plan_id=str(current_row[2]),
        name=current_row[3],
        code=current_row[4],
        monthly_price=float(current_row[5]) if current_row[5] else 0.0,
        annual_price=float(current_row[6]) if current_row[6] else 0.0,
        max_team_members=current_row[7],
        max_clients=current_row[8],
        max_scenarios_per_month=current_row[9],
        features=current_features,
        highlight_text=current_row[11],
    )

    target_plan = SubscriptionPlan(
        plan_id=str(target_row[0]),
        name=target_row[1],
        code=target_row[2],
        monthly_price=float(target_row[3]) if target_row[3] else 0.0,
        annual_price=float(target_row[4]) if target_row[4] else 0.0,
        max_team_members=target_row[5],
        max_clients=target_row[6],
        max_scenarios_per_month=target_row[7],
        features=target_features,
        highlight_text=target_row[9],
    )

    # Calculate price difference and proration
    billing_cycle = current_row[0]
    current_price = current_plan.monthly_price if billing_cycle == "monthly" else current_plan.annual_price / 12
    target_price = target_plan.monthly_price if billing_cycle == "monthly" else target_plan.annual_price / 12
    price_difference = target_price - current_price

    # Calculate prorated amount based on remaining days
    period_end = current_row[1]
    if isinstance(period_end, str):
        period_end = datetime.fromisoformat(period_end.replace('Z', '+00:00'))
    days_remaining = max(0, (period_end - datetime.utcnow()).days) if period_end else 0
    prorated_amount = (price_difference / 30) * days_remaining if price_difference > 0 else 0

    # Determine features gained/lost
    features_gained = []
    features_lost = []
    feature_names = {
        "multi_state": "Multi-state analysis",
        "api_access": "API access",
        "white_label": "White-label branding",
        "priority_support": "Priority support",
        "custom_domain": "Custom domain",
        "sso": "Single sign-on (SSO)",
        "audit_log_export": "Audit log export",
    }

    for attr, name in feature_names.items():
        current_val = getattr(current_features, attr)
        target_val = getattr(target_features, attr)
        if target_val and not current_val:
            features_gained.append(name)
        elif current_val and not target_val:
            features_lost.append(name)

    # Add limit changes
    if (target_plan.max_team_members or 0) > (current_plan.max_team_members or 0):
        features_gained.append(f"Up to {target_plan.max_team_members or 'unlimited'} team members")
    if (target_plan.max_clients or 0) > (current_plan.max_clients or 0):
        features_gained.append(f"Up to {target_plan.max_clients or 'unlimited'} clients")

    # Generate recommendations based on usage
    recommendations = []
    if price_difference > 0:
        recommendations.append(f"Upgrade effective immediately with ${prorated_amount:.2f} prorated charge")
    else:
        recommendations.append("Downgrade will take effect at end of billing period")

    return PlanComparison(
        current_plan=current_plan,
        target_plan=target_plan,
        price_difference=float(money(price_difference)),
        prorated_amount=float(money(prorated_amount)),
        effective_date=datetime.utcnow() if price_difference > 0 else period_end or datetime.utcnow(),
        features_gained=features_gained,
        features_lost=features_lost,
        recommendations=recommendations,
    )


@router.post("/upgrade")
@require_permission(UserPermission.CHANGE_PLAN)
async def upgrade_plan(
    target_plan_code: str,
    billing_cycle: str = Query("monthly", description="monthly or annual"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Upgrade to a higher plan.

    Charges will be prorated based on remaining billing period.
    """
    # Get current subscription
    current_query = text("""
        SELECT s.subscription_id, s.billing_cycle, s.current_period_end,
               p.monthly_price, p.annual_price
        FROM subscriptions s
        JOIN subscription_plans p ON s.plan_id = p.plan_id
        WHERE s.firm_id = :firm_id AND s.status = 'active'
        ORDER BY s.created_at DESC
        LIMIT 1
    """)
    current_result = await session.execute(current_query, {"firm_id": firm_id})
    current_row = current_result.fetchone()

    if not current_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    # Get target plan
    target_query = text("""
        SELECT plan_id, monthly_price, annual_price, max_team_members
        FROM subscription_plans
        WHERE code = :code AND is_active = true
    """)
    target_result = await session.execute(target_query, {"code": target_plan_code})
    target_row = target_result.fetchone()

    if not target_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{target_plan_code}' not found",
        )

    # Calculate prorated charge
    current_price = float(current_row[3]) if current_row[1] == "monthly" else float(current_row[4]) / 12
    target_price = float(target_row[1]) if billing_cycle == "monthly" else float(target_row[2]) / 12

    if target_price <= current_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use downgrade endpoint for moving to a lower plan",
        )

    # Calculate proration
    period_end = current_row[2]
    if isinstance(period_end, str):
        period_end = datetime.fromisoformat(period_end.replace('Z', '+00:00'))
    days_remaining = max(0, (period_end - datetime.utcnow()).days) if period_end else 0
    prorated_charge = ((target_price - current_price) / 30) * days_remaining

    # Update subscription
    now = datetime.utcnow()
    update_query = text("""
        UPDATE subscriptions SET
            plan_id = :plan_id,
            billing_cycle = :billing_cycle,
            updated_at = :updated_at
        WHERE subscription_id = :subscription_id
    """)
    await session.execute(update_query, {
        "subscription_id": current_row[0],
        "plan_id": target_row[0],
        "billing_cycle": billing_cycle,
        "updated_at": now.isoformat(),
    })

    # Update firm limits
    update_firm_query = text("""
        UPDATE firms SET
            max_team_members = :max_team,
            updated_at = :updated_at
        WHERE firm_id = :firm_id
    """)
    await session.execute(update_firm_query, {
        "firm_id": firm_id,
        "max_team": target_row[3],
        "updated_at": now.isoformat(),
    })

    # Log the upgrade event
    event_id = str(uuid4())
    event_query = text("""
        INSERT INTO audit_logs (
            log_id, firm_id, user_id, action, resource_type, resource_id,
            details, created_at
        ) VALUES (
            :log_id, :firm_id, :user_id, 'plan_upgrade', 'subscription', :sub_id,
            :details, :created_at
        )
    """)
    await session.execute(event_query, {
        "log_id": event_id,
        "firm_id": firm_id,
        "user_id": user.user_id,
        "sub_id": str(current_row[0]),
        "details": json.dumps({
            "from_plan": current_row[1],
            "to_plan": target_plan_code,
            "prorated_charge": float(money(prorated_charge)),
        }),
        "created_at": now.isoformat(),
    })

    await session.commit()
    logger.info(f"Plan upgraded for firm {firm_id} to {target_plan_code} by {user.email}")

    # Stripe charge for prorated amount
    stripe_key = os.environ.get("STRIPE_SECRET_KEY")
    if stripe_key and prorated_charge > 0:
        logger.warning(
            f"Stripe charge not yet integrated: ${prorated_charge:.2f} for firm {firm_id}. "
            f"Manual billing required."
        )

    return {
        "status": "success",
        "message": "Plan upgraded successfully",
        "new_plan": target_plan_code,
        "effective_immediately": True,
        "prorated_charge": float(money(prorated_charge)),
        "billing_note": "Stripe billing integration pending" if not stripe_key else None,
    }


@router.post("/downgrade")
@require_permission(UserPermission.CHANGE_PLAN)
async def downgrade_plan(
    target_plan_code: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Downgrade to a lower plan.

    Downgrade takes effect at end of current billing period.
    """
    # Get current subscription
    current_query = text("""
        SELECT s.subscription_id, s.current_period_end,
               p.monthly_price, p.code as current_code
        FROM subscriptions s
        JOIN subscription_plans p ON s.plan_id = p.plan_id
        WHERE s.firm_id = :firm_id AND s.status = 'active'
        ORDER BY s.created_at DESC
        LIMIT 1
    """)
    current_result = await session.execute(current_query, {"firm_id": firm_id})
    current_row = current_result.fetchone()

    if not current_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    # Get target plan
    target_query = text("""
        SELECT plan_id, monthly_price, max_team_members, max_clients, features
        FROM subscription_plans
        WHERE code = :code AND is_active = true
    """)
    target_result = await session.execute(target_query, {"code": target_plan_code})
    target_row = target_result.fetchone()

    if not target_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{target_plan_code}' not found",
        )

    # Check if this is actually a downgrade
    if float(target_row[1]) >= float(current_row[2]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use upgrade endpoint for moving to a higher plan",
        )

    # Check for potential issues
    warnings = []

    # Check team member count
    team_query = text("SELECT COUNT(*) FROM users WHERE firm_id = :firm_id AND is_active = true")
    team_result = await session.execute(team_query, {"firm_id": firm_id})
    team_count = team_result.fetchone()[0]

    if target_row[2] and team_count > target_row[2]:
        warnings.append(f"You have {team_count} team members but new plan allows {target_row[2]}. "
                       f"{team_count - target_row[2]} members will be deactivated.")

    # Check client count
    client_query = text("""
        SELECT COUNT(*) FROM clients c
        JOIN users u ON c.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id AND c.is_active = true
    """)
    client_result = await session.execute(client_query, {"firm_id": firm_id})
    client_count = client_result.fetchone()[0]

    if target_row[3] and client_count > target_row[3]:
        warnings.append(f"You have {client_count} clients but new plan allows {target_row[3]}. "
                       "Excess clients will be archived.")

    # Check feature loss
    target_features = json.loads(target_row[4]) if target_row[4] else {}
    if not target_features.get("api_access"):
        warnings.append("API access will be revoked at downgrade")

    # Schedule downgrade (sets pending_plan_id)
    effective_date = current_row[1]
    if isinstance(effective_date, str):
        effective_date = datetime.fromisoformat(effective_date.replace('Z', '+00:00'))

    update_query = text("""
        UPDATE subscriptions SET
            pending_plan_id = :pending_plan_id,
            pending_downgrade_date = :downgrade_date,
            updated_at = :updated_at
        WHERE subscription_id = :subscription_id
    """)
    await session.execute(update_query, {
        "subscription_id": current_row[0],
        "pending_plan_id": target_row[0],
        "downgrade_date": effective_date.isoformat() if effective_date else datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    })

    # Log the downgrade event
    event_id = str(uuid4())
    event_query = text("""
        INSERT INTO audit_logs (
            log_id, firm_id, user_id, action, resource_type, resource_id,
            details, created_at
        ) VALUES (
            :log_id, :firm_id, :user_id, 'plan_downgrade_scheduled', 'subscription', :sub_id,
            :details, :created_at
        )
    """)
    await session.execute(event_query, {
        "log_id": event_id,
        "firm_id": firm_id,
        "user_id": user.user_id,
        "sub_id": str(current_row[0]),
        "details": json.dumps({
            "from_plan": current_row[3],
            "to_plan": target_plan_code,
            "effective_date": effective_date.isoformat() if effective_date else None,
        }),
        "created_at": datetime.utcnow().isoformat(),
    })

    await session.commit()
    logger.info(f"Plan downgrade scheduled for firm {firm_id} to {target_plan_code}")

    return {
        "status": "success",
        "message": "Plan will be downgraded at end of billing period",
        "new_plan": target_plan_code,
        "effective_date": effective_date,
        "warnings": warnings,
    }


@router.get("/invoices", response_model=List[Invoice])
@require_permission(UserPermission.VIEW_BILLING)
async def list_invoices(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get invoice history.

    Returns paginated list of invoices with download links.
    """
    # Build query with optional status filter
    conditions = ["i.firm_id = :firm_id"]
    params = {"firm_id": firm_id, "limit": limit}

    if status_filter:
        conditions.append("i.status = :status")
        params["status"] = status_filter

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT i.invoice_id, i.invoice_number, i.amount_due, i.amount_paid,
               i.currency, i.status, i.period_start, i.period_end,
               i.due_date, i.paid_at, i.pdf_url, i.line_items
        FROM invoices i
        WHERE {where_clause}
        ORDER BY i.created_at DESC
        LIMIT :limit
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    invoices = []
    for row in rows:
        # Parse dates
        def parse_dt(val):
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(val.replace('Z', '+00:00'))

        line_items = json.loads(row[11]) if row[11] else []

        invoices.append(Invoice(
            invoice_id=str(row[0]),
            invoice_number=row[1],
            amount_due=float(row[2]) if row[2] else 0.0,
            amount_paid=float(row[3]) if row[3] else 0.0,
            currency=row[4] or "USD",
            status=row[5],
            period_start=parse_dt(row[6]) or datetime.utcnow(),
            period_end=parse_dt(row[7]) or datetime.utcnow(),
            due_date=parse_dt(row[8]),
            paid_at=parse_dt(row[9]),
            pdf_url=row[10],
            line_items=line_items,
        ))

    return invoices


@router.get("/invoices/{invoice_id}", response_model=Invoice)
@require_permission(UserPermission.VIEW_BILLING)
async def get_invoice(
    invoice_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get details of a specific invoice."""
    query = text("""
        SELECT i.invoice_id, i.invoice_number, i.amount_due, i.amount_paid,
               i.currency, i.status, i.period_start, i.period_end,
               i.due_date, i.paid_at, i.pdf_url, i.line_items
        FROM invoices i
        WHERE i.invoice_id = :invoice_id AND i.firm_id = :firm_id
    """)

    result = await session.execute(query, {"invoice_id": invoice_id, "firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    # Parse dates
    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    line_items = json.loads(row[11]) if row[11] else []

    return Invoice(
        invoice_id=str(row[0]),
        invoice_number=row[1],
        amount_due=float(row[2]) if row[2] else 0.0,
        amount_paid=float(row[3]) if row[3] else 0.0,
        currency=row[4] or "USD",
        status=row[5],
        period_start=parse_dt(row[6]) or datetime.utcnow(),
        period_end=parse_dt(row[7]) or datetime.utcnow(),
        due_date=parse_dt(row[8]),
        paid_at=parse_dt(row[9]),
        pdf_url=row[10],
        line_items=line_items,
    )


@router.post("/payment-method")
@require_permission(UserPermission.UPDATE_PAYMENT)
async def update_payment_method(
    payment_method_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update payment method.

    Uses Stripe payment method ID from frontend Stripe Elements.
    """
    # Get current subscription
    sub_query = text("""
        SELECT subscription_id, stripe_customer_id
        FROM subscriptions
        WHERE firm_id = :firm_id AND status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
    """)
    sub_result = await session.execute(sub_query, {"firm_id": firm_id})
    sub_row = sub_result.fetchone()

    if not sub_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    # Stripe payment method attachment
    stripe_key = os.environ.get("STRIPE_SECRET_KEY")
    if stripe_key:
        logger.warning(
            f"Stripe payment method attachment not yet integrated for firm {firm_id}. "
            f"Payment method stored locally only."
        )

    # For now, store the payment method ID in the subscription
    update_query = text("""
        UPDATE subscriptions SET
            payment_method = :payment_method,
            updated_at = :updated_at
        WHERE subscription_id = :subscription_id
    """)
    await session.execute(update_query, {
        "subscription_id": sub_row[0],
        "payment_method": json.dumps({"stripe_payment_method_id": payment_method_id}),
        "updated_at": datetime.utcnow().isoformat(),
    })

    # Log the event
    event_id = str(uuid4())
    event_query = text("""
        INSERT INTO audit_logs (
            log_id, firm_id, user_id, action, resource_type, resource_id,
            details, created_at
        ) VALUES (
            :log_id, :firm_id, :user_id, 'payment_method_updated', 'subscription', :sub_id,
            :details, :created_at
        )
    """)
    await session.execute(event_query, {
        "log_id": event_id,
        "firm_id": firm_id,
        "user_id": user.user_id,
        "sub_id": str(sub_row[0]),
        "details": json.dumps({"payment_method_id": payment_method_id}),
        "created_at": datetime.utcnow().isoformat(),
    })

    await session.commit()
    logger.info(f"Payment method updated for firm {firm_id} by {user.email}")

    return {
        "status": "success",
        "message": "Payment method updated",
    }
