"""
Tests for CPA Panel - CPA Decision Intelligence & Advisory Platform.

Comprehensive tests for:
- Workflow management (status transitions, approvals, notes)
- Analysis tools (delta analyzer, tax drivers, scenario comparison)
- CPA insights engine
- API endpoints
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# =============================================================================
# WORKFLOW MODULE TESTS
# =============================================================================

class TestReturnStatus:
    """Test ReturnStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        from cpa_panel.workflow.status_manager import ReturnStatus

        assert ReturnStatus.DRAFT.value == "DRAFT"
        assert ReturnStatus.IN_REVIEW.value == "IN_REVIEW"
        assert ReturnStatus.CPA_APPROVED.value == "CPA_APPROVED"

    def test_status_from_string(self):
        """Test creating status from string."""
        from cpa_panel.workflow.status_manager import ReturnStatus

        assert ReturnStatus("DRAFT") == ReturnStatus.DRAFT
        assert ReturnStatus("IN_REVIEW") == ReturnStatus.IN_REVIEW
        assert ReturnStatus("CPA_APPROVED") == ReturnStatus.CPA_APPROVED

    def test_status_from_string_helper(self):
        """Test from_string helper method."""
        from cpa_panel.workflow.status_manager import ReturnStatus

        assert ReturnStatus.from_string("draft") == ReturnStatus.DRAFT
        assert ReturnStatus.from_string("IN_REVIEW") == ReturnStatus.IN_REVIEW
        assert ReturnStatus.from_string("invalid") == ReturnStatus.DRAFT  # Default


class TestStatusRecord:
    """Test StatusRecord dataclass."""

    def test_status_record_creation(self):
        """Test creating a StatusRecord."""
        from cpa_panel.workflow.status_manager import StatusRecord, ReturnStatus

        record = StatusRecord(
            session_id="test-session",
            status=ReturnStatus.DRAFT
        )

        assert record.session_id == "test-session"
        assert record.status == ReturnStatus.DRAFT
        assert record.tenant_id == "default"

    def test_status_record_to_dict(self):
        """Test converting StatusRecord to dict."""
        from cpa_panel.workflow.status_manager import StatusRecord, ReturnStatus

        record = StatusRecord(
            session_id="test-session",
            status=ReturnStatus.DRAFT
        )

        d = record.to_dict()
        assert d["session_id"] == "test-session"
        assert d["status"] == "DRAFT"


class TestFeatureAccess:
    """Test FeatureAccess class."""

    def test_feature_access_for_draft(self):
        """Test feature access for DRAFT status."""
        from cpa_panel.workflow.status_manager import FeatureAccess, ReturnStatus

        access = FeatureAccess.for_status(ReturnStatus.DRAFT)

        assert access.editable is True
        assert access.export_enabled is False
        assert access.smart_insights_enabled is False
        assert access.can_submit_for_review is True

    def test_feature_access_for_in_review(self):
        """Test feature access for IN_REVIEW status."""
        from cpa_panel.workflow.status_manager import FeatureAccess, ReturnStatus

        # Non-CPA cannot edit
        access = FeatureAccess.for_status(ReturnStatus.IN_REVIEW, is_cpa=False)
        assert access.editable is False
        assert access.can_approve is False

        # CPA can edit and approve
        cpa_access = FeatureAccess.for_status(ReturnStatus.IN_REVIEW, is_cpa=True)
        assert cpa_access.editable is True
        assert cpa_access.can_approve is True

    def test_feature_access_for_approved(self):
        """Test feature access for CPA_APPROVED status."""
        from cpa_panel.workflow.status_manager import FeatureAccess, ReturnStatus

        access = FeatureAccess.for_status(ReturnStatus.CPA_APPROVED)

        assert access.editable is False
        assert access.export_enabled is True
        assert access.smart_insights_enabled is True
        assert access.cpa_approved is True

    def test_feature_access_to_dict(self):
        """Test converting FeatureAccess to dict."""
        from cpa_panel.workflow.status_manager import FeatureAccess, ReturnStatus

        access = FeatureAccess.for_status(ReturnStatus.DRAFT)
        d = access.to_dict()

        assert "editable" in d
        assert "export_enabled" in d
        assert "smart_insights_enabled" in d


