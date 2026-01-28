"""
Webhook Triggers

Helper functions to emit webhook events from application code.
These functions handle errors gracefully to ensure the main operation
succeeds even if webhook delivery fails.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def _safe_emit(event_type: str, firm_id: str, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Safely emit a webhook event, catching and logging any errors.

    This ensures the main application flow is not interrupted if webhook
    delivery fails.
    """
    try:
        from webhooks.events import emit_webhook_event, WebhookEventType

        # Convert string to enum if needed
        event_enum = None
        for et in WebhookEventType:
            if et.value == event_type:
                event_enum = et
                break

        if event_enum:
            emit_webhook_event(
                event_type=event_enum,
                firm_id=firm_id,
                data=data,
                metadata=metadata,
                async_delivery=True,  # Always async to not block main flow
            )
        else:
            logger.warning(f"[WEBHOOK TRIGGER] Unknown event type: {event_type}")

    except ImportError:
        # Webhooks module not available
        logger.debug("[WEBHOOK TRIGGER] Webhooks module not available")
    except Exception as e:
        # Log but don't raise - webhook failure shouldn't break main flow
        logger.error(f"[WEBHOOK TRIGGER] Failed to emit {event_type}: {e}")


# =============================================================================
# CLIENT EVENTS
# =============================================================================

def trigger_client_created(
    firm_id: str,
    client_id: str,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    created_by: Optional[str] = None,
) -> None:
    """Trigger webhook when a client is created."""
    _safe_emit(
        event_type="client.created",
        firm_id=firm_id,
        data={
            "client_id": client_id,
            "name": name,
            "email": email,
            "phone": phone,
            "created_at": datetime.utcnow().isoformat(),
        },
        metadata={"created_by": created_by},
    )


def trigger_client_updated(
    firm_id: str,
    client_id: str,
    changes: Dict[str, Any],
    updated_by: Optional[str] = None,
) -> None:
    """Trigger webhook when a client is updated."""
    _safe_emit(
        event_type="client.updated",
        firm_id=firm_id,
        data={
            "client_id": client_id,
            "changes": changes,
            "updated_at": datetime.utcnow().isoformat(),
        },
        metadata={"updated_by": updated_by},
    )


def trigger_client_archived(
    firm_id: str,
    client_id: str,
    archived_by: Optional[str] = None,
) -> None:
    """Trigger webhook when a client is archived."""
    _safe_emit(
        event_type="client.archived",
        firm_id=firm_id,
        data={
            "client_id": client_id,
            "archived_at": datetime.utcnow().isoformat(),
        },
        metadata={"archived_by": archived_by},
    )


# =============================================================================
# RETURN EVENTS
# =============================================================================

def trigger_return_created(
    firm_id: str,
    return_id: str,
    client_id: Optional[str],
    tax_year: int,
    filing_status: str,
    status: str = "DRAFT",
    created_by: Optional[str] = None,
) -> None:
    """Trigger webhook when a tax return is created."""
    _safe_emit(
        event_type="return.created",
        firm_id=firm_id,
        data={
            "return_id": return_id,
            "client_id": client_id,
            "tax_year": tax_year,
            "filing_status": filing_status,
            "status": status,
            "created_at": datetime.utcnow().isoformat(),
        },
        metadata={"created_by": created_by},
    )


