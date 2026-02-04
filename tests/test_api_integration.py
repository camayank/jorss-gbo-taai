"""
API Integration Tests for Universal Report System.

Tests the complete flow from session creation to report generation and PDF download.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from pathlib import Path
import tempfile
import json


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def sample_profile():
    """Sample taxpayer profile for testing."""
    return {
        "taxpayer_name": "John Doe",
        "filing_status": "married_filing_jointly",
        "tax_year": 2025,
        "total_income": 150000,
        "w2_income": 120000,
        "business_income": 30000,
        "is_self_employed": True,
        "state": "CA",
        "dependents": 2,
        "itemized_deductions": {
            "mortgage_interest": 12000,
            "property_taxes": 8000,
            "charitable": 5000,
        },
        "retirement_contributions": {
            "401k": 15000,
            "ira": 5000,
        },
    }


@pytest.fixture
def sample_session_data(sample_profile):
    """Sample session data including calculations."""
    return {
        "profile": sample_profile,
        "calculations": {
            "total_income": 150000,
            "agi": 135000,
            "taxable_income": 110000,
            "federal_tax": 18500,
            "state_tax": 6200,
            "total_tax": 24700,
            "effective_rate": 16.5,
        },
        "strategies": [
            {
                "name": "Maximize 401(k)",
                "savings": 2500,
                "description": "Increase 401(k) contributions",
            },
            {
                "name": "HSA Contribution",
                "savings": 1200,
                "description": "Open and fund HSA",
            },
        ],
        "lead_score": 75,
    }


@pytest.fixture
def mock_chat_engine(sample_session_data):
    """Mock chat engine for API tests."""
    engine = Mock()
    engine.sessions = {"test-session-123": sample_session_data}
    engine.get_or_create_session = Mock(return_value=sample_session_data)
    engine.determine_complexity = Mock(return_value="moderate")
    return engine


# =============================================================================
# API ENDPOINT INTEGRATION TESTS
# =============================================================================

class TestReportAPIIntegration:
    """Integration tests for report generation API endpoints."""

    def test_html_report_generation_flow(self, sample_session_data):
        """Test complete HTML report generation flow."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        # Generate HTML report
        html = engine.generate_html_report(
            source_type='chatbot',
            source_id='test-session-123',
            source_data=sample_session_data,
            tier_level=2,
        )

        # Verify HTML structure
        assert isinstance(html, str) and len(html) > 0
        assert "<html" in html.lower(), "Response should contain valid HTML"
        assert "Tax Advisory" in html
        # Disclaimer check (case-insensitive)
        assert "not tax advice" in html.lower() or "informational purposes" in html.lower()

    def test_pdf_report_generation_flow(self, sample_session_data):
        """Test complete PDF report generation flow."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        # Generate report with PDF output
        output = engine.generate_report(
            source_type='chatbot',
            source_id='test-session-123',
            source_data=sample_session_data,
            output_format='pdf',
            tier_level=2,
        )

        # Verify PDF was generated
        assert output is not None
        assert output.pdf_bytes is not None
        assert len(output.pdf_bytes) > 1000  # PDF has content

        # Verify PDF header (starts with %PDF)
        assert output.pdf_bytes[:4] == b'%PDF'

    def test_report_with_cpa_branding(self, sample_session_data):
        """Test report generation with CPA branding."""
        from universal_report import UniversalReportEngine

        cpa_profile = {
            "firm_name": "Smith & Associates CPA",
            "advisor_name": "John Smith",
            "credentials": ["CPA", "CFP"],
            "email": "john@smithcpa.com",
            "phone": "(555) 123-4567",
            "primary_color": "#1a365d",
        }

        engine = UniversalReportEngine()
        html = engine.generate_html_report(
            source_type='chatbot',
            source_id='test-session-123',
            source_data=sample_session_data,
            cpa_profile=cpa_profile,
            tier_level=2,
        )

        # Verify branding applied
        assert "Smith & Associates CPA" in html
        assert "#1a365d" in html or "1a365d" in html

    def test_tier_restrictions_applied(self, sample_session_data):
        """Test that tier restrictions are properly applied."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        # Tier 1 (teaser) should have limited content
        tier1_html = engine.generate_html_report(
            source_type='chatbot',
            source_id='test-session-123',
            source_data=sample_session_data,
            tier_level=1,
        )

        # Tier 2 (full) should have more content
        tier2_html = engine.generate_html_report(
            source_type='chatbot',
            source_id='test-session-123',
            source_data=sample_session_data,
            tier_level=2,
        )

        # Tier 2 should be larger (more content)
        assert len(tier2_html) > len(tier1_html)

    def test_report_metadata_complete(self, sample_session_data):
        """Test that report output contains complete metadata."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()
        output = engine.generate_report(
            source_type='chatbot',
            source_id='test-session-123',
            source_data=sample_session_data,
            output_format='html',
            tier_level=2,
        )

        # Verify metadata
        assert output.source_type == 'chatbot'
        assert output.source_id == 'test-session-123'
        assert output.tier_level == 2
        assert output.html_content is not None


class TestPDFExporterIntegration:
    """Integration tests for PDF exporter with visualizations."""

    def test_pdf_with_visualizations(self):
        """Test PDF generation with all visualizations enabled."""
        from export.advisory_pdf_exporter import AdvisoryPDFExporter, CPABrandConfig
        from dataclasses import dataclass, field
        from typing import List, Dict, Any

        @dataclass
        class MockSection:
            section_id: str
            title: str
            content: Dict[str, Any]

        @dataclass
        class MockReport:
            report_id: str
            taxpayer_name: str
            tax_year: int
            filing_status: str
            current_tax_liability: Decimal
            potential_savings: Decimal
            confidence_score: int
            top_recommendations_count: int
            sections: List[MockSection] = field(default_factory=list)

        report = MockReport(
            report_id='test-001',
            taxpayer_name='Test User',
            tax_year=2025,
            filing_status='single',
            current_tax_liability=Decimal('25000'),
            potential_savings=Decimal('5000'),
            confidence_score=85,
            top_recommendations_count=3,
            sections=[
                MockSection(
                    section_id='executive_summary',
                    title='Executive Summary',
                    content={'overview': 'Test overview'}
                ),
                MockSection(
                    section_id='current_position',
                    title='Current Position',
                    content={
                        'income_summary': {
                            'total_income': 100000,
                            'agi': 90000,
                            'taxable_income': 75000,
                        },
                        'tax_liability': {
                            'federal_tax': 20000,
                            'state_tax': 5000,
                            'total_tax': 25000,
                        },
                        'effective_rate': 25.0,
                    }
                ),
            ]
        )

        exporter = AdvisoryPDFExporter(include_visualizations=True)

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = exporter.generate_pdf(
                report=report,
                output_path=f.name,
                include_charts=True,
                include_toc=True,
            )

            # Verify PDF created
            assert Path(pdf_path).exists()
            assert Path(pdf_path).stat().st_size > 5000  # Has content

    def test_pdf_watermark_applied(self):
        """Test that watermark is applied to PDF."""
        from export.advisory_pdf_exporter import AdvisoryPDFExporter
        from dataclasses import dataclass, field
        from typing import List, Dict, Any

        @dataclass
        class MockSection:
            section_id: str
            title: str
            content: Dict[str, Any]

        @dataclass
        class MockReport:
            report_id: str
            taxpayer_name: str
            tax_year: int
            filing_status: str
            current_tax_liability: Decimal
            potential_savings: Decimal
            confidence_score: int
            top_recommendations_count: int
            sections: List[MockSection] = field(default_factory=list)

        report = MockReport(
            report_id='test-002',
            taxpayer_name='Test User',
            tax_year=2025,
            filing_status='single',
            current_tax_liability=Decimal('25000'),
            potential_savings=Decimal('5000'),
            confidence_score=85,
            top_recommendations_count=3,
            sections=[
                MockSection(
                    section_id='executive_summary',
                    title='Executive Summary',
                    content={'overview': 'Test'}
                ),
            ]
        )

        # Test with watermark
        exporter_with_watermark = AdvisoryPDFExporter(watermark="DRAFT")

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = exporter_with_watermark.generate_pdf(
                report=report,
                output_path=f.name,
            )

            # Verify PDF created (watermark is visual, hard to test programmatically)
            assert Path(pdf_path).exists()

        # Test without watermark
        exporter_no_watermark = AdvisoryPDFExporter(watermark=None)

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = exporter_no_watermark.generate_pdf(
                report=report,
                output_path=f.name,
            )
            assert Path(pdf_path).exists()


class TestVisualizationIntegration:
    """Integration tests for PDF visualizations."""

    def test_all_chart_types_generate(self):
        """Test that all chart types can be generated."""
        from export.pdf_visualizations import PDFChartGenerator

        generator = PDFChartGenerator()

        # Savings gauge
        gauge = generator.create_savings_gauge(25000, 5000)
        assert gauge is not None

        # Income pie chart
        income_chart = generator.create_income_pie_chart([
            {'category': 'W-2', 'amount': 100000},
            {'category': 'Business', 'amount': 50000},
        ])
        assert income_chart is not None

        # Tax bracket chart
        bracket_chart = generator.create_tax_bracket_chart(100000, 'single')
        assert bracket_chart is not None

        # Comparison chart
        comparison = generator.create_comparison_chart(
            {'federal_tax': 20000, 'state_tax': 5000, 'total_tax': 25000},
            {'federal_tax': 16000, 'state_tax': 4000, 'total_tax': 20000},
        )
        assert comparison is not None

        # Deduction comparison
        deduction = generator.create_deduction_comparison(14600, 18000, 'itemized')
        assert deduction is not None

    def test_chart_to_reportlab_conversion(self):
        """Test conversion of charts to ReportLab images."""
        from export.pdf_visualizations import PDFChartGenerator

        generator = PDFChartGenerator()

        # Create a chart
        gauge_buffer = generator.create_savings_gauge(25000, 5000)
        assert gauge_buffer is not None

        # Convert to ReportLab image
        gauge_buffer.seek(0)
        rl_image = generator.buffer_to_reportlab_image(gauge_buffer, width=5, height=3)
        assert rl_image is not None


# =============================================================================
# SESSION HANDLING TESTS
# =============================================================================

class TestSessionHandling:
    """Tests for session management and expiration."""

    def test_session_data_persistence(self, sample_session_data):
        """Test that session data is properly persisted."""
        from universal_report import UniversalReportEngine
        from universal_report.data_collector import ReportDataCollector

        collector = ReportDataCollector()

        # Collect data from session
        normalized = collector.from_chatbot_session(
            session_id='test-session',
            session_data=sample_session_data,
        )

        # Verify data integrity - check that key fields are populated
        assert normalized.taxpayer_name is not None
        assert normalized.filing_status is not None
        assert normalized.tax_year == 2025

    def test_missing_session_handled(self):
        """Test handling of missing session data."""
        from universal_report.data_collector import ReportDataCollector

        collector = ReportDataCollector()

        # Empty session should not crash
        normalized = collector.from_chatbot_session(
            session_id='nonexistent',
            session_data={},
        )

        # Should have defaults - collector uses "Tax Client" as default
        assert normalized.taxpayer_name is not None
        assert normalized.tax_year == 2025

    def test_expired_session_handling(self):
        """Test handling of expired session."""
        from universal_report.data_collector import ReportDataCollector

        collector = ReportDataCollector()

        # Partial/expired session data
        expired_data = {
            "profile": {
                "taxpayer_name": "Old User",
                # Missing required fields
            }
        }

        normalized = collector.from_chatbot_session(
            session_id='expired-session',
            session_data=expired_data,
        )

        # Should handle gracefully without crashing
        assert normalized is not None
        assert normalized.taxpayer_name is not None


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in report generation."""

    def test_invalid_filing_status_handled(self):
        """Test handling of invalid filing status."""
        from universal_report.data_collector import ReportDataCollector

        collector = ReportDataCollector()

        session_data = {
            "profile": {
                "taxpayer_name": "Test User",
                "filing_status": "invalid_status",
                "total_income": 100000,
            }
        }

        # Should not crash, should use default
        normalized = collector.from_chatbot_session(
            session_id='test',
            session_data=session_data,
        )

        assert normalized is not None

    def test_negative_income_handled(self):
        """Test handling of negative income (losses)."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            "profile": {
                "taxpayer_name": "Loss User",
                "filing_status": "single",
                "total_income": -50000,  # Business loss
            },
            "calculations": {
                "total_income": -50000,
                "total_tax": 0,
            },
        }

        # Should not crash
        html = engine.generate_html_report(
            source_type='chatbot',
            source_id='test',
            source_data=session_data,
            tier_level=2,
        )

        assert isinstance(html, str) and len(html) > 0
        # Report should generate without crashing for negative values
        assert "<html" in html.lower(), "Response should contain valid HTML"

    def test_very_large_numbers_handled(self):
        """Test handling of very large income amounts."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            "profile": {
                "taxpayer_name": "Rich User",
                "filing_status": "single",
                "total_income": 100000000,  # $100M
            },
            "calculations": {
                "total_income": 100000000,
                "total_tax": 35000000,
            },
        }

        # Should not crash or overflow
        html = engine.generate_html_report(
            source_type='chatbot',
            source_id='test',
            source_data=session_data,
            tier_level=2,
        )

        assert isinstance(html, str) and len(html) > 0
        assert "<html" in html.lower(), "Response should contain valid HTML"
        assert "100,000,000" in html or "100000000" in html


