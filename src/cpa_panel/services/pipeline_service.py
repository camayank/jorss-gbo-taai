"""
Lead Pipeline Service for CPA Practice Growth

Provides lead pipeline visualization, conversion metrics, and
velocity tracking for CPA dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class PipelineStage:
    """A stage in the lead pipeline."""
    state: str
    display_name: str
    leads: List[Dict[str, Any]]
    count: int
    total_value: float
    avg_days_in_stage: float


@dataclass
class ConversionMetrics:
    """Lead conversion metrics."""
    total_leads: int
    converted_leads: int
    conversion_rate: float
    avg_conversion_time_days: float
    conversion_by_source: Dict[str, float]
    stage_conversion_rates: Dict[str, float]
    period_comparison: Dict[str, Any]


@dataclass
class VelocityMetrics:
    """Lead velocity metrics."""
    leads_per_day: float
    leads_per_week: float
    avg_time_to_advisory_ready: float
    avg_time_to_conversion: float
    bottleneck_stage: Optional[str]
    acceleration_opportunities: List[str]


class LeadPipelineService:
    """
    Service for lead pipeline management and analytics.

    Provides:
    - Pipeline views by state
    - Conversion metrics
    - Velocity tracking
    - Priority queue management
    """

    def __init__(self):
        """Initialize pipeline service."""
        self._engine = None

    @property
    def engine(self):
        """Get the lead state engine."""
        if self._engine is None:
            from cpa_panel.api.common import get_lead_state_engine
            self._engine = get_lead_state_engine()
        return self._engine

    def get_pipeline_by_state(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get leads organized by pipeline state.

        Returns Kanban-style view of leads in each state.
        """
        from cpa_panel.lead_state import LeadState
        from cpa_panel.lead_state.states import STATE_VISIBILITY

        pipeline = {}
        total_leads = 0
        total_value = 0

        for state in LeadState:
            leads = self.engine.get_leads_by_state(state, tenant_id)
            lead_dicts = [l.to_dict() for l in leads]

            # Calculate estimated value for each lead
            for lead_dict in lead_dicts:
                lead_dict['estimated_value'] = self._estimate_lead_value(lead_dict)

            state_value = sum(l['estimated_value'] for l in lead_dicts)

            pipeline[state.name] = {
                "state": state.name,
                "display_name": state.display_name,
                "visibility": STATE_VISIBILITY[state].value,
                "is_monetizable": state.is_monetizable,
                "is_priority": state.is_priority,
                "leads": lead_dicts,
                "count": len(leads),
                "total_value": state_value,
            }

            total_leads += len(leads)
            total_value += state_value

        return {
            "success": True,
            "pipeline": pipeline,
            "summary": {
                "total_leads": total_leads,
                "total_pipeline_value": total_value,
                "states_with_leads": [s for s, p in pipeline.items() if p["count"] > 0],
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_conversion_metrics(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get lead conversion metrics.

        Analyzes conversion rates, timing, and patterns.
        """
        from cpa_panel.lead_state import LeadState

        all_leads = []
        for state in LeadState:
            leads = self.engine.get_leads_by_state(state, tenant_id)
            all_leads.extend(leads)

        total_leads = len(all_leads)
        if total_leads == 0:
            return {
                "success": True,
                "metrics": {
                    "total_leads": 0,
                    "converted_leads": 0,
                    "conversion_rate": 0,
                    "avg_conversion_time_days": 0,
                },
                "message": "No leads found",
            }

        # Count conversions (HIGH_LEVERAGE state)
        converted = [l for l in all_leads if l.current_state == LeadState.HIGH_LEVERAGE]
        converted_count = len(converted)

        # Calculate conversion rate
        conversion_rate = (converted_count / total_leads * 100) if total_leads > 0 else 0

        # Calculate average conversion time
        conversion_times = []
        for lead in converted:
            if lead.transitions:
                first_time = lead.transitions[0].timestamp
                last_time = lead.transitions[-1].timestamp
                days = (last_time - first_time).days
                conversion_times.append(days)

        avg_conversion_time = sum(conversion_times) / len(conversion_times) if conversion_times else 0

        # Stage-by-stage conversion rates
        stage_rates = {}
        prev_count = total_leads
        for state in LeadState:
            state_leads = [l for l in all_leads if l.current_state.value >= state.value]
            state_count = len(state_leads)
            rate = (state_count / prev_count * 100) if prev_count > 0 else 0
            stage_rates[state.name] = round(rate, 1)

        return {
            "success": True,
            "metrics": {
                "total_leads": total_leads,
                "converted_leads": converted_count,
                "conversion_rate": round(conversion_rate, 1),
                "avg_conversion_time_days": round(avg_conversion_time, 1),
                "stage_conversion_rates": stage_rates,
                "leads_by_state": {
                    state.name: len([l for l in all_leads if l.current_state == state])
                    for state in LeadState
                },
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_velocity_metrics(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get lead velocity metrics.

        Tracks speed of lead progression through pipeline.
        """
        from cpa_panel.lead_state import LeadState

        all_leads = []
        for state in LeadState:
            leads = self.engine.get_leads_by_state(state, tenant_id)
            all_leads.extend(leads)

        if not all_leads:
            return {
                "success": True,
                "metrics": {
                    "leads_per_day": 0,
                    "leads_per_week": 0,
                    "avg_time_to_advisory_ready": 0,
                    "avg_time_to_conversion": 0,
                    "bottleneck_stage": None,
                    "acceleration_opportunities": [],
                },
                "message": "No leads found",
            }

        # Calculate leads per day/week (based on creation dates)
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)

        recent_leads = [l for l in all_leads if l.transitions and l.transitions[0].timestamp > week_ago]
        leads_per_week = len(recent_leads)
        leads_per_day = leads_per_week / 7

        # Time to advisory ready
        advisory_ready_times = []
        for lead in all_leads:
            if lead.current_state.value >= LeadState.ADVISORY_READY.value and lead.transitions:
                for trans in lead.transitions:
                    if trans.to_state == LeadState.ADVISORY_READY:
                        first_time = lead.transitions[0].timestamp
                        days = (trans.timestamp - first_time).days
                        advisory_ready_times.append(days)
                        break

        avg_time_to_advisory = sum(advisory_ready_times) / len(advisory_ready_times) if advisory_ready_times else 0

        # Time to high leverage
        conversion_times = []
        for lead in all_leads:
            if lead.current_state == LeadState.HIGH_LEVERAGE and lead.transitions:
                first_time = lead.transitions[0].timestamp
                last_time = lead.transitions[-1].timestamp
                days = (last_time - first_time).days
                conversion_times.append(days)

        avg_time_to_conversion = sum(conversion_times) / len(conversion_times) if conversion_times else 0

        # Find bottleneck (state with most leads stuck)
        state_counts = defaultdict(int)
        for lead in all_leads:
            state_counts[lead.current_state.name] += 1

        bottleneck = max(state_counts.items(), key=lambda x: x[1])[0] if state_counts else None

        # Acceleration opportunities
        opportunities = []
        if bottleneck == "CURIOUS":
            opportunities.append("Many leads at CURIOUS - consider targeted outreach")
        if bottleneck == "EVALUATING":
            opportunities.append("Leads stuck in EVALUATING - offer consultation calls")
        if avg_time_to_advisory > 14:
            opportunities.append("Long time to Advisory Ready - streamline qualification")

        return {
            "success": True,
            "metrics": {
                "leads_per_day": round(leads_per_day, 1),
                "leads_per_week": leads_per_week,
                "avg_time_to_advisory_ready": round(avg_time_to_advisory, 1),
                "avg_time_to_conversion": round(avg_time_to_conversion, 1),
                "bottleneck_stage": bottleneck,
                "acceleration_opportunities": opportunities,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_priority_queue(self, tenant_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """
        Get prioritized lead queue for CPA action.

        Returns leads ordered by priority score, combining:
        - State (higher states = higher priority)
        - Engagement level (signal count)
        - Time in current state
        - Estimated value
        """
        from cpa_panel.lead_state import LeadState

        # Get monetizable leads (ADVISORY_READY and above)
        monetizable = self.engine.get_monetizable_leads(tenant_id)

        # Score and rank leads
        scored_leads = []
        for lead in monetizable:
            score = self._calculate_priority_score(lead)
            lead_dict = lead.to_dict()
            lead_dict['priority_score'] = score
            lead_dict['estimated_value'] = self._estimate_lead_value(lead_dict)
            lead_dict['recommended_action'] = self._get_recommended_action(lead)
            scored_leads.append(lead_dict)

        # Sort by priority score
        scored_leads.sort(key=lambda x: x['priority_score'], reverse=True)

        return {
            "success": True,
            "priority_queue": scored_leads[:limit],
            "total_monetizable": len(scored_leads),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def advance_lead(self, lead_id: str, target_state: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Manually advance a lead to a target state.

        Used by CPAs to move leads forward in the pipeline.
        """
        from cpa_panel.lead_state import LeadState

        try:
            target = LeadState[target_state.upper()]
        except KeyError:
            return {
                "success": False,
                "error": f"Invalid state: {target_state}",
            }

        lead = self.engine.get_lead(lead_id)
        if not lead:
            return {
                "success": False,
                "error": f"Lead not found: {lead_id}",
            }

        # Find a signal that would advance to target state
        from cpa_panel.lead_state import SIGNAL_CATALOG

        advancement_signal = None
        for signal_id, signal in SIGNAL_CATALOG.items():
            if signal.minimum_state_for == target:
                advancement_signal = signal_id
                break

        if advancement_signal:
            try:
                self.engine.process_signal(
                    lead_id=lead_id,
                    signal_id=advancement_signal,
                    tenant_id=tenant_id,
                    metadata={"manual_advance": True, "advanced_by": "cpa"},
                )
                lead = self.engine.get_lead(lead_id)
            except Exception as e:
                logger.warning(f"Signal-based advance failed: {e}")

        return {
            "success": True,
            "lead": lead.to_dict() if lead else None,
            "current_state": lead.current_state.name if lead else None,
        }

    def _calculate_priority_score(self, lead) -> float:
        """Calculate priority score for a lead."""
        from cpa_panel.lead_state import LeadState

        score = 0

        # State-based scoring (0-50 points)
        state_scores = {
            LeadState.BROWSING: 0,
            LeadState.CURIOUS: 10,
            LeadState.EVALUATING: 25,
            LeadState.ADVISORY_READY: 40,
            LeadState.HIGH_LEVERAGE: 50,
        }
        score += state_scores.get(lead.current_state, 0)

        # Signal count (0-20 points)
        signal_count = len(lead.signals_received)
        score += min(signal_count * 2, 20)

        # Recency bonus (0-15 points)
        if lead.transitions:
            last_activity = lead.transitions[-1].timestamp
            days_since = (datetime.utcnow() - last_activity).days
            if days_since == 0:
                score += 15
            elif days_since <= 3:
                score += 10
            elif days_since <= 7:
                score += 5

        # Engagement strength (0-15 points)
        high_value_signals = [s for s in lead.signals_received if "tax_savings" in s or "schedule" in s]
        score += min(len(high_value_signals) * 3, 15)

        return score

    def _estimate_lead_value(self, lead_dict: Dict[str, Any]) -> float:
        """Estimate the dollar value of a lead."""
        # Base value by state
        state = lead_dict.get("current_state", "BROWSING")
        base_values = {
            "BROWSING": 0,
            "CURIOUS": 100,
            "EVALUATING": 300,
            "ADVISORY_READY": 600,
            "HIGH_LEVERAGE": 1200,
        }
        return base_values.get(state, 0)

    def _get_recommended_action(self, lead) -> str:
        """Get recommended action for a lead."""
        from cpa_panel.lead_state import LeadState

        actions = {
            LeadState.BROWSING: "Monitor - not yet engaged",
            LeadState.CURIOUS: "Send educational content",
            LeadState.EVALUATING: "Offer discovery call",
            LeadState.ADVISORY_READY: "Send engagement letter",
            LeadState.HIGH_LEVERAGE: "Schedule advisory session",
        }
        return actions.get(lead.current_state, "Review lead status")


# Singleton instance
_pipeline_service: Optional[LeadPipelineService] = None


def get_pipeline_service() -> LeadPipelineService:
    """Get or create singleton pipeline service."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = LeadPipelineService()
    return _pipeline_service
