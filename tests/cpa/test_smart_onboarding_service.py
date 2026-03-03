"""
Tests for SmartOnboardingService.

Covers session lifecycle, document processing, question submission,
instant analysis, client creation, progress tracking, and edge cases.
"""
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cpa_panel.services.smart_onboarding_service import (
    SmartOnboardingService,
    OnboardingSession,
    OnboardingStatus,
    OptimizationOpportunity,
    InstantAnalysis,
    get_smart_onboarding_service,
)
from cpa_panel.services.form_1040_parser import FilingStatus, Parsed1040Data


# =========================================================================
# ENUM TESTS
# =========================================================================

class TestOnboardingStatusEnum:
    """Verify OnboardingStatus members."""

    @pytest.mark.parametrize("member,value", [
        (OnboardingStatus.INITIATED, "initiated"),
        (OnboardingStatus.DOCUMENT_UPLOADED, "document_uploaded"),
        (OnboardingStatus.OCR_PROCESSING, "ocr_processing"),
        (OnboardingStatus.OCR_COMPLETE, "ocr_complete"),
        (OnboardingStatus.QUESTIONS_GENERATED, "questions_generated"),
        (OnboardingStatus.QUESTIONS_ANSWERED, "questions_answered"),
        (OnboardingStatus.ANALYSIS_COMPLETE, "analysis_complete"),
        (OnboardingStatus.CLIENT_CREATED, "client_created"),
        (OnboardingStatus.FAILED, "failed"),
    ])
    def test_status_values(self, member, value):
        assert member.value == value

    def test_status_count(self):
        assert len(OnboardingStatus) == 9


# =========================================================================
# DATACLASS TESTS
# =========================================================================

class TestOptimizationOpportunity:
    """Tests for OptimizationOpportunity dataclass."""

    def test_creation(self, sample_opportunity):
        assert sample_opportunity.id == "opp_401k"
        assert sample_opportunity.category == "retirement"
        assert sample_opportunity.potential_savings == Decimal("3500")

    def test_to_dict(self, sample_opportunity):
        d = sample_opportunity.to_dict()
        assert d["id"] == "opp_401k"
        assert d["potential_savings"] == 3500.0
        assert d["confidence"] == "high"
        assert d["priority"] == 1

    @pytest.mark.parametrize("confidence", ["high", "medium", "low"])
    def test_various_confidence_levels(self, confidence):
        opp = OptimizationOpportunity(
            id="test", title="Test", category="test",
            potential_savings=Decimal("100"), confidence=confidence,
            description="desc", action_required="action", priority=1,
        )
        assert opp.confidence == confidence

    @pytest.mark.parametrize("priority", range(1, 9))
    def test_priority_levels(self, priority):
        opp = OptimizationOpportunity(
            id="test", title="Test", category="test",
            potential_savings=Decimal("100"), confidence="high",
            description="desc", action_required="action", priority=priority,
        )
        assert opp.priority == priority


class TestInstantAnalysis:
    """Tests for InstantAnalysis dataclass."""

    def test_creation(self, sample_analysis):
        assert sample_analysis.total_potential_savings == Decimal("3500")
        assert sample_analysis.recommendations_count == 1

    def test_to_dict(self, sample_analysis):
        d = sample_analysis.to_dict()
        assert d["total_potential_savings"] == 3500.0
        assert len(d["opportunities"]) == 1
        assert d["analysis_confidence"] == "high"

    def test_empty_analysis(self):
        analysis = InstantAnalysis(
            total_potential_savings=Decimal("0"),
            opportunities=[],
            tax_summary={},
            recommendations_count=0,
            analysis_confidence="low",
        )
        d = analysis.to_dict()
        assert d["total_potential_savings"] == 0.0
        assert d["opportunities"] == []


