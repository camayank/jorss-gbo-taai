"""
HTML Exporter - Export reports to HTML format.

Generates complete, standalone HTML documents suitable for:
- Browser viewing
- Email embedding
- PDF conversion
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING
from pathlib import Path
import logging
import html

if TYPE_CHECKING:
    from universal_report.section_renderer import RenderedSection
    from universal_report.data_collector import NormalizedReportData
    from universal_report.branding.theme_manager import BrandTheme

logger = logging.getLogger(__name__)


class HTMLExporter:
    """
    Export reports to complete HTML documents.

    Features:
    - Standalone HTML with embedded CSS
    - Print-ready styling
    - Responsive design
    - SVG chart preservation
    """

    def __init__(self, theme: Optional["BrandTheme"] = None):
        self.theme = theme

    def export(
        self,
        sections: List["RenderedSection"],
        data: "NormalizedReportData",
        output_path: Optional[str] = None,
        include_print_styles: bool = True,
    ) -> str:
        """
        Export sections to HTML document.

        Args:
            sections: List of rendered sections
            data: Normalized report data
            output_path: Optional file path to save HTML
            include_print_styles: Include print-optimized CSS

        Returns:
            Complete HTML document string
        """
        from universal_report.branding.theme_manager import ThemeManager
        from universal_report.branding.logo_handler import LogoHandler

        theme_manager = ThemeManager()
        theme = self.theme or theme_manager.get_preset("default")

        # Generate CSS
        css = theme_manager.generate_full_css(theme)

        # Print styles
        print_css = ""
        if include_print_styles:
            print_css = self._get_print_styles()

        # Build sections HTML
        sections_html = self._build_sections_html(sections)

        # Footer
        logo_handler = LogoHandler(theme)
        footer_html = logo_handler.render_footer_with_logo()

        # Watermark
        watermark_html = ""
        if theme.show_watermark and theme.watermark_text:
            watermark_html = logo_handler.render_watermark(text=theme.watermark_text)

        # Build document
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="generator" content="Universal Report Engine">
  <title>{html.escape(theme.report_title)} - {html.escape(data.taxpayer_name)}</title>
  <style>
{css}
{print_css}

.report-container {{
  max-width: 900px;
  margin: 0 auto;
  padding: 40px;
  background: white;
  min-height: 100vh;
}}

.report-section {{
  margin-bottom: 40px;
}}

/* SVG charts responsive */
svg {{
  max-width: 100%;
  height: auto;
}}

/* Animation for gauges */
@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(20px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.report-section {{
  animation: fadeIn 0.5s ease-out forwards;
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

        # Save to file if path provided
        if output_path:
            self._save_to_file(html, output_path)

        return html

    def export_for_email(
        self,
        sections: List["RenderedSection"],
        data: "NormalizedReportData",
    ) -> str:
        """
        Export sections to email-compatible HTML.

        Email HTML requires:
        - Inline styles (no external CSS)
        - Table-based layout for compatibility
        - No JavaScript

        Args:
            sections: List of rendered sections
            data: Normalized report data

        Returns:
            Email-compatible HTML string
        """
        from universal_report.branding.theme_manager import ThemeManager

        theme_manager = ThemeManager()
        theme = self.theme or theme_manager.get_preset("default")

        # Build sections with inline styles
        sections_html = self._build_sections_html(sections, inline_styles=True)

        # Simple email-safe wrapper
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{theme.report_title}</title>
</head>
<body style="
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: #1f2937;
  background-color: #f9fafb;
">
  <table role="presentation" style="
    width: 100%;
    max-width: 600px;
    margin: 0 auto;
    background-color: white;
    border-collapse: collapse;
  ">
    <tr>
      <td style="padding: 40px;">
        {sections_html}

        <div style="
          margin-top: 40px;
          padding-top: 20px;
          border-top: 1px solid #e5e7eb;
          text-align: center;
          font-size: 12px;
          color: #6b7280;
        ">
          <p style="margin: 0 0 8px 0;">
            {theme.firm_name}
          </p>
          <p style="margin: 0; font-style: italic;">
            This report is for informational purposes only and does not constitute tax advice.
          </p>
        </div>
      </td>
    </tr>
  </table>
</body>
</html>
'''

    def _build_sections_html(
        self,
        sections: List["RenderedSection"],
        inline_styles: bool = False,
    ) -> str:
        """Build combined HTML from sections."""
        sections_html = ""

        for section in sorted(sections, key=lambda s: s.order):
            # Page break styles
            style_parts = []
            if section.page_break_before:
                style_parts.append("page-break-before: always;")
            if section.page_break_after:
                style_parts.append("page-break-after: always;")

            style_attr = f'style="{" ".join(style_parts)}"' if style_parts else ""

            sections_html += f'''
<div class="report-section" id="{section.section_id}" {style_attr}>
  {section.content}
</div>
'''

        return sections_html

    def _get_print_styles(self) -> str:
        """Get print-optimized CSS."""
        return '''
@media print {
  body {
    margin: 0;
    padding: 0;
  }

  .report-container {
    max-width: 100%;
    padding: 0.5in;
    margin: 0;
  }

  .no-print {
    display: none !important;
  }

  .page-break {
    page-break-before: always;
  }

  /* Ensure charts don't break across pages */
  svg {
    page-break-inside: avoid;
  }

  .card, .recommendation-card, .metric-card {
    page-break-inside: avoid;
    box-shadow: none !important;
    border: 1px solid #ddd !important;
  }

  /* Headers at top of pages */
  h2, h3 {
    page-break-after: avoid;
  }

  /* Tables */
  table {
    page-break-inside: auto;
  }

  tr {
    page-break-inside: avoid;
  }

  thead {
    display: table-header-group;
  }

  /* Links */
  a {
    text-decoration: none;
    color: inherit;
  }

  /* Hide interactive elements */
  button, .interactive {
    display: none !important;
  }
}

@page {
  margin: 0.75in;
  size: letter;
}

@page :first {
  margin-top: 0.5in;
}
'''

    def _save_to_file(self, html: str, output_path: str) -> None:
        """Save HTML to file."""
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding='utf-8')
            logger.info(f"HTML report saved to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save HTML: {e}")
            raise
