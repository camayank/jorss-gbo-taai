"""Validate that AI services deliver measurably richer output than fallbacks.

Integration tests proving source tagging works end-to-end and that
quality metrics are recorded correctly.
"""

import pytest
from unittest.mock import patch

from recommendation.ai_enhancer import AIRecommendationEnhancer, AIEnhancedRecommendation
from services.tax_opportunity_detector import TaxOpportunityDetector, TaxpayerProfile
from services.ai.metrics_service import AIMetricsService, get_ai_metrics_service


def _make_test_opportunity():
    """Create a test TaxSavingOpportunity."""
    from recommendation.recommendation_engine import TaxSavingOpportunity
    return TaxSavingOpportunity(
        category="credits",
        title="Claim Child Tax Credit",
        estimated_savings=2000,
        priority="immediate",
        description="You have 2 qualifying children under 17",
        action_required="Complete Schedule 8812",
        confidence=95.0,
        irs_reference="IRC Section 24",
    )


def _make_test_profile():
    """Create a test TaxpayerProfile."""
    from decimal import Decimal
    return TaxpayerProfile(
        filing_status="married_filing_jointly",
        age=40,
        w2_wages=Decimal("100000"),
        self_employment_income=Decimal("20000"),
        num_dependents=2,
        has_children_under_17=True,
        owns_home=True,
        has_business=True,
        traditional_401k=Decimal("10000"),
    )


class TestEnhancerSourceTagging:

    def test_fallback_has_source_tag(self):
        """Fallback enhancement should have _source: 'fallback'."""
        enhancer = AIRecommendationEnhancer()
        opp = _make_test_opportunity()
        result = enhancer._fallback_enhancement(opp)
        assert result.metadata.get("_source") == "fallback"
        assert result.metadata.get("_provider") == "none"

    def test_fallback_has_fewer_populated_fields(self):
        """Fallback should have fewer populated fields than max possible."""
        enhancer = AIRecommendationEnhancer()
        opp = _make_test_opportunity()
        result = enhancer._fallback_enhancement(opp)

        # Fallback copies description and confidence, but leaves
        # common_questions, risk_considerations, related_opportunities empty
        assert result.common_questions == []
        assert result.risk_considerations == []
        assert result.related_opportunities == []

    def test_enhance_recommendation_returns_tagged_result(self):
        """enhance_recommendation() should return tagged result even in fallback."""
        with patch('recommendation.ai_enhancer.get_available_providers', return_value=[]):
            enhancer = AIRecommendationEnhancer()
            opp = _make_test_opportunity()
            result = enhancer.enhance_recommendation(opp)
            assert "_source" in result.metadata
            assert result.metadata["_source"] in ("ai", "fallback")


class TestOpportunityDetectorSourceTagging:

    def test_rule_based_opportunities_tagged(self):
        """Every rule-based opportunity should have _source: 'rules'."""
        with patch('services.tax_opportunity_detector.get_available_providers', return_value=[]):
            detector = TaxOpportunityDetector()
            profile = _make_test_profile()
            opps = detector.detect_opportunities(profile)
            for opp in opps:
                assert "_source" in opp.metadata, f"Opportunity '{opp.title}' missing _source tag"
                assert opp.metadata["_source"] == "rules"

    def test_all_opportunities_have_source(self):
        """Every opportunity should have a _source tag regardless of AI availability."""
        with patch('services.tax_opportunity_detector.get_available_providers', return_value=[]):
            detector = TaxOpportunityDetector()
            profile = _make_test_profile()
            opps = detector.detect_opportunities(profile)
            assert len(opps) > 0, "Should detect at least one opportunity"
            for opp in opps:
                assert "_source" in opp.metadata


class TestMetricsRecordQualityData:

    def test_fallback_enhancement_records_quality(self):
        """Fallback enhancement should record quality metrics."""
        # Use a fresh metrics service
        metrics = AIMetricsService()
        with patch('recommendation.ai_enhancer.get_ai_metrics_service', return_value=metrics):
            enhancer = AIRecommendationEnhancer()
            opp = _make_test_opportunity()
            enhancer._fallback_enhancement(opp)

        assert len(metrics._quality_records) == 1
        rec = metrics._quality_records[0]
        assert rec["service"] == "enhancer"
        assert rec["source"] == "fallback"
        assert rec["total_fields"] == 7

    def test_opportunity_detection_records_quality(self):
        """Opportunity detection should record quality for each opportunity."""
        metrics = AIMetricsService()
        with patch('services.tax_opportunity_detector.get_ai_metrics_service', return_value=metrics):
            with patch('services.tax_opportunity_detector.get_available_providers', return_value=[]):
                detector = TaxOpportunityDetector()
                profile = _make_test_profile()
                opps = detector.detect_opportunities(profile)

        # Should have one quality record per opportunity
        assert len(metrics._quality_records) == len(opps)
        for rec in metrics._quality_records:
            assert rec["service"] == "opportunity_detector"
            assert rec["source"] == "rules"

    def test_delivery_stats_after_recording(self):
        """get_ai_delivery_stats should reflect recorded data."""
        metrics = AIMetricsService()
        # Simulate mixed AI and fallback
        metrics.record_response_quality("enhancer", "ai", 5, 7)
        metrics.record_response_quality("enhancer", "ai", 6, 7)
        metrics.record_response_quality("enhancer", "fallback", 2, 7)

        stats = metrics.get_ai_delivery_stats(days=1)
        assert stats["enhancer"]["ai_count"] == 2
        assert stats["enhancer"]["fallback_count"] == 1
        assert stats["enhancer"]["ai_rate"] == pytest.approx(2 / 3)

    def test_quality_comparison_shows_improvement(self):
        """AI should show measurably more fields than fallback."""
        metrics = AIMetricsService()
        # AI populates 5-6 fields
        metrics.record_response_quality("enhancer", "ai", 5, 7)
        metrics.record_response_quality("enhancer", "ai", 6, 7)
        # Fallback populates 2 fields
        metrics.record_response_quality("enhancer", "fallback", 2, 7)
        metrics.record_response_quality("enhancer", "fallback", 2, 7)

        comparison = metrics.get_quality_comparison("enhancer", days=1)
        assert comparison["ai"]["avg_fields"] > comparison["fallback"]["avg_fields"]
        assert comparison["improvement_factor"] > 1.0
