"""
AI-Powered Recommendation Enhancer.

Enhances rule-based tax recommendations with AI-generated explanations,
personalized advice, and natural language summaries.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from recommendation.recommendation_engine import ComprehensiveRecommendation, TaxSavingOpportunity

from services.ai import get_ai_service, run_async
from services.ai.metrics_service import get_ai_metrics_service
from config.ai_providers import ModelCapability, get_available_providers

logger = logging.getLogger(__name__)


def _count_populated_enhancement(rec: "AIEnhancedRecommendation") -> int:
    """Count non-empty fields in an AIEnhancedRecommendation."""
    count = 0
    if rec.personalized_explanation:
        count += 1
    if rec.action_steps:
        count += 1
    if rec.common_questions:
        count += 1
    if rec.risk_considerations:
        count += 1
    if rec.related_opportunities:
        count += 1
    if rec.confidence_explanation:
        count += 1
    if rec.irs_reference:
        count += 1
    return count


@dataclass
class AIEnhancedRecommendation:
    """AI-enhanced version of a tax recommendation."""
    original_title: str
    original_description: str
    estimated_savings: float

    # AI-enhanced fields
    personalized_explanation: str
    action_steps: List[str]
    common_questions: List[Dict[str, str]]  # Q&A pairs
    risk_considerations: List[str]
    related_opportunities: List[str]
    confidence_explanation: str

    # Metadata
    irs_reference: str
    priority: str
    category: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIRecommendationSummary:
    """AI-generated summary of all recommendations."""
    executive_summary: str
    key_takeaways: List[str]
    priority_actions: List[str]
    estimated_total_savings: float
    confidence_summary: str
    personalized_advice: str
    warnings: List[str]


class AIRecommendationEnhancer:
    """
    Enhances tax recommendations using AI.

    Takes rule-based recommendations from the TaxRecommendationEngine
    and adds:
    - Personalized natural language explanations
    - Step-by-step action guides
    - Common questions and answers
    - Risk considerations
    - Confidence explanations
    """

    def __init__(self):
        """Initialize the AI enhancer."""
        pass

    @property
    def is_available(self) -> bool:
        """Check if AI enhancement is available."""
        return len(get_available_providers()) > 0

    def enhance_recommendation(
        self,
        opportunity: "TaxSavingOpportunity",
        taxpayer_context: Optional[Dict[str, Any]] = None
    ) -> AIEnhancedRecommendation:
        """
        Enhance a single recommendation with AI-generated content.

        Args:
            opportunity: The original rule-based opportunity
            taxpayer_context: Optional context about the taxpayer

        Returns:
            AIEnhancedRecommendation with enhanced explanations
        """
        if not self.is_available:
            return self._fallback_enhancement(opportunity)

        try:
            # Build context for AI
            context = {
                "title": opportunity.title,
                "category": opportunity.category,
                "description": opportunity.description,
                "estimated_savings": opportunity.estimated_savings,
                "action_required": opportunity.action_required,
                "priority": opportunity.priority,
                "irs_reference": opportunity.irs_reference,
                "confidence": opportunity.confidence,
            }

            if taxpayer_context:
                context["taxpayer"] = {
                    "filing_status": taxpayer_context.get("filing_status"),
                    "income_range": self._get_income_range(taxpayer_context.get("agi", 0)),
                    "has_dependents": taxpayer_context.get("has_dependents", False),
                }

            # Generate enhanced content
            prompt = self._build_enhancement_prompt(context)
            response = self._call_openai(prompt)

            if response:
                enhanced = json.loads(response)
                result = AIEnhancedRecommendation(
                    original_title=opportunity.title,
                    original_description=opportunity.description,
                    estimated_savings=opportunity.estimated_savings,
                    personalized_explanation=enhanced.get("personalized_explanation", opportunity.description),
                    action_steps=enhanced.get("action_steps", [opportunity.action_required]),
                    common_questions=enhanced.get("common_questions", []),
                    risk_considerations=enhanced.get("risk_considerations", []),
                    related_opportunities=enhanced.get("related_opportunities", []),
                    confidence_explanation=enhanced.get("confidence_explanation", ""),
                    irs_reference=opportunity.irs_reference,
                    priority=opportunity.priority,
                    category=opportunity.category,
                    metadata={"_source": "ai", "_provider": "openai"},
                )
                get_ai_metrics_service().record_response_quality(
                    service="enhancer", source="ai",
                    response_fields_populated=_count_populated_enhancement(result),
                    total_fields=7,
                )
                return result
        except Exception as e:
            logger.warning(f"AI enhancement failed: {e}")

        return self._fallback_enhancement(opportunity)

    def generate_summary(
        self,
        recommendation: "ComprehensiveRecommendation"
    ) -> AIRecommendationSummary:
        """
        Generate an AI-enhanced summary of all recommendations.

        Args:
            recommendation: The comprehensive recommendation from the engine

        Returns:
            AIRecommendationSummary with natural language insights
        """
        if not self.is_available:
            return self._fallback_summary(recommendation)

        try:
            # Build context
            context = {
                "taxpayer_name": recommendation.taxpayer_name,
                "filing_status": recommendation.filing_status,
                "current_tax": recommendation.current_total_tax,
                "optimized_tax": recommendation.optimized_total_tax,
                "total_savings": recommendation.total_potential_savings,
                "immediate_savings": recommendation.immediate_action_savings,
                "top_opportunities": [
                    {
                        "title": opp.title,
                        "savings": opp.estimated_savings,
                        "category": opp.category,
                    }
                    for opp in recommendation.top_opportunities[:5]
                ],
                "warnings": recommendation.warnings[:3],
            }

            prompt = self._build_summary_prompt(context)
            response = self._call_openai(prompt)

            if response:
                summary = json.loads(response)
                return AIRecommendationSummary(
                    executive_summary=summary.get("executive_summary", recommendation.executive_summary),
                    key_takeaways=summary.get("key_takeaways", []),
                    priority_actions=summary.get("priority_actions", []),
                    estimated_total_savings=recommendation.total_potential_savings,
                    confidence_summary=summary.get("confidence_summary", ""),
                    personalized_advice=summary.get("personalized_advice", ""),
                    warnings=summary.get("warnings", recommendation.warnings),
                )
        except Exception as e:
            logger.warning(f"AI summary generation failed: {e}")

        return self._fallback_summary(recommendation)

    def explain_in_plain_language(
        self,
        opportunity: "TaxSavingOpportunity",
        education_level: str = "general"
    ) -> str:
        """
        Generate a plain-language explanation of a tax opportunity.

        Args:
            opportunity: The opportunity to explain
            education_level: "general", "detailed", or "expert"

        Returns:
            Plain-language explanation string
        """
        if not self.is_available:
            return opportunity.description

        try:
            prompt = f"""Explain this tax opportunity in plain language for a {education_level} audience.

