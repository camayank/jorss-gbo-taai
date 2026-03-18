"""Tests for AIReportSummarizer (src/advisory/report_summarizer.py).

Covers:
- All 4 public summary methods with mocked AI service
- generate_all_summaries orchestration
- Fallback paths when AI is unavailable
- Caching behaviour (call twice, second returns cached)
- _extract_key_metrics helper
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from advisory.report_summarizer import (
    AIReportSummarizer,
    MultiLevelSummaries,
    SummaryLevel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_ai_service(content: str = "AI-generated summary text"):
    """Return a mock AI service whose .complete() returns *content*."""
    response = MagicMock()
    response.content = content
    service = MagicMock()
    service.complete = AsyncMock(return_value=response)
    return service


def _make_report_data(
    total_income: float = 120_000,
    total_tax: float = 18_000,
    potential_savings: float = 5_000,
    filing_status: str = "single",
    tax_year: int = 2025,
):
    """Build a minimal report_data dict compatible with the summarizer."""
    return {
        "tax_year": tax_year,
        "filing_status": filing_status,
        "metrics": {
            "total_income": total_income,
            "agi": total_income,
            "taxable_income": total_income - 15_000,
            "current_tax_liability": total_tax,
            "total_tax": total_tax,
            "effective_rate": (total_tax / total_income * 100) if total_income else 0,
            "potential_savings": potential_savings,
            "confidence_score": 85,
        },
        "recommendations": {
            "top_recommendations": [
                {
                    "title": "Maximize 401(k) Contributions",
                    "savings": 3_000,
                    "priority": "immediate",
                },
                {
                    "title": "HSA Contribution",
                    "savings": 1_200,
                    "priority": "current_year",
                },
                {
                    "title": "Roth Conversion",
                    "savings": 800,
                    "priority": "next_year",
                },
            ],
        },
        "sections": [
            {
                "title": "Executive Summary",
                "content": {"agi": total_income, "taxable_income": total_income - 15_000},
            },
        ],
    }


# ---------------------------------------------------------------------------
# Tests: _extract_key_metrics
# ---------------------------------------------------------------------------

class TestExtractKeyMetrics:
    """Unit tests for the _extract_key_metrics helper."""

    def test_extracts_basic_metrics(self):
        summarizer = AIReportSummarizer()
        data = _make_report_data()
        metrics = summarizer._extract_key_metrics(data)

        assert metrics["tax_year"] == 2025
        assert metrics["filing_status"] == "single"
        assert metrics["total_income"] == 120_000
        assert metrics["total_tax"] == 18_000
        assert metrics["potential_savings"] == 5_000
        assert metrics["action_count"] == 3
        assert metrics["top_opportunity"] == "Maximize 401(k) Contributions"

    def test_handles_empty_recommendations(self):
        summarizer = AIReportSummarizer()
        data = _make_report_data()
        data["recommendations"] = {"top_recommendations": []}
        metrics = summarizer._extract_key_metrics(data)

        assert metrics["action_count"] == 0
        assert metrics["top_opportunity"] == "N/A"
        assert metrics["top_opportunities"] == []

    def test_handles_recommendations_as_list(self):
        summarizer = AIReportSummarizer()
        data = _make_report_data()
        data["recommendations"] = [
            {"title": "Item A", "savings": 100, "priority": "immediate"},
        ]
        metrics = summarizer._extract_key_metrics(data)

        assert metrics["action_count"] == 1
        assert metrics["top_opportunity"] == "Item A"

    def test_immediate_actions_count(self):
        summarizer = AIReportSummarizer()
        data = _make_report_data()
        metrics = summarizer._extract_key_metrics(data)

        # 1 "immediate" + 1 "current_year" = 2 items matching the filter
        assert metrics["immediate_actions"] == 2

    def test_missing_metrics_key(self):
        summarizer = AIReportSummarizer()
        data = {"recommendations": []}
        metrics = summarizer._extract_key_metrics(data)

        assert metrics["total_income"] == 0
        assert metrics["total_tax"] == 0


# ---------------------------------------------------------------------------
# Tests: generate_one_liner
# ---------------------------------------------------------------------------

class TestGenerateOneLiner:
    """Tests for generate_one_liner."""

    @pytest.mark.asyncio
    async def test_returns_ai_content(self):
        service = _make_ai_service("Save $5,000 by maximizing retirement contributions")
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_one_liner(_make_report_data())

        assert "Save $5,000" in result
        service.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_truncates_long_responses(self):
        long_text = " ".join([f"word{i}" for i in range(25)])
        service = _make_ai_service(long_text)
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_one_liner(_make_report_data())

        # Should truncate to ~15 words + "..."
        assert result.endswith("...")
        assert len(result.split()) <= 16  # 15 words + "..."

    @pytest.mark.asyncio
    async def test_fallback_on_ai_failure(self):
        service = MagicMock()
        service.complete = AsyncMock(side_effect=RuntimeError("API down"))
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_one_liner(_make_report_data())

        assert "$5,000" in result
        assert "save" in result.lower()

    @pytest.mark.asyncio
    async def test_fallback_with_zero_savings(self):
        service = MagicMock()
        service.complete = AsyncMock(side_effect=RuntimeError("fail"))
        summarizer = AIReportSummarizer(ai_service=service)

        data = _make_report_data(potential_savings=0)
        result = await summarizer.generate_one_liner(data)

        assert "analysis is complete" in result.lower() or "tax analysis" in result.lower()


# ---------------------------------------------------------------------------
# Tests: generate_tweet_summary
# ---------------------------------------------------------------------------

class TestGenerateTweetSummary:
    """Tests for generate_tweet_summary."""

    @pytest.mark.asyncio
    async def test_returns_ai_content(self):
        service = _make_ai_service("Your tax analysis reveals $5K in savings.")
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_tweet_summary(_make_report_data())

        assert "$5K" in result
        assert len(result) <= 280

    @pytest.mark.asyncio
    async def test_truncates_to_280_chars(self):
        long_text = "A" * 300
        service = _make_ai_service(long_text)
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_tweet_summary(_make_report_data())

        assert len(result) <= 280
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_fallback_on_ai_failure(self):
        service = MagicMock()
        service.complete = AsyncMock(side_effect=Exception("timeout"))
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_tweet_summary(_make_report_data())

        assert len(result) <= 280
        assert "$18,000" in result or "$5,000" in result


# ---------------------------------------------------------------------------
# Tests: generate_executive_summary
# ---------------------------------------------------------------------------

class TestGenerateExecutiveSummary:
    """Tests for generate_executive_summary."""

    @pytest.mark.asyncio
    async def test_returns_ai_content(self):
        service = _make_ai_service("Executive overview of tax position.")
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_executive_summary(
            _make_report_data(), taxpayer_name="Jane Smith"
        )

        assert result == "Executive overview of tax position."

    @pytest.mark.asyncio
    async def test_fallback_includes_taxpayer_name(self):
        service = MagicMock()
        service.complete = AsyncMock(side_effect=Exception("fail"))
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_executive_summary(
            _make_report_data(), taxpayer_name="Jane Smith"
        )

        assert "Jane Smith" in result
        assert "Tax Advisory Summary" in result


# ---------------------------------------------------------------------------
# Tests: generate_detailed_summary
# ---------------------------------------------------------------------------

class TestGenerateDetailedSummary:
    """Tests for generate_detailed_summary."""

    @pytest.mark.asyncio
    async def test_returns_ai_content(self):
        service = _make_ai_service("Comprehensive tax analysis report.")
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_detailed_summary(
            _make_report_data(), taxpayer_name="Bob"
        )

        assert result == "Comprehensive tax analysis report."

    @pytest.mark.asyncio
    async def test_fallback_includes_sections(self):
        service = MagicMock()
        service.complete = AsyncMock(side_effect=Exception("fail"))
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_detailed_summary(
            _make_report_data(), taxpayer_name="Bob"
        )

        assert "# Comprehensive Tax Analysis for Bob" in result
        assert "## Overview" in result
        assert "## Tax Position" in result
        assert "$120,000" in result  # total income


# ---------------------------------------------------------------------------
# Tests: generate_all_summaries
# ---------------------------------------------------------------------------

class TestGenerateAllSummaries:
    """Tests for generate_all_summaries orchestration."""

    @pytest.mark.asyncio
    async def test_returns_multi_level_summaries(self):
        service = _make_ai_service("Summary text")
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_all_summaries(
            _make_report_data(), taxpayer_name="Alice"
        )

        assert isinstance(result, MultiLevelSummaries)
        assert result.one_liner == "Summary text"
        assert result.tweet == "Summary text"
        assert result.executive == "Summary text"
        assert result.detailed == "Summary text"
        assert "total_income" in result.key_metrics

    @pytest.mark.asyncio
    async def test_get_summary_by_level(self):
        service = _make_ai_service("Level text")
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_all_summaries(_make_report_data())

        assert result.get_summary(SummaryLevel.ONE_LINER) == "Level text"
        assert result.get_summary(SummaryLevel.EXECUTIVE) == "Level text"

    @pytest.mark.asyncio
    async def test_to_dict_serialization(self):
        service = _make_ai_service("Serializable")
        summarizer = AIReportSummarizer(ai_service=service)

        result = await summarizer.generate_all_summaries(_make_report_data())
        d = result.to_dict()

        assert d["one_liner"] == "Serializable"
        assert "generated_at" in d
        assert "key_metrics" in d


# ---------------------------------------------------------------------------
# Tests: Caching
# ---------------------------------------------------------------------------

class TestCaching:
    """Tests for internal caching behaviour."""

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self):
        service = _make_ai_service("Cached result")
        summarizer = AIReportSummarizer(ai_service=service)
        data = _make_report_data()

        result1 = await summarizer.generate_one_liner(data)
        result2 = await summarizer.generate_one_liner(data)

        assert result1 == result2
        # AI service should only be called once
        assert service.complete.await_count == 1

    @pytest.mark.asyncio
    async def test_different_data_not_cached(self):
        service = _make_ai_service("Fresh result")
        summarizer = AIReportSummarizer(ai_service=service)

        data1 = _make_report_data(total_income=100_000)
        data2 = _make_report_data(total_income=200_000)

        await summarizer.generate_one_liner(data1)
        await summarizer.generate_one_liner(data2)

        assert service.complete.await_count == 2

    @pytest.mark.asyncio
    async def test_generate_all_summaries_cached(self):
        service = _make_ai_service("All cached")
        summarizer = AIReportSummarizer(ai_service=service)
        data = _make_report_data()

        result1 = await summarizer.generate_all_summaries(data)
        result2 = await summarizer.generate_all_summaries(data)

        assert result1 is result2  # Same object from cache
        # 4 calls for individual summaries on first run, 0 on second
        assert service.complete.await_count == 4

    def test_expired_cache_is_evicted(self):
        summarizer = AIReportSummarizer()
        summarizer._cache_ttl = 0  # Expire immediately

        summarizer._set_cached("key1", "value1")
        assert summarizer._get_cached("key1") is None

    def test_valid_cache_returns_value(self):
        summarizer = AIReportSummarizer()
        summarizer._set_cached("key1", "value1")
        assert summarizer._get_cached("key1") == "value1"
