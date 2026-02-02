"""
AI-Powered Client Research for CPA Panel.

Uses Perplexity for real-time client and business research including:
- Business client background research
- Industry trend identification
- Competitive landscape analysis
- News and event monitoring
- Financial health indicators
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class ResearchDepth(Enum):
    """Research depth levels."""
    QUICK = "quick"  # Basic overview (1-2 queries)
    STANDARD = "standard"  # Moderate depth (3-5 queries)
    COMPREHENSIVE = "comprehensive"  # Full research (5-10 queries)


class IndustryTrendSignal(Enum):
    """Industry trend signals."""
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    DISRUPTED = "disrupted"
    EMERGING = "emerging"


class FinancialHealthIndicator(Enum):
    """Financial health indicators."""
    STRONG = "strong"
    HEALTHY = "healthy"
    MODERATE = "moderate"
    CONCERNING = "concerning"
    DISTRESSED = "distressed"
    UNKNOWN = "unknown"


@dataclass
class CompanyProfile:
    """Research profile for a company."""
    company_name: str
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    founded_year: Optional[int] = None
    headquarters: Optional[str] = None
    employee_count: Optional[str] = None
    revenue_range: Optional[str] = None
    business_model: Optional[str] = None
    key_products_services: List[str] = field(default_factory=list)
    target_market: Optional[str] = None
    competitive_position: Optional[str] = None


@dataclass
class IndustryInsight:
    """Industry trend and insight."""
    trend_name: str
    description: str
    signal: IndustryTrendSignal
    relevance_to_client: str
    tax_implications: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)


@dataclass
class NewsItem:
    """News or event item."""
    headline: str
    summary: str
    date: Optional[str] = None
    source: Optional[str] = None
    relevance: str = "medium"  # high, medium, low
    tax_relevance: Optional[str] = None
    action_required: bool = False


@dataclass
class CompetitorInfo:
    """Competitor information."""
    name: str
    description: str
    market_position: Optional[str] = None
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)


@dataclass
class FinancialIndicators:
    """Financial health indicators."""
    overall_health: FinancialHealthIndicator
    revenue_trend: Optional[str] = None
    profitability_signals: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    growth_indicators: List[str] = field(default_factory=list)
    confidence_level: float = 0.0


@dataclass
class TaxConsiderations:
    """Tax considerations based on research."""
    entity_type_suggestions: List[str] = field(default_factory=list)
    deduction_opportunities: List[str] = field(default_factory=list)
    compliance_considerations: List[str] = field(default_factory=list)
    planning_opportunities: List[str] = field(default_factory=list)
    industry_specific_credits: List[str] = field(default_factory=list)


@dataclass
class ClientResearchResult:
    """Complete client research result."""
    client_name: str
    research_timestamp: datetime
    research_depth: ResearchDepth
    company_profile: Optional[CompanyProfile] = None
    industry_insights: List[IndustryInsight] = field(default_factory=list)
    recent_news: List[NewsItem] = field(default_factory=list)
    competitors: List[CompetitorInfo] = field(default_factory=list)
    financial_indicators: Optional[FinancialIndicators] = None
    tax_considerations: Optional[TaxConsiderations] = None
    key_talking_points: List[str] = field(default_factory=list)
    questions_to_ask: List[str] = field(default_factory=list)
    research_sources: List[str] = field(default_factory=list)
    ai_confidence: float = 0.0
    raw_research: Optional[str] = None


class PerplexityClientResearcher:
    """
    AI-powered client research using Perplexity for real-time intelligence.

    Provides comprehensive business research for CPA client preparation
    and relationship management.
    """

    # Perplexity uses OpenAI-compatible API
    PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
    DEFAULT_MODEL = "llama-3.1-sonar-large-128k-online"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the client researcher.

        Args:
            api_key: Perplexity API key. If not provided, uses PERPLEXITY_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        self._client: Optional[Any] = None

    @property
    def client(self):
        """Lazy-load the Perplexity client (OpenAI compatible)."""
        if self._client is None:
            if not OPENAI_AVAILABLE:
                raise ImportError("openai package not installed. Run: pip install openai")
            if not self.api_key:
                raise ValueError("PERPLEXITY_API_KEY not configured")
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.PERPLEXITY_BASE_URL
            )
        return self._client

    def research_client(
        self,
        client_name: str,
        company_name: Optional[str] = None,
        industry: Optional[str] = None,
        location: Optional[str] = None,
        depth: ResearchDepth = ResearchDepth.STANDARD
    ) -> ClientResearchResult:
        """
        Perform comprehensive client research.

        Args:
            client_name: Name of the client/contact.
            company_name: Business name if applicable.
            industry: Industry hint for better research.
            location: Geographic location for context.
            depth: Research depth level.

        Returns:
            ClientResearchResult with comprehensive research.
        """
        research_target = company_name or client_name

        try:
            # Build research based on depth
            results = []

            # Always get company profile
            profile = self._research_company_profile(research_target, industry, location)
            results.append(("profile", profile))

            if depth in (ResearchDepth.STANDARD, ResearchDepth.COMPREHENSIVE):
                # Get industry insights
                industry_insights = self._research_industry_trends(
                    profile.get("industry", industry or "general business")
                )
                results.append(("industry", industry_insights))

                # Get recent news
                news = self._research_recent_news(research_target)
                results.append(("news", news))

            if depth == ResearchDepth.COMPREHENSIVE:
                # Get competitive landscape
                competitors = self._research_competitors(
                    research_target,
                    profile.get("industry", industry)
                )
                results.append(("competitors", competitors))

                # Get financial indicators
                financial = self._research_financial_health(research_target)
                results.append(("financial", financial))

            return self._compile_research_result(
                client_name, research_target, depth, results
            )

        except Exception as e:
            return ClientResearchResult(
                client_name=client_name,
                research_timestamp=datetime.now(),
                research_depth=depth,
                key_talking_points=[f"Research error: {str(e)}"],
                ai_confidence=0.0,
                raw_research=str(e)
            )

    def research_industry_trends(
        self,
        industry: str,
        focus_areas: Optional[List[str]] = None
    ) -> List[IndustryInsight]:
        """
        Research industry trends and developments.

        Args:
            industry: Industry to research.
            focus_areas: Specific areas to focus on.

        Returns:
            List of IndustryInsight objects.
        """
        focus_str = ", ".join(focus_areas) if focus_areas else "general trends, tax implications, growth areas"

        query = f"""Research current trends in the {industry} industry.

