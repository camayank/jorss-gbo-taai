"""
Lead State Engine

Core engine for processing signals and managing lead state transitions.
Implements forward-only state machine with signal accumulation.

Supports optional database persistence via LeadStatePersistence.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Set, Any, TYPE_CHECKING
import logging

from .states import (
    LeadState,
    SignalStrength,
    CPAVisibility,
    STATE_VISIBILITY,
    can_transition,
    VALID_TRANSITIONS,
)
from .signals import LeadSignal, SignalType, SIGNAL_CATALOG, get_signal

if TYPE_CHECKING:
    from src.database.lead_state_persistence import LeadStatePersistence

logger = logging.getLogger(__name__)


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: LeadState
    to_state: LeadState
    trigger_signal: LeadSignal
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_state": self.from_state.name,
            "to_state": self.to_state.name,
            "trigger_signal": self.trigger_signal.signal_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class LeadRecord:
    """
    Complete lead record with state and signal history.

    Immutable state progression - once advanced, cannot regress.
    """
    lead_id: str
    session_id: str
    tenant_id: str = "default"
    current_state: LeadState = LeadState.BROWSING
    signals_received: List[str] = field(default_factory=list)
    transitions: List[StateTransition] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def visibility(self) -> CPAVisibility:
        """Get CPA visibility for this lead."""
        return STATE_VISIBILITY[self.current_state]

    @property
    def is_monetizable(self) -> bool:
        """Whether this lead is in a monetizable state."""
        return self.current_state.is_monetizable

    @property
    def is_visible_to_cpa(self) -> bool:
        """Whether this lead is visible to CPA."""
        return self.current_state.is_visible_to_cpa

    @property
    def is_priority(self) -> bool:
        """Whether this lead is priority."""
        return self.current_state.is_priority

    @property
    def signal_count(self) -> int:
        """Total signals received."""
        return len(self.signals_received)

    @property
    def unique_signals(self) -> Set[str]:
        """Unique signal IDs received."""
        return set(self.signals_received)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lead_id": self.lead_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "current_state": self.current_state.name,
            "state_display": self.current_state.display_name,
            "visibility": self.visibility.value,
            "is_monetizable": self.is_monetizable,
            "is_priority": self.is_priority,
            "signal_count": self.signal_count,
            "unique_signals": list(self.unique_signals),
            "transitions": [t.to_dict() for t in self.transitions],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class LeadStateEngine:
    """
    Engine for processing signals and managing lead state transitions.

    Thread-safe for concurrent signal processing.
    Forward-only state progression.

    Supports optional database persistence. When persistence is provided,
    leads are stored durably in SQLite. Without persistence, leads are
    stored in-memory only.
    """

    # Thresholds for automatic state advancement
    DISCOVERY_THRESHOLD = 3      # 3 discovery signals → CURIOUS
    EVALUATION_THRESHOLD = 2     # 2 evaluation signals → EVALUATING
    COMMITMENT_THRESHOLD = 1     # 1 commitment signal → ADVISORY_READY
    HIGH_LEVERAGE_SIGNALS = {    # Any of these → HIGH_LEVERAGE
        "commitment.complex_situation",
        "commitment.high_income",
        "commitment.business_owner",
        "commitment.urgency_indicated",
    }

    def __init__(self, persistence: Optional["LeadStatePersistence"] = None):
        """
        Initialize the engine.

        Args:
            persistence: Optional persistence layer for durable storage.
                        If None, leads are stored in-memory only.
        """
        self._leads: Dict[str, LeadRecord] = {}
        self._persistence = persistence

    def get_or_create_lead(
        self,
        lead_id: str,
        session_id: str,
        tenant_id: str = "default",
    ) -> LeadRecord:
        """Get existing lead or create new one."""
        # Check in-memory cache first
        if lead_id in self._leads:
            return self._leads[lead_id]

        # Check persistence if available
        if self._persistence:
            db_lead = self._persistence.load_lead(lead_id, tenant_id)
            if db_lead:
                # Restore from database
                lead = self._restore_lead_from_db(db_lead)
                self._leads[lead_id] = lead
                return lead

        # Create new lead
        lead = LeadRecord(
            lead_id=lead_id,
            session_id=session_id,
            tenant_id=tenant_id,
        )
        self._leads[lead_id] = lead

        # Persist if available
        if self._persistence:
            self._persistence.save_lead(
                lead_id=lead_id,
                session_id=session_id,
                tenant_id=tenant_id,
                current_state=lead.current_state.name,
            )

        return lead

    def get_lead(self, lead_id: str, tenant_id: Optional[str] = None) -> Optional[LeadRecord]:
        """Get lead by ID."""
        # Check in-memory cache first
        if lead_id in self._leads:
            cached_lead = self._leads[lead_id]
            # If tenant filter provided, verify it matches
            if tenant_id is None or cached_lead.tenant_id == tenant_id:
                return cached_lead
            # Tenant mismatch - don't return cached lead
            return None

        # Check persistence if available
        if self._persistence:
            db_lead = self._persistence.load_lead(lead_id, tenant_id)
            if db_lead:
                lead = self._restore_lead_from_db(db_lead)
                self._leads[lead_id] = lead
                return lead

        return None

    def _restore_lead_from_db(self, db_lead) -> LeadRecord:
        """Restore a LeadRecord from database record."""
        # Get signals and transitions from DB
        signals = []
        transitions = []

        if self._persistence:
            signal_ids = self._persistence.get_signal_ids_for_lead(db_lead.lead_id)
            signals = signal_ids

            db_transitions = self._persistence.get_transitions_for_lead(db_lead.lead_id)
            for t in db_transitions:
                trigger_signal = get_signal(t.trigger_signal_id)
                if not trigger_signal:
                    # Create synthetic signal for unknown triggers
                    trigger_signal = LeadSignal(
                        signal_id=t.trigger_signal_id,
                        name=t.trigger_signal_id,
                        signal_type=SignalType.COMMITMENT,
                        strength=SignalStrength.GOLD,
                        description="Restored transition trigger",
                        minimum_state_for=LeadState[t.to_state],
                    )
                transitions.append(StateTransition(
                    from_state=LeadState[t.from_state],
                    to_state=LeadState[t.to_state],
                    trigger_signal=trigger_signal,
                    timestamp=datetime.fromisoformat(t.timestamp),
                    metadata=t.metadata,
                ))

        return LeadRecord(
            lead_id=db_lead.lead_id,
            session_id=db_lead.session_id,
            tenant_id=db_lead.tenant_id,
            current_state=LeadState[db_lead.current_state],
            signals_received=signals,
            transitions=transitions,
            created_at=datetime.fromisoformat(db_lead.created_at),
            updated_at=datetime.fromisoformat(db_lead.updated_at),
            metadata=db_lead.metadata,
        )

    def process_signal(
        self,
        lead_id: str,
        signal_id: str,
        session_id: Optional[str] = None,
        tenant_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LeadRecord:
        """
        Process a signal for a lead.

        Args:
            lead_id: Lead identifier
            signal_id: Signal identifier from catalog
            session_id: Session identifier (required if new lead)
            tenant_id: Tenant identifier
            metadata: Optional metadata for the signal

        Returns:
            Updated LeadRecord

        Raises:
            ValueError: If signal_id is invalid
            TransitionError: If transition fails
        """
        signal = get_signal(signal_id)
        if not signal:
            raise ValueError(f"Unknown signal: {signal_id}")

        # Get or create lead
        lead = self._leads.get(lead_id)
        if not lead:
            # Try to load from persistence
            if self._persistence:
                db_lead = self._persistence.load_lead(lead_id, tenant_id)
                if db_lead:
                    lead = self._restore_lead_from_db(db_lead)
                    self._leads[lead_id] = lead

        if not lead:
            if not session_id:
                raise ValueError("session_id required for new lead")
            lead = LeadRecord(
                lead_id=lead_id,
                session_id=session_id,
                tenant_id=tenant_id,
            )
            self._leads[lead_id] = lead

            # Persist new lead
            if self._persistence:
                self._persistence.save_lead(
                    lead_id=lead_id,
                    session_id=session_id,
                    tenant_id=tenant_id,
                    current_state=lead.current_state.name,
                )

        # Record signal
        lead.signals_received.append(signal_id)
        lead.updated_at = datetime.utcnow()

        # Persist signal
        if self._persistence:
            self._persistence.save_signal(
                lead_id=lead_id,
                signal_id=signal_id,
                tenant_id=tenant_id,
                metadata=metadata,
            )

        # Evaluate state transition
        new_state = self._evaluate_transition(lead, signal)

        if new_state and new_state > lead.current_state:
            self._apply_transition(lead, new_state, signal, metadata)

        return lead

    def _evaluate_transition(
        self,
        lead: LeadRecord,
        signal: LeadSignal,
    ) -> Optional[LeadState]:
        """
        Evaluate whether a signal should trigger a state transition.

        Returns the target state if transition should occur, None otherwise.
        """
        current = lead.current_state

        # Check if this signal directly qualifies for high-leverage
        if signal.signal_id in self.HIGH_LEVERAGE_SIGNALS:
            if can_transition(current, LeadState.HIGH_LEVERAGE):
                return LeadState.HIGH_LEVERAGE

        # Check signal's minimum state
        if signal.minimum_state_for > current:
            if can_transition(current, signal.minimum_state_for):
                return signal.minimum_state_for

        # Check accumulated signals for threshold-based transitions
        return self._check_thresholds(lead)

    def _check_thresholds(self, lead: LeadRecord) -> Optional[LeadState]:
        """Check if accumulated signals meet any threshold."""
        current = lead.current_state
        signals = lead.signals_received

        # Count signals by type
        discovery_count = sum(
            1 for s in signals
            if s.startswith("discovery.")
        )
        evaluation_count = sum(
            1 for s in signals
            if s.startswith("evaluation.")
        )
        commitment_count = sum(
            1 for s in signals
            if s.startswith("commitment.")
        )

        # Check thresholds in reverse order (highest first)
        if commitment_count >= self.COMMITMENT_THRESHOLD:
            if current < LeadState.ADVISORY_READY:
                if can_transition(current, LeadState.ADVISORY_READY):
                    return LeadState.ADVISORY_READY

        if evaluation_count >= self.EVALUATION_THRESHOLD:
            if current < LeadState.EVALUATING:
                if can_transition(current, LeadState.EVALUATING):
                    return LeadState.EVALUATING

        if discovery_count >= self.DISCOVERY_THRESHOLD:
            if current < LeadState.CURIOUS:
                if can_transition(current, LeadState.CURIOUS):
                    return LeadState.CURIOUS

        return None

    def _apply_transition(
        self,
        lead: LeadRecord,
        new_state: LeadState,
        trigger_signal: LeadSignal,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Apply a state transition to a lead."""
        if new_state <= lead.current_state:
            raise TransitionError(
                f"Cannot transition backwards: {lead.current_state.name} → {new_state.name}"
            )

        if not can_transition(lead.current_state, new_state):
            raise TransitionError(
                f"Invalid transition: {lead.current_state.name} → {new_state.name}"
            )

        old_state = lead.current_state

        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            trigger_signal=trigger_signal,
            metadata=metadata or {},
        )

        lead.transitions.append(transition)
        lead.current_state = new_state
        lead.updated_at = datetime.utcnow()

        # Persist transition and updated lead state
        if self._persistence:
            self._persistence.save_transition(
                lead_id=lead.lead_id,
                from_state=old_state.name,
                to_state=new_state.name,
                trigger_signal_id=trigger_signal.signal_id,
                metadata=metadata,
            )
            self._persistence.save_lead(
                lead_id=lead.lead_id,
                session_id=lead.session_id,
                tenant_id=lead.tenant_id,
                current_state=new_state.name,
                metadata=lead.metadata,
            )

        logger.info(
            f"Lead {lead.lead_id} transitioned: "
            f"{transition.from_state.name} → {transition.to_state.name} "
            f"(trigger: {trigger_signal.signal_id})"
        )

    def force_transition(
        self,
        lead_id: str,
        target_state: LeadState,
        reason: str,
    ) -> LeadRecord:
        """
        Force a state transition (for CPA manual override).

        Only allows forward transitions.
        """
        lead = self._leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead not found: {lead_id}")

        if target_state <= lead.current_state:
            raise TransitionError(
                f"Cannot transition backwards: {lead.current_state.name} → {target_state.name}"
            )

        # Create a synthetic signal for the forced transition
        synthetic_signal = LeadSignal(
            signal_id=f"forced.{reason}",
            name=f"Forced: {reason}",
            signal_type=SignalType.COMMITMENT,
            strength=SignalStrength.GOLD,
            description=f"CPA forced transition: {reason}",
            minimum_state_for=target_state,
        )

        self._apply_transition(
            lead,
            target_state,
            synthetic_signal,
            {"forced": True, "reason": reason},
        )

        return lead

    def _load_all_leads_for_tenant(self, tenant_id: str) -> None:
        """Load all leads for a tenant from persistence into cache."""
        if not self._persistence:
            return

        db_leads = self._persistence.list_leads(tenant_id=tenant_id, limit=1000)
        for db_lead in db_leads:
            if db_lead.lead_id not in self._leads:
                lead = self._restore_lead_from_db(db_lead)
                self._leads[db_lead.lead_id] = lead

    def get_leads_by_state(
        self,
        state: LeadState,
        tenant_id: Optional[str] = None,
    ) -> List[LeadRecord]:
        """Get all leads in a specific state."""
        # Load from persistence if available
        if self._persistence and tenant_id:
            db_leads = self._persistence.list_leads_by_state(
                state=state.name,
                tenant_id=tenant_id,
            )
            result = []
            for db_lead in db_leads:
                if db_lead.lead_id in self._leads:
                    result.append(self._leads[db_lead.lead_id])
                else:
                    lead = self._restore_lead_from_db(db_lead)
                    self._leads[db_lead.lead_id] = lead
                    result.append(lead)
            return result

        # Fall back to in-memory
        leads = list(self._leads.values())
        if tenant_id:
            leads = [l for l in leads if l.tenant_id == tenant_id]
        return [l for l in leads if l.current_state == state]

    def get_visible_leads(
        self,
        tenant_id: Optional[str] = None,
    ) -> List[LeadRecord]:
        """Get all leads visible to CPA (EVALUATING and above)."""
        # Load from persistence if available
        if self._persistence and tenant_id:
            self._load_all_leads_for_tenant(tenant_id)

        leads = list(self._leads.values())
        if tenant_id:
            leads = [l for l in leads if l.tenant_id == tenant_id]
        return [l for l in leads if l.is_visible_to_cpa]

    def get_monetizable_leads(
        self,
        tenant_id: Optional[str] = None,
    ) -> List[LeadRecord]:
        """Get all monetizable leads (ADVISORY_READY and above)."""
        # Load from persistence if available
        if self._persistence and tenant_id:
            self._load_all_leads_for_tenant(tenant_id)

        leads = list(self._leads.values())
        if tenant_id:
            leads = [l for l in leads if l.tenant_id == tenant_id]
        return [l for l in leads if l.is_monetizable]

    def get_priority_leads(
        self,
        tenant_id: Optional[str] = None,
    ) -> List[LeadRecord]:
        """Get priority leads (HIGH_LEVERAGE only)."""
        # Load from persistence if available
        if self._persistence and tenant_id:
            self._load_all_leads_for_tenant(tenant_id)

        leads = list(self._leads.values())
        if tenant_id:
            leads = [l for l in leads if l.tenant_id == tenant_id]
        return [l for l in leads if l.is_priority]

    def get_state_counts(
        self,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """Get count of leads in each state."""
        # Use persistence directly if available (more efficient)
        if self._persistence and tenant_id:
            return self._persistence.get_state_counts(tenant_id)

        leads = list(self._leads.values())
        if tenant_id:
            leads = [l for l in leads if l.tenant_id == tenant_id]

        counts = {state.name: 0 for state in LeadState}
        for lead in leads:
            counts[lead.current_state.name] += 1

        return counts

    def get_queue_summary(
        self,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get summary for CPA queue display."""
        counts = self.get_state_counts(tenant_id)

        return {
            "total_leads": sum(counts.values()),
            "state_counts": counts,
            "visible_count": counts.get("EVALUATING", 0) +
                           counts.get("ADVISORY_READY", 0) +
                           counts.get("HIGH_LEVERAGE", 0),
            "monetizable_count": counts.get("ADVISORY_READY", 0) +
                                counts.get("HIGH_LEVERAGE", 0),
            "priority_count": counts.get("HIGH_LEVERAGE", 0),
            "hidden_count": counts.get("BROWSING", 0) +
                          counts.get("CURIOUS", 0),
        }
