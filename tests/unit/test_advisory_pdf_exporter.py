"""Tests for AdvisoryPDFExporter (src/export/advisory_pdf_exporter.py).

Covers:
- PDF generation with a valid AdvisoryReportResult
- Generation with empty sections
- CPA branding configuration
- Convenience function export_advisory_report_to_pdf
- Actual PDF output to a temp file (validates file is created and non-empty)
"""

import os
import tempfile
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from advisory.report_generator import (
    AdvisoryReportResult,
    AdvisoryReportSection,
    ReportType,
)
from export.advisory_pdf_exporter import (
    AdvisoryPDFExporter,
    CPABrandConfig,
    export_advisory_report_to_pdf,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_section(section_id: str, title: str, content: dict) -> AdvisoryReportSection:
    """Create a minimal AdvisoryReportSection."""
    return AdvisoryReportSection(
        section_id=section_id,
        title=title,
        content=content,
        page_number=1,
    )


def _make_report(
    sections=None,
    taxpayer_name: str = "Jane Doe",
    filing_status: str = "single",
    tax_year: int = 2025,
    current_tax: float = 15000,
    savings: float = 3000,
    confidence: float = 82,
) -> AdvisoryReportResult:
    """Build a minimal AdvisoryReportResult for testing."""
    if sections is None:
        sections = [
            _make_section("executive_summary", "Executive Summary", {
                "overview": f"Tax advisory report for {taxpayer_name}",
                "tax_year": tax_year,
                "filing_status": filing_status,
                "current_liability": {
                    "federal": current_tax,
                    "state": 2000.0,
                    "total": current_tax + 2000.0,
                },
                "agi": 100_000.0,
                "taxable_income": 85_000.0,
            }),
            _make_section("current_position", "Current Tax Position", {
                "income_summary": {
                    "total_income": 100_000.0,
                    "agi": 100_000.0,
                    "taxable_income": 85_000.0,
                },
                "deductions": {
                    "standard_or_itemized": "standard",
                    "total_deductions": 15_000.0,
                },
                "tax_liability": {
                    "federal_tax": current_tax,
                    "state_tax": 2000.0,
                    "total_tax": current_tax + 2000.0,
                },
                "effective_rate": 17.0,
            }),
            _make_section("recommendations", "Tax Optimization Recommendations", {
                "total_opportunities": 3,
                "total_potential_savings": savings,
                "confidence": confidence,
                "top_recommendations": [
                    {
                        "category": "retirement",
                        "title": "Maximize 401(k)",
                        "savings": 2000.0,
                        "priority": "immediate",
                        "description": "Increase 401(k) contributions to the maximum.",
                        "action_required": "Contact HR to increase contribution.",
                        "confidence": 90.0,
                        "irs_reference": "IRC Section 401(k)",
                    },
                ],
            }),
            _make_section("action_plan", "Prioritized Action Plan", {
                "immediate_actions": [
                    {
                        "title": "Max 401(k)",
                        "action": "Increase contribution",
                        "savings": 2000.0,
                    },
                ],
                "current_year_actions": [],
                "next_year_planning": [],
                "long_term_strategies": [],
            }),
            _make_section("disclaimers", "Disclaimers & Methodology", {
                "disclaimers": [
                    "This report is for informational purposes only.",
                ],
                "circular_230": (
                    "Any tax advice contained in this communication was not intended "
                    "or written to be used for the purpose of avoiding penalties."
                ),
                "methodology": [
                    "Calculations use IRS Publication 17.",
                ],
            }),
        ]

    return AdvisoryReportResult(
        report_id="ADV_2025_TEST",
        report_type=ReportType.STANDARD_REPORT,
        tax_year=tax_year,
        generated_at="2025-06-15T10:00:00",
        taxpayer_name=taxpayer_name,
        filing_status=filing_status,
        sections=sections,
        current_tax_liability=Decimal(str(current_tax)),
        potential_savings=Decimal(str(savings)),
        confidence_score=Decimal(str(confidence)),
        top_recommendations_count=3,
        immediate_action_items=[
            {"title": "Max 401(k)", "savings": 2000.0, "action": "Increase contribution"},
        ],
    )


@pytest.fixture
def report():
    """Default report fixture."""
    return _make_report()


@pytest.fixture
def tmp_pdf_path():
    """Create a temporary file path for PDF output and clean up after."""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


# ---------------------------------------------------------------------------
# Tests: PDF generation with valid report
# ---------------------------------------------------------------------------

class TestPDFGeneration:
    """Test actual PDF file generation."""

    def test_generates_pdf_file(self, report, tmp_pdf_path):
        """generate_pdf should create a non-empty PDF file."""
        exporter = AdvisoryPDFExporter(
            include_visualizations=False,
        )
        result_path = exporter.generate_pdf(
            report, tmp_pdf_path, include_charts=False, include_toc=True
        )

        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0

    def test_pdf_starts_with_pdf_header(self, report, tmp_pdf_path):
        """Generated file should start with %PDF magic bytes."""
        exporter = AdvisoryPDFExporter(include_visualizations=False)
        exporter.generate_pdf(report, tmp_pdf_path, include_charts=False)

        with open(tmp_pdf_path, "rb") as f:
            header = f.read(5)

        assert header == b"%PDF-"

    def test_generates_pdf_without_toc(self, report, tmp_pdf_path):
        """PDF generation should work without table of contents."""
        exporter = AdvisoryPDFExporter(include_visualizations=False)
        result_path = exporter.generate_pdf(
            report, tmp_pdf_path, include_charts=False, include_toc=False
        )

        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0


# ---------------------------------------------------------------------------
# Tests: Empty sections
# ---------------------------------------------------------------------------

class TestEmptySections:
    """Test PDF generation with empty or minimal sections."""

    def test_empty_sections_list(self, tmp_pdf_path):
        """PDF should still generate with no sections."""
        report = _make_report(sections=[])
        exporter = AdvisoryPDFExporter(include_visualizations=False)

        result_path = exporter.generate_pdf(
            report, tmp_pdf_path, include_charts=False, include_toc=False
        )

        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0

    def test_only_disclaimers_section(self, tmp_pdf_path):
        """PDF should work with only a disclaimers section."""
        sections = [
            _make_section("disclaimers", "Disclaimers", {
                "disclaimers": ["Test disclaimer."],
                "methodology": [],
            }),
        ]
        report = _make_report(sections=sections)
        exporter = AdvisoryPDFExporter(include_visualizations=False)

        result_path = exporter.generate_pdf(
            report, tmp_pdf_path, include_charts=False
        )

        assert os.path.exists(result_path)


# ---------------------------------------------------------------------------
# Tests: CPA Branding
# ---------------------------------------------------------------------------

class TestCPABranding:
    """Test PDF generation with CPA brand configuration."""

    def test_branded_pdf_generates(self, report, tmp_pdf_path):
        """PDF should generate with full CPA branding."""
        brand = CPABrandConfig(
            firm_name="Smith & Associates CPA",
            firm_tagline="Your Trusted Tax Partner",
            advisor_name="John Smith",
            advisor_credentials=["CPA", "CFP"],
            contact_email="john@smithcpa.com",
            contact_phone="(555) 123-4567",
            contact_website="www.smithcpa.com",
            primary_color="#1e3a5f",
            accent_color="#10b981",
        )
        exporter = AdvisoryPDFExporter(
            brand_config=brand,
            include_visualizations=False,
        )

        result_path = exporter.generate_pdf(
            report, tmp_pdf_path, include_charts=False
        )

        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0

    def test_default_brand_config(self):
        """Default CPABrandConfig should have sensible defaults."""
        brand = CPABrandConfig()

        assert brand.firm_name == "Tax Advisory Services"
        assert brand.primary_color == "#2c5aa0"
        assert brand.show_footer_on_all_pages is True
        assert brand.logo_path is None

    def test_brand_color_conversion(self):
        """Hex colors should convert to ReportLab color objects."""
        brand = CPABrandConfig(
            primary_color="#ff0000",
            secondary_color="#00ff00",
            accent_color="#0000ff",
        )

        primary = brand.get_primary_color()
        secondary = brand.get_secondary_color()
        accent = brand.get_accent_color()

        # ReportLab HexColor objects should be returned
        assert primary is not None
        assert secondary is not None
        assert accent is not None

    def test_watermark_pdf(self, report, tmp_pdf_path):
        """PDF with watermark text should generate successfully."""
        exporter = AdvisoryPDFExporter(
            watermark="DRAFT",
            include_visualizations=False,
        )
        result_path = exporter.generate_pdf(
            report, tmp_pdf_path, include_charts=False
        )

        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0


# ---------------------------------------------------------------------------
# Tests: Convenience function
# ---------------------------------------------------------------------------

class TestConvenienceFunction:
    """Test the export_advisory_report_to_pdf convenience function."""

    def test_basic_export(self, report, tmp_pdf_path):
        """Convenience function should produce a valid PDF."""
        result_path = export_advisory_report_to_pdf(
            report=report,
            output_path=tmp_pdf_path,
            watermark="DRAFT",
            include_charts=False,
            include_toc=True,
        )

        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0

    def test_export_with_brand_config(self, report, tmp_pdf_path):
        """Convenience function should accept brand_config."""
        brand = CPABrandConfig(
            firm_name="Test Firm",
            advisor_name="Test Advisor",
        )
        result_path = export_advisory_report_to_pdf(
            report=report,
            output_path=tmp_pdf_path,
            watermark=None,
            include_charts=False,
            brand_config=brand,
        )

        assert os.path.exists(result_path)

    def test_export_creates_parent_directory(self, report):
        """Convenience function should create parent dirs if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = os.path.join(tmpdir, "subdir", "report.pdf")
            result_path = export_advisory_report_to_pdf(
                report=report,
                output_path=nested_path,
                include_charts=False,
                include_toc=False,
            )

            assert os.path.exists(result_path)


# ---------------------------------------------------------------------------
# Tests: AdvisoryReportResult model
# ---------------------------------------------------------------------------

class TestAdvisoryReportResult:
    """Test the AdvisoryReportResult model itself."""

    def test_to_dict(self, report):
        """to_dict should serialize all key fields."""
        d = report.to_dict()

        assert d["report_id"] == "ADV_2025_TEST"
        assert d["report_type"] == "standard_report"
        assert d["taxpayer_name"] == "Jane Doe"
        assert d["metrics"]["current_tax_liability"] == 15000.0
        assert d["metrics"]["potential_savings"] == 3000.0
        assert d["status"] == "complete"
        assert isinstance(d["sections"], list)

    def test_sections_serialization(self, report):
        """Sections should serialize with required fields."""
        d = report.to_dict()

        for section in d["sections"]:
            assert "section_id" in section
            assert "title" in section
            assert "content" in section
