"""Security regressions for CPA notification authentication handling."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cpa_panel.api.notification_routes import notification_router


def _build_notification_app() -> FastAPI:
    app = FastAPI()
    app.include_router(notification_router, prefix="/api/cpa")
    return app


def test_notification_routes_fail_with_401_when_unauthenticated():
    """
    Notification routes must not convert auth failures into 500s.

    This protects the launch blocker requirement that unauthenticated writes
    (and reads) consistently return 401/403.
    """
    client = TestClient(_build_notification_app())

    requests = [
        ("get", "/api/cpa/notifications", {}),
        ("post", "/api/cpa/notifications/mark-read", {"json": {"notification_ids": ["n1"]}}),
        ("post", "/api/cpa/notifications/mark-all-read", {}),
        ("get", "/api/cpa/reminders", {}),
        ("post", "/api/cpa/reminders/r1/snooze", {}),
        ("get", "/api/cpa/notifications/stats", {}),
    ]

    for method, path, kwargs in requests:
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 401, f"{method.upper()} {path} returned {response.status_code}"
        assert "authentication required" in response.json()["detail"].lower()
