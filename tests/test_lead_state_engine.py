"""
Tests for Lead State Engine

Verifies:
1. Forward-only state transitions
2. Signal processing and accumulation
3. Threshold-based state advancement
4. CPA visibility rules
5. State machine integrity
"""

import pytest
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cpa_panel.lead_state.states import (
    LeadState,
    SignalType,
    SignalStrength,
    CPAVisibility,
    STATE_VISIBILITY,
    can_transition,
    get_visibility,
)

from cpa_panel.lead_state.signals import (
    LeadSignal,
    DiscoverySignal,
    EvaluationSignal,
    CommitmentSignal,
    SIGNAL_CATALOG,
    get_signal,
    get_signals_by_type,
)

from cpa_panel.lead_state.engine import (
    LeadStateEngine,
    LeadRecord,
    StateTransition,
    TransitionError,
)


# =============================================================================
# STATE TESTS
# =============================================================================

class TestLeadStates:
    """Test lead state properties and ordering."""

    def test_state_ordering(self):
        """States should be ordered by engagement level."""
        assert LeadState.BROWSING < LeadState.CURIOUS
        assert LeadState.CURIOUS < LeadState.EVALUATING
        assert LeadState.EVALUATING < LeadState.ADVISORY_READY
        assert LeadState.ADVISORY_READY < LeadState.HIGH_LEVERAGE

    def test_monetizable_states(self):
        """Only ADVISORY_READY and HIGH_LEVERAGE are monetizable."""
        assert not LeadState.BROWSING.is_monetizable
        assert not LeadState.CURIOUS.is_monetizable
        assert not LeadState.EVALUATING.is_monetizable
        assert LeadState.ADVISORY_READY.is_monetizable
        assert LeadState.HIGH_LEVERAGE.is_monetizable

    def test_visible_states(self):
        """EVALUATING and above are visible to CPA."""
        assert not LeadState.BROWSING.is_visible_to_cpa
        assert not LeadState.CURIOUS.is_visible_to_cpa
        assert LeadState.EVALUATING.is_visible_to_cpa
        assert LeadState.ADVISORY_READY.is_visible_to_cpa
        assert LeadState.HIGH_LEVERAGE.is_visible_to_cpa

    def test_priority_state(self):
        """Only HIGH_LEVERAGE is priority."""
        assert not LeadState.BROWSING.is_priority
        assert not LeadState.CURIOUS.is_priority
        assert not LeadState.EVALUATING.is_priority
        assert not LeadState.ADVISORY_READY.is_priority
        assert LeadState.HIGH_LEVERAGE.is_priority

    def test_state_visibility_mapping(self):
        """Each state has correct visibility level."""
        assert get_visibility(LeadState.BROWSING) == CPAVisibility.HIDDEN
        assert get_visibility(LeadState.CURIOUS) == CPAVisibility.AGGREGATE_ONLY
        assert get_visibility(LeadState.EVALUATING) == CPAVisibility.PASSIVE
        assert get_visibility(LeadState.ADVISORY_READY) == CPAVisibility.ACTIVE
        assert get_visibility(LeadState.HIGH_LEVERAGE) == CPAVisibility.PRIORITY

    def test_display_names(self):
        """States have display names with indicators."""
        assert "Browsing" in LeadState.BROWSING.display_name
        assert "Curious" in LeadState.CURIOUS.display_name
        assert "Evaluating" in LeadState.EVALUATING.display_name
        assert "⭐" in LeadState.ADVISORY_READY.display_name
        assert "🔥" in LeadState.HIGH_LEVERAGE.display_name


# =============================================================================
# TRANSITION VALIDATION TESTS
# =============================================================================

