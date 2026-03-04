"""Tests for client journey orchestrator."""

import pytest
from events.event_bus import EventBus
from events.journey_events import (
    AdvisorProfileComplete,
    DocumentProcessed,
    ReturnDraftSaved,
    ReturnSubmittedForReview,
    ScenarioCreated,
    ReviewCompleted,
    ReportGenerated,
)
from services.journey_orchestrator import (
    ClientJourneyOrchestrator,
    JourneyStage,
)


class TestJourneyStageProgression:

    def setup_method(self):
        self.bus = EventBus()
        self.orchestrator = ClientJourneyOrchestrator(self.bus)

    def test_initial_stage_is_intake(self):
        stage = self.orchestrator.get_stage("u1", "t1")
        assert stage == JourneyStage.INTAKE

    def test_profile_complete_advances_to_documents(self):
        self.bus.emit(AdvisorProfileComplete(
            session_id="s1", tenant_id="t1", user_id="u1",
            profile_completeness=0.85, extracted_forms=["W-2"],
        ))
        assert self.orchestrator.get_stage("u1", "t1") == JourneyStage.DOCUMENTS

    def test_low_completeness_stays_profiling(self):
        self.bus.emit(AdvisorProfileComplete(
            session_id="s1", tenant_id="t1", user_id="u1",
            profile_completeness=0.3, extracted_forms=[],
        ))
        assert self.orchestrator.get_stage("u1", "t1") == JourneyStage.PROFILING

    def test_document_processed_stays_documents(self):
        self.orchestrator._set_stage("u1", "t1", JourneyStage.DOCUMENTS)
        self.bus.emit(DocumentProcessed(
            document_id="d1", tenant_id="t1", user_id="u1",
            document_type="W-2", fields_extracted=12,
        ))
        assert self.orchestrator.get_stage("u1", "t1") == JourneyStage.DOCUMENTS

    def test_return_saved_advances_to_return_draft(self):
        self.orchestrator._set_stage("u1", "t1", JourneyStage.DOCUMENTS)
        self.bus.emit(ReturnDraftSaved(
            return_id="r1", tenant_id="t1", user_id="u1",
            session_id="s1", completeness=0.7,
        ))
        assert self.orchestrator.get_stage("u1", "t1") == JourneyStage.RETURN_DRAFT

    def test_submit_for_review_advances_to_cpa_review(self):
        self.orchestrator._set_stage("u1", "t1", JourneyStage.RETURN_DRAFT)
        self.bus.emit(ReturnSubmittedForReview(
            session_id="s1", tenant_id="t1", user_id="u1",
        ))
        assert self.orchestrator.get_stage("u1", "t1") == JourneyStage.CPA_REVIEW

    def test_review_completed_advances_to_report(self):
        self.orchestrator._set_stage("u1", "t1", JourneyStage.CPA_REVIEW)
        self.bus.emit(ReviewCompleted(
            session_id="s1", tenant_id="t1", user_id="u1",
            cpa_id="cpa1", status="CPA_APPROVED",
        ))
        assert self.orchestrator.get_stage("u1", "t1") == JourneyStage.REPORT


class TestJourneyNextStep:

    def setup_method(self):
        self.bus = EventBus()
        self.orchestrator = ClientJourneyOrchestrator(self.bus)

    def test_next_step_after_profile_complete(self):
        self.bus.emit(AdvisorProfileComplete(
            session_id="s1", tenant_id="t1", user_id="u1",
            profile_completeness=0.85, extracted_forms=["W-2"],
        ))
        ns = self.orchestrator.get_next_step("u1", "t1")
        assert ns is not None
        assert ns["action"] == "upload_documents"
        assert "cta_url" in ns

    def test_next_step_for_intake_is_start_advisor(self):
        ns = self.orchestrator.get_next_step("u1", "t1")
        assert ns["action"] == "start_advisor"


class TestJourneyTenantIsolation:

    def setup_method(self):
        self.bus = EventBus()
        self.orchestrator = ClientJourneyOrchestrator(self.bus)

    def test_different_tenants_independent(self):
        self.bus.emit(AdvisorProfileComplete(
            session_id="s1", tenant_id="t1", user_id="u1",
            profile_completeness=0.85, extracted_forms=[],
        ))
        assert self.orchestrator.get_stage("u1", "t1") == JourneyStage.DOCUMENTS
        assert self.orchestrator.get_stage("u1", "t2") == JourneyStage.INTAKE


class TestJourneyCostTracking:

    def setup_method(self):
        self.bus = EventBus()
        self.orchestrator = ClientJourneyOrchestrator(self.bus)

    def test_tracks_cumulative_cost(self):
        self.orchestrator.track_cost("u1", "t1", 0.15)
        self.orchestrator.track_cost("u1", "t1", 0.10)
        assert self.orchestrator.get_session_cost("u1", "t1") == pytest.approx(0.25)

    def test_returns_false_when_limit_exceeded(self):
        result = self.orchestrator.track_cost("u1", "t1", 11.0)
        assert result is False

    def test_different_users_independent(self):
        self.orchestrator.track_cost("u1", "t1", 5.0)
        self.orchestrator.track_cost("u2", "t1", 1.0)
        assert self.orchestrator.get_session_cost("u1", "t1") == 5.0
        assert self.orchestrator.get_session_cost("u2", "t1") == 1.0


class TestJourneyProgress:

    def setup_method(self):
        self.bus = EventBus()
        self.orchestrator = ClientJourneyOrchestrator(self.bus)

    def test_progress_shows_all_stages(self):
        progress = self.orchestrator.get_progress("u1", "t1")
        assert progress["current_stage"] == "intake"
        assert len(progress["stages"]) == 8
        assert progress["completion_pct"] == 0

    def test_progress_after_advancement(self):
        self.orchestrator._set_stage("u1", "t1", JourneyStage.RETURN_DRAFT)
        progress = self.orchestrator.get_progress("u1", "t1")
        assert progress["current_stage"] == "return_draft"
        assert progress["completion_pct"] > 0
        completed = [s for s in progress["stages"] if s["status"] == "completed"]
        assert len(completed) == 3  # intake, profiling, documents
