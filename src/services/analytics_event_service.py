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

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional, Dict
from decimal import Decimal
from uuid import uuid4
from queue import Queue

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
    """Service for persisting journey events to analytics_events table.

    Uses a queue-based approach to persist events asynchronously without blocking
    the event emitter. A background thread manages the async database operations.
    """

    def __init__(self, session_factory: async_sessionmaker):
        """Initialize with database session factory."""
        self.session_factory = session_factory
        self.event_bus = get_event_bus()
        self._event_queue: Queue[Dict[str, Any]] = Queue()
        self._background_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

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

        # Start background worker thread
        self._start_worker()
        logger.info("[AnalyticsEventService] Event handlers registered and worker started")

    def _start_worker(self) -> None:
        """Start the background worker thread for async persistence."""
        if self._background_thread is None:
            self._background_thread = threading.Thread(
                target=self._worker_loop, daemon=True, name="AnalyticsEventWorker"
            )
            self._background_thread.start()

    def _worker_loop(self) -> None:
        """Background thread main loop - processes events from queue."""
        try:
            asyncio.run(self._async_worker())
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Worker loop error: {e}", exc_info=True)

    async def _async_worker(self) -> None:
        """Async worker that processes queued events."""
        while not self._shutdown_event.is_set():
            try:
                # Non-blocking check for queued events
                try:
                    fields = self._event_queue.get(timeout=1.0)
                except:
                    # Queue timeout - check shutdown and continue
                    continue

                # Persist the event
                await self._persist_event(**fields)
            except Exception as e:
                logger.error(f"[AnalyticsEventService] Worker error: {e}", exc_info=True)

    async def _persist_event(self, **fields) -> Optional[AnalyticsEventRecord]:
        """Persist an event record to the database.

        Args:
            **fields: Field values for AnalyticsEventRecord

        Returns:
            Created AnalyticsEventRecord or None if error
        """
        try:
            async with self.session_factory() as session:
                record = AnalyticsEventRecord(**fields)
                session.add(record)
                await session.commit()
                return record

        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to persist event: {e}")
            return None

    def _handle_advisor_profile_complete(self, event: AdvisorProfileComplete) -> None:
        """Queue AdvisorProfileComplete event for persistence."""
        try:
            self._event_queue.put({
                "event_id": uuid4(),
                "received_at": datetime.now(timezone.utc),
                "event_type": "AdvisorProfileComplete",
                "tenant_id": event.tenant_id,
                "user_id": event.user_id,
                "session_id": event.session_id,
                "profile_completeness": Decimal(str(event.profile_completeness)),
                "extracted_forms": ",".join(event.extracted_forms) if event.extracted_forms else None,
                "data_json": {
                    "session_id": event.session_id,
                    "profile_completeness": event.profile_completeness,
                    "extracted_forms": event.extracted_forms
                },
            })
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to queue event: {e}")

    def _handle_advisor_message_sent(self, event: AdvisorMessageSent) -> None:
        """Queue AdvisorMessageSent event for persistence."""
        try:
            self._event_queue.put({
                "event_id": uuid4(),
                "received_at": datetime.now(timezone.utc),
                "event_type": "AdvisorMessageSent",
                "tenant_id": event.tenant_id,
                "user_id": event.user_id,
                "session_id": event.session_id,
                "message_text": event.message_text[:1000] if event.message_text else None,
                "data_json": {
                    "session_id": event.session_id,
                    "message_length": len(event.message_text) if event.message_text else 0
                },
            })
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to queue event: {e}")

    def _handle_document_processed(self, event: DocumentProcessed) -> None:
        """Queue DocumentProcessed event for persistence."""
        try:
            self._event_queue.put({
                "event_id": uuid4(),
                "received_at": datetime.now(timezone.utc),
                "event_type": "DocumentProcessed",
                "tenant_id": event.tenant_id,
                "user_id": event.user_id,
                "document_id": event.document_id,
                "document_type": event.document_type,
                "fields_extracted": event.fields_extracted,
                "data_json": {
                    "document_id": event.document_id,
                    "document_type": event.document_type,
                    "fields_extracted": event.fields_extracted
                },
            })
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to queue event: {e}")

    def _handle_return_draft_saved(self, event: ReturnDraftSaved) -> None:
        """Queue ReturnDraftSaved event for persistence."""
        try:
            self._event_queue.put({
                "event_id": uuid4(),
                "received_at": datetime.now(timezone.utc),
                "event_type": "ReturnDraftSaved",
                "tenant_id": event.tenant_id,
                "user_id": event.user_id,
                "session_id": event.session_id,
                "return_id": event.return_id,
                "return_completeness": Decimal(str(event.completeness)),
                "data_json": {
                    "return_id": event.return_id,
                    "completeness": event.completeness
                },
            })
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to queue event: {e}")

    def _handle_return_submitted(self, event: ReturnSubmittedForReview) -> None:
        """Queue ReturnSubmittedForReview event for persistence."""
        try:
            self._event_queue.put({
                "event_id": uuid4(),
                "received_at": datetime.now(timezone.utc),
                "event_type": "ReturnSubmittedForReview",
                "tenant_id": event.tenant_id,
                "user_id": event.user_id,
                "session_id": event.session_id,
                "data_json": {"session_id": event.session_id},
            })
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to queue event: {e}")

    def _handle_scenario_created(self, event: ScenarioCreated) -> None:
        """Queue ScenarioCreated event for persistence."""
        try:
            self._event_queue.put({
                "event_id": uuid4(),
                "received_at": datetime.now(timezone.utc),
                "event_type": "ScenarioCreated",
                "tenant_id": event.tenant_id,
                "user_id": event.user_id,
                "return_id": event.return_id,
                "scenario_id": event.scenario_id,
                "scenario_name": event.name,
                "scenario_savings": Decimal(str(event.savings_amount)) if event.savings_amount else None,
                "data_json": {
                    "scenario_id": event.scenario_id,
                    "name": event.name,
                    "savings_amount": event.savings_amount
                },
            })
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to queue event: {e}")

    def _handle_review_completed(self, event: ReviewCompleted) -> None:
        """Queue ReviewCompleted event for persistence."""
        try:
            self._event_queue.put({
                "event_id": uuid4(),
                "received_at": datetime.now(timezone.utc),
                "event_type": "ReviewCompleted",
                "tenant_id": event.tenant_id,
                "user_id": event.user_id,
                "session_id": event.session_id,
                "cpa_id": event.cpa_id,
                "review_status": event.status,
                "review_notes": event.notes[:1000] if event.notes else None,
                "data_json": {
                    "session_id": event.session_id,
                    "cpa_id": event.cpa_id,
                    "status": event.status,
                    "notes": event.notes
                },
            })
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to queue event: {e}")

    def _handle_report_generated(self, event: ReportGenerated) -> None:
        """Queue ReportGenerated event for persistence."""
        try:
            self._event_queue.put({
                "event_id": uuid4(),
                "received_at": datetime.now(timezone.utc),
                "event_type": "ReportGenerated",
                "tenant_id": event.tenant_id,
                "user_id": event.user_id,
                "session_id": event.session_id,
                "report_id": event.report_id,
                "download_url": event.download_url,
                "data_json": {
                    "report_id": event.report_id,
                    "download_url": event.download_url
                },
            })
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to queue event: {e}")

    def _handle_lead_state_changed(self, event: LeadStateChanged) -> None:
        """Queue LeadStateChanged event for persistence."""
        try:
            self._event_queue.put({
                "event_id": uuid4(),
                "received_at": datetime.now(timezone.utc),
                "event_type": "LeadStateChanged",
                "tenant_id": event.tenant_id,
                "user_id": event.user_id,
                "lead_id": event.lead_id,
                "lead_from_state": event.from_state,
                "lead_to_state": event.to_state,
                "lead_trigger": event.trigger,
                "data_json": {
                    "lead_id": event.lead_id,
                    "from_state": event.from_state,
                    "to_state": event.to_state,
                    "trigger": event.trigger
                },
            })
        except Exception as e:
            logger.error(f"[AnalyticsEventService] Failed to queue event: {e}")