Title: {opportunity.title}
Category: {opportunity.category}
Description: {opportunity.description}
Potential Savings: ${opportunity.estimated_savings:,.0f}
IRS Reference: {opportunity.irs_reference}

Provide a clear, conversational explanation that:
1. Explains what this is in simple terms
2. Why it matters for the taxpayer
3. How much they could save
4. What they need to do

Keep it concise (2-3 sentences for general, 4-5 for detailed)."""

            response = self._call_openai(prompt, as_json=False)
            return response or opportunity.description
        except Exception as e:
            logger.warning(f"Plain language explanation failed: {e}")
            return opportunity.description

    def _build_enhancement_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for enhancing a recommendation."""
        return f"""You are a tax advisor AI. Enhance this tax recommendation with helpful explanations.

Recommendation Context:
{json.dumps(context, indent=2)}

Generate a JSON response with these fields:
{{
  "personalized_explanation": "A clear, personalized explanation of why this matters for the taxpayer",
  "action_steps": ["Step 1", "Step 2", ...],
  "common_questions": [
    {{"question": "Q1?", "answer": "A1"}},
    ...
  ],
  "risk_considerations": ["Risk 1", ...],
  "related_opportunities": ["Related opportunity 1", ...],
  "confidence_explanation": "Why we are confident/uncertain about this recommendation"
}}

Focus on being helpful, accurate, and actionable. Reference IRS rules when appropriate.
Return only valid JSON, no markdown code blocks."""

    def _build_summary_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for generating a summary."""
        return f"""You are a tax advisor AI. Generate a personalized summary of tax recommendations.

