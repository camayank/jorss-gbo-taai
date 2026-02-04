"""
AI-Powered Report Summarizer for Tax Advisory Reports.

Uses OpenAI for generating multi-level summaries:
- One-liner: Key finding in ~15 words
- Tweet-length: Highlights in 280 characters
- Executive: 1-page overview (~300 words)
- Detailed: Full analysis with all sections

Usage:
    from advisory.report_summarizer import get_report_summarizer

    summarizer = get_report_summarizer()
    summaries = await summarizer.generate_all_summaries(report_data)

    print(summaries.one_liner)  # "You could save $12,450 this year"
    print(summaries.tweet)      # Tweet-length summary
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


class SummaryLevel(str, Enum):
    """Summary detail levels."""
    ONE_LINER = "one_liner"       # ~15 words
    TWEET = "tweet"               # 280 characters max
    EXECUTIVE = "executive"       # ~300 words
    DETAILED = "detailed"         # Full summary


@dataclass
class ReportSummary:
    """A single summary at a specific level."""
    level: SummaryLevel
    content: str
    word_count: int
    char_count: int
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "content": self.content,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "key_metrics": self.key_metrics,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class MultiLevelSummaries:
    """Collection of summaries at all levels."""
    one_liner: str
    tweet: str
    executive: str
    detailed: str
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "one_liner": self.one_liner,
            "tweet": self.tweet,
            "executive": self.executive,
            "detailed": self.detailed,
            "key_metrics": self.key_metrics,
            "generated_at": self.generated_at.isoformat(),
        }

    def get_summary(self, level: SummaryLevel) -> str:
        """Get summary at specified level."""
        mapping = {
            SummaryLevel.ONE_LINER: self.one_liner,
            SummaryLevel.TWEET: self.tweet,
            SummaryLevel.EXECUTIVE: self.executive,
            SummaryLevel.DETAILED: self.detailed,
        }
        return mapping.get(level, self.executive)


class AIReportSummarizer:
    """
    AI-powered report summarizer using OpenAI.

    Generates summaries at multiple levels of detail:
    - Optimized for different contexts (dashboards, emails, reports)
    - Preserves key metrics and action items
    - Maintains consistent messaging across levels
    """

    def __init__(self, ai_service=None):
        """
        Initialize report summarizer.

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

    async def generate_all_summaries(
        self,
        report_data: Dict[str, Any],
        taxpayer_name: Optional[str] = None,
    ) -> MultiLevelSummaries:
        """
        Generate summaries at all levels.

        Args:
            report_data: Full report data
            taxpayer_name: Optional taxpayer name for personalization

        Returns:
            MultiLevelSummaries with all summary levels
        """
        cache_key = self._cache_key("all_summaries", report_data, taxpayer_name)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Extract key metrics for consistent reference
        key_metrics = self._extract_key_metrics(report_data)

        # Generate each level
        one_liner = await self.generate_one_liner(report_data, key_metrics)
        tweet = await self.generate_tweet_summary(report_data, key_metrics)
        executive = await self.generate_executive_summary(
            report_data, key_metrics, taxpayer_name
        )
        detailed = await self.generate_detailed_summary(
            report_data, key_metrics, taxpayer_name
        )

        result = MultiLevelSummaries(
            one_liner=one_liner,
            tweet=tweet,
            executive=executive,
            detailed=detailed,
            key_metrics=key_metrics,
        )

        self._set_cached(cache_key, result)
        return result

    async def generate_one_liner(
        self,
        report_data: Dict[str, Any],
        key_metrics: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a one-liner summary (~15 words).

        Focus on the single most impactful finding.

        Args:
            report_data: Full report data
            key_metrics: Pre-extracted key metrics

        Returns:
            One-liner summary string
        """
        cache_key = self._cache_key("one_liner", report_data)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if key_metrics is None:
            key_metrics = self._extract_key_metrics(report_data)

        prompt = f"""Create a single-sentence summary (max 15 words) of this tax analysis.

KEY METRICS:
- Total Tax: ${key_metrics.get('total_tax', 0):,.0f}
- Potential Savings: ${key_metrics.get('potential_savings', 0):,.0f}
- Top Opportunity: {key_metrics.get('top_opportunity', 'N/A')}
- Action Items: {key_metrics.get('action_count', 0)}

Rules:
1. Focus on the MOST IMPACTFUL finding (usually savings or action)
2. Include a specific dollar amount if savings exist
3. Make it compelling and actionable
4. Maximum 15 words

Examples of good one-liners:
- "You could save $12,450 this year by maximizing retirement contributions"
- "Three immediate actions could reduce your tax bill by $8,200"
- "Your S-Corp election would save $15,000 annually in self-employment taxes"

Generate ONLY the one-liner, no explanation:"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.OPENAI,
                max_tokens=50,
            )

            content = response.content.strip().strip('"\'')
            # Ensure it's not too long
            words = content.split()
            if len(words) > 20:
                content = " ".join(words[:15]) + "..."

            self._set_cached(cache_key, content)
            return content

        except Exception as e:
            logger.error(f"Failed to generate one-liner: {e}")
            return self._fallback_one_liner(key_metrics)

    async def generate_tweet_summary(
        self,
        report_data: Dict[str, Any],
        key_metrics: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a tweet-length summary (280 characters).

        Args:
            report_data: Full report data
            key_metrics: Pre-extracted key metrics

        Returns:
            Tweet-length summary string
        """
        cache_key = self._cache_key("tweet_summary", report_data)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if key_metrics is None:
            key_metrics = self._extract_key_metrics(report_data)

        prompt = f"""Create a tweet-length summary (max 280 characters) of this tax analysis.

KEY METRICS:
- Tax Year: {key_metrics.get('tax_year', 'Current')}
- Filing Status: {key_metrics.get('filing_status', 'Unknown')}
- Total Tax: ${key_metrics.get('total_tax', 0):,.0f}
- Potential Savings: ${key_metrics.get('potential_savings', 0):,.0f}
- Top 3 Opportunities: {json.dumps(key_metrics.get('top_opportunities', [])[:3])}
- Immediate Actions: {key_metrics.get('immediate_actions', 0)}

Rules:
1. Max 280 characters (including spaces)
2. Include key savings number if significant
3. Mention most impactful action
4. Use professional but accessible language
5. No hashtags or emojis

Generate ONLY the tweet text:"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.OPENAI,
                max_tokens=100,
            )

            content = response.content.strip().strip('"\'')
            # Truncate to 280 chars if needed
            if len(content) > 280:
                content = content[:277] + "..."

            self._set_cached(cache_key, content)
            return content

        except Exception as e:
            logger.error(f"Failed to generate tweet summary: {e}")
            return self._fallback_tweet(key_metrics)

    async def generate_executive_summary(
        self,
        report_data: Dict[str, Any],
        key_metrics: Optional[Dict[str, Any]] = None,
        taxpayer_name: Optional[str] = None,
    ) -> str:
        """
        Generate an executive summary (~300 words).

        Args:
            report_data: Full report data
            key_metrics: Pre-extracted key metrics
            taxpayer_name: Optional name for personalization

        Returns:
            Executive summary string
        """
        cache_key = self._cache_key("executive_summary", report_data, taxpayer_name)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if key_metrics is None:
            key_metrics = self._extract_key_metrics(report_data)

        name = taxpayer_name or "the taxpayer"

        prompt = f"""Write an executive summary (250-350 words) for this tax advisory report.

TAXPAYER: {name}
TAX YEAR: {key_metrics.get('tax_year', 'Current')}

KEY METRICS:
- Filing Status: {key_metrics.get('filing_status', 'Unknown')}
- Total Income: ${key_metrics.get('total_income', 0):,.0f}
- Total Tax Liability: ${key_metrics.get('total_tax', 0):,.0f}
- Effective Tax Rate: {key_metrics.get('effective_rate', 0):.1f}%
- Potential Savings: ${key_metrics.get('potential_savings', 0):,.0f}

TOP OPPORTUNITIES:
{json.dumps(key_metrics.get('top_opportunities', [])[:5], indent=2)}

IMMEDIATE ACTION ITEMS:
{json.dumps(key_metrics.get('immediate_action_items', [])[:3], indent=2)}

Structure:
1. Opening paragraph: Current tax position summary
2. Key findings: 2-3 most important insights
3. Top recommendations: Highlight biggest opportunities
4. Next steps: Clear call to action

Tone: Professional, confident, actionable
Avoid: Disclaimers, hedging, generic statements

Generate the executive summary:"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.OPENAI,
                max_tokens=500,
            )

            result = response.content.strip()
            self._set_cached(cache_key, result)
            return result

        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            return self._fallback_executive(key_metrics, name)

    async def generate_detailed_summary(
        self,
        report_data: Dict[str, Any],
        key_metrics: Optional[Dict[str, Any]] = None,
        taxpayer_name: Optional[str] = None,
    ) -> str:
        """
        Generate a detailed summary (full analysis).

        Args:
            report_data: Full report data
            key_metrics: Pre-extracted key metrics
            taxpayer_name: Optional name for personalization

        Returns:
            Detailed summary string
        """
        cache_key = self._cache_key("detailed_summary", report_data, taxpayer_name)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if key_metrics is None:
            key_metrics = self._extract_key_metrics(report_data)

        name = taxpayer_name or "the taxpayer"

        # Get sections from report
        sections = report_data.get("sections", [])
        section_summaries = []

        for section in sections:
            section_summaries.append({
                "title": section.get("title", "Section"),
                "key_points": self._extract_section_points(section),
            })

        prompt = f"""Write a comprehensive summary (600-800 words) for this tax advisory report.

