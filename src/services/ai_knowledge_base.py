"""
AI-Powered Tax Knowledge Base.

Uses Perplexity for real-time tax law research and guidance:
- Real-time IRS guidance monitoring
- Tax court case updates
- State law change tracking
- Professional publication monitoring
- Tax threshold verification

Usage:
    from services.ai_knowledge_base import get_tax_knowledge_base

    kb = get_tax_knowledge_base()

    # Get current guidance on a topic
    guidance = await kb.get_current_guidance("401k contribution limits")

    # Check for recent changes
    changes = await kb.monitor_tax_changes()

    # Verify a tax threshold
    verification = await kb.verify_threshold("standard_deduction", "married_filing_jointly", 2025)
"""

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GuidanceType(str, Enum):
    """Types of tax guidance."""
    IRS_PUBLICATION = "irs_publication"
    REVENUE_RULING = "revenue_ruling"
    REVENUE_PROCEDURE = "revenue_procedure"
    NOTICE = "notice"
    ANNOUNCEMENT = "announcement"
    REGULATION = "regulation"
    TAX_COURT = "tax_court"
    STATE_LAW = "state_law"
    PROFESSIONAL = "professional"


class ChangeCategory(str, Enum):
    """Categories of tax law changes."""
    THRESHOLDS = "thresholds"           # Dollar amounts, limits
    RATES = "rates"                      # Tax rates, brackets
    DEDUCTIONS = "deductions"            # Deduction rules
    CREDITS = "credits"                  # Tax credit rules
    FILING = "filing"                    # Filing requirements
    RETIREMENT = "retirement"            # Retirement account rules
    BUSINESS = "business"                # Business taxation
    INTERNATIONAL = "international"      # International tax
    STATE = "state"                       # State-specific changes


@dataclass
class TaxGuidance:
    """A piece of tax guidance or ruling."""
    topic: str
    guidance_type: GuidanceType
    title: str
    summary: str
    key_points: List[str]
    effective_date: Optional[str]
    expiration_date: Optional[str]
    source_url: Optional[str]
    source_name: str
    citation: Optional[str]
    confidence: float  # 0-1
    retrieved_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "guidance_type": self.guidance_type.value,
            "title": self.title,
            "summary": self.summary,
            "key_points": self.key_points,
            "effective_date": self.effective_date,
            "expiration_date": self.expiration_date,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "citation": self.citation,
            "confidence": self.confidence,
            "retrieved_at": self.retrieved_at.isoformat(),
        }


@dataclass
class TaxLawChange:
    """A detected change in tax law."""
    category: ChangeCategory
    title: str
    description: str
    old_value: Optional[str]
    new_value: Optional[str]
    effective_date: str
    tax_years_affected: List[int]
    impact_level: str  # "high", "medium", "low"
    source: str
    source_url: Optional[str]
    detected_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "effective_date": self.effective_date,
            "tax_years_affected": self.tax_years_affected,
            "impact_level": self.impact_level,
            "source": self.source,
            "source_url": self.source_url,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class ThresholdVerification:
    """Result of verifying a tax threshold."""
    threshold_name: str
    category: str
    tax_year: int
    expected_value: Optional[float]
    verified_value: float
    is_current: bool
    source: str
    source_url: Optional[str]
    last_updated: Optional[str]
    notes: List[str] = field(default_factory=list)
    verified_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threshold_name": self.threshold_name,
            "category": self.category,
            "tax_year": self.tax_year,
            "expected_value": self.expected_value,
            "verified_value": self.verified_value,
            "is_current": self.is_current,
            "source": self.source,
            "source_url": self.source_url,
            "last_updated": self.last_updated,
            "notes": self.notes,
            "verified_at": self.verified_at.isoformat(),
        }


