"""Tests for journey event dataclasses."""

import pytest
from dataclasses import asdict
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


class TestJourneyEvents:
    """All journey events are valid dataclasses with required fields."""

    def test_advisor_profile_complete(self):
        event = AdvisorProfileComplete(
            session_id="s1", tenant_id="t1", user_id="u1",
            profile_completeness=0.85, extracted_forms=["W-2", "1099-NEC"],
        )
        d = asdict(event)
        assert d["profile_completeness"] == 0.85
        assert "W-2" in d["extracted_forms"]

    def test_document_processed(self):
        event = DocumentProcessed(
            document_id="d1", tenant_id="t1", user_id="u1",
            document_type="W-2", fields_extracted=12,
        )
        assert event.fields_extracted == 12

    def test_return_draft_saved(self):
        event = ReturnDraftSaved(
            return_id="r1", tenant_id="t1", user_id="u1",
            session_id="s1", completeness=0.6,
        )
        assert event.completeness == 0.6

    def test_return_submitted_for_review(self):
        event = ReturnSubmittedForReview(
            session_id="s1", tenant_id="t1", user_id="u1",
        )
        assert event.session_id == "s1"

    def test_scenario_created(self):
        event = ScenarioCreated(
            scenario_id="sc1", tenant_id="t1", user_id="u1",
            return_id="r1", name="Standard vs Itemized",
        )
        assert event.name == "Standard vs Itemized"

    def test_review_completed(self):
        event = ReviewCompleted(
            session_id="s1", tenant_id="t1", user_id="u1",
            cpa_id="cpa1", status="CPA_APPROVED",
        )
        assert event.status == "CPA_APPROVED"

    def test_report_generated(self):
        event = ReportGenerated(
            report_id="rp1", tenant_id="t1", user_id="u1",
            session_id="s1",
        )
        assert event.report_id == "rp1"

    def test_advisor_message_sent(self):
        event = AdvisorMessageSent(
            session_id="s1", tenant_id="t1", user_id="u1",
            message_text="my SSN is 123-45-6789",
        )
        assert event.message_text == "my SSN is 123-45-6789"
