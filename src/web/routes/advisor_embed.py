"""
Embeddable AI Tax Advisor — auth-free, frameable, no sidebar.

Serves the full conversational advisor as an embeddable widget
for external sites like mayankwadhera.com.

Usage on external site:
  <iframe src="https://yourdomain.com/advisor-embed" ...></iframe>

  With CPA branding:
  <iframe src="https://yourdomain.com/advisor-embed?cpa=mayank" ...></iframe>
"""

import os
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Advisor Embed"])
templates = Jinja2Templates(directory="web/templates")

# Domains allowed to frame the embed (configurable via env)
_ALLOWED_FRAME_ANCESTORS = os.environ.get(
    "EMBED_ALLOWED_ORIGINS",
    "https://mayankwadhera.com https://www.mayankwadhera.com"
)


@router.get("/advisor-embed", response_class=HTMLResponse, include_in_schema=False)
async def advisor_embed(request: Request, cpa: str = None, theme: str = None):
    """
    Serve the full AI tax advisor in embed mode.

    No authentication required. No sidebar. Frameable by allowed origins.

    Query params:
        cpa: CPA slug for white-label branding (colors, logo, firm name)
        theme: 'light' or 'dark' (default: light)
    """
    context = {
        "request": request,
        "embed_mode": True,
        "theme": theme or "light",
        "cpa_branding": None,
    }

    # Load CPA branding if slug provided
    if cpa:
        try:
            from database.tenant_persistence import get_tenant_persistence
            persistence = get_tenant_persistence()
            branding = persistence.get_cpa_branding(cpa)
            if branding:
                context["cpa_branding"] = branding
                logger.info(f"Embed loaded with CPA branding: {cpa}")
        except Exception as e:
            logger.debug(f"CPA branding lookup failed for '{cpa}': {e}")

    response = templates.TemplateResponse("advisor_embed.html", context)

    # Override security headers to allow framing from configured origins
    response.headers["Content-Security-Policy"] = (
        f"frame-ancestors 'self' {_ALLOWED_FRAME_ANCESTORS}; "
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "img-src 'self' data: blob: https:; "
        "media-src 'self' blob:; "
        "object-src 'none'; "
        "base-uri 'self';"
    )
    # Remove X-Frame-Options entirely (CSP frame-ancestors supersedes it)
    if "X-Frame-Options" in response.headers:
        del response.headers["X-Frame-Options"]
    response.headers["X-Frame-Options"] = "ALLOW-FROM " + _ALLOWED_FRAME_ANCESTORS.split()[0]

    return response