class PerplexityTaxKnowledgeBase:
    """
    Real-time tax knowledge base using Perplexity.

    Provides always-current tax information by querying
    authoritative sources in real-time:
    - IRS.gov official publications
    - Tax court decisions
    - State tax authorities
    - Professional publications (Tax Notes, JofA)
    """

    # Authoritative tax sources
    PRIMARY_SOURCES = [
        "irs.gov",
        "ustaxcourt.gov",
    ]

    PROFESSIONAL_SOURCES = [
        "taxnotes.com",
        "journalofaccountancy.com",
        "thetaxadviser.com",
        "cpajournal.com",
    ]

    STATE_SOURCES = [
        "tax.ny.gov",
        "ftb.ca.gov",
        "revenue.state.tx.us",
    ]

    # Common tax thresholds to monitor
    MONITORED_THRESHOLDS = {
        "standard_deduction": {
            "single": "standard deduction single filer",
            "married_filing_jointly": "standard deduction married filing jointly",
            "married_filing_separately": "standard deduction married filing separately",
            "head_of_household": "standard deduction head of household",
        },
        "retirement_contributions": {
            "401k_limit": "401k contribution limit",
            "401k_catch_up": "401k catch up contribution over 50",
            "ira_limit": "IRA contribution limit",
            "ira_catch_up": "IRA catch up contribution",
        },
        "income_thresholds": {
            "social_security_wage_base": "social security wage base",
            "medicare_additional_tax": "additional medicare tax threshold",
            "niit_threshold": "net investment income tax threshold",
        },
        "business": {
            "section_179": "section 179 deduction limit",
            "qbi_threshold": "qualified business income deduction threshold",
        },
    }

    def __init__(self, ai_service=None, cache_ttl_hours: int = 24):
        """
        Initialize tax knowledge base.

        Args:
            ai_service: UnifiedAIService instance (lazy-loaded if not provided)
            cache_ttl_hours: How long to cache results (default 24 hours)
        """
        self._ai_service = ai_service
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self._cache: Dict[str, tuple] = {}  # key -> (result, timestamp)

    @property
    def ai_service(self):
        """Lazy-load AI service."""
        if self._ai_service is None:
            from services.ai.unified_ai_service import get_ai_service
            self._ai_service = get_ai_service()
        return self._ai_service

    async def get_current_guidance(
        self,
        topic: str,
        tax_year: int = 2025,
        include_professional: bool = True,
    ) -> TaxGuidance:
        """
        Get current IRS guidance on a specific topic.

        Args:
            topic: Tax topic to research (e.g., "401k contribution limits")
            tax_year: Tax year for the guidance
            include_professional: Include professional publications

        Returns:
            TaxGuidance with current information
        """
        cache_key = f"guidance:{topic}:{tax_year}"

        # Check cache
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Build search query
        sources = self.PRIMARY_SOURCES.copy()
        if include_professional:
            sources.extend(self.PROFESSIONAL_SOURCES)

        prompt = f"""Research the current IRS guidance for: {topic}

Tax Year: {tax_year}

Search authoritative sources and provide:
1. The current rule or limit
2. Any recent changes
3. Key requirements or conditions
4. Important deadlines
5. Source citations

Return as JSON:
{{
    "title": "Official guidance title",
    "summary": "Clear summary of the guidance",
    "key_points": ["point1", "point2", ...],
    "current_value": "specific amount or rule if applicable",
    "effective_date": "when this became effective",
    "source_name": "primary source",
    "citation": "IRS Publication X, Section Y",
    "confidence": 0.0-1.0
}}"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.PERPLEXITY,
            )

            # Parse response
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            guidance = TaxGuidance(
                topic=topic,
                guidance_type=GuidanceType.IRS_PUBLICATION,
                title=data.get("title", topic),
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                effective_date=data.get("effective_date"),
                expiration_date=data.get("expiration_date"),
                source_url=data.get("source_url"),
                source_name=data.get("source_name", "IRS"),
                citation=data.get("citation"),
                confidence=data.get("confidence", 0.7),
            )

            # Cache result
            self._set_cached(cache_key, guidance)

            return guidance

        except Exception as e:
            logger.error(f"Failed to get tax guidance for {topic}: {e}")
            return TaxGuidance(
                topic=topic,
                guidance_type=GuidanceType.IRS_PUBLICATION,
                title=f"Guidance for {topic}",
                summary=f"Unable to retrieve current guidance. Please consult IRS.gov for {topic}.",
                key_points=[],
                effective_date=None,
                expiration_date=None,
                source_url="https://www.irs.gov",
                source_name="IRS",
                citation=None,
                confidence=0.0,
            )

    async def monitor_tax_changes(
        self,
        categories: Optional[List[ChangeCategory]] = None,
        since_days: int = 30,
    ) -> List[TaxLawChange]:
        """
        Monitor for recent tax law changes.

        Args:
            categories: Categories to monitor (all if None)
            since_days: Look back period in days

        Returns:
            List of detected tax law changes
        """
        if categories is None:
            categories = list(ChangeCategory)

        changes = []

        for category in categories:
            try:
                category_changes = await self._check_category_changes(category, since_days)
                changes.extend(category_changes)
            except Exception as e:
                logger.warning(f"Failed to check {category.value} changes: {e}")

        # Sort by impact level and date
        impact_order = {"high": 0, "medium": 1, "low": 2}
        changes.sort(key=lambda x: (impact_order.get(x.impact_level, 3), x.detected_at), reverse=True)

        return changes

    async def verify_threshold(
        self,
        threshold_type: str,
        category: str,
        tax_year: int,
        expected_value: Optional[float] = None,
    ) -> ThresholdVerification:
        """
        Verify a specific tax threshold is current.

        Args:
            threshold_type: Type of threshold (e.g., "standard_deduction")
            category: Category within type (e.g., "single")
            tax_year: Tax year to verify
            expected_value: Optional expected value to compare

        Returns:
            ThresholdVerification with current value and status
        """
        # Get search topic
        topics = self.MONITORED_THRESHOLDS.get(threshold_type, {})
        search_topic = topics.get(category, f"{threshold_type} {category}")

        prompt = f"""Find the current {search_topic} for tax year {tax_year}.

