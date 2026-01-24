"""
Advisory Report PDF Exporter - Generates professional PDF reports.

Uses ReportLab to create beautiful, CPA-ready advisory reports from
the structured data produced by AdvisoryReportGenerator.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from decimal import Decimal
from pathlib import Path
import logging

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

if TYPE_CHECKING:
    from advisory.report_generator import AdvisoryReportResult

logger = logging.getLogger(__name__)


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
    - Headers/footers with page numbers
    - Tables for financial data
    - Charts for visualizations (Matplotlib)
    - Watermarks for draft documents
    - Table of contents
    """

    def __init__(
        self,
        page_size=letter,
        watermark: Optional[str] = None,
    ):
        """
        Initialize PDF exporter.

        Args:
            page_size: Page size (letter or A4)
            watermark: Watermark text for draft documents (e.g., "DRAFT")
        """
        self.page_size = page_size
        self.watermark = watermark
        self.width, self.height = page_size

        # Set up styles
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

        logger.info(f"PDF Exporter initialized (watermark: {watermark or 'None'})")

    def _create_custom_styles(self):
        """Create custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        ))

        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c5aa0'),
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

    def generate_pdf(
        self,
        report: "AdvisoryReportResult",
        output_path: str,
        include_charts: bool = True,
    ) -> str:
        """
        Generate PDF from advisory report.

        Args:
            report: Advisory report result from AdvisoryReportGenerator
            output_path: Path to save PDF
            include_charts: Whether to include charts and graphs

        Returns:
            Path to generated PDF file
        """
        logger.info(f"Generating PDF for report {report.report_id}")

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Create PDF
        doc = SimpleDocTemplate(
            str(output_file),
            pagesize=self.page_size,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=1 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build story (content)
        story = []

        # Add cover page
        story.extend(self._build_cover_page(report))
        story.append(PageBreak())

        # Add executive summary
        story.extend(self._build_executive_summary(report))
        story.append(PageBreak())

        # Add each section
        for section in report.sections:
            if section.section_id == "executive_summary":
                continue  # Already added

            story.extend(self._build_section(section, include_charts))

            # Page break after major sections
            if section.section_id in ["current_position", "recommendations", "entity_comparison"]:
                story.append(PageBreak())

        # Build PDF with watermark if specified
        if self.watermark:
            doc.build(
                story,
                onFirstPage=lambda c, d: PDFWatermark.add_watermark(c, d, self.watermark),
                onLaterPages=lambda c, d: PDFWatermark.add_watermark(c, d, self.watermark),
            )
        else:
            doc.build(story)

        logger.info(f"PDF generated: {output_path}")
        return str(output_file)

    def _build_cover_page(self, report: "AdvisoryReportResult") -> List:
        """Build PDF cover page."""
        story = []

        # Title
        story.append(Spacer(1, 1.5 * inch))
        story.append(Paragraph(
            "Tax Advisory Report",
            self.styles['CustomTitle']
        ))

        story.append(Spacer(1, 0.3 * inch))

        # Client name
        story.append(Paragraph(
            f"Prepared for: <b>{report.taxpayer_name}</b>",
            self.styles['Heading2']
        ))

        story.append(Spacer(1, 0.5 * inch))

        # Key metrics table
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
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(metrics_table)

        story.append(Spacer(1, 1 * inch))

        # Confidence indicator
        confidence_text = f"Analysis Confidence: <b>{report.confidence_score}%</b>"
        story.append(Paragraph(confidence_text, self.styles['Heading3']))

        return story

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
        """Build current tax position section."""
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

        # Effective rate
        if "effective_rate" in content:
            rate_text = f"Effective Tax Rate: <b>{content['effective_rate']}%</b>"
            story.append(Paragraph(rate_text, self.styles['CustomBody']))

        return story

    def _build_recommendations_section(self, content: Dict) -> List:
        """Build recommendations section."""
        story = []

        # Summary
        total_savings = content.get('total_potential_savings', 0)
        confidence = content.get('confidence', 0)

        summary = f"We identified <b>{content.get('total_opportunities', 0)} optimization opportunities</b> "
        summary += f"with potential savings of <b>${total_savings:,.2f}</b> "
        summary += f"(Confidence: {confidence}%)."

        story.append(Paragraph(summary, self.styles['CustomBody']))
        story.append(Spacer(1, 0.3 * inch))

        # Top recommendations
        if "top_recommendations" in content:
            story.append(Paragraph("Top Recommendations", self.styles['SubsectionHeading']))

            for i, rec in enumerate(content["top_recommendations"][:10], 1):
                # Recommendation box
                rec_items = []

                # Title with savings
                title = f"<b>{i}. {rec['title']}</b> - Potential Savings: <b>${rec['savings']:,.2f}</b>"
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
        """Create a styled data table."""
        table = Table(data)
        table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
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
        ]))

        return table


# Convenience function
def export_advisory_report_to_pdf(
    report: "AdvisoryReportResult",
    output_path: str,
    watermark: Optional[str] = "DRAFT",
    include_charts: bool = True,
) -> str:
    """
    Quick function to export advisory report to PDF.

    Usage:
        from export.advisory_pdf_exporter import export_advisory_report_to_pdf

        pdf_path = export_advisory_report_to_pdf(
            report=my_advisory_report,
            output_path="/tmp/advisory_report.pdf",
            watermark="DRAFT",  # or None for final version
        )
    """
    exporter = AdvisoryPDFExporter(watermark=watermark)
    return exporter.generate_pdf(report, output_path, include_charts)
