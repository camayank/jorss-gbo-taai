"""Tests for AI narrative integration in report generators.

Verifies that:
1. AI narratives are added to advisory report executive summaries when available
2. Advisory report falls back gracefully when AI fails
3. Recommendation engine uses AI narratives when available
4. Recommendation engine falls back to static summaries when AI fails
5. Timeouts do not block report generation
6. AINarrativeGenerator fallback paths for individual methods
"""

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Lightweight stubs so we don't need full model imports
# ---------------------------------------------------------------------------

class _FilingStatus(Enum):
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"


@dataclass
class _Taxpayer:
    first_name: str = "John"
    last_name: str = "Doe"
    filing_status: _FilingStatus = _FilingStatus.SINGLE
    name: str = ""
    state: str = "CA"


@dataclass
class _Income:
    w2_wages: Decimal = Decimal("75000")
    self_employment_income: Decimal = Decimal("0")
    self_employment_expenses: Decimal = Decimal("0")
    retirement_contributions_401k: Decimal = Decimal("0")

    def get_total_income(self):
        return self.w2_wages + self.self_employment_income

    def get_total_wages(self):
        return float(self.w2_wages)


@dataclass
class _Deductions:
    use_standard_deduction: bool = True
    mortgage_interest: Decimal = Decimal("0")
    charitable_cash: Decimal = Decimal("0")
    property_taxes: Decimal = Decimal("0")


@dataclass
class _TaxReturn:
    tax_year: int = 2025
    taxpayer: _Taxpayer = field(default_factory=_Taxpayer)
    income: _Income = field(default_factory=_Income)
    deductions: _Deductions = field(default_factory=_Deductions)
    adjusted_gross_income: Decimal = Decimal("75000")
    taxable_income: Decimal = Decimal("62000")
    tax_liability: Decimal = Decimal("9500")
    state_tax_liability: Decimal = Decimal("3000")
    refund_or_owed: float = 0.0


@dataclass
class _TaxResult:
    """Mimics the result from TaxCalculator.calculate_complete_return."""
    tax_liability: Decimal = Decimal("9500")
    state_tax_liability: Decimal = Decimal("3000")
    adjusted_gross_income: Decimal = Decimal("75000")
    taxable_income: Decimal = Decimal("62000")
    income: _Income = field(default_factory=_Income)
    deductions: _Deductions = field(default_factory=_Deductions)


# ---------------------------------------------------------------------------
# Helper to build a mock narrative generator
# ---------------------------------------------------------------------------

def _make_narrative_mock(content: str = "AI-generated executive summary."):
    """Return a mock get_narrative_generator that produces a narrative."""
    narrative = MagicMock()
    narrative.content = content

    generator = MagicMock()
    generator.generate_executive_summary = AsyncMock(return_value=narrative)

    factory = MagicMock(return_value=generator)
    return factory, generator, narrative


def _make_failing_narrative_mock(exc: Exception = RuntimeError("AI unavailable")):
    """Return a mock get_narrative_generator that raises on call."""
    generator = MagicMock()
    generator.generate_executive_summary = AsyncMock(side_effect=exc)

    factory = MagicMock(return_value=generator)
    return factory, generator


# ===================================================================
# Tests for src/advisory/report_generator.py
# ===================================================================

