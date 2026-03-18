"""End-to-end pipeline integration tests for advisory report generation.

Pipeline: TaxReturn -> TaxCalculator -> RecommendationEngine -> ReportGenerator -> (optional) PDF

Covers:
- Simple single filer with W2 income
- Self-employed taxpayer with entity comparison
- Report sections are present and contain expected data
- No external AI services are called (mocked/disabled)
"""

import os
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Lightweight stubs matching the project's domain models
# ---------------------------------------------------------------------------

class _FilingStatus(Enum):
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    HEAD_OF_HOUSEHOLD = "head_of_household"


@dataclass
class _Taxpayer:
    first_name: str = "Test"
    last_name: str = "User"
    filing_status: _FilingStatus = _FilingStatus.SINGLE
    name: str = ""
    state: str = "CA"


@dataclass
class _Income:
    w2_wages: Decimal = Decimal("0")
    self_employment_income: Decimal = Decimal("0")
    self_employment_expenses: Decimal = Decimal("0")
    retirement_contributions_401k: Decimal = Decimal("0")
    interest_income: Decimal = Decimal("0")
    dividend_income: Decimal = Decimal("0")

    def get_total_income(self):
        return self.w2_wages + self.self_employment_income + self.interest_income + self.dividend_income

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
    adjusted_gross_income: Decimal = Decimal("0")
    taxable_income: Decimal = Decimal("0")
    tax_liability: Decimal = Decimal("0")
    state_tax_liability: Decimal = Decimal("0")
    refund_or_owed: float = 0.0


@dataclass
class _TaxResult:
    """Result from TaxCalculator.calculate_complete_return."""
    tax_liability: Decimal = Decimal("0")
    state_tax_liability: Decimal = Decimal("0")
    adjusted_gross_income: Decimal = Decimal("0")
    taxable_income: Decimal = Decimal("0")
    income: _Income = field(default_factory=_Income)
    deductions: _Deductions = field(default_factory=_Deductions)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_w2_filer(wages: float = 85_000) -> _TaxReturn:
    """Build a simple single filer with W2 income."""
    agi = Decimal(str(wages))
    taxable = agi - Decimal("15000")  # rough standard deduction
    tax = taxable * Decimal("0.18")   # rough effective rate

    return _TaxReturn(
        tax_year=2025,
        taxpayer=_Taxpayer(first_name="Alice", last_name="W2", filing_status=_FilingStatus.SINGLE),
        income=_Income(w2_wages=agi),
        deductions=_Deductions(use_standard_deduction=True),
        adjusted_gross_income=agi,
        taxable_income=taxable,
        tax_liability=tax,
        state_tax_liability=Decimal("2500"),
    )


def _build_self_employed(revenue: float = 150_000, expenses: float = 30_000) -> _TaxReturn:
    """Build a self-employed taxpayer with business income."""
    net_income = Decimal(str(revenue - expenses))
    agi = net_income
    taxable = agi - Decimal("15000")
    tax = taxable * Decimal("0.22")

    return _TaxReturn(
        tax_year=2025,
        taxpayer=_Taxpayer(first_name="Bob", last_name="Freelance", filing_status=_FilingStatus.SINGLE),
        income=_Income(
            self_employment_income=Decimal(str(revenue)),
            self_employment_expenses=Decimal(str(expenses)),
        ),
        deductions=_Deductions(use_standard_deduction=True),
        adjusted_gross_income=agi,
        taxable_income=taxable,
        tax_liability=tax,
        state_tax_liability=Decimal("3000"),
    )


def _make_calc_result(tax_return: _TaxReturn) -> _TaxResult:
    """Build a TaxResult matching the tax return data."""
    return _TaxResult(
        tax_liability=tax_return.tax_liability,
        state_tax_liability=tax_return.state_tax_liability,
        adjusted_gross_income=tax_return.adjusted_gross_income,
        taxable_income=tax_return.taxable_income,
        income=tax_return.income,
        deductions=tax_return.deductions,
    )


# ---------------------------------------------------------------------------
# Tests: Single W2 Filer Pipeline
# ---------------------------------------------------------------------------