class TestCPAWorkflowManager:
    """Test CPAWorkflowManager class."""

    def test_init_creates_workflow_manager(self):
        """Test initialization."""
        from cpa_panel.workflow.status_manager import CPAWorkflowManager

        manager = CPAWorkflowManager()
        assert manager is not None
        assert hasattr(manager, '_persistence')

    def test_get_status_returns_status_record(self):
        """Test get_status returns a StatusRecord."""
        from cpa_panel.workflow.status_manager import CPAWorkflowManager, StatusRecord

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = None

        manager = CPAWorkflowManager(persistence=mock_persistence)
        result = manager.get_status("new-session-123")

        # Should return a StatusRecord object
        assert isinstance(result, StatusRecord)
        assert result.session_id == "new-session-123"

    def test_get_status_default_is_draft(self):
        """Test default status is DRAFT."""
        from cpa_panel.workflow.status_manager import CPAWorkflowManager, ReturnStatus

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = None

        manager = CPAWorkflowManager(persistence=mock_persistence)
        result = manager.get_status("new-session-123")

        assert result.status == ReturnStatus.DRAFT

    def test_transition_valid(self):
        """Test valid status transition."""
        from cpa_panel.workflow.status_manager import CPAWorkflowManager, ReturnStatus

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = None

        manager = CPAWorkflowManager(persistence=mock_persistence)

        # DRAFT -> IN_REVIEW is valid
        can_trans, msg = manager.can_transition("test", ReturnStatus.IN_REVIEW)
        assert can_trans is True

    def test_transition_invalid(self):
        """Test invalid status transition."""
        from cpa_panel.workflow.status_manager import CPAWorkflowManager, ReturnStatus

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = None

        manager = CPAWorkflowManager(persistence=mock_persistence)

        # DRAFT -> CPA_APPROVED is invalid (must go through IN_REVIEW)
        can_trans, msg = manager.can_transition("test", ReturnStatus.CPA_APPROVED)
        assert can_trans is False
        assert "Cannot transition" in msg

    def test_submit_for_review(self):
        """Test submit_for_review method."""
        from cpa_panel.workflow.status_manager import CPAWorkflowManager, ReturnStatus

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = None

        manager = CPAWorkflowManager(persistence=mock_persistence)
        result = manager.submit_for_review("test-session")

        # Verify persistence was called
        mock_persistence.set_return_status.assert_called_once()

    def test_approve_requires_in_review(self):
        """Test approve requires IN_REVIEW status."""
        from cpa_panel.workflow.status_manager import (
            CPAWorkflowManager, WorkflowTransitionError
        )

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = None  # Returns DRAFT default

        manager = CPAWorkflowManager(persistence=mock_persistence)

        with pytest.raises(WorkflowTransitionError):
            manager.approve("test-session", "CPA001", "John CPA")

    def test_get_feature_access(self):
        """Test get_feature_access method."""
        from cpa_panel.workflow.status_manager import CPAWorkflowManager, FeatureAccess

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = None

        manager = CPAWorkflowManager(persistence=mock_persistence)
        access = manager.get_feature_access("test-session")

        assert isinstance(access, FeatureAccess)


class TestApprovalManager:
    """Test ApprovalManager class."""

    def test_generate_signature_hash(self):
        """Test signature hash generation."""
        from cpa_panel.workflow.approval import ApprovalManager

        manager = ApprovalManager()
        hash1 = manager.generate_signature_hash(
            session_id="test-session",
            cpa_reviewer_id="CPA001",
            timestamp=datetime(2025, 1, 15, 10, 0, 0)
        )

        # Hash should be full SHA-256 (64 hex characters) for cryptographic integrity
        assert len(hash1) == 64
        assert isinstance(hash1, str)

    def test_signature_hash_deterministic(self):
        """Test that same inputs produce same hash."""
        from cpa_panel.workflow.approval import ApprovalManager

        manager = ApprovalManager()
        timestamp = datetime(2025, 1, 15, 10, 0, 0)

        hash1 = manager.generate_signature_hash("session", "CPA001", timestamp)
        hash2 = manager.generate_signature_hash("session", "CPA001", timestamp)

        assert hash1 == hash2

    def test_verify_signature_valid(self):
        """Test signature verification for valid signature."""
        from cpa_panel.workflow.approval import ApprovalManager

        manager = ApprovalManager()
        timestamp = datetime(2025, 1, 15, 10, 0, 0)

        signature = manager.generate_signature_hash("session", "CPA001", timestamp)
        is_valid = manager.verify_signature("session", "CPA001", timestamp, signature)

        assert is_valid is True

    def test_verify_signature_invalid(self):
        """Test signature verification for invalid signature."""
        from cpa_panel.workflow.approval import ApprovalManager

        manager = ApprovalManager()
        timestamp = datetime(2025, 1, 15, 10, 0, 0)

        is_valid = manager.verify_signature("session", "CPA001", timestamp, "wrong_hash")

        assert is_valid is False


