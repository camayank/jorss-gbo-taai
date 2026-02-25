#!/usr/bin/env python3
"""
Route-Auth-Nav Verification Script

Audits the codebase to verify:
1. Auth coverage — every non-public GET page route has an auth guard
2. Nav coverage — every non-redirect page route appears in at least one template nav
3. Broken links — every href="/..." in templates resolves to a registered route

Usage:
    python scripts/audit_routes.py
"""

import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Resolve project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
WEB_DIR = PROJECT_ROOT / "src" / "web"
APP_PY = WEB_DIR / "app.py"
ROUTERS_DIR = WEB_DIR / "routers"
TEMPLATES_DIR = WEB_DIR / "templates"


# =============================================================================
# CONFIGURATION
# =============================================================================

# Routes that are intentionally public (no auth required)
PUBLIC_ALLOWLIST = {
    "/", "/landing", "/cpa-landing", "/for-cpas", "/intelligent-advisor", "/file",
    "/login", "/signup", "/forgot-password", "/reset-password", "/mfa-setup", "/mfa-verify",
    "/client/login", "/logout",
    "/terms", "/terms-of-service", "/privacy", "/privacy-policy",
    "/cookies", "/cookie-policy", "/disclaimer",
    "/health", "/docs", "/openapi.json", "/manifest.json",
    "/quick-estimate", "/estimate",
    "/advisor", "/start", "/analysis", "/chat", "/simple", "/conversation",
    "/tax-advisory", "/advisory",
    # Self-protecting (inline role checks with redirect)
    "/app/portal",
    # Dev-only routes (behind _ENABLE_TEST_ROUTES env flag)
    "/test-auth", "/test-hub", "/test-dashboard",
}

# Prefixes for public routes
PUBLIC_PREFIXES = [
    "/lead-magnet/", "/auth/", "/api/", "/static/",
    "/smart-tax",  # redirects
]

# Routes accessed via parent page actions, not sidebar nav (nav-exempt)
NAV_EXEMPT = {
    "/documents/{document_id}/view",
    "/support/tickets/{ticket_id}",
    "/support/new",
    "/tasks/{task_id}",
    "/guided/{session_id}",
    "/appointments/book",
    "/appointments/settings",
    "/appointments",  # Canonical alias — nav uses /appointments/calendar
    "/appointments/calendar",  # Alias for /appointments
    "/workflow",  # Canonical alias — nav uses /workflow-hub
    "/advisory-report-preview",  # Accessed from advisor flow
    "/app/portal",  # Role-router destination, not sidebar item
    "/app/settings",  # Settings router destination
    "/cpa/settings/branding",  # Accessed from CPA settings
    "/cpa/settings/payments",  # Accessed from CPA settings
    "/settings/notifications",  # Accessed from settings page
    "/documents/library",  # Accessed from documents redirect
    "/guided",  # Accessed from dashboard action
    "/test-hub", "/test-dashboard",  # Dev-only test pages
}

# Redirect-only routes (no page content, just 302)
REDIRECT_ROUTES = {
    "/cpa", "/settings", "/documents", "/returns", "/clients",
    "/projections", "/smart-tax", "/smart-tax/{path:path}",
    "/smart-tax-legacy",
    "/app", "/workspace", "/portal",
    "/client",
}

# Auth guard patterns (regex) to detect in function bodies
AUTH_PATTERNS = [
    r"_require_any_auth\(",
    r"_require_admin_page_access\(",
    r"_require_page_auth",
    r"_require_admin_page\b",
    r"Depends\(_require_page_auth\)",
    r"Depends\(_require_admin_page\)",
    r"require_cpa_auth",
    r"get_user_from_request",
    r"HTTPException\(status_code=401",
]


@dataclass
class Route:
    path: str
    method: str
    function_name: str
    source_file: str
    line_number: int
    has_auth: bool = False
    is_redirect: bool = False
    is_page: bool = False  # GET + HTMLResponse


@dataclass
class AuditResult:
    routes: list = field(default_factory=list)
    unprotected: list = field(default_factory=list)
    missing_nav: list = field(default_factory=list)
    broken_links: list = field(default_factory=list)
    template_hrefs: set = field(default_factory=set)
    nav_hrefs: set = field(default_factory=set)