def trigger_return_status_changed(
    firm_id: str,
    return_id: str,
    previous_status: str,
    new_status: str,
    changed_by: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Trigger webhook when a return status changes."""
    _safe_emit(
        event_type="return.status_changed",
        firm_id=firm_id,
        data={
            "return_id": return_id,
            "previous_status": previous_status,
            "new_status": new_status,
            "changed_at": datetime.utcnow().isoformat(),
            "notes": notes,
        },
        metadata={"changed_by": changed_by},
    )


def trigger_return_submitted(
    firm_id: str,
    return_id: str,
    tax_year: int,
    filing_method: str = "e-file",
    submitted_by: Optional[str] = None,
) -> None:
    """Trigger webhook when a return is submitted for filing."""
    _safe_emit(
        event_type="return.submitted",
        firm_id=firm_id,
        data={
            "return_id": return_id,
            "tax_year": tax_year,
            "filing_method": filing_method,
            "submitted_at": datetime.utcnow().isoformat(),
        },
        metadata={"submitted_by": submitted_by},
    )


def trigger_return_accepted(
    firm_id: str,
    return_id: str,
    confirmation_number: Optional[str] = None,
    accepted_at: Optional[datetime] = None,
) -> None:
    """Trigger webhook when IRS accepts a return."""
    _safe_emit(
        event_type="return.accepted",
        firm_id=firm_id,
        data={
            "return_id": return_id,
            "confirmation_number": confirmation_number,
            "accepted_at": (accepted_at or datetime.utcnow()).isoformat(),
        },
    )


def trigger_return_rejected(
    firm_id: str,
    return_id: str,
    rejection_code: Optional[str] = None,
    rejection_reason: Optional[str] = None,
) -> None:
    """Trigger webhook when IRS rejects a return."""
    _safe_emit(
        event_type="return.rejected",
        firm_id=firm_id,
        data={
            "return_id": return_id,
            "rejection_code": rejection_code,
            "rejection_reason": rejection_reason,
            "rejected_at": datetime.utcnow().isoformat(),
        },
    )


# =============================================================================
# DOCUMENT EVENTS
# =============================================================================

def trigger_document_uploaded(
    firm_id: str,
    document_id: str,
    filename: str,
    file_type: str,
    file_size: int,
    client_id: Optional[str] = None,
    return_id: Optional[str] = None,
    uploaded_by: Optional[str] = None,
) -> None:
    """Trigger webhook when a document is uploaded."""
    _safe_emit(
        event_type="document.uploaded",
        firm_id=firm_id,
        data={
            "document_id": document_id,
            "client_id": client_id,
            "return_id": return_id,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "uploaded_at": datetime.utcnow().isoformat(),
        },
        metadata={"uploaded_by": uploaded_by},
    )


def trigger_document_processed(
    firm_id: str,
    document_id: str,
    processing_result: str,
    extracted_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Trigger webhook when document processing completes."""
    _safe_emit(
        event_type="document.processed",
        firm_id=firm_id,
        data={
            "document_id": document_id,
            "processing_result": processing_result,
            "extracted_fields": list(extracted_data.keys()) if extracted_data else [],
            "processed_at": datetime.utcnow().isoformat(),
        },
    )


# =============================================================================
# ENGAGEMENT EVENTS
# =============================================================================

def trigger_engagement_signed(
    firm_id: str,
    engagement_id: str,
    client_id: str,
    signed_by: str,
    ip_address: Optional[str] = None,
) -> None:
    """Trigger webhook when engagement letter is signed."""
    _safe_emit(
        event_type="engagement.signed",
        firm_id=firm_id,
        data={
            "engagement_id": engagement_id,
            "client_id": client_id,
            "signed_by": signed_by,
            "signed_at": datetime.utcnow().isoformat(),
            "ip_address": ip_address,
        },
    )


# =============================================================================
# SCENARIO EVENTS
# =============================================================================

def trigger_scenario_created(
    firm_id: str,
    scenario_id: str,
    return_id: str,
    scenario_name: str,
    created_by: Optional[str] = None,
) -> None:
    """Trigger webhook when a tax scenario is created."""
    _safe_emit(
        event_type="scenario.created",
        firm_id=firm_id,
        data={
            "scenario_id": scenario_id,
            "return_id": return_id,
            "scenario_name": scenario_name,
            "created_at": datetime.utcnow().isoformat(),
        },
        metadata={"created_by": created_by},
    )


def trigger_scenario_completed(
    firm_id: str,
    scenario_id: str,
    return_id: str,
    estimated_tax: float,
    estimated_refund: Optional[float] = None,
) -> None:
    """Trigger webhook when scenario analysis completes."""
    _safe_emit(
        event_type="scenario.completed",
        firm_id=firm_id,
        data={
            "scenario_id": scenario_id,
            "return_id": return_id,
            "estimated_tax": estimated_tax,
            "estimated_refund": estimated_refund,
            "completed_at": datetime.utcnow().isoformat(),
        },
    )


# =============================================================================
# RECOMMENDATION EVENTS
# =============================================================================

def trigger_recommendation_generated(
    firm_id: str,
    return_id: str,
    recommendation_count: int,
    total_potential_savings: float,
    categories: list,
) -> None:
    """Trigger webhook when advisory recommendations are generated."""
    _safe_emit(
        event_type="recommendation.generated",
        firm_id=firm_id,
        data={
            "return_id": return_id,
            "recommendation_count": recommendation_count,
            "total_potential_savings": total_potential_savings,
            "categories": categories,
            "generated_at": datetime.utcnow().isoformat(),
        },
    )


def trigger_report_generated(
    firm_id: str,
    report_id: str,
    report_type: str,
    return_id: Optional[str] = None,
    client_id: Optional[str] = None,
    format: str = "pdf",
) -> None:
    """Trigger webhook when a report is generated."""
    _safe_emit(
        event_type="report.generated",
        firm_id=firm_id,
        data={
            "report_id": report_id,
            "report_type": report_type,
            "return_id": return_id,
            "client_id": client_id,
            "format": format,
            "generated_at": datetime.utcnow().isoformat(),
        },
    )
