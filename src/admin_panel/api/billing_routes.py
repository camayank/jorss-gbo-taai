"""
Billing Routes - Subscription and billing management endpoints.

Provides:
- Current subscription information
- Usage metrics
- Plan upgrade/downgrade
- Invoice history
"""

from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..auth.rbac import (
    get_current_user,
    get_current_firm,
    TenantContext,
    require_permission,
)
from ..models.user import UserPermission

router = APIRouter(prefix="/billing", tags=["Billing"])


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
):
    """
    Get current subscription details.

    Includes plan details, status, and payment information.
    """
    # TODO: Implement actual database query
    return CurrentSubscription(
        subscription_id="sub-123",
        plan=SubscriptionPlan(
            plan_id="plan-pro",
            name="Professional",
            code="professional",
            monthly_price=499.00,
            annual_price=4990.00,
            max_team_members=10,
            max_clients=500,
            max_scenarios_per_month=500,
            features=PlanFeatures(
                scenario_analysis=True,
                multi_state=True,
                api_access=False,
                white_label=False,
                priority_support=True,
                custom_domain=False,
                sso=False,
                audit_log_export=True,
            ),
            highlight_text="Most Popular",
        ),
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow(),
        next_billing_date=datetime.utcnow(),
        trial_end=None,
        payment_method={
            "type": "card",
            "brand": "visa",
            "last4": "4242",
            "exp_month": 12,
            "exp_year": 2026,
        },
    )


@router.get("/usage", response_model=UsageMetrics)
async def get_usage_metrics(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    period: str = Query("current", description="current, previous, or YYYY-MM"),
):
    """
    Get usage metrics for the billing period.

    Shows current usage vs. plan limits.
    """
    # TODO: Implement actual usage calculation
    return UsageMetrics(
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        team_members={
            "current": 5,
            "limit": 10,
            "percent_used": 50,
        },
        clients={
            "current": 156,
            "limit": 500,
            "percent_used": 31.2,
        },
        returns={
            "this_period": 47,
            "total": 312,
        },
        scenarios={
            "this_period": 234,
            "limit": 500,
            "percent_used": 46.8,
        },
        api_calls=None,  # Enterprise only
        storage={
            "used_gb": 2.4,
            "limit_gb": 10,
            "percent_used": 24,
        },
    )


@router.get("/plans", response_model=List[SubscriptionPlan])
async def get_available_plans(
    user: TenantContext = Depends(get_current_user),
):
    """
    Get all available subscription plans.

    Returns plans for comparison and upgrade decisions.
    """
    return [
        SubscriptionPlan(
            plan_id="plan-starter",
            name="Starter",
            code="starter",
            monthly_price=199.00,
            annual_price=1990.00,
            max_team_members=3,
            max_clients=100,
            max_scenarios_per_month=50,
            features=PlanFeatures(
                scenario_analysis=True,
                multi_state=False,
                api_access=False,
                white_label=False,
                priority_support=False,
                custom_domain=False,
                sso=False,
                audit_log_export=False,
            ),
        ),
        SubscriptionPlan(
            plan_id="plan-pro",
            name="Professional",
            code="professional",
            monthly_price=499.00,
            annual_price=4990.00,
            max_team_members=10,
            max_clients=500,
            max_scenarios_per_month=500,
            features=PlanFeatures(
                scenario_analysis=True,
                multi_state=True,
                api_access=False,
                white_label=False,
                priority_support=True,
                custom_domain=False,
                sso=False,
                audit_log_export=True,
            ),
            highlight_text="Most Popular",
        ),
        SubscriptionPlan(
            plan_id="plan-enterprise",
            name="Enterprise",
            code="enterprise",
            monthly_price=999.00,
            annual_price=9990.00,
            max_team_members=None,  # Unlimited
            max_clients=None,
            max_scenarios_per_month=None,
            features=PlanFeatures(
                scenario_analysis=True,
                multi_state=True,
                api_access=True,
                white_label=True,
                priority_support=True,
                custom_domain=True,
                sso=True,
                audit_log_export=True,
            ),
        ),
    ]


