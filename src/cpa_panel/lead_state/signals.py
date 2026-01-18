"""
Lead Signals

Defines the specific behavioral signals that indicate prospect intent
and drive state transitions.

Signal Classifications:
- Discovery (Weak): Viewing, browsing, time spent
- Evaluation (Attention): Comparing, downloading, engaging
- Commitment (Gold): Requesting review, hitting locks, detailed answers
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

from .states import SignalType, SignalStrength, LeadState


@dataclass(frozen=True)
class LeadSignal:
    """
    Base signal definition.

    Immutable to ensure signal catalog integrity.
    """
    signal_id: str
    name: str
    signal_type: SignalType
    strength: SignalStrength
    description: str
    minimum_state_for: LeadState  # This signal can advance to at least this state

    def __hash__(self):
        return hash(self.signal_id)


# =============================================================================
# DISCOVERY SIGNALS (Weak) - Browsing → Curious
# =============================================================================

class DiscoverySignal:
    """Discovery signals indicate initial interest but no commitment."""

    VIEWED_OUTCOME = LeadSignal(
        signal_id="discovery.viewed_outcome",
        name="Viewed Outcome",
        signal_type=SignalType.DISCOVERY,
        strength=SignalStrength.WEAK,
        description="Prospect viewed their estimated outcome (refund/owed)",
        minimum_state_for=LeadState.CURIOUS,
    )

    EXPANDED_DRIVERS = LeadSignal(
        signal_id="discovery.expanded_drivers",
        name="Expanded Drivers",
        signal_type=SignalType.DISCOVERY,
        strength=SignalStrength.WEAK,
        description="Prospect expanded to see tax driver breakdown",
        minimum_state_for=LeadState.CURIOUS,
    )

    TIME_ON_SUMMARY = LeadSignal(
        signal_id="discovery.time_on_summary",
        name="Time on Summary",
        signal_type=SignalType.DISCOVERY,
        strength=SignalStrength.MODERATE,
        description="Prospect spent significant time reviewing summary (>60s)",
        minimum_state_for=LeadState.CURIOUS,
    )

    VIEWED_COMPLEXITY = LeadSignal(
        signal_id="discovery.viewed_complexity",
        name="Viewed Complexity",
        signal_type=SignalType.DISCOVERY,
        strength=SignalStrength.WEAK,
        description="Prospect viewed their complexity assessment",
        minimum_state_for=LeadState.CURIOUS,
    )

    RETURNED_SESSION = LeadSignal(
        signal_id="discovery.returned_session",
        name="Returned to Session",
        signal_type=SignalType.DISCOVERY,
        strength=SignalStrength.MODERATE,
        description="Prospect returned to view their session again",
        minimum_state_for=LeadState.CURIOUS,
    )


# =============================================================================
# EVALUATION SIGNALS (Attention) - Curious → Evaluating
# =============================================================================

class EvaluationSignal:
    """Evaluation signals indicate active consideration and comparison."""

    COMPARED_SCENARIOS = LeadSignal(
        signal_id="evaluation.compared_scenarios",
        name="Compared Scenarios",
        signal_type=SignalType.EVALUATION,
        strength=SignalStrength.MODERATE,
        description="Prospect compared different tax scenarios",
        minimum_state_for=LeadState.EVALUATING,
    )

    DOWNLOADED_SUMMARY = LeadSignal(
        signal_id="evaluation.downloaded_summary",
        name="Downloaded Summary",
        signal_type=SignalType.EVALUATION,
        strength=SignalStrength.MODERATE,
        description="Prospect downloaded their discovery summary",
        minimum_state_for=LeadState.EVALUATING,
    )

    VIEWED_OPPORTUNITIES = LeadSignal(
        signal_id="evaluation.viewed_opportunities",
        name="Viewed Opportunities",
        signal_type=SignalType.EVALUATION,
        strength=SignalStrength.MODERATE,
        description="Prospect viewed flagged optimization opportunities",
        minimum_state_for=LeadState.EVALUATING,
    )

    EXPLORED_WHAT_IF = LeadSignal(
        signal_id="evaluation.explored_what_if",
        name="Explored What-If",
        signal_type=SignalType.EVALUATION,
        strength=SignalStrength.STRONG,
        description="Prospect used what-if scenario modeling",
        minimum_state_for=LeadState.EVALUATING,
    )

    MULTIPLE_SESSIONS = LeadSignal(
        signal_id="evaluation.multiple_sessions",
        name="Multiple Sessions",
        signal_type=SignalType.EVALUATION,
        strength=SignalStrength.MODERATE,
        description="Prospect has visited 3+ times",
        minimum_state_for=LeadState.EVALUATING,
    )

    UPDATED_DATA = LeadSignal(
        signal_id="evaluation.updated_data",
        name="Updated Data",
        signal_type=SignalType.EVALUATION,
        strength=SignalStrength.STRONG,
        description="Prospect updated their financial data after initial entry",
        minimum_state_for=LeadState.EVALUATING,
    )


# =============================================================================
# COMMITMENT SIGNALS (Gold) - Evaluating → Advisory-Ready / High-Leverage
# =============================================================================

class CommitmentSignal:
    """Commitment signals indicate readiness for CPA engagement."""

    REQUESTED_CPA_REVIEW = LeadSignal(
        signal_id="commitment.requested_cpa_review",
        name="Requested CPA Review",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect explicitly requested CPA review",
        minimum_state_for=LeadState.ADVISORY_READY,
    )

    HIT_FEATURE_LOCK = LeadSignal(
        signal_id="commitment.hit_feature_lock",
        name="Hit Feature Lock",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.STRONG,
        description="Prospect attempted to access CPA-only feature",
        minimum_state_for=LeadState.ADVISORY_READY,
    )

    PROVIDED_CONTACT = LeadSignal(
        signal_id="commitment.provided_contact",
        name="Provided Contact Info",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect provided contact information for follow-up",
        minimum_state_for=LeadState.ADVISORY_READY,
    )

    DETAILED_ANSWERS = LeadSignal(
        signal_id="commitment.detailed_answers",
        name="Detailed Answers",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.STRONG,
        description="Prospect provided detailed/nuanced answers to questions",
        minimum_state_for=LeadState.ADVISORY_READY,
    )

    COMPLEX_SITUATION = LeadSignal(
        signal_id="commitment.complex_situation",
        name="Complex Tax Situation",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect has complex situation (multi-state, K-1, foreign, crypto)",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    HIGH_INCOME = LeadSignal(
        signal_id="commitment.high_income",
        name="High Income Indicator",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect indicated high income (>$200k)",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    BUSINESS_OWNER = LeadSignal(
        signal_id="commitment.business_owner",
        name="Business Owner",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect indicated business ownership",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    MULTIPLE_OPPORTUNITIES = LeadSignal(
        signal_id="commitment.multiple_opportunities",
        name="Multiple Opportunities",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.STRONG,
        description="Prospect has 3+ optimization opportunities flagged",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    URGENCY_INDICATED = LeadSignal(
        signal_id="commitment.urgency_indicated",
        name="Urgency Indicated",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect indicated time-sensitive situation",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )


# =============================================================================
# P1: FINANCIAL INDICATOR SIGNALS (High-Value Lead Qualification)
# =============================================================================

class FinancialIndicatorSignal:
    """
    Financial indicator signals identify high-value prospects.

    These signals detect financial complexity that warrants CPA advisory services
    and higher engagement pricing tiers.
    """

    INVESTMENT_PORTFOLIO = LeadSignal(
        signal_id="financial.investment_portfolio",
        name="Investment Portfolio",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.STRONG,
        description="Prospect has significant investment income (dividends, capital gains)",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    REAL_ESTATE_HOLDINGS = LeadSignal(
        signal_id="financial.real_estate_holdings",
        name="Real Estate Holdings",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect has rental properties or real estate investments",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    RETIREMENT_DISTRIBUTIONS = LeadSignal(
        signal_id="financial.retirement_distributions",
        name="Retirement Distributions",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.STRONG,
        description="Prospect is taking or planning retirement distributions",
        minimum_state_for=LeadState.ADVISORY_READY,
    )

    ESTATE_TRUST_INVOLVEMENT = LeadSignal(
        signal_id="financial.estate_trust",
        name="Estate/Trust Involvement",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect has estate planning or trust-related tax needs",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    HIGH_LIABILITY_INDICATED = LeadSignal(
        signal_id="financial.high_liability",
        name="High Tax Liability",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect has estimated tax liability >$50,000",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    MULTI_STATE_INCOME = LeadSignal(
        signal_id="financial.multi_state",
        name="Multi-State Income",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.STRONG,
        description="Prospect has income from multiple states",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    FOREIGN_INCOME_ASSETS = LeadSignal(
        signal_id="financial.foreign_income",
        name="Foreign Income/Assets",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect has foreign income, assets, or reporting requirements",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    CRYPTO_ACTIVITY = LeadSignal(
        signal_id="financial.crypto_activity",
        name="Cryptocurrency Activity",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.STRONG,
        description="Prospect has cryptocurrency transactions requiring reporting",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    SELF_EMPLOYMENT_SIGNIFICANT = LeadSignal(
        signal_id="financial.self_employment",
        name="Significant Self-Employment",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect has self-employment income >$100,000",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    EQUITY_COMPENSATION = LeadSignal(
        signal_id="financial.equity_compensation",
        name="Equity Compensation",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.GOLD,
        description="Prospect has stock options, RSUs, or other equity compensation",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    AMT_EXPOSURE = LeadSignal(
        signal_id="financial.amt_exposure",
        name="AMT Exposure",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.STRONG,
        description="Prospect may be subject to Alternative Minimum Tax",
        minimum_state_for=LeadState.HIGH_LEVERAGE,
    )

    ESTIMATED_TAX_PENALTIES = LeadSignal(
        signal_id="financial.estimated_tax_penalties",
        name="Estimated Tax Penalty Risk",
        signal_type=SignalType.COMMITMENT,
        strength=SignalStrength.STRONG,
        description="Prospect at risk for underpayment penalties",
        minimum_state_for=LeadState.ADVISORY_READY,
    )


# =============================================================================
# SIGNAL CATALOG
# =============================================================================

SIGNAL_CATALOG: Dict[str, LeadSignal] = {
    # Discovery signals
    DiscoverySignal.VIEWED_OUTCOME.signal_id: DiscoverySignal.VIEWED_OUTCOME,
    DiscoverySignal.EXPANDED_DRIVERS.signal_id: DiscoverySignal.EXPANDED_DRIVERS,
    DiscoverySignal.TIME_ON_SUMMARY.signal_id: DiscoverySignal.TIME_ON_SUMMARY,
    DiscoverySignal.VIEWED_COMPLEXITY.signal_id: DiscoverySignal.VIEWED_COMPLEXITY,
    DiscoverySignal.RETURNED_SESSION.signal_id: DiscoverySignal.RETURNED_SESSION,
    # Evaluation signals
    EvaluationSignal.COMPARED_SCENARIOS.signal_id: EvaluationSignal.COMPARED_SCENARIOS,
    EvaluationSignal.DOWNLOADED_SUMMARY.signal_id: EvaluationSignal.DOWNLOADED_SUMMARY,
    EvaluationSignal.VIEWED_OPPORTUNITIES.signal_id: EvaluationSignal.VIEWED_OPPORTUNITIES,
    EvaluationSignal.EXPLORED_WHAT_IF.signal_id: EvaluationSignal.EXPLORED_WHAT_IF,
    EvaluationSignal.MULTIPLE_SESSIONS.signal_id: EvaluationSignal.MULTIPLE_SESSIONS,
    EvaluationSignal.UPDATED_DATA.signal_id: EvaluationSignal.UPDATED_DATA,
    # Commitment signals
    CommitmentSignal.REQUESTED_CPA_REVIEW.signal_id: CommitmentSignal.REQUESTED_CPA_REVIEW,
    CommitmentSignal.HIT_FEATURE_LOCK.signal_id: CommitmentSignal.HIT_FEATURE_LOCK,
    CommitmentSignal.PROVIDED_CONTACT.signal_id: CommitmentSignal.PROVIDED_CONTACT,
    CommitmentSignal.DETAILED_ANSWERS.signal_id: CommitmentSignal.DETAILED_ANSWERS,
    CommitmentSignal.COMPLEX_SITUATION.signal_id: CommitmentSignal.COMPLEX_SITUATION,
    CommitmentSignal.HIGH_INCOME.signal_id: CommitmentSignal.HIGH_INCOME,
    CommitmentSignal.BUSINESS_OWNER.signal_id: CommitmentSignal.BUSINESS_OWNER,
    CommitmentSignal.MULTIPLE_OPPORTUNITIES.signal_id: CommitmentSignal.MULTIPLE_OPPORTUNITIES,
    CommitmentSignal.URGENCY_INDICATED.signal_id: CommitmentSignal.URGENCY_INDICATED,
    # P1: Financial indicator signals
    FinancialIndicatorSignal.INVESTMENT_PORTFOLIO.signal_id: FinancialIndicatorSignal.INVESTMENT_PORTFOLIO,
    FinancialIndicatorSignal.REAL_ESTATE_HOLDINGS.signal_id: FinancialIndicatorSignal.REAL_ESTATE_HOLDINGS,
    FinancialIndicatorSignal.RETIREMENT_DISTRIBUTIONS.signal_id: FinancialIndicatorSignal.RETIREMENT_DISTRIBUTIONS,
    FinancialIndicatorSignal.ESTATE_TRUST_INVOLVEMENT.signal_id: FinancialIndicatorSignal.ESTATE_TRUST_INVOLVEMENT,
    FinancialIndicatorSignal.HIGH_LIABILITY_INDICATED.signal_id: FinancialIndicatorSignal.HIGH_LIABILITY_INDICATED,
    FinancialIndicatorSignal.MULTI_STATE_INCOME.signal_id: FinancialIndicatorSignal.MULTI_STATE_INCOME,
    FinancialIndicatorSignal.FOREIGN_INCOME_ASSETS.signal_id: FinancialIndicatorSignal.FOREIGN_INCOME_ASSETS,
    FinancialIndicatorSignal.CRYPTO_ACTIVITY.signal_id: FinancialIndicatorSignal.CRYPTO_ACTIVITY,
    FinancialIndicatorSignal.SELF_EMPLOYMENT_SIGNIFICANT.signal_id: FinancialIndicatorSignal.SELF_EMPLOYMENT_SIGNIFICANT,
    FinancialIndicatorSignal.EQUITY_COMPENSATION.signal_id: FinancialIndicatorSignal.EQUITY_COMPENSATION,
    FinancialIndicatorSignal.AMT_EXPOSURE.signal_id: FinancialIndicatorSignal.AMT_EXPOSURE,
    FinancialIndicatorSignal.ESTIMATED_TAX_PENALTIES.signal_id: FinancialIndicatorSignal.ESTIMATED_TAX_PENALTIES,
}


def get_signal(signal_id: str) -> Optional[LeadSignal]:
    """Get a signal by ID."""
    return SIGNAL_CATALOG.get(signal_id)


def get_signals_by_type(signal_type: SignalType) -> list[LeadSignal]:
    """Get all signals of a given type."""
    return [s for s in SIGNAL_CATALOG.values() if s.signal_type == signal_type]


def get_signals_for_state(target_state: LeadState) -> list[LeadSignal]:
    """Get all signals that can advance a lead to at least the target state."""
    return [s for s in SIGNAL_CATALOG.values() if s.minimum_state_for >= target_state]
