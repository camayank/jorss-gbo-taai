"""Tests for AI narrative integration in report generators.

Verifies that:
1. AI narratives are added to advisory report executive summaries when available
2. Advisory report falls back gracefully when AI fails
3. Recommendation engine uses AI narratives when available
4. Recommendation engine falls back to static summaries when AI fails
5. Timeouts do not block report generation
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
