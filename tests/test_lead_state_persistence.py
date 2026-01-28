"""
Tests for Lead State Persistence Layer.

Tests database-backed persistence for leads, signals, and transitions.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from database.lead_state_persistence import (
    LeadStatePersistence,
    LeadDbRecord,
    SignalDbRecord,
    TransitionDbRecord,
)


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


class TestLeadPersistence:
    """Tests for lead CRUD operations."""

    def test_save_new_lead(self, persistence):
        """Test saving a new lead."""
        lead = persistence.save_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
            current_state="BROWSING",
        )

        assert lead.lead_id == "lead-001"
        assert lead.session_id == "session-001"
        assert lead.tenant_id == "tenant-a"
        assert lead.current_state == "BROWSING"
        assert lead.created_at is not None
        assert lead.updated_at is not None

    def test_update_existing_lead(self, persistence):
        """Test updating an existing lead."""
        # Save initial
        persistence.save_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
            current_state="BROWSING",
        )

        # Update
        updated = persistence.save_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
            current_state="CURIOUS",
        )

        assert updated.current_state == "CURIOUS"

    def test_load_lead(self, persistence):
        """Test loading a lead by ID."""
        persistence.save_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
        )

        lead = persistence.load_lead("lead-001")
        assert lead is not None
        assert lead.lead_id == "lead-001"

    def test_load_lead_with_tenant_filter(self, persistence):
        """Test loading a lead with tenant filter."""
        persistence.save_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
        )

        # Should find with correct tenant
        lead = persistence.load_lead("lead-001", tenant_id="tenant-a")
        assert lead is not None

        # Should not find with wrong tenant
        lead = persistence.load_lead("lead-001", tenant_id="tenant-b")
        assert lead is None

    def test_load_nonexistent_lead(self, persistence):
        """Test loading a nonexistent lead returns None."""
        lead = persistence.load_lead("nonexistent")
        assert lead is None

    def test_delete_lead(self, persistence):
        """Test deleting a lead."""
        persistence.save_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
        )

        # Add signal and transition for cascade delete test
        persistence.save_signal(
            lead_id="lead-001",
            signal_id="discovery.page_view",
            tenant_id="tenant-a",
        )
        persistence.save_transition(
            lead_id="lead-001",
            from_state="BROWSING",
            to_state="CURIOUS",
            trigger_signal_id="discovery.page_view",
        )

        # Delete
        result = persistence.delete_lead("lead-001")
        assert result is True

        # Verify deleted
        lead = persistence.load_lead("lead-001")
        assert lead is None

        # Verify signals deleted
        signals = persistence.get_signals_for_lead("lead-001")
        assert len(signals) == 0

        # Verify transitions deleted
        transitions = persistence.get_transitions_for_lead("lead-001")
        assert len(transitions) == 0

    def test_list_leads(self, persistence):
        """Test listing leads for a tenant."""
        # Create leads for two tenants
        persistence.save_lead("lead-001", "session-001", "tenant-a")
        persistence.save_lead("lead-002", "session-002", "tenant-a")
        persistence.save_lead("lead-003", "session-003", "tenant-b")

        # List for tenant-a
        leads = persistence.list_leads(tenant_id="tenant-a")
        assert len(leads) == 2

        # List for tenant-b
        leads = persistence.list_leads(tenant_id="tenant-b")
        assert len(leads) == 1

    def test_list_leads_by_state(self, persistence):
        """Test listing leads by state."""
        persistence.save_lead("lead-001", "s1", "tenant-a", "BROWSING")
        persistence.save_lead("lead-002", "s2", "tenant-a", "CURIOUS")
        persistence.save_lead("lead-003", "s3", "tenant-a", "CURIOUS")
        persistence.save_lead("lead-004", "s4", "tenant-a", "ADVISORY_READY")

        curious = persistence.list_leads_by_state("CURIOUS", "tenant-a")
        assert len(curious) == 2

        browsing = persistence.list_leads_by_state("BROWSING", "tenant-a")
        assert len(browsing) == 1

    def test_get_state_counts(self, persistence):
        """Test getting state counts."""
        persistence.save_lead("lead-001", "s1", "tenant-a", "BROWSING")
        persistence.save_lead("lead-002", "s2", "tenant-a", "BROWSING")
        persistence.save_lead("lead-003", "s3", "tenant-a", "CURIOUS")
        persistence.save_lead("lead-004", "s4", "tenant-a", "ADVISORY_READY")

        counts = persistence.get_state_counts("tenant-a")
        assert counts["BROWSING"] == 2
        assert counts["CURIOUS"] == 1
        assert counts["ADVISORY_READY"] == 1
        assert counts["EVALUATING"] == 0
        assert counts["HIGH_LEVERAGE"] == 0


class TestSignalPersistence:
    """Tests for signal persistence."""

    def test_save_signal(self, persistence):
        """Test saving a signal."""
        persistence.save_lead("lead-001", "session-001", "tenant-a")

        signal = persistence.save_signal(
            lead_id="lead-001",
            signal_id="discovery.page_view",
            tenant_id="tenant-a",
            metadata={"page": "/pricing"},
        )

        assert signal.lead_id == "lead-001"
        assert signal.signal_id == "discovery.page_view"
        assert signal.tenant_id == "tenant-a"
        assert signal.metadata == {"page": "/pricing"}

    def test_get_signals_for_lead(self, persistence):
        """Test getting signal history for a lead."""
        persistence.save_lead("lead-001", "session-001", "tenant-a")
        persistence.save_signal("lead-001", "discovery.page_view", "tenant-a")
        persistence.save_signal("lead-001", "discovery.multiple_pages", "tenant-a")
        persistence.save_signal("lead-001", "evaluation.tax_complexity", "tenant-a")

        signals = persistence.get_signals_for_lead("lead-001")
        assert len(signals) == 3
        assert signals[0].signal_id == "discovery.page_view"
        assert signals[1].signal_id == "discovery.multiple_pages"
        assert signals[2].signal_id == "evaluation.tax_complexity"

    def test_get_signal_ids_for_lead(self, persistence):
        """Test getting just signal IDs for a lead."""
        persistence.save_lead("lead-001", "session-001", "tenant-a")
        persistence.save_signal("lead-001", "discovery.page_view", "tenant-a")
        persistence.save_signal("lead-001", "discovery.multiple_pages", "tenant-a")

        signal_ids = persistence.get_signal_ids_for_lead("lead-001")
        assert signal_ids == ["discovery.page_view", "discovery.multiple_pages"]


class TestTransitionPersistence:
    """Tests for transition persistence."""

    def test_save_transition(self, persistence):
        """Test saving a transition."""
        persistence.save_lead("lead-001", "session-001", "tenant-a")

        transition = persistence.save_transition(
            lead_id="lead-001",
            from_state="BROWSING",
            to_state="CURIOUS",
            trigger_signal_id="discovery.page_view",
            metadata={"reason": "threshold_reached"},
        )

        assert transition.lead_id == "lead-001"
        assert transition.from_state == "BROWSING"
        assert transition.to_state == "CURIOUS"
        assert transition.trigger_signal_id == "discovery.page_view"
        assert transition.metadata == {"reason": "threshold_reached"}

    def test_get_transitions_for_lead(self, persistence):
        """Test getting transition history for a lead."""
        persistence.save_lead("lead-001", "session-001", "tenant-a")
        persistence.save_transition(
            "lead-001", "BROWSING", "CURIOUS", "discovery.page_view"
        )
        persistence.save_transition(
            "lead-001", "CURIOUS", "EVALUATING", "evaluation.tax_complexity"
        )
        persistence.save_transition(
            "lead-001", "EVALUATING", "ADVISORY_READY", "commitment.contact_request"
        )

        transitions = persistence.get_transitions_for_lead("lead-001")
        assert len(transitions) == 3
        assert transitions[0].from_state == "BROWSING"
        assert transitions[0].to_state == "CURIOUS"
        assert transitions[1].from_state == "CURIOUS"
        assert transitions[1].to_state == "EVALUATING"
        assert transitions[2].from_state == "EVALUATING"
        assert transitions[2].to_state == "ADVISORY_READY"


class TestFullLeadLoad:
    """Tests for loading complete lead data."""

    def test_load_full_lead(self, persistence):
        """Test loading a complete lead with signals and transitions."""
        persistence.save_lead("lead-001", "session-001", "tenant-a", "ADVISORY_READY")
        persistence.save_signal("lead-001", "discovery.page_view", "tenant-a")
        persistence.save_signal("lead-001", "evaluation.tax_complexity", "tenant-a")
        persistence.save_transition(
            "lead-001", "BROWSING", "CURIOUS", "discovery.page_view"
        )
        persistence.save_transition(
            "lead-001", "CURIOUS", "ADVISORY_READY", "evaluation.tax_complexity"
        )

        full = persistence.load_full_lead("lead-001")
        assert full is not None
        assert full["lead"].lead_id == "lead-001"
        assert full["lead"].current_state == "ADVISORY_READY"
        assert len(full["signals"]) == 2
        assert len(full["transitions"]) == 2

    def test_load_full_lead_not_found(self, persistence):
        """Test loading full data for nonexistent lead."""
        full = persistence.load_full_lead("nonexistent")
        assert full is None


class TestLeadMetadata:
    """Tests for lead metadata handling."""

    def test_save_lead_with_metadata(self, persistence):
        """Test saving a lead with metadata."""
        metadata = {
            "source": "google_ads",
            "utm_campaign": "tax_2025",
            "initial_page": "/schedule-c",
        }

        lead = persistence.save_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
            metadata=metadata,
        )

        assert lead.metadata == metadata

        # Reload and verify
        loaded = persistence.load_lead("lead-001")
        # Check key metadata fields (system may add _pii_encrypted flag)
        for key, value in metadata.items():
            assert loaded.metadata.get(key) == value

    def test_update_lead_metadata(self, persistence):
        """Test updating lead metadata."""
        persistence.save_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
            metadata={"version": 1},
        )

        persistence.save_lead(
            lead_id="lead-001",
            session_id="session-001",
            tenant_id="tenant-a",
            metadata={"version": 2, "updated": True},
        )

        loaded = persistence.load_lead("lead-001")
        # Check key metadata fields (system may add _pii_encrypted flag)
        assert loaded.metadata.get("version") == 2
        assert loaded.metadata.get("updated") == True
