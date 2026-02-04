"""
Logo Handler - Handle logo placement and sizing for reports.

Supports:
- Header logo placement
- Footer logo placement
- Watermark overlays
- Multiple image formats
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING
import base64
import os
from pathlib import Path
import logging

if TYPE_CHECKING:
    from universal_report.branding.theme_manager import BrandTheme

logger = logging.getLogger(__name__)


class LogoHandler:
    """
    Handle logo placement and rendering in reports.

    Features:
    - URL and file-based logos
    - Base64 encoding for PDF embedding
    - Responsive sizing
    - Position configuration
    """

    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.svg', '.gif', '.webp'}

    def __init__(self, theme: Optional["BrandTheme"] = None):
        self.theme = theme
        self._cached_logos: dict[str, str] = {}

    def render_logo_html(
        self,
        logo_url: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        position: str = "header",
        alignment: str = "left",
        alt_text: str = "Company Logo",
    ) -> str:
        """
        Render logo as HTML img element.

        Args:
            logo_url: URL or path to logo image
            width: Logo width in pixels
            height: Logo height in pixels (auto if None)
            position: Position context ('header', 'footer', 'watermark')
            alignment: Horizontal alignment ('left', 'center', 'right')
            alt_text: Alt text for the image

        Returns:
            HTML string for logo display
        """
        # Use theme values as defaults
        if self.theme:
            logo_url = logo_url or self.theme.logo_url
            width = width or self.theme.logo_width
            height = height or self.theme.logo_height
            position = position or self.theme.logo_position
            alignment = alignment or self.theme.logo_alignment

        if not logo_url:
            return ""

        # Determine alignment style
        align_styles = {
            "left": "text-align: left;",
            "center": "text-align: center;",
            "right": "text-align: right;",
        }
        container_style = align_styles.get(alignment, "text-align: left;")

        # Build size style
        size_style = ""
        if width:
            size_style += f"max-width: {width}px; "
        if height:
            size_style += f"max-height: {height}px; "
        size_style += "height: auto; width: auto;"

        # Position-specific styling
        position_classes = {
            "header": "report-logo-header",
            "footer": "report-logo-footer",
            "watermark": "report-logo-watermark",
        }
        position_class = position_classes.get(position, "report-logo-header")

        return f'''
<div class="{position_class}" style="{container_style} margin-bottom: 16px;">
  <img src="{logo_url}" alt="{alt_text}" class="report-logo"
       style="{size_style}" />
</div>
'''

    def render_header_with_logo(
        self,
        logo_url: Optional[str] = None,
        firm_name: Optional[str] = None,
        tagline: Optional[str] = None,
        contact_info: Optional[dict] = None,
    ) -> str:
        """
        Render complete header with logo and firm info.

        Args:
            logo_url: Logo URL or path
            firm_name: Firm name to display
            tagline: Optional firm tagline
            contact_info: Dict with email, phone, website

        Returns:
            HTML string for complete header
        """
        # Use theme values
        if self.theme:
            logo_url = logo_url or self.theme.logo_url
            firm_name = firm_name or self.theme.firm_name
            tagline = tagline or self.theme.firm_tagline
            contact_info = contact_info or {
                "email": self.theme.contact_email,
                "phone": self.theme.contact_phone,
                "website": self.theme.website_url,
            }

        primary_color = self.theme.primary_color if self.theme else "#1e3a5f"
        muted_color = self.theme.muted_color if self.theme else "#6b7280"

        # Logo HTML
        logo_html = ""
        if logo_url:
            width = self.theme.logo_width if self.theme else 200
            logo_html = f'''
    <img src="{logo_url}" alt="{firm_name or 'Logo'}" class="report-logo"
         style="max-width: {width}px; height: auto;" />
'''

        # Firm name and tagline
        name_html = ""
        if firm_name:
            name_html = f'''
    <h1 style="font-size: 1.5rem; color: {primary_color}; margin: 0;">{firm_name}</h1>
'''
            if tagline:
                name_html += f'''
    <p style="font-size: 0.875rem; color: {muted_color}; margin: 4px 0 0 0;">{tagline}</p>
'''

        # Contact info
        contact_html = ""
        if contact_info:
            contact_parts = []
            if contact_info.get("email"):
                contact_parts.append(contact_info["email"])
            if contact_info.get("phone"):
                contact_parts.append(contact_info["phone"])
            if contact_info.get("website"):
                contact_parts.append(contact_info["website"])

            if contact_parts:
                contact_html = f'''
    <div style="font-size: 0.75rem; color: {muted_color}; margin-top: 8px;">
      {" | ".join(contact_parts)}
    </div>
'''

        return f'''
<header class="report-header" style="
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 20px;
  border-bottom: 2px solid {primary_color};
  margin-bottom: 30px;
">
  <div class="header-branding">
    {logo_html}
    {name_html}
    {contact_html}
  </div>
</header>
'''

    def render_footer_with_logo(
        self,
        logo_url: Optional[str] = None,
        firm_name: Optional[str] = None,
        disclaimer: Optional[str] = None,
        show_page_number: bool = True,
    ) -> str:
        """
        Render complete footer with optional logo and disclaimer.

        Args:
            logo_url: Logo URL or path
            firm_name: Firm name
            disclaimer: Disclaimer text
            show_page_number: Whether to show page numbers

        Returns:
            HTML string for complete footer
        """
        if self.theme:
            logo_url = logo_url or (self.theme.logo_url if self.theme.logo_position == "footer" else None)
            firm_name = firm_name or self.theme.firm_name
            disclaimer = disclaimer or self.theme.disclaimer_text

        muted_color = self.theme.muted_color if self.theme else "#6b7280"
        border_color = "#e5e7eb"

        logo_html = ""
        if logo_url:
            logo_html = f'''
    <img src="{logo_url}" alt="{firm_name or 'Logo'}" style="max-width: 100px; height: auto; opacity: 0.7;" />
'''

        disclaimer_html = ""
        if disclaimer:
            disclaimer_html = f'''
    <p style="font-size: 0.7rem; color: {muted_color}; margin: 8px 0; max-width: 600px;">
      {disclaimer}
    </p>
'''
        else:
            # Default disclaimer
            disclaimer_html = f'''
    <p style="font-size: 0.7rem; color: {muted_color}; margin: 8px 0; max-width: 600px;">
      This report is for informational purposes only and does not constitute tax advice.
      Consult with a licensed tax professional before making tax decisions.
    </p>
'''

        page_number_html = ""
        if show_page_number:
            page_number_html = '''
    <div class="page-number" style="font-size: 0.75rem; color: #9ca3af;">
      Page <span class="page"></span>
    </div>
'''

        return f'''
<footer class="report-footer" style="
  padding-top: 20px;
  border-top: 1px solid {border_color};
  margin-top: 40px;
  text-align: center;
">
  {logo_html}
  <div style="font-size: 0.875rem; color: {muted_color}; margin-top: 8px;">
    {firm_name or "Tax Advisory Services"}
  </div>
  {disclaimer_html}
  {page_number_html}
</footer>
'''

    def render_watermark(
        self,
        text: Optional[str] = None,
        logo_url: Optional[str] = None,
        opacity: float = 0.1,
    ) -> str:
        """
        Render watermark overlay (text or logo).

        Args:
            text: Watermark text (e.g., "DRAFT", "CONFIDENTIAL")
            logo_url: Logo URL for logo watermark
            opacity: Watermark opacity (0-1)

        Returns:
            HTML/CSS for watermark overlay
        """
        if self.theme:
            if self.theme.show_watermark:
                text = text or self.theme.watermark_text
            logo_url = logo_url or (self.theme.logo_url if self.theme.logo_position == "watermark" else None)

        if text:
            return f'''
<div class="watermark" style="
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-45deg);
  font-size: 120px;
  font-weight: bold;
  color: rgba(0, 0, 0, {opacity});
  pointer-events: none;
  z-index: -1;
  white-space: nowrap;
">
  {text}
</div>
'''
        elif logo_url:
            return f'''
<div class="watermark" style="
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  opacity: {opacity};
  pointer-events: none;
  z-index: -1;
">
  <img src="{logo_url}" alt="Watermark" style="max-width: 400px; height: auto;" />
</div>
'''
        return ""

    def encode_logo_base64(self, logo_path: str) -> Optional[str]:
        """
        Encode a local logo file as base64 data URL.

        Args:
            logo_path: Path to logo file

        Returns:
            Base64 data URL or None if failed
        """
        if logo_path in self._cached_logos:
            return self._cached_logos[logo_path]

        try:
            path = Path(logo_path)
            if not path.exists():
                logger.warning(f"Logo file not found: {logo_path}")
                return None

            if path.suffix.lower() not in self.SUPPORTED_FORMATS:
                logger.warning(f"Unsupported logo format: {path.suffix}")
                return None

            # Determine MIME type
            mime_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.svg': 'image/svg+xml',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
            }
            mime_type = mime_types.get(path.suffix.lower(), 'image/png')

            # Read and encode
            with open(path, 'rb') as f:
                content = f.read()

            encoded = base64.b64encode(content).decode('utf-8')
            data_url = f"data:{mime_type};base64,{encoded}"

            # Cache the result
            self._cached_logos[logo_path] = data_url

            return data_url

        except Exception as e:
            logger.error(f"Error encoding logo: {e}")
            return None

    def get_logo_for_pdf(self, logo_url: Optional[str] = None) -> Optional[str]:
        """
        Get logo prepared for PDF embedding.

        For local files, encodes as base64.
        For URLs, returns the URL (PDF lib will fetch).

        Args:
            logo_url: Logo URL or local path

        Returns:
            URL or base64 data URL for PDF embedding
        """
        if not logo_url:
            if self.theme:
                logo_url = self.theme.logo_url

        if not logo_url:
            return None

        # Check if it's a local file
        if not logo_url.startswith(('http://', 'https://', 'data:')):
            # Try to encode as base64
            encoded = self.encode_logo_base64(logo_url)
            if encoded:
                return encoded

        return logo_url