@router.post("/upgrade/preview", response_model=PlanComparison)
@require_permission(UserPermission.CHANGE_PLAN)
async def preview_upgrade(
    target_plan_code: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    Preview an upgrade to a different plan.

    Shows price difference, prorated amount, and feature changes.
    """
    # TODO: Implement actual upgrade preview
    return PlanComparison(
        current_plan=SubscriptionPlan(
            plan_id="plan-starter",
            name="Starter",
            code="starter",
            monthly_price=199.00,
            annual_price=1990.00,
            max_team_members=3,
            max_clients=100,
            max_scenarios_per_month=50,
            features=PlanFeatures(),
        ),
        target_plan=SubscriptionPlan(
            plan_id="plan-pro",
            name="Professional",
            code="professional",
            monthly_price=499.00,
            annual_price=4990.00,
            max_team_members=10,
            max_clients=500,
            max_scenarios_per_month=500,
            features=PlanFeatures(multi_state=True, priority_support=True, audit_log_export=True),
            highlight_text="Most Popular",
        ),
        price_difference=300.00,
        prorated_amount=150.00,  # Based on remaining days
        effective_date=datetime.utcnow(),
        features_gained=[
            "Multi-state analysis",
            "Priority support",
            "Audit log export",
            "Up to 10 team members",
            "Up to 500 clients",
        ],
        features_lost=[],
        recommendations=[
            "Based on your 40% complex returns, Professional plan could save significant analysis time",
            "You're currently at 3/3 team members - upgrade unlocks 7 more seats",
        ],
    )


@router.post("/upgrade")
@require_permission(UserPermission.CHANGE_PLAN)
async def upgrade_plan(
    target_plan_code: str,
    billing_cycle: str = Query("monthly", description="monthly or annual"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    Upgrade to a higher plan.

    Charges will be prorated based on remaining billing period.
    """
    # TODO: Implement actual upgrade via Stripe
    return {
        "status": "success",
        "message": "Plan upgraded successfully",
        "new_plan": target_plan_code,
        "effective_immediately": True,
        "prorated_charge": 150.00,
    }


@router.post("/downgrade")
@require_permission(UserPermission.CHANGE_PLAN)
async def downgrade_plan(
    target_plan_code: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    Downgrade to a lower plan.

    Downgrade takes effect at end of current billing period.
    """
    # TODO: Implement actual downgrade
    return {
        "status": "success",
        "message": "Plan will be downgraded at end of billing period",
        "new_plan": target_plan_code,
        "effective_date": datetime.utcnow(),  # End of period
        "warnings": [
            "Team members exceeding new limit will be deactivated",
            "API access will be revoked",
        ],
    }


@router.get("/invoices", response_model=List[Invoice])
@require_permission(UserPermission.VIEW_BILLING)
async def list_invoices(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """
    Get invoice history.

    Returns paginated list of invoices with download links.
    """
    # TODO: Implement actual invoice query
    return [
        Invoice(
            invoice_id="inv-123",
            invoice_number="INV-2026-001",
            amount_due=499.00,
            amount_paid=499.00,
            currency="USD",
            status="paid",
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow(),
            due_date=datetime.utcnow(),
            paid_at=datetime.utcnow(),
            pdf_url="/invoices/inv-123.pdf",
            line_items=[
                {
                    "description": "Professional Plan - Monthly",
                    "quantity": 1,
                    "unit_price": 499.00,
                    "amount": 499.00,
                },
            ],
        ),
    ]


@router.get("/invoices/{invoice_id}", response_model=Invoice)
@require_permission(UserPermission.VIEW_BILLING)
async def get_invoice(
    invoice_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """Get details of a specific invoice."""
    # TODO: Implement actual invoice query
    return Invoice(
        invoice_id=invoice_id,
        invoice_number="INV-2026-001",
        amount_due=499.00,
        amount_paid=499.00,
        currency="USD",
        status="paid",
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        due_date=datetime.utcnow(),
        paid_at=datetime.utcnow(),
        pdf_url=f"/invoices/{invoice_id}.pdf",
        line_items=[],
    )


@router.post("/payment-method")
@require_permission(UserPermission.UPDATE_PAYMENT)
async def update_payment_method(
    payment_method_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
):
    """
    Update payment method.

    Uses Stripe payment method ID from frontend Stripe Elements.
    """
    # TODO: Implement actual Stripe integration
    return {
        "status": "success",
        "message": "Payment method updated",
    }