class TestTransitionValidation:
    """Test forward-only transition rules."""

    def test_forward_transitions_allowed(self):
        """Forward transitions should be allowed."""
        assert can_transition(LeadState.BROWSING, LeadState.CURIOUS)
        assert can_transition(LeadState.BROWSING, LeadState.EVALUATING)
        assert can_transition(LeadState.BROWSING, LeadState.ADVISORY_READY)
        assert can_transition(LeadState.BROWSING, LeadState.HIGH_LEVERAGE)
        assert can_transition(LeadState.CURIOUS, LeadState.EVALUATING)
        assert can_transition(LeadState.CURIOUS, LeadState.ADVISORY_READY)
        assert can_transition(LeadState.EVALUATING, LeadState.ADVISORY_READY)
        assert can_transition(LeadState.ADVISORY_READY, LeadState.HIGH_LEVERAGE)

    def test_backward_transitions_blocked(self):
        """Backward transitions should be blocked."""
        assert not can_transition(LeadState.CURIOUS, LeadState.BROWSING)
        assert not can_transition(LeadState.EVALUATING, LeadState.CURIOUS)
        assert not can_transition(LeadState.EVALUATING, LeadState.BROWSING)
        assert not can_transition(LeadState.ADVISORY_READY, LeadState.EVALUATING)
        assert not can_transition(LeadState.HIGH_LEVERAGE, LeadState.ADVISORY_READY)

    def test_same_state_transition_blocked(self):
        """Transition to same state should be blocked."""
        for state in LeadState:
            assert not can_transition(state, state)

    def test_high_leverage_is_terminal(self):
        """HIGH_LEVERAGE has no valid outgoing transitions."""
        for state in LeadState:
            if state != LeadState.HIGH_LEVERAGE:
                assert not can_transition(LeadState.HIGH_LEVERAGE, state)


# =============================================================================
# SIGNAL TESTS
# =============================================================================

class TestSignals:
    """Test signal definitions and catalog."""

    def test_signal_catalog_complete(self):
        """All signals should be in catalog."""
        # Check discovery signals
        assert DiscoverySignal.VIEWED_OUTCOME.signal_id in SIGNAL_CATALOG
        assert DiscoverySignal.EXPANDED_DRIVERS.signal_id in SIGNAL_CATALOG

        # Check evaluation signals
        assert EvaluationSignal.COMPARED_SCENARIOS.signal_id in SIGNAL_CATALOG
        assert EvaluationSignal.DOWNLOADED_SUMMARY.signal_id in SIGNAL_CATALOG

        # Check commitment signals
        assert CommitmentSignal.REQUESTED_CPA_REVIEW.signal_id in SIGNAL_CATALOG
        assert CommitmentSignal.COMPLEX_SITUATION.signal_id in SIGNAL_CATALOG

    def test_get_signal_by_id(self):
        """Should retrieve signal by ID."""
        signal = get_signal("discovery.viewed_outcome")
        assert signal is not None
        assert signal.signal_type == SignalType.DISCOVERY

    def test_get_signals_by_type(self):
        """Should filter signals by type."""
        discovery = get_signals_by_type(SignalType.DISCOVERY)
        assert len(discovery) > 0
        assert all(s.signal_type == SignalType.DISCOVERY for s in discovery)

        commitment = get_signals_by_type(SignalType.COMMITMENT)
        assert len(commitment) > 0
        assert all(s.signal_type == SignalType.COMMITMENT for s in commitment)

    def test_signal_strength_ordering(self):
        """Signal strengths should be ordered."""
        assert SignalStrength.WEAK < SignalStrength.MODERATE
        assert SignalStrength.MODERATE < SignalStrength.STRONG
        assert SignalStrength.STRONG < SignalStrength.GOLD

    def test_signal_immutability(self):
        """Signals should be immutable."""
        signal = DiscoverySignal.VIEWED_OUTCOME
        with pytest.raises((AttributeError, TypeError)):
            signal.name = "Modified"


# =============================================================================
# ENGINE TESTS
# =============================================================================