class TestW2FilerPipeline:
    """End-to-end pipeline for a simple W2 single filer."""

    @patch("advisory.report_generator.MultiYearProjectionEngine")
    @patch("advisory.report_generator.EntityStructureOptimizer")
    @patch("advisory.report_generator.TaxRecommendationEngine")
    @patch("advisory.report_generator.TaxCalculator")
    def test_full_report_generation(
        self, MockCalc, MockRec, MockEntity, MockProjection
    ):
        """Full pipeline: TaxReturn -> Calculator -> Recommendations -> Report."""
        from advisory.report_generator import AdvisoryReportGenerator, ReportType

        tax_return = _build_w2_filer(85_000)
        calc_result = _make_calc_result(tax_return)

        # Mock calculator
        mock_calc = MagicMock()
        mock_calc.calculate_complete_return.return_value = calc_result
        MockCalc.return_value = mock_calc

        # Mock recommendation engine
        mock_rec = MagicMock()
        mock_rec_result = MagicMock()
        mock_rec_result.total_potential_savings = 4500.0
        mock_rec_result.overall_confidence = 78.0
        mock_rec_result.top_opportunities = []
        mock_rec_result.all_opportunities = []
        mock_rec.analyze.return_value = mock_rec_result
        MockRec.return_value = mock_rec

        # Mock projection engine
        mock_projection = MagicMock()
        mock_proj_result = MagicMock()
        mock_proj_result.base_year = 2025
        mock_proj_result.projection_years = 3
        mock_proj_result.yearly_projections = []
        mock_proj_result.total_projected_income = Decimal("270000")
        mock_proj_result.total_projected_tax = Decimal("50000")
        mock_proj_result.total_strategy_savings = Decimal("5000")
        mock_projection.project_multi_year.return_value = mock_proj_result
        MockProjection.return_value = mock_projection

        generator = AdvisoryReportGenerator(
            tax_calculator=mock_calc,
            recommendation_engine=mock_rec,
            projection_engine=mock_projection,
        )

        report = generator.generate_report(
            tax_return,
            report_type=ReportType.STANDARD_REPORT,
            include_entity_comparison=False,
            include_multi_year=True,
        )

        # Verify report metadata
        assert report.status == "complete"
        assert report.tax_year == 2025
        assert report.taxpayer_name == "Alice W2"
        assert report.filing_status == "single"
        assert report.report_type == ReportType.STANDARD_REPORT

        # Verify key metrics
        assert float(report.potential_savings) == 4500.0

        # Verify sections exist
        section_ids = [s.section_id for s in report.sections]
        assert "executive_summary" in section_ids
        assert "current_position" in section_ids
        assert "disclaimers" in section_ids

    @patch("advisory.report_generator.MultiYearProjectionEngine")
    @patch("advisory.report_generator.EntityStructureOptimizer")
    @patch("advisory.report_generator.TaxRecommendationEngine")
    @patch("advisory.report_generator.TaxCalculator")
    def test_executive_summary_content(
        self, MockCalc, MockRec, MockEntity, MockProjection
    ):
        """Executive summary section should contain tax position data."""
        from advisory.report_generator import AdvisoryReportGenerator

        tax_return = _build_w2_filer(85_000)
        calc_result = _make_calc_result(tax_return)

        mock_calc = MagicMock()
        mock_calc.calculate_complete_return.return_value = calc_result
        MockCalc.return_value = mock_calc

        mock_rec = MagicMock()
        mock_rec_result = MagicMock()
        mock_rec_result.total_potential_savings = 0
        mock_rec_result.overall_confidence = 70
        mock_rec_result.top_opportunities = []
        mock_rec_result.all_opportunities = []
        mock_rec.analyze.return_value = mock_rec_result
        MockRec.return_value = mock_rec

        mock_projection = MagicMock()
        mock_projection.project_multi_year.side_effect = Exception("skip")
        MockProjection.return_value = mock_projection

        generator = AdvisoryReportGenerator(
            tax_calculator=mock_calc,
            recommendation_engine=mock_rec,
            projection_engine=mock_projection,
        )

        report = generator.generate_report(tax_return, include_multi_year=False)

        exec_section = next(
            (s for s in report.sections if s.section_id == "executive_summary"), None
        )
        assert exec_section is not None
        content = exec_section.content
        assert content["tax_year"] == 2025
        assert content["filing_status"] == "single"
        assert "current_liability" in content
        assert content["current_liability"]["federal"] == float(tax_return.tax_liability)