# =============================================================================
# ROUTE PARSING
# =============================================================================

def parse_routes_from_file(filepath: Path, decorator_prefix: str = "@app") -> list[Route]:
    """Parse FastAPI route decorators from a Python file."""
    routes = []
    if not filepath.exists():
        return routes

    content = filepath.read_text()
    lines = content.split("\n")

    # Match route decorators like @app.get("/path", ...) or @router.get("/path", ...)
    route_re = re.compile(
        r'@(?:app|router)\.(get|post|put|delete|patch)\(\s*"([^"]+)"'
    )
    redirect_re = re.compile(r'RedirectResponse\(')
    html_response_re = re.compile(r'response_class\s*=\s*HTMLResponse')
    func_re = re.compile(r'(?:async\s+)?def\s+(\w+)\s*\(')

    i = 0
    while i < len(lines):
        line = lines[i]
        route_match = route_re.search(line)
        if route_match:
            method = route_match.group(1).upper()
            path = route_match.group(2)
            is_html = bool(html_response_re.search(line))

            # Collect all stacked decorators
            decorator_start = i
            i += 1
            while i < len(lines) and route_re.search(lines[i]):
                if html_response_re.search(lines[i]):
                    is_html = True
                i += 1

            # Find function definition
            func_name = "unknown"
            func_line = i
            while func_line < min(i + 5, len(lines)):
                func_match = func_re.search(lines[func_line])
                if func_match:
                    func_name = func_match.group(1)
                    break
                func_line += 1

            # Check function body for auth guards
            has_auth = False
            is_redirect = False
            body_end = min(func_line + 50, len(lines))
            body = "\n".join(lines[func_line:body_end])

            # Find next function or class to limit body scope
            for j in range(func_line + 1, body_end):
                if lines[j] and not lines[j].startswith(" ") and not lines[j].startswith("\t"):
                    if lines[j].startswith("@") or lines[j].startswith("def ") or lines[j].startswith("class "):
                        body = "\n".join(lines[func_line:j])
                        break

            for pattern in AUTH_PATTERNS:
                if re.search(pattern, body):
                    has_auth = True
                    break

            if redirect_re.search(body) and "TemplateResponse" not in body:
                is_redirect = True

            route = Route(
                path=path,
                method=method,
                function_name=func_name,
                source_file=str(filepath.relative_to(PROJECT_ROOT)),
                line_number=decorator_start + 1,
                has_auth=has_auth,
                is_redirect=is_redirect,
                is_page=(method == "GET" and (is_html or "TemplateResponse" in body)),
            )
            routes.append(route)
        else:
            i += 1

    return routes


def is_public_route(path: str) -> bool:
    """Check if a route path is in the public allowlist."""
    if path in PUBLIC_ALLOWLIST:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    # Path parameter routes: normalize
    normalized = re.sub(r'\{[^}]+\}', '*', path)
    if normalized in PUBLIC_ALLOWLIST:
        return True
    return False


def is_redirect_route(path: str) -> bool:
    """Check if a route is redirect-only."""
    return path in REDIRECT_ROUTES


def is_nav_exempt(path: str) -> bool:
    """Check if a route is exempt from nav coverage."""
    if path in NAV_EXEMPT:
        return True
    # Normalize path params
    normalized = re.sub(r'\{[^}]+\}', '{param}', path)
    for exempt in NAV_EXEMPT:
        exempt_normalized = re.sub(r'\{[^}]+\}', '{param}', exempt)
        if normalized == exempt_normalized:
            return True
    return False


# =============================================================================
# TEMPLATE HREF PARSING
# =============================================================================

def extract_template_hrefs(templates_dir: Path) -> set[str]:
    """Extract all href="/..." values from templates."""
    hrefs = set()
    href_re = re.compile(r'href="(/[^"{}]*?)"')

    for template_file in templates_dir.rglob("*.html"):
        content = template_file.read_text(errors="replace")
        for match in href_re.finditer(content):
            href = match.group(1)
            # Strip query params
            href = href.split("?")[0]
            if href and not href.startswith("/static/") and not href.startswith("//"):
                hrefs.add(href)

    return hrefs


