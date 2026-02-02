"""
Tax Research Service.

Specialized research service for tax-related queries using Perplexity AI
for real-time access to:
- IRS regulations and publications
- Tax court cases and rulings
- State tax information
- Current year tax limits and thresholds
- Recent tax law changes

Usage:
    from services.ai.tax_research_service import get_tax_research_service

    research = get_tax_research_service()

    # Research current limits
    result = await research.get_tax_limits(2025, "401k")

    # Research IRS guidance
    guidance = await research.research_irs_guidance("home office deduction")

    # Research state tax
    state_info = await research.research_state_tax("CA", "LLC taxation")
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from config.ai_providers import AIProvider, ModelCapability
from services.ai.unified_ai_service import (
    UnifiedAIService,
    AIResponse,
    get_ai_service,
)

logger = logging.getLogger(__name__)


class ResearchCategory(str, Enum):
    """Categories of tax research."""
    IRS_GUIDANCE = "irs_guidance"
    TAX_LIMITS = "tax_limits"
    TAX_COURT = "tax_court"
    STATE_TAX = "state_tax"
    TAX_FORMS = "tax_forms"
    TAX_NEWS = "tax_news"
    GENERAL = "general"


@dataclass
class ResearchResult:
    """Structured research result."""
    query: str
    category: ResearchCategory
    summary: str
    key_points: List[str]
    sources: List[str]
    citations: List[str]
    effective_date: Optional[str]
    confidence: float
    raw_response: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaxLimit:
    """A specific tax limit or threshold."""
    name: str
    amount: float
    tax_year: int
    description: str
    phase_out_start: Optional[float] = None
    phase_out_end: Optional[float] = None
    source: str = "IRS"


# =============================================================================
# TAX-SPECIFIC PROMPTS
# =============================================================================

RESEARCH_SYSTEM_PROMPT = """You are an expert tax research assistant with access to current IRS
guidance, tax publications, court cases, and authoritative tax sources.

CRITICAL REQUIREMENTS:
1. ALWAYS cite specific sources (IRS Publication numbers, IRC sections, court cases)
2. Include effective dates for all information
3. Distinguish between current law and proposed changes
4. Note any phase-outs or income limitations
5. Identify if information varies by filing status
6. Flag areas of ambiguity or ongoing IRS guidance

When citing sources, use this format:
- IRS publications: "IRS Publication 17, Tax Year 2025"
- Tax code: "IRC Section 401(k)"
- Court cases: "Case Name, Court, Year"
- Revenue rulings: "Rev. Rul. XXXX-XX"

Structure your response with:
1. Direct answer to the question
2. Key details and limitations
3. Relevant thresholds or phase-outs
4. Source citations
5. Any caveats or considerations"""


IRS_GUIDANCE_PROMPT = """Research the following IRS guidance topic. Provide:
1. Current IRS position and applicable rules
2. Relevant IRC sections
3. Key IRS publications that address this topic
4. Recent changes or updates
5. Common compliance issues

Topic: {topic}
Context: {context}"""


TAX_LIMITS_PROMPT = """Provide the current tax limits and thresholds for {tax_year}.
Focus on: {category}

Include:
1. Exact dollar amounts
2. Phase-out ranges by filing status
3. Inflation adjustments from prior year
4. Any special rules or exceptions
5. Source citations (IRS announcement numbers)

Present limits in a clear, structured format."""


STATE_TAX_PROMPT = """Research state tax rules for {state}.
Topic: {topic}

Provide:
1. State-specific rules and rates
2. Differences from federal treatment
3. Filing requirements
4. Key deadlines
5. Recent state tax law changes
6. Links to official state tax authority guidance"""


TAX_COURT_PROMPT = """Research tax court cases and rulings related to:
{topic}