# ---------------------------------------------------------------------------
# Tests: Self-Employed Pipeline (entity comparison)
# ---------------------------------------------------------------------------

class TestSelfEmployedPipeline:
    """End-to-end pipeline for self-employed taxpayer."""

    @patch("advisory.report_generator.MultiYearProjectionEngine")
    @patch("advisory.report_generator.EntityStructureOptimizer")
    @patch("advisory.report_generator.TaxRecommendationEngine")
    @patch("advisory.report_generator.TaxCalculator")
    def test_self_employed_report(
        self, MockCalc, MockRec, MockEntity, MockProjection
    ):
        """Self-employed report should include entity comparison when requested."""
        from advisory.report_generator import AdvisoryReportGenerator

        tax_return = _build_self_employed(150_000, 30_000)
        calc_result = _make_calc_result(tax_return)

        mock_calc = MagicMock()
        mock_calc.calculate_complete_return.return_value = calc_result
        MockCalc.return_value = mock_calc

        # Mock recommendation engine
        mock_rec = MagicMock()
        mock_rec_result = MagicMock()
        mock_rec_result.total_potential_savings = 12_000.0
        mock_rec_result.overall_confidence = 80.0
        mock_rec_result.top_opportunities = []
        mock_rec_result.all_opportunities = []
        mock_rec.analyze.return_value = mock_rec_result
        MockRec.return_value = mock_rec

        # Mock entity optimizer
        mock_entity = MagicMock()
        mock_entity_result = MagicMock()
        mock_entity_result.recommended_entity = MagicMock()
        mock_entity_result.recommended_entity.value = "s_corporation"
        mock_entity_result.max_annual_savings = 8000
        sole_prop = MagicMock()
        sole_prop.total_business_tax = 25000
        sole_prop.self_employment_tax = 16000
        s_corp = MagicMock()
        s_corp.total_business_tax = 17000
        s_corp.self_employment_tax = 0
        mock_entity_result.analyses = {
            "sole_proprietorship": sole_prop,
            "s_corporation": s_corp,
        }
        mock_entity.compare_structures.return_value = mock_entity_result
        MockEntity.return_value = mock_entity

        # Mock projection
        mock_projection = MagicMock()
        mock_projection.project_multi_year.side_effect = Exception("skip")
        MockProjection.return_value = mock_projection

        generator = AdvisoryReportGenerator(
            tax_calculator=mock_calc,
            recommendation_engine=mock_rec,
            entity_optimizer=mock_entity,
            projection_engine=mock_projection,
        )

        report = generator.generate_report(
            tax_return,
            include_entity_comparison=True,
            include_multi_year=False,
        )

        assert report.status == "complete"
        assert report.taxpayer_name == "Bob Freelance"
        assert float(report.potential_savings) == 12_000.0

        section_ids = [s.section_id for s in report.sections]
        assert "executive_summary" in section_ids
        assert "entity_comparison" in section_ids

        # Check entity comparison content
        entity_section = next(s for s in report.sections if s.section_id == "entity_comparison")
        entity_content = entity_section.content
        assert "entity_comparison" in entity_content
        assert "sole_proprietor" in entity_content["entity_comparison"]
        assert "s_corp" in entity_content["entity_comparison"]

    @patch("advisory.report_generator.MultiYearProjectionEngine")
    @patch("advisory.report_generator.EntityStructureOptimizer")
    @patch("advisory.report_generator.TaxRecommendationEngine")
    @patch("advisory.report_generator.TaxCalculator")
    def test_error_report_on_failure(
        self, MockCalc, MockRec, MockEntity, MockProjection
    ):
        """If an exception occurs during report generation, an error report is returned."""
        from advisory.report_generator import AdvisoryReportGenerator

        tax_return = _build_w2_filer()

        mock_calc = MagicMock()
        mock_calc.calculate_complete_return.side_effect = Exception("Calculator exploded")
        MockCalc.return_value = mock_calc

        generator = AdvisoryReportGenerator(tax_calculator=mock_calc)

        report = generator.generate_report(tax_return)

        assert report.status == "error"
        assert "Calculator exploded" in report.error_message
        assert report.sections == []