Return as JSON:
{{
    "value": numeric_value,
    "formatted_value": "$XX,XXX",
    "source": "IRS Publication or source",
    "source_url": "url if available",
    "last_updated": "date of last update",
    "notes": ["any relevant notes"]
}}

Be precise with the dollar amount. Only return official IRS values."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.PERPLEXITY,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            verified_value = float(data.get("value", 0))
            is_current = True

            if expected_value is not None:
                # Check if values match (within small tolerance for rounding)
                tolerance = max(1, expected_value * 0.001)  # 0.1% or $1
                is_current = abs(verified_value - expected_value) <= tolerance

            return ThresholdVerification(
                threshold_name=f"{threshold_type}_{category}",
                category=category,
                tax_year=tax_year,
                expected_value=expected_value,
                verified_value=verified_value,
                is_current=is_current,
                source=data.get("source", "IRS"),
                source_url=data.get("source_url"),
                last_updated=data.get("last_updated"),
                notes=data.get("notes", []),
            )

        except Exception as e:
            logger.error(f"Failed to verify threshold {threshold_type}/{category}: {e}")
            return ThresholdVerification(
                threshold_name=f"{threshold_type}_{category}",
                category=category,
                tax_year=tax_year,
                expected_value=expected_value,
                verified_value=expected_value or 0,
                is_current=False,
                source="Verification failed",
                source_url=None,
                last_updated=None,
                notes=[f"Error: {str(e)}"],
            )

    async def search_tax_court_cases(
        self,
        topic: str,
        limit: int = 5,
    ) -> List[TaxGuidance]:
        """
        Search for relevant tax court cases.

        Args:
            topic: Topic to search for
            limit: Maximum number of cases to return

        Returns:
            List of relevant tax court cases
        """
        prompt = f"""Find the most relevant US Tax Court cases regarding: {topic}

Return up to {limit} cases as JSON array:
[
    {{
        "case_name": "Taxpayer v. Commissioner",
        "citation": "T.C. Memo 2024-XX",
        "year": 2024,
        "summary": "Brief summary of holding",
        "key_points": ["relevant points"],
        "outcome": "taxpayer won/IRS won"
    }}
]

Focus on recent and frequently cited cases."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.PERPLEXITY,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            cases_data = json.loads(content)

            cases = []
            for case_data in cases_data[:limit]:
                cases.append(TaxGuidance(
                    topic=topic,
                    guidance_type=GuidanceType.TAX_COURT,
                    title=case_data.get("case_name", "Unknown Case"),
                    summary=case_data.get("summary", ""),
                    key_points=case_data.get("key_points", []),
                    effective_date=str(case_data.get("year", "")),
                    expiration_date=None,
                    source_url=None,
                    source_name="US Tax Court",
                    citation=case_data.get("citation"),
                    confidence=0.8,
                ))

            return cases

        except Exception as e:
            logger.error(f"Failed to search tax court cases for {topic}: {e}")
            return []

    async def get_state_tax_info(
        self,
        state: str,
        topic: str,
        tax_year: int = 2025,
    ) -> TaxGuidance:
        """
        Get state-specific tax information.

        Args:
            state: State code (e.g., "CA", "NY")
            topic: Tax topic to research
            tax_year: Tax year

        Returns:
            TaxGuidance with state-specific information
        """
        state_names = {
            "CA": "California",
            "NY": "New York",
            "TX": "Texas",
            "FL": "Florida",
            "IL": "Illinois",
            "PA": "Pennsylvania",
            "OH": "Ohio",
            "GA": "Georgia",
            "NC": "North Carolina",
            "MI": "Michigan",
        }

        state_name = state_names.get(state.upper(), state)

        prompt = f"""Research {state_name} state tax rules for: {topic}

