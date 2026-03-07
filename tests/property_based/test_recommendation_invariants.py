"""Property-based tests for the recommendation engine.

Verifies that recommendations always have valid structure regardless
of input combination.

Run with: pytest tests/property_based/test_recommendation_invariants.py -v
"""

import pytest
from hypothesis import given, settings, HealthCheck
from unittest.mock import patch, MagicMock

from models.tax_return import TaxReturn
from calculator.tax_calculator import TaxCalculator

from conftest import tax_return_strategy


# Suppress slow test warnings for property-based tests
PROP_SETTINGS = settings(
    max_examples=50,
    deadline=10000,
    suppress_health_check=[HealthCheck.too_slow],
)


class TestRecommendationEngineInvariants:
    """Recommendation engine must produce valid output for any input."""

    @given(tax_return=tax_return_strategy())
    @PROP_SETTINGS
    def test_engine_never_crashes(self, tax_return):
        """Recommendation engine must handle any valid TaxReturn."""
        try:
            from recommendation.recommendation_engine import TaxRecommendationEngine
        except ImportError:
            pytest.skip("recommendation_engine not available")

        # First calculate tax so engine has computed values
        calc = TaxCalculator()
        calculated = calc.calculate_complete_return(tax_return)

        engine = TaxRecommendationEngine()
        result = engine.analyze(calculated)
        assert result is not None

    @given(tax_return=tax_return_strategy())
    @PROP_SETTINGS
    def test_recommendations_have_positive_savings(self, tax_return):
        """Every recommendation must have non-negative estimated savings."""
        try:
            from recommendation.recommendation_engine import TaxRecommendationEngine
        except ImportError:
            pytest.skip("recommendation_engine not available")

        calc = TaxCalculator()
        calculated = calc.calculate_complete_return(tax_return)

        engine = TaxRecommendationEngine()
        result = engine.analyze(calculated)

        # Check top opportunities if they exist
        result_dict = result.to_dict() if hasattr(result, 'to_dict') else {}
        opportunities = result_dict.get('top_opportunities', [])

        for opp in opportunities:
            savings = opp.get('estimated_savings', 0)
            assert savings >= 0, (
                f"Recommendation '{opp.get('title', 'unknown')}' has negative savings: {savings}"
            )

    @given(tax_return=tax_return_strategy())
    @PROP_SETTINGS
    def test_quick_analysis_never_crashes(self, tax_return):
        """Quick analysis must handle any valid TaxReturn."""
        try:
            from recommendation.recommendation_engine import TaxRecommendationEngine
        except ImportError:
            pytest.skip("recommendation_engine not available")

        calc = TaxCalculator()
        calculated = calc.calculate_complete_return(tax_return)

        engine = TaxRecommendationEngine()
        result = engine.get_quick_analysis(calculated)
        assert isinstance(result, dict)