Include:
1. Relevant recent cases (last 5 years preferred)
2. Key holdings and precedents
3. IRS position in these cases
4. Implications for taxpayers
5. Any Circuit Court splits or evolving positions"""


# =============================================================================
# TAX RESEARCH SERVICE
# =============================================================================

class TaxResearchService:
    """
    Specialized service for tax research using Perplexity.

    Features:
    - Real-time IRS guidance research
    - Tax limit lookups
    - State tax research
    - Tax court case research
    - Structured research results with citations
    """

    def __init__(self, ai_service: Optional[UnifiedAIService] = None):
        self.ai_service = ai_service or get_ai_service()
        self._cache: Dict[str, ResearchResult] = {}
        self._cache_ttl_seconds = 3600  # 1 hour cache

    async def research(
        self,
        query: str,
        category: ResearchCategory = ResearchCategory.GENERAL,
        context: Optional[str] = None,
        use_cache: bool = True
    ) -> ResearchResult:
        """
        Perform general tax research.

        Args:
            query: Research question
            category: Research category for specialized prompts
            context: Additional context
            use_cache: Whether to use cached results

        Returns:
            ResearchResult with structured findings
        """
        cache_key = f"{category.value}:{query}"

        # Check cache
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            age = (datetime.now() - cached.timestamp).total_seconds()
            if age < self._cache_ttl_seconds:
                logger.debug(f"Cache hit for research query: {query[:50]}...")
                return cached

        # Build prompt based on category
        prompt = self._build_research_prompt(query, category, context)

        # Execute research
        response = await self.ai_service.research(prompt)

        # Parse and structure result
        result = self._parse_research_response(
            query=query,
            category=category,
            response=response
        )

        # Cache result
        self._cache[cache_key] = result

        return result

    async def research_irs_guidance(
        self,
        topic: str,
        context: Optional[str] = None
    ) -> ResearchResult:
        """
        Research IRS guidance on a specific topic.

        Args:
            topic: The tax topic to research
            context: Optional additional context

        Returns:
            ResearchResult with IRS guidance
        """
        prompt = IRS_GUIDANCE_PROMPT.format(
            topic=topic,
            context=context or "General research"
        )

        response = await self.ai_service.research(prompt)

        return self._parse_research_response(
            query=f"IRS guidance on: {topic}",
            category=ResearchCategory.IRS_GUIDANCE,
            response=response
        )

    async def get_tax_limits(
        self,
        tax_year: int,
        category: str = "all"
    ) -> ResearchResult:
        """
        Get current tax limits and thresholds.

        Args:
            tax_year: The tax year
            category: Specific category (e.g., "401k", "ira", "health", "all")

        Returns:
            ResearchResult with tax limits
        """
        prompt = TAX_LIMITS_PROMPT.format(
            tax_year=tax_year,
            category=category
        )

        response = await self.ai_service.research(prompt)

        result = self._parse_research_response(
            query=f"Tax limits for {tax_year}: {category}",
            category=ResearchCategory.TAX_LIMITS,
            response=response
        )

        # Add year to metadata
        result.metadata["tax_year"] = tax_year
        result.metadata["limit_category"] = category

        return result

    async def research_state_tax(
        self,
        state: str,
        topic: str
    ) -> ResearchResult:
        """
        Research state-specific tax rules.

        Args:
            state: State abbreviation (e.g., "CA", "NY")
            topic: Specific topic to research

        Returns:
            ResearchResult with state tax information
        """
        prompt = STATE_TAX_PROMPT.format(
            state=state,
            topic=topic
        )

        response = await self.ai_service.research(prompt)

        result = self._parse_research_response(
            query=f"{state} state tax: {topic}",
            category=ResearchCategory.STATE_TAX,
            response=response
        )

        result.metadata["state"] = state

        return result

    async def research_tax_court(
        self,
        topic: str
    ) -> ResearchResult:
        """
        Research tax court cases and rulings.

        Args:
            topic: Legal topic to research

        Returns:
            ResearchResult with case law information
        """
        prompt = TAX_COURT_PROMPT.format(topic=topic)

        response = await self.ai_service.research(prompt)

        return self._parse_research_response(
            query=f"Tax court research: {topic}",
            category=ResearchCategory.TAX_COURT,
            response=response
        )

    async def get_form_instructions(
        self,
        form_number: str,
        tax_year: int
    ) -> ResearchResult:
        """
        Get IRS form instructions and guidance.

        Args:
            form_number: IRS form number (e.g., "1040", "Schedule C")
            tax_year: Tax year

        Returns:
            ResearchResult with form instructions
        """
        prompt = f"""Provide a summary of IRS Form {form_number} for tax year {tax_year}.

Include:
1. Purpose of the form
2. Who must file it
3. Key sections and what they cover
4. Common mistakes to avoid
5. Related forms or schedules
6. Important deadlines
7. Link to official IRS form and instructions"""

        response = await self.ai_service.research(prompt)

        result = self._parse_research_response(
            query=f"Form {form_number} ({tax_year})",
            category=ResearchCategory.TAX_FORMS,
            response=response
        )

        result.metadata["form_number"] = form_number
        result.metadata["tax_year"] = tax_year

        return result

    async def get_recent_tax_news(
        self,
        topic: Optional[str] = None
    ) -> ResearchResult:
        """
        Get recent tax news and updates.

        Args:
            topic: Optional specific topic to focus on

        Returns:
            ResearchResult with recent tax news
        """
        topic_clause = f" specifically about {topic}" if topic else ""
        prompt = f"""What are the most recent tax news and updates{topic_clause}?

Focus on:
1. Recent IRS announcements or guidance
2. Tax law changes effective this year or next
3. Important deadlines coming up
4. Significant tax court decisions
5. Proposed legislation that could affect taxpayers

