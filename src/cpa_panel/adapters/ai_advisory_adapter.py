"""
AI Advisory Adapter for CPA Panel

Bridges the AI recommendation enhancer to the CPA panel,
providing AI-enhanced explanations and insights for tax recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime
import logging

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

logger = logging.getLogger(__name__)


@dataclass
class EnhancedInsight:
    """An AI-enhanced tax insight."""
    original_title: str
    original_description: str
    estimated_savings: float
    personalized_explanation: str
    action_steps: List[str]
    common_questions: List[Dict[str, str]]
    risk_considerations: List[str]
    related_opportunities: List[str]
    confidence_explanation: str
    irs_reference: str
    priority: str
    category: str


class AIAdvisoryAdapter:
    """
    Adapter for AI-enhanced advisory features.

    Provides CPA panel access to:
    - AI-enhanced recommendations with personalized explanations
    - Plain-language explanations for complex tax concepts
    - AI-generated summaries for client communication
    """

    def __init__(self):
        """Initialize adapter."""
        self._ai_enhancer = None
        self._recommendation_engine = None

    @property
    def ai_enhancer(self):
        """Lazy load AI enhancer."""
        if self._ai_enhancer is None:
            try:
                from recommendation.ai_enhancer import get_ai_enhancer
                self._ai_enhancer = get_ai_enhancer()
            except ImportError:
                logger.warning("AI enhancer not available")
        return self._ai_enhancer

    @property
    def recommendation_engine(self):
        """Lazy load recommendation engine."""
        if self._recommendation_engine is None:
            try:
                from recommendation.recommendation_engine import TaxRecommendationEngine
                self._recommendation_engine = TaxRecommendationEngine()
            except ImportError:
                logger.warning("Recommendation engine not available")
        return self._recommendation_engine

    def get_tax_return(self, session_id: str) -> Optional["TaxReturn"]:
        """Get tax return from session."""
        try:
            from cpa_panel.adapters import TaxReturnAdapter
            adapter = TaxReturnAdapter()
            return adapter.get_tax_return(session_id)
        except Exception as e:
            logger.error(f"Failed to get tax return for {session_id}: {e}")
            return None

    def get_ai_enhanced_insights(self, session_id: str) -> Dict[str, Any]:
        """
        Get AI-enhanced recommendations for a client.

        Takes the rule-based recommendations and enhances them
        with AI-generated explanations, action steps, and Q&A.
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return {
                "success": False,
                "error": f"Tax return not found for session {session_id}",
            }

        try:
            # Get base recommendations
            if not self.recommendation_engine:
                return {
                    "success": False,
                    "error": "Recommendation engine not available",
                }

            recommendation = self.recommendation_engine.analyze(tax_return)

            # Get AI summary
            ai_summary = None
            if self.ai_enhancer and self.ai_enhancer.is_available:
                try:
                    summary = self.ai_enhancer.generate_summary(recommendation)
                    ai_summary = {
                        "executive_summary": summary.executive_summary,
                        "key_takeaways": summary.key_takeaways,
                        "priority_actions": summary.priority_actions,
                        "confidence_summary": summary.confidence_summary,
                        "personalized_advice": summary.personalized_advice,
                        "warnings": summary.warnings,
                    }
                except Exception as e:
                    logger.warning(f"AI summary generation failed: {e}")

            # Enhance top opportunities
            enhanced_opportunities = []
            for opp in recommendation.top_opportunities[:10]:
                enhanced = self._enhance_opportunity(opp, tax_return)
                enhanced_opportunities.append(enhanced)

            return {
                "success": True,
                "session_id": session_id,
                "ai_available": self.ai_enhancer and self.ai_enhancer.is_available,
                "summary": ai_summary or {
                    "executive_summary": recommendation.executive_summary,
                    "key_takeaways": [
                        f"Total potential savings: ${recommendation.total_potential_savings:,.0f}",
                        f"Immediate action savings: ${recommendation.immediate_action_savings:,.0f}",
                        f"Review {len(recommendation.top_opportunities)} opportunities",
                    ],
                    "priority_actions": [o.action_required for o in recommendation.top_opportunities[:3]],
                    "confidence_summary": f"Overall confidence: {recommendation.overall_confidence:.0f}%",
                    "personalized_advice": "Review each recommendation with your CPA.",
                    "warnings": recommendation.warnings,
                },
                "total_potential_savings": recommendation.total_potential_savings,
                "immediate_action_savings": recommendation.immediate_action_savings,
                "enhanced_opportunities": enhanced_opportunities,
                "opportunity_count": len(recommendation.all_opportunities),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"AI insights failed for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def explain_recommendation(
        self,
        session_id: str,
        recommendation_id: str,
        education_level: str = "general",
    ) -> Dict[str, Any]:
        """
        Get a plain-language explanation for a specific recommendation.

        Args:
            session_id: Client session ID
            recommendation_id: The recommendation to explain
            education_level: Target level - "general", "detailed", or "expert"
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return {
                "success": False,
                "error": f"Tax return not found for session {session_id}",
            }

        try:
            if not self.recommendation_engine:
                return {
                    "success": False,
                    "error": "Recommendation engine not available",
                }

            recommendation = self.recommendation_engine.analyze(tax_return)

            # Find the specific opportunity
            opportunity = None
            for opp in recommendation.all_opportunities:
                if opp.opportunity_id == recommendation_id:
                    opportunity = opp
                    break

            if not opportunity:
                return {
                    "success": False,
                    "error": f"Recommendation not found: {recommendation_id}",
                }

            # Get AI explanation
            explanation = opportunity.description  # Default
            if self.ai_enhancer and self.ai_enhancer.is_available:
                try:
                    explanation = self.ai_enhancer.explain_in_plain_language(
                        opportunity, education_level
                    )
                except Exception as e:
                    logger.warning(f"AI explanation failed: {e}")

            return {
                "success": True,
                "session_id": session_id,
                "recommendation_id": recommendation_id,
                "title": opportunity.title,
                "category": opportunity.category,
                "estimated_savings": opportunity.estimated_savings,
                "explanation": explanation,
                "education_level": education_level,
                "action_required": opportunity.action_required,
                "irs_reference": opportunity.irs_reference,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Explain recommendation failed for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def generate_client_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Generate a client-friendly summary of tax recommendations.

        Creates a summary suitable for client communication,
        with plain language and actionable takeaways.
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return {
                "success": False,
                "error": f"Tax return not found for session {session_id}",
            }

        try:
            if not self.recommendation_engine:
                return {
                    "success": False,
                    "error": "Recommendation engine not available",
                }

            recommendation = self.recommendation_engine.analyze(tax_return)

            # Build client-friendly sections
            sections = []

            # Overview section
            sections.append({
                "title": "Tax Overview",
                "content": f"Based on our analysis, you have ${recommendation.total_potential_savings:,.0f} in potential tax savings opportunities. Your current estimated tax liability is ${recommendation.current_total_tax:,.0f}.",
            })

            # Top actions section
            top_actions = []
            for opp in recommendation.top_opportunities[:3]:
                top_actions.append(f"**{opp.title}** - Save up to ${opp.estimated_savings:,.0f}")
            sections.append({
                "title": "Top Actions",
                "content": "\n".join(top_actions) if top_actions else "No immediate actions identified.",
            })

            # Categories section
            categories = {}
            for opp in recommendation.all_opportunities:
                cat = opp.category
                if cat not in categories:
                    categories[cat] = {"count": 0, "savings": 0}
                categories[cat]["count"] += 1
                categories[cat]["savings"] += opp.estimated_savings

            cat_summary = [
                f"**{cat.replace('_', ' ').title()}**: {info['count']} opportunities (${info['savings']:,.0f} potential)"
                for cat, info in sorted(categories.items(), key=lambda x: x[1]['savings'], reverse=True)[:5]
            ]
            sections.append({
                "title": "Opportunities by Category",
                "content": "\n".join(cat_summary) if cat_summary else "No categorized opportunities.",
            })

            # Warnings section
            if recommendation.warnings:
                sections.append({
                    "title": "Important Notes",
                    "content": "\n".join(f"- {w}" for w in recommendation.warnings[:3]),
                })

            return {
                "success": True,
                "session_id": session_id,
                "client_name": f"{tax_return.taxpayer.first_name} {tax_return.taxpayer.last_name}".strip() if tax_return.taxpayer else "Client",
                "total_savings": recommendation.total_potential_savings,
                "sections": sections,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Generate client summary failed for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _enhance_opportunity(self, opportunity, tax_return) -> Dict[str, Any]:
        """Enhance a single opportunity with AI if available."""
        base = {
            "opportunity_id": opportunity.opportunity_id,
            "title": opportunity.title,
            "category": opportunity.category,
            "description": opportunity.description,
            "estimated_savings": opportunity.estimated_savings,
            "action_required": opportunity.action_required,
            "priority": opportunity.priority,
            "confidence": opportunity.confidence,
            "irs_reference": opportunity.irs_reference,
        }

        # Try AI enhancement
        if self.ai_enhancer and self.ai_enhancer.is_available:
            try:
                taxpayer_context = {}
                if tax_return.taxpayer:
                    taxpayer_context = {
                        "filing_status": tax_return.taxpayer.filing_status.value if tax_return.taxpayer.filing_status else None,
                        "agi": tax_return.adjusted_gross_income,
                        "has_dependents": bool(tax_return.dependents),
                    }

                enhanced = self.ai_enhancer.enhance_recommendation(opportunity, taxpayer_context)

                base.update({
                    "personalized_explanation": enhanced.personalized_explanation,
                    "action_steps": enhanced.action_steps,
                    "common_questions": enhanced.common_questions,
                    "risk_considerations": enhanced.risk_considerations,
                    "related_opportunities": enhanced.related_opportunities,
                    "confidence_explanation": enhanced.confidence_explanation,
                    "ai_enhanced": True,
                })
            except Exception as e:
                logger.warning(f"Enhancement failed for {opportunity.opportunity_id}: {e}")
                base["ai_enhanced"] = False
        else:
            base["ai_enhanced"] = False

        return base


# Singleton instance
_ai_advisory_adapter: Optional[AIAdvisoryAdapter] = None


def get_ai_advisory_adapter() -> AIAdvisoryAdapter:
    """Get or create singleton AI advisory adapter."""
    global _ai_advisory_adapter
    if _ai_advisory_adapter is None:
        _ai_advisory_adapter = AIAdvisoryAdapter()
    return _ai_advisory_adapter
