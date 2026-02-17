"""Regression tests for web login/entrypoint routing guards."""

from __future__ import annotations

from fastapi.testclient import TestClient

from web.app import app


def test_client_login_route_exists():
    client = TestClient(app)
    response = client.get("/client/login")
    assert response.status_code == 200
    assert "client portal access" in response.text.lower()


def test_workspace_route_no_longer_renders_broken_template_for_anonymous():
    client = TestClient(app)
    response = client.get("/app/workspace", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=/cpa/dashboard"


def test_portal_route_requires_login_for_anonymous_users():
    client = TestClient(app)
    response = client.get("/app/portal", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/client/login?next=/app/portal"


def test_portal_route_accepts_token_link_for_client_magic_link_flow():
    client = TestClient(app)
    response = client.get("/app/portal?token=demo-token", follow_redirects=False)
    assert response.status_code == 200
    assert "client portal" in response.text.lower()


def test_admin_shell_rejects_spoofed_role_cookie_without_auth():
    client = TestClient(app)
    response = client.get(
        "/admin",
        cookies={"user_role": "admin"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=/admin"


def test_admin_shell_allows_authenticated_admin_context(monkeypatch):
    monkeypatch.setattr(
        "web.app.get_user_from_request",
        lambda _request: {
            "role": "admin",
            "user_type": "platform_admin",
            "id": "admin-user",
        },
    )

    client = TestClient(app)
    response = client.get("/admin")
    assert response.status_code == 200
    assert "admin" in response.text.lower()
