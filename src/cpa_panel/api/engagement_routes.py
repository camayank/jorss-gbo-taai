"""
Engagement Letter API Routes

Endpoints for generating and managing engagement letters.

Scope:
- Generate engagement letters
- Get letter content
- Receive e-sign webhooks

NOT in scope:
- Contract negotiation
- Version management
- Full CRM functionality
"""

import os
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import Response
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from ..engagement import (
    EngagementLetterGenerator,
    EngagementLetterType,
    EngagementLetter,
    ESignWebhookHandler,
    ESignProvider,
    PDF_AVAILABLE,
)
from ..engagement.esign_hooks import get_esign_handler
from .common import format_success_response, format_error_response, get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/engagement", tags=["engagement"])


# SECURITY FIX: E-sign webhook secrets from environment
# Each provider should have its own secret configured
ESIGN_WEBHOOK_SECRETS = {
    "docusign": os.environ.get("DOCUSIGN_WEBHOOK_SECRET"),
    "hellosign": os.environ.get("HELLOSIGN_WEBHOOK_SECRET"),
    "pandadoc": os.environ.get("PANDADOC_WEBHOOK_SECRET"),
}

# Persistent storage for engagement letters (SQLite-backed with in-memory fallback)
import json
import sqlite3

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "engagement_letters.db")


def _get_letter_db():
    """Get or create the engagement letters SQLite database."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS engagement_letters (
            letter_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_el_tenant ON engagement_letters(tenant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_el_session ON engagement_letters(session_id)")
    conn.commit()
    return conn


def _store_letter(letter: EngagementLetter):
    """Persist an engagement letter."""
    try:
        conn = _get_letter_db()
        conn.execute(
            "INSERT OR REPLACE INTO engagement_letters (letter_id, tenant_id, session_id, data) VALUES (?, ?, ?, ?)",
            (letter.letter_id, letter.tenant_id, letter.session_id, json.dumps(letter.to_dict())),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to persist letter {letter.letter_id}: {e}")
        _letters_fallback[letter.letter_id] = letter


def _load_letter(letter_id: str, tenant_id: Optional[str] = None) -> Optional[EngagementLetter]:
    """Load an engagement letter by ID, optionally scoped by tenant."""
    try:
        conn = _get_letter_db()
        if tenant_id:
            row = conn.execute(
                "SELECT data FROM engagement_letters WHERE letter_id = ? AND tenant_id = ?",
                (letter_id, tenant_id),
            ).fetchone()
        else:
            row = conn.execute("SELECT data FROM engagement_letters WHERE letter_id = ?", (letter_id,)).fetchone()
        conn.close()
        if row:
            data = json.loads(row[0])
            return _dict_to_letter(data)
    except Exception as e:
        logger.warning(f"DB load failed for letter {letter_id}: {e}")
    fallback = _letters_fallback.get(letter_id)
    if fallback and tenant_id and getattr(fallback, 'tenant_id', None) != tenant_id:
        return None
    return fallback


def _load_letters_for_session(session_id: str, tenant_id: str) -> list:
    """Load all engagement letters for a session."""
    try:
        conn = _get_letter_db()
        rows = conn.execute(
            "SELECT data FROM engagement_letters WHERE session_id = ? AND tenant_id = ?",
            (session_id, tenant_id),
        ).fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]
    except Exception as e:
        logger.warning(f"DB load failed for session {session_id}: {e}")
    return [
        l.to_dict() for l in _letters_fallback.values()
        if l.session_id == session_id and l.tenant_id == tenant_id
    ]


def _dict_to_letter(data: dict) -> EngagementLetter:
    """Reconstruct an EngagementLetter from a dict (best-effort)."""
    letter = EngagementLetter.__new__(EngagementLetter)
    for k, v in data.items():
        setattr(letter, k, v)
    return letter


_letters_fallback: Dict[str, EngagementLetter] = {}
_generator = EngagementLetterGenerator()


@router.post("/letters/generate")
async def generate_engagement_letter(
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate an engagement letter for a client.

    Required fields:
    - session_id: Tax return session ID
    - letter_type: "tax_preparation" | "tax_advisory" | "tax_planning" | "amended_return"
    - cpa_firm_name: Name of the CPA firm
    - cpa_name: CPA's name
    - cpa_credentials: CPA's credentials (e.g., "CPA, MST")
    - firm_address: Firm's address
    - client_name: Client's full name
    - client_email: Client's email
    - client_address: Client's address
    - tax_year: Tax year (e.g., 2025)
    - complexity_tier: Complexity tier name
    - fee_amount: Engagement fee (number)

    Optional:
    - services: List of service descriptions (auto-generated if not provided)
    - fee_description: Additional fee terms
    """
    tenant_id = get_tenant_id(request)

    required_fields = [
        "session_id", "letter_type", "cpa_firm_name", "cpa_name",
        "cpa_credentials", "firm_address", "client_name", "client_email",
        "client_address", "tax_year", "complexity_tier", "fee_amount"
    ]

    for field in required_fields:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    try:
        letter_type = EngagementLetterType(body["letter_type"])
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid letter_type. Must be one of: {[t.value for t in EngagementLetterType]}"
        )

    # Get services list
    services = body.get("services")
    if not services:
        services = _generator.get_services_for_complexity(
            body["complexity_tier"],
            letter_type
        )

    # Generate letter
    letter = _generator.generate(
        session_id=body["session_id"],
        tenant_id=tenant_id,
        letter_type=letter_type,
        cpa_firm_name=body["cpa_firm_name"],
        cpa_name=body["cpa_name"],
        cpa_credentials=body["cpa_credentials"],
        firm_address=body["firm_address"],
        client_name=body["client_name"],
        client_email=body["client_email"],
        client_address=body["client_address"],
        tax_year=int(body["tax_year"]),
        complexity_tier=body["complexity_tier"],
        services=services,
        fee_amount=float(body["fee_amount"]),
        fee_description=body.get("fee_description", ""),
    )

    # Store letter (persisted to SQLite)
    _store_letter(letter)

    logger.info(f"Generated engagement letter {letter.letter_id} for session {body['session_id']}")

    return format_success_response({
        "letter": letter.to_dict(),
        "content": letter.letter_content,
    })


