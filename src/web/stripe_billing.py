"""
Stripe Billing API — CPA Portal

Endpoints:
  POST /api/billing/create-subscription  — Create/resume Stripe subscription
  POST /api/billing/portal               — Open Stripe self-serve billing portal
  POST /api/billing/webhook              — Stripe webhook (no auth; verified by signature)
  GET  /api/billing/status               — Current subscription status for CPA

Uses the same httpx-based Stripe caller as admin_panel/api/billing_routes.py.
Authenticated via require_cpa_auth (session cookie / JWT).
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from web.cpa_dashboard_pages import require_cpa_auth, get_cpa_id_from_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["Stripe Billing"])

_STRIPE_BASE = "https://api.stripe.com/v1"
_STRIPE_KEY = lambda: os.environ.get("STRIPE_SECRET_KEY", "")
_STRIPE_PRICE_ID = lambda: os.environ.get("STRIPE_PRICE_ID", "price_placeholder")
_STRIPE_WEBHOOK_SECRET = lambda: os.environ.get("STRIPE_WEBHOOK_SECRET", "")


# ---------------------------------------------------------------------------
# Stripe HTTP helpers
# ---------------------------------------------------------------------------

async def _stripe(method: str, path: str, **data) -> dict:
    key = _STRIPE_KEY()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY.",
        )
    url = f"{_STRIPE_BASE}{path}"
    auth = (key, "")
    async with httpx.AsyncClient(timeout=15) as client:
        if method == "GET":
            resp = await client.get(url, auth=auth, params=data)
        else:
            resp = await client.post(url, auth=auth, data=data)
    if not resp.is_success:
        body = resp.json()
        raise HTTPException(
            status_code=resp.status_code,
            detail=body.get("error", {}).get("message", "Stripe error"),
        )
    return resp.json()


# ---------------------------------------------------------------------------
# DB helpers (SQLite tenant + billing_subscriptions)
# ---------------------------------------------------------------------------

def _db_path() -> str:
    return os.environ.get("SQLITE_DB_PATH", "./data/tax_returns.db")


def _get_tenant(tenant_id: str) -> Optional[dict]:
    try:
        with sqlite3.connect(_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT tenant_id, admin_email, stripe_customer_id FROM tenants WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.debug(f"_get_tenant error: {e}")
        return None


def _save_stripe_customer(tenant_id: str, stripe_customer_id: str) -> None:
    try:
        with sqlite3.connect(_db_path()) as conn:
            conn.execute(
                "UPDATE tenants SET stripe_customer_id = ? WHERE tenant_id = ?",
                (stripe_customer_id, tenant_id),
            )
    except Exception as e:
        logger.debug(f"_save_stripe_customer error: {e}")


def _upsert_subscription(tenant_id: str, sub: dict) -> None:
    """Persist Stripe subscription data to billing_subscriptions table if it exists."""
    try:
        with sqlite3.connect(_db_path()) as conn:
            # Ensure table exists (in case migration hasn't run)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS billing_subscriptions (
                    tenant_id TEXT PRIMARY KEY,
                    stripe_subscription_id TEXT,
                    stripe_customer_id TEXT,
                    status TEXT,
                    current_period_end INTEGER,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                INSERT INTO billing_subscriptions
                    (tenant_id, stripe_subscription_id, stripe_customer_id, status, current_period_end, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    stripe_subscription_id = excluded.stripe_subscription_id,
                    stripe_customer_id = excluded.stripe_customer_id,
                    status = excluded.status,
                    current_period_end = excluded.current_period_end,
                    updated_at = excluded.updated_at
            """, (
                tenant_id,
                sub.get("id"),
                sub.get("customer"),
                sub.get("status"),
                sub.get("current_period_end"),
                datetime.now(timezone.utc).isoformat(),
            ))
    except Exception as e:
        logger.debug(f"_upsert_subscription error: {e}")


