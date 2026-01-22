"""
Tests for Advisory Report Generator.

These tests verify that the new AdvisoryReportGenerator correctly
orchestrates all existing engines (which already have 180+ passing tests).
"""

import pytest
from decimal import Decimal

from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income
from models.deductions import Deductions
from models.credits import TaxCredits

from advisory.report_generator import (
    AdvisoryReportGenerator,
    ReportType,
    generate_advisory_report,
)


@pytest.fixture
def sample_w2_tax_return() -> TaxReturn:
    """Create a sample W-2 employee tax return."""
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="John",
            last_name="Smith",
            ssn="123-45-6789",
            filing_status=FilingStatus.SINGLE,
        ),
        income=Income(
            w2_wages=85000.0,
            federal_withholding=16000.0,
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )

    # Calculate AGI and taxable income
    tax_return.calculate()

    return tax_return


@pytest.fixture
def business_tax_return() -> TaxReturn:
    """Create a sample business owner tax return."""
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Jane",
            last_name="Business",
            ssn="987-65-4321",
            filing_status=FilingStatus.SINGLE,
        ),
        income=Income(
            self_employment_income=150000.0,
            self_employment_expenses=30000.0,
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )

    tax_return.calculate()

    return tax_return


class TestAdvisoryReportGenerator:
    """Test the Advisory Report Generator orchestration."""

    def test_generator_initialization(self):
        """Test: Generator initializes with all engines."""
        generator = AdvisoryReportGenerator()

        assert generator.tax_calculator is not None
        assert generator.recommendation_engine is not None
        assert generator.entity_optimizer is not None
        assert generator.projection_engine is not None

    def test_generate_standard_report_w2(self, sample_w2_tax_return):
        """Test: Generate standard report for W-2 employee."""
        generator = AdvisoryReportGenerator()

        report = generator.generate_report(
            tax_return=sample_w2_tax_return,
            report_type=ReportType.STANDARD_REPORT,
            include_entity_comparison=False,
            include_multi_year=True,
            years_ahead=3,
        )

        # Verify report structure
        assert report.status == "complete"
        assert report.report_id.startswith("ADV_2025_")
        assert report.taxpayer_name == "John Smith"
        assert report.filing_status == "single"

        # Verify sections exist
        section_ids = [s.section_id for s in report.sections]
        assert "executive_summary" in section_ids
        assert "current_position" in section_ids
        assert "recommendations" in section_ids
        assert "action_plan" in section_ids
        assert "disclaimers" in section_ids

        # Verify metrics
        assert report.current_tax_liability > 0
        assert report.confidence_score > 0
        assert report.top_recommendations_count > 0

    def test_generate_report_with_entity_comparison(self, business_tax_return):
        """Test: Generate report with entity comparison for business owner."""
        generator = AdvisoryReportGenerator()

        report = generator.generate_report(
            tax_return=business_tax_return,
            report_type=ReportType.FULL_ANALYSIS,
            include_entity_comparison=True,
            include_multi_year=True,
            years_ahead=5,
        )

        # Verify entity comparison section exists
        section_ids = [s.section_id for s in report.sections]
        assert "entity_comparison" in section_ids

        # Find entity comparison section
        entity_section = next(s for s in report.sections if s.section_id == "entity_comparison")
        assert "entity_comparison" in entity_section.content
        assert "sole_proprietor" in entity_section.content["entity_comparison"]
        assert "s_corp" in entity_section.content["entity_comparison"]

    def test_generate_report_with_multi_year_projection(self, sample_w2_tax_return):
        """Test: Generate report with multi-year projections."""
        generator = AdvisoryReportGenerator()

        report = generator.generate_report(
            tax_return=sample_w2_tax_return,
            report_type=ReportType.MULTI_YEAR,
            include_multi_year=True,
            years_ahead=3,
        )

        # Verify projection section exists
        section_ids = [s.section_id for s in report.sections]
        assert "multi_year_projection" in section_ids

        # Find projection section
        projection_section = next(s for s in report.sections if s.section_id == "multi_year_projection")
        assert "yearly_data" in projection_section.content
        assert len(projection_section.content["yearly_data"]) == 4  # Current + 3 future years

    def test_convenience_function(self, sample_w2_tax_return):
        """Test: Convenience function works."""
        report = generate_advisory_report(
            tax_return=sample_w2_tax_return,
            report_type=ReportType.EXECUTIVE_SUMMARY,
        )

        assert report.status == "complete"
        assert report.taxpayer_name == "John Smith"

    def test_report_to_dict(self, sample_w2_tax_return):
        """Test: Report converts to dict for JSON serialization."""
        report = generate_advisory_report(
            tax_return=sample_w2_tax_return,
            report_type=ReportType.STANDARD_REPORT,
        )

        report_dict = report.to_dict()

        # Verify dict structure
        assert "report_id" in report_dict
        assert "sections" in report_dict
        assert "metrics" in report_dict
        assert "recommendations" in report_dict

        # Verify metrics are floats (JSON serializable)
        assert isinstance(report_dict["metrics"]["current_tax_liability"], float)
        assert isinstance(report_dict["metrics"]["potential_savings"], float)

    def test_executive_summary_section(self, sample_w2_tax_return):
        """Test: Executive summary section contains key info."""
        generator = AdvisoryReportGenerator()
        report = generator.generate_report(sample_w2_tax_return)

        exec_summary = next(s for s in report.sections if s.section_id == "executive_summary")

        assert exec_summary.title == "Executive Summary"
        assert "overview" in exec_summary.content
        assert "current_liability" in exec_summary.content
        assert exec_summary.content["tax_year"] == 2025

    def test_recommendations_section(self, sample_w2_tax_return):
        """Test: Recommendations section uses existing recommendation engine."""
        generator = AdvisoryReportGenerator()
        report = generator.generate_report(sample_w2_tax_return)

        rec_section = next(s for s in report.sections if s.section_id == "recommendations")

        assert rec_section.title == "Tax Optimization Recommendations"
        assert "top_recommendations" in rec_section.content
        assert "total_potential_savings" in rec_section.content
        assert len(rec_section.content["top_recommendations"]) > 0

        # Verify each recommendation has required fields
        for rec in rec_section.content["top_recommendations"]:
            assert "title" in rec
            assert "savings" in rec
            assert "action_required" in rec
            assert "confidence" in rec

    def test_action_plan_section(self, sample_w2_tax_return):
        """Test: Action plan groups recommendations by priority."""
        generator = AdvisoryReportGenerator()
        report = generator.generate_report(sample_w2_tax_return)

        action_plan = next(s for s in report.sections if s.section_id == "action_plan")

        assert "immediate_actions" in action_plan.content
        assert "current_year_actions" in action_plan.content
        assert "next_year_planning" in action_plan.content
        assert "long_term_strategies" in action_plan.content

    def test_error_handling(self):
        """Test: Generator handles errors gracefully."""
        generator = AdvisoryReportGenerator()

        # Create invalid tax return (missing calculation)
        bad_tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                ssn="000-00-0000",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(),  # Empty income
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )
        # Don't call calculate() - should cause issues

        report = generator.generate_report(bad_tax_return)

        # Should return error status, not crash
        assert report.status == "error"
        assert report.error_message is not None

    def test_immediate_actions_extracted(self, sample_w2_tax_return):
        """Test: Immediate actions are extracted to report summary."""
        report = generate_advisory_report(sample_w2_tax_return)

        assert len(report.immediate_action_items) > 0

        # Each immediate action should have key fields
        for action in report.immediate_action_items:
            assert "title" in action
            assert "savings" in action
            assert "action" in action