class TestLeadStateEngine:
    """Test lead state engine behavior."""

    @pytest.fixture
    def engine(self):
        """Create fresh engine for each test."""
        return LeadStateEngine()

    def test_create_new_lead(self, engine):
        """Should create new lead in BROWSING state."""
        lead = engine.get_or_create_lead(
            lead_id="lead-1",
            session_id="session-1",
            tenant_id="tenant-1",
        )

        assert lead.lead_id == "lead-1"
        assert lead.session_id == "session-1"
        assert lead.current_state == LeadState.BROWSING
        assert len(lead.signals_received) == 0

    def test_get_existing_lead(self, engine):
        """Should return existing lead."""
        engine.get_or_create_lead("lead-1", "session-1")
        lead = engine.get_lead("lead-1")

        assert lead is not None
        assert lead.lead_id == "lead-1"

    def test_process_discovery_signal(self, engine):
        """Processing discovery signals should accumulate."""
        lead = engine.process_signal(
            lead_id="lead-1",
            signal_id="discovery.viewed_outcome",
            session_id="session-1",
        )

        assert "discovery.viewed_outcome" in lead.signals_received
        assert lead.signal_count == 1

    def test_discovery_threshold_advances_to_curious(self, engine):
        """3 discovery signals should advance to CURIOUS."""
        # Send 3 discovery signals
        engine.process_signal("lead-1", "discovery.viewed_outcome", session_id="s1")
        engine.process_signal("lead-1", "discovery.expanded_drivers")
        lead = engine.process_signal("lead-1", "discovery.viewed_complexity")

        assert lead.current_state == LeadState.CURIOUS
        assert len(lead.transitions) == 1

    def test_evaluation_signal_advances_to_evaluating(self, engine):
        """Evaluation signals should advance to EVALUATING."""
        # First get to CURIOUS
        engine.process_signal("lead-1", "discovery.viewed_outcome", session_id="s1")
        engine.process_signal("lead-1", "discovery.expanded_drivers")
        engine.process_signal("lead-1", "discovery.viewed_complexity")

        # Now evaluation signals
        engine.process_signal("lead-1", "evaluation.compared_scenarios")
        lead = engine.process_signal("lead-1", "evaluation.viewed_opportunities")

        assert lead.current_state == LeadState.EVALUATING

    def test_commitment_signal_advances_to_advisory_ready(self, engine):
        """Commitment signal should advance to ADVISORY_READY."""
        lead = engine.process_signal(
            lead_id="lead-1",
            signal_id="commitment.requested_cpa_review",
            session_id="session-1",
        )

        assert lead.current_state == LeadState.ADVISORY_READY
        assert lead.is_monetizable

    def test_high_leverage_signals_advance_directly(self, engine):
        """High-leverage signals should advance directly to HIGH_LEVERAGE."""
        lead = engine.process_signal(
            lead_id="lead-1",
            signal_id="commitment.complex_situation",
            session_id="session-1",
        )

        assert lead.current_state == LeadState.HIGH_LEVERAGE
        assert lead.is_priority

    def test_business_owner_is_high_leverage(self, engine):
        """Business owner signal should trigger HIGH_LEVERAGE."""
        lead = engine.process_signal(
            lead_id="lead-1",
            signal_id="commitment.business_owner",
            session_id="session-1",
        )

        assert lead.current_state == LeadState.HIGH_LEVERAGE

    def test_high_income_is_high_leverage(self, engine):
        """High income signal should trigger HIGH_LEVERAGE."""
        lead = engine.process_signal(
            lead_id="lead-1",
            signal_id="commitment.high_income",
            session_id="session-1",
        )

        assert lead.current_state == LeadState.HIGH_LEVERAGE


# =============================================================================
# FORWARD-ONLY ENFORCEMENT TESTS
# =============================================================================

