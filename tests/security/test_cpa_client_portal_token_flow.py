"""Regression tests for CPA client portal token authentication flow."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from cpa_panel.api import client_portal_routes


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeSession:
    def __init__(self, row=None):
        self._row = row

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self._row)


@pytest.fixture(autouse=True)
def _reset_legacy_tokens():
    client_portal_routes._client_tokens.clear()
    yield
    client_portal_routes._client_tokens.clear()


def _build_portal_router_app(session_value=None) -> FastAPI:
    app = FastAPI()
    app.include_router(client_portal_routes.router, prefix="/api/cpa")

    async def _session_override():
        yield session_value

    app.dependency_overrides[client_portal_routes.get_async_session] = _session_override
    return app


def _build_identity_test_app(session_value) -> FastAPI:
    app = FastAPI()

    async def _session_override():
        yield session_value

    app.dependency_overrides[client_portal_routes.get_async_session] = _session_override

    @app.get("/whoami")
    async def whoami(
        client: client_portal_routes.ClientContext = Depends(
            client_portal_routes.get_current_client
        ),
    ):
        return {"client_id": client.client_id, "email": client.email}

    return app


def test_verify_token_accepts_client_portal_jwt_payload(monkeypatch):
    app = _build_portal_router_app(session_value=None)
    client = TestClient(app)

    monkeypatch.setattr(
        client_portal_routes,
        "decode_token_safe",
        lambda _token: {
            "type": "client_portal",
            "client_id": "client-123",
            "name": "Client One",
            "email": "client@example.com",
        },
    )

    response = client.post("/api/cpa/client/verify-token", params={"token": "jwt-token"})
    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "client_id": "client-123",
        "name": "Client One",
        "email": "client@example.com",
    }


def test_get_current_client_accepts_legacy_token_path():
    fake_client_row = (
        "client-legacy",
        "Legacy",
        "User",
        "legacy@example.com",
        None,
        None,
    )
    app = _build_identity_test_app(session_value=_FakeSession(row=fake_client_row))
    client = TestClient(app)

    client_portal_routes._client_tokens["legacy-token"] = {
        "client_id": "client-legacy",
        "email": "legacy@example.com",
        "first_name": "Legacy",
        "last_name": "User",
        "expires_at": datetime.utcnow() + timedelta(hours=1),
    }

    response = client.get("/whoami", headers={"Authorization": "Bearer legacy-token"})
    assert response.status_code == 200
    assert response.json() == {
        "client_id": "client-legacy",
        "email": "legacy@example.com",
    }


def test_get_current_client_rejects_non_client_jwt_payload(monkeypatch):
    app = _build_identity_test_app(session_value=_FakeSession(row=None))
    client = TestClient(app)

    monkeypatch.setattr(
        client_portal_routes,
        "decode_token_safe",
        lambda _token: {
            "type": "client_portal",
            "sub": "not-a-client",
            "role": "partner",
            "user_type": "firm_user",
        },
    )

    response = client.get("/whoami", headers={"Authorization": "Bearer invalid-client-token"})
    assert response.status_code == 401
    assert "not valid for client portal" in response.json()["detail"].lower()
