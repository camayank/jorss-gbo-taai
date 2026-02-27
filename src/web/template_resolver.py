"""
Template Resolver for UX v2 Migration

Provides utilities for resolving templates based on feature flags.
Integrates with FastAPI's Jinja2Templates for seamless v1/v2 switching.

Usage:
    from web.template_resolver import get_template, TemplateResponseV2

    # Option 1: Get template path
    template_path = get_template(request, "dashboard.html")
    return templates.TemplateResponse(template_path, {"request": request})

    # Option 2: Use helper response
    return TemplateResponseV2(request, "dashboard.html", {"data": data})
"""

from typing import Dict, Any, Optional
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

from web.feature_flags import (
    should_use_ux_v2,
    set_ux_version_cookie,
    get_ux_version,
)

# Template directory
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# Templates that have v2 versions
V2_TEMPLATES = {
    "base.html",
    "results.html",
    "guided_filing.html",
    "dashboard.html",
    "lead_magnet/landing.html",
}


def get_template(request: Request, template_name: str) -> str:
    """
    Resolve template path based on feature flags.

    Args:
        request: FastAPI request object
        template_name: Original template name (e.g., "dashboard.html")

    Returns:
        Resolved template path (e.g., "v2/dashboard.html" or "dashboard.html")
    """
    if should_use_ux_v2(request) and template_name in V2_TEMPLATES:
        return f"v2/{template_name}"
    return template_name


def get_template_context(request: Request, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance template context with UX version information.

    Args:
        request: FastAPI request object
        context: Original template context

    Returns:
        Enhanced context with ux_version
    """
    context = context.copy()
    context["ux_version"] = get_ux_version(request)
    context["request"] = request
    return context


class TemplateResponseV2:
    """
    Helper class for rendering templates with automatic v2 resolution.

    Usage:
        return TemplateResponseV2(request, "dashboard.html", {"data": data})
    """

    def __init__(
        self,
        request: Request,
        template_name: str,
        context: Optional[Dict[str, Any]] = None,
        templates: Optional[Jinja2Templates] = None,
    ):
        self.request = request
        self.template_name = template_name
        self.context = context or {}
        self._templates = templates

    def render(self, templates: Jinja2Templates) -> HTMLResponse:
        """Render the template with v2 resolution."""
        # Resolve template path
        resolved_path = get_template(self.request, self.template_name)

        # Enhance context
        full_context = get_template_context(self.request, self.context)

        # Render response
        response = templates.TemplateResponse(resolved_path, full_context)

        # Set version cookie for session consistency
        use_v2 = should_use_ux_v2(self.request)
        set_ux_version_cookie(response, use_v2)

        return response


def create_template_response(
    request: Request,
    template_name: str,
    context: Dict[str, Any],
    templates: Jinja2Templates,
) -> HTMLResponse:
    """
    Create a template response with automatic v2 resolution.

    This is the recommended way to render templates during the v2 migration.

    Args:
        request: FastAPI request object
        template_name: Template name (e.g., "dashboard.html")
        context: Template context dictionary
        templates: Jinja2Templates instance

    Returns:
        HTMLResponse with rendered template

    Example:
        return create_template_response(
            request,
            "dashboard.html",
            {"user": user, "data": data},
            templates
        )
    """
    # Resolve template path
    resolved_path = get_template(request, template_name)

    # Enhance context
    full_context = get_template_context(request, context)

    # Render response
    response = templates.TemplateResponse(resolved_path, full_context)

    # Set version cookie for session consistency
    use_v2 = should_use_ux_v2(request)
    set_ux_version_cookie(response, use_v2)

    return response


# =============================================================================
# ROUTE DECORATOR (Alternative approach)
# =============================================================================

def with_v2_template(template_name: str):
    """
    Decorator for routes that should use v2 template resolution.

    Usage:
        @app.get("/dashboard")
        @with_v2_template("dashboard.html")
        async def dashboard(request: Request):
            return {"data": get_dashboard_data()}

    Note: This is an alternative approach. The recommended way is to use
    create_template_response() directly in your route handlers.
    """
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            # Get context from route handler
            context = await func(request, *args, **kwargs)
            if not isinstance(context, dict):
                return context  # Return as-is if not a dict

            # Resolve template
            resolved = get_template(request, template_name)
            context = get_template_context(request, context)

            # This requires templates to be available - typically injected
            # For now, return context with template info
            context["_template"] = resolved
            return context

        return wrapper
    return decorator