class TestAdvisoryReportAINarrative:
    """Tests for AI narrative in AdvisoryReportGenerator._generate_executive_summary."""

    def _make_generator(self):
        """Build an AdvisoryReportGenerator with a mocked tax calculator."""
        from advisory.report_generator import AdvisoryReportGenerator

        calc = MagicMock()
        calc.calculate_complete_return.return_value = _TaxResult()
        return AdvisoryReportGenerator(tax_calculator=calc)

    @patch("advisory.ai_narrative_generator.get_narrative_generator")
    def test_ai_narrative_added_on_success(self, mock_get_gen):
        """When AI succeeds, content dict should contain ai_narrative key."""
        factory, generator, narrative = _make_narrative_mock(
            "Personalized AI summary for John Doe."
        )
        mock_get_gen.side_effect = factory.side_effect
        mock_get_gen.return_value = factory.return_value

        # Re-wire: the code does `from advisory.ai_narrative_generator import get_narrative_generator`
        # inside a try block, so we patch at module level
        gen = self._make_generator()

        with patch(
            "advisory.ai_narrative_generator.get_narrative_generator",
            return_value=generator,
        ):
            section = gen._generate_executive_summary(_TaxReturn())

        assert "ai_narrative" in section.content
        assert section.content["ai_narrative"] == "Personalized AI summary for John Doe."
        # Structured data must still be present
        assert "agi" in section.content
        assert "current_liability" in section.content
        assert section.content["tax_year"] == 2025

    @patch("advisory.ai_narrative_generator.get_narrative_generator")
    def test_static_fallback_on_ai_failure(self, mock_get_gen):
        """When AI fails, content dict should NOT contain ai_narrative but still have all static data."""
        mock_get_gen.side_effect = RuntimeError("AI service down")

        gen = self._make_generator()
        section = gen._generate_executive_summary(_TaxReturn())

        assert "ai_narrative" not in section.content
        # All static fields must be present
        assert section.content["overview"] == "Tax advisory report for John Doe"
        assert section.content["agi"] == 75000.0
        assert section.content["taxable_income"] == 62000.0
        assert section.content["current_liability"]["total"] == 12500.0
        assert section.section_id == "executive_summary"

    @patch("advisory.ai_narrative_generator.get_narrative_generator")
    def test_empty_narrative_not_added(self, mock_get_gen):
        """If AI returns empty content, ai_narrative should not be added."""
        narrative = MagicMock()
        narrative.content = ""
        generator = MagicMock()
        generator.generate_executive_summary = AsyncMock(return_value=narrative)
        mock_get_gen.return_value = generator

        gen = self._make_generator()
        section = gen._generate_executive_summary(_TaxReturn())

        assert "ai_narrative" not in section.content


# ===================================================================
# Tests for src/recommendation/recommendation_engine.py
# ===================================================================

class TestRecommendationEngineAINarrative:
    """Tests for AI narrative in TaxRecommendationEngine._generate_executive_summary."""

    def _make_opportunities(self, count: int = 3) -> list:
        """Create mock TaxSavingOpportunity objects."""
        from recommendation.recommendation_engine import TaxSavingOpportunity

        return [
            TaxSavingOpportunity(
                category="retirement",
                title=f"Opportunity {i}",
                estimated_savings=1000.0 * (count - i),
                priority="immediate" if i == 0 else "current_year",
                description=f"Description {i}",
                action_required=f"Action {i}",
                confidence=80.0,
                irs_reference="IRC Section 401(k)",
            )
            for i in range(count)
        ]

    @patch("advisory.ai_narrative_generator.get_narrative_generator")
    def test_ai_narrative_returned_on_success(self, mock_get_gen):
        """When AI succeeds, the AI narrative string should be returned."""
        narrative = MagicMock()
        narrative.content = "AI-powered recommendation summary."
        generator_mock = MagicMock()
        generator_mock.generate_executive_summary = AsyncMock(return_value=narrative)
        mock_get_gen.return_value = generator_mock

        from recommendation.recommendation_engine import TaxRecommendationEngine

        engine = TaxRecommendationEngine()
        opps = self._make_opportunities()
        result = engine._generate_executive_summary(_TaxReturn(), 3000.0, opps)

        assert result == "AI-powered recommendation summary."

    @patch("advisory.ai_narrative_generator.get_narrative_generator")
    def test_static_fallback_on_ai_failure(self, mock_get_gen):
        """When AI fails, static f-string summary should be returned."""
        mock_get_gen.side_effect = RuntimeError("Service unavailable")

        from recommendation.recommendation_engine import TaxRecommendationEngine

        engine = TaxRecommendationEngine()
        opps = self._make_opportunities()
        result = engine._generate_executive_summary(_TaxReturn(), 3000.0, opps)

        # Should contain static summary content
        assert "single" in result.lower() or "filing status" in result.lower()
        assert "$75,000" in result  # AGI
        assert "$9,500" in result  # tax liability
        assert "$3,000" in result  # total savings
        assert "Opportunity 0" in result  # top opportunity title

    @patch("advisory.ai_narrative_generator.get_narrative_generator")
    def test_static_fallback_on_empty_narrative(self, mock_get_gen):
        """When AI returns empty content, static summary should be used."""
        narrative = MagicMock()
        narrative.content = ""
        generator_mock = MagicMock()
        generator_mock.generate_executive_summary = AsyncMock(return_value=narrative)
        mock_get_gen.return_value = generator_mock

        from recommendation.recommendation_engine import TaxRecommendationEngine

        engine = TaxRecommendationEngine()
        opps = self._make_opportunities()
        result = engine._generate_executive_summary(_TaxReturn(), 3000.0, opps)

        # Should fall through to static summary
        assert "$75,000" in result

    @patch("advisory.ai_narrative_generator.get_narrative_generator")
    def test_timeout_falls_back_to_static(self, mock_get_gen):
        """When AI generation raises a timeout error, static fallback is used."""
        import concurrent.futures

        def _raise_timeout(*args, **kwargs):
            raise concurrent.futures.TimeoutError("AI took too long")

        mock_get_gen.side_effect = _raise_timeout

        from recommendation.recommendation_engine import TaxRecommendationEngine

        engine = TaxRecommendationEngine()
        opps = self._make_opportunities()

        result = engine._generate_executive_summary(_TaxReturn(), 3000.0, opps)

        # Should have used static fallback
        assert "$75,000" in result
        assert "optimization opportunities" in result


