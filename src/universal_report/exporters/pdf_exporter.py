"""
PDF Exporter - Export reports to PDF format.

Supports multiple PDF generation backends:
1. WeasyPrint (preferred - maintains HTML/CSS fidelity)
2. ReportLab (fallback - manual layout)
3. HTML fallback (returns HTML if no PDF library available)
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING, Union
from pathlib import Path
from io import BytesIO
import logging

if TYPE_CHECKING:
    from universal_report.section_renderer import RenderedSection
    from universal_report.data_collector import NormalizedReportData
    from universal_report.branding.theme_manager import BrandTheme

logger = logging.getLogger(__name__)


# Check available PDF libraries
WEASYPRINT_AVAILABLE = False
REPORTLAB_AVAILABLE = False

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    pass

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    pass


class PDFExporter:
    """
    Export reports to PDF format.

    Tries WeasyPrint first for best HTML/CSS rendering,
    falls back to ReportLab for basic PDF generation.
    """

    def __init__(self, theme: Optional["BrandTheme"] = None):
        self.theme = theme

    def export(
        self,
        sections: List["RenderedSection"],
        data: "NormalizedReportData",
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Export sections to PDF.

        Args:
            sections: List of rendered sections
            data: Normalized report data
            output_path: Optional file path to save PDF

        Returns:
            PDF bytes
        """
        from universal_report.exporters.html_exporter import HTMLExporter

        # First generate HTML
        html_exporter = HTMLExporter(self.theme)
        html_content = html_exporter.export(sections, data)

        # Convert to PDF
        pdf_bytes = self.html_to_pdf(html_content)

        # Save to file if path provided
        if output_path:
            self._save_to_file(pdf_bytes, output_path)

        return pdf_bytes

    def html_to_pdf(self, html_content: str) -> bytes:
        """
        Convert HTML content to PDF.

        Tries available backends in order of preference.

        Args:
            html_content: HTML string to convert

        Returns:
            PDF bytes
        """
        if WEASYPRINT_AVAILABLE:
            return self._weasyprint_convert(html_content)
        elif REPORTLAB_AVAILABLE:
            return self._reportlab_convert(html_content)
        else:
            logger.warning("No PDF library available, returning HTML as bytes")
            return html_content.encode('utf-8')

    def _weasyprint_convert(self, html_content: str) -> bytes:
        """
        Convert HTML to PDF using WeasyPrint.

        WeasyPrint provides excellent HTML/CSS rendering including:
        - SVG support
        - CSS Grid/Flexbox
        - Web fonts
        - Page breaks
        """
        try:
            # Additional CSS for PDF
            pdf_css = CSS(string='''
                @page {
                    size: letter;
                    margin: 0.75in;
                }

                @page :first {
                    margin-top: 0.5in;
                }

                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                }

                /* Ensure SVGs render properly */
                svg {
                    max-width: 100%;
                }

                /* Page break handling */
                .page-break {
                    page-break-before: always;
                }

                h2, h3 {
                    page-break-after: avoid;
                }

                .card, .recommendation-card {
                    page-break-inside: avoid;
                }
            ''')

            html = HTML(string=html_content)
            pdf_bytes = html.write_pdf(stylesheets=[pdf_css])

            logger.info("PDF generated using WeasyPrint")
            return pdf_bytes

        except Exception as e:
            logger.error(f"WeasyPrint conversion failed: {e}")
            if REPORTLAB_AVAILABLE:
                return self._reportlab_convert(html_content)
            return html_content.encode('utf-8')

    def _reportlab_convert(self, html_content: str) -> bytes:
        """
        Convert to PDF using ReportLab.

        This is a simplified conversion that won't preserve all
        HTML/CSS styling but provides a basic PDF output.
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
            import re
            from html.parser import HTMLParser

            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=inch,
                bottomMargin=0.75*inch,
            )

            # Custom styles
            styles = getSampleStyleSheet()
            styles.add(ParagraphStyle(
                name='CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor(self.theme.primary_color if self.theme else '#2563eb'),
                spaceAfter=20,
                alignment=TA_CENTER,
            ))
            styles.add(ParagraphStyle(
                name='CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor(self.theme.primary_color if self.theme else '#2563eb'),
                spaceAfter=12,
                spaceBefore=20,
            ))
            styles.add(ParagraphStyle(
                name='CustomBody',
                parent=styles['BodyText'],
                fontSize=11,
                leading=14,
                alignment=TA_JUSTIFY,
            ))

            # Simple HTML to story conversion
            story = []

            # Extract text content from HTML (simplified)
            class HTMLTextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.current_tag = None

                def handle_starttag(self, tag, attrs):
                    self.current_tag = tag

                def handle_data(self, data):
                    text = data.strip()
                    if text:
                        self.text_parts.append((self.current_tag, text))

            extractor = HTMLTextExtractor()
            extractor.feed(html_content)

            for tag, text in extractor.text_parts:
                if tag == 'h1':
                    story.append(Paragraph(text, styles['CustomTitle']))
                elif tag in ('h2', 'h3'):
                    story.append(Paragraph(text, styles['CustomHeading']))
                elif tag == 'p' or tag is None:
                    story.append(Paragraph(text, styles['CustomBody']))
                    story.append(Spacer(1, 6))

            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()

            logger.info("PDF generated using ReportLab")
            return pdf_bytes

        except Exception as e:
            logger.error(f"ReportLab conversion failed: {e}")
            return html_content.encode('utf-8')

    def _save_to_file(self, pdf_bytes: bytes, output_path: str) -> None:
        """Save PDF to file."""
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pdf_bytes)
            logger.info(f"PDF report saved to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save PDF: {e}")
            raise

    @staticmethod
    def is_available() -> bool:
        """Check if PDF generation is available."""
        return WEASYPRINT_AVAILABLE or REPORTLAB_AVAILABLE

    @staticmethod
    def get_backend() -> str:
        """Get the name of the PDF backend being used."""
        if WEASYPRINT_AVAILABLE:
            return "weasyprint"
        elif REPORTLAB_AVAILABLE:
            return "reportlab"
        else:
            return "none"
