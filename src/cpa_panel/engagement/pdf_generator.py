"""
Engagement Letter PDF Generator

Generates professional PDF engagement letters using ReportLab.
Supports CPA branding (logo, colors) and creates legally-formatted documents.
"""

from __future__ import annotations

import io
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
        PageBreak,
    )
    from reportlab.pdfgen import canvas
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

logger = logging.getLogger(__name__)


class EngagementLetterPDFGenerator:
    """Generates PDF engagement letters with CPA branding."""

    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab is required for PDF generation. Install with: pip install reportlab")

        self._styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        # Firm header style
        self._styles.add(ParagraphStyle(
            'FirmHeader',
            parent=self._styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=6,
        ))

        # Client address style
        self._styles.add(ParagraphStyle(
            'Address',
            parent=self._styles['Normal'],
            fontSize=10,
            leading=14,
            spaceAfter=12,
        ))

        # Section heading style
        self._styles.add(ParagraphStyle(
            'SectionHeading',
            parent=self._styles['Heading2'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceBefore=16,
            spaceAfter=8,
            textColor=colors.HexColor("#1e40af"),
        ))

        # Body text style
        self._styles.add(ParagraphStyle(
            'BodyText',
            parent=self._styles['Normal'],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=10,
        ))

        # Bullet style
        self._styles.add(ParagraphStyle(
            'Bullet',
            parent=self._styles['Normal'],
            fontSize=10,
            leading=14,
            leftIndent=20,
            spaceAfter=4,
        ))

        # Signature style
        self._styles.add(ParagraphStyle(
            'Signature',
            parent=self._styles['Normal'],
            fontSize=10,
            spaceBefore=24,
            spaceAfter=6,
        ))

        # Disclaimer style (small print)
        self._styles.add(ParagraphStyle(
            'Disclaimer',
            parent=self._styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.gray,
            alignment=TA_JUSTIFY,
            spaceBefore=24,
        ))

    def generate_pdf(
        self,
        letter_content: Dict[str, Any],
        branding: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Generate a PDF engagement letter.

        Args:
            letter_content: Letter data including:
                - letter_type: Type of engagement
                - cpa_firm_name: CPA firm name
                - cpa_name: CPA name
                - cpa_credentials: CPA credentials
                - firm_address: Firm address
                - client_name: Client name
                - client_address: Client address
                - tax_year: Tax year
                - complexity_tier: Complexity tier
                - services: List of services
                - fee_amount: Fee amount
                - fee_description: Fee description
                - generated_at: Generation date
            branding: Optional branding settings:
                - logo_url: Path to logo image
                - primary_color: Hex color code
                - secondary_color: Hex color code

        Returns:
            PDF bytes
        """
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build story (content elements)
        story = []

        # Primary color from branding
        primary_color = colors.HexColor(
            branding.get("primary_color", "#1e40af") if branding else "#1e40af"
        )

        # Firm Header
        story.append(Paragraph(
            letter_content.get("cpa_firm_name", "Tax Advisory Firm"),
            self._styles['FirmHeader']
        ))

        firm_address = letter_content.get("firm_address", "")
        if firm_address:
            story.append(Paragraph(firm_address.replace("\n", "<br/>"), self._styles['Address']))

        story.append(Spacer(1, 0.25 * inch))

        # Date
        gen_date = letter_content.get("generated_at", datetime.utcnow().strftime("%B %d, %Y"))
        if isinstance(gen_date, str) and "T" in gen_date:
            gen_date = datetime.fromisoformat(gen_date.replace("Z", "")).strftime("%B %d, %Y")
        story.append(Paragraph(str(gen_date), self._styles['BodyText']))

        story.append(Spacer(1, 0.25 * inch))

        # Client Info
        client_name = letter_content.get("client_name", "Client")
        client_address = letter_content.get("client_address", "")

        story.append(Paragraph(client_name, self._styles['Address']))
        if client_address:
            story.append(Paragraph(client_address.replace("\n", "<br/>"), self._styles['Address']))

        story.append(Spacer(1, 0.25 * inch))

        # Subject line
        tax_year = letter_content.get("tax_year", datetime.now().year)
        letter_type = letter_content.get("letter_type", "tax_preparation")
        type_display = {
            "tax_preparation": "Tax Preparation Services",
            "tax_advisory": "Tax Advisory Services",
            "tax_planning": "Tax Planning Services",
            "amended_return": "Amended Return Preparation",
        }.get(letter_type, "Tax Services")

        story.append(Paragraph(
            f"<b>RE: Engagement Letter for {tax_year} {type_display}</b>",
            self._styles['BodyText']
        ))

        story.append(Spacer(1, 0.25 * inch))

        # Greeting
        story.append(Paragraph(f"Dear {client_name}:", self._styles['BodyText']))

        # Opening paragraph
        story.append(Paragraph(
            f"This letter confirms the terms of our engagement to provide {type_display.lower()} "
            f"for your {tax_year} tax situation.",
            self._styles['BodyText']
        ))

        # Scope of Services
        story.append(Paragraph("SCOPE OF SERVICES", self._styles['SectionHeading']))

        complexity_tier = letter_content.get("complexity_tier", "Standard")
        story.append(Paragraph(
            f"This engagement is classified as <b>{complexity_tier}</b> complexity based on your tax situation. "
            f"Our services include:",
            self._styles['BodyText']
        ))

        services = letter_content.get("services", [])
        if isinstance(services, str):
            services = services.split("; ")

        for service in services:
            story.append(Paragraph(f"&bull; {service}", self._styles['Bullet']))

        # Client Responsibilities
        story.append(Paragraph("YOUR RESPONSIBILITIES", self._styles['SectionHeading']))
        story.append(Paragraph(
            "You are responsible for providing complete and accurate information necessary for "
            "the preparation of your tax returns. Specifically, you are responsible for:",
            self._styles['BodyText']
        ))

        responsibilities = [
            "Providing all relevant tax documents (W-2s, 1099s, K-1s, etc.)",
            "Responding promptly to our requests for additional information",
            "Reviewing and approving the completed returns before filing",
            "Maintaining adequate records to support the items reported on your returns",
        ]
        for resp in responsibilities:
            story.append(Paragraph(f"&bull; {resp}", self._styles['Bullet']))

        # Fees
        story.append(Paragraph("FEES", self._styles['SectionHeading']))

        fee_amount = letter_content.get("fee_amount", 0)
        fee_description = letter_content.get("fee_description", "")

        story.append(Paragraph(
            f"Our fee for the services described above is <b>${fee_amount:,.2f}</b>. "
            f"{fee_description or 'This fee is based on the complexity of your tax situation.'}",
            self._styles['BodyText']
        ))

        story.append(Paragraph(
            "Payment is due upon completion of the engagement. We reserve the right to suspend "
            "services if payment is not received.",
            self._styles['BodyText']
        ))

        # Limitations
        story.append(Paragraph("LIMITATIONS", self._styles['SectionHeading']))

        limitations = [
            "Audit, review, or compilation of financial statements",
            "Bookkeeping or accounting services",
            "Legal advice",
            "Investment or financial planning advice",
            "Representation before the IRS (unless separately engaged)",
        ]
        story.append(Paragraph("This engagement does not include:", self._styles['BodyText']))
        for limit in limitations:
            story.append(Paragraph(f"&bull; {limit}", self._styles['Bullet']))

        # Circular 230 Disclosure
        story.append(Paragraph("IRS CIRCULAR 230 DISCLOSURE", self._styles['SectionHeading']))
        story.append(Paragraph(
            "To ensure compliance with requirements imposed by the IRS, we inform you that any "
            "U.S. federal tax advice contained in this communication is not intended or written "
            "to be used, and cannot be used, for the purpose of (i) avoiding penalties under the "
            "Internal Revenue Code or (ii) promoting, marketing, or recommending to another party "
            "any transaction or matter addressed herein.",
            self._styles['Disclaimer']
        ))

        # Important Notice
        story.append(Paragraph(
            "<b>IMPORTANT:</b> This engagement is for tax preparation advisory services only. "
            "Tax returns prepared through this engagement must be filed through IRS-authorized "
            "e-file channels or paper filing. This is not an e-filing service.",
            self._styles['Disclaimer']
        ))

        # Agreement
        story.append(Paragraph("AGREEMENT", self._styles['SectionHeading']))
        story.append(Paragraph(
            "If you agree to the terms of this engagement, please sign below and return a copy "
            "to our office. Your signature indicates that you understand and agree to the terms "
            "described above.",
            self._styles['BodyText']
        ))

        story.append(Paragraph(
            "We appreciate the opportunity to serve you.",
            self._styles['BodyText']
        ))

        story.append(Spacer(1, 0.25 * inch))

        # CPA Signature
        story.append(Paragraph("Sincerely,", self._styles['Signature']))
        story.append(Spacer(1, 0.5 * inch))

        cpa_name = letter_content.get("cpa_name", "")
        cpa_credentials = letter_content.get("cpa_credentials", "")
        cpa_firm = letter_content.get("cpa_firm_name", "")

        story.append(Paragraph(f"<b>{cpa_name}, {cpa_credentials}</b>", self._styles['Signature']))
        story.append(Paragraph(cpa_firm, self._styles['Signature']))

        # Client Signature Block
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph("<b>ACCEPTED AND AGREED:</b>", self._styles['Signature']))
        story.append(Spacer(1, 0.5 * inch))

        # Signature line
        story.append(Paragraph("_" * 50, self._styles['Signature']))
        story.append(Paragraph(client_name, self._styles['Signature']))
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph("Date: _____________", self._styles['Signature']))

        # Build PDF
        doc.build(story)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"Generated PDF engagement letter for {client_name} ({len(pdf_bytes)} bytes)")

        return pdf_bytes


# Singleton instance
_pdf_generator: Optional[EngagementLetterPDFGenerator] = None


def get_pdf_generator() -> EngagementLetterPDFGenerator:
    """Get the PDF generator singleton."""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = EngagementLetterPDFGenerator()
    return _pdf_generator