TAXPAYER: {name}
TAX YEAR: {key_metrics.get('tax_year', 'Current')}

FULL METRICS:
- Filing Status: {key_metrics.get('filing_status', 'Unknown')}
- Total Income: ${key_metrics.get('total_income', 0):,.0f}
- Adjusted Gross Income: ${key_metrics.get('agi', 0):,.0f}
- Taxable Income: ${key_metrics.get('taxable_income', 0):,.0f}
- Total Tax Liability: ${key_metrics.get('total_tax', 0):,.0f}
- Effective Tax Rate: {key_metrics.get('effective_rate', 0):.1f}%
- Potential Savings: ${key_metrics.get('potential_savings', 0):,.0f}

ALL RECOMMENDATIONS:
{json.dumps(key_metrics.get('all_opportunities', []), indent=2)}

REPORT SECTIONS:
{json.dumps(section_summaries, indent=2)}

Structure the summary with these sections:
1. Overview (current tax position, key numbers)
2. Income Analysis (sources, changes, observations)
3. Tax Liability Breakdown (federal, state, effective rates)
4. Optimization Opportunities (all recommendations with details)
5. Prioritized Action Plan (what to do first, second, third)
6. Long-term Considerations (future planning)

Use headers for each section. Be specific with numbers and recommendations.