Focus on: {focus_str}

Provide:
1. Key industry trends (growth/decline signals)
2. Tax and regulatory implications
3. Opportunities for businesses
4. Recent developments

Format as detailed analysis with specific facts and statistics."""

        try:
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": query}]
            )

            content = response.choices[0].message.content

            # Parse into structured insights
            return self._parse_industry_insights(content, industry)

        except Exception:
            return []

    def monitor_client_news(
        self,
        company_name: str,
        days_back: int = 30
    ) -> List[NewsItem]:
        """
        Monitor recent news about a client.

        Args:
            company_name: Company to monitor.
            days_back: How many days of news to retrieve.

        Returns:
            List of relevant NewsItem objects.
        """
        query = f"""Find recent news and developments about "{company_name}" from the past {days_back} days.

Include:
1. Major announcements
2. Financial news
3. Industry developments affecting them
4. Leadership changes
5. Regulatory or compliance news

For each item note tax relevance if applicable."""

        try:
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": query}]
            )

            content = response.choices[0].message.content
            return self._parse_news_items(content)

        except Exception:
            return []

    def research_tax_implications(
        self,
        business_type: str,
        industry: str,
        recent_events: Optional[List[str]] = None
    ) -> TaxConsiderations:
        """
        Research tax implications for a business.

        Args:
            business_type: Type of business entity.
            industry: Industry sector.
            recent_events: Recent events to consider.

        Returns:
            TaxConsiderations with relevant insights.
        """
        events_str = "\n".join(recent_events) if recent_events else "No specific events"

        query = f"""Research tax considerations for a {business_type} in the {industry} industry.

