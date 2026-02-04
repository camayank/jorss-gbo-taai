"""
Theme Manager - Manage and apply branding themes for reports.

Supports white-label customization for CPA firms:
- Custom colors
- Logo placement
- Firm contact information
- Advisor details
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import re


@dataclass
class BrandTheme:
    """
    CPA/Firm branding configuration.

    This dataclass defines all customizable branding elements
    for white-label report generation.
    """
    # Colors
    primary_color: str = "#1e3a5f"      # Main accent (buttons, headers)
    secondary_color: str = "#152b47"    # Secondary accent
    accent_color: str = "#10b981"       # Success/savings (green)
    warning_color: str = "#f59e0b"      # Warnings (amber)
    danger_color: str = "#ef4444"       # Risks/alerts (red)
    background_color: str = "#ffffff"   # Page background
    text_color: str = "#1f2937"         # Primary text
    muted_color: str = "#6b7280"        # Secondary text

    # Logo
    logo_url: Optional[str] = None
    logo_width: int = 200
    logo_height: Optional[int] = None  # Auto if None
    logo_position: str = "header"  # 'header', 'footer', 'watermark'
    logo_alignment: str = "left"   # 'left', 'center', 'right'

    # Typography
    heading_font: str = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    body_font: str = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    mono_font: str = "'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace"
    base_font_size: int = 14

    # Firm info
    firm_name: str = "Tax Advisory"
    firm_tagline: Optional[str] = None
    firm_address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website_url: Optional[str] = None

    # Advisor info
    advisor_name: Optional[str] = None
    advisor_title: Optional[str] = None
    advisor_credentials: List[str] = field(default_factory=list)
    advisor_photo_url: Optional[str] = None
    advisor_email: Optional[str] = None
    advisor_phone: Optional[str] = None

    # Report styling
    report_title: str = "Tax Advisory Report"
    show_disclaimer: bool = True
    disclaimer_text: Optional[str] = None
    show_watermark: bool = False
    watermark_text: Optional[str] = None

    # Feature flags
    show_savings_gauge: bool = True
    show_charts: bool = True
    show_recommendations: bool = True
    show_scenarios: bool = True

    def to_css_variables(self) -> str:
        """Generate CSS custom properties from theme."""
        return f"""
