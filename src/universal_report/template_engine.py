"""
Universal Report Template Engine - Main orchestrator for report generation.

This is the central entry point for generating reports from any data source.
It handles:
- Data collection and normalization
- Theme/branding application
- Section rendering
- Export to multiple formats
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime
import logging
import uuid
import html

from universal_report.data_collector import (
    NormalizedReportData,
    ReportDataCollector,
    SourceType,
)
from universal_report.section_renderer import SectionRenderer, RenderedSection
from universal_report.branding.theme_manager import BrandTheme, ThemeManager
from universal_report.branding.logo_handler import LogoHandler

logger = logging.getLogger(__name__)


@dataclass
class ReportOutput:
    """
    Output container for generated reports.

    Contains the rendered report in various formats along with metadata.
    """
    report_id: str
    source_type: str
    source_id: Optional[str]
    generated_at: datetime = field(default_factory=datetime.now)

    # Output content
    html_content: Optional[str] = None
    pdf_bytes: Optional[bytes] = None

    # Metadata
    taxpayer_name: str = ""
    tax_year: int = 2025
    total_sections: int = 0
    tier_level: int = 2

    # Metrics for display
    potential_savings: float = 0.0
    recommendation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "report_id": self.report_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "generated_at": self.generated_at.isoformat(),
            "taxpayer_name": self.taxpayer_name,
            "tax_year": self.tax_year,
            "total_sections": self.total_sections,
            "tier_level": self.tier_level,
            "potential_savings": self.potential_savings,
            "recommendation_count": self.recommendation_count,
            "has_html": self.html_content is not None,
            "has_pdf": self.pdf_bytes is not None,
        }


class UniversalReportEngine:
    """
    Main orchestrator for universal report generation.

    This class coordinates:
    1. Data collection from various sources
    2. Branding/theme application
    3. Section rendering
    4. Export to multiple formats

    Usage:
        engine = UniversalReportEngine()
        output = engine.generate_report(
            source_type='chatbot',
            source_id='session_123',
            source_data=session_data,
            cpa_profile={'firm_name': 'Acme Tax', 'primary_color': '#1e40af'},
            output_format='html',
        )
    """

    def __init__(self):
        self.collector = ReportDataCollector()
        self.theme_manager = ThemeManager()

    def generate_report(
        self,
        source_type: str,
        source_id: Optional[str] = None,
        source_data: Optional[Dict[str, Any]] = None,
        cpa_profile: Optional[Dict[str, Any]] = None,
        output_format: str = 'html',
        tier_level: int = 2,
    ) -> ReportOutput:
        """
        Generate a report from any data source.

        Args:
            source_type: Type of data source ('chatbot', 'advisory', 'lead_magnet', 'manual', 'ocr')
            source_id: Session ID or identifier for the data
            source_data: Raw data from the source (required for most sources)
            cpa_profile: Optional CPA branding configuration
            output_format: Output format ('html', 'pdf', 'both')
            tier_level: Report detail level (1=teaser, 2=full, 3=complete)

        Returns:
            ReportOutput with generated report content
        """
        report_id = self._generate_report_id()
        logger.info(f"Generating report {report_id} from {source_type}")

        try:
            # 1. Collect and normalize data
            data = self._collect_data(source_type, source_id, source_data)
            data.report_id = report_id

            # 2. Apply branding
            theme = self.theme_manager.from_cpa_profile(cpa_profile)

            # 3. Render sections
            renderer = SectionRenderer(data, theme)
            sections = renderer.render_all(tier_level)

            # 4. Apply tier restrictions (blur/hide sections for teasers)
            sections = self._apply_tier_restrictions(sections, tier_level)

            # 5. Export to requested format
            html_content = None
            pdf_bytes = None

            if output_format in ('html', 'both'):
                html_content = self._export_html(sections, data, theme)

            if output_format in ('pdf', 'both'):
                pdf_bytes = self._export_pdf(sections, data, theme)

            return ReportOutput(
                report_id=report_id,
                source_type=source_type,
                source_id=source_id,
                html_content=html_content,
                pdf_bytes=pdf_bytes,
                taxpayer_name=data.taxpayer_name,
                tax_year=data.tax_year,
                total_sections=len(sections),
                tier_level=tier_level,
                potential_savings=float(data.potential_savings_high or 0),
                recommendation_count=len(data.recommendations),
            )

        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
            raise ReportGenerationError(f"Failed to generate report: {str(e)}") from e

    def generate_html_report(
        self,
        source_type: str,
        source_id: Optional[str] = None,
        source_data: Optional[Dict[str, Any]] = None,
        cpa_profile: Optional[Dict[str, Any]] = None,
        tier_level: int = 2,
    ) -> str:
        """
        Generate HTML report only.

        Convenience method that returns just the HTML string.
        """
        output = self.generate_report(
            source_type=source_type,
            source_id=source_id,
            source_data=source_data,
            cpa_profile=cpa_profile,
            output_format='html',
            tier_level=tier_level,
        )
        return output.html_content or ""

    def generate_pdf_report(
        self,
        source_type: str,
        source_id: Optional[str] = None,
        source_data: Optional[Dict[str, Any]] = None,
        cpa_profile: Optional[Dict[str, Any]] = None,
        tier_level: int = 2,
    ) -> bytes:
        """
        Generate PDF report only.

        Convenience method that returns just the PDF bytes.
        """
        output = self.generate_report(
            source_type=source_type,
            source_id=source_id,
            source_data=source_data,
            cpa_profile=cpa_profile,
            output_format='pdf',
            tier_level=tier_level,
        )
        return output.pdf_bytes or b""

    def _generate_report_id(self) -> str:
        """Generate unique report ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"RPT_{timestamp}_{unique_id}"

    def _collect_data(
        self,
        source_type: str,
        source_id: Optional[str],
        source_data: Optional[Dict[str, Any]],
    ) -> NormalizedReportData:
        """
        Collect and normalize data from the specified source.

        Args:
            source_type: Type of data source
            source_id: Session/identifier
            source_data: Raw source data

        Returns:
            NormalizedReportData ready for rendering
        """
        if source_data is None:
            source_data = {}

        if source_type == 'chatbot':
            return self.collector.from_chatbot_session(
                session_id=source_id or "",
                session_data=source_data,
            )
        elif source_type == 'advisory':
            return self.collector.from_advisory_analysis(source_data)
        elif source_type == 'lead_magnet':
            return self.collector.from_lead_magnet_session(
                session_id=source_id or "",
                session_data=source_data,
            )
        elif source_type == 'manual':
            return self.collector.from_manual_entry(source_data)
        elif source_type == 'ocr':
            return self.collector.from_ocr_extraction(source_data)
        else:
            logger.warning(f"Unknown source type: {source_type}, using manual")
            return self.collector.from_manual_entry(source_data)

    def _apply_tier_restrictions(
        self,
        sections: List[RenderedSection],
        tier_level: int,
    ) -> List[RenderedSection]:
        """
        Apply tier-based restrictions to sections.

        Tier 1 (teaser): Only show summary, blur/hide details
        Tier 2 (full): Show most sections
        Tier 3 (complete): Show everything

        Args:
            sections: List of rendered sections
            tier_level: Restriction level

        Returns:
            Filtered/modified sections list
        """
        if tier_level >= 3:
            return sections  # No restrictions

        # Define which sections are available at each tier
        tier_sections = {
            1: {'cover_page', 'executive_summary', 'savings_gauge', 'disclaimers'},
            2: {'cover_page', 'executive_summary', 'savings_gauge', 'tax_summary',
                'income_analysis', 'deductions_analysis', 'tax_brackets',
                'recommendations', 'action_items', 'tax_education',
                'risk_assessment', 'tax_timeline', 'document_checklist', 'disclaimers'},
        }

        allowed = tier_sections.get(tier_level, tier_sections[2])

        filtered = []
        for section in sections:
            if section.section_id in allowed:
                filtered.append(section)
            elif tier_level == 1 and section.section_id == 'recommendations':
                # For teaser, add blurred recommendations preview
                blurred = RenderedSection(
                    section_id=section.section_id,
                    title=section.title,
                    content=self._blur_section(section.content),
                    order=section.order,
                )
                filtered.append(blurred)

        return filtered

    def _blur_section(self, content: str) -> str:
        """Add blur overlay to section for teaser mode."""
        return f'''
<div class="blurred-section" style="position: relative;">
  <div style="filter: blur(8px); pointer-events: none;">
    {content}
  </div>
  <div style="
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: white;
    padding: 20px 40px;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
  ">
    <div style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">
      Upgrade to View Full Report
    </div>
    <div style="font-size: 14px; opacity: 0.9;">
      Get access to all recommendations and detailed analysis
    </div>
  </div>
</div>
'''

    def _export_html(
        self,
        sections: List[RenderedSection],
        data: NormalizedReportData,
        theme: BrandTheme,
    ) -> str:
        """
        Export sections to complete HTML document.

        Args:
            sections: Rendered sections
            data: Normalized report data
            theme: Brand theme

        Returns:
            Complete HTML document string
        """
        # Generate CSS
        css = self.theme_manager.generate_full_css(theme)

        # Build sections HTML
        sections_html = ""
        for section in sorted(sections, key=lambda s: s.order):
            page_break_before = 'page-break-before: always;' if section.page_break_before else ''
            page_break_after = 'page-break-after: always;' if section.page_break_after else ''

            sections_html += f'''
<div class="report-section" id="{section.section_id}" style="{page_break_before} {page_break_after}">
  {section.content}
</div>
'''

        # Footer
        logo_handler = LogoHandler(theme)
        footer_html = logo_handler.render_footer_with_logo()

        # Watermark
        watermark_html = ""
        if theme.show_watermark and theme.watermark_text:
            watermark_html = logo_handler.render_watermark(text=theme.watermark_text)

        # Build complete document
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(theme.report_title)} - {html.escape(data.taxpayer_name)}</title>
  <style>
{css}

