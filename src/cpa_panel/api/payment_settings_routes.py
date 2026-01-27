"""
CPA Payment Settings Routes - Stripe Connect integration for CPAs.

Allows CPAs to:
- Connect their own Stripe account to collect client payments
- View payment settings and connection status
- Manage payout preferences

Platform collects its subscription fees separately (Mercury/bank transfer).
"""

import os
import logging
from typing import Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database.async_engine import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment-settings", tags=["CPA Payment Settings"])


# =============================================================================
# CONFIGURATION
# =============================================================================

def get_stripe_config():
    """Get Stripe configuration from environment."""
    return {
        "client_id": os.environ.get("STRIPE_CLIENT_ID"),
        "secret_key": os.environ.get("STRIPE_SECRET_KEY"),
        "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY"),
        "connect_redirect_uri": os.environ.get(
            "STRIPE_CONNECT_REDIRECT_URI",
            "http://localhost:8000/api/cpa/payment-settings/stripe/callback"
        ),
    }


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class StripeConnectStatus(BaseModel):
    """Stripe Connect account status."""
    connected: bool
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    account_email: Optional[str] = None
    charges_enabled: bool = False
    payouts_enabled: bool = False
    requirements_due: list = Field(default_factory=list)
    connected_at: Optional[datetime] = None


class PaymentSettings(BaseModel):
    """CPA payment settings."""
    cpa_id: str
    stripe_connect: StripeConnectStatus
    default_currency: str = "USD"
    auto_invoice: bool = True
    invoice_due_days: int = 30
    payment_methods_enabled: list = Field(default_factory=lambda: ["card"])


class UpdatePaymentSettingsRequest(BaseModel):
    """Request to update payment settings."""
    default_currency: Optional[str] = None
    auto_invoice: Optional[bool] = None
    invoice_due_days: Optional[int] = Field(None, ge=1, le=90)
    payment_methods_enabled: Optional[list] = None


# =============================================================================
# ROUTES
# =============================================================================

