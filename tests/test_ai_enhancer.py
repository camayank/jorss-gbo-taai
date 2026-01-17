"""
Tests for AI Recommendation Enhancer.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestAIRecommendationEnhancer:
    """Tests for AI recommendation enhancer."""

    def test_import(self):
        """Test module can be imported."""
        from recommendation.ai_enhancer import (
            AIRecommendationEnhancer,
            AIEnhancedRecommendation,
            AIRecommendationSummary,
            get_ai_enhancer,
        )
        assert AIRecommendationEnhancer is not None
        assert AIEnhancedRecommendation is not None
        assert AIRecommendationSummary is not None
        assert get_ai_enhancer is not None

    def test_enhancer_without_api_key(self):
        """Test enhancer works without API key (fallback mode)."""
        from recommendation.ai_enhancer import AIRecommendationEnhancer

        enhancer = AIRecommendationEnhancer(api_key=None)
        assert not enhancer.is_available

    def test_fallback_enhancement(self):
        """Test fallback enhancement when AI is unavailable."""
        from recommendation.ai_enhancer import AIRecommendationEnhancer
        from recommendation.recommendation_engine import TaxSavingOpportunity

        enhancer = AIRecommendationEnhancer(api_key=None)

        opportunity = TaxSavingOpportunity(
            category="credits",
            title="Claim Child Tax Credit",
            estimated_savings=2000,
            priority="immediate",
            description="You have 2 qualifying children under 17",
            action_required="Complete Schedule 8812",
            confidence=95.0,
            irs_reference="IRC Section 24",
        )

        result = enhancer.enhance_recommendation(opportunity)

        assert result.original_title == "Claim Child Tax Credit"
        assert result.estimated_savings == 2000
        assert result.irs_reference == "IRC Section 24"
        assert len(result.action_steps) > 0
        assert "95" in result.confidence_explanation

    def test_income_range_calculation(self):
        """Test income range categorization."""
        from recommendation.ai_enhancer import AIRecommendationEnhancer

        enhancer = AIRecommendationEnhancer()

        assert "under $50,000" in enhancer._get_income_range(40000)
        assert "$50,000-$100,000" in enhancer._get_income_range(75000)
        assert "$100,000-$200,000" in enhancer._get_income_range(150000)
        assert "$200,000-$500,000" in enhancer._get_income_range(300000)
        assert "over $500,000" in enhancer._get_income_range(600000)

    def test_singleton_instance(self):
        """Test singleton getter."""
        from recommendation.ai_enhancer import get_ai_enhancer

        enhancer1 = get_ai_enhancer()
        enhancer2 = get_ai_enhancer()

        assert enhancer1 is enhancer2

    def test_enhance_with_taxpayer_context(self):
        """Test enhancement with taxpayer context."""
        from recommendation.ai_enhancer import AIRecommendationEnhancer
        from recommendation.recommendation_engine import TaxSavingOpportunity

        enhancer = AIRecommendationEnhancer(api_key=None)

        opportunity = TaxSavingOpportunity(
            category="deductions",
            title="Switch to Itemized Deductions",
            estimated_savings=1500,
            priority="immediate",
            description="Your itemized deductions exceed standard deduction",
            action_required="File Schedule A",
            confidence=85.0,
            irs_reference="IRC Section 63; Schedule A",
        )

        context = {
            "filing_status": "married_joint",
            "agi": 150000,
            "has_dependents": True,
        }

        result = enhancer.enhance_recommendation(opportunity, context)

        assert result is not None
        assert result.original_title == "Switch to Itemized Deductions"


class TestAIEnhancedRecommendation:
    """Tests for AIEnhancedRecommendation dataclass."""

    def test_dataclass_fields(self):
        """Test all required fields exist."""
        from recommendation.ai_enhancer import AIEnhancedRecommendation

        rec = AIEnhancedRecommendation(
            original_title="Test",
            original_description="Test desc",
            estimated_savings=1000,
            personalized_explanation="Personalized",
            action_steps=["Step 1", "Step 2"],
            common_questions=[{"question": "Q?", "answer": "A"}],
            risk_considerations=["Risk 1"],
            related_opportunities=["Related"],
            confidence_explanation="High confidence",
            irs_reference="IRC 1",
            priority="immediate",
            category="credits",
        )

        assert rec.original_title == "Test"
        assert rec.estimated_savings == 1000
        assert len(rec.action_steps) == 2
        assert len(rec.common_questions) == 1


class TestAIRecommendationSummary:
    """Tests for AIRecommendationSummary dataclass."""

    def test_dataclass_fields(self):
        """Test all required fields exist."""
        from recommendation.ai_enhancer import AIRecommendationSummary

        summary = AIRecommendationSummary(
            executive_summary="Summary here",
            key_takeaways=["Point 1", "Point 2"],
            priority_actions=["Action 1"],
            estimated_total_savings=5000,
            confidence_summary="High confidence overall",
            personalized_advice="Your advice here",
            warnings=["Warning 1"],
        )

        assert summary.executive_summary == "Summary here"
        assert summary.estimated_total_savings == 5000
        assert len(summary.key_takeaways) == 2
        assert len(summary.warnings) == 1


class TestFallbackSummary:
    """Tests for fallback summary generation."""

    def test_fallback_summary_without_ai(self):
        """Test fallback summary when AI is unavailable."""
        from recommendation.ai_enhancer import AIRecommendationEnhancer
        from recommendation.recommendation_engine import (
            TaxSavingOpportunity,
            ComprehensiveRecommendation,
            FilingStatusRecommendation,
            DeductionRecommendation,
            CreditRecommendation,
            TaxStrategyReport,
        )

        enhancer = AIRecommendationEnhancer(api_key=None)

        # Create mock comprehensive recommendation
        opportunity = TaxSavingOpportunity(
            category="credits",
            title="Test Credit",
            estimated_savings=1000,
            priority="immediate",
            description="Test",
            action_required="Do something",
            confidence=90.0,
            irs_reference="IRC 24",
        )

        # Create minimal mock objects for the comprehensive recommendation
        mock_filing = Mock(spec=FilingStatusRecommendation)
        mock_deduction = Mock(spec=DeductionRecommendation)
        mock_credit = Mock(spec=CreditRecommendation)
        mock_strategy = Mock(spec=TaxStrategyReport)

        recommendation = ComprehensiveRecommendation(
            tax_year=2025,
            generated_at="2025-01-17",
            taxpayer_name="John Doe",
            filing_status="single",
            current_federal_tax=10000,
            current_state_tax=2000,
            current_total_tax=12000,
            current_effective_rate=15.0,
            current_marginal_rate=22.0,
            optimized_federal_tax=9000,
            optimized_state_tax=1800,
            optimized_total_tax=10800,
            optimized_effective_rate=13.5,
            total_potential_savings=1200,
            immediate_action_savings=800,
            current_year_savings=200,
            long_term_annual_savings=200,
            filing_status_recommendation=mock_filing,
            deduction_recommendation=mock_deduction,
            credit_recommendation=mock_credit,
            strategy_report=mock_strategy,
            top_opportunities=[opportunity],
            all_opportunities=[opportunity],
            executive_summary="Test summary",
            detailed_findings=["Finding 1"],
            warnings=["Warning 1"],
            disclaimers=["Disclaimer 1"],
            overall_confidence=85.0,
            data_completeness=90.0,
        )

        summary = enhancer.generate_summary(recommendation)

        assert summary is not None
        assert summary.estimated_total_savings == 1200
        assert "1,200" in summary.key_takeaways[0]
        assert len(summary.warnings) > 0


class TestPlainLanguageExplanation:
    """Tests for plain language explanation generation."""

    def test_plain_language_fallback(self):
        """Test plain language explanation without AI."""
        from recommendation.ai_enhancer import AIRecommendationEnhancer
        from recommendation.recommendation_engine import TaxSavingOpportunity

        enhancer = AIRecommendationEnhancer(api_key=None)

        opportunity = TaxSavingOpportunity(
            category="retirement",
            title="Maximize 401(k) Contributions",
            estimated_savings=3000,
            priority="current_year",
            description="You can contribute $5,000 more to reach the annual limit",
            action_required="Contact your HR department",
            confidence=95.0,
            irs_reference="IRC Section 402(g)",
        )

        result = enhancer.explain_in_plain_language(opportunity)

        # Should return original description when AI unavailable
        assert result == opportunity.description


class TestIntegrationWithRecommendationEngine:
    """Integration tests with recommendation engine."""

    def test_enhancer_accepts_recommendation_engine_output(self):
        """Test enhancer works with recommendation engine output."""
        from recommendation.ai_enhancer import AIRecommendationEnhancer
        from recommendation.recommendation_engine import TaxSavingOpportunity

        enhancer = AIRecommendationEnhancer(api_key=None)

        # Simulate output from recommendation engine
        opportunities = [
            TaxSavingOpportunity(
                category="credits",
                title="Child Tax Credit",
                estimated_savings=2000,
                priority="immediate",
                description="2 qualifying children",
                action_required="Complete Schedule 8812",
                confidence=95.0,
                irs_reference="IRC Section 24; Schedule 8812",
            ),
            TaxSavingOpportunity(
                category="deductions",
                title="HSA Contribution",
                estimated_savings=1000,
                priority="current_year",
                description="Contribute to HSA before deadline",
                action_required="Make HSA contribution",
                confidence=90.0,
                irs_reference="IRC Section 223; Form 8889",
            ),
        ]

        # Enhance all opportunities
        enhanced = [enhancer.enhance_recommendation(opp) for opp in opportunities]

        assert len(enhanced) == 2
        assert enhanced[0].original_title == "Child Tax Credit"
        assert enhanced[1].original_title == "HSA Contribution"
        assert all(e.irs_reference for e in enhanced)
