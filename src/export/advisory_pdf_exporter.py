"""
Advisory Report PDF Exporter - Generates professional PDF reports.

Uses ReportLab to create beautiful, CPA-ready advisory reports from
the structured data produced by AdvisoryReportGenerator.

Features:
- Professional visualizations (savings gauge, income charts, tax brackets)
- CPA/firm branding with logo support
- PDF bookmarks and table of contents
- Watermarks for draft documents
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from decimal import Decimal
from pathlib import Path
import logging
from dataclasses import dataclass, field
from io import BytesIO

# ReportLab imports
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image as RLImage,
    KeepTogether,
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Import visualization module
try:
    from export.pdf_visualizations import PDFChartGenerator, COLORS as VIZ_COLORS
    VISUALIZATIONS_AVAILABLE = True
except ImportError:
    VISUALIZATIONS_AVAILABLE = False

if TYPE_CHECKING:
    from advisory.report_generator import AdvisoryReportResult

logger = logging.getLogger(__name__)


@dataclass
class CPABrandConfig:
    """
    CPA/Firm branding configuration for PDF reports.

    Usage:
        brand = CPABrandConfig(
            firm_name="Smith & Associates CPA",
            logo_path="/path/to/logo.png",
            primary_color="#1a365d",
            advisor_name="John Smith, CPA",
            advisor_credentials=["CPA", "CFP", "MST"],
            contact_email="john@smithcpa.com",
            contact_phone="(555) 123-4567"
        )
    """
    # Firm information
    firm_name: str = "Tax Advisory Services"
    firm_tagline: Optional[str] = None
    logo_path: Optional[str] = None
    logo_width: float = 1.5  # inches

    # Advisor information
    advisor_name: Optional[str] = None
    advisor_credentials: List[str] = field(default_factory=list)
    advisor_photo_path: Optional[str] = None

    # Contact information
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_website: Optional[str] = None
    contact_address: Optional[str] = None

    # Branding colors (hex codes)
    primary_color: str = "#2c5aa0"
    secondary_color: str = "#1a365d"
    accent_color: str = "#10b981"

    # Footer settings
    show_footer_on_all_pages: bool = True
    footer_text: Optional[str] = None

    def get_primary_color(self):
        """Convert hex to ReportLab color."""
        return colors.HexColor(self.primary_color)

    def get_secondary_color(self):
        """Convert hex to ReportLab color."""
        return colors.HexColor(self.secondary_color)

    def get_accent_color(self):
        """Convert hex to ReportLab color."""
        return colors.HexColor(self.accent_color)


class PDFWatermark:
    """Watermark handler for draft/final PDFs."""

    @staticmethod
    def add_watermark(canvas_obj, doc, watermark_text: Optional[str] = None):
        """Add watermark to PDF page."""
        if not watermark_text:
            return

        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica-Bold', 60)
        canvas_obj.setFillColor(colors.lightgrey, alpha=0.3)
        canvas_obj.translate(4.25 * inch, 5.5 * inch)
        canvas_obj.rotate(45)
        canvas_obj.drawCentredString(0, 0, watermark_text)
        canvas_obj.restoreState()


class AdvisoryPDFExporter:
    """
    Exports advisory reports to professional PDF format.

    Features:
    - Professional formatting
    - Headers/footers with page numbers and CPA branding
    - Tables for financial data
    - Charts for visualizations (Matplotlib)
    - Watermarks for draft documents
    - Table of contents with bookmarks
    - CPA logo and branding support
    """

    def __init__(
        self,
        page_size=letter,
        watermark: Optional[str] = None,
        brand_config: Optional[CPABrandConfig] = None,
        include_visualizations: bool = True,
    ):
        """
        Initialize PDF exporter.

        Args:
            page_size: Page size (letter or A4)
            watermark: Watermark text for draft documents (e.g., "DRAFT")
            brand_config: CPA/firm branding configuration
            include_visualizations: Whether to include charts and gauges
        """
        self.page_size = page_size
        self.watermark = watermark
        self.brand_config = brand_config or CPABrandConfig()
        self.include_visualizations = include_visualizations and VISUALIZATIONS_AVAILABLE
        self.width, self.height = page_size

        # Initialize visualization generator
        if self.include_visualizations:
            self.chart_generator = PDFChartGenerator()
        else:
            self.chart_generator = None

        # Track sections for TOC and bookmarks
        self.toc_entries: List[Dict[str, Any]] = []
        self.current_page = 1

        # Set up styles
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

        logger.info(
            f"PDF Exporter initialized (watermark: {watermark or 'None'}, "
            f"brand: {self.brand_config.firm_name}, "
            f"visualizations: {self.include_visualizations})"
        )

    def _create_custom_styles(self):
        """Create custom paragraph styles using brand colors."""
        primary_color = self.brand_config.get_primary_color()
        secondary_color = self.brand_config.get_secondary_color()
        accent_color = self.brand_config.get_accent_color()

        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=secondary_color,
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        ))

        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=primary_color,
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold',
        ))

        # Subsection heading
        self.styles.add(ParagraphStyle(
            name='SubsectionHeading',
            parent=self.styles['Heading3'],
            fontSize=13,
            textColor=colors.HexColor('#4a4a4a'),
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold',
        ))

        # Body text
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#333333'),
            alignment=TA_JUSTIFY,
        ))

        # Bullet points
        self.styles.add(ParagraphStyle(
            name='BulletPoint',
            parent=self.styles['CustomBody'],
            leftIndent=20,
            bulletIndent=10,
        ))

        # Disclaimer text
        self.styles.add(ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['BodyText'],
            fontSize=9,
            leading=11,
            textColor=colors.HexColor('#666666'),
            alignment=TA_JUSTIFY,
        ))

        # TOC entry styles
        self.styles.add(ParagraphStyle(
            name='TOCEntry',
            parent=self.styles['BodyText'],
            fontSize=11,
            leading=18,
            textColor=primary_color,
            leftIndent=0,
        ))

        self.styles.add(ParagraphStyle(
            name='TOCSubEntry',
            parent=self.styles['BodyText'],
            fontSize=10,
            leading=16,
            textColor=colors.HexColor('#555555'),
            leftIndent=20,
        ))

        # Savings highlight style
        self.styles.add(ParagraphStyle(
            name='SavingsHighlight',
            parent=self.styles['BodyText'],
            fontSize=14,
            textColor=accent_color,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
        ))

        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#888888'),
            alignment=TA_CENTER,
        ))

    def generate_pdf(
        self,
        report: "AdvisoryReportResult",
        output_path: str,
        include_charts: bool = True,
        include_toc: bool = True,
    ) -> str:
        """
        Generate PDF from advisory report.

        Args:
            report: Advisory report result from AdvisoryReportGenerator
            output_path: Path to save PDF
            include_charts: Whether to include charts and graphs
            include_toc: Whether to include table of contents

        Returns:
            Path to generated PDF file
        """
        logger.info(f"Generating PDF for report {report.report_id}")

        # Reset TOC entries
        self.toc_entries = []

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Create PDF
        doc = SimpleDocTemplate(
            str(output_file),
            pagesize=self.page_size,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=1.25 * inch,  # Extra space for header
            bottomMargin=1 * inch,   # Extra space for footer
        )

        # Store report reference for header/footer callbacks
        self._current_report = report

        # Build story (content)
        story = []

        # Add cover page with branding
        story.extend(self._build_cover_page(report))
        story.append(PageBreak())

        # Add Table of Contents (if enabled)
        if include_toc:
            story.extend(self._build_table_of_contents(report))
            story.append(PageBreak())

        # Add executive summary
        self.toc_entries.append({'title': 'Executive Summary', 'level': 1})
        story.extend(self._build_executive_summary(report))
        story.append(PageBreak())

        # Add each section
        for section in report.sections:
            if section.section_id == "executive_summary":
                continue  # Already added

            # Track section for TOC
            self.toc_entries.append({'title': section.title, 'level': 1})

            story.extend(self._build_section(section, include_charts))

            # Page break after major sections
            if section.section_id in ["current_position", "recommendations", "entity_comparison"]:
                story.append(PageBreak())

        # Build PDF with header/footer and optional watermark
        doc.build(
            story,
            onFirstPage=self._add_first_page_elements,
            onLaterPages=self._add_later_page_elements,
        )

        logger.info(f"PDF generated: {output_path}")
        return str(output_file)

    def _add_first_page_elements(self, canvas_obj, doc):
        """Add elements to the first page (cover page)."""
        canvas_obj.saveState()

        # Add watermark if specified
        if self.watermark:
            PDFWatermark.add_watermark(canvas_obj, doc, self.watermark)

        # Add logo to cover page (centered at top)
        self._add_logo(canvas_obj, doc, cover_page=True)

        canvas_obj.restoreState()

    def _add_later_page_elements(self, canvas_obj, doc):
        """Add header and footer to subsequent pages."""
        canvas_obj.saveState()

        # Add watermark if specified
        if self.watermark:
            PDFWatermark.add_watermark(canvas_obj, doc, self.watermark)

        # Add header with branding
        self._add_header(canvas_obj, doc)

        # Add footer
        self._add_footer(canvas_obj, doc)

        canvas_obj.restoreState()

    def _add_logo(self, canvas_obj, doc, cover_page: bool = False):
        """Add logo to the page."""
        if not self.brand_config.logo_path:
            return

        try:
            logo_path = Path(self.brand_config.logo_path)
            if not logo_path.exists():
                logger.warning(f"Logo file not found: {logo_path}")
                return

            logo_width = self.brand_config.logo_width * inch

            if cover_page:
                # Center logo at top of cover page
                x = (self.width - logo_width) / 2
                y = self.height - 1.2 * inch
            else:
                # Left-align in header
                x = 0.75 * inch
                y = self.height - 0.7 * inch

            canvas_obj.drawImage(
                str(logo_path),
                x, y,
                width=logo_width,
                preserveAspectRatio=True,
                anchor='nw'
            )

        except Exception as e:
            logger.error(f"Error adding logo: {e}")

    def _add_header(self, canvas_obj, doc):
        """Add branded header to the page."""
        # Header background line
        primary_color = self.brand_config.get_primary_color()
        canvas_obj.setStrokeColor(primary_color)
        canvas_obj.setLineWidth(2)
        canvas_obj.line(
            0.75 * inch,
            self.height - 0.9 * inch,
            self.width - 0.75 * inch,
            self.height - 0.9 * inch
        )

        # Firm name on the left (if no logo)
        if not self.brand_config.logo_path:
            canvas_obj.setFont('Helvetica-Bold', 10)
            canvas_obj.setFillColor(primary_color)
            canvas_obj.drawString(
                0.75 * inch,
                self.height - 0.6 * inch,
                self.brand_config.firm_name
            )
        else:
            self._add_logo(canvas_obj, doc, cover_page=False)

        # Report title on the right
        if hasattr(self, '_current_report'):
            canvas_obj.setFont('Helvetica', 9)
            canvas_obj.setFillColor(colors.HexColor('#666666'))
            canvas_obj.drawRightString(
                self.width - 0.75 * inch,
                self.height - 0.6 * inch,
                f"Tax Advisory Report - {self._current_report.taxpayer_name}"
            )

    def _add_footer(self, canvas_obj, doc):
        """Add branded footer to the page."""
        if not self.brand_config.show_footer_on_all_pages:
            return

        # Footer line
        canvas_obj.setStrokeColor(colors.HexColor('#cccccc'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(
            0.75 * inch,
            0.75 * inch,
            self.width - 0.75 * inch,
            0.75 * inch
        )

        # Page number on right
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.setFillColor(colors.HexColor('#666666'))
        canvas_obj.drawRightString(
            self.width - 0.75 * inch,
            0.5 * inch,
            f"Page {doc.page}"
        )

        # Firm contact info in center
        footer_parts = []
        if self.brand_config.contact_phone:
            footer_parts.append(self.brand_config.contact_phone)
        if self.brand_config.contact_email:
            footer_parts.append(self.brand_config.contact_email)
        if self.brand_config.contact_website:
            footer_parts.append(self.brand_config.contact_website)

        if footer_parts:
            footer_text = " | ".join(footer_parts)
            canvas_obj.drawCentredString(
                self.width / 2,
                0.5 * inch,
                footer_text
            )

        # Advisor info on left (if available)
        if self.brand_config.advisor_name:
            advisor_text = self.brand_config.advisor_name
            if self.brand_config.advisor_credentials:
                advisor_text += f", {', '.join(self.brand_config.advisor_credentials)}"
            canvas_obj.drawString(
                0.75 * inch,
                0.5 * inch,
                advisor_text
            )

    def _build_table_of_contents(self, report: "AdvisoryReportResult") -> List:
        """Build table of contents page."""
        story = []

        story.append(Paragraph("Table of Contents", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.5 * inch))

        # Define TOC entries based on report sections
        toc_items = [
            ("Executive Summary", 1),
        ]

        for section in report.sections:
            if section.section_id != "executive_summary":
                toc_items.append((section.title, 1))

        # Build TOC entries
        for title, level in toc_items:
            style = self.styles['TOCEntry'] if level == 1 else self.styles['TOCSubEntry']
            # Add dots and page number placeholder (ReportLab handles actual page numbers)
            toc_entry = f"{title}"
            story.append(Paragraph(toc_entry, style))
            story.append(Spacer(1, 0.05 * inch))

        return story

    def _build_cover_page(self, report: "AdvisoryReportResult") -> List:
        """Build PDF cover page with branding and savings gauge."""
        story = []

        # Space for logo (added via canvas)
        if self.brand_config.logo_path:
            story.append(Spacer(1, 1 * inch))

        # Firm name and tagline (if no logo)
        if not self.brand_config.logo_path:
            story.append(Spacer(1, 0.5 * inch))
            story.append(Paragraph(
                self.brand_config.firm_name,
                self.styles['CustomTitle']
            ))
            if self.brand_config.firm_tagline:
                story.append(Paragraph(
                    f"<i>{self.brand_config.firm_tagline}</i>",
                    ParagraphStyle(
                        'Tagline',
                        parent=self.styles['Normal'],
                        fontSize=12,
                        textColor=colors.HexColor('#666666'),
                        alignment=TA_CENTER,
                    )
                ))
            story.append(Spacer(1, 0.5 * inch))

        # Title
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph(
            "Tax Advisory Report",
            self.styles['CustomTitle']
        ))

        story.append(Spacer(1, 0.2 * inch))

        # Client name
        story.append(Paragraph(
            f"Prepared for: <b>{report.taxpayer_name}</b>",
            self.styles['Heading2']
        ))

        story.append(Spacer(1, 0.3 * inch))

        # Add Savings Gauge Visualization
        if self.include_visualizations and self.chart_generator:
            savings_gauge = self._create_savings_gauge_image(
                current_tax=float(report.current_tax_liability),
                potential_savings=float(report.potential_savings)
            )
            if savings_gauge:
                story.append(savings_gauge)
                story.append(Spacer(1, 0.2 * inch))
        else:
            # Fallback: Text-based savings highlight
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph(
                f"Potential Tax Savings: ${report.potential_savings:,.2f}",
                self.styles['SavingsHighlight']
            ))
            story.append(Spacer(1, 0.2 * inch))

        # Key metrics table
        primary_color = self.brand_config.get_primary_color()
        metrics_data = [
            ["Tax Year:", str(report.tax_year)],
            ["Report Date:", datetime.now().strftime("%B %d, %Y")],
            ["Filing Status:", report.filing_status.replace('_', ' ').title()],
            ["Current Tax Liability:", f"${report.current_tax_liability:,.2f}"],
            ["Potential Savings:", f"${report.potential_savings:,.2f}"],
            ["Recommendations:", str(report.top_recommendations_count)],
        ]

        metrics_table = Table(metrics_data, colWidths=[2.5 * inch, 3.5 * inch])
        metrics_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TEXTCOLOR', (0, 0), (0, -1), primary_color),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(metrics_table)

        story.append(Spacer(1, 0.5 * inch))

        # Confidence indicator
        confidence_text = f"Analysis Confidence: <b>{report.confidence_score}%</b>"
        story.append(Paragraph(confidence_text, self.styles['Heading3']))

        # Advisor signature block (if available)
        if self.brand_config.advisor_name:
            story.append(Spacer(1, 0.5 * inch))
            advisor_text = f"Prepared by: <b>{self.brand_config.advisor_name}</b>"
            if self.brand_config.advisor_credentials:
                advisor_text += f"<br/><i>{', '.join(self.brand_config.advisor_credentials)}</i>"
            story.append(Paragraph(advisor_text, self.styles['CustomBody']))

        return story

    def _create_savings_gauge_image(
        self,
        current_tax: float,
        potential_savings: float
    ) -> Optional[RLImage]:
        """Create savings gauge visualization for PDF."""
        if not self.chart_generator:
            return None

        try:
            buffer = self.chart_generator.create_savings_gauge(
                current_tax=current_tax,
                potential_savings=potential_savings,
                width=5,
                height=2.5
            )

            if buffer:
                return self.chart_generator.buffer_to_reportlab_image(
                    buffer, width=5, height=2.5
                )
        except Exception as e:
            logger.error(f"Error creating savings gauge: {e}")

        return None

    def _build_executive_summary(self, report: "AdvisoryReportResult") -> List:
        """Build executive summary section."""
        story = []

        # Find executive summary section
        exec_summary = next(
            (s for s in report.sections if s.section_id == "executive_summary"),
            None
        )

        if not exec_summary:
            return story

        story.append(Paragraph("Executive Summary", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.2 * inch))

        # Overview
        content = exec_summary.content
        if "overview" in content:
            story.append(Paragraph(content["overview"], self.styles['CustomBody']))
            story.append(Spacer(1, 0.2 * inch))

        # Current tax position summary table
        if "current_liability" in content:
            liability = content["current_liability"]
            summary_data = [
                ["Item", "Amount"],
                ["Federal Tax", f"${liability.get('federal', 0):,.2f}"],
                ["State Tax", f"${liability.get('state', 0):,.2f}"],
                ["Total Tax", f"${liability.get('total', 0):,.2f}"],
            ]

            summary_table = Table(summary_data, colWidths=[3 * inch, 2.5 * inch])
            summary_table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),

                # Data rows
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),

                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

                # Total row emphasis
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
            ]))

            story.append(summary_table)

        return story

    def _build_section(self, section, include_charts: bool = True) -> List:
        """Build a report section."""
        story = []

        # Section heading
        story.append(Paragraph(section.title, self.styles['SectionHeading']))
        story.append(Spacer(1, 0.15 * inch))

        # Handle different section types
        if section.section_id == "current_position":
            story.extend(self._build_current_position_section(section.content))

        elif section.section_id == "recommendations":
            story.extend(self._build_recommendations_section(section.content))

        elif section.section_id == "action_plan":
            story.extend(self._build_action_plan_section(section.content))

        elif section.section_id == "disclaimers":
            story.extend(self._build_disclaimers_section(section.content))

        elif section.section_id == "entity_comparison":
            story.extend(self._build_entity_comparison_section(section.content))

        elif section.section_id == "multi_year_projection":
            story.extend(self._build_projection_section(section.content, include_charts))

        return story

    def _build_current_position_section(self, content: Dict) -> List:
        """Build current tax position section with visualizations."""
        story = []

        # Income summary
        if "income_summary" in content:
            story.append(Paragraph("Income Summary", self.styles['SubsectionHeading']))

            income = content["income_summary"]
            income_data = [
                ["Description", "Amount"],
                ["Total Income", f"${income.get('total_income', 0):,.2f}"],
                ["Adjusted Gross Income", f"${income.get('agi', 0):,.2f}"],
                ["Taxable Income", f"${income.get('taxable_income', 0):,.2f}"],
            ]

            income_table = self._create_data_table(income_data)
            story.append(income_table)
            story.append(Spacer(1, 0.2 * inch))

            # Add income breakdown pie chart if available
            if self.include_visualizations and "income_breakdown" in content:
                income_chart = self._create_income_chart(content["income_breakdown"])
                if income_chart:
                    story.append(income_chart)
                    story.append(Spacer(1, 0.2 * inch))

        # Tax liability
        if "tax_liability" in content:
            story.append(Paragraph("Tax Liability", self.styles['SubsectionHeading']))

            liability = content["tax_liability"]
            tax_data = [
                ["Type", "Amount"],
                ["Federal Tax", f"${liability.get('federal_tax', 0):,.2f}"],
                ["State Tax", f"${liability.get('state_tax', 0):,.2f}"],
                ["Total Tax", f"${liability.get('total_tax', 0):,.2f}"],
            ]

            tax_table = self._create_data_table(tax_data)
            story.append(tax_table)
            story.append(Spacer(1, 0.2 * inch))

        # Tax bracket visualization
        if self.include_visualizations and "income_summary" in content:
            taxable_income = content["income_summary"].get('taxable_income', 0)
            filing_status = content.get('filing_status', 'single')
            if taxable_income > 0:
                bracket_chart = self._create_tax_bracket_chart(
                    taxable_income=float(taxable_income),
                    filing_status=filing_status
                )
                if bracket_chart:
                    story.append(Paragraph("Tax Bracket Breakdown", self.styles['SubsectionHeading']))
                    story.append(bracket_chart)
                    story.append(Spacer(1, 0.2 * inch))

        # Deduction comparison visualization
        if self.include_visualizations and "deductions" in content:
            deductions = content["deductions"]
            standard = deductions.get('standard_deduction', 0)
            itemized = deductions.get('itemized_total', 0)
            selected = deductions.get('selected_type', 'standard')

            if standard > 0 or itemized > 0:
                deduction_chart = self._create_deduction_chart(
                    standard_deduction=float(standard),
                    itemized_deduction=float(itemized),
                    selected_type=selected
                )
                if deduction_chart:
                    story.append(Paragraph("Deduction Analysis", self.styles['SubsectionHeading']))
                    story.append(deduction_chart)
                    story.append(Spacer(1, 0.2 * inch))

        # Effective rate
        if "effective_rate" in content:
            rate_text = f"Effective Tax Rate: <b>{content['effective_rate']}%</b>"
            story.append(Paragraph(rate_text, self.styles['CustomBody']))

        return story

    def _create_income_chart(self, income_breakdown: List[Dict]) -> Optional[RLImage]:
        """Create income pie chart for PDF."""
        if not self.chart_generator or not income_breakdown:
            return None

        try:
            buffer = self.chart_generator.create_income_pie_chart(
                income_items=income_breakdown,
                width=5,
                height=3.5,
                title="Income Breakdown by Category"
            )

            if buffer:
                return self.chart_generator.buffer_to_reportlab_image(
                    buffer, width=5, height=3.5
                )
        except Exception as e:
            logger.error(f"Error creating income chart: {e}")

        return None

    def _create_tax_bracket_chart(
        self,
        taxable_income: float,
        filing_status: str
    ) -> Optional[RLImage]:
        """Create tax bracket chart for PDF."""
        if not self.chart_generator:
            return None

        try:
            # Normalize filing status
            status_map = {
                'married_filing_jointly': 'married_joint',
                'married_filing_separately': 'married_separate',
                'head_of_household': 'head_of_household',
                'single': 'single',
            }
            normalized_status = status_map.get(filing_status, 'single')

            buffer = self.chart_generator.create_tax_bracket_chart(
                taxable_income=taxable_income,
                filing_status=normalized_status,
                width=6,
                height=3
            )

            if buffer:
                return self.chart_generator.buffer_to_reportlab_image(
                    buffer, width=6, height=3
                )
        except Exception as e:
            logger.error(f"Error creating tax bracket chart: {e}")

        return None

    def _create_deduction_chart(
        self,
        standard_deduction: float,
        itemized_deduction: float,
        selected_type: str
    ) -> Optional[RLImage]:
        """Create deduction comparison chart for PDF."""
        if not self.chart_generator:
            return None

        try:
            buffer = self.chart_generator.create_deduction_comparison(
                standard_deduction=standard_deduction,
                itemized_deduction=itemized_deduction,
                selected_type=selected_type,
                width=5,
                height=2.5
            )

            if buffer:
                return self.chart_generator.buffer_to_reportlab_image(
                    buffer, width=5, height=2.5
                )
        except Exception as e:
            logger.error(f"Error creating deduction chart: {e}")

        return None

    def _build_recommendations_section(self, content: Dict) -> List:
        """Build recommendations section with comparison visualization."""
        story = []

        # Summary
        total_savings = content.get('total_potential_savings', 0)
        confidence = content.get('confidence', 0)

        summary = f"We identified <b>{content.get('total_opportunities', 0)} optimization opportunities</b> "
        summary += f"with potential savings of <b>${total_savings:,.2f}</b> "
        summary += f"(Confidence: {confidence}%)."

        story.append(Paragraph(summary, self.styles['CustomBody']))
        story.append(Spacer(1, 0.3 * inch))

        # Add Current vs Optimized comparison chart
        if self.include_visualizations and "current_scenario" in content and "optimized_scenario" in content:
            comparison_chart = self._create_comparison_chart(
                current_scenario=content["current_scenario"],
                optimized_scenario=content["optimized_scenario"]
            )
            if comparison_chart:
                story.append(Paragraph("Tax Comparison: Current vs Optimized", self.styles['SubsectionHeading']))
                story.append(comparison_chart)
                story.append(Spacer(1, 0.3 * inch))

        # Top recommendations
        if "top_recommendations" in content:
            story.append(Paragraph("Top Recommendations", self.styles['SubsectionHeading']))

            for i, rec in enumerate(content["top_recommendations"][:10], 1):
                # Recommendation box
                rec_items = []

                # Title with savings
                accent_color = self.brand_config.accent_color
                title = f"<b>{i}. {rec['title']}</b> - Potential Savings: <font color='{accent_color}'><b>${rec['savings']:,.2f}</b></font>"
                rec_items.append(Paragraph(title, self.styles['CustomBody']))
                rec_items.append(Spacer(1, 0.05 * inch))

                # Description
                rec_items.append(Paragraph(rec['description'], self.styles['CustomBody']))
                rec_items.append(Spacer(1, 0.05 * inch))

                # Action required
                action_text = f"<b>Action Required:</b> {rec['action_required']}"
                rec_items.append(Paragraph(action_text, self.styles['CustomBody']))
                rec_items.append(Spacer(1, 0.05 * inch))

                # IRS reference
                if rec.get('irs_reference'):
                    ref_text = f"<i>IRS Reference: {rec['irs_reference']}</i>"
                    rec_items.append(Paragraph(ref_text, self.styles['Disclaimer']))

                # Keep recommendation together
                story.append(KeepTogether(rec_items))
                story.append(Spacer(1, 0.2 * inch))

        return story

    def _create_comparison_chart(
        self,
        current_scenario: Dict[str, float],
        optimized_scenario: Dict[str, float]
    ) -> Optional[RLImage]:
        """Create current vs optimized comparison chart for PDF."""
        if not self.chart_generator:
            return None

        try:
            buffer = self.chart_generator.create_comparison_chart(
                current_scenario=current_scenario,
                optimized_scenario=optimized_scenario,
                width=6,
                height=3.5
            )

            if buffer:
                return self.chart_generator.buffer_to_reportlab_image(
                    buffer, width=6, height=3.5
                )
        except Exception as e:
            logger.error(f"Error creating comparison chart: {e}")

        return None

    def _build_action_plan_section(self, content: Dict) -> List:
        """Build action plan section."""
        story = []

        # Immediate actions
        if "immediate_actions" in content and content["immediate_actions"]:
            story.append(Paragraph("Immediate Actions", self.styles['SubsectionHeading']))

            for action in content["immediate_actions"]:
                bullet = f"• <b>{action['title']}</b> (Saves: ${action['savings']:,.2f})<br/>"
                bullet += f"  {action['action']}"
                story.append(Paragraph(bullet, self.styles['BulletPoint']))
                story.append(Spacer(1, 0.1 * inch))

            story.append(Spacer(1, 0.2 * inch))

        # Current year actions
        if "current_year_actions" in content and content["current_year_actions"]:
            story.append(Paragraph("Current Year Actions", self.styles['SubsectionHeading']))

            for action in content["current_year_actions"]:
                bullet = f"• <b>{action['title']}</b> (Saves: ${action['savings']:,.2f})<br/>"
                bullet += f"  {action['action']}"
                story.append(Paragraph(bullet, self.styles['BulletPoint']))
                story.append(Spacer(1, 0.1 * inch))

        return story

    def _build_disclaimers_section(self, content: Dict) -> List:
        """Build disclaimers section with strong legal disclaimers."""
        story = []

        # Standard legal disclaimer - always included
        story.append(Paragraph("IMPORTANT LEGAL NOTICE", self.styles['SubsectionHeading']))
        story.append(Paragraph(
            "<b>NOT TAX ADVICE:</b> This document is for informational and educational purposes only. "
            "TaxAdvisor Pro is a tax information platform, NOT a tax preparation service or tax advisory service. "
            "All calculations, estimates, and recommendations are approximations based on general tax rules "
            "and may not reflect your actual tax situation.",
            self.styles['Disclaimer']
        ))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(
            "<b>CONSULT A PROFESSIONAL:</b> ALWAYS consult with a licensed CPA, Enrolled Agent, "
            "or tax attorney before making any tax decisions or filing any tax returns. "
            "Do not rely solely on this document for tax planning or filing decisions.",
            self.styles['Disclaimer']
        ))
        story.append(Spacer(1, 0.2 * inch))

        # Additional disclaimers from content
        if "disclaimers" in content:
            story.append(Paragraph("Additional Disclaimers", self.styles['SubsectionHeading']))

            for disclaimer in content["disclaimers"]:
                story.append(Paragraph(f"• {disclaimer}", self.styles['Disclaimer']))
                story.append(Spacer(1, 0.08 * inch))

            story.append(Spacer(1, 0.2 * inch))

        # Methodology
        if "methodology" in content:
            story.append(Paragraph("Methodology", self.styles['SubsectionHeading']))

            for method in content["methodology"]:
                story.append(Paragraph(f"• {method}", self.styles['Disclaimer']))
                story.append(Spacer(1, 0.08 * inch))

        return story

    def _build_entity_comparison_section(self, content: Dict) -> List:
        """Build entity comparison section."""
        story = []

        story.append(Paragraph(
            "This section compares different business entity structures to optimize your tax position.",
            self.styles['CustomBody']
        ))
        story.append(Spacer(1, 0.2 * inch))

        if "entity_comparison" in content:
            # Build comparison table
            headers = ["Entity Type", "Total Tax", "SE Tax", "Net Benefit"]
            data = [headers]

            for entity_type, analysis in content["entity_comparison"].items():
                row = [
                    entity_type.replace('_', ' ').title(),
                    f"${analysis['total_tax']:,.2f}",
                    f"${analysis.get('self_employment_tax', 0):,.2f}",
                    f"${analysis.get('net_benefit', 0):,.2f}",
                ]
                data.append(row)

            entity_table = self._create_data_table(data)
            story.append(entity_table)

        return story

    def _build_projection_section(self, content: Dict, include_charts: bool) -> List:
        """Build multi-year projection section."""
        story = []

        if "yearly_data" in content:
            years_data = content["yearly_data"]

            # Build projection table
            headers = ["Year", "Income", "Tax", "Effective Rate"]
            data = [headers]

            for year_data in years_data:
                row = [
                    str(year_data['year']),
                    f"${year_data['total_income']:,.0f}",
                    f"${year_data['total_tax']:,.0f}",
                    f"{year_data['effective_rate']:.1f}%",
                ]
                data.append(row)

            projection_table = self._create_data_table(data)
            story.append(projection_table)

        return story

    def _create_data_table(self, data: List[List[str]]) -> Table:
        """Create a styled data table with brand colors."""
        primary_color = self.brand_config.get_primary_color()

        table = Table(data)
        table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

            # Data
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))

        return table


# Convenience functions
def export_advisory_report_to_pdf(
    report: "AdvisoryReportResult",
    output_path: str,
    watermark: Optional[str] = "DRAFT",
    include_charts: bool = True,
    include_toc: bool = True,
    brand_config: Optional[CPABrandConfig] = None,
) -> str:
    """
    Quick function to export advisory report to PDF.

    Usage:
        from export.advisory_pdf_exporter import export_advisory_report_to_pdf, CPABrandConfig

        # Basic usage
        pdf_path = export_advisory_report_to_pdf(
            report=my_advisory_report,
            output_path="/tmp/advisory_report.pdf",
            watermark="DRAFT",  # or None for final version
        )

        # With CPA branding
        brand = CPABrandConfig(
            firm_name="Smith & Associates CPA",
            logo_path="/path/to/logo.png",
            advisor_name="John Smith",
            advisor_credentials=["CPA", "CFP"],
            contact_email="john@smithcpa.com",
            contact_phone="(555) 123-4567",
        )

        pdf_path = export_advisory_report_to_pdf(
            report=my_advisory_report,
            output_path="/tmp/branded_report.pdf",
            watermark=None,  # Final version, no watermark
            brand_config=brand,
        )
    """
    exporter = AdvisoryPDFExporter(
        watermark=watermark,
        brand_config=brand_config,
        include_visualizations=include_charts,
    )
    return exporter.generate_pdf(report, output_path, include_charts, include_toc)


def create_branded_pdf_exporter(
    firm_name: str,
    logo_path: Optional[str] = None,
    advisor_name: Optional[str] = None,
    advisor_credentials: Optional[List[str]] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    primary_color: str = "#2c5aa0",
    accent_color: str = "#10b981",
) -> AdvisoryPDFExporter:
    """
    Create a branded PDF exporter with CPA/firm configuration.

    Usage:
        from export.advisory_pdf_exporter import create_branded_pdf_exporter

        exporter = create_branded_pdf_exporter(
            firm_name="Smith & Associates CPA",
            logo_path="/path/to/logo.png",
            advisor_name="John Smith, CPA",
            contact_email="john@smithcpa.com",
        )

        pdf_path = exporter.generate_pdf(report, "/tmp/report.pdf")
    """
    brand_config = CPABrandConfig(
        firm_name=firm_name,
        logo_path=logo_path,
        advisor_name=advisor_name,
        advisor_credentials=advisor_credentials or [],
        contact_email=contact_email,
        contact_phone=contact_phone,
        primary_color=primary_color,
        accent_color=accent_color,
    )

    return AdvisoryPDFExporter(
        brand_config=brand_config,
        watermark=None,  # Final version by default
        include_visualizations=True,
    )