Only include news from the last 30 days or major ongoing developments."""

        response = await self.ai_service.research(prompt)

        return self._parse_research_response(
            query=f"Recent tax news{topic_clause}",
            category=ResearchCategory.TAX_NEWS,
            response=response
        )

    def _build_research_prompt(
        self,
        query: str,
        category: ResearchCategory,
        context: Optional[str]
    ) -> str:
        """Build category-specific research prompt."""
        context_clause = f"\n\nAdditional context: {context}" if context else ""

        base_prompts = {
            ResearchCategory.IRS_GUIDANCE: f"Research IRS guidance on: {query}",
            ResearchCategory.TAX_LIMITS: f"Find current tax limits for: {query}",
            ResearchCategory.TAX_COURT: f"Research tax court cases about: {query}",
            ResearchCategory.STATE_TAX: f"Research state tax rules for: {query}",
            ResearchCategory.TAX_FORMS: f"Explain IRS form: {query}",
            ResearchCategory.TAX_NEWS: f"Recent tax news about: {query}",
            ResearchCategory.GENERAL: query,
        }

        base = base_prompts.get(category, query)
        return base + context_clause

    def _parse_research_response(
        self,
        query: str,
        category: ResearchCategory,
        response: AIResponse
    ) -> ResearchResult:
        """Parse AI response into structured ResearchResult."""
        content = response.content

        # Extract key points (look for numbered lists or bullet points)
        key_points = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            # Match numbered items or bullet points
            if (line and (line[0].isdigit() or line.startswith('-') or line.startswith('•'))):
                # Clean up the line
                cleaned = line.lstrip('0123456789.-•) ').strip()
                if cleaned and len(cleaned) > 10:
                    key_points.append(cleaned[:200])  # Limit length

        # Extract citations from metadata or content
        citations = response.metadata.get("citations", [])
        if not citations:
            # Try to extract citations from content
            citations = self._extract_citations(content)

        # Estimate confidence based on citation count and response quality
        confidence = self._estimate_confidence(content, citations)

        return ResearchResult(
            query=query,
            category=category,
            summary=self._extract_summary(content),
            key_points=key_points[:10],  # Limit to 10 key points
            sources=citations[:5],  # Top 5 sources
            citations=citations,
            effective_date=self._extract_date(content),
            confidence=confidence,
            raw_response=content,
            metadata={
                "model": response.model,
                "provider": response.provider.value,
                "tokens": response.input_tokens + response.output_tokens,
                "latency_ms": response.latency_ms,
            }
        )

    def _extract_summary(self, content: str) -> str:
        """Extract a summary from the response."""
        # Take first paragraph or first 500 characters
        paragraphs = content.split('\n\n')
        if paragraphs:
            first_para = paragraphs[0].strip()
            if len(first_para) > 500:
                return first_para[:500] + "..."
            return first_para
        return content[:500] + "..." if len(content) > 500 else content

    def _extract_citations(self, content: str) -> List[str]:
        """Extract citations from content."""
        citations = []

        # Common citation patterns
        import re

        # IRS Publications
        pubs = re.findall(r'IRS Publication \d+', content, re.IGNORECASE)
        citations.extend(pubs)

        # IRC Sections
        ircs = re.findall(r'IRC (?:Section |§)?\d+(?:\([a-z]\))?', content, re.IGNORECASE)
        citations.extend(ircs)

        # Revenue Rulings
        revs = re.findall(r'Rev\. Rul\. \d{4}-\d+', content, re.IGNORECASE)
        citations.extend(revs)

        # Treasury Regulations
        tregs = re.findall(r'Treas\. Reg\. (?:§)?[\d.]+', content, re.IGNORECASE)
        citations.extend(tregs)

        return list(set(citations))

    def _extract_date(self, content: str) -> Optional[str]:
        """Extract effective date from content."""
        import re

        # Look for year patterns
        year_pattern = r'(?:tax year|effective|for)\s+(\d{4})'
        match = re.search(year_pattern, content, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _estimate_confidence(
        self,
        content: str,
        citations: List[str]
    ) -> float:
        """Estimate confidence in the research result."""
        confidence = 0.5  # Base confidence

        # More citations = higher confidence
        if len(citations) > 5:
            confidence += 0.2
        elif len(citations) > 2:
            confidence += 0.1

        # Longer, detailed responses = higher confidence
        if len(content) > 2000:
            confidence += 0.1
        elif len(content) > 1000:
            confidence += 0.05

        # Specific IRS references boost confidence
        if 'IRS Publication' in content or 'IRC Section' in content:
            confidence += 0.1

        # Uncertainty markers decrease confidence
        uncertainty_markers = ['unclear', 'uncertain', 'may vary', 'consult', 'depends']
        for marker in uncertainty_markers:
            if marker.lower() in content.lower():
                confidence -= 0.05

        return max(0.1, min(1.0, confidence))

    def clear_cache(self):
        """Clear the research cache."""
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "cache_ttl_seconds": self._cache_ttl_seconds,
            "categories_cached": list(set(
                k.split(':')[0] for k in self._cache.keys()
            ))
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_tax_research_service: Optional[TaxResearchService] = None


def get_tax_research_service() -> TaxResearchService:
    """Get the singleton tax research service instance."""
    global _tax_research_service
    if _tax_research_service is None:
        _tax_research_service = TaxResearchService()
    return _tax_research_service


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "TaxResearchService",
    "ResearchCategory",
    "ResearchResult",
    "TaxLimit",
    "get_tax_research_service",
]
