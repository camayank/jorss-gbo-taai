"""
AI-Powered Narrative Generator for Tax Advisory Reports.

Uses Claude for generating personalized, professional narratives:
- Executive summaries tailored to client communication style
- Complex tax strategy explanations in plain language
- Personalized recommendations based on client goals
- Action items with clear deadlines and priorities

Usage:
    from advisory.ai_narrative_generator import get_narrative_generator

    generator = get_narrative_generator()
    summary = await generator.generate_executive_summary(
        analysis=tax_analysis,
        client_profile=client_profile
    )
"""

import hashlib
import logging
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CommunicationStyle(str, Enum):
    """Client communication style preferences."""
    FORMAL = "formal"           # Professional, detailed language
    CONVERSATIONAL = "conversational"  # Friendly, approachable
    TECHNICAL = "technical"     # Industry jargon, detailed analysis
    SIMPLIFIED = "simplified"   # Plain language, minimal jargon


class TaxSophistication(str, Enum):
    """Client's level of tax knowledge."""
    NOVICE = "novice"           # Basic understanding
    INTERMEDIATE = "intermediate"  # Familiar with common concepts
    ADVANCED = "advanced"       # Understands complex strategies
    EXPERT = "expert"           # Professional-level knowledge


@dataclass
class ClientProfile:
    """Profile of the client for personalization."""
    name: str
    occupation: Optional[str] = None
    financial_goals: List[str] = field(default_factory=list)
    communication_style: CommunicationStyle = CommunicationStyle.CONVERSATIONAL
    tax_sophistication: TaxSophistication = TaxSophistication.INTERMEDIATE
    primary_concern: Optional[str] = None
    preferred_tone: str = "professional but warm"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "occupation": self.occupation,
            "financial_goals": self.financial_goals,
            "communication_style": self.communication_style.value,
            "tax_sophistication": self.tax_sophistication.value,
            "primary_concern": self.primary_concern,
            "preferred_tone": self.preferred_tone,
        }


@dataclass
class GeneratedNarrative:
    """Result of narrative generation."""
    content: str
    narrative_type: str
    word_count: int
    key_points: List[str]
    tone_used: str
    generated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "narrative_type": self.narrative_type,
            "word_count": self.word_count,
            "key_points": self.key_points,
            "tone_used": self.tone_used,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
        }