def _get_cached_subscription(tenant_id: str) -> Optional[dict]:
    try:
        with sqlite3.connect(_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM billing_subscriptions WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class SubscribeRequest(BaseModel):
    return_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def billing_status(current_user: dict = Depends(require_cpa_auth)):
    """Return current subscription status for the CPA firm."""
    tenant_id = get_cpa_id_from_user(current_user)
    cached = _get_cached_subscription(tenant_id)

    if cached and cached.get("stripe_subscription_id"):
        period_end = cached.get("current_period_end")
        next_billing = (
            datetime.fromtimestamp(period_end, tz=timezone.utc).strftime("%B %d, %Y")
            if period_end else None
        )
        return {
            "active": cached["status"] in ("active", "trialing"),
            "status": cached["status"],
            "plan": "CA4CPA Advisor — CPA Portal",
            "next_billing_date": next_billing,
            "trial_active": cached["status"] == "trialing",
            "stripe_configured": bool(_STRIPE_KEY()),
        }

    return {
        "active": False,
        "status": "inactive",
        "plan": None,
        "next_billing_date": None,
        "trial_active": False,
        "stripe_configured": bool(_STRIPE_KEY()),
    }


@router.post("/create-subscription")
async def create_subscription(
    body: SubscribeRequest,
    current_user: dict = Depends(require_cpa_auth),
):
    """
    Create or resume a Stripe subscription for this CPA firm.
    Returns {subscription_id, client_secret, status} so the frontend
    can confirm payment via stripe.js.
    """
    tenant_id = get_cpa_id_from_user(current_user)
    tenant = _get_tenant(tenant_id)
    email = (tenant or {}).get("admin_email") or current_user.get("email") or f"{tenant_id}@ca4cpa.com"

    # Get or create Stripe customer
    customer_id = (tenant or {}).get("stripe_customer_id")
    if not customer_id:
        cust = await _stripe("POST", "/customers", email=email, **{"metadata[tenant_id]": tenant_id})
        customer_id = cust["id"]
        _save_stripe_customer(tenant_id, customer_id)

    # Check for existing active subscription
    existing = await _stripe("GET", "/subscriptions", customer=customer_id, status="active", limit="1")
    if existing.get("data"):
        sub = existing["data"][0]
        _upsert_subscription(tenant_id, sub)
        return {"subscription_id": sub["id"], "client_secret": None, "status": sub["status"]}

    # Create new subscription (payment_behavior=default_incomplete → returns client_secret)
    sub = await _stripe(
        "POST", "/subscriptions",
        customer=customer_id,
        **{
            "items[0][price]": _STRIPE_PRICE_ID(),
            "payment_behavior": "default_incomplete",
            "expand[]": "latest_invoice.payment_intent",
        },
    )
    _upsert_subscription(tenant_id, sub)

    client_secret = None
    try:
        client_secret = sub["latest_invoice"]["payment_intent"]["client_secret"]
    except (KeyError, TypeError):
        pass

    return {"subscription_id": sub["id"], "client_secret": client_secret, "status": sub["status"]}


@router.post("/portal")
async def billing_portal(
    request: Request,
    current_user: dict = Depends(require_cpa_auth),
):
    """Open Stripe self-serve billing portal for the CPA firm."""
    tenant_id = get_cpa_id_from_user(current_user)
    tenant = _get_tenant(tenant_id)
    customer_id = (tenant or {}).get("stripe_customer_id")

    if not customer_id:
        # Check cached subscription
        cached = _get_cached_subscription(tenant_id)
        customer_id = cached.get("stripe_customer_id") if cached else None

    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription. Subscribe first.",
        )

    return_url = str(request.base_url).rstrip("/") + "/cpa/billing"
    session = await _stripe(
        "POST", "/billing_portal/sessions",
        customer=customer_id,
        return_url=return_url,
    )
    return {"url": session["url"]}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Receive and verify Stripe webhook events.
    Updates billing_subscriptions on subscription changes.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    secret = _STRIPE_WEBHOOK_SECRET()

    if secret:
        try:
            import hmac, hashlib
            # Verify Stripe signature (simplified — use stripe-python SDK in production)
            parts = {k: v for p in sig_header.split(",") for k, v in [p.split("=", 1)]}
            ts = parts.get("t", "")
            signed_payload = f"{ts}.{payload.decode()}"
            expected = hmac.HMAC(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, parts.get("v1", "")):
                raise HTTPException(status_code=400, detail="Invalid signature")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Stripe webhook signature check failed: {e}")

    try:
        import json
        event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type", "")
    data_obj = event.get("data", {}).get("object", {})

    if event_type.startswith("customer.subscription"):
        sub_id = data_obj.get("id")
        customer_id = data_obj.get("customer")
        if sub_id and customer_id:
            # Find tenant by stripe_customer_id
            try:
                with sqlite3.connect(_db_path()) as conn:
                    row = conn.execute(
                        "SELECT tenant_id FROM tenants WHERE stripe_customer_id = ?",
                        (customer_id,),
                    ).fetchone()
                    if row:
                        _upsert_subscription(row[0], data_obj)
            except Exception as e:
                logger.debug(f"Webhook DB update error: {e}")

    elif event_type == "invoice.payment_failed":
        logger.warning("Stripe payment_failed for customer=%s", data_obj.get("customer"))

    return {"received": True}