/* Report-specific styles */
.report-container {{
  max-width: 900px;
  margin: 0 auto;
  padding: 40px;
  background: white;
}}

.report-section {{
  margin-bottom: 40px;
}}

@media print {{
  .report-container {{
    max-width: 100%;
    padding: 20px;
  }}

  .no-print {{
    display: none !important;
  }}
}}
  </style>
</head>
<body>
  {watermark_html}
  <div class="report-container">
    {sections_html}
    {footer_html}
  </div>
</body>
</html>
'''

    def _export_pdf(
        self,
        sections: List[RenderedSection],
        data: NormalizedReportData,
        theme: BrandTheme,
    ) -> bytes:
        """
        Export sections to PDF.

        Uses the HTML exporter and then converts to PDF.
        Falls back to HTML if PDF generation fails.

        Args:
            sections: Rendered sections
            data: Normalized report data
            theme: Brand theme

        Returns:
            PDF bytes
        """
        # First generate HTML
        html_content = self._export_html(sections, data, theme)

        # Try to use PDF exporter
        try:
            from universal_report.exporters.pdf_exporter import PDFExporter
            exporter = PDFExporter(theme)
            return exporter.html_to_pdf(html_content)
        except ImportError:
            logger.warning("PDF exporter not available, returning HTML as fallback")
            return html_content.encode('utf-8')
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return html_content.encode('utf-8')


class ReportGenerationError(Exception):
    """Error during report generation."""
    pass


# Convenience function for quick report generation
def generate_universal_report(
    source_type: str,
    source_data: Dict[str, Any],
    cpa_profile: Optional[Dict[str, Any]] = None,
    output_format: str = 'html',
    tier_level: int = 2,
) -> ReportOutput:
    """
    Quick function to generate a universal report.

    Usage:
        from universal_report import generate_universal_report

        report = generate_universal_report(
            source_type='chatbot',
            source_data=session_data,
            cpa_profile={'firm_name': 'My Firm', 'primary_color': '#1e40af'},
            output_format='html',
        )

        html = report.html_content
    """
    engine = UniversalReportEngine()
    return engine.generate_report(
        source_type=source_type,
        source_data=source_data,
        cpa_profile=cpa_profile,
        output_format=output_format,
        tier_level=tier_level,
    )
