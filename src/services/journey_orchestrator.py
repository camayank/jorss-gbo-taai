"""
Client Journey Orchestrator

Listens for subsystem events via EventBus and advances the client
through their tax journey. Tracks stage, generates next-step CTAs.

Usage:
    from services.journey_orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    stage = orchestrator.get_stage(user_id, tenant_id)
    next_step = orchestrator.get_next_step(user_id, tenant_id)
"""

import logging
import threading
from enum import Enum
from typing import Any, Dict, Optional

from events.event_bus import EventBus
from events.journey_events import (
    AdvisorProfileComplete,
    AdvisorMessageSent,
    DocumentProcessed,
    ReturnDraftSaved,
    ReturnSubmittedForReview,
    ScenarioCreated,
    ReviewCompleted,
    ReportGenerated,
)
from security.tenant_scoped_store import TenantScopedStore

logger = logging.getLogger(__name__)

PROFILE_COMPLETE_THRESHOLD = 0.6


class JourneyStage(str, Enum):
    INTAKE = "intake"
    PROFILING = "profiling"
    DOCUMENTS = "documents"
    RETURN_DRAFT = "return_draft"
    SCENARIOS = "scenarios"
    CPA_REVIEW = "cpa_review"
    REPORT = "report"
    FILED = "filed"


# Next-step templates per stage
_NEXT_STEPS = {
    JourneyStage.INTAKE: {
        "action": "start_advisor",
        "message": "Start by telling us about your tax situation.",
        "cta_label": "Talk to Tax Advisor",
        "cta_url": "/intelligent-advisor",
    },
    JourneyStage.PROFILING: {
        "action": "continue_advisor",
        "message": "Continue your conversation to complete your tax profile.",
        "cta_label": "Continue with Advisor",
        "cta_url": "/intelligent-advisor",
    },
    JourneyStage.DOCUMENTS: {
        "action": "upload_documents",
        "message": "Upload your tax documents to auto-fill your return.",
        "cta_label": "Upload Documents",
        "cta_url": "/documents",
    },
    JourneyStage.RETURN_DRAFT: {
        "action": "review_return",
        "message": "Review your draft tax return and explore scenarios.",
        "cta_label": "Review Return",
        "cta_url": "/app",
    },
    JourneyStage.SCENARIOS: {
        "action": "explore_scenarios",
        "message": "Compare tax strategies to maximize your savings.",
        "cta_label": "View Scenarios",
        "cta_url": "/scenarios",
    },
    JourneyStage.CPA_REVIEW: {
        "action": "await_review",
        "message": "Your return is being reviewed by your CPA.",
        "cta_label": "Check Status",
        "cta_url": "/app",
    },
    JourneyStage.REPORT: {
        "action": "download_report",
        "message": "Your tax report is ready!",
        "cta_label": "View Report",
        "cta_url": "/app",
    },
    JourneyStage.FILED: {
        "action": "view_confirmation",
        "message": "Your return has been filed. Keep your records safe.",
        "cta_label": "View Confirmation",
        "cta_url": "/app",
    },
}


