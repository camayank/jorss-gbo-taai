"""
CPA Panel Report Routes

API endpoints for generating comprehensive advisory reports
combining all optimization analyses into professional deliverables.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

report_router = APIRouter(tags=["Advisory Reports"])


def get_report_service():
    """Get the report service singleton."""
    from cpa_panel.services.advisory_report_service import get_report_service
    return get_report_service()


# =============================================================================
# REPORT GENERATION
# =============================================================================

@report_router.post("/session/{session_id}/report/generate")
async def generate_report(session_id: str, request: Request):
    """
    Generate a comprehensive advisory report.

    Request body (optional):
        - sections: List of section IDs to include (default: all)
        - include_scenarios: Whether to include scenario analysis (default: true)

    Returns complete report with:
        - Executive summary (AI-generated)
        - Tax overview and income breakdown
        - Credit analysis
        - Deduction optimization
        - Filing status comparison
        - Entity structure recommendation
        - Retirement planning
        - Investment strategy
        - Scenario comparisons
        - Action items with priorities
        - Professional disclaimer
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.debug(f"Failed to parse request body: {e}")
        body = {}

    sections = body.get("sections")
    include_scenarios = body.get("include_scenarios", True)

    try:
        service = get_report_service()
        result = service.generate_report(
            session_id,
            sections=sections,
            include_scenarios=include_scenarios,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=404 if "not found" in result.get("error", "").lower() else 500,
                detail=result.get("error", "Report generation failed"),
            )

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate report error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@report_router.get("/session/{session_id}/report/download")
async def download_report(session_id: str, request: Request, format: str = "json"):
    """
    Download a generated report.

    Query params:
        - format: Output format - "json" (default), "markdown", or "html"

    Returns the report in the requested format for download
    or use in external systems.
    """
    try:
        service = get_report_service()
        result = service.generate_report(session_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=404 if "not found" in result.get("error", "").lower() else 500,
                detail=result.get("error", "Report generation failed"),
            )

        report = result.get("report", {})

        if format == "markdown":
            # Convert to markdown
            md_content = _report_to_markdown(report)
            return JSONResponse({
                "success": True,
                "format": "markdown",
                "content": md_content,
                "filename": f"advisory_report_{session_id[:8]}.md",
            })

        elif format == "html":
            # Convert to HTML
            html_content = _report_to_html(report)
            return JSONResponse({
                "success": True,
                "format": "html",
                "content": html_content,
                "filename": f"advisory_report_{session_id[:8]}.html",
            })

        else:
            # Return JSON
            return JSONResponse({
                "success": True,
                "format": "json",
                "report": report,
                "filename": f"advisory_report_{session_id[:8]}.json",
            })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download report error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@report_router.get("/session/{session_id}/report/sections")
async def get_report_sections(session_id: str, request: Request):
    """
    Get available report sections.

    Returns list of sections that can be included in a report,
    useful for building custom report configurations.
    """
    try:
        service = get_report_service()
        result = service.get_report_sections()

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            **result,
        })

    except Exception as e:
        logger.error(f"Get report sections error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _report_to_markdown(report: dict) -> str:
    """Convert report to markdown format."""
    md = f"# {report.get('title', 'Tax Advisory Report')}\n\n"
    md += f"**Client:** {report.get('client_name', 'Client')}\n"
    md += f"**Filing Status:** {report.get('filing_status', 'N/A').replace('_', ' ').title()}\n"
    md += f"**Tax Year:** {report.get('tax_year', 2025)}\n"
    md += f"**Generated:** {report.get('generated_at', 'N/A')}\n"
    md += f"**Total Potential Savings:** ${report.get('total_potential_savings', 0):,.0f}\n\n"
    md += "---\n\n"

    for section in report.get("sections", []):
        md += section.get("content", "") + "\n\n"

    return md


def _report_to_html(report: dict) -> str:
    """Convert report to HTML format."""
    import html

    title = html.escape(report.get('title', 'Tax Advisory Report'))
    client = html.escape(report.get('client_name', 'Client'))

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #34495e; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }}
        h3 {{ color: #7f8c8d; }}
        .header {{ background: #ecf0f1; padding: 20px; margin-bottom: 20px; border-radius: 5px; }}
        .savings {{ color: #27ae60; font-size: 1.2em; font-weight: bold; }}
        .section {{ margin-bottom: 30px; }}
        ul {{ line-height: 1.8; }}
        .disclaimer {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p><strong>Client:</strong> {client}</p>
        <p><strong>Filing Status:</strong> {html.escape(report.get('filing_status', 'N/A').replace('_', ' ').title())}</p>
        <p><strong>Tax Year:</strong> {report.get('tax_year', 2025)}</p>
        <p class="savings">Total Potential Savings: ${report.get('total_potential_savings', 0):,.0f}</p>
    </div>
"""

    for section in report.get("sections", []):
        content = section.get("content", "")
        # Basic markdown to HTML conversion
        content = content.replace("## ", "<h2>").replace("\n### ", "</h2>\n<h3>")
        content = content.replace("\n**", "\n<strong>").replace("**\n", "</strong>\n")
        content = content.replace("**:", "</strong>:")
        content = content.replace("\n- ", "\n<li>").replace("</li>\n<li>", "</li>\n<li>")

        html_content += f"""
    <div class="section">
        {content}
    </div>
"""

    html_content += """
</body>
</html>
"""

    return html_content