Generate the detailed summary:"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.OPENAI,
                max_tokens=1200,
            )

            result = response.content.strip()
            self._set_cached(cache_key, result)
            return result

        except Exception as e:
            logger.error(f"Failed to generate detailed summary: {e}")
            return self._fallback_detailed(key_metrics, name, sections)

    async def generate_summary_for_email(
        self,
        report_data: Dict[str, Any],
        recipient_type: str = "client",
    ) -> str:
        """
        Generate summary optimized for email delivery.

        Args:
            report_data: Full report data
            recipient_type: "client" or "internal"

        Returns:
            Email-ready summary
        """
        cache_key = self._cache_key("email_summary", report_data, recipient_type)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        key_metrics = self._extract_key_metrics(report_data)

        if recipient_type == "internal":
            # Internal summary focuses on technical details
            prompt = f"""Write an internal team summary email about this tax analysis.

KEY METRICS:
{json.dumps(key_metrics, indent=2)}

Include:
1. Client name and tax year
2. Key findings (technical details OK)
3. Recommended strategies with dollar impacts
4. Any red flags or concerns
5. Suggested next steps for the team

Keep it concise but complete. Professional internal tone."""

        else:
            # Client summary is warm and accessible
            prompt = f"""Write a client-facing email summary of their tax analysis.

KEY METRICS:
- Tax Year: {key_metrics.get('tax_year', 'Current')}
- Total Tax: ${key_metrics.get('total_tax', 0):,.0f}
- Potential Savings: ${key_metrics.get('potential_savings', 0):,.0f}
- Top Opportunity: {key_metrics.get('top_opportunity', 'N/A')}

Include:
1. Warm, professional greeting
2. High-level findings (avoid jargon)
3. Key savings opportunity highlighted
4. Clear next step / call to action
5. Professional closing

Keep under 200 words. Warm but professional tone."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.OPENAI,
                max_tokens=400,
            )

            result = response.content.strip()
            self._set_cached(cache_key, result)
            return result

        except Exception as e:
            logger.error(f"Failed to generate email summary: {e}")
            return f"Your {key_metrics.get('tax_year', 'current year')} tax analysis is ready for review."

    def _extract_key_metrics(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key metrics from report data."""
        metrics = report_data.get("metrics", {})
        recommendations = report_data.get("recommendations", {})

        # Get all opportunities
        all_opportunities = []
        if isinstance(recommendations, dict):
            all_opportunities = recommendations.get("top_recommendations", [])
        elif isinstance(recommendations, list):
            all_opportunities = recommendations

        # Extract immediate actions
        immediate_actions = [
            r for r in all_opportunities
            if r.get("priority") in ("immediate", "current_year")
        ]

        return {
            "tax_year": report_data.get("tax_year", datetime.now().year),
            "filing_status": report_data.get("filing_status", "Unknown"),
            "total_income": metrics.get("total_income", 0),
            "agi": metrics.get("agi", metrics.get("adjusted_gross_income", 0)),
            "taxable_income": metrics.get("taxable_income", 0),
            "total_tax": metrics.get("current_tax_liability", metrics.get("total_tax", 0)),
            "effective_rate": metrics.get("effective_rate", 0),
            "potential_savings": metrics.get("potential_savings", 0),
            "confidence_score": metrics.get("confidence_score", 0),
            "top_opportunity": all_opportunities[0].get("title", "N/A") if all_opportunities else "N/A",
            "top_opportunities": [
                {"title": r.get("title"), "savings": r.get("savings", 0)}
                for r in all_opportunities[:5]
            ],
            "all_opportunities": all_opportunities,
            "action_count": len(all_opportunities),
            "immediate_actions": len(immediate_actions),
            "immediate_action_items": immediate_actions[:3],
        }

    def _extract_section_points(self, section: Dict[str, Any]) -> List[str]:
        """Extract key points from a report section."""
        content = section.get("content", {})
        points = []

        # Handle different content structures
        if isinstance(content, dict):
            for key, value in content.items():
                if isinstance(value, (int, float)):
                    points.append(f"{key}: {value}")
                elif isinstance(value, str) and len(value) < 100:
                    points.append(f"{key}: {value}")
                elif isinstance(value, list) and len(value) <= 3:
                    points.append(f"{key}: {len(value)} items")

        return points[:5]

    def _fallback_one_liner(self, key_metrics: Dict[str, Any]) -> str:
        """Generate fallback one-liner without AI."""
        savings = key_metrics.get("potential_savings", 0)
        if savings > 0:
            return f"You could save ${savings:,.0f} with our tax optimization recommendations"
        return f"Your {key_metrics.get('tax_year', 'current year')} tax analysis is complete"

    def _fallback_tweet(self, key_metrics: Dict[str, Any]) -> str:
        """Generate fallback tweet without AI."""
        savings = key_metrics.get("potential_savings", 0)
        tax = key_metrics.get("total_tax", 0)

        if savings > 0:
            return (
                f"Tax analysis complete: ${tax:,.0f} liability identified with "
                f"${savings:,.0f} in potential savings. "
                f"{key_metrics.get('action_count', 0)} recommendations ready for review."
            )[:280]

        return (
            f"Your {key_metrics.get('tax_year', 'current year')} tax analysis is ready. "
            f"Total liability: ${tax:,.0f}. Review your personalized recommendations."
        )[:280]

    def _fallback_executive(
        self,
        key_metrics: Dict[str, Any],
        name: str,
    ) -> str:
        """Generate fallback executive summary without AI."""
        return f"""Tax Advisory Summary for {name}

Tax Year: {key_metrics.get('tax_year', 'Current')}
Filing Status: {key_metrics.get('filing_status', 'Unknown')}

Current Tax Position:
Your total tax liability is ${key_metrics.get('total_tax', 0):,.0f}, resulting in an effective tax rate of {key_metrics.get('effective_rate', 0):.1f}%.

Optimization Opportunities:
Our analysis has identified ${key_metrics.get('potential_savings', 0):,.0f} in potential tax savings through {key_metrics.get('action_count', 0)} recommendations.

Top Opportunity: {key_metrics.get('top_opportunity', 'Review recommendations for details')}

Next Steps:
Please review the detailed recommendations in this report. {key_metrics.get('immediate_actions', 0)} actions require immediate attention.

Contact us to discuss implementation of these tax-saving strategies."""

    def _fallback_detailed(
        self,
        key_metrics: Dict[str, Any],
        name: str,
        sections: List[Dict],
    ) -> str:
        """Generate fallback detailed summary without AI."""
        summary_parts = [
            f"# Comprehensive Tax Analysis for {name}",
            f"\n## Overview",
            f"Tax Year: {key_metrics.get('tax_year', 'Current')}",
            f"Filing Status: {key_metrics.get('filing_status', 'Unknown')}",
            f"\n## Tax Position",
            f"- Total Income: ${key_metrics.get('total_income', 0):,.0f}",
            f"- Taxable Income: ${key_metrics.get('taxable_income', 0):,.0f}",
            f"- Total Tax Liability: ${key_metrics.get('total_tax', 0):,.0f}",
            f"- Effective Tax Rate: {key_metrics.get('effective_rate', 0):.1f}%",
            f"\n## Optimization Opportunities",
            f"Potential Savings Identified: ${key_metrics.get('potential_savings', 0):,.0f}",
            f"Total Recommendations: {key_metrics.get('action_count', 0)}",
        ]

        for opp in key_metrics.get("top_opportunities", [])[:5]:
            summary_parts.append(f"- {opp.get('title', 'N/A')}: ${opp.get('savings', 0):,.0f}")

        summary_parts.extend([
            f"\n## Next Steps",
            f"Review all recommendations and contact your advisor to implement these strategies.",
        ])

        return "\n".join(summary_parts)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_report_summarizer: Optional[AIReportSummarizer] = None


def get_report_summarizer() -> AIReportSummarizer:
    """Get the singleton report summarizer instance."""
    global _report_summarizer
    if _report_summarizer is None:
        _report_summarizer = AIReportSummarizer()
    return _report_summarizer


__all__ = [
    "AIReportSummarizer",
    "SummaryLevel",
    "ReportSummary",
    "MultiLevelSummaries",
    "get_report_summarizer",
]