@router.get("/letters/{letter_id}")
async def get_engagement_letter(
    request: Request,
    letter_id: str,
) -> Dict[str, Any]:
    """Get an engagement letter by ID."""
    tenant_id = get_tenant_id(request)

    letter = _load_letter(letter_id, tenant_id=tenant_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    letter_dict = letter.to_dict() if hasattr(letter, 'to_dict') else letter.__dict__

    return format_success_response({
        "letter": letter_dict,
        "content": letter_dict.get("letter_content", ""),
    })


@router.get("/letters/session/{session_id}")
async def get_letters_for_session(
    request: Request,
    session_id: str,
) -> Dict[str, Any]:
    """Get all engagement letters for a session."""
    tenant_id = get_tenant_id(request)

    letters = _load_letters_for_session(session_id, tenant_id)

    return format_success_response({
        "session_id": session_id,
        "letters": letters,
        "count": len(letters),
    })


@router.post("/letters/{letter_id}/send-for-signature")
async def send_for_signature(
    request: Request,
    letter_id: str,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Mark a letter as sent for e-signature.

    This endpoint is called AFTER the integrator has sent the letter
    via their e-sign provider (DocuSign, HelloSign, etc.).

    Required:
    - envelope_id: The e-sign provider's envelope/request ID
    """
    tenant_id = get_tenant_id(request)

    letter = _load_letter(letter_id, tenant_id=tenant_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    envelope_id = body.get("envelope_id")
    if not envelope_id:
        raise HTTPException(status_code=400, detail="envelope_id is required")

    # Update letter status
    letter.esign_status = "sent"
    letter.esign_envelope_id = envelope_id

    # Register with webhook handler
    handler = get_esign_handler()
    handler.register_letter(envelope_id, letter_id, letter.session_id)

    logger.info(f"Letter {letter_id} sent for signature, envelope: {envelope_id}")

    return format_success_response({
        "letter_id": letter_id,
        "esign_status": letter.esign_status,
        "envelope_id": envelope_id,
    })


@router.post("/webhooks/esign/{provider}")
async def esign_webhook(
    request: Request,
    provider: str,
    x_signature: Optional[str] = Header(None, alias="X-DocuSign-Signature-1"),
    x_hellosign_signature: Optional[str] = Header(None, alias="X-HelloSign-Signature"),
    x_pandadoc_signature: Optional[str] = Header(None, alias="X-PandaDoc-Signature"),
) -> Dict[str, Any]:
    """
    Receive e-signature webhook callbacks.

    Supported providers: docusign, hellosign, pandadoc, generic

    The signature header varies by provider:
    - DocuSign: X-DocuSign-Signature-1
    - HelloSign: X-HelloSign-Signature
    - PandaDoc: X-PandaDoc-Signature

    SECURITY: Webhook signatures are validated when a secret is configured
    for the provider. Configure secrets via environment variables:
    - DOCUSIGN_WEBHOOK_SECRET
    - HELLOSIGN_WEBHOOK_SECRET
    - PANDADOC_WEBHOOK_SECRET
    """
    try:
        esign_provider = ESignProvider(provider.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider. Must be one of: {[p.value for p in ESignProvider]}"
        )

    # Get signature based on provider
    if provider.lower() == "docusign":
        signature = x_signature
    elif provider.lower() == "hellosign":
        signature = x_hellosign_signature
    elif provider.lower() == "pandadoc":
        signature = x_pandadoc_signature
    else:
        signature = x_signature or x_hellosign_signature or x_pandadoc_signature

    # SECURITY FIX: Get webhook secret from configuration
    webhook_secret = ESIGN_WEBHOOK_SECRETS.get(provider.lower())

    # If a secret is configured, signature is required
    if webhook_secret and not signature:
        logger.warning(f"E-sign webhook from {provider} missing required signature")
        raise HTTPException(
            status_code=401,
            detail="Missing webhook signature"
        )

    # Parse body
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Process webhook with signature validation
    handler = get_esign_handler()
    event = handler.process_webhook(
        provider=esign_provider,
        payload=payload,
        signature=signature,
        secret=webhook_secret,  # SECURITY FIX: Use configured secret
    )

    # If signature validation failed (when secret is configured)
    if webhook_secret and signature and not event:
        logger.warning(f"E-sign webhook from {provider} failed signature validation")
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )

    if not event:
        logger.warning(f"Could not process webhook from {provider}")
        return {"status": "ignored"}

    # Update letter if we found it
    if event.letter_id:
        letter = _load_letter(event.letter_id)
        if letter:
            letter.esign_status = event.status.value
            if event.signed_at:
                letter.signed_at = event.signed_at
            _store_letter(letter)
            logger.info(f"Letter {event.letter_id} status updated to {event.status.value}")

    return {"status": "received", "event_type": event.event_type}


@router.get("/complexity-services/{tier}")
async def get_services_for_tier(
    tier: str,
    letter_type: str = "tax_preparation",
) -> Dict[str, Any]:
    """Get default services list for a complexity tier."""
    try:
        lt = EngagementLetterType(letter_type)
    except ValueError:
        lt = EngagementLetterType.TAX_PREPARATION

    services = _generator.get_services_for_complexity(tier, lt)

    return format_success_response({
        "complexity_tier": tier,
        "letter_type": letter_type,
        "services": services,
    })


@router.get("/letters/{letter_id}/pdf")
async def download_letter_pdf(
    request: Request,
    letter_id: str,
) -> Response:
    """
    Download engagement letter as PDF.

    Generates a professional PDF document suitable for printing or e-signing.
    """
    if not PDF_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="PDF generation is not available. Install reportlab with: pip install reportlab"
        )

    tenant_id = get_tenant_id(request)

    letter = _load_letter(letter_id, tenant_id=tenant_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    try:
        from ..engagement import get_pdf_generator

        pdf_generator = get_pdf_generator()

        # Build letter content dict
        letter_content = {
            "letter_type": letter.letter_type.value,
            "cpa_firm_name": letter.cpa_firm_name,
            "cpa_name": letter.cpa_name,
            "cpa_credentials": letter.cpa_credentials,
            "firm_address": "",  # Not stored in EngagementLetter
            "client_name": letter.client_name,
            "client_address": "",  # Not stored in EngagementLetter
            "tax_year": letter.tax_year,
            "complexity_tier": letter.complexity_tier,
            "services": letter.services_description.split("; "),
            "fee_amount": letter.fee_amount,
            "fee_description": letter.fee_description,
            "generated_at": letter.generated_at.isoformat(),
        }

        # Get branding from request headers (optional)
        branding = {
            "primary_color": request.headers.get("X-Primary-Color", "#1e3a5f"),
        }

        pdf_bytes = pdf_generator.generate_pdf(letter_content, branding)

        # Create filename
        filename = f"engagement_letter_{letter.client_name.replace(' ', '_')}_{letter.tax_year}.pdf"

        logger.info(f"Generated PDF for letter {letter_id}")

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            }
        )

    except Exception as e:
        logger.error(f"Failed to generate PDF for letter {letter_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF")
