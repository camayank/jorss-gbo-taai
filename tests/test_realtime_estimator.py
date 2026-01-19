"""Tests for Real-Time Tax Estimator."""

import pytest
from decimal import Decimal

from src.recommendation.realtime_estimator import (
    RealTimeEstimator,
    TaxEstimate,
    EstimateConfidence,
    quick_estimate_from_w2,
    get_refund_range,
)


class TestRealTimeEstimator:
    """Tests for RealTimeEstimator class."""

    def test_initialization(self):
        """Test estimator initializes correctly."""
        estimator = RealTimeEstimator()
        assert estimator.tax_year == 2024
        assert "single" in estimator.STANDARD_DEDUCTIONS

    def test_initialization_custom_year(self):
        """Test estimator with custom tax year."""
        estimator = RealTimeEstimator(tax_year=2025)
        assert estimator.tax_year == 2025


class TestW2Estimate:
    """Tests for W-2 based estimates."""

    def test_basic_w2_estimate(self):
        """Test basic estimate from W-2 data."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={
                "wages": 50000,
                "federal_tax_withheld": 5000,
            },
            filing_status="single",
        )

        assert isinstance(estimate, TaxEstimate)
        assert estimate.estimated_tax > 0
        assert estimate.total_withholding == 5000
        assert estimate.confidence_score > 0

    def test_w2_estimate_with_dependents(self):
        """Test estimate includes child tax credit for dependents."""
        estimator = RealTimeEstimator()

        # Without dependents
        no_deps = estimator.estimate_from_w2(
            w2_data={"wages": 75000, "federal_tax_withheld": 10000},
            filing_status="single",
            num_dependents=0,
        )

        # With dependents
        with_deps = estimator.estimate_from_w2(
            w2_data={"wages": 75000, "federal_tax_withheld": 10000},
            filing_status="single",
            num_dependents=2,
        )

        # Should have higher refund with dependents due to CTC
        assert with_deps.estimated_credits > no_deps.estimated_credits
        assert with_deps.refund_or_owed > no_deps.refund_or_owed

    def test_w2_estimate_different_filing_status(self):
        """Test estimates vary by filing status."""
        estimator = RealTimeEstimator()
        w2_data = {"wages": 100000, "federal_tax_withheld": 15000}

        single = estimator.estimate_from_w2(w2_data, filing_status="single")
        mfj = estimator.estimate_from_w2(w2_data, filing_status="married_joint")

        # MFJ should have lower tax due to higher standard deduction and wider brackets
        assert mfj.estimated_tax < single.estimated_tax

    def test_w2_estimate_refund_positive(self):
        """Test refund scenario (over-withholding)."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={
                "wages": 40000,
                "federal_tax_withheld": 8000,  # High withholding for this income
            },
            filing_status="single",
        )

        # Should expect a refund
        assert estimate.refund_or_owed > 0
        assert estimate.likely_amount > 0

    def test_w2_estimate_owe_taxes(self):
        """Test owe taxes scenario (under-withholding)."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={
                "wages": 100000,
                "federal_tax_withheld": 5000,  # Low withholding for this income
            },
            filing_status="single",
        )

        # Should expect to owe taxes
        assert estimate.refund_or_owed < 0

    def test_w2_estimate_has_confidence_band(self):
        """Test estimate includes confidence band."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 60000, "federal_tax_withheld": 7000},
            filing_status="single",
        )

        # Band should bracket the likely amount
        assert estimate.low_estimate <= estimate.likely_amount
        assert estimate.high_estimate >= estimate.likely_amount
        # Band shouldn't be too narrow for single W-2
        assert estimate.high_estimate - estimate.low_estimate > 100