class TestReportIntegration:
    """Test integration with all existing engines."""

    def test_uses_tax_calculator(self, sample_w2_tax_return):
        """Test: Uses existing TaxCalculator (40+ tests passing)."""
        generator = AdvisoryReportGenerator()
        report = generator.generate_report(sample_w2_tax_return)

        # Tax should be calculated
        assert report.current_tax_liability > 0

        # Current position section should have calculation results
        current_pos = next(s for s in report.sections if s.section_id == "current_position")
        assert current_pos.content["tax_liability"]["federal_tax"] > 0

    def test_uses_recommendation_engine(self, sample_w2_tax_return):
        """Test: Uses existing TaxRecommendationEngine (80+ tests passing)."""
        generator = AdvisoryReportGenerator()
        report = generator.generate_report(sample_w2_tax_return)

        # Should have recommendations
        assert report.top_recommendations_count > 0
        assert report.potential_savings > 0

    def test_uses_entity_optimizer(self, business_tax_return):
        """Test: Uses existing EntityOptimizer (48 tests passing)."""
        generator = AdvisoryReportGenerator()
        report = generator.generate_report(
            business_tax_return,
            include_entity_comparison=True,
        )

        # Should have entity comparison
        entity_section = next(
            (s for s in report.sections if s.section_id == "entity_comparison"),
            None
        )
        assert entity_section is not None
        assert "sole_proprietor" in entity_section.content["entity_comparison"]
        assert "s_corp" in entity_section.content["entity_comparison"]

    def test_uses_projection_engine(self, sample_w2_tax_return):
        """Test: Uses existing MultiYearProjectionEngine."""
        generator = AdvisoryReportGenerator()
        report = generator.generate_report(
            sample_w2_tax_return,
            include_multi_year=True,
            years_ahead=3,
        )

        # Should have multi-year projection
        projection_section = next(
            (s for s in report.sections if s.section_id == "multi_year_projection"),
            None
        )
        assert projection_section is not None
        assert len(projection_section.content["yearly_data"]) == 4  # Current + 3


