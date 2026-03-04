"""Tests for AI quality metrics collection (record_response_quality, get_ai_delivery_stats, get_quality_comparison)."""

import pytest
from services.ai.metrics_service import AIMetricsService


@pytest.fixture
def metrics():
    return AIMetricsService()


class TestRecordResponseQuality:

    def test_record_stores_quality_data(self, metrics):
        metrics.record_response_quality(
            service="enhancer", source="ai",
            response_fields_populated=5, total_fields=7,
        )
        assert len(metrics._quality_records) == 1
        rec = metrics._quality_records[0]
        assert rec["service"] == "enhancer"
        assert rec["source"] == "ai"
        assert rec["fields_populated"] == 5
        assert rec["total_fields"] == 7
        assert rec["field_rate"] == pytest.approx(5 / 7)

    def test_record_with_session_id(self, metrics):
        metrics.record_response_quality(
            service="enhancer", source="fallback",
            response_fields_populated=2, total_fields=7,
            session_id="sess-123",
        )
        assert metrics._quality_records[0]["session_id"] == "sess-123"

    def test_record_zero_total_fields(self, metrics):
        metrics.record_response_quality(
            service="enhancer", source="ai",
            response_fields_populated=0, total_fields=0,
        )
        assert metrics._quality_records[0]["field_rate"] == 0


class TestGetAIDeliveryStats:

    def test_empty_returns_empty_dict(self, metrics):
        assert metrics.get_ai_delivery_stats(days=7) == {}

    def test_single_service_stats(self, metrics):
        # 3 AI, 2 fallback
        for _ in range(3):
            metrics.record_response_quality("enhancer", "ai", 5, 7)
        for _ in range(2):
            metrics.record_response_quality("enhancer", "fallback", 2, 7)

        stats = metrics.get_ai_delivery_stats(days=7)
        assert "enhancer" in stats
        assert stats["enhancer"]["ai_count"] == 3
        assert stats["enhancer"]["fallback_count"] == 2
        assert stats["enhancer"]["ai_rate"] == pytest.approx(0.6)
        assert stats["enhancer"]["avg_ai_fields"] == pytest.approx(5.0)
        assert stats["enhancer"]["avg_fallback_fields"] == pytest.approx(2.0)

    def test_multiple_services(self, metrics):
        metrics.record_response_quality("enhancer", "ai", 5, 7)
        metrics.record_response_quality("opportunity_detector", "rules", 3, 6)

        stats = metrics.get_ai_delivery_stats(days=7)
        assert "enhancer" in stats
        assert "opportunity_detector" in stats
        assert stats["enhancer"]["ai_count"] == 1
        assert stats["opportunity_detector"]["fallback_count"] == 1

    def test_all_ai_gives_rate_1(self, metrics):
        for _ in range(5):
            metrics.record_response_quality("enhancer", "ai", 6, 7)
        stats = metrics.get_ai_delivery_stats(days=7)
        assert stats["enhancer"]["ai_rate"] == pytest.approx(1.0)
        assert stats["enhancer"]["fallback_count"] == 0


class TestGetQualityComparison:

    def test_empty_service(self, metrics):
        result = metrics.get_quality_comparison("enhancer", days=30)
        assert result["ai"]["count"] == 0
        assert result["fallback"]["count"] == 0
        assert result["improvement_factor"] == 0

    def test_comparison_with_data(self, metrics):
        # AI: 5 fields populated out of 7
        metrics.record_response_quality("enhancer", "ai", 5, 7)
        metrics.record_response_quality("enhancer", "ai", 6, 7)
        # Fallback: 2 fields populated out of 7
        metrics.record_response_quality("enhancer", "fallback", 2, 7)

        result = metrics.get_quality_comparison("enhancer", days=30)
        assert result["ai"]["count"] == 2
        assert result["ai"]["avg_fields"] == pytest.approx(5.5)
        assert result["fallback"]["count"] == 1
        assert result["fallback"]["avg_fields"] == pytest.approx(2.0)
        assert result["improvement_factor"] == pytest.approx(2.75)

    def test_only_ai_data(self, metrics):
        metrics.record_response_quality("enhancer", "ai", 6, 7)
        result = metrics.get_quality_comparison("enhancer", days=30)
        assert result["ai"]["count"] == 1
        assert result["fallback"]["count"] == 0
        # No fallback data → improvement_factor = 0
        assert result["improvement_factor"] == 0

    def test_filters_by_service(self, metrics):
        metrics.record_response_quality("enhancer", "ai", 5, 7)
        metrics.record_response_quality("opportunity_detector", "ai", 4, 6)

        result = metrics.get_quality_comparison("enhancer", days=30)
        assert result["ai"]["count"] == 1  # Only enhancer records