class TestNotesManager:
    """Test NotesManager class."""

    def test_add_note(self):
        """Test adding a CPA note."""
        from cpa_panel.workflow.notes import NotesManager, NoteCategory

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = {"status": "DRAFT", "review_notes": "[]"}

        manager = NotesManager(persistence=mock_persistence)
        note = manager.add_note(
            session_id="test-session",
            text="Please verify Schedule C calculations",
            cpa_id="CPA001",
            cpa_name="John CPA",
            category=NoteCategory.REVIEW
        )

        assert note is not None
        assert note.text == "Please verify Schedule C calculations"
        assert note.category == NoteCategory.REVIEW

    def test_get_notes_for_session(self):
        """Test getting all notes for a session."""
        from cpa_panel.workflow.notes import NotesManager, NoteCategory

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = {
            "status": "DRAFT",
            "review_notes": '[{"id": "1", "text": "Note 1", "category": "general", "cpa_id": "CPA001", "cpa_name": "John", "timestamp": "2025-01-15T10:00:00"}]'
        }

        manager = NotesManager(persistence=mock_persistence)
        notes = manager.get_notes("test-session", include_internal=True)

        assert len(notes) == 1
        assert notes[0].text == "Note 1"

    def test_delete_note(self):
        """Test deleting a note."""
        from cpa_panel.workflow.notes import NotesManager

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = {
            "status": "DRAFT",
            "review_notes": '[{"id": "note123", "text": "Test", "category": "general", "cpa_id": "CPA001", "cpa_name": "John", "timestamp": "2025-01-15T10:00:00"}]'
        }

        manager = NotesManager(persistence=mock_persistence)
        result = manager.delete_note("test-session", "note123")

        assert result is True

    def test_delete_nonexistent_note(self):
        """Test deleting a note that doesn't exist."""
        from cpa_panel.workflow.notes import NotesManager

        mock_persistence = Mock()
        mock_persistence.get_return_status.return_value = {"status": "DRAFT", "review_notes": "[]"}

        manager = NotesManager(persistence=mock_persistence)
        result = manager.delete_note("test-session", "nonexistent-note-id")

        assert result is False


class TestNoteCategory:
    """Test NoteCategory enum."""

    def test_note_categories(self):
        """Test all note categories exist."""
        from cpa_panel.workflow.notes import NoteCategory

        assert NoteCategory.GENERAL.value == "general"
        assert NoteCategory.REVIEW.value == "review"
        assert NoteCategory.QUESTION.value == "question"
        assert NoteCategory.RECOMMENDATION.value == "recommendation"
        assert NoteCategory.WARNING.value == "warning"


# =============================================================================
# ANALYSIS MODULE TESTS
# =============================================================================

class TestDeltaAnalyzer:
    """Test DeltaAnalyzer class."""

    def test_init(self):
        """Test initialization."""
        from cpa_panel.analysis.delta_analyzer import DeltaAnalyzer

        analyzer = DeltaAnalyzer()
        assert analyzer is not None

    def test_get_marginal_rate(self):
        """Test marginal rate lookup."""
        from cpa_panel.analysis.delta_analyzer import DeltaAnalyzer

        analyzer = DeltaAnalyzer()

        # Test various income levels (based on 2025 single filer brackets)
        assert analyzer._get_marginal_rate(10000) == 0.10
        assert analyzer._get_marginal_rate(15000) == 0.12  # Above 11925 threshold
        assert analyzer._get_marginal_rate(50000) == 0.22  # Above 48475 threshold
        assert analyzer._get_marginal_rate(110000) == 0.24  # Above 103350 threshold
        assert analyzer._get_marginal_rate(1000000) == 0.37

    def test_calculate_effective_rate(self):
        """Test effective rate calculation."""
        from cpa_panel.analysis.delta_analyzer import DeltaAnalyzer

        analyzer = DeltaAnalyzer()

        # 10% effective rate
        rate = analyzer._calculate_effective_rate(10000, 100000)
        assert rate == 0.10

        # Handle zero income
        rate = analyzer._calculate_effective_rate(1000, 0)
        assert rate == 0