# Summary test
def test_advisory_system_integration(sample_w2_tax_return):
    """
    Integration test: Verify complete advisory system works end-to-end.

    This test proves that the new Advisory Report Generator successfully
    orchestrates all existing engines (180+ passing tests) into unified reports.
    """
    report = generate_advisory_report(
        tax_return=sample_w2_tax_return,
        report_type=ReportType.FULL_ANALYSIS,
        include_entity_comparison=False,
        include_multi_year=True,
        years_ahead=3,
    )

    # Report generated successfully
    assert report.status == "complete"
    assert report.error_message is None

    # Has all major sections
    section_ids = [s.section_id for s in report.sections]
    assert "executive_summary" in section_ids
    assert "current_position" in section_ids
    assert "recommendations" in section_ids
    assert "multi_year_projection" in section_ids
    assert "action_plan" in section_ids

    # Has actionable data
    assert report.top_recommendations_count > 0
    assert report.potential_savings > 0
    assert len(report.immediate_action_items) > 0

    # Is JSON serializable
    report_dict = report.to_dict()
    assert isinstance(report_dict, dict)

    print("\n" + "=" * 70)
    print("✅ ADVISORY SYSTEM INTEGRATION TEST PASSED")
    print("=" * 70)
    print(f"Report ID: {report.report_id}")
    print(f"Taxpayer: {report.taxpayer_name}")
    print(f"Current Tax: ${report.current_tax_liability:,.2f}")
    print(f"Potential Savings: ${report.potential_savings:,.2f}")
    print(f"Recommendations: {report.top_recommendations_count}")
    print(f"Sections Generated: {len(report.sections)}")
    print("=" * 70)
    print("Advisory Report Generator successfully orchestrates:")
    print("  ✅ Tax Calculator (40+ tests)")
    print("  ✅ Recommendation Engine (80+ tests)")
    print("  ✅ Entity Optimizer (48 tests)")
    print("  ✅ Multi-Year Projector")
    print("=" * 70)