class AINarrativeGenerator:
    """
    AI-powered narrative generator using Claude.

    Generates personalized, professional narratives for tax advisory reports:
    - Adapts language to client sophistication level
    - Matches preferred communication style
    - Focuses on client's primary concerns and goals
    - Explains complex concepts in accessible terms
    """

    def __init__(self, ai_service=None):
        """
        Initialize narrative generator.

        Args:
            ai_service: UnifiedAIService instance (lazy-loaded if not provided)
        """
        self._ai_service = ai_service
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: int = 3600

    def _cache_key(self, *args) -> str:
        """Create a SHA256 hash key from the given arguments."""
        raw = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[Any]:
        """Return cached value if present and not expired, otherwise None."""
        entry = self._cache.get(key)
        if entry is not None:
            timestamp, value = entry
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Cache hit for key {key[:12]}...")
                return value
            # Expired -- remove stale entry
            del self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        """Store a value in the cache with the current timestamp."""
        self._cache[key] = (time.time(), value)

    @property
    def ai_service(self):
        """Lazy-load AI service."""
        if self._ai_service is None:
            from services.ai.unified_ai_service import get_ai_service
            self._ai_service = get_ai_service()
        return self._ai_service

    async def generate_executive_summary(
        self,
        analysis: Dict[str, Any],
        client_profile: ClientProfile,
        max_words: int = 300,
    ) -> GeneratedNarrative:
        """
        Generate a personalized executive summary.

        Args:
            analysis: Tax analysis data (from AdvisoryReportResult)
            client_profile: Client profile for personalization
            max_words: Maximum word count for summary

        Returns:
            GeneratedNarrative with personalized executive summary
        """
        prompt = self._build_executive_summary_prompt(
            analysis, client_profile, max_words
        )

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(client_profile),
            )

            # Parse the response
            content = response.content.strip()
            key_points = self._extract_key_points(content)

            return GeneratedNarrative(
                content=content,
                narrative_type="executive_summary",
                word_count=len(content.split()),
                key_points=key_points,
                tone_used=client_profile.preferred_tone,
                metadata={
                    "client_name": client_profile.name,
                    "max_words_requested": max_words,
                    "sophistication_level": client_profile.tax_sophistication.value,
                },
            )

        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            # Return fallback narrative
            return self._generate_fallback_summary(analysis, client_profile)

    async def generate_recommendation_explanation(
        self,
        recommendation: Dict[str, Any],
        client_profile: ClientProfile,
    ) -> GeneratedNarrative:
        """
        Generate a personalized explanation of a tax recommendation.

        Args:
            recommendation: Recommendation data
            client_profile: Client profile for personalization

        Returns:
            GeneratedNarrative explaining the recommendation
        """
        prompt = f"""Explain this tax recommendation to {client_profile.name}:

Recommendation: {recommendation.get('title', 'Tax Optimization Strategy')}
Category: {recommendation.get('category', 'general')}
Estimated Savings: ${recommendation.get('savings', 0):,.2f}
Description: {recommendation.get('description', '')}
Action Required: {recommendation.get('action_required', '')}
IRS Reference: {recommendation.get('irs_reference', 'N/A')}

Client Profile:
- Occupation: {client_profile.occupation or 'Not specified'}
- Tax Knowledge: {client_profile.tax_sophistication.value}
- Primary Concern: {client_profile.primary_concern or 'Minimizing taxes'}
- Communication Style: {client_profile.communication_style.value}

Write a personalized explanation that:
1. Explains WHY this recommendation matters for them specifically
2. Breaks down HOW it saves them money (in simple terms if needed)
3. Lists the specific STEPS they need to take
4. Mentions any DEADLINES or timing considerations
5. Notes any RISKS or considerations

Use {client_profile.preferred_tone} tone.
Adjust technical language for their {client_profile.tax_sophistication.value} level.
Keep it concise but complete."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(client_profile),
            )

            content = response.content.strip()

            return GeneratedNarrative(
                content=content,
                narrative_type="recommendation_explanation",
                word_count=len(content.split()),
                key_points=self._extract_key_points(content),
                tone_used=client_profile.preferred_tone,
                metadata={
                    "recommendation_title": recommendation.get("title"),
                    "estimated_savings": recommendation.get("savings"),
                },
            )

        except Exception as e:
            logger.error(f"Failed to generate recommendation explanation: {e}")
            return GeneratedNarrative(
                content=recommendation.get("description", ""),
                narrative_type="recommendation_explanation",
                word_count=len(recommendation.get("description", "").split()),
                key_points=[recommendation.get("title", "")],
                tone_used="default",
            )

    async def generate_action_plan_narrative(
        self,
        action_items: List[Dict[str, Any]],
        client_profile: ClientProfile,
    ) -> GeneratedNarrative:
        """
        Generate a personalized action plan narrative.

        Args:
            action_items: List of action items with priorities
            client_profile: Client profile for personalization

        Returns:
            GeneratedNarrative with prioritized action plan
        """
        # Group actions by priority
        immediate = [a for a in action_items if a.get("priority") == "immediate"]
        current_year = [a for a in action_items if a.get("priority") == "current_year"]
        next_year = [a for a in action_items if a.get("priority") == "next_year"]

        prompt = f"""Create a personalized action plan for {client_profile.name}:

IMMEDIATE ACTIONS (do this week):
{json.dumps(immediate, indent=2) if immediate else "None"}

THIS TAX YEAR ACTIONS:
{json.dumps(current_year, indent=2) if current_year else "None"}

NEXT YEAR PLANNING:
{json.dumps(next_year, indent=2) if next_year else "None"}

Client Profile:
- Occupation: {client_profile.occupation or 'Not specified'}
- Primary Goal: {client_profile.financial_goals[0] if client_profile.financial_goals else 'Save on taxes'}
- Communication Style: {client_profile.communication_style.value}

Create a motivating, clear action plan that:
1. Prioritizes actions by urgency and impact
2. Provides specific deadlines where applicable
3. Explains the "why" behind each action
4. Groups related actions together
5. Ends with encouragement and next steps