# ===================================================================
# Tests for src/advisory/ai_narrative_generator.py fallback paths
# ===================================================================

class TestAINarrativeGeneratorFallbacks:
    """Tests for AINarrativeGenerator fallback paths when AI service fails.

    Each public method should gracefully degrade and return a
    GeneratedNarrative with fallback content when the AI service
    raises an exception.
    """

    def _make_failing_generator(self, exc=None):
        """Create an AINarrativeGenerator with a failing AI service."""
        from advisory.ai_narrative_generator import AINarrativeGenerator

        exc = exc or RuntimeError("AI service unavailable")
        mock_service = MagicMock()
        mock_service.complete = AsyncMock(side_effect=exc)
        return AINarrativeGenerator(ai_service=mock_service)

    def _make_client_profile(self):
        """Build a ClientProfile for testing."""
        from advisory.ai_narrative_generator import ClientProfile
        return ClientProfile(
            name="Test User",
            occupation="Engineer",
            financial_goals=["Save on taxes"],
            primary_concern="Reducing tax burden",
        )

    @pytest.mark.asyncio
    async def test_generate_recommendation_explanation_fallback(self):
        """When AI fails, recommendation explanation should return the original description."""
        gen = self._make_failing_generator()
        profile = self._make_client_profile()
        recommendation = {
            "title": "Maximize 401(k)",
            "category": "retirement",
            "savings": 5000.0,
            "description": "Increase your 401(k) contributions to the annual limit.",
            "action_required": "Contact HR",
            "irs_reference": "IRC Section 401(k)",
        }

        result = await gen.generate_recommendation_explanation(recommendation, profile)

        assert result.narrative_type == "recommendation_explanation"
        assert result.content == recommendation["description"]
        assert result.tone_used == "default"
        assert "Maximize 401(k)" in result.key_points

    @pytest.mark.asyncio
    async def test_generate_recommendation_explanation_fallback_empty_description(self):
        """When AI fails and description is empty, fallback should still work."""
        gen = self._make_failing_generator()
        profile = self._make_client_profile()
        recommendation = {
            "title": "Some Strategy",
            "category": "general",
            "savings": 0,
        }

        result = await gen.generate_recommendation_explanation(recommendation, profile)

        assert result.narrative_type == "recommendation_explanation"
        assert result.content == ""
        assert result.tone_used == "default"

    @pytest.mark.asyncio
    async def test_generate_action_plan_narrative_fallback(self):
        """When AI fails, action plan should use the text-based fallback."""
        gen = self._make_failing_generator()
        profile = self._make_client_profile()
        action_items = [
            {
                "title": "Max 401(k)",
                "action": "Contact HR to increase contributions",
                "savings": 3000.0,
                "priority": "immediate",
            },
            {
                "title": "Open HSA",
                "action": "Set up HSA account",
                "savings": 1200.0,
                "priority": "current_year",
            },
        ]

        result = await gen.generate_action_plan_narrative(action_items, profile)

        assert result.narrative_type == "action_plan"
        assert "Your Tax Action Plan" in result.content
        assert "Max 401(k)" in result.content
        assert "Open HSA" in result.content
        assert "$3,000.00" in result.content
        assert result.tone_used == "default"
        assert result.metadata.get("fallback") is True

    @pytest.mark.asyncio
    async def test_generate_action_plan_fallback_empty_items(self):
        """Fallback action plan with no items should still produce valid output."""
        gen = self._make_failing_generator()
        profile = self._make_client_profile()

        result = await gen.generate_action_plan_narrative([], profile)

        assert result.narrative_type == "action_plan"
        assert "Your Tax Action Plan" in result.content
        assert result.metadata.get("fallback") is True

    @pytest.mark.asyncio
    async def test_generate_year_over_year_narrative_fallback(self):
        """When AI fails, year-over-year narrative should return a brief fallback."""
        gen = self._make_failing_generator()
        profile = self._make_client_profile()
        current_year = {
            "tax_year": 2025,
            "total_income": 100_000,
            "taxable_income": 85_000,
            "total_tax": 18_000,
            "effective_rate": 18.0,
        }
        prior_year = {
            "tax_year": 2024,
            "total_income": 90_000,
            "taxable_income": 75_000,
            "total_tax": 15_000,
            "effective_rate": 16.7,
        }

        result = await gen.generate_year_over_year_narrative(
            current_year, prior_year, profile
        )

        assert result.narrative_type == "year_over_year"
        assert "not available" in result.content.lower()
        assert result.tone_used == "default"
        assert result.word_count == 5

    @pytest.mark.asyncio
    async def test_generate_executive_summary_fallback(self):
        """When AI fails, executive summary should use _generate_fallback_summary."""
        gen = self._make_failing_generator()
        profile = self._make_client_profile()
        analysis = {
            "tax_year": 2025,
            "filing_status": "single",
            "metrics": {
                "current_tax_liability": 15000,
                "potential_savings": 5000,
                "confidence_score": 80,
            },
            "recommendations": {
                "total_count": 5,
                "immediate_actions": [],
            },
        }

        result = await gen.generate_executive_summary(analysis, profile)

        assert result.narrative_type == "executive_summary"
        assert "Test User" in result.content  # Should be personalized
        assert "$5,000.00" in result.content or "5,000" in result.content
        assert result.metadata.get("fallback") is True

    @pytest.mark.asyncio
    async def test_fallback_on_connection_error(self):
        """ConnectionError should trigger fallback, not crash."""
        gen = self._make_failing_generator(ConnectionError("Network unreachable"))
        profile = self._make_client_profile()
        recommendation = {
            "title": "Strategy X",
            "description": "Do something.",
        }

        result = await gen.generate_recommendation_explanation(recommendation, profile)

        assert result.narrative_type == "recommendation_explanation"
        assert result.content == "Do something."

    @pytest.mark.asyncio
    async def test_fallback_on_timeout_error(self):
        """TimeoutError should trigger fallback."""
        gen = self._make_failing_generator(TimeoutError("Request timed out"))
        profile = self._make_client_profile()
        action_items = [
            {"title": "Quick Win", "priority": "immediate"},
        ]

        result = await gen.generate_action_plan_narrative(action_items, profile)

        assert result.narrative_type == "action_plan"
        assert "Your Tax Action Plan" in result.content