class TestChangeType:
    """Test ChangeType enum."""

    def test_change_types_exist(self):
        """Test all change types exist."""
        from cpa_panel.analysis.delta_analyzer import ChangeType

        assert ChangeType.INCOME.value == "income"
        assert ChangeType.WAGES.value == "wages"
        assert ChangeType.DEDUCTION.value == "deduction"
        assert ChangeType.CREDIT.value == "credit"


class TestTaxMetrics:
    """Test TaxMetrics dataclass."""

    def test_tax_metrics_creation(self):
        """Test creating TaxMetrics."""
        from cpa_panel.analysis.delta_analyzer import TaxMetrics

        metrics = TaxMetrics(
            adjusted_gross_income=100000,
            taxable_income=85000,
            tax_liability=15000,
            effective_rate=0.15
        )

        assert metrics.adjusted_gross_income == 100000
        assert metrics.taxable_income == 85000

    def test_tax_metrics_to_dict(self):
        """Test TaxMetrics to_dict method."""
        from cpa_panel.analysis.delta_analyzer import TaxMetrics

        metrics = TaxMetrics(adjusted_gross_income=100000)
        d = metrics.to_dict()

        assert "adjusted_gross_income" in d
        assert d["adjusted_gross_income"] == 100000


class TestTaxDriversAnalyzer:
    """Test TaxDriversAnalyzer class."""

    def test_init(self):
        """Test initialization."""
        from cpa_panel.analysis.tax_drivers import TaxDriversAnalyzer

        analyzer = TaxDriversAnalyzer()
        assert analyzer is not None

    def test_marginal_rate_lookup(self):
        """Test marginal rate lookup."""
        from cpa_panel.analysis.tax_drivers import TaxDriversAnalyzer

        analyzer = TaxDriversAnalyzer()

        # Test bracket boundaries (2025 single filer brackets)
        rate1 = analyzer._get_marginal_rate(10000)
        assert rate1 == 0.10

        rate2 = analyzer._get_marginal_rate(200000)
        assert rate2 == 0.32  # Above 197300 threshold, below 250500


class TestTaxDriver:
    """Test TaxDriver dataclass."""

    def test_tax_driver_creation(self):
        """Test creating TaxDriver."""
        from cpa_panel.analysis.tax_drivers import TaxDriver, DriverDirection

        driver = TaxDriver(
            rank=1,
            factor="Wages",
            impact="Primary income source",
            direction=DriverDirection.INCREASES,
            dollar_amount=100000
        )

        assert driver.rank == 1
        assert driver.factor == "Wages"
        assert driver.direction == DriverDirection.INCREASES

    def test_tax_driver_to_dict(self):
        """Test TaxDriver to_dict method."""
        from cpa_panel.analysis.tax_drivers import TaxDriver, DriverDirection

        driver = TaxDriver(
            rank=1,
            factor="Wages",
            impact="Primary income",
            direction=DriverDirection.INCREASES
        )

        d = driver.to_dict()
        assert d["rank"] == 1
        assert d["factor"] == "Wages"


class TestScenarioComparator:
    """Test ScenarioComparator class."""

    def test_init(self):
        """Test initialization."""
        from cpa_panel.analysis.scenario_comparison import ScenarioComparator

        comparator = ScenarioComparator()
        assert comparator is not None


class TestScenario:
    """Test Scenario dataclass."""

    def test_scenario_creation(self):
        """Test creating Scenario."""
        from cpa_panel.analysis.scenario_comparison import Scenario

        scenario = Scenario(
            name="Max 401k",
            description="Maximize 401k contribution"
        )

        assert scenario.name == "Max 401k"
        assert scenario.description == "Maximize 401k contribution"


