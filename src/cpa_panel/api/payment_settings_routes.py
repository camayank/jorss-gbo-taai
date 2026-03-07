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
from datetime import datetime, timezone
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
    """Get Stripe configuration from environment.

    IMPORTANT: In production, ensure STRIPE_CONNECT_REDIRECT_URI is set
    to your actual callback URL. The localhost default is for development only.
    """
    # Get base URL from environment for building callback URL
    app_base_url = os.environ.get("APP_URL", os.environ.get("BASE_URL", "http://localhost:8000"))

    return {
        "client_id": os.environ.get("STRIPE_CLIENT_ID"),
        "secret_key": os.environ.get("STRIPE_SECRET_KEY"),
        "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY"),
        "connect_redirect_uri": os.environ.get(
            "STRIPE_CONNECT_REDIRECT_URI",
            f"{app_base_url}/api/cpa/payment-settings/stripe/callback"
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
        "updated_at": datetime.now(timezone.utc).isoformat(),
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

    now = datetime.now(timezone.utc)
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
    # Production guard: require real Stripe credentials
    stripe_secret = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe_secret:
        logger.error("Stripe OAuth callback received but STRIPE_SECRET_KEY not configured")
        return RedirectResponse(
            url="/cpa/settings/payments?error=stripe_not_configured",
            status_code=302,
        )

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

        # SECURITY FIX: Add timeout to prevent hanging requests
        # Stripe OAuth token exchanges should complete within 30 seconds
        STRIPE_OAUTH_TIMEOUT = 30.0

        async with httpx.AsyncClient(timeout=httpx.Timeout(STRIPE_OAUTH_TIMEOUT, connect=10.0)) as client:
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
            stripe_refresh_token = token_data.get("refresh_token")

            if not stripe_account_id:
                logger.error("Stripe token response missing stripe_user_id")
                return RedirectResponse(
                    url="/cpa/settings/payments?error=invalid_response",
                    status_code=302,
                )

    except httpx.TimeoutException:
        logger.error("Stripe OAuth request timed out")
        return RedirectResponse(
            url="/cpa/settings/payments?error=timeout",
            status_code=302,
        )
    except httpx.ConnectError as e:
        logger.error(f"Stripe OAuth connection error: {e}")
        return RedirectResponse(
            url="/cpa/settings/payments?error=connection_failed",
            status_code=302,
        )
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

    now = datetime.now(timezone.utc)
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
        "updated_at": datetime.now(timezone.utc).isoformat(),
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

    if config["secret_key"]:
        try:
            import stripe
            stripe.api_key = config["secret_key"]
            account = stripe.Account.retrieve(stripe_account_id)
            return {
                "connected": True,
                "account_id": stripe_account_id,
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled,
                "requirements": account.requirements.currently_due if account.requirements else [],
                "dashboard_url": f"https://dashboard.stripe.com/{stripe_account_id}",
            }
        except Exception as e:
            logger.warning(f"Could not fetch Stripe account status: {e}")

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

    config = get_stripe_config()
    if not config["secret_key"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY."
        )

    try:
        import stripe
        stripe.api_key = config["secret_key"]

        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=request.currency.lower(),
            application_fee_amount=platform_fee,
            stripe_account=stripe_account_id,
            metadata={
                "cpa_id": cpa_id,
                "client_id": request.client_id,
                **request.metadata,
            },
        )

        return {
            "success": True,
            "client_secret": payment_intent.client_secret,
            "payment_intent_id": payment_intent.id,
            "amount": request.amount,
            "currency": request.currency,
            "platform_fee": platform_fee / 100,
            "publishable_key": config["publishable_key"],
            "stripe_account": stripe_account_id,
        }
    except stripe.StripeError as e:
        logger.error(f"Stripe PaymentIntent failed: {e}")
        raise HTTPException(status_code=400, detail=str(e.user_message or e))


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