def extract_nav_hrefs(templates_dir: Path) -> set[str]:
    """Extract hrefs specifically from navigation sections (sidebar, nav items)."""
    hrefs = set()
    # We look for hrefs within nav-related contexts
    href_re = re.compile(r'href="(/[^"{}]*?)"')
    nav_context_re = re.compile(r'nav-item|nav-section|sidebar|default_nav')

    for template_file in templates_dir.rglob("*.html"):
        content = template_file.read_text(errors="replace")
        lines = content.split("\n")
        in_nav_context = False

        for j, line in enumerate(lines):
            if nav_context_re.search(line):
                in_nav_context = True

            if in_nav_context:
                for match in href_re.finditer(line):
                    href = match.group(1).split("?")[0]
                    if href and not href.startswith("/static/"):
                        hrefs.add(href)

            # Reset after blank lines or closing divs outside nav
            if not line.strip():
                in_nav_context = False

    return hrefs


# =============================================================================
# AUDIT
# =============================================================================

def run_audit() -> AuditResult:
    """Run the full route-auth-nav audit."""
    result = AuditResult()

    # 1. Parse all routes
    source_files = [
        APP_PY,
        ROUTERS_DIR / "pages.py",
        ROUTERS_DIR / "feature_pages.py",
    ]

    # Also scan for CPA dashboard pages and lead magnet pages
    for candidate in [
        WEB_DIR / "cpa_dashboard_pages.py",
        WEB_DIR / "lead_magnet_pages.py",
    ]:
        if candidate.exists():
            source_files.append(candidate)

    for filepath in source_files:
        if filepath.exists():
            result.routes.extend(parse_routes_from_file(filepath))

    # 2. Check auth coverage — every non-public GET page route needs auth
    for route in result.routes:
        if route.method != "GET":
            continue
        if not route.is_page:
            continue
        if is_public_route(route.path):
            continue
        if route.is_redirect or is_redirect_route(route.path):
            continue
        if not route.has_auth:
            result.unprotected.append(route)

    # 3. Extract template hrefs
    result.template_hrefs = extract_template_hrefs(TEMPLATES_DIR)
    result.nav_hrefs = extract_nav_hrefs(TEMPLATES_DIR)

    # 4. Check nav coverage — every page route should appear in at least one nav
    route_paths = set()
    for route in result.routes:
        if route.method == "GET" and route.is_page:
            if not route.is_redirect and not is_redirect_route(route.path):
                if not is_public_route(route.path):
                    if not is_nav_exempt(route.path):
                        if "{" not in route.path:  # Skip parameterized routes
                            route_paths.add(route.path)

    for path in sorted(route_paths):
        if path not in result.template_hrefs and path not in result.nav_hrefs:
            result.missing_nav.append(path)

    # 5. Check broken links — template hrefs should resolve to routes
    registered_paths = set()
    for route in result.routes:
        registered_paths.add(route.path)
        # Also add the base path for parameterized routes
        if "{" in route.path:
            base = re.sub(r'/\{[^}]+\}.*', '', route.path)
            if base:
                registered_paths.add(base)

    # Add known static/external paths and SPA catch-all prefixes
    registered_paths.update({"/static", "/docs", "/openapi.json", "/redoc", "/api"})
    # Routes served by modules not parsed by this script
    registered_paths.update({
        "/intelligent-advisor", "/for-cpas", "/health",
        "/system-hub", "/workflow-hub", "/appointments/calendar",
    })
    # Marketing/footer placeholder pages (not yet built, but not auth-relevant)
    _marketing_placeholders = {
        "/about", "/blog", "/careers", "/contact", "/features",
        "/guides", "/help", "/integrations", "/press", "/pricing", "/security",
    }
    registered_paths.update(_marketing_placeholders)
    # Template links that use variant URL patterns
    # /support/ticket/N → /support/tickets/{id}, /support/create → /support/new
    # /messages/new → future feature
    _template_variants = {"/support/create", "/messages/new"}
    registered_paths.update(_template_variants)
    # CPA dashboard pages are served by cpa_dashboard_pages module (not parsed here)
    # Admin sub-routes are caught by /admin/{path:path}
    # These prefixes are valid destinations even if not individually registered
    _spa_prefixes = [
        "/cpa/", "/admin/", "/api/", "/auth/", "/lead-magnet",
        "/support/ticket/",  # Demo links: /support/ticket/1..5
    ]

    for href in sorted(result.template_hrefs):
        # Skip external links, anchors, javascript
        if href.startswith("//") or href.startswith("#"):
            continue
        # Normalize — strip trailing slashes
        normalized = href.rstrip("/") or "/"

        # Check if it matches any registered route
        found = False
        if normalized in registered_paths:
            found = True
        else:
            # Check prefix matches for catch-all routes
            for rpath in registered_paths:
                if "{path:path}" in rpath:
                    prefix = rpath.split("{")[0].rstrip("/")
                    if normalized.startswith(prefix):
                        found = True
                        break
                elif "{" in rpath:
                    # Parameterized — check base prefix
                    prefix = re.sub(r'/\{[^}]+\}.*', '', rpath)
                    if normalized.startswith(prefix + "/") or normalized == prefix:
                        found = True
                        break

        # Check SPA prefixes (CPA dashboard, admin SPA, API, auth)
        if not found:
            for spa_prefix in _spa_prefixes:
                if normalized.startswith(spa_prefix):
                    found = True
                    break

        if not found:
            result.broken_links.append(href)

    return result


