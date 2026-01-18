"""
Tests for Lead State Engine with Persistence Integration.

Tests that the engine correctly persists and restores lead state.
"""

import pytest
import tempfile
from pathlib import Path

from cpa_panel.lead_state import LeadStateEngine, LeadState
from database.lead_state_persistence import LeadStatePersistence


@pytest.fixture
def persistence():
    """Create a fresh persistence instance with temp database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    p = LeadStatePersistence(db_path=db_path)
    yield p

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def engine(persistence):
    """Create engine with persistence."""
    return LeadStateEngine(persistence=persistence)


class TestEngineWithPersistence:
    """Tests for engine with persistence layer."""

    def test_create_lead_persists(self, engine, persistence):
        """Test that creating a lead persists it to database."""
        lead = engine.get_or_create_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
        )

        assert lead.lead_id == "lead-001"

        # Verify persisted
        db_lead = persistence.load_lead("lead-001", "tenant-a")
        assert db_lead is not None
        assert db_lead.lead_id == "lead-001"
        assert db_lead.current_state == "BROWSING"

    def test_signal_persists(self, engine, persistence):
        """Test that processing signals persists them."""
        engine.process_signal(
            lead_id="lead-001",
            signal_id="discovery.viewed_outcome",
            session_id="session-001",
            tenant_id="tenant-a",
        )

        # Verify signal persisted
        signals = persistence.get_signal_ids_for_lead("lead-001")
        assert "discovery.viewed_outcome" in signals

    def test_transition_persists(self, engine, persistence):
        """Test that state transitions persist."""
        # Process enough signals to trigger transition
        for signal_id in [
            "discovery.viewed_outcome",
            "discovery.expanded_drivers",
            "discovery.returned_session",
        ]:
            engine.process_signal(
                lead_id="lead-001",
                signal_id=signal_id,
                session_id="session-001",
                tenant_id="tenant-a",
            )

        # Verify transition persisted
        transitions = persistence.get_transitions_for_lead("lead-001")
        assert len(transitions) >= 1
        assert transitions[0].from_state == "BROWSING"
        assert transitions[0].to_state == "CURIOUS"

        # Verify lead state updated in DB
        db_lead = persistence.load_lead("lead-001")
        assert db_lead.current_state == "CURIOUS"

    def test_restore_lead_from_persistence(self, persistence):
        """Test that a lead can be restored from persistence after engine restart."""
        # Create engine and process signals
        engine1 = LeadStateEngine(persistence=persistence)
        engine1.process_signal(
            lead_id="lead-001",
            signal_id="discovery.viewed_outcome",
            session_id="session-001",
            tenant_id="tenant-a",
        )
        engine1.process_signal(
            lead_id="lead-001",
            signal_id="discovery.expanded_drivers",
            session_id="session-001",
            tenant_id="tenant-a",
        )
        engine1.process_signal(
            lead_id="lead-001",
            signal_id="discovery.returned_session",
            session_id="session-001",
            tenant_id="tenant-a",
        )

        lead1 = engine1.get_lead("lead-001")
        assert lead1.current_state == LeadState.CURIOUS
        assert lead1.signal_count == 3

        # Create new engine (simulating restart)
        engine2 = LeadStateEngine(persistence=persistence)

        # Get lead - should restore from DB
        lead2 = engine2.get_lead("lead-001", tenant_id="tenant-a")
        assert lead2 is not None
        assert lead2.current_state == LeadState.CURIOUS
        assert lead2.signal_count == 3
        assert len(lead2.transitions) == 1

    def test_continue_processing_after_restore(self, persistence):
        """Test that processing continues correctly after restore."""
        # First engine session
        engine1 = LeadStateEngine(persistence=persistence)
        for signal_id in [
            "discovery.viewed_outcome",
            "discovery.expanded_drivers",
            "discovery.returned_session",
        ]:
            engine1.process_signal(
                lead_id="lead-001",
                signal_id=signal_id,
                session_id="session-001",
                tenant_id="tenant-a",
            )

        # Second engine session - add more signals
        engine2 = LeadStateEngine(persistence=persistence)
        engine2.process_signal(
            lead_id="lead-001",
            signal_id="evaluation.compared_scenarios",
            session_id="session-001",
            tenant_id="tenant-a",
        )
        engine2.process_signal(
            lead_id="lead-001",
            signal_id="evaluation.downloaded_summary",
            session_id="session-001",
            tenant_id="tenant-a",
        )

        lead = engine2.get_lead("lead-001")
        assert lead.current_state == LeadState.EVALUATING
        assert lead.signal_count == 5  # 3 + 2

    def test_get_state_counts_uses_persistence(self, engine, persistence):
        """Test that get_state_counts uses persistence."""
        # Create multiple leads
        for i in range(3):
            persistence.save_lead(
                lead_id=f"lead-{i}",
                session_id=f"session-{i}",
                tenant_id="tenant-a",
                current_state="BROWSING",
            )

        for i in range(3, 5):
            persistence.save_lead(
                lead_id=f"lead-{i}",
                session_id=f"session-{i}",
                tenant_id="tenant-a",
                current_state="CURIOUS",
            )

        counts = engine.get_state_counts(tenant_id="tenant-a")
        assert counts["BROWSING"] == 3
        assert counts["CURIOUS"] == 2

    def test_get_leads_by_state_loads_from_persistence(self, engine, persistence):
        """Test that get_leads_by_state loads leads from persistence."""
        # Create leads directly in persistence
        persistence.save_lead("lead-001", "s1", "tenant-a", "EVALUATING")
        persistence.save_lead("lead-002", "s2", "tenant-a", "EVALUATING")
        persistence.save_lead("lead-003", "s3", "tenant-a", "BROWSING")

        leads = engine.get_leads_by_state(LeadState.EVALUATING, tenant_id="tenant-a")
        assert len(leads) == 2
        assert all(l.current_state == LeadState.EVALUATING for l in leads)

    def test_queue_summary_with_persistence(self, engine, persistence):
        """Test queue summary reflects persisted data."""
        persistence.save_lead("l1", "s1", "tenant-a", "BROWSING")
        persistence.save_lead("l2", "s2", "tenant-a", "BROWSING")
        persistence.save_lead("l3", "s3", "tenant-a", "CURIOUS")
        persistence.save_lead("l4", "s4", "tenant-a", "EVALUATING")
        persistence.save_lead("l5", "s5", "tenant-a", "ADVISORY_READY")
        persistence.save_lead("l6", "s6", "tenant-a", "HIGH_LEVERAGE")

        summary = engine.get_queue_summary(tenant_id="tenant-a")

        assert summary["total_leads"] == 6
        assert summary["visible_count"] == 3  # EVALUATING + ADVISORY_READY + HIGH_LEVERAGE
        assert summary["monetizable_count"] == 2  # ADVISORY_READY + HIGH_LEVERAGE
        assert summary["priority_count"] == 1  # HIGH_LEVERAGE
        assert summary["hidden_count"] == 3  # BROWSING + CURIOUS


class TestEngineWithoutPersistence:
    """Tests ensuring engine still works without persistence."""

    def test_engine_works_in_memory_only(self):
        """Test that engine works without persistence."""
        engine = LeadStateEngine()  # No persistence

        lead = engine.get_or_create_lead(
            lead_id="lead-001",
            session_id="session-001",
        )

        assert lead.lead_id == "lead-001"
        assert lead.current_state == LeadState.BROWSING

    def test_signals_work_without_persistence(self):
        """Test signal processing without persistence."""
        engine = LeadStateEngine()

        for signal_id in [
            "discovery.viewed_outcome",
            "discovery.expanded_drivers",
            "discovery.returned_session",
        ]:
            engine.process_signal(
                lead_id="lead-001",
                signal_id=signal_id,
                session_id="session-001",
            )

        lead = engine.get_lead("lead-001")
        assert lead.current_state == LeadState.CURIOUS
        assert lead.signal_count == 3


class TestTenantIsolation:
    """Tests for tenant isolation with persistence."""

    def test_tenant_isolation_in_queries(self, persistence):
        """Test that leads are isolated by tenant."""
        engine = LeadStateEngine(persistence=persistence)

        # Create leads for different tenants
        persistence.save_lead("l1", "s1", "tenant-a", "ADVISORY_READY")
        persistence.save_lead("l2", "s2", "tenant-a", "ADVISORY_READY")
        persistence.save_lead("l3", "s3", "tenant-b", "ADVISORY_READY")

        # Query for tenant-a
        leads_a = engine.get_monetizable_leads(tenant_id="tenant-a")
        assert len(leads_a) == 2

        # Query for tenant-b
        leads_b = engine.get_monetizable_leads(tenant_id="tenant-b")
        assert len(leads_b) == 1

    def test_load_lead_respects_tenant(self, persistence):
        """Test that loading a lead respects tenant filter."""
        engine = LeadStateEngine(persistence=persistence)

        persistence.save_lead("lead-001", "s1", "tenant-a", "BROWSING")

        # Should find with correct tenant
        lead = engine.get_lead("lead-001", tenant_id="tenant-a")
        assert lead is not None

        # Should not find with wrong tenant
        lead = engine.get_lead("lead-001", tenant_id="tenant-b")
        assert lead is None