class TestScenarioAdjustment:
    """Test ScenarioAdjustment dataclass."""

    def test_adjustment_creation(self):
        """Test creating ScenarioAdjustment."""
        from cpa_panel.analysis.scenario_comparison import ScenarioAdjustment

        adjustment = ScenarioAdjustment(
            field="traditional_401k",
            value=23000,
            description="Max out 401k"
        )

        assert adjustment.field == "traditional_401k"
        assert adjustment.value == 23000


# =============================================================================
# INSIGHTS MODULE TESTS
# =============================================================================

class TestCPAInsightsEngine:
    """Test CPAInsightsEngine class."""

    def test_init(self):
        """Test initialization."""
        from cpa_panel.insights.cpa_insights import CPAInsightsEngine

        engine = CPAInsightsEngine()
        assert engine is not None


class TestInsightCategory:
    """Test InsightCategory enum."""

    def test_categories_exist(self):
        """Test all insight categories exist."""
        from cpa_panel.insights.cpa_insights import InsightCategory

        assert InsightCategory.REVIEW_REQUIRED.value == "review_required"
        assert InsightCategory.RISK_FLAG.value == "risk_flag"
        assert InsightCategory.COMPLIANCE.value == "compliance"
        assert InsightCategory.OPTIMIZATION.value == "optimization"


class TestInsightPriority:
    """Test InsightPriority enum."""

    def test_priorities_exist(self):
        """Test all insight priorities exist."""
        from cpa_panel.insights.cpa_insights import InsightPriority

        assert InsightPriority.CRITICAL.value == "critical"
        assert InsightPriority.HIGH.value == "high"
        assert InsightPriority.MEDIUM.value == "medium"
        assert InsightPriority.LOW.value == "low"


class TestCPAInsight:
    """Test CPAInsight dataclass."""

    def test_insight_creation(self):
        """Test creating CPAInsight."""
        from cpa_panel.insights.cpa_insights import (
            CPAInsight, InsightCategory, InsightPriority
        )

        insight = CPAInsight(
            id="INS001",
            category=InsightCategory.REVIEW_REQUIRED,
            priority=InsightPriority.HIGH,
            title="High charitable deduction",
            description="Charitable contributions are 40% of AGI"
        )

        assert insight.id == "INS001"
        assert insight.category == InsightCategory.REVIEW_REQUIRED
        assert insight.priority == InsightPriority.HIGH

    def test_insight_to_dict(self):
        """Test CPAInsight to_dict method."""
        from cpa_panel.insights.cpa_insights import (
            CPAInsight, InsightCategory, InsightPriority
        )

        insight = CPAInsight(
            id="INS001",
            category=InsightCategory.RISK_FLAG,
            priority=InsightPriority.CRITICAL,
            title="Test",
            description="Test description"
        )

        d = insight.to_dict()
        assert d["id"] == "INS001"
        assert d["category"] == "risk_flag"
        assert d["priority"] == "critical"


# =============================================================================
# API ROUTER TESTS
# =============================================================================

class TestCPAPanelRouter:
    """Test CPA Panel API router."""

    def test_router_import(self):
        """Test that CPA router can be imported."""
        from cpa_panel.api.router import cpa_router
        assert cpa_router is not None

    def test_router_has_correct_prefix(self):
        """Test router prefix is correct."""
        from cpa_panel.api.router import cpa_router
        assert cpa_router.prefix == "/cpa"

    def test_router_has_status_endpoint(self):
        """Test router has status endpoint."""
        from cpa_panel.api.router import cpa_router

        routes = [r.path for r in cpa_router.routes]
        assert any("/returns/{session_id}/status" in r for r in routes)

    def test_router_has_insights_endpoint(self):
        """Test router has insights endpoint."""
        from cpa_panel.api.router import cpa_router

        routes = [r.path for r in cpa_router.routes]
        assert any("/returns/{session_id}/insights" in r for r in routes)

    def test_router_has_delta_endpoint(self):
        """Test router has delta analysis endpoint."""
        from cpa_panel.api.router import cpa_router

        routes = [r.path for r in cpa_router.routes]
        assert any("/returns/{session_id}/delta" in r for r in routes)

    def test_router_has_notes_endpoint(self):
        """Test router has notes endpoint."""
        from cpa_panel.api.router import cpa_router

        routes = [r.path for r in cpa_router.routes]
        assert any("/returns/{session_id}/notes" in r for r in routes)

    def test_router_has_queue_endpoints(self):
        """Test router has queue management endpoints."""
        from cpa_panel.api.router import cpa_router

        routes = [r.path for r in cpa_router.routes]
        assert any("/queue" in r for r in routes)