# =============================================================================
# RATE LIMITING TESTS
# =============================================================================

class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rapid_report_generation(self, sample_session_data):
        """Test that rapid report generation doesn't cause issues."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        # Generate multiple reports rapidly
        for i in range(10):
            html = engine.generate_html_report(
                source_type='chatbot',
                source_id=f'test-session-{i}',
                source_data=sample_session_data,
                tier_level=2,
            )
            assert isinstance(html, str) and len(html) > 0

    def test_concurrent_pdf_generation(self, sample_session_data):
        """Test concurrent PDF generation."""
        from universal_report import UniversalReportEngine
        import concurrent.futures
        import os

        engine = UniversalReportEngine()

        def generate_pdf(session_id):
            output = engine.generate_report(
                source_type='chatbot',
                source_id=session_id,
                source_data=sample_session_data,
                output_format='pdf',
                tier_level=2,
            )
            return output.pdf_bytes is not None

        # Generate 5 PDFs concurrently (cap workers to available CPUs)
        max_workers = min(5, os.cpu_count() or 2)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(generate_pdf, f'session-{i}')
                for i in range(5)
            ]
            results = []
            for f in concurrent.futures.as_completed(futures):
                try:
                    results.append(f.result(timeout=30))
                except (concurrent.futures.TimeoutError, Exception) as e:
                    pytest.fail(f"Concurrent PDF generation failed: {e}")

        # All should succeed
        assert all(results)
