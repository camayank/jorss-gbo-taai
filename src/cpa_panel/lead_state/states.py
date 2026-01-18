"""
Lead States and Enumerations

Defines the 5 lead states and their properties.
States are categorical, not scored - this is intentional.
"""

from enum import Enum, IntEnum
from typing import Dict, Set


class LeadState(IntEnum):
    """
    Lead readiness states - ordered by engagement level.

    IntEnum allows comparison: ADVISORY_READY > EVALUATING
    Forward-only transitions: state can only increase, never decrease.
    """
    BROWSING = 1        # Hidden from CPA - noise filtering
    CURIOUS = 2         # Aggregated counts only - awareness
    EVALUATING = 3      # Passive visibility - optional follow-up
    ADVISORY_READY = 4  # First monetizable state - CPA engages
    HIGH_LEVERAGE = 5   # Priority state - CPA prioritizes

    @property
    def display_name(self) -> str:
        """Human-readable state name."""
        names = {
            LeadState.BROWSING: "Browsing",
            LeadState.CURIOUS: "Curious",
            LeadState.EVALUATING: "Evaluating",
            LeadState.ADVISORY_READY: "Advisory-Ready ⭐",
            LeadState.HIGH_LEVERAGE: "High-Leverage 🔥",
        }
        return names[self]

    @property
    def is_monetizable(self) -> bool:
        """Whether this state represents a monetizable lead."""
        return self >= LeadState.ADVISORY_READY

    @property
    def is_visible_to_cpa(self) -> bool:
        """Whether individual leads in this state are visible to CPA."""
        return self >= LeadState.EVALUATING

    @property
    def is_priority(self) -> bool:
        """Whether this state warrants priority attention."""
        return self == LeadState.HIGH_LEVERAGE


class SignalType(str, Enum):
    """
    Categories of prospect behavior signals.

    Signals are classified by what they reveal about prospect intent.
    """
    DISCOVERY = "discovery"       # Weak: exploring, no commitment
    EVALUATION = "evaluation"     # Attention: comparing, considering
    COMMITMENT = "commitment"     # Gold: ready to engage


class SignalStrength(IntEnum):
    """
    Signal strength for transition weight calculation.

    Higher strength signals have more impact on state transitions.
    """
    WEAK = 1        # Minor interest indicator
    MODERATE = 2    # Clear interest indicator
    STRONG = 3      # High intent indicator
    GOLD = 4        # Commitment indicator


class CPAVisibility(str, Enum):
    """
    CPA visibility levels for leads in different states.
    """
    HIDDEN = "hidden"               # Not shown at all (BROWSING)
    AGGREGATE_ONLY = "aggregate"    # Only in counts (CURIOUS)
    PASSIVE = "passive"             # Visible but not highlighted (EVALUATING)
    ACTIVE = "active"               # Highlighted for engagement (ADVISORY_READY)
    PRIORITY = "priority"           # Top of queue (HIGH_LEVERAGE)


# State → Visibility mapping
STATE_VISIBILITY: Dict[LeadState, CPAVisibility] = {
    LeadState.BROWSING: CPAVisibility.HIDDEN,
    LeadState.CURIOUS: CPAVisibility.AGGREGATE_ONLY,
    LeadState.EVALUATING: CPAVisibility.PASSIVE,
    LeadState.ADVISORY_READY: CPAVisibility.ACTIVE,
    LeadState.HIGH_LEVERAGE: CPAVisibility.PRIORITY,
}


# Valid state transitions (forward-only)
VALID_TRANSITIONS: Dict[LeadState, Set[LeadState]] = {
    LeadState.BROWSING: {LeadState.CURIOUS, LeadState.EVALUATING, LeadState.ADVISORY_READY, LeadState.HIGH_LEVERAGE},
    LeadState.CURIOUS: {LeadState.EVALUATING, LeadState.ADVISORY_READY, LeadState.HIGH_LEVERAGE},
    LeadState.EVALUATING: {LeadState.ADVISORY_READY, LeadState.HIGH_LEVERAGE},
    LeadState.ADVISORY_READY: {LeadState.HIGH_LEVERAGE},
    LeadState.HIGH_LEVERAGE: set(),  # Terminal state - no further transitions
}


def get_visibility(state: LeadState) -> CPAVisibility:
    """Get CPA visibility level for a lead state."""
    return STATE_VISIBILITY[state]


def can_transition(from_state: LeadState, to_state: LeadState) -> bool:
    """Check if a state transition is valid (forward-only)."""
    return to_state in VALID_TRANSITIONS.get(from_state, set())


# =============================================================================
# P2: LEAD ASSIGNMENT/OWNERSHIP
# =============================================================================

class AssignmentStatus(str, Enum):
    """Lead assignment status for CPA ownership tracking."""
    UNASSIGNED = "unassigned"          # No CPA assigned
    ASSIGNED = "assigned"               # Assigned to a CPA
    ACCEPTED = "accepted"               # CPA accepted the lead
    IN_PROGRESS = "in_progress"         # CPA actively working
    CONVERTED = "converted"             # Lead became a client
    DECLINED = "declined"               # CPA declined the lead
    REASSIGNED = "reassigned"           # Reassigned to different CPA


class AssignmentPriority(IntEnum):
    """Lead priority for assignment queue ordering."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


# Priority mapping based on state and financial indicators
def get_assignment_priority(state: LeadState, has_financial_indicators: bool = False) -> AssignmentPriority:
    """
    Get assignment priority based on lead state and indicators.

    High-leverage leads and those with financial indicators get higher priority.
    """
    if state == LeadState.HIGH_LEVERAGE:
        return AssignmentPriority.URGENT if has_financial_indicators else AssignmentPriority.HIGH
    elif state == LeadState.ADVISORY_READY:
        return AssignmentPriority.HIGH if has_financial_indicators else AssignmentPriority.NORMAL
    elif state == LeadState.EVALUATING:
        return AssignmentPriority.NORMAL if has_financial_indicators else AssignmentPriority.LOW
    else:
        return AssignmentPriority.LOW