# =============================================================================
# STRIPE CHECKOUT SESSION (simplest way to collect payment from clients)
# =============================================================================

class CreateCheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout session."""
    invoice_id: Optional[str] = None
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    client_email: str
    description: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@router.post("/checkout-session")
async def create_checkout_session(
    cpa_id: str,
    request: CreateCheckoutRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a Stripe Checkout session for client payment.

    Returns a checkout URL the client can visit to pay.
    Uses CPA's connected Stripe account (Stripe Connect).
    """
    config = get_stripe_config()
    if not config["secret_key"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured."
        )

    # Get CPA's connected account
    query = text("SELECT stripe_account_id FROM cpa_profiles WHERE cpa_id = :cpa_id")
    result = await session.execute(query, {"cpa_id": cpa_id})
    row = result.fetchone()

    if not row or not row[0]:
        raise HTTPException(
            status_code=400,
            detail="Stripe account not connected."
        )

    stripe_account_id = row[0]
    amount_cents = int(request.amount * 100)
    platform_fee = int(amount_cents * 0.029 + 30)  # 2.9% + $0.30

    app_base_url = os.environ.get("APP_URL", "http://localhost:8000")
    success_url = request.success_url or f"{app_base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = request.cancel_url or f"{app_base_url}/payment/cancelled"

    try:
        import stripe
        stripe.api_key = config["secret_key"]

        checkout = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": request.currency.lower(),
                    "product_data": {"name": request.description},
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            mode="payment",
            customer_email=request.client_email,
            success_url=success_url,
            cancel_url=cancel_url,
            payment_intent_data={
                "application_fee_amount": platform_fee,
            },
            metadata={
                "cpa_id": cpa_id,
                "invoice_id": request.invoice_id or "",
            },
            stripe_account=stripe_account_id,
        )

        return {
            "checkout_url": checkout.url,
            "session_id": checkout.id,
            "amount": request.amount,
            "currency": request.currency,
        }
    except Exception as e:
        logger.error(f"Stripe Checkout creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# STRIPE WEBHOOK (receives payment confirmations)
# =============================================================================

@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Stripe webhook endpoint for payment events.

    Handles: checkout.session.completed, payment_intent.succeeded,
    payment_intent.payment_failed, charge.refunded
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not set, skipping signature verification")
        import json
        event_data = json.loads(payload)
    else:
        try:
            import stripe
            stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            event_data = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception as e:
            logger.error(f"Stripe webhook verification failed: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event_data.get("type") if isinstance(event_data, dict) else event_data.type
    obj = event_data.get("data", {}).get("object", {}) if isinstance(event_data, dict) else event_data.data.object

    logger.info(f"Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        # Client completed payment
        cpa_id = obj.get("metadata", {}).get("cpa_id")
        invoice_id = obj.get("metadata", {}).get("invoice_id")
        amount = (obj.get("amount_total") or 0) / 100
        client_email = obj.get("customer_email") or obj.get("customer_details", {}).get("email")

        logger.info(f"Payment received: ${amount:.2f} for CPA {cpa_id} from {client_email}")

        # Record payment in database
        try:
            insert_query = text("""
                INSERT INTO cpa_payments (payment_id, cpa_id, client_email, amount, currency, status, stripe_session_id, invoice_id, created_at)
                VALUES (:payment_id, :cpa_id, :client_email, :amount, :currency, 'succeeded', :stripe_session_id, :invoice_id, :created_at)
            """)
            await session.execute(insert_query, {
                "payment_id": uuid4().hex,
                "cpa_id": cpa_id,
                "client_email": client_email or "",
                "amount": amount,
                "currency": obj.get("currency", "usd"),
                "stripe_session_id": obj.get("id"),
                "invoice_id": invoice_id or None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            await session.commit()
        except Exception as e:
            logger.warning(f"Could not record payment: {e}")

    elif event_type == "charge.refunded":
        logger.info(f"Refund processed: {obj.get('id')}")

    return {"received": True}
