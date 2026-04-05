"""
Analytics Event Service - Persist journey events to analytics_events table.

Subscribes to journey events from the event bus and persists them to the database
for analytics, dashboards, and future data warehouse export.

Usage:
    from services.analytics_event_service import AnalyticsEventService
    from database.async_engine import get_async_session_factory

    session_factory = get_async_session_factory()
    analytics_svc = AnalyticsEventService(session_factory)
    analytics_svc.register_handlers()  # Call at app startup
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database.models import AnalyticsEventRecord
from src.events.event_bus import get_event_bus
from src.events.journey_events import (
    AdvisorProfileComplete,
    AdvisorMessageSent,
    DocumentProcessed,
    ReturnDraftSaved,
    ReturnSubmittedForReview,
    ScenarioCreated,
    ReviewCompleted,
    ReportGenerated,
    LeadStateChanged,
)

logger = logging.getLogger(__name__)


class AnalyticsEventService:
    """Service for persisting journey events to analytics_events table."""

    def __init__(self, session_factory: async_sessionmaker):
        """Initialize with database session factory."""
        self.session_factory = session_factory
        self.event_bus = get_event_bus()

    def register_handlers(self) -> None:
        """Register event bus handlers for all journey events.

        Call this at application startup to connect event bus to database persistence.
        """
        self.event_bus.on(AdvisorProfileComplete, self._handle_advisor_profile_complete)
        self.event_bus.on(AdvisorMessageSent, self._handle_advisor_message_sent)
        self.event_bus.on(DocumentProcessed, self._handle_document_processed)
        self.event_bus.on(ReturnDraftSaved, self._handle_return_draft_saved)
        self.event_bus.on(ReturnSubmittedForReview, self._handle_return_submitted)
        self.event_bus.on(ScenarioCreated, self._handle_scenario_created)
        self.event_bus.on(ReviewCompleted, self._handle_review_completed)
        self.event_bus.on(ReportGenerated, self._handle_report_generated)
        self.event_bus.on(LeadStateChanged, self._handle_lead_state_changed)

        logger.info("[AnalyticsEventService] Event handlers registered")

    async def _persist_event(self, **fields) -> Optional[AnalyticsEventRecord]:
        """Persist an event record to the database.

        Args:
            **fields: Field values for AnalyticsEventRecord

        Returns:
            Created AnalyticsEventRecord or None if error
        """
        try:
            async with self.session_factory() as session:
                record = AnalyticsEventRecord(
                    event_id=uuid4(),
                    received_at=datetime.now(timezone.utc),
                    **fields
                )
                session.add(record)
                await session.commit()
                return record

        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to persist event: {e}")
            return None

    def _handle_advisor_profile_complete(self, event: AdvisorProfileComplete) -> None:
        """Handle AdvisorProfileComplete event."""
        import asyncio
        try:
            asyncio.run(self._persist_event(
                event_type="AdvisorProfileComplete",
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                session_id=event.session_id,
                profile_completeness=Decimal(str(event.profile_completeness)),
                extracted_forms=",".join(event.extracted_forms) if event.extracted_forms else None,
                event_payload=json.dumps({
                    "session_id": event.session_id,
                    "profile_completeness": event.profile_completeness,
                    "extracted_forms": event.extracted_forms
                }),
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Handler error: {e}")

    def _handle_advisor_message_sent(self, event: AdvisorMessageSent) -> None:
        """Handle AdvisorMessageSent event."""
        import asyncio
        try:
            asyncio.run(self._persist_event(
                event_type="AdvisorMessageSent",
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                session_id=event.session_id,
                message_text=event.message_text[:1000] if event.message_text else None,
                event_payload=json.dumps({
                    "session_id": event.session_id,
                    "message_length": len(event.message_text) if event.message_text else 0
                }),
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Handler error: {e}")

    def _handle_document_processed(self, event: DocumentProcessed) -> None:
        """Handle DocumentProcessed event."""
        import asyncio
        try:
            asyncio.run(self._persist_event(
                event_type="DocumentProcessed",
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                document_id=event.document_id,
                document_type=event.document_type,
                fields_extracted=event.fields_extracted,
                event_payload=json.dumps({
                    "document_id": event.document_id,
                    "document_type": event.document_type,
                    "fields_extracted": event.fields_extracted
                }),
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Handler error: {e}")

    def _handle_return_draft_saved(self, event: ReturnDraftSaved) -> None:
        """Handle ReturnDraftSaved event."""
        import asyncio
        try:
            asyncio.run(self._persist_event(
                event_type="ReturnDraftSaved",
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                session_id=event.session_id,
                return_id=event.return_id,
                return_completeness=Decimal(str(event.completeness)),
                event_payload=json.dumps({
                    "return_id": event.return_id,
                    "completeness": event.completeness
                }),
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Handler error: {e}")

    def _handle_return_submitted(self, event: ReturnSubmittedForReview) -> None:
        """Handle ReturnSubmittedForReview event."""
        import asyncio
        try:
            asyncio.run(self._persist_event(
                event_type="ReturnSubmittedForReview",
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                session_id=event.session_id,
                event_payload=json.dumps({"session_id": event.session_id}),
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Handler error: {e}")

    def _handle_scenario_created(self, event: ScenarioCreated) -> None:
        """Handle ScenarioCreated event."""
        import asyncio
        try:
            asyncio.run(self._persist_event(
                event_type="ScenarioCreated",
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                return_id=event.return_id,
                scenario_id=event.scenario_id,
                scenario_name=event.name,
                scenario_savings=Decimal(str(event.savings_amount)) if event.savings_amount else None,
                event_payload=json.dumps({
                    "scenario_id": event.scenario_id,
                    "name": event.name,
                    "savings_amount": event.savings_amount
                }),
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Handler error: {e}")

    def _handle_review_completed(self, event: ReviewCompleted) -> None:
        """Handle ReviewCompleted event."""
        import asyncio
        try:
            asyncio.run(self._persist_event(
                event_type="ReviewCompleted",
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                session_id=event.session_id,
                cpa_id=event.cpa_id,
                review_status=event.status,
                review_notes=event.notes[:1000] if event.notes else None,
                event_payload=json.dumps({
                    "session_id": event.session_id,
                    "cpa_id": event.cpa_id,
                    "status": event.status,
                    "notes": event.notes
                }),
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Handler error: {e}")

    def _handle_report_generated(self, event: ReportGenerated) -> None:
        """Handle ReportGenerated event."""
        import asyncio
        try:
            asyncio.run(self._persist_event(
                event_type="ReportGenerated",
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                session_id=event.session_id,
                report_id=event.report_id,
                download_url=event.download_url,
                event_payload=json.dumps({
                    "report_id": event.report_id,
                    "download_url": event.download_url
                }),
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Handler error: {e}")

    def _handle_lead_state_changed(self, event: LeadStateChanged) -> None:
        """Handle LeadStateChanged event."""
        import asyncio
        try:
            asyncio.run(self._persist_event(
                event_type="LeadStateChanged",
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                lead_id=event.lead_id,
                lead_previous_state=event.from_state,
                lead_new_state=event.to_state,
                lead_trigger=event.trigger,
                event_payload=json.dumps({
                    "lead_id": event.lead_id,
                    "from_state": event.from_state,
                    "to_state": event.to_state,
                    "trigger": event.trigger
                }),
                occurred_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Handler error: {e}")