# =============================================================================
# REPORTING
# =============================================================================

def print_report(result: AuditResult):
    """Print the audit report."""
    total_routes = len(result.routes)
    page_routes = [r for r in result.routes if r.is_page and r.method == "GET"]
    redirect_routes = [r for r in result.routes if r.is_redirect]

    print("=" * 70)
    print("ROUTE-AUTH-NAV AUDIT REPORT")
    print("=" * 70)
    print()
    print(f"Total routes parsed:     {total_routes}")
    print(f"  Page routes (GET+HTML): {len(page_routes)}")
    print(f"  Redirect routes:        {len(redirect_routes)}")
    print(f"  Template hrefs found:   {len(result.template_hrefs)}")
    print()

    # Auth gaps
    print("-" * 70)
    print(f"AUTH GAPS: {len(result.unprotected)} unprotected page routes")
    print("-" * 70)
    if result.unprotected:
        for r in result.unprotected:
            print(f"  FAIL  {r.path}")
            print(f"        -> {r.source_file}:{r.line_number} ({r.function_name})")
    else:
        print("  PASS  All non-public page routes have auth guards")
    print()

    # Nav gaps
    print("-" * 70)
    print(f"NAV GAPS: {len(result.missing_nav)} page routes missing from navigation")
    print("-" * 70)
    if result.missing_nav:
        for path in result.missing_nav:
            print(f"  WARN  {path}")
    else:
        print("  PASS  All page routes appear in navigation")
    print()

    # Broken links
    print("-" * 70)
    print(f"BROKEN LINKS: {len(result.broken_links)} template hrefs with no matching route")
    print("-" * 70)
    if result.broken_links:
        for href in result.broken_links:
            print(f"  WARN  {href}")
    else:
        print("  PASS  All template hrefs resolve to registered routes")
    print()

    # Summary
    print("=" * 70)
    auth_ok = len(result.unprotected) == 0
    nav_ok = len(result.missing_nav) == 0
    links_ok = len(result.broken_links) == 0

    if auth_ok and nav_ok and links_ok:
        print("RESULT: ALL CHECKS PASSED")
    else:
        issues = []
        if not auth_ok:
            issues.append(f"{len(result.unprotected)} auth gaps")
        if not nav_ok:
            issues.append(f"{len(result.missing_nav)} nav gaps")
        if not links_ok:
            issues.append(f"{len(result.broken_links)} broken links")
        print(f"RESULT: {', '.join(issues)}")
    print("=" * 70)

    return 0 if auth_ok else 1


if __name__ == "__main__":
    result = run_audit()
    exit_code = print_report(result)
    sys.exit(exit_code)