Tax Year: {tax_year}

Provide:
1. State-specific rules or rates
2. Differences from federal treatment
3. Filing requirements
4. Important deadlines
5. Source citations

Return as JSON:
{{
    "title": "State guidance title",
    "summary": "Clear summary",
    "key_points": ["point1", "point2"],
    "state_specific_rules": "rules that differ from federal",
    "source_name": "State tax authority",
    "confidence": 0.0-1.0
}}"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.PERPLEXITY,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return TaxGuidance(
                topic=f"{state} - {topic}",
                guidance_type=GuidanceType.STATE_LAW,
                title=data.get("title", f"{state_name} {topic}"),
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                effective_date=None,
                expiration_date=None,
                source_url=None,
                source_name=data.get("source_name", f"{state_name} Tax Authority"),
                citation=None,
                confidence=data.get("confidence", 0.7),
            )

        except Exception as e:
            logger.error(f"Failed to get state tax info for {state}/{topic}: {e}")
            return TaxGuidance(
                topic=f"{state} - {topic}",
                guidance_type=GuidanceType.STATE_LAW,
                title=f"{state_name} Tax Information",
                summary=f"Unable to retrieve. Please consult {state_name} tax authority.",
                key_points=[],
                effective_date=None,
                expiration_date=None,
                source_url=None,
                source_name=f"{state_name} Tax Authority",
                citation=None,
                confidence=0.0,
            )

    async def _check_category_changes(
        self,
        category: ChangeCategory,
        since_days: int,
    ) -> List[TaxLawChange]:
        """Check for changes in a specific category."""
        category_topics = {
            ChangeCategory.THRESHOLDS: "tax threshold changes inflation adjustments",
            ChangeCategory.RATES: "tax rate changes brackets",
            ChangeCategory.DEDUCTIONS: "deduction limit changes rules",
            ChangeCategory.CREDITS: "tax credit changes requirements",
            ChangeCategory.FILING: "filing requirement changes deadlines",
            ChangeCategory.RETIREMENT: "retirement account contribution limit changes",
            ChangeCategory.BUSINESS: "business tax changes section 199A QBI",
            ChangeCategory.INTERNATIONAL: "international tax changes FATCA",
            ChangeCategory.STATE: "state tax law changes",
        }

        topic = category_topics.get(category, category.value)

        prompt = f"""Find recent changes (last {since_days} days) to US tax law regarding: {topic}

Return as JSON array:
[
    {{
        "title": "Change title",
        "description": "What changed",
        "old_value": "previous rule/value",
        "new_value": "new rule/value",
        "effective_date": "YYYY-MM-DD",
        "tax_years_affected": [2025, 2026],
        "impact_level": "high/medium/low",
        "source": "Source of change"
    }}
]

Only include confirmed changes from official sources. Return empty array if no changes."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.PERPLEXITY,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            changes_data = json.loads(content)

            changes = []
            for change_data in changes_data:
                changes.append(TaxLawChange(
                    category=category,
                    title=change_data.get("title", "Tax Change"),
                    description=change_data.get("description", ""),
                    old_value=change_data.get("old_value"),
                    new_value=change_data.get("new_value"),
                    effective_date=change_data.get("effective_date", "Unknown"),
                    tax_years_affected=change_data.get("tax_years_affected", []),
                    impact_level=change_data.get("impact_level", "medium"),
                    source=change_data.get("source", "Unknown"),
                    source_url=change_data.get("source_url"),
                ))

            return changes

        except Exception as e:
            logger.warning(f"Failed to check {category.value} changes: {e}")
            return []

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached result if still valid."""
        if key in self._cache:
            result, timestamp = self._cache[key]
            if datetime.now() - timestamp < self.cache_ttl:
                return result
            else:
                del self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        """Cache a result."""
        self._cache[key] = (value, datetime.now())


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_tax_knowledge_base: Optional[PerplexityTaxKnowledgeBase] = None


def get_tax_knowledge_base() -> PerplexityTaxKnowledgeBase:
    """Get the singleton tax knowledge base instance."""
    global _tax_knowledge_base
    if _tax_knowledge_base is None:
        _tax_knowledge_base = PerplexityTaxKnowledgeBase()
    return _tax_knowledge_base


__all__ = [
    "PerplexityTaxKnowledgeBase",
    "TaxGuidance",
    "TaxLawChange",
    "ThresholdVerification",
    "GuidanceType",
    "ChangeCategory",
    "get_tax_knowledge_base",
]