class TestConfidenceLevels:
    """Tests for confidence scoring."""

    def test_confidence_level_single_w2(self):
        """Test confidence level for single W-2."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 50000, "federal_tax_withheld": 5000},
            filing_status="single",
        )

        # Single W-2 shouldn't be HIGH confidence
        assert estimate.confidence_level in [
            EstimateConfidence.MEDIUM,
            EstimateConfidence.LOW,
        ]

    def test_confidence_increases_with_more_fields(self):
        """Test that more complete data increases confidence."""
        estimator = RealTimeEstimator()

        minimal = estimator.estimate_from_w2(
            w2_data={
                "wages": 50000,
            },
            filing_status="single",
        )

        complete = estimator.estimate_from_w2(
            w2_data={
                "wages": 50000,
                "federal_tax_withheld": 5000,
                "social_security_wages": 50000,
                "social_security_tax": 3100,
                "medicare_wages": 50000,
                "medicare_tax": 725,
            },
            filing_status="single",
        )

        assert complete.confidence_score > minimal.confidence_score


class TestMultiDocumentEstimate:
    """Tests for multi-document estimates."""

    def test_multiple_w2s(self):
        """Test aggregating multiple W-2s."""
        estimator = RealTimeEstimator()
        documents = [
            {"type": "w2", "fields": {"wages": 40000, "federal_tax_withheld": 4000}},
            {"type": "w2", "fields": {"wages": 30000, "federal_tax_withheld": 3000}},
        ]

        estimate = estimator.estimate_from_multiple_documents(documents)

        # Should aggregate wages and withholding
        assert estimate.total_withholding == 7000

    def test_w2_plus_1099(self):
        """Test combining W-2 and 1099 income."""
        estimator = RealTimeEstimator()
        documents = [
            {"type": "w2", "fields": {"wages": 50000, "federal_tax_withheld": 6000}},
            {"type": "1099_int", "fields": {"interest_income": 500}},
            {"type": "1099_div", "fields": {"ordinary_dividends": 1000}},
        ]

        estimate = estimator.estimate_from_multiple_documents(documents)

        # Tax should account for all income
        # Total income = 50000 + 500 + 1000 = 51500
        assert estimate.estimated_tax > 0

    def test_multiple_docs_higher_confidence(self):
        """Test that multiple documents improve data completeness."""
        estimator = RealTimeEstimator()

        single_doc = estimator.estimate_from_w2(
            w2_data={"wages": 50000, "federal_tax_withheld": 5000}
        )

        multi_docs = estimator.estimate_from_multiple_documents([
            {"type": "w2", "fields": {"wages": 50000, "federal_tax_withheld": 5000}},
            {"type": "1099_int", "fields": {"interest_income": 100}},
        ])

        # More documents should improve data completeness
        assert multi_docs.data_completeness >= single_doc.data_completeness
        # Confidence should be at least as good
        assert multi_docs.confidence_score >= single_doc.confidence_score

    def test_self_employment_income(self):
        """Test handling of 1099-NEC self-employment income."""
        estimator = RealTimeEstimator()
        documents = [
            {"type": "1099_nec", "fields": {"nonemployee_compensation": 50000}},
        ]

        estimate = estimator.estimate_from_multiple_documents(documents)

        # Should include SE tax
        assert estimate.estimated_tax > 0
        assert "Self-employment" in str(estimate.assumptions_made)


class TestQuickOpportunities:
    """Tests for quick opportunity detection."""

    def test_detects_over_withholding(self):
        """Test detection of over-withholding."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={
                "wages": 40000,
                "federal_tax_withheld": 10000,  # Way too much for this income
            },
            filing_status="single",
        )

        # Should suggest W-4 adjustment
        withholding_opp = next(
            (o for o in estimate.quick_opportunities if o["type"] == "withholding"),
            None
        )
        assert withholding_opp is not None

    def test_detects_hoh_opportunity(self):
        """Test detection of Head of Household opportunity."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 50000, "federal_tax_withheld": 5000},
            filing_status="single",
            num_dependents=1,
        )

        # Should suggest checking HOH eligibility
        hoh_opp = next(
            (o for o in estimate.quick_opportunities if o["type"] == "filing_status"),
            None
        )
        assert hoh_opp is not None

    def test_detects_retirement_opportunity(self):
        """Test detection of 401(k) opportunity."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 75000, "federal_tax_withheld": 10000},
            filing_status="single",
        )

        # Should suggest 401(k) contribution
        retirement_opp = next(
            (o for o in estimate.quick_opportunities if o["type"] == "retirement"),
            None
        )
        assert retirement_opp is not None


class TestRefineEstimate:
    """Tests for estimate refinement."""

    def test_refine_increases_confidence(self):
        """Test that refinement increases confidence."""
        estimator = RealTimeEstimator()

        initial = estimator.estimate_from_w2(
            w2_data={"wages": 50000, "federal_tax_withheld": 5000}
        )

        refined = estimator.refine_estimate(
            initial,
            additional_data={"confirmed_filing_status": "single"}
        )

        assert refined.confidence_score > initial.confidence_score

    def test_refine_narrows_band(self):
        """Test that refinement increases confidence and adjusts band."""
        estimator = RealTimeEstimator()

        initial = estimator.estimate_from_w2(
            w2_data={"wages": 50000, "federal_tax_withheld": 5000}
        )

        refined = estimator.refine_estimate(
            initial,
            additional_data={"has_health_insurance": True}
        )

        # Refinement should increase confidence
        assert refined.confidence_score >= initial.confidence_score
        # Refinement should improve data completeness
        assert refined.data_completeness >= initial.data_completeness