:root {{
  --color-primary: {self.primary_color};
  --color-secondary: {self.secondary_color};
  --color-accent: {self.accent_color};
  --color-warning: {self.warning_color};
  --color-danger: {self.danger_color};
  --color-background: {self.background_color};
  --color-text: {self.text_color};
  --color-muted: {self.muted_color};

  --font-heading: {self.heading_font};
  --font-body: {self.body_font};
  --font-mono: {self.mono_font};
  --font-size-base: {self.base_font_size}px;

  --logo-width: {self.logo_width}px;
}}
"""


class ThemeManager:
    """
    Manage and apply branding themes.

    This class handles:
    - Theme creation from CPA profiles
    - CSS variable generation
    - Theme application to HTML templates
    """

    # Preset themes
    PRESETS = {
        "default": BrandTheme(),
        "corporate": BrandTheme(
            primary_color="#1e3a5f",
            secondary_color="#0c1b2f",
            accent_color="#059669",
            heading_font="'Roboto', Arial, sans-serif",
            body_font="'Roboto', Arial, sans-serif",
        ),
        "modern": BrandTheme(
            primary_color="#1e3a5f",
            secondary_color="#152b47",
            accent_color="#22c55e",
            heading_font="'Poppins', sans-serif",
            body_font="'Inter', sans-serif",
        ),
        "classic": BrandTheme(
            primary_color="#1f2937",
            secondary_color="#374151",
            accent_color="#059669",
            heading_font="'Georgia', serif",
            body_font="'Times New Roman', serif",
        ),
        "professional": BrandTheme(
            primary_color="#0f172a",
            secondary_color="#1e293b",
            accent_color="#0d9488",
            heading_font="'Merriweather', serif",
            body_font="'Source Sans Pro', sans-serif",
        ),
    }

    def __init__(self):
        self._default_theme = BrandTheme()

    def from_cpa_profile(self, cpa_profile: Optional[Dict[str, Any]]) -> BrandTheme:
        """
        Create BrandTheme from CPA profile dictionary.

        Args:
            cpa_profile: Dictionary with CPA/firm branding info

        Returns:
            BrandTheme configured from profile
        """
        if not cpa_profile:
            return BrandTheme()

        # Start with a preset if specified
        preset_name = cpa_profile.get("preset", "default")
        preset = self.PRESETS.get(preset_name, self.PRESETS["default"])

        # Build theme with overrides
        theme_kwargs = {}

        # Colors
        if "primary_color" in cpa_profile:
            theme_kwargs["primary_color"] = self._validate_color(
                cpa_profile["primary_color"], preset.primary_color
            )
        else:
            theme_kwargs["primary_color"] = preset.primary_color

        if "secondary_color" in cpa_profile:
            theme_kwargs["secondary_color"] = self._validate_color(
                cpa_profile["secondary_color"], preset.secondary_color
            )
        else:
            theme_kwargs["secondary_color"] = preset.secondary_color

        if "accent_color" in cpa_profile:
            theme_kwargs["accent_color"] = self._validate_color(
                cpa_profile["accent_color"], preset.accent_color
            )
        else:
            theme_kwargs["accent_color"] = preset.accent_color

        # Logo
        theme_kwargs["logo_url"] = cpa_profile.get("logo_url")
        theme_kwargs["logo_width"] = cpa_profile.get("logo_width", 200)
        theme_kwargs["logo_position"] = cpa_profile.get("logo_position", "header")
        theme_kwargs["logo_alignment"] = cpa_profile.get("logo_alignment", "left")

        # Fonts
        if "heading_font" in cpa_profile:
            theme_kwargs["heading_font"] = cpa_profile["heading_font"]
        else:
            theme_kwargs["heading_font"] = preset.heading_font

        if "body_font" in cpa_profile:
            theme_kwargs["body_font"] = cpa_profile["body_font"]
        else:
            theme_kwargs["body_font"] = preset.body_font

        # Firm info
        theme_kwargs["firm_name"] = cpa_profile.get("firm_name", "Tax Advisory")
        theme_kwargs["firm_tagline"] = cpa_profile.get("firm_tagline")
        theme_kwargs["firm_address"] = cpa_profile.get("firm_address")
        theme_kwargs["contact_email"] = cpa_profile.get("contact_email") or cpa_profile.get("email")
        theme_kwargs["contact_phone"] = cpa_profile.get("contact_phone") or cpa_profile.get("phone")
        theme_kwargs["website_url"] = cpa_profile.get("website_url") or cpa_profile.get("website")

        # Advisor info
        theme_kwargs["advisor_name"] = cpa_profile.get("advisor_name") or cpa_profile.get("name")
        theme_kwargs["advisor_title"] = cpa_profile.get("advisor_title") or cpa_profile.get("title")
        theme_kwargs["advisor_credentials"] = cpa_profile.get("credentials", [])
        theme_kwargs["advisor_photo_url"] = cpa_profile.get("advisor_photo_url") or cpa_profile.get("photo_url")
        theme_kwargs["advisor_email"] = cpa_profile.get("advisor_email")
        theme_kwargs["advisor_phone"] = cpa_profile.get("advisor_phone")

        # Report settings
        theme_kwargs["report_title"] = cpa_profile.get("report_title", "Tax Advisory Report")
        theme_kwargs["show_disclaimer"] = cpa_profile.get("show_disclaimer", True)
        theme_kwargs["disclaimer_text"] = cpa_profile.get("disclaimer_text")
        theme_kwargs["show_watermark"] = cpa_profile.get("show_watermark", False)
        theme_kwargs["watermark_text"] = cpa_profile.get("watermark_text")

        # Feature flags
        theme_kwargs["show_savings_gauge"] = cpa_profile.get("show_savings_gauge", True)
        theme_kwargs["show_charts"] = cpa_profile.get("show_charts", True)
        theme_kwargs["show_recommendations"] = cpa_profile.get("show_recommendations", True)
        theme_kwargs["show_scenarios"] = cpa_profile.get("show_scenarios", True)

        return BrandTheme(**theme_kwargs)

    def get_preset(self, name: str) -> BrandTheme:
        """Get a preset theme by name."""
        return self.PRESETS.get(name, self.PRESETS["default"])

    def generate_css_variables(self, theme: BrandTheme) -> str:
        """
        Generate CSS custom properties from theme.

        Args:
            theme: BrandTheme to convert

        Returns:
            CSS string with custom properties
        """
        return theme.to_css_variables()

    def generate_full_css(self, theme: BrandTheme) -> str:
        """
        Generate complete CSS stylesheet with theme applied.

        Args:
            theme: BrandTheme to apply

        Returns:
            Complete CSS stylesheet string
        """
        css_vars = theme.to_css_variables()

        return f"""
{css_vars}

