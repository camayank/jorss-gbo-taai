"""Guardrails for web launch route auth protections."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Set, Tuple

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return node.__class__.__name__


def _collect_route_decorators() -> Dict[Tuple[str, str], Set[str]]:
    """Return {(METHOD, PATH): {decorator_names}} for src/web/app.py."""
    app_path = Path(__file__).resolve().parents[2] / "src" / "web" / "app.py"
    module = ast.parse(app_path.read_text(encoding="utf-8"))
    route_map: Dict[Tuple[str, str], Set[str]] = {}

    for node in module.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        decorator_names = {_decorator_name(d) for d in node.decorator_list}
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            if not isinstance(dec.func.value, ast.Name) or dec.func.value.id != "app":
                continue
            if dec.func.attr not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not dec.args or not isinstance(dec.args[0], ast.Constant):
                continue
            path = dec.args[0].value
            if not isinstance(path, str):
                continue
            method = dec.func.attr.upper()
            route_map[(method, path)] = decorator_names

    return route_map


def test_launch_blocker_routes_require_auth():
    """Critical web route families must keep explicit auth decorators."""
    routes = _collect_route_decorators()
    required_auth = {
        ("GET", "/api/upload/status/{task_id}"),
        ("GET", "/api/documents/{document_id}/status"),
        ("POST", "/api/upload/cancel/{task_id}"),
        ("GET", "/api/documents"),
        ("GET", "/api/documents/{document_id}"),
        ("POST", "/api/documents/{document_id}/apply"),
        ("POST", "/api/calculate-tax"),
        ("GET", "/api/returns"),
        ("GET", "/api/returns/{session_id}/status"),
        ("POST", "/api/returns/{session_id}/submit-for-review"),
        ("POST", "/api/returns/{session_id}/revert-to-draft"),
        ("GET", "/api/returns/queue/{status}"),
        ("POST", "/api/returns/{session_id}/delta"),
        ("POST", "/api/returns/{session_id}/notes"),
        ("GET", "/api/returns/{session_id}/notes"),
        ("GET", "/api/returns/{session_id}/tax-drivers"),
        ("POST", "/api/returns/{session_id}/compare-scenarios"),
    }

    missing_route_defs = [route for route in required_auth if route not in routes]
    assert not missing_route_defs, f"Routes not found in app.py: {missing_route_defs}"

    missing_auth = [route for route in required_auth if "require_auth" not in routes[route]]
    assert not missing_auth, f"Routes missing @require_auth: {missing_auth}"


def test_session_scoped_routes_require_session_owner():
    """Session-scoped state mutations/reads must retain ownership checks."""
    routes = _collect_route_decorators()
    required_owner = {
        ("GET", "/api/returns/{session_id}/status"),
        ("POST", "/api/returns/{session_id}/submit-for-review"),
        ("POST", "/api/returns/{session_id}/revert-to-draft"),
        ("POST", "/api/returns/{session_id}/delta"),
        ("POST", "/api/returns/{session_id}/notes"),
        ("GET", "/api/returns/{session_id}/notes"),
        ("GET", "/api/returns/{session_id}/tax-drivers"),
        ("POST", "/api/returns/{session_id}/compare-scenarios"),
    }

    missing_route_defs = [route for route in required_owner if route not in routes]
    assert not missing_route_defs, f"Routes not found in app.py: {missing_route_defs}"

    missing_owner = [route for route in required_owner if "require_session_owner" not in routes[route]]
    assert not missing_owner, f"Routes missing @require_session_owner: {missing_owner}"


def test_require_auth_attaches_user_to_request_state(monkeypatch):
    """Decorator should expose authenticated principal to endpoint logic."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")

    from security import auth_decorators as auth

    monkeypatch.setattr(
        auth,
        "get_user_from_request",
        lambda _request: {
            "id": "user-1",
            "role": auth.Role.TAXPAYER.value,
            "tenant_id": "tenant-a",
        },
    )

    app = FastAPI()

    @app.get("/protected")
    @auth.require_auth(roles=[auth.Role.TAXPAYER])
    async def protected(request: Request):
        return {"user_id": request.state.user["id"], "tenant_id": request.state.user["tenant_id"]}

    client = TestClient(app)
    response = client.get("/protected")

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1", "tenant_id": "tenant-a"}


def test_require_auth_rejects_unauthenticated_requests(monkeypatch):
    """Fail-closed behavior should return 401 in production mode."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")

    from security import auth_decorators as auth

    monkeypatch.setattr(auth, "get_user_from_request", lambda _request: None)

    app = FastAPI()

    @app.get("/protected")
    @auth.require_auth()
    async def protected(request: Request):
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/protected")

    assert response.status_code == 401
    assert "authentication required" in response.json()["detail"].lower()