# =============================================================================
# MODULE EXPORT TESTS
# =============================================================================

class TestCPAPanelModuleExports:
    """Test module exports are correct."""

    def test_main_module_exports(self):
        """Test main cpa_panel module exports."""
        from cpa_panel import (
            ReturnStatus,
            CPAWorkflowManager,
            WorkflowTransitionError,
            ApprovalManager,
            ApprovalRecord,
            DeltaAnalyzer,
            DeltaResult,
            TaxDriversAnalyzer,
            TaxDriver,
            ScenarioComparator,
            Scenario,
            ScenarioResult,
            CPAInsightsEngine,
            CPAInsight
        )

        # All exports should be importable
        assert ReturnStatus is not None
        assert CPAWorkflowManager is not None
        assert ApprovalManager is not None
        assert DeltaAnalyzer is not None
        assert TaxDriversAnalyzer is not None
        assert ScenarioComparator is not None
        assert CPAInsightsEngine is not None

    def test_workflow_module_exports(self):
        """Test workflow submodule exports."""
        from cpa_panel.workflow import (
            ReturnStatus,
            CPAWorkflowManager,
            StatusRecord,
            ApprovalManager,
            NotesManager,
            CPANote
        )

        assert ReturnStatus is not None
        assert CPAWorkflowManager is not None
        assert StatusRecord is not None
        assert ApprovalManager is not None
        assert NotesManager is not None
        assert CPANote is not None

    def test_analysis_module_exports(self):
        """Test analysis submodule exports."""
        from cpa_panel.analysis import (
            DeltaAnalyzer,
            DeltaResult,
            ChangeType,
            TaxDriversAnalyzer,
            TaxDriver,
            ScenarioComparator,
            Scenario
        )

        assert DeltaAnalyzer is not None
        assert DeltaResult is not None
        assert ChangeType is not None
        assert TaxDriversAnalyzer is not None
        assert TaxDriver is not None
        assert ScenarioComparator is not None
        assert Scenario is not None

    def test_insights_module_exports(self):
        """Test insights submodule exports."""
        from cpa_panel.insights import (
            CPAInsightsEngine,
            CPAInsight,
            InsightCategory,
            InsightPriority
        )

        assert CPAInsightsEngine is not None
        assert CPAInsight is not None
        assert InsightCategory is not None
        assert InsightPriority is not None

    def test_api_module_exports(self):
        """Test API submodule exports."""
        from cpa_panel.api import cpa_router

        assert cpa_router is not None


# =============================================================================
# WORKFLOW INTEGRATION TESTS
# =============================================================================

class TestWorkflowIntegration:
    """Integration tests for workflow module."""

    def test_workflow_transition_rules(self):
        """Test valid workflow transitions."""
        from cpa_panel.workflow.status_manager import VALID_TRANSITIONS, ReturnStatus

        # DRAFT can only go to IN_REVIEW
        assert VALID_TRANSITIONS[ReturnStatus.DRAFT] == [ReturnStatus.IN_REVIEW]

        # IN_REVIEW can go to CPA_APPROVED or back to DRAFT
        assert ReturnStatus.CPA_APPROVED in VALID_TRANSITIONS[ReturnStatus.IN_REVIEW]
        assert ReturnStatus.DRAFT in VALID_TRANSITIONS[ReturnStatus.IN_REVIEW]

        # CPA_APPROVED can only go back to DRAFT
        assert VALID_TRANSITIONS[ReturnStatus.CPA_APPROVED] == [ReturnStatus.DRAFT]


class TestWorkflowTransitionError:
    """Test WorkflowTransitionError exception."""

    def test_error_attributes(self):
        """Test error has correct attributes."""
        from cpa_panel.workflow.status_manager import WorkflowTransitionError

        error = WorkflowTransitionError(
            "Cannot transition",
            current_status="DRAFT",
            target_status="CPA_APPROVED"
        )

        assert error.current_status == "DRAFT"
        assert error.target_status == "CPA_APPROVED"
        assert "Cannot transition" in str(error)
