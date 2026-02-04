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

# In-memory storage for letters (replace with DB in production)
_letters: Dict[str, EngagementLetter] = {}
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

    # Store letter
    _letters[letter.letter_id] = letter

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

    letter = _letters.get(letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    if letter.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Letter not found")

    return format_success_response({
        "letter": letter.to_dict(),
        "content": letter.letter_content,
    })


@router.get("/letters/session/{session_id}")
async def get_letters_for_session(
    request: Request,
    session_id: str,
) -> Dict[str, Any]:
    """Get all engagement letters for a session."""
    tenant_id = get_tenant_id(request)

    letters = [
        letter.to_dict()
        for letter in _letters.values()
        if letter.session_id == session_id and letter.tenant_id == tenant_id
    ]

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

    letter = _letters.get(letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    if letter.tenant_id != tenant_id:
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
) -> Dict[str, Any]:
    """
    Receive e-signature webhook callbacks.

    Supported providers: docusign, hellosign, pandadoc, generic

    The signature header varies by provider:
    - DocuSign: X-DocuSign-Signature-1
    - HelloSign: X-HelloSign-Signature
    """
    try:
        esign_provider = ESignProvider(provider.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider. Must be one of: {[p.value for p in ESignProvider]}"
        )

    # Get signature based on provider
    signature = x_signature or x_hellosign_signature

    # Parse body
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Process webhook
    handler = get_esign_handler()
    event = handler.process_webhook(
        provider=esign_provider,
        payload=payload,
        signature=signature,
        secret=None,  # Secret should come from config in production
    )

    if not event:
        logger.warning(f"Could not process webhook from {provider}")
        return {"status": "ignored"}

    # Update letter if we found it
    if event.letter_id and event.letter_id in _letters:
        letter = _letters[event.letter_id]
        letter.esign_status = event.status.value
        if event.signed_at:
            letter.signed_at = event.signed_at

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

    letter = _letters.get(letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    if letter.tenant_id != tenant_id:
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