Write in {client_profile.preferred_tone} tone.
Make it feel like a personalized roadmap, not a generic checklist."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(client_profile),
            )

            content = response.content.strip()

            return GeneratedNarrative(
                content=content,
                narrative_type="action_plan",
                word_count=len(content.split()),
                key_points=[a.get("title", "") for a in immediate[:3]],
                tone_used=client_profile.preferred_tone,
                metadata={
                    "total_actions": len(action_items),
                    "immediate_count": len(immediate),
                    "current_year_count": len(current_year),
                },
            )

        except Exception as e:
            logger.error(f"Failed to generate action plan narrative: {e}")
            return self._generate_fallback_action_plan(action_items)

    async def generate_year_over_year_narrative(
        self,
        current_year: Dict[str, Any],
        prior_year: Dict[str, Any],
        client_profile: ClientProfile,
    ) -> GeneratedNarrative:
        """
        Generate narrative comparing year-over-year tax changes.

        Args:
            current_year: Current year tax data
            prior_year: Prior year tax data
            client_profile: Client profile for personalization

        Returns:
            GeneratedNarrative with year-over-year analysis
        """
        prompt = f"""Analyze the year-over-year tax changes for {client_profile.name}:

CURRENT YEAR ({current_year.get('tax_year', 'Current')}):
- Total Income: ${current_year.get('total_income', 0):,.2f}
- Taxable Income: ${current_year.get('taxable_income', 0):,.2f}
- Total Tax: ${current_year.get('total_tax', 0):,.2f}
- Effective Rate: {current_year.get('effective_rate', 0):.1f}%

PRIOR YEAR ({prior_year.get('tax_year', 'Prior')}):
- Total Income: ${prior_year.get('total_income', 0):,.2f}
- Taxable Income: ${prior_year.get('taxable_income', 0):,.2f}
- Total Tax: ${prior_year.get('total_tax', 0):,.2f}
- Effective Rate: {prior_year.get('effective_rate', 0):.1f}%

Client Profile:
- Communication Style: {client_profile.communication_style.value}
- Tax Knowledge: {client_profile.tax_sophistication.value}

Write a narrative that:
1. Highlights key changes (income, deductions, tax liability)
2. Explains REASONS for significant changes
3. Notes positive trends to celebrate
4. Identifies concerning trends to address
5. Provides context (inflation, life changes, etc.)

Use {client_profile.preferred_tone} tone.
Keep technical explanations appropriate for {client_profile.tax_sophistication.value} level."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(client_profile),
            )

            content = response.content.strip()

            return GeneratedNarrative(
                content=content,
                narrative_type="year_over_year",
                word_count=len(content.split()),
                key_points=self._extract_key_points(content),
                tone_used=client_profile.preferred_tone,
                metadata={
                    "current_year": current_year.get("tax_year"),
                    "prior_year": prior_year.get("tax_year"),
                    "tax_change": current_year.get("total_tax", 0) - prior_year.get("total_tax", 0),
                },
            )

        except Exception as e:
            logger.error(f"Failed to generate year-over-year narrative: {e}")
            return GeneratedNarrative(
                content="Year-over-year comparison not available.",
                narrative_type="year_over_year",
                word_count=5,
                key_points=[],
                tone_used="default",
            )

    def _build_executive_summary_prompt(
        self,
        analysis: Dict[str, Any],
        client_profile: ClientProfile,
        max_words: int,
    ) -> str:
        """Build prompt for executive summary generation."""
        metrics = analysis.get("metrics", {})
        recommendations = analysis.get("recommendations", {})

        return f"""Write a personalized executive summary for {client_profile.name}'s tax advisory report.

TAX ANALYSIS DATA:
- Tax Year: {analysis.get('tax_year', 'Current')}
- Filing Status: {analysis.get('filing_status', 'Unknown')}
- Current Tax Liability: ${metrics.get('current_tax_liability', 0):,.2f}
- Potential Savings Identified: ${metrics.get('potential_savings', 0):,.2f}
- Number of Recommendations: {recommendations.get('total_count', 0)}
- Confidence Score: {metrics.get('confidence_score', 0):.0f}%

IMMEDIATE ACTION ITEMS:
{json.dumps(recommendations.get('immediate_actions', []), indent=2)}

CLIENT PROFILE:
- Name: {client_profile.name}
- Occupation: {client_profile.occupation or 'Not specified'}
- Financial Goals: {', '.join(client_profile.financial_goals) if client_profile.financial_goals else 'Not specified'}
- Primary Concern: {client_profile.primary_concern or 'Tax optimization'}
- Communication Style: {client_profile.communication_style.value}
- Tax Sophistication: {client_profile.tax_sophistication.value}

INSTRUCTIONS:
Write a {max_words}-word executive summary that:
1. Opens with a personalized greeting addressing their specific situation
2. Highlights the MOST IMPORTANT finding (biggest savings opportunity)
3. Provides context - how does their tax situation compare to expectations?
4. Lists top 2-3 actions they should prioritize
5. Ends with an encouraging next step

TONE: {client_profile.preferred_tone}
LANGUAGE LEVEL: Appropriate for {client_profile.tax_sophistication.value} tax knowledge

