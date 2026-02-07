"""
E-Signature Webhook Integration

Provides webhook handlers for e-signature providers (DocuSign, HelloSign).
This is NOT a full signing flow - just webhook receipt and status updates.

Scope:
- Receive webhook callbacks from e-sign providers
- Update engagement letter status
- Emit events for downstream processing

NOT in scope:
- Initiating signing flows (done via provider API by integrator)
- Document rendering (letters are plain text for provider to format)
- Signing UI
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


class ESignProvider(str, Enum):
    """Supported e-signature providers."""
    DOCUSIGN = "docusign"
    HELLOSIGN = "hellosign"
    PANDADOC = "pandadoc"
    GENERIC = "generic"


class ESignStatus(str, Enum):
    """E-signature status values."""
    PENDING = "pending"           # Letter generated, not yet sent
    SENT = "sent"                 # Sent to client for signature
    VIEWED = "viewed"             # Client viewed the document
    SIGNED = "signed"             # Client signed
    DECLINED = "declined"         # Client declined to sign
    VOIDED = "voided"             # CPA voided the request
    EXPIRED = "expired"           # Signing request expired


@dataclass
class ESignEvent:
    """E-signature event from webhook."""
    provider: ESignProvider
    event_type: str
    envelope_id: str
    letter_id: Optional[str]
    status: ESignStatus
    signer_email: Optional[str]
    signed_at: Optional[datetime]
    raw_payload: Dict[str, Any]


class ESignWebhookHandler:
    """
    Handles webhooks from e-signature providers.

    Usage:
        handler = ESignWebhookHandler()
        handler.register_callback(on_signed_callback)

        # In webhook endpoint:
        event = handler.process_webhook(provider, payload, signature, secret)
        # Status is automatically updated and callbacks fired
    """

    def __init__(self):
        """Initialize webhook handler."""
        self._callbacks: list[Callable[[ESignEvent], None]] = []
        self._letter_store: Dict[str, Dict[str, Any]] = {}  # envelope_id -> letter data

    def register_callback(self, callback: Callable[[ESignEvent], None]):
        """Register a callback for e-sign events."""
        self._callbacks.append(callback)

    def register_letter(self, envelope_id: str, letter_id: str, session_id: str):
        """
        Register a letter for webhook tracking.

        Call this after sending a letter for e-signature.
        """
        self._letter_store[envelope_id] = {
            "letter_id": letter_id,
            "session_id": session_id,
            "registered_at": datetime.utcnow().isoformat(),
        }

    def process_webhook(
        self,
        provider: ESignProvider,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> Optional[ESignEvent]:
        """
        Process an incoming webhook from an e-sign provider.

        Args:
            provider: Which e-sign provider sent this
            payload: Raw webhook payload
            signature: Webhook signature header (for verification)
            secret: Shared secret for signature verification

        Returns:
            Parsed ESignEvent or None if invalid
        """
        # Verify signature if provided
        if signature and secret:
            if not self._verify_signature(provider, payload, signature, secret):
                logger.warning(f"Invalid webhook signature from {provider}")
                return None

        # Parse based on provider
        event = self._parse_webhook(provider, payload)
        if not event:
            logger.warning(f"Could not parse webhook from {provider}")
            return None

        # Fire callbacks
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return event

    def _verify_signature(
        self,
        provider: ESignProvider,
        payload: Dict[str, Any],
        signature: str,
        secret: str,
    ) -> bool:
        """Verify webhook signature."""
        if provider == ESignProvider.DOCUSIGN:
            # DocuSign uses HMAC-SHA256
            import json
            payload_bytes = json.dumps(payload, separators=(',', ':')).encode()
            expected = hmac.new(
                secret.encode(),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)

        elif provider == ESignProvider.HELLOSIGN:
            # HelloSign uses HMAC-SHA256 with event_time
            event_time = payload.get("event", {}).get("event_time", "")
            expected = hmac.new(
                secret.encode(),
                f"{event_time}".encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)

        elif provider == ESignProvider.PANDADOC:
            # PandaDoc uses HMAC-SHA256 on the JSON payload
            import json
            payload_bytes = json.dumps(payload, separators=(',', ':')).encode()
            expected = hmac.new(
                secret.encode(),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)

        # Generic fallback - require valid signature format but can't verify
        logger.warning(f"No signature verification implemented for {provider}")
        return False  # Fail closed for unknown providers

    def _parse_webhook(
        self,
        provider: ESignProvider,
        payload: Dict[str, Any],
    ) -> Optional[ESignEvent]:
        """Parse webhook payload into ESignEvent."""
        try:
            if provider == ESignProvider.DOCUSIGN:
                return self._parse_docusign(payload)
            elif provider == ESignProvider.HELLOSIGN:
                return self._parse_hellosign(payload)
            elif provider == ESignProvider.PANDADOC:
                return self._parse_pandadoc(payload)
            else:
                return self._parse_generic(payload)
        except Exception as e:
            logger.error(f"Parse error for {provider}: {e}")
            return None

    def _parse_docusign(self, payload: Dict[str, Any]) -> Optional[ESignEvent]:
        """Parse DocuSign webhook."""
        event_type = payload.get("event", "")
        envelope_id = payload.get("data", {}).get("envelopeId", "")

        # Map DocuSign events to our status
        status_map = {
            "envelope-sent": ESignStatus.SENT,
            "envelope-delivered": ESignStatus.VIEWED,
            "envelope-completed": ESignStatus.SIGNED,
            "envelope-declined": ESignStatus.DECLINED,
            "envelope-voided": ESignStatus.VOIDED,
        }
        status = status_map.get(event_type, ESignStatus.PENDING)

        # Get signer info
        recipients = payload.get("data", {}).get("envelopeSummary", {}).get("recipients", {})
        signers = recipients.get("signers", [])
        signer_email = signers[0].get("email") if signers else None

        # Get signed timestamp
        signed_at = None
        if status == ESignStatus.SIGNED:
            completed = payload.get("data", {}).get("envelopeSummary", {}).get("completedDateTime")
            if completed:
                signed_at = datetime.fromisoformat(completed.replace("Z", "+00:00"))

        # Look up letter ID
        letter_data = self._letter_store.get(envelope_id, {})

        return ESignEvent(
            provider=ESignProvider.DOCUSIGN,
            event_type=event_type,
            envelope_id=envelope_id,
            letter_id=letter_data.get("letter_id"),
            status=status,
            signer_email=signer_email,
            signed_at=signed_at,
            raw_payload=payload,
        )

    def _parse_hellosign(self, payload: Dict[str, Any]) -> Optional[ESignEvent]:
        """Parse HelloSign/Dropbox Sign webhook."""
        event = payload.get("event", {})
        event_type = event.get("event_type", "")
        signature_request = payload.get("signature_request", {})
        envelope_id = signature_request.get("signature_request_id", "")

        # Map HelloSign events to our status
        status_map = {
            "signature_request_sent": ESignStatus.SENT,
            "signature_request_viewed": ESignStatus.VIEWED,
            "signature_request_signed": ESignStatus.SIGNED,
            "signature_request_declined": ESignStatus.DECLINED,
            "signature_request_canceled": ESignStatus.VOIDED,
        }
        status = status_map.get(event_type, ESignStatus.PENDING)

        # Get signer info
        signatures = signature_request.get("signatures", [])
        signer_email = signatures[0].get("signer_email_address") if signatures else None

        # Get signed timestamp
        signed_at = None
        if status == ESignStatus.SIGNED and signatures:
            signed_ts = signatures[0].get("signed_at")
            if signed_ts:
                signed_at = datetime.fromtimestamp(signed_ts)

        letter_data = self._letter_store.get(envelope_id, {})

        return ESignEvent(
            provider=ESignProvider.HELLOSIGN,
            event_type=event_type,
            envelope_id=envelope_id,
            letter_id=letter_data.get("letter_id"),
            status=status,
            signer_email=signer_email,
            signed_at=signed_at,
            raw_payload=payload,
        )

    def _parse_pandadoc(self, payload: Dict[str, Any]) -> Optional[ESignEvent]:
        """Parse PandaDoc webhook."""
        event_type = payload.get("event", "")
        data = payload.get("data", {})
        envelope_id = data.get("id", "")

        status_map = {
            "document_state_changed:document.sent": ESignStatus.SENT,
            "document_state_changed:document.viewed": ESignStatus.VIEWED,
            "document_state_changed:document.completed": ESignStatus.SIGNED,
            "document_state_changed:document.voided": ESignStatus.VOIDED,
        }
        status = status_map.get(event_type, ESignStatus.PENDING)

        letter_data = self._letter_store.get(envelope_id, {})

        return ESignEvent(
            provider=ESignProvider.PANDADOC,
            event_type=event_type,
            envelope_id=envelope_id,
            letter_id=letter_data.get("letter_id"),
            status=status,
            signer_email=data.get("recipients", [{}])[0].get("email"),
            signed_at=datetime.utcnow() if status == ESignStatus.SIGNED else None,
            raw_payload=payload,
        )

    def _parse_generic(self, payload: Dict[str, Any]) -> Optional[ESignEvent]:
        """Parse generic webhook format."""
        return ESignEvent(
            provider=ESignProvider.GENERIC,
            event_type=payload.get("event_type", "unknown"),
            envelope_id=payload.get("envelope_id", payload.get("document_id", "")),
            letter_id=payload.get("letter_id"),
            status=ESignStatus(payload.get("status", "pending")),
            signer_email=payload.get("signer_email"),
            signed_at=datetime.fromisoformat(payload["signed_at"]) if payload.get("signed_at") else None,
            raw_payload=payload,
        )


# Singleton for application-wide use
_esign_handler: Optional[ESignWebhookHandler] = None


def get_esign_handler() -> ESignWebhookHandler:
    """Get the global e-sign webhook handler."""
    global _esign_handler
    if _esign_handler is None:
        _esign_handler = ESignWebhookHandler()
    return _esign_handler