class TestOnboardingSession:
    """Tests for OnboardingSession dataclass."""

    def test_creation(self):
        session = OnboardingSession(
            session_id="s1",
            cpa_id="cpa1",
            status=OnboardingStatus.INITIATED,
            created_at=datetime(2025, 3, 1),
        )
        assert session.session_id == "s1"
        assert session.parsed_1040 is None
        assert session.answers == {}
        assert session.error_message is None

    def test_to_dict_keys(self):
        session = OnboardingSession(
            session_id="s1",
            cpa_id="cpa1",
            status=OnboardingStatus.INITIATED,
            created_at=datetime(2025, 3, 1),
        )
        d = session.to_dict()
        expected_keys = {
            "session_id", "cpa_id", "status", "created_at",
            "document", "extraction", "questions", "answers",
            "analysis", "client", "error",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_status_is_string(self):
        session = OnboardingSession(
            session_id="s1", cpa_id="cpa1",
            status=OnboardingStatus.INITIATED,
            created_at=datetime(2025, 3, 1),
        )
        d = session.to_dict()
        assert d["status"] == "initiated"


# =========================================================================
# SESSION LIFECYCLE
# =========================================================================

class TestStartOnboarding:
    """Tests for start_onboarding."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch("cpa_panel.services.smart_onboarding_service.Form1040Parser"), \
             patch("cpa_panel.services.smart_onboarding_service.AIQuestionGenerator"):
            self.service = SmartOnboardingService()

    def test_start_returns_session(self):
        session = self.service.start_onboarding("cpa-001")
        assert isinstance(session, OnboardingSession)

    def test_start_sets_initiated_status(self):
        session = self.service.start_onboarding("cpa-001")
        assert session.status == OnboardingStatus.INITIATED

    def test_start_sets_cpa_id(self):
        session = self.service.start_onboarding("cpa-001")
        assert session.cpa_id == "cpa-001"

    def test_start_generates_uuid(self):
        session = self.service.start_onboarding("cpa-001")
        uuid.UUID(session.session_id)

    def test_start_stores_session(self):
        session = self.service.start_onboarding("cpa-001")
        assert self.service.get_session(session.session_id) is session

    def test_start_sets_created_at(self):
        session = self.service.start_onboarding("cpa-001")
        assert isinstance(session.created_at, datetime)

    def test_multiple_sessions_unique(self):
        s1 = self.service.start_onboarding("cpa-001")
        s2 = self.service.start_onboarding("cpa-001")
        assert s1.session_id != s2.session_id

    @pytest.mark.parametrize("cpa_id", [
        "cpa-001", "cpa-abc", "prospect", "", "cpa-with-long-id-12345678",
    ])
    def test_various_cpa_ids(self, cpa_id):
        session = self.service.start_onboarding(cpa_id)
        assert session.cpa_id == cpa_id


# =========================================================================
# SUBMIT ANSWERS
# =========================================================================

class TestSubmitAnswers:
    """Tests for submit_answers."""

    @pytest.fixture(autouse=True)
    def setup_service(self, parsed_1040_single):
        with patch("cpa_panel.services.smart_onboarding_service.Form1040Parser"), \
             patch("cpa_panel.services.smart_onboarding_service.AIQuestionGenerator"):
            self.service = SmartOnboardingService()
            session = self.service.start_onboarding("cpa-001")
            session.parsed_1040 = parsed_1040_single
            session.status = OnboardingStatus.QUESTIONS_GENERATED
            self.session_id = session.session_id

    def test_submit_sets_answers(self):
        answers = {"retirement_401k_available": "yes_with_match"}
        session = self.service.submit_answers(self.session_id, answers)
        assert session.answers == answers

    def test_submit_runs_analysis(self):
        answers = {"retirement_401k_available": "yes_with_match", "retirement_401k_contribution": "6-10"}
        session = self.service.submit_answers(self.session_id, answers)
        assert session.analysis is not None
        assert isinstance(session.analysis, InstantAnalysis)

    def test_submit_updates_status(self):
        session = self.service.submit_answers(self.session_id, {})
        assert session.status == OnboardingStatus.ANALYSIS_COMPLETE

    def test_submit_nonexistent_session_raises(self):
        with pytest.raises(ValueError, match="not found"):
            self.service.submit_answers("nonexistent", {})

    def test_submit_empty_answers(self):
        session = self.service.submit_answers(self.session_id, {})
        assert session.analysis is not None

    @pytest.mark.parametrize("answer_key,answer_val", [
        ("retirement_401k_available", "yes_with_match"),
        ("retirement_401k_available", "yes_no_match"),
        ("healthcare_hdhp", "yes"),
        ("retirement_ira", "no"),
        ("credits_energy", "ev"),
        ("credits_energy", "solar"),
        ("deductions_charity", "high"),
    ])
    def test_various_answer_combinations(self, answer_key, answer_val):
        session = self.service.submit_answers(self.session_id, {answer_key: answer_val})
        assert session.status == OnboardingStatus.ANALYSIS_COMPLETE


# =========================================================================
# INSTANT ANALYSIS
# =========================================================================

class TestInstantAnalysisGeneration:
    """Tests for _run_instant_analysis."""

    @pytest.fixture(autouse=True)
    def setup_service(self, parsed_1040_single):
        with patch("cpa_panel.services.smart_onboarding_service.Form1040Parser"), \
             patch("cpa_panel.services.smart_onboarding_service.AIQuestionGenerator"):
            self.service = SmartOnboardingService()
            self.parsed = parsed_1040_single

    def _make_session(self, answers=None, parsed=None):
        session = OnboardingSession(
            session_id="test", cpa_id="cpa",
            status=OnboardingStatus.QUESTIONS_ANSWERED,
            created_at=datetime.utcnow(),
            parsed_1040=parsed or self.parsed,
            answers=answers or {},
        )
        return session

    def test_no_parsed_data_returns_empty(self):
        session = self._make_session(parsed=None)
        session.parsed_1040 = None
        analysis = self.service._run_instant_analysis(session)
        assert analysis.total_potential_savings == Decimal("0")
        assert analysis.opportunities == []
        assert analysis.analysis_confidence == "low"

    def test_401k_opportunity_detected(self):
        session = self._make_session(answers={
            "retirement_401k_available": "yes_with_match",
            "retirement_401k_contribution": "6-10",
        })
        analysis = self.service._run_instant_analysis(session)
        opp_ids = [o.id for o in analysis.opportunities]
        assert "opp_401k" in opp_ids

    def test_hsa_opportunity_detected(self):
        session = self._make_session(answers={
            "healthcare_hdhp": "yes",
            "healthcare_hsa": "partial",
        })
        analysis = self.service._run_instant_analysis(session)
        opp_ids = [o.id for o in analysis.opportunities]
        assert "opp_hsa" in opp_ids

    def test_dcfsa_opportunity_detected(self):
        session = self._make_session(answers={
            "dependents_childcare": "yes_high",
        })
        analysis = self.service._run_instant_analysis(session)
        opp_ids = [o.id for o in analysis.opportunities]
        assert "opp_dcfsa" in opp_ids

    def test_ira_opportunity_detected(self):
        session = self._make_session(answers={
            "retirement_ira": "no",
        })
        analysis = self.service._run_instant_analysis(session)
        opp_ids = [o.id for o in analysis.opportunities]
        assert "opp_ira" in opp_ids

    def test_ev_credit_detected(self):
        session = self._make_session(answers={
            "credits_energy": "ev",
        })
        analysis = self.service._run_instant_analysis(session)
        opp_ids = [o.id for o in analysis.opportunities]
        assert "opp_ev" in opp_ids

    def test_solar_credit_detected(self):
        session = self._make_session(answers={
            "credits_energy": "solar",
        })
        analysis = self.service._run_instant_analysis(session)
        opp_ids = [o.id for o in analysis.opportunities]
        assert "opp_solar" in opp_ids

    def test_charitable_bunching_detected(self):
        parsed = Parsed1040Data(
            filing_status=FilingStatus.SINGLE,
            adjusted_gross_income=Decimal("85000"),
            wages_salaries_tips=Decimal("85000"),
            standard_deduction=Decimal("14600"),
            extraction_confidence=85.0,
        )
        session = self._make_session(
            answers={"deductions_charity": "high"},
            parsed=parsed,
        )
        analysis = self.service._run_instant_analysis(session)
        opp_ids = [o.id for o in analysis.opportunities]
        assert "opp_bunching" in opp_ids

    def test_home_office_detected(self):
        session = self._make_session(answers={
            "income_self_employment": "yes_significant",
            "income_home_office": "yes_dedicated",
        })
        analysis = self.service._run_instant_analysis(session)
        opp_ids = [o.id for o in analysis.opportunities]
        assert "opp_home_office" in opp_ids

    def test_opportunities_sorted_by_priority(self):
        session = self._make_session(answers={
            "retirement_401k_available": "yes_with_match",
            "retirement_401k_contribution": "1-5",
            "healthcare_hdhp": "yes",
            "healthcare_hsa": "0",
            "retirement_ira": "no",
        })
        analysis = self.service._run_instant_analysis(session)
        priorities = [o.priority for o in analysis.opportunities]
        assert priorities == sorted(priorities)

    def test_total_savings_is_sum(self):
        session = self._make_session(answers={
            "retirement_401k_available": "yes_with_match",
            "retirement_401k_contribution": "1-5",
            "healthcare_hdhp": "yes",
            "healthcare_hsa": "0",
        })
        analysis = self.service._run_instant_analysis(session)
        opp_total = sum(o.potential_savings for o in analysis.opportunities)
        assert analysis.total_potential_savings == opp_total.quantize(Decimal("1"))

    def test_high_confidence_analysis(self):
        parsed = Parsed1040Data(
            filing_status=FilingStatus.SINGLE,
            adjusted_gross_income=Decimal("85000"),
            wages_salaries_tips=Decimal("85000"),
            extraction_confidence=85.0,
        )
        session = self._make_session(
            answers={
                "retirement_401k_available": "yes_with_match",
                "retirement_401k_contribution": "1-5",
                "healthcare_hdhp": "yes",
                "healthcare_hsa": "0",
                "retirement_ira": "no",
            },
            parsed=parsed,
        )
        analysis = self.service._run_instant_analysis(session)
        assert analysis.analysis_confidence == "high"

    def test_low_confidence_analysis(self):
        parsed = Parsed1040Data(
            filing_status=FilingStatus.SINGLE,
            adjusted_gross_income=Decimal("85000"),
            extraction_confidence=40.0,
        )
        session = self._make_session(answers={}, parsed=parsed)
        analysis = self.service._run_instant_analysis(session)
        assert analysis.analysis_confidence == "low"

    def test_tax_summary_fields(self):
        session = self._make_session(answers={})
        analysis = self.service._run_instant_analysis(session)
        summary = analysis.tax_summary
        assert "filing_status" in summary
        assert "adjusted_gross_income" in summary
        assert "effective_rate" in summary

    def test_max_contribution_already_reached(self):
        """If 401k already at max, no opportunity should be generated."""
        session = self._make_session(answers={
            "retirement_401k_available": "yes_with_match",
            "retirement_401k_contribution": "max",
        })
        analysis = self.service._run_instant_analysis(session)
        opp_ids = [o.id for o in analysis.opportunities]
        assert "opp_401k" not in opp_ids


# =========================================================================
# MARGINAL RATE
# =========================================================================

class TestGetMarginalRate:
    """Tests for _get_marginal_rate."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch("cpa_panel.services.smart_onboarding_service.Form1040Parser"), \
             patch("cpa_panel.services.smart_onboarding_service.AIQuestionGenerator"):
            self.service = SmartOnboardingService()

    @pytest.mark.parametrize("agi,fs,expected", [
        (Decimal("10000"), FilingStatus.SINGLE, Decimal("0.10")),
        (Decimal("30000"), FilingStatus.SINGLE, Decimal("0.12")),
        (Decimal("80000"), FilingStatus.SINGLE, Decimal("0.22")),
        (Decimal("150000"), FilingStatus.SINGLE, Decimal("0.24")),
        (Decimal("230000"), FilingStatus.SINGLE, Decimal("0.32")),
        (Decimal("500000"), FilingStatus.SINGLE, Decimal("0.35")),
        (Decimal("700000"), FilingStatus.SINGLE, Decimal("0.37")),
        (Decimal("20000"), FilingStatus.MARRIED_FILING_JOINTLY, Decimal("0.10")),
        (Decimal("60000"), FilingStatus.MARRIED_FILING_JOINTLY, Decimal("0.12")),
        (Decimal("150000"), FilingStatus.MARRIED_FILING_JOINTLY, Decimal("0.22")),
    ])
    def test_marginal_rate_brackets(self, agi, fs, expected):
        rate = self.service._get_marginal_rate(agi, fs)
        assert rate == expected

    def test_none_filing_status_uses_single(self):
        rate = self.service._get_marginal_rate(Decimal("80000"), None)
        assert rate == Decimal("0.22")


# =========================================================================
# PROGRESS TRACKING
# =========================================================================

class TestCalculateProgress:
    """Tests for _calculate_progress."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch("cpa_panel.services.smart_onboarding_service.Form1040Parser"), \
             patch("cpa_panel.services.smart_onboarding_service.AIQuestionGenerator"):
            self.service = SmartOnboardingService()

    @pytest.mark.parametrize("status,expected_progress", [
        (OnboardingStatus.INITIATED, 10),
        (OnboardingStatus.DOCUMENT_UPLOADED, 20),
        (OnboardingStatus.OCR_PROCESSING, 30),
        (OnboardingStatus.OCR_COMPLETE, 50),
        (OnboardingStatus.QUESTIONS_GENERATED, 60),
        (OnboardingStatus.QUESTIONS_ANSWERED, 80),
        (OnboardingStatus.ANALYSIS_COMPLETE, 90),
        (OnboardingStatus.CLIENT_CREATED, 100),
        (OnboardingStatus.FAILED, 0),
    ])
    def test_progress_by_status(self, status, expected_progress):
        session = OnboardingSession(
            session_id="p1", cpa_id="cpa",
            status=status, created_at=datetime.utcnow(),
        )
        assert self.service._calculate_progress(session) == expected_progress


# =========================================================================
# SESSION SUMMARY
# =========================================================================

class TestGetSessionSummary:
    """Tests for get_session_summary."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch("cpa_panel.services.smart_onboarding_service.Form1040Parser"), \
             patch("cpa_panel.services.smart_onboarding_service.AIQuestionGenerator"):
            self.service = SmartOnboardingService()

    def test_summary_not_found(self):
        summary = self.service.get_session_summary("nonexistent")
        assert "error" in summary

    def test_summary_basic(self):
        session = self.service.start_onboarding("cpa-001")
        summary = self.service.get_session_summary(session.session_id)
        assert summary["session_id"] == session.session_id
        assert summary["status"] == "initiated"
        assert summary["progress"] == 10

    def test_summary_with_parsed_data(self, parsed_1040_single):
        session = self.service.start_onboarding("cpa-001")
        session.parsed_1040 = parsed_1040_single
        session.extraction_confidence = 92.0
        summary = self.service.get_session_summary(session.session_id)
        assert "extracted_data" in summary
        assert summary["extracted_data"]["agi"] == 85000.0

    def test_summary_with_analysis(self, parsed_1040_single, sample_analysis):
        session = self.service.start_onboarding("cpa-001")
        session.parsed_1040 = parsed_1040_single
        session.analysis = sample_analysis
        summary = self.service.get_session_summary(session.session_id)
        assert "analysis" in summary
        assert summary["analysis"]["total_potential_savings"] == 3500.0

    def test_summary_with_client(self):
        session = self.service.start_onboarding("cpa-001")
        session.client_id = "c1"
        session.client_name = "Test Client"
        summary = self.service.get_session_summary(session.session_id)
        assert summary["client"]["id"] == "c1"
        assert summary["client"]["name"] == "Test Client"


# =========================================================================
# CREATE CLIENT
# =========================================================================

class TestCreateClient:
    """Tests for create_client (async)."""

    @pytest.fixture(autouse=True)
    def setup_service(self, parsed_1040_single, sample_analysis):
        with patch("cpa_panel.services.smart_onboarding_service.Form1040Parser"), \
             patch("cpa_panel.services.smart_onboarding_service.AIQuestionGenerator"):
            self.service = SmartOnboardingService()
            session = self.service.start_onboarding("cpa-001")
            session.parsed_1040 = parsed_1040_single
            session.analysis = sample_analysis
            session.status = OnboardingStatus.ANALYSIS_COMPLETE
            self.session_id = session.session_id

    @pytest.mark.asyncio
    async def test_create_client_returns_session(self):
        session = await self.service.create_client(self.session_id)
        assert session.client_id is not None
        assert session.status == OnboardingStatus.CLIENT_CREATED

    @pytest.mark.asyncio
    async def test_create_client_uses_parsed_name(self):
        session = await self.service.create_client(self.session_id)
        assert session.client_name == "Jane Doe"

    @pytest.mark.asyncio
    async def test_create_client_custom_name(self):
        session = await self.service.create_client(self.session_id, client_name="Custom Name")
        assert session.client_name == "Custom Name"

    @pytest.mark.asyncio
    async def test_create_client_not_found_raises(self):
        with pytest.raises(ValueError, match="not found"):
            await self.service.create_client("nonexistent")

    @pytest.mark.asyncio
    async def test_create_client_wrong_status_raises(self):
        session = self.service.get_session(self.session_id)
        session.status = OnboardingStatus.INITIATED
        with pytest.raises(ValueError, match="not ready"):
            await self.service.create_client(self.session_id)

    @pytest.mark.asyncio
    async def test_create_client_generates_uuid(self):
        session = await self.service.create_client(self.session_id)
        uuid.UUID(session.client_id)


# =========================================================================
# ERROR HANDLING
# =========================================================================

class TestErrorHandling:
    """Tests for error scenarios."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch("cpa_panel.services.smart_onboarding_service.Form1040Parser"), \
             patch("cpa_panel.services.smart_onboarding_service.AIQuestionGenerator"):
            self.service = SmartOnboardingService()

    def test_get_session_nonexistent(self):
        assert self.service.get_session("nope") is None

    def test_submit_answers_nonexistent(self):
        with pytest.raises(ValueError):
            self.service.submit_answers("nope", {})


# =========================================================================
# SINGLETON
# =========================================================================

class TestOnboardingSingleton:
    """Test singleton accessor."""

    def test_get_service_returns_instance(self):
        with patch("cpa_panel.services.smart_onboarding_service.Form1040Parser"), \
             patch("cpa_panel.services.smart_onboarding_service.AIQuestionGenerator"):
            svc = get_smart_onboarding_service()
            assert isinstance(svc, SmartOnboardingService)