Context:
{json.dumps(context, indent=2)}

Generate a JSON response with these fields:
{{
  "executive_summary": "A 2-3 sentence executive summary of the tax situation and opportunities",
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
  "priority_actions": ["Action 1 (do first)", "Action 2", "Action 3"],
  "confidence_summary": "Brief explanation of how confident we are in these recommendations",
  "personalized_advice": "Specific advice based on their situation",
  "warnings": ["Important warning 1", ...]
}}

Be concise, professional, and helpful. Return only valid JSON, no markdown code blocks."""

    def _call_openai(self, prompt: str, as_json: bool = True) -> Optional[str]:
        """Make an AI API call via unified service."""
        if not self.is_available:
            return None

        try:
            ai = get_ai_service()
            response = run_async(ai.complete(
                prompt=prompt,
                system_prompt="You are a helpful tax advisor AI. Provide accurate, IRS-compliant advice.",
                capability=ModelCapability.FAST,
                temperature=0.3,
                max_tokens=1000,
            ))
            return response.content
        except Exception as e:
            logger.error(f"AI API call failed: {e}")
            return None

    def _fallback_enhancement(self, opportunity: "TaxSavingOpportunity") -> AIEnhancedRecommendation:
        """Create a fallback enhancement without AI."""
        result = AIEnhancedRecommendation(
            original_title=opportunity.title,
            original_description=opportunity.description,
            estimated_savings=opportunity.estimated_savings,
            personalized_explanation=opportunity.description,
            action_steps=[opportunity.action_required],
            common_questions=[],
            risk_considerations=[],
            related_opportunities=[],
            confidence_explanation=f"Confidence level: {opportunity.confidence:.0f}%",
            irs_reference=opportunity.irs_reference,
            priority=opportunity.priority,
            category=opportunity.category,
            metadata={"_source": "fallback", "_provider": "none"},
        )
        get_ai_metrics_service().record_response_quality(
            service="enhancer", source="fallback",
            response_fields_populated=_count_populated_enhancement(result),
            total_fields=7,
        )
        return result

    def _fallback_summary(self, recommendation: "ComprehensiveRecommendation") -> AIRecommendationSummary:
        """Create a fallback summary without AI."""
        return AIRecommendationSummary(
            executive_summary=recommendation.executive_summary,
            key_takeaways=[
                f"Total potential savings: ${recommendation.total_potential_savings:,.0f}",
                f"Immediate action savings: ${recommendation.immediate_action_savings:,.0f}",
                f"Review {len(recommendation.top_opportunities)} opportunities",
            ],
            priority_actions=[opp.action_required for opp in recommendation.top_opportunities[:3]],
            estimated_total_savings=recommendation.total_potential_savings,
            confidence_summary=f"Overall confidence: {recommendation.overall_confidence:.0f}%",
            personalized_advice="Review each recommendation carefully and consult a tax professional if needed.",
            warnings=recommendation.warnings,
        )

    def _get_income_range(self, agi: float) -> str:
        """Get income range description for context."""
        if agi < 50000:
            return "under $50,000"
        elif agi < 100000:
            return "$50,000-$100,000"
        elif agi < 200000:
            return "$100,000-$200,000"
        elif agi < 500000:
            return "$200,000-$500,000"
        else:
            return "over $500,000"


# Singleton instance
_enhancer_instance: Optional[AIRecommendationEnhancer] = None


def get_ai_enhancer() -> AIRecommendationEnhancer:
    """Get or create the singleton AI enhancer instance."""
    global _enhancer_instance
    if _enhancer_instance is None:
        _enhancer_instance = AIRecommendationEnhancer()
    return _enhancer_instance