DO NOT:
- Use generic platitudes
- Include disclaimers (those go in a separate section)
- List every recommendation (focus on highlights)
- Use jargon without explanation (unless client is expert level)"""

    def _get_system_prompt(self, client_profile: ClientProfile) -> str:
        """Get system prompt for Claude based on client profile."""
        style_instructions = {
            CommunicationStyle.FORMAL: "Use formal, professional language. Address the client respectfully.",
            CommunicationStyle.CONVERSATIONAL: "Use warm, approachable language. Be friendly but professional.",
            CommunicationStyle.TECHNICAL: "Include technical details and industry terminology. Be precise.",
            CommunicationStyle.SIMPLIFIED: "Use simple, plain language. Avoid jargon. Explain all tax terms.",
        }

        sophistication_instructions = {
            TaxSophistication.NOVICE: "Explain all tax concepts. Use analogies. Avoid acronyms.",
            TaxSophistication.INTERMEDIATE: "Briefly explain complex concepts. Some tax terms are OK.",
            TaxSophistication.ADVANCED: "Can use tax terminology freely. Focus on strategy details.",
            TaxSophistication.EXPERT: "Use professional-level language. Focus on nuances and edge cases.",
        }

        return f"""You are a senior tax advisor writing personalized reports.

COMMUNICATION STYLE: {style_instructions.get(client_profile.communication_style)}
SOPHISTICATION LEVEL: {sophistication_instructions.get(client_profile.tax_sophistication)}

Your writing should:
- Feel personally written for THIS client, not templated
- Focus on actionable insights, not generic advice
- Be confident but not overpromising
- Cite specific dollar amounts when discussing savings
- Use the client's name naturally throughout

Always prioritize clarity over completeness."""

    def _extract_key_points(self, content: str) -> List[str]:
        """Extract key points from generated content."""
        lines = content.split("\n")
        key_points = []

        for line in lines:
            line = line.strip()
            # Look for bullet points, numbered items, or emphasized text
            if (
                line.startswith(("-", "*", "•")) or
                (len(line) > 2 and line[0].isdigit() and line[1] in ".)")
            ):
                # Clean up the line
                clean_line = line.lstrip("-*•0123456789.) ").strip()
                if clean_line and len(clean_line) > 10:
                    key_points.append(clean_line[:100])  # Limit length

        return key_points[:5]  # Return top 5 key points

    def _generate_fallback_summary(
        self,
        analysis: Dict[str, Any],
        client_profile: ClientProfile,
    ) -> GeneratedNarrative:
        """Generate fallback summary when AI is unavailable."""
        metrics = analysis.get("metrics", {})
        recommendations = analysis.get("recommendations", {})

        savings = metrics.get("potential_savings", 0)
        liability = metrics.get("current_tax_liability", 0)

        content = f"""Dear {client_profile.name},

Your {analysis.get('tax_year', 'current year')} tax analysis is complete.

Current Tax Position:
Your total tax liability is ${liability:,.2f}. Our analysis has identified ${savings:,.2f} in potential tax savings opportunities.

Top Recommendations:
We have {recommendations.get('total_count', 0)} recommendations for your consideration, with immediate action items that could meaningfully reduce your tax burden.

Next Steps:
Please review the detailed recommendations in this report and contact us to discuss implementation.

Best regards,
Your Tax Advisory Team"""

        return GeneratedNarrative(
            content=content,
            narrative_type="executive_summary",
            word_count=len(content.split()),
            key_points=["Tax analysis complete", f"${savings:,.2f} potential savings"],
            tone_used="default",
            metadata={"fallback": True},
        )

    def _generate_fallback_action_plan(
        self,
        action_items: List[Dict[str, Any]],
    ) -> GeneratedNarrative:
        """Generate fallback action plan when AI is unavailable."""
        lines = ["Your Tax Action Plan:\n"]

        for i, item in enumerate(action_items[:5], 1):
            lines.append(f"{i}. {item.get('title', 'Action item')}")
            if item.get("action"):
                lines.append(f"   Action: {item['action']}")
            if item.get("savings"):
                lines.append(f"   Potential savings: ${item['savings']:,.2f}")
            lines.append("")

        content = "\n".join(lines)

        return GeneratedNarrative(
            content=content,
            narrative_type="action_plan",
            word_count=len(content.split()),
            key_points=[a.get("title", "") for a in action_items[:3]],
            tone_used="default",
            metadata={"fallback": True},
        )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_narrative_generator: Optional[AINarrativeGenerator] = None


def get_narrative_generator() -> AINarrativeGenerator:
    """Get the singleton narrative generator instance."""
    global _narrative_generator
    if _narrative_generator is None:
        _narrative_generator = AINarrativeGenerator()
    return _narrative_generator


__all__ = [
    "AINarrativeGenerator",
    "ClientProfile",
    "CommunicationStyle",
    "TaxSophistication",
    "GeneratedNarrative",
    "get_narrative_generator",
]