class TestForwardOnlyEnforcement:
    """Test that backward transitions are blocked."""

    @pytest.fixture
    def engine(self):
        return LeadStateEngine()

    def test_cannot_regress_from_curious(self, engine):
        """Lead in CURIOUS cannot go back to BROWSING."""
        # Advance to CURIOUS
        engine.process_signal("lead-1", "discovery.viewed_outcome", session_id="s1")
        engine.process_signal("lead-1", "discovery.expanded_drivers")
        engine.process_signal("lead-1", "discovery.viewed_complexity")

        lead = engine.get_lead("lead-1")
        assert lead.current_state == LeadState.CURIOUS

        # More discovery signals should not regress state
        engine.process_signal("lead-1", "discovery.returned_session")
        assert lead.current_state == LeadState.CURIOUS

    def test_cannot_regress_from_advisory_ready(self, engine):
        """Lead in ADVISORY_READY cannot regress."""
        # Advance to ADVISORY_READY
        engine.process_signal(
            "lead-1",
            "commitment.requested_cpa_review",
            session_id="s1",
        )

        lead = engine.get_lead("lead-1")
        assert lead.current_state == LeadState.ADVISORY_READY

        # Discovery signals should not regress
        engine.process_signal("lead-1", "discovery.viewed_outcome")
        assert lead.current_state == LeadState.ADVISORY_READY

    def test_high_leverage_is_terminal(self, engine):
        """HIGH_LEVERAGE lead stays in HIGH_LEVERAGE."""
        engine.process_signal(
            "lead-1",
            "commitment.complex_situation",
            session_id="s1",
        )

        lead = engine.get_lead("lead-1")
        assert lead.current_state == LeadState.HIGH_LEVERAGE

        # More signals should not change state
        engine.process_signal("lead-1", "discovery.viewed_outcome")
        engine.process_signal("lead-1", "evaluation.compared_scenarios")
        engine.process_signal("lead-1", "commitment.requested_cpa_review")

        assert lead.current_state == LeadState.HIGH_LEVERAGE


# =============================================================================
# LEAD RECORD TESTS
# =============================================================================

class TestLeadRecord:
    """Test lead record properties."""

    def test_new_lead_properties(self):
        """New lead should have correct default properties."""
        lead = LeadRecord(
            lead_id="lead-1",
            session_id="session-1",
        )

        assert lead.current_state == LeadState.BROWSING
        assert lead.visibility == CPAVisibility.HIDDEN
        assert not lead.is_monetizable
        assert not lead.is_visible_to_cpa
        assert not lead.is_priority
        assert lead.signal_count == 0

    def test_lead_to_dict(self):
        """Lead should serialize to dict."""
        lead = LeadRecord(
            lead_id="lead-1",
            session_id="session-1",
            tenant_id="tenant-1",
        )

        d = lead.to_dict()

        assert d["lead_id"] == "lead-1"
        assert d["session_id"] == "session-1"
        assert d["current_state"] == "BROWSING"
        assert d["visibility"] == "hidden"
        assert d["is_monetizable"] is False


# =============================================================================
# QUEUE SUMMARY TESTS
# =============================================================================