Recent events/changes:
{events_str}

Provide:
1. Entity structure optimization suggestions
2. Available deductions specific to this industry
3. Compliance requirements and deadlines
4. Tax planning opportunities
5. Industry-specific tax credits or incentives

Focus on current 2025/2026 tax law."""

        try:
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": query}]
            )

            content = response.choices[0].message.content
            return self._parse_tax_considerations(content)

        except Exception:
            return TaxConsiderations()

    def generate_meeting_prep(
        self,
        research_result: ClientResearchResult
    ) -> Dict[str, Any]:
        """
        Generate meeting preparation materials from research.

        Args:
            research_result: Previous research result.

        Returns:
            Meeting prep materials including agenda, talking points, questions.
        """
        # Compile key info
        company_info = ""
        if research_result.company_profile:
            cp = research_result.company_profile
            company_info = f"""
Company: {cp.company_name}
Industry: {cp.industry or 'Unknown'}
Size: {cp.employee_count or 'Unknown'}
Revenue: {cp.revenue_range or 'Unknown'}
"""

        query = f"""Create meeting preparation materials for a CPA meeting with this client.

CLIENT RESEARCH:
{company_info}

KEY INSIGHTS:
{chr(10).join(research_result.key_talking_points[:5])}

RECENT NEWS:
{chr(10).join([n.headline for n in research_result.recent_news[:3]])}

TAX CONSIDERATIONS:
{json.dumps(research_result.tax_considerations.__dict__ if research_result.tax_considerations else {}, indent=2)}

Generate:
1. Meeting agenda (5-7 items)
2. Key talking points
3. Questions to ask the client
4. Value propositions to highlight
5. Potential concerns to address
6. Follow-up action items