class ClientJourneyOrchestrator:
    """Orchestrates the client tax journey via events."""

    def __init__(self, event_bus: EventBus):
        self._store = TenantScopedStore(name="journey", max_size=50000)
        self._next_step_store = TenantScopedStore(name="journey_next", max_size=50000)
        self._cost_store = TenantScopedStore(name="journey_cost", max_size=50000)
        self._bus = event_bus
        self.MAX_COST_PER_SESSION = 10.0
        self._register_handlers()

    def _register_handlers(self):
        self._bus.on(AdvisorProfileComplete, self._on_profile_complete)
        self._bus.on(DocumentProcessed, self._on_document_processed)
        self._bus.on(ReturnDraftSaved, self._on_return_saved)
        self._bus.on(ReturnSubmittedForReview, self._on_submitted_for_review)
        self._bus.on(ScenarioCreated, self._on_scenario_created)
        self._bus.on(ReviewCompleted, self._on_review_completed)
        self._bus.on(ReportGenerated, self._on_report_generated)

    # --- Stage management ---

    def get_stage(self, user_id: str, tenant_id: str) -> JourneyStage:
        raw = self._store.get(f"stage:{user_id}", tenant_id)
        if raw is None:
            return JourneyStage.INTAKE
        return JourneyStage(raw)

    def _set_stage(self, user_id: str, tenant_id: str, stage: JourneyStage):
        self._store.set(f"stage:{user_id}", stage.value, tenant_id)
        self._next_step_store.set(
            f"next:{user_id}", _NEXT_STEPS.get(stage), tenant_id
        )
        logger.info(f"[Journey] {user_id}@{tenant_id} -> {stage.value}")

    def get_next_step(self, user_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        ns = self._next_step_store.get(f"next:{user_id}", tenant_id)
        if ns is not None:
            return ns
        stage = self.get_stage(user_id, tenant_id)
        return _NEXT_STEPS.get(stage)

    def get_progress(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        current = self.get_stage(user_id, tenant_id)
        stages = list(JourneyStage)
        current_idx = stages.index(current)
        return {
            "current_stage": current.value,
            "stages": [
                {
                    "name": s.value,
                    "label": s.value.replace("_", " ").title(),
                    "status": (
                        "completed" if i < current_idx
                        else "active" if i == current_idx
                        else "pending"
                    ),
                }
                for i, s in enumerate(stages)
            ],
            "completion_pct": round(current_idx / (len(stages) - 1) * 100),
        }

    # --- Cost tracking ---

    def track_cost(self, user_id: str, tenant_id: str, cost: float) -> bool:
        """Track AI cost. Returns False if limit exceeded."""
        current = self._cost_store.get(f"cost:{user_id}", tenant_id) or 0.0
        new_total = current + cost
        self._cost_store.set(f"cost:{user_id}", new_total, tenant_id)
        if new_total > self.MAX_COST_PER_SESSION:
            logger.warning(f"[Journey] Cost limit exceeded for {user_id}@{tenant_id}: ${new_total:.2f}")
            return False
        return True

    def get_session_cost(self, user_id: str, tenant_id: str) -> float:
        return self._cost_store.get(f"cost:{user_id}", tenant_id) or 0.0

    # --- Event handlers ---

    def _on_profile_complete(self, event: AdvisorProfileComplete):
        if event.profile_completeness >= PROFILE_COMPLETE_THRESHOLD:
            self._set_stage(event.user_id, event.tenant_id, JourneyStage.DOCUMENTS)
            if event.extracted_forms:
                first_form = event.extracted_forms[0]
                self._next_step_store.set(
                    f"next:{event.user_id}",
                    {
                        "action": "upload_documents",
                        "message": f"Profile complete! Upload your {first_form} to auto-fill your return.",
                        "cta_label": f"Upload {first_form}",
                        "cta_url": "/documents",
                    },
                    event.tenant_id,
                )
        else:
            self._set_stage(event.user_id, event.tenant_id, JourneyStage.PROFILING)

    def _on_document_processed(self, event: DocumentProcessed):
        self._next_step_store.set(
            f"next:{event.user_id}",
            {
                "action": "upload_documents",
                "message": f"{event.document_type} processed — {event.fields_extracted} fields extracted. Upload more or review your return.",
                "cta_label": "Review Return",
                "cta_url": "/app",
            },
            event.tenant_id,
        )

    def _on_return_saved(self, event: ReturnDraftSaved):
        current = self.get_stage(event.user_id, event.tenant_id)
        if current in (JourneyStage.DOCUMENTS, JourneyStage.INTAKE, JourneyStage.PROFILING):
            self._set_stage(event.user_id, event.tenant_id, JourneyStage.RETURN_DRAFT)

    def _on_submitted_for_review(self, event: ReturnSubmittedForReview):
        self._set_stage(event.user_id, event.tenant_id, JourneyStage.CPA_REVIEW)

    def _on_scenario_created(self, event: ScenarioCreated):
        current = self.get_stage(event.user_id, event.tenant_id)
        if current == JourneyStage.RETURN_DRAFT:
            self._set_stage(event.user_id, event.tenant_id, JourneyStage.SCENARIOS)

    def _on_review_completed(self, event: ReviewCompleted):
        if event.status == "CPA_APPROVED":
            self._set_stage(event.user_id, event.tenant_id, JourneyStage.REPORT)

    def _on_report_generated(self, event: ReportGenerated):
        self._set_stage(event.user_id, event.tenant_id, JourneyStage.REPORT)
        self._next_step_store.set(
            f"next:{event.user_id}",
            {
                "action": "download_report",
                "message": "Your tax report is ready!",
                "cta_label": "Download Report",
                "cta_url": event.download_url or f"/api/advisory/reports/{event.report_id}/download",
            },
            event.tenant_id,
        )


# Singleton
_orchestrator = None  # type: Optional[ClientJourneyOrchestrator]
_orch_lock = threading.Lock()


def get_orchestrator(event_bus: Optional[EventBus] = None) -> ClientJourneyOrchestrator:
    """Get or create the global orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        with _orch_lock:
            if _orchestrator is None:
                if event_bus is None:
                    from events.event_bus import get_event_bus
                    event_bus = get_event_bus()
                _orchestrator = ClientJourneyOrchestrator(event_bus)
    return _orchestrator
