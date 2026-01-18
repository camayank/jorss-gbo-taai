"""
Lead State Engine

State-based lead qualification system for CPA panel.
Uses forward-only state transitions based on prospect behavior signals,
NOT scoring algorithms.

Design Principles:
- States, not scores: Clear categorical states instead of opaque numbers
- Forward-only: Once a prospect advances, they don't regress
- Signal-driven: Behavior signals trigger state transitions
- CPA control: States determine visibility, CPA decides engagement

States:
1. BROWSING     - Hidden from CPA (noise filtering)
2. CURIOUS      - Aggregated counts only (awareness)
3. EVALUATING   - Passive visibility (optional follow-up)
4. ADVISORY_READY ⭐ - First monetizable state (CPA engages)
5. HIGH_LEVERAGE 🔥 - Priority state (CPA prioritizes)
"""

from .states import (
    LeadState,
    SignalType,
    SignalStrength,
    CPAVisibility,
    VALID_TRANSITIONS,
)

from .signals import (
    LeadSignal,
    DiscoverySignal,
    EvaluationSignal,
    CommitmentSignal,
    SIGNAL_CATALOG,
)

from .engine import (
    LeadStateEngine,
    StateTransition,
    LeadRecord,
    TransitionError,
)

__all__ = [
    # States and enums
    "LeadState",
    "SignalType",
    "SignalStrength",
    "CPAVisibility",
    "VALID_TRANSITIONS",
    # Signals
    "LeadSignal",
    "DiscoverySignal",
    "EvaluationSignal",
    "CommitmentSignal",
    "SIGNAL_CATALOG",
    # Engine
    "LeadStateEngine",
    "StateTransition",
    "LeadRecord",
    "TransitionError",
]