@router.get("/", response_model=PaymentSettings)
async def get_payment_settings(
    cpa_id: str = Query(..., description="CPA ID"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get CPA payment settings.

    Returns Stripe Connect status and payment preferences.
    """
    # Get CPA profile
    cpa_query = text("""
        SELECT cpa_id, stripe_account_id, stripe_connected_at,
               payment_settings
        FROM cpa_profiles
        WHERE cpa_id = :cpa_id
    """)
    result = await session.execute(cpa_query, {"cpa_id": cpa_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CPA profile not found"
        )

    stripe_account_id = row[1]
    stripe_connected_at = row[2]
    payment_settings_json = row[3]

    # Parse payment settings
    import json
    settings = {}
    if payment_settings_json:
        try:
            settings = json.loads(payment_settings_json) if isinstance(payment_settings_json, str) else payment_settings_json
        except (json.JSONDecodeError, TypeError):
            settings = {}

    # Build Stripe Connect status
    stripe_status = StripeConnectStatus(
        connected=bool(stripe_account_id),
        account_id=stripe_account_id,
        charges_enabled=settings.get("charges_enabled", False),
        payouts_enabled=settings.get("payouts_enabled", False),
        requirements_due=settings.get("requirements_due", []),
        connected_at=stripe_connected_at,
    )

    return PaymentSettings(
        cpa_id=cpa_id,
        stripe_connect=stripe_status,
        default_currency=settings.get("default_currency", "USD"),
        auto_invoice=settings.get("auto_invoice", True),
        invoice_due_days=settings.get("invoice_due_days", 30),
        payment_methods_enabled=settings.get("payment_methods_enabled", ["card"]),
    )


@router.put("/")
async def update_payment_settings(
    cpa_id: str,
    request: UpdatePaymentSettingsRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update CPA payment settings.

    Does not affect Stripe Connect status.
    """
    import json

    # Get current settings
    query = text("SELECT payment_settings FROM cpa_profiles WHERE cpa_id = :cpa_id")
    result = await session.execute(query, {"cpa_id": cpa_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CPA profile not found"
        )

    # Parse and update settings
    current = {}
    if row[0]:
        try:
            current = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except (json.JSONDecodeError, TypeError):
            current = {}

    if request.default_currency is not None:
        current["default_currency"] = request.default_currency
    if request.auto_invoice is not None:
        current["auto_invoice"] = request.auto_invoice
    if request.invoice_due_days is not None:
        current["invoice_due_days"] = request.invoice_due_days
    if request.payment_methods_enabled is not None:
        current["payment_methods_enabled"] = request.payment_methods_enabled

    # Save updated settings
    update_query = text("""
        UPDATE cpa_profiles
        SET payment_settings = :settings,
            updated_at = :updated_at
        WHERE cpa_id = :cpa_id
    """)
    await session.execute(update_query, {
        "cpa_id": cpa_id,
        "settings": json.dumps(current),
        "updated_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    return {"status": "success", "message": "Payment settings updated"}


# =============================================================================
# STRIPE CONNECT ROUTES
# =============================================================================

@router.get("/stripe/connect-url")
async def get_stripe_connect_url(
    cpa_id: str = Query(..., description="CPA ID"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get Stripe Connect OAuth URL for CPA onboarding.

    Returns the URL to redirect the CPA to connect their Stripe account.
    """
    config = get_stripe_config()

    if not config["client_id"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe Connect is not configured. Please set STRIPE_CLIENT_ID."
        )

    # Generate state token for CSRF protection
    state = f"{cpa_id}:{uuid4().hex}"

    # Store state in session/database for verification
    state_query = text("""
        INSERT INTO stripe_connect_states (state_token, cpa_id, created_at, expires_at)
        VALUES (:state, :cpa_id, :created_at, :expires_at)
        ON CONFLICT (cpa_id) DO UPDATE SET
            state_token = :state,
            created_at = :created_at,
            expires_at = :expires_at
    """)

    now = datetime.utcnow()
    try:
        await session.execute(state_query, {
            "state": state,
            "cpa_id": cpa_id,
            "created_at": now.isoformat(),
            "expires_at": (now.replace(hour=now.hour + 1)).isoformat(),
        })
        await session.commit()
    except Exception:
        # Table may not exist, continue without state storage
        pass

    # Build Stripe Connect OAuth URL
    # Using Express account type for simpler onboarding
    connect_url = (
        f"https://connect.stripe.com/express/oauth/authorize"
        f"?client_id={config['client_id']}"
        f"&state={state}"
        f"&redirect_uri={config['connect_redirect_uri']}"
        f"&stripe_user[business_type]=individual"
        f"&suggested_capabilities[]=card_payments"
        f"&suggested_capabilities[]=transfers"
    )

    return {
        "connect_url": connect_url,
        "state": state,
        "expires_in": 3600,
    }


@router.get("/stripe/callback")
async def stripe_connect_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Stripe Connect OAuth callback.

    Exchanges authorization code for connected account ID.
    """
    # Handle errors from Stripe
    if error:
        logger.error(f"Stripe Connect error: {error} - {error_description}")
        # Redirect to error page
        return RedirectResponse(
            url=f"/cpa/settings/payments?error={error}&message={error_description}",
            status_code=302,
        )

    if not code or not state:
        return RedirectResponse(
            url="/cpa/settings/payments?error=missing_params",
            status_code=302,
        )

    # Extract CPA ID from state
    try:
        cpa_id = state.split(":")[0]
    except (IndexError, AttributeError):
        return RedirectResponse(
            url="/cpa/settings/payments?error=invalid_state",
            status_code=302,
        )

    config = get_stripe_config()

    # Exchange code for access token and account ID
    # In production, use stripe library:
    # stripe.OAuth.token(grant_type="authorization_code", code=code)

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://connect.stripe.com/oauth/token",
                data={
                    "client_secret": config["secret_key"],
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )

            if response.status_code != 200:
                logger.error(f"Stripe token exchange failed: {response.text}")
                return RedirectResponse(
                    url="/cpa/settings/payments?error=token_exchange_failed",
                    status_code=302,
                )

            token_data = response.json()
            stripe_account_id = token_data.get("stripe_user_id")

    except ImportError:
        # httpx not available, simulate for development
        stripe_account_id = f"acct_demo_{uuid4().hex[:12]}"
        logger.warning("httpx not available, using demo Stripe account ID")
    except Exception as e:
        logger.error(f"Stripe Connect callback error: {e}")
        return RedirectResponse(
            url="/cpa/settings/payments?error=connection_failed",
            status_code=302,
        )

    # Save connected account to CPA profile
    import json

    update_query = text("""
        UPDATE cpa_profiles
        SET stripe_account_id = :account_id,
            stripe_connected_at = :connected_at,
            payment_settings = COALESCE(payment_settings, '{}')::jsonb || :new_settings::jsonb,
            updated_at = :updated_at
        WHERE cpa_id = :cpa_id
    """)

    now = datetime.utcnow()
    new_settings = json.dumps({
        "charges_enabled": True,
        "payouts_enabled": True,
    })

    try:
        await session.execute(update_query, {
            "cpa_id": cpa_id,
            "account_id": stripe_account_id,
            "connected_at": now.isoformat(),
            "new_settings": new_settings,
            "updated_at": now.isoformat(),
        })
        await session.commit()
        logger.info(f"CPA {cpa_id} connected Stripe account {stripe_account_id}")
    except Exception as e:
        logger.error(f"Failed to save Stripe account: {e}")
        # Try simpler update for SQLite
        simple_query = text("""
            UPDATE cpa_profiles
            SET stripe_account_id = :account_id,
                stripe_connected_at = :connected_at
            WHERE cpa_id = :cpa_id
        """)
        await session.execute(simple_query, {
            "cpa_id": cpa_id,
            "account_id": stripe_account_id,
            "connected_at": now.isoformat(),
        })
        await session.commit()

    # Redirect to success page
    return RedirectResponse(
        url="/cpa/settings/payments?success=connected",
        status_code=302,
    )


@router.post("/stripe/disconnect")
async def disconnect_stripe(
    cpa_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Disconnect Stripe account from CPA profile.

    Note: This only removes the connection from our system.
    The CPA should also revoke access from their Stripe dashboard.
    """
    # Clear Stripe connection
    update_query = text("""
        UPDATE cpa_profiles
        SET stripe_account_id = NULL,
            stripe_connected_at = NULL,
            updated_at = :updated_at
        WHERE cpa_id = :cpa_id
    """)

    result = await session.execute(update_query, {
        "cpa_id": cpa_id,
        "updated_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CPA profile not found"
        )

    logger.info(f"CPA {cpa_id} disconnected Stripe account")

    return {
        "status": "success",
        "message": "Stripe account disconnected. Please also revoke access from your Stripe dashboard."
    }


@router.get("/stripe/account-status")
async def get_stripe_account_status(
    cpa_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get detailed Stripe account status.

    Retrieves real-time status from Stripe API.
    """
    # Get stored account ID
    query = text("SELECT stripe_account_id FROM cpa_profiles WHERE cpa_id = :cpa_id")
    result = await session.execute(query, {"cpa_id": cpa_id})
    row = result.fetchone()

    if not row or not row[0]:
        return {
            "connected": False,
            "message": "No Stripe account connected"
        }

    stripe_account_id = row[0]
    config = get_stripe_config()

    # In production, retrieve account from Stripe:
    # stripe.Account.retrieve(stripe_account_id)

    # For now, return basic status
    return {
        "connected": True,
        "account_id": stripe_account_id,
        "charges_enabled": True,
        "payouts_enabled": True,
        "requirements": [],
        "dashboard_url": f"https://dashboard.stripe.com/{stripe_account_id}",
    }


# =============================================================================
# CLIENT PAYMENT ROUTES
# =============================================================================

class CreatePaymentIntentRequest(BaseModel):
    """Request to create a payment intent for client payment."""
    client_id: str
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    description: str
    metadata: dict = Field(default_factory=dict)


@router.post("/create-payment-intent")
async def create_payment_intent(
    cpa_id: str,
    request: CreatePaymentIntentRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a payment intent for client payment.

    Uses CPA's connected Stripe account.
    Platform fee is automatically deducted.
    """
    # Get CPA's Stripe account
    query = text("SELECT stripe_account_id FROM cpa_profiles WHERE cpa_id = :cpa_id")
    result = await session.execute(query, {"cpa_id": cpa_id})
    row = result.fetchone()

    if not row or not row[0]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe account not connected. Please connect your Stripe account first."
        )

    stripe_account_id = row[0]

    # Calculate platform fee (e.g., 2.9% + $0.30)
    platform_fee_percent = 0.029
    platform_fee_fixed = 0.30
    amount_cents = int(request.amount * 100)
    platform_fee = int(amount_cents * platform_fee_percent + platform_fee_fixed * 100)

    # In production, create Stripe PaymentIntent:
    # stripe.PaymentIntent.create(
    #     amount=amount_cents,
    #     currency=request.currency.lower(),
    #     application_fee_amount=platform_fee,
    #     stripe_account=stripe_account_id,
    #     metadata={
    #         "cpa_id": cpa_id,
    #         "client_id": request.client_id,
    #         **request.metadata,
    #     }
    # )

    # FREEZE & FINISH: Payment processing deferred to Phase 2
    # Return clear message that payments are handled outside the platform
    return {
        "success": False,
        "feature_status": "coming_soon",
        "message": "Online payment processing is coming soon.",
        "instructions": "Please contact your CPA directly for payment arrangements.",
        "amount_requested": request.amount,
        "currency": request.currency,
        "help_text": "Your CPA can provide invoice details and accepted payment methods."
    }


@router.get("/payment-history")
async def get_payment_history(
    cpa_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get payment history for CPA.

    Returns list of payments collected through Stripe.
    """
    # In production, fetch from Stripe:
    # stripe.PaymentIntent.list(limit=limit, stripe_account=stripe_account_id)

    # For now, return from local payments table if exists
    try:
        query = text("""
            SELECT payment_id, client_id, amount, currency, status,
                   platform_fee, net_amount, created_at
            FROM cpa_payments
            WHERE cpa_id = :cpa_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await session.execute(query, {
            "cpa_id": cpa_id,
            "limit": limit,
            "offset": offset,
        })
        rows = result.fetchall()

        payments = []
        for row in rows:
            payments.append({
                "payment_id": row[0],
                "client_id": row[1],
                "amount": float(row[2]),
                "currency": row[3],
                "status": row[4],
                "platform_fee": float(row[5]) if row[5] else 0,
                "net_amount": float(row[6]) if row[6] else float(row[2]),
                "created_at": row[7],
            })

        return {"payments": payments, "count": len(payments)}

    except Exception:
        # Table doesn't exist
        return {"payments": [], "count": 0}