# ---------------------------------------------------------------------------
# Tests: Report to_dict and serialization
# ---------------------------------------------------------------------------

class TestReportSerialization:
    """Test that generated reports serialize properly."""

    @patch("advisory.report_generator.MultiYearProjectionEngine")
    @patch("advisory.report_generator.EntityStructureOptimizer")
    @patch("advisory.report_generator.TaxRecommendationEngine")
    @patch("advisory.report_generator.TaxCalculator")
    def test_to_dict_round_trip(
        self, MockCalc, MockRec, MockEntity, MockProjection
    ):
        """Report to_dict should produce a JSON-serializable dict."""
        import json
        from advisory.report_generator import AdvisoryReportGenerator

        tax_return = _build_w2_filer()
        calc_result = _make_calc_result(tax_return)

        mock_calc = MagicMock()
        mock_calc.calculate_complete_return.return_value = calc_result

        mock_rec = MagicMock()
        mock_rec_result = MagicMock()
        mock_rec_result.total_potential_savings = 0
        mock_rec_result.overall_confidence = 50
        mock_rec_result.top_opportunities = []
        mock_rec_result.all_opportunities = []
        mock_rec.analyze.return_value = mock_rec_result

        mock_projection = MagicMock()
        mock_projection.project_multi_year.side_effect = Exception("skip")

        generator = AdvisoryReportGenerator(
            tax_calculator=mock_calc,
            recommendation_engine=mock_rec,
            projection_engine=mock_projection,
        )

        report = generator.generate_report(tax_return, include_multi_year=False)
        d = report.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["report_type"] == "standard_report"


# ---------------------------------------------------------------------------
# Tests: Optional PDF export step
# ---------------------------------------------------------------------------

class TestPipelinePDFExport:
    """Test that pipeline output can be exported to PDF."""

    @patch("advisory.report_generator.MultiYearProjectionEngine")
    @patch("advisory.report_generator.EntityStructureOptimizer")
    @patch("advisory.report_generator.TaxRecommendationEngine")
    @patch("advisory.report_generator.TaxCalculator")
    def test_pipeline_to_pdf(
        self, MockCalc, MockRec, MockEntity, MockProjection
    ):
        """Generated report should be exportable to PDF."""
        from advisory.report_generator import AdvisoryReportGenerator
        from export.advisory_pdf_exporter import export_advisory_report_to_pdf

        tax_return = _build_w2_filer()
        calc_result = _make_calc_result(tax_return)

        mock_calc = MagicMock()
        mock_calc.calculate_complete_return.return_value = calc_result

        mock_rec = MagicMock()
        mock_rec_result = MagicMock()
        mock_rec_result.total_potential_savings = 3000
        mock_rec_result.overall_confidence = 75
        mock_rec_result.top_opportunities = []
        mock_rec_result.all_opportunities = []
        mock_rec.analyze.return_value = mock_rec_result

        mock_projection = MagicMock()
        mock_projection.project_multi_year.side_effect = Exception("skip")

        generator = AdvisoryReportGenerator(
            tax_calculator=mock_calc,
            recommendation_engine=mock_rec,
            projection_engine=mock_projection,
        )

        report = generator.generate_report(tax_return, include_multi_year=False)
        assert report.status == "complete"

        # Export to PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name

        try:
            result_path = export_advisory_report_to_pdf(
                report=report,
                output_path=pdf_path,
                watermark="TEST",
                include_charts=False,
                include_toc=False,
            )
            assert os.path.exists(result_path)
            assert os.path.getsize(result_path) > 0
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)