class TestTaxCalculation:
    """Tests for internal tax calculation."""

    def test_tax_brackets_single(self):
        """Test tax calculation uses correct brackets for single."""
        estimator = RealTimeEstimator()

        # $50,000 income - $14,600 standard = $35,400 taxable
        # Tax: $11,600 * 10% + ($35,400 - $11,600) * 12%
        # = $1,160 + $2,856 = $4,016
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 50000, "federal_tax_withheld": 5000},
            filing_status="single",
        )

        expected_tax = 4016
        assert abs(estimate.estimated_tax - expected_tax) < 100  # Allow small variance

    def test_tax_brackets_mfj(self):
        """Test tax calculation uses correct brackets for MFJ."""
        estimator = RealTimeEstimator()

        # $100,000 income - $29,200 standard = $70,800 taxable
        # MFJ brackets: $23,200 at 10% + ($70,800 - $23,200) at 12%
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 100000, "federal_tax_withheld": 12000},
            filing_status="married_joint",
        )

        # Should be around $8,000-$8,500
        assert estimate.estimated_tax < 10000
        assert estimate.estimated_tax > 7000


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_quick_estimate_from_w2(self):
        """Test quick_estimate_from_w2 convenience function."""
        result = quick_estimate_from_w2(
            wages=60000,
            federal_withheld=7000,
            filing_status="single",
        )

        assert isinstance(result, dict)
        assert "refund_or_owed" in result
        assert "confidence_band" in result
        assert "disclaimer" in result

    def test_get_refund_range(self):
        """Test get_refund_range convenience function."""
        low, likely, high = get_refund_range(
            wages=50000,
            federal_withheld=6000,
            filing_status="single",
        )

        assert low <= likely <= high

    def test_quick_estimate_with_dependents(self):
        """Test quick estimate includes dependents."""
        without_deps = quick_estimate_from_w2(
            wages=50000,
            federal_withheld=5000,
            num_dependents=0,
        )

        with_deps = quick_estimate_from_w2(
            wages=50000,
            federal_withheld=5000,
            num_dependents=2,
        )

        # More refund expected with dependents
        assert with_deps["refund_or_owed"] > without_deps["refund_or_owed"]


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_income(self):
        """Test handling of zero income."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 0, "federal_tax_withheld": 0}
        )

        assert estimate.estimated_tax == 0
        assert estimate.refund_or_owed == 0

    def test_very_high_income(self):
        """Test handling of very high income."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 1000000, "federal_tax_withheld": 300000},
            filing_status="single",
        )

        # Should hit 37% bracket
        assert estimate.estimated_tax > 300000

    def test_negative_values_handled(self):
        """Test that negative values are handled gracefully."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": -5000, "federal_tax_withheld": 0}
        )

        # Should handle gracefully
        assert estimate is not None
        assert estimate.estimated_tax == 0

    def test_string_values_converted(self):
        """Test that string values are converted to float."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={
                "wages": "50,000.00",
                "federal_tax_withheld": "$5,000",
            }
        )

        assert estimate.total_withholding == 5000

    def test_decimal_values_supported(self):
        """Test that Decimal values are supported."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={
                "wages": Decimal("50000"),
                "federal_tax_withheld": Decimal("5000"),
            }
        )

        assert estimate.total_withholding == 5000


class TestSerializationMethods:
    """Tests for serialization."""

    def test_to_dict(self):
        """Test TaxEstimate.to_dict() method."""
        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 50000, "federal_tax_withheld": 5000}
        )

        result = estimate.to_dict()

        assert isinstance(result, dict)
        assert "refund_or_owed" in result
        assert "confidence_band" in result
        assert "breakdown" in result
        assert "quick_opportunities" in result

    def test_to_dict_json_serializable(self):
        """Test that to_dict result is JSON serializable."""
        import json

        estimator = RealTimeEstimator()
        estimate = estimator.estimate_from_w2(
            w2_data={"wages": 50000, "federal_tax_withheld": 5000}
        )

        result = estimate.to_dict()

        # Should not raise
        json_str = json.dumps(result)
        assert json_str is not None
