#!/usr/bin/env python3
"""Generate a one-page sales sheet PDF for TaxPro Enterprise."""

from fpdf import FPDF


class SalesSheetPDF(FPDF):
    """Custom PDF class for sales sheet generation."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=False)

    def header_section(self):
        """Create the header with branding."""
        # Blue header bar
        self.set_fill_color(25, 55, 95)  # Dark blue
        self.rect(0, 0, 210, 45, 'F')

        # Company name
        self.set_font('Helvetica', 'B', 28)
        self.set_text_color(255, 255, 255)
        self.set_xy(15, 12)
        self.cell(0, 10, 'TaxPro Enterprise')

        # Tagline
        self.set_font('Helvetica', '', 14)
        self.set_xy(15, 26)
        self.cell(0, 8, 'AI-Powered Tax Preparation for Professional Accountants')

    def value_prop_section(self):
        """Main value proposition."""
        self.set_xy(15, 52)
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(25, 55, 95)
        self.cell(0, 10, 'Transform Your Practice. Maximize Client Value.')

        self.set_xy(15, 64)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(60, 60, 60)
        self.multi_cell(180, 5,
            'TaxPro Enterprise empowers CPAs to handle complex tax scenarios with enterprise-grade '
            'automation. Deliver premium advisory services, increase capacity by 50%, and command '
            'higher fees - all while reducing errors and compliance risk.')

    def stats_section(self):
        """Key statistics boxes."""
        y_start = 82
        box_width = 42
        box_height = 28
        spacing = 4

        stats = [
            ('25+', 'IRS Forms\nSupported'),
            ('50', 'States + DC\nCovered'),
            ('1,557', 'Automated\nTests'),
            ('80%', 'Time\nSaved'),
        ]

        x = 15
        for value, label in stats:
            # Box background
            self.set_fill_color(240, 245, 250)
            self.rect(x, y_start, box_width, box_height, 'F')

            # Border
            self.set_draw_color(25, 55, 95)
            self.rect(x, y_start, box_width, box_height, 'D')

            # Value
            self.set_font('Helvetica', 'B', 20)
            self.set_text_color(25, 55, 95)
            self.set_xy(x, y_start + 3)
            self.cell(box_width, 10, value, align='C')

            # Label
            self.set_font('Helvetica', '', 8)
            self.set_text_color(80, 80, 80)
            self.set_xy(x, y_start + 14)
            self.multi_cell(box_width, 4, label, align='C')

            x += box_width + spacing

    def features_section(self):
        """Two-column feature list."""
        y_start = 118

        # Section header
        self.set_xy(15, y_start)
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(25, 55, 95)
        self.cell(0, 8, 'COMPREHENSIVE CAPABILITIES')

        # Divider line
        self.set_draw_color(25, 55, 95)
        self.line(15, y_start + 9, 195, y_start + 9)

        left_features = [
            'Schedule A-H (All Major Schedules)',
            'Form 6251 (Alternative Minimum Tax)',
            'Form 8995 (QBI Deduction - Sec. 199A)',
            'Form 1116 (Foreign Tax Credit)',
            'Form 2210 (Estimated Tax Penalty)',
            'Form 8582 (Passive Activity Loss)',
            'Form 4797 (Business Property Sales)',
        ]

        right_features = [
            'All 50 States + DC Tax Calculators',
            'AI-Powered Data Collection',
            'Real-Time Scenario Modeling',
            'Professional Software Export',
            'Complete Audit Trail',
            'Multi-Year Carryforward Tracking',
            'IRS MeF XML Generation',
        ]

        self.set_font('Helvetica', '', 9)
        self.set_text_color(50, 50, 50)

        y = y_start + 14
        for i, (left, right) in enumerate(zip(left_features, right_features)):
            self.set_xy(15, y + (i * 7))
            self.set_font('Helvetica', 'B', 9)
            self.set_text_color(25, 55, 95)
            self.cell(5, 6, '>')
            self.set_font('Helvetica', '', 9)
            self.set_text_color(50, 50, 50)
            self.cell(80, 6, left)

            self.set_xy(105, y + (i * 7))
            self.set_font('Helvetica', 'B', 9)
            self.set_text_color(25, 55, 95)
            self.cell(5, 6, '>')
            self.set_font('Helvetica', '', 9)
            self.set_text_color(50, 50, 50)
            self.cell(80, 6, right)

    def tiers_section(self):
        """Service tiers pricing."""
        y_start = 175

        # Section header
        self.set_xy(15, y_start)
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(25, 55, 95)
        self.cell(0, 8, 'PREMIUM SERVICE TIERS')

        # Divider line
        self.line(15, y_start + 9, 195, y_start + 9)

        tiers = [
            ('Elite Tax Advisory', 'HNW, Executives, Business Owners', '$2,500 - $15,000+',
             'Multi-state optimization, AMT planning, QBI strategy'),
            ('Business Owner Suite', 'Self-Employed, SMBs, Contractors', '$1,500 - $5,000',
             'S-Corp analysis, SE tax minimization, Planning'),
            ('Investment & Retirement', 'Investors, Retirees, Portfolios', '$1,000 - $4,000',
             'Roth conversions, RMD, Loss harvesting'),
        ]

        y = y_start + 14
        col_widths = [50, 55, 40, 45]

        # Header row
        self.set_font('Helvetica', 'B', 8)
        self.set_fill_color(25, 55, 95)
        self.set_text_color(255, 255, 255)
        self.set_xy(15, y)
        headers = ['SERVICE TIER', 'TARGET CLIENT', 'PRICE RANGE', 'KEY FEATURES']
        x = 15
        for header, width in zip(headers, col_widths):
            self.set_xy(x, y)
            self.cell(width, 7, header, fill=True, align='C')
            x += width

        # Data rows
        self.set_font('Helvetica', '', 8)
        self.set_text_color(50, 50, 50)
        y += 8

        for i, (tier, target, price, features) in enumerate(tiers):
            if i % 2 == 0:
                self.set_fill_color(248, 250, 252)
            else:
                self.set_fill_color(255, 255, 255)

            x = 15
            self.set_xy(x, y)
            self.set_font('Helvetica', 'B', 8)
            self.set_text_color(50, 50, 50)
            self.cell(col_widths[0], 10, tier, fill=True)
            x += col_widths[0]

            self.set_font('Helvetica', '', 8)
            self.set_xy(x, y)
            self.cell(col_widths[1], 10, target, fill=True)
            x += col_widths[1]

            self.set_font('Helvetica', 'B', 8)
            self.set_text_color(25, 120, 80)
            self.set_xy(x, y)
            self.cell(col_widths[2], 10, price, fill=True, align='C')
            x += col_widths[2]

            self.set_font('Helvetica', '', 7)
            self.set_text_color(50, 50, 50)
            self.set_xy(x, y)
            self.cell(col_widths[3], 10, features, fill=True)

            y += 10

    def roi_section(self):
        """ROI highlight box."""
        y_start = 218

        # Green accent box
        self.set_fill_color(232, 245, 233)
        self.set_draw_color(25, 120, 80)
        self.rect(15, y_start, 85, 38, 'DF')

        self.set_xy(18, y_start + 3)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(25, 90, 60)
        self.cell(0, 6, 'FIRST-YEAR ROI')

        self.set_xy(18, y_start + 12)
        self.set_font('Helvetica', 'B', 24)
        self.set_text_color(25, 120, 80)
        self.cell(0, 10, '$326,250')

        self.set_xy(18, y_start + 26)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(60, 60, 60)
        self.cell(0, 5, 'Net benefit for 5-person firm')
        self.set_xy(18, y_start + 32)
        self.cell(0, 5, '(Additional revenue + cost savings)')

        # Benefits list
        self.set_xy(110, y_start)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(25, 55, 95)
        self.cell(0, 6, 'WHY CPAS CHOOSE US')

        benefits = [
            '+ 50% more returns with same staff',
            '+ Premium pricing justified by capabilities',
            '+ Complex returns handled in-house',
            '+ Year-round planning revenue',
            '+ Reduced E&O exposure',
        ]

        self.set_font('Helvetica', '', 8)
        self.set_text_color(50, 50, 50)
        y = y_start + 9
        for benefit in benefits:
            self.set_xy(110, y)
            self.cell(0, 5.5, benefit)
            y += 5.5

    def cta_section(self):
        """Call to action footer."""
        y_start = 262

        # Blue footer bar
        self.set_fill_color(25, 55, 95)
        self.rect(0, y_start, 210, 35, 'F')

        # CTA text
        self.set_xy(15, y_start + 5)
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, 'Ready to Transform Your Practice?')

        self.set_xy(15, y_start + 15)
        self.set_font('Helvetica', '', 10)
        self.cell(0, 6, 'Schedule a demo today and see how TaxPro Enterprise can help you')
        self.set_xy(15, y_start + 22)
        self.cell(0, 6, 'deliver more value to clients while growing your practice.')

        # Contact info (right side)
        self.set_xy(145, y_start + 8)
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 7, 'www.taxpro-enterprise.com')

        self.set_xy(145, y_start + 17)
        self.set_font('Helvetica', '', 9)
        self.cell(0, 6, 'contact@taxpro-enterprise.com')


def generate_sales_sheet():
    """Generate the sales sheet PDF."""
    pdf = SalesSheetPDF()
    pdf.add_page()

    # Build each section
    pdf.header_section()
    pdf.value_prop_section()
    pdf.stats_section()
    pdf.features_section()
    pdf.tiers_section()
    pdf.roi_section()
    pdf.cta_section()

    # Save
    output_path = 'docs/TaxPro_Enterprise_Sales_Sheet.pdf'
    pdf.output(output_path)
    print(f"Sales sheet generated: {output_path}")
    return output_path


if __name__ == '__main__':
    generate_sales_sheet()