/* Base styles */
* {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

body {{
  font-family: var(--font-body);
  font-size: var(--font-size-base);
  color: var(--color-text);
  background-color: var(--color-background);
  line-height: 1.6;
}}

/* Typography */
h1, h2, h3, h4, h5, h6 {{
  font-family: var(--font-heading);
  font-weight: 700;
  line-height: 1.3;
  color: var(--color-text);
}}

h1 {{
  font-size: 2.25rem;
  margin-bottom: 1rem;
}}

h2 {{
  font-size: 1.75rem;
  margin-bottom: 0.875rem;
  color: var(--color-primary);
}}

h3 {{
  font-size: 1.375rem;
  margin-bottom: 0.75rem;
}}

p {{
  margin-bottom: 1rem;
}}

a {{
  color: var(--color-primary);
  text-decoration: none;
}}

a:hover {{
  text-decoration: underline;
}}

/* Report specific styles */
.report-container {{
  max-width: 900px;
  margin: 0 auto;
  padding: 40px;
}}

.report-header {{
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 20px;
  margin-bottom: 30px;
}}

.report-logo {{
  max-width: var(--logo-width);
  height: auto;
}}

.report-title {{
  color: var(--color-primary);
  margin-top: 20px;
}}

.section {{
  margin-bottom: 40px;
  page-break-inside: avoid;
}}

.section-title {{
  color: var(--color-primary);
  border-bottom: 1px solid var(--color-primary);
  padding-bottom: 8px;
  margin-bottom: 20px;
}}

/* Cards */
.card {{
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}

.card-header {{
  font-weight: 600;
  font-size: 1.125rem;
  margin-bottom: 12px;
}}

/* Tables */
.data-table {{
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
}}

.data-table th {{
  background: var(--color-primary);
  color: white;
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
}}

.data-table td {{
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}}

.data-table tr:nth-child(even) {{
  background: #f9fafb;
}}

/* Utility classes */
.text-primary {{ color: var(--color-primary); }}
.text-accent {{ color: var(--color-accent); }}
.text-warning {{ color: var(--color-warning); }}
.text-danger {{ color: var(--color-danger); }}
.text-muted {{ color: var(--color-muted); }}

.bg-primary {{ background-color: var(--color-primary); }}
.bg-accent {{ background-color: var(--color-accent); }}

.font-bold {{ font-weight: 700; }}
.font-semibold {{ font-weight: 600; }}

.text-center {{ text-align: center; }}
.text-right {{ text-align: right; }}

.mt-1 {{ margin-top: 0.25rem; }}
.mt-2 {{ margin-top: 0.5rem; }}
.mt-4 {{ margin-top: 1rem; }}
.mb-1 {{ margin-bottom: 0.25rem; }}
.mb-2 {{ margin-bottom: 0.5rem; }}
.mb-4 {{ margin-bottom: 1rem; }}

/* Print styles */
@media print {{
  .report-container {{
    padding: 20px;
  }}

  .no-print {{
    display: none !important;
  }}

  .page-break {{
    page-break-before: always;
  }}

  .card {{
    box-shadow: none;
    border: 1px solid #ddd;
  }}
}}
"""

    def apply_to_html(self, html: str, theme: BrandTheme) -> str:
        """
        Apply theme to HTML content.

        Replaces template variables with themed values.

        Args:
            html: HTML content with template variables
            theme: BrandTheme to apply

        Returns:
            HTML with theme applied
        """
        # Replace CSS variables
        css = self.generate_full_css(theme)

        # Template variable replacements
        replacements = {
            "{{PRIMARY_COLOR}}": theme.primary_color,
            "{{SECONDARY_COLOR}}": theme.secondary_color,
            "{{ACCENT_COLOR}}": theme.accent_color,
            "{{WARNING_COLOR}}": theme.warning_color,
            "{{DANGER_COLOR}}": theme.danger_color,
            "{{FIRM_NAME}}": theme.firm_name,
            "{{REPORT_TITLE}}": theme.report_title,
            "{{ADVISOR_NAME}}": theme.advisor_name or "",
            "{{ADVISOR_TITLE}}": theme.advisor_title or "",
            "{{CONTACT_EMAIL}}": theme.contact_email or "",
            "{{CONTACT_PHONE}}": theme.contact_phone or "",
            "{{THEME_CSS}}": css,
        }

        result = html
        for key, value in replacements.items():
            result = result.replace(key, value)

        return result

    def _validate_color(self, color: str, default: str) -> str:
        """Validate hex color and return default if invalid."""
        if not color:
            return default

        # Check if valid hex color
        hex_pattern = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
        if re.match(hex_pattern, color):
            return color

        return default