Format as structured JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": query}]
            )

            content = response.choices[0].message.content

            # Try to parse JSON
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])

            # Return structured content if JSON parsing fails
            return {
                "agenda": ["Review current tax situation", "Discuss business developments",
                          "Identify planning opportunities", "Address questions"],
                "talking_points": research_result.key_talking_points,
                "questions": research_result.questions_to_ask,
                "raw_prep": content
            }

        except Exception as e:
            return {
                "error": str(e),
                "talking_points": research_result.key_talking_points,
                "questions": research_result.questions_to_ask
            }

    def _research_company_profile(
        self,
        company_name: str,
        industry_hint: Optional[str],
        location: Optional[str]
    ) -> Dict[str, Any]:
        """Research basic company profile."""
        location_str = f" in {location}" if location else ""
        industry_str = f" ({industry_hint} industry)" if industry_hint else ""

        query = f"""Research the company "{company_name}"{industry_str}{location_str}.

Provide:
1. Industry and sub-industry
2. Business model and main products/services
3. Approximate size (employees, revenue range)
4. Target market
5. Competitive position
6. Year founded (if available)

Be specific with facts when available, note uncertainty when guessing."""

        try:
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": query}]
            )

            content = response.choices[0].message.content

            # Parse into profile dict
            return {
                "company_name": company_name,
                "industry": industry_hint,
                "raw_profile": content
            }

        except Exception:
            return {"company_name": company_name, "industry": industry_hint}

    def _research_industry_trends(self, industry: str) -> Dict[str, Any]:
        """Research industry trends."""
        query = f"""What are the current trends and outlook for the {industry} industry in 2025-2026?

Include:
1. Growth or decline signals
2. Major disruptors or changes
3. Regulatory environment
4. Tax law changes affecting this industry"""

        try:
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": query}]
            )

            return {"industry": industry, "trends": response.choices[0].message.content}

        except Exception:
            return {"industry": industry, "trends": "Unable to research"}

    def _research_recent_news(self, company_name: str) -> Dict[str, Any]:
        """Research recent news about company."""
        query = f"""Find recent news about "{company_name}" from the past 90 days.

Include business developments, financial news, and any regulatory matters."""

        try:
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": query}]
            )

            return {"company": company_name, "news": response.choices[0].message.content}

        except Exception:
            return {"company": company_name, "news": "No recent news found"}

    def _research_competitors(
        self,
        company_name: str,
        industry: Optional[str]
    ) -> Dict[str, Any]:
        """Research competitive landscape."""
        industry_str = f" in the {industry} industry" if industry else ""

        query = f"""Who are the main competitors of "{company_name}"{industry_str}?

For each competitor provide:
1. Name and brief description
2. Market position
3. Key strengths and weaknesses"""

        try:
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": query}]
            )

            return {"competitors": response.choices[0].message.content}

        except Exception:
            return {"competitors": "Unable to research"}

    def _research_financial_health(self, company_name: str) -> Dict[str, Any]:
        """Research financial health indicators."""
        query = f"""What are the financial health indicators for "{company_name}"?

Look for:
1. Revenue trends
2. Profitability signals
3. Growth indicators
4. Any financial concerns or risks
5. Recent funding or financial events

Note: For private companies, use available public information and industry benchmarks."""

        try:
            response = self.client.chat.completions.create(
                model=self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": query}]
            )

            return {"financial": response.choices[0].message.content}

        except Exception:
            return {"financial": "Unable to research"}

    def _compile_research_result(
        self,
        client_name: str,
        company_name: str,
        depth: ResearchDepth,
        results: List[tuple]
    ) -> ClientResearchResult:
        """Compile all research into final result."""
        result = ClientResearchResult(
            client_name=client_name,
            research_timestamp=datetime.now(),
            research_depth=depth,
            ai_confidence=0.7
        )

        raw_research = []

        for result_type, data in results:
            raw_research.append(f"=== {result_type.upper()} ===\n{json.dumps(data, indent=2)}")

            if result_type == "profile":
                result.company_profile = CompanyProfile(
                    company_name=company_name,
                    industry=data.get("industry")
                )

            elif result_type == "industry":
                result.industry_insights = self._parse_industry_insights(
                    data.get("trends", ""), data.get("industry", "")
                )

            elif result_type == "news":
                result.recent_news = self._parse_news_items(data.get("news", ""))

            elif result_type == "competitors":
                result.competitors = self._parse_competitors(data.get("competitors", ""))

            elif result_type == "financial":
                result.financial_indicators = self._parse_financial_indicators(
                    data.get("financial", "")
                )

        result.raw_research = "\n\n".join(raw_research)

        # Generate talking points and questions
        result.key_talking_points = self._generate_talking_points(result)
        result.questions_to_ask = self._generate_questions(result)

        return result

    def _parse_industry_insights(self, content: str, industry: str) -> List[IndustryInsight]:
        """Parse industry insights from research content."""
        # Simple parsing - in production, would use more sophisticated NLP
        insights = []

        if "growth" in content.lower() or "growing" in content.lower():
            insights.append(IndustryInsight(
                trend_name="Industry Growth",
                description=f"The {industry} industry shows growth signals",
                signal=IndustryTrendSignal.GROWING,
                relevance_to_client="Potential for business expansion",
                tax_implications=["Higher income may affect tax brackets"],
                opportunities=["Expansion planning", "R&D credits"]
            ))

        if "regulation" in content.lower() or "compliance" in content.lower():
            insights.append(IndustryInsight(
                trend_name="Regulatory Environment",
                description="Regulatory changes affecting the industry",
                signal=IndustryTrendSignal.STABLE,
                relevance_to_client="Compliance requirements may change",
                tax_implications=["New compliance costs may be deductible"],
                opportunities=["Compliance consulting", "Process optimization"]
            ))

        return insights

    def _parse_news_items(self, content: str) -> List[NewsItem]:
        """Parse news items from research content."""
        # Simple extraction - would be more sophisticated in production
        news_items = []

        if content and len(content) > 50:
            # Create a summary news item
            news_items.append(NewsItem(
                headline="Recent Developments",
                summary=content[:500] if len(content) > 500 else content,
                relevance="medium"
            ))

        return news_items

    def _parse_competitors(self, content: str) -> List[CompetitorInfo]:
        """Parse competitor information from research content."""
        competitors = []

        if content and len(content) > 20:
            competitors.append(CompetitorInfo(
                name="Industry Competitors",
                description=content[:300] if len(content) > 300 else content
            ))

        return competitors

    def _parse_financial_indicators(self, content: str) -> FinancialIndicators:
        """Parse financial indicators from research content."""
        health = FinancialHealthIndicator.UNKNOWN

        content_lower = content.lower()
        if "strong" in content_lower or "healthy" in content_lower:
            health = FinancialHealthIndicator.HEALTHY
        elif "concern" in content_lower or "risk" in content_lower:
            health = FinancialHealthIndicator.CONCERNING
        elif "growth" in content_lower:
            health = FinancialHealthIndicator.STRONG

        return FinancialIndicators(
            overall_health=health,
            confidence_level=0.5
        )

    def _parse_tax_considerations(self, content: str) -> TaxConsiderations:
        """Parse tax considerations from research content."""
        considerations = TaxConsiderations()

        # Extract mentions of specific tax items
        if "deduction" in content.lower():
            considerations.deduction_opportunities.append(
                "Review industry-specific deductions mentioned in research"
            )

        if "credit" in content.lower():
            considerations.industry_specific_credits.append(
                "Potential tax credits identified - requires detailed analysis"
            )

        if "compliance" in content.lower():
            considerations.compliance_considerations.append(
                "Compliance requirements noted - review with client"
            )

        return considerations

    def _generate_talking_points(self, result: ClientResearchResult) -> List[str]:
        """Generate talking points from research."""
        points = []

        if result.company_profile and result.company_profile.industry:
            points.append(f"Industry expertise in {result.company_profile.industry}")

        if result.industry_insights:
            for insight in result.industry_insights[:2]:
                points.append(f"{insight.trend_name}: {insight.relevance_to_client}")

        if result.recent_news:
            points.append("Recent developments show active business growth")

        if result.financial_indicators:
            health = result.financial_indicators.overall_health.value
            points.append(f"Financial health appears {health}")

        # Default points
        if not points:
            points = [
                "Personalized tax strategy development",
                "Industry-specific deduction opportunities",
                "Proactive tax planning approach"
            ]

        return points

    def _generate_questions(self, result: ClientResearchResult) -> List[str]:
        """Generate questions to ask based on research."""
        questions = [
            "What are your primary business goals for the next 12-24 months?",
            "What's your biggest tax concern or frustration currently?",
            "How has your business changed since your last tax filing?",
        ]

        if result.company_profile and result.company_profile.industry:
            questions.append(
                f"How are trends in the {result.company_profile.industry} "
                "industry affecting your business?"
            )

        if result.recent_news:
            questions.append(
                "Can you tell me more about the recent developments in your business?"
            )

        return questions


# Singleton instance
_client_researcher: Optional[PerplexityClientResearcher] = None


def get_client_researcher() -> PerplexityClientResearcher:
    """Get the singleton PerplexityClientResearcher instance."""
    global _client_researcher
    if _client_researcher is None:
        _client_researcher = PerplexityClientResearcher()
    return _client_researcher


__all__ = [
    "PerplexityClientResearcher",
    "get_client_researcher",
    "ClientResearchResult",
    "CompanyProfile",
    "IndustryInsight",
    "NewsItem",
    "CompetitorInfo",
    "FinancialIndicators",
    "TaxConsiderations",
    "ResearchDepth",
    "IndustryTrendSignal",
    "FinancialHealthIndicator",
]