class TestQueueSummary:
    """Test CPA queue summary functionality."""

    @pytest.fixture
    def engine_with_leads(self):
        """Create engine with leads in various states."""
        engine = LeadStateEngine()

        # 2 browsing (no signals)
        engine.get_or_create_lead("b1", "s1")
        engine.get_or_create_lead("b2", "s2")

        # 2 curious (discovery threshold)
        for i in range(3):
            engine.process_signal("c1", f"discovery.viewed_outcome", session_id="s3")
        for i in range(3):
            engine.process_signal("c2", f"discovery.expanded_drivers", session_id="s4")

        # 1 evaluating
        engine.process_signal("e1", "evaluation.compared_scenarios", session_id="s5")
        engine.process_signal("e1", "evaluation.viewed_opportunities")

        # 2 advisory-ready
        engine.process_signal("a1", "commitment.requested_cpa_review", session_id="s6")
        engine.process_signal("a2", "commitment.provided_contact", session_id="s7")

        # 1 high-leverage
        engine.process_signal("h1", "commitment.complex_situation", session_id="s8")

        return engine

    def test_state_counts(self, engine_with_leads):
        """Should return correct state counts."""
        counts = engine_with_leads.get_state_counts()

        assert counts["BROWSING"] == 2
        assert counts["CURIOUS"] == 2
        assert counts["EVALUATING"] == 1
        assert counts["ADVISORY_READY"] == 2
        assert counts["HIGH_LEVERAGE"] == 1

    def test_queue_summary(self, engine_with_leads):
        """Should return correct queue summary."""
        summary = engine_with_leads.get_queue_summary()

        assert summary["total_leads"] == 8
        assert summary["visible_count"] == 4  # EVALUATING + ADVISORY_READY + HIGH_LEVERAGE
        assert summary["monetizable_count"] == 3  # ADVISORY_READY + HIGH_LEVERAGE
        assert summary["priority_count"] == 1  # HIGH_LEVERAGE only
        assert summary["hidden_count"] == 4  # BROWSING + CURIOUS

    def test_get_visible_leads(self, engine_with_leads):
        """Should return only visible leads."""
        visible = engine_with_leads.get_visible_leads()

        assert len(visible) == 4
        assert all(l.is_visible_to_cpa for l in visible)

    def test_get_monetizable_leads(self, engine_with_leads):
        """Should return only monetizable leads."""
        monetizable = engine_with_leads.get_monetizable_leads()

        assert len(monetizable) == 3
        assert all(l.is_monetizable for l in monetizable)

    def test_get_priority_leads(self, engine_with_leads):
        """Should return only priority leads."""
        priority = engine_with_leads.get_priority_leads()

        assert len(priority) == 1
        assert all(l.is_priority for l in priority)


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error handling."""

    @pytest.fixture
    def engine(self):
        return LeadStateEngine()

    def test_invalid_signal_raises_error(self, engine):
        """Invalid signal ID should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            engine.process_signal(
                "lead-1",
                "invalid.signal",
                session_id="s1",
            )

        assert "Unknown signal" in str(exc_info.value)

    def test_missing_session_id_raises_error(self, engine):
        """New lead without session_id should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            engine.process_signal(
                "lead-1",
                "discovery.viewed_outcome",
                # No session_id
            )

        assert "session_id required" in str(exc_info.value)

    def test_force_backward_transition_raises_error(self, engine):
        """Forcing backward transition should raise TransitionError."""
        # Advance to ADVISORY_READY
        engine.process_signal(
            "lead-1",
            "commitment.requested_cpa_review",
            session_id="s1",
        )

        with pytest.raises(TransitionError) as exc_info:
            engine.force_transition(
                "lead-1",
                LeadState.BROWSING,
                "test",
            )

        assert "Cannot transition backwards" in str(exc_info.value)


# =============================================================================
# TRANSITION HISTORY TESTS
# =============================================================================

class TestTransitionHistory:
    """Test transition history tracking."""

    @pytest.fixture
    def engine(self):
        return LeadStateEngine()

    def test_transitions_tracked(self, engine):
        """State transitions should be recorded."""
        # Advance through multiple states
        engine.process_signal("lead-1", "discovery.viewed_outcome", session_id="s1")
        engine.process_signal("lead-1", "discovery.expanded_drivers")
        engine.process_signal("lead-1", "discovery.viewed_complexity")  # → CURIOUS

        engine.process_signal("lead-1", "evaluation.compared_scenarios")
        engine.process_signal("lead-1", "evaluation.viewed_opportunities")  # → EVALUATING

        engine.process_signal("lead-1", "commitment.requested_cpa_review")  # → ADVISORY_READY

        lead = engine.get_lead("lead-1")

        assert len(lead.transitions) == 3
        assert lead.transitions[0].from_state == LeadState.BROWSING
        assert lead.transitions[0].to_state == LeadState.CURIOUS
        assert lead.transitions[1].to_state == LeadState.EVALUATING
        assert lead.transitions[2].to_state == LeadState.ADVISORY_READY

    def test_transition_has_trigger_signal(self, engine):
        """Transitions should record trigger signal."""
        engine.process_signal(
            "lead-1",
            "commitment.complex_situation",
            session_id="s1",
        )

        lead = engine.get_lead("lead-1")
        transition = lead.transitions[0]

        assert transition.trigger_signal.signal_id == "commitment.complex_situation"

    def test_transition_has_timestamp(self, engine):
        """Transitions should have timestamps."""
        engine.process_signal(
            "lead-1",
            "commitment.requested_cpa_review",
            session_id="s1",
        )

        lead = engine.get_lead("lead-1")
        transition = lead.transitions[0]

        assert isinstance(transition.timestamp, datetime)
