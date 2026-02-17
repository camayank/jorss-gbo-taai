"""Security guardrails for CPA panel internal/auth route boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Dict, Set, Tuple

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cpa_panel.api import auth_dependencies
from cpa_panel.api.router import cpa_router


def _build_cpa_app() -> FastAPI:
    app = FastAPI()
    app.include_router(cpa_router, prefix="/api")
    return app


def _dependency_map(app: FastAPI) -> Dict[Tuple[str, str], Set[str]]:
    dep_map: Dict[Tuple[str, str], Set[str]] = {}
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if not path.startswith("/api/cpa"):
            continue

        deps: Set[str] = set()
        dependant = getattr(route, "dependant", None)
        if dependant is not None:
            for dep in getattr(dependant, "dependencies", []) or []:
                call = getattr(dep, "call", None)
                if call:
                    deps.add(
                        f"{getattr(call, '__module__', '?')}.{getattr(call, '__name__', str(call))}"
                    )

        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            dep_map[(method, path)] = deps

    return dep_map


def test_internal_cpa_routes_include_internal_auth_dependency():
    app = _build_cpa_app()
    dep_map = _dependency_map(app)

    protected_routes = {
        ("GET", "/api/cpa/health"),
        ("GET", "/api/cpa/docs/routes"),
        ("POST", "/api/cpa/funnel/process-lead"),
        ("POST", "/api/cpa/funnel/calculate-fee"),
        ("GET", "/api/cpa/leads/pipeline"),
        ("POST", "/api/cpa/leads/{lead_id}/assign"),
        ("GET", "/api/cpa/lead-magnet/leads"),
        ("POST", "/api/cpa/lead-magnet/leads/{lead_id}/engage"),
        ("POST", "/api/cpa/lead-magnet/cpa-profiles"),
        ("PUT", "/api/cpa/lead-magnet/cpa-profiles/{cpa_id}"),
    }

    missing_routes = sorted(route for route in protected_routes if route not in dep_map)
    assert not missing_routes, f"Missing expected CPA routes: {missing_routes}"

    missing_auth = []
    for route in protected_routes:
        deps = dep_map[route]
        if "cpa_panel.api.auth_dependencies.require_internal_cpa_auth" not in deps:
            missing_auth.append((route, sorted(deps)))

    assert not missing_auth, f"Routes missing internal CPA auth dependency: {missing_auth}"


def test_no_unexpected_open_cpa_routes():
    """
    Only explicit prospect/public lead endpoints may remain open.

    Any additional no-dependency route under /api/cpa is a launch blocker.
    """
    app = _build_cpa_app()
    dep_map = _dependency_map(app)

    open_routes = {
        route
        for route, deps in dep_map.items()
        if not deps
    }

    allowed_open_routes = {
        ("GET", "/api/cpa/lead-magnet/cpa-profiles/{cpa_slug}"),
        ("GET", "/api/cpa/lead-magnet/demo/report"),
        ("POST", "/api/cpa/lead-magnet/start"),
        ("POST", "/api/cpa/lead-magnet/{session_id}/contact"),
        ("POST", "/api/cpa/lead-magnet/{session_id}/event"),
        ("POST", "/api/cpa/lead-magnet/{session_id}/profile"),
        ("GET", "/api/cpa/lead-magnet/{session_id}/report"),
        ("GET", "/api/cpa/lead-magnet/{session_id}/report/full"),
        ("GET", "/api/cpa/leads/demo/full-analysis"),
        ("GET", "/api/cpa/leads/demo/teaser"),
        ("POST", "/api/cpa/leads/estimate"),
        ("POST", "/api/cpa/leads/upload"),
        ("POST", "/api/cpa/leads/{lead_id}/contact"),
    }

    unexpected_open = sorted(open_routes - allowed_open_routes)
    assert not unexpected_open, f"Unexpected open /api/cpa routes: {unexpected_open}"


def test_internal_route_rejects_anonymous_requests():
    app = _build_cpa_app()
    client = TestClient(app)

    response = client.post(
        "/api/cpa/funnel/calculate-fee",
        json={"engagement_value": 1000, "is_high_value": False},
    )

    assert response.status_code == 401
    assert "authentication required" in response.json()["detail"].lower()


def test_public_prospect_routes_still_work_without_auth():
    app = _build_cpa_app()
    client = TestClient(app)

    response = client.post("/api/cpa/lead-magnet/start", json={"assessment_mode": "quick"})
    assert response.status_code == 200
    payload = response.json()
    assert "session_id" in payload
    assert payload.get("assessment_mode") == "quick"


def test_internal_cpa_routes_reject_client_principals():
    """
    Authenticated client/consumer principals must not access internal CPA routes.
    """
    app = _build_cpa_app()
    app.dependency_overrides[auth_dependencies.get_optional_user] = lambda: SimpleNamespace(
        user_type="cpa_client",
        cpa_role=None,
    )
    app.dependency_overrides[auth_dependencies.optional_auth] = lambda: None

    client = TestClient(app)
    response = client.post(
        "/api/cpa/funnel/calculate-fee",
        json={"engagement_value": 1000, "is_high_value": False},
    )

    assert response.status_code == 403
    assert "internal cpa credentials" in response.json()["detail"].lower()
