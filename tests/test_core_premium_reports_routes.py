"""
Focused tests for Core Premium Reports CPA endpoints.

Covers:
- /reports/cpa/pricing
- /reports/cpa/generate-for-client
"""

from __future__ import annotations

import json
import sqlite3
import sys
from enum import Enum
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api import premium_reports_routes as premium_routes
from core.models.user import UserContext, UserType


class _StubReportTier(str, Enum):
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"


class _StubReportFormat(str, Enum):
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


class _StubActionItem:
    def to_dict(self) -> dict:
        return {"title": "Follow-up", "priority": "high"}


class _StubReport:
    def __init__(self):
        self.report_id = "rpt-test-001"
        self.session_id = "session-1"
        self.tier = _StubReportTier.PREMIUM
        self.format = _StubReportFormat.HTML
        self.generated_at = "2026-02-16T10:00:00Z"
        self.taxpayer_name = "Client Example"
        self.tax_year = 2025
        self.sections = [{"id": "summary"}, {"id": "actions"}]
        self.action_items = [_StubActionItem()]
        self.html_content = "<html><body>report</body></html>"
        self.metadata = {}


class _StubPremiumReportGenerator:
    def generate(self, session_id, tier, format):  # noqa: A002
        _ = session_id, tier, format
        return _StubReport()


def _install_stub_premium_report_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a lightweight stub for export.premium_report_generator."""
    stub_module = SimpleNamespace(
        PremiumReportGenerator=_StubPremiumReportGenerator,
        ReportTier=_StubReportTier,
        ReportFormat=_StubReportFormat,
    )
    monkeypatch.setitem(sys.modules, "export.premium_report_generator", stub_module)


def _make_user(
    user_type: UserType,
    *,
    user_id: str = "user-1",
    firm_id: str | None = None,
) -> UserContext:
    return UserContext(
        user_id=user_id,
        email=f"{user_id}@example.com",
        user_type=user_type,
        full_name="Test User",
        firm_id=firm_id,
        permissions=[],
    )


def _set_current_user(app: FastAPI, user: UserContext) -> None:
    async def _override_user() -> UserContext:
        return user

    app.dependency_overrides[premium_routes.get_current_user] = _override_user


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(premium_routes.router)
    return app


@pytest.fixture
def client(app: FastAPI):
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestCPAPricingEndpoint:
    def test_pricing_requires_cpa_team_user(self, app: FastAPI, client: TestClient):
        _set_current_user(app, _make_user(UserType.CONSUMER, user_id="consumer-1"))

        response = client.get("/reports/cpa/pricing")

        assert response.status_code == 403

    def test_pricing_requires_firm_context(self, app: FastAPI, client: TestClient):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id=None))

        response = client.get("/reports/cpa/pricing")

        assert response.status_code == 400
        assert "associated with a firm" in response.json()["detail"]

    def test_pricing_uses_firm_settings_when_available(
        self,
        app: FastAPI,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id="firm-1"))
        monkeypatch.setattr(
            premium_routes,
            "_get_firm_report_pricing",
            lambda firm_id: {
                "basic": {"price": 0.0, "enabled": True},
                "standard": {"price": 149.0, "enabled": True},
                "premium": {"price": 399.0, "enabled": True},
            },
        )

        response = client.get("/reports/cpa/pricing")

        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "firm_settings"
        assert payload["pricing"]["standard"]["price"] == 149.0
        assert payload["pricing"]["premium"]["price"] == 399.0

    def test_pricing_falls_back_to_default_profile(
        self,
        app: FastAPI,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id="firm-1"))
        monkeypatch.setattr(premium_routes, "_get_firm_report_pricing", lambda firm_id: None)

        response = client.get("/reports/cpa/pricing")

        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "default_profile"
        assert payload["pricing"]["standard"]["price"] == 99.0
        assert payload["pricing"]["premium"]["price"] == 299.0


class TestCPAPricingDBIntegration:
    def test_pricing_reads_firms_settings_from_sqlite(
        self,
        app: FastAPI,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id="firm-db-1"))

        db_path = tmp_path / "reports_pricing_test.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE firms (
                    firm_id TEXT PRIMARY KEY,
                    settings TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO firms (firm_id, settings)
                VALUES (?, ?)
                """,
                (
                    "firm-db-1",
                    json.dumps(
                        {
                            "reports": {
                                "report_pricing": {
                                    "basic": {"price": 0, "enabled": True},
                                    "standard": {"price": 179, "enabled": True},
                                    "premium": {"price": 449, "enabled": True},
                                }
                            }
                        }
                    ),
                ),
            )
            conn.commit()

        monkeypatch.setattr(premium_routes, "_TAX_RETURNS_DB_PATH", db_path)

        response = client.get("/reports/cpa/pricing")

        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "firm_settings"
        assert payload["pricing"]["basic"]["price"] == 0.0
        assert payload["pricing"]["standard"]["price"] == 179.0
        assert payload["pricing"]["premium"]["price"] == 449.0

    def test_pricing_falls_back_to_firm_settings_integrations_json(
        self,
        app: FastAPI,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id="firm-db-2"))

        db_path = tmp_path / "reports_pricing_fallback_test.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE firms (
                    firm_id TEXT PRIMARY KEY,
                    settings TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO firms (firm_id, settings)
                VALUES (?, ?)
                """,
                (
                    "firm-db-2",
                    json.dumps(
                        {
                            "branding": {"primary_color": "#123456"},
                            "reports": {"template": "default"},
                        }
                    ),
                ),
            )
            conn.execute(
                """
                CREATE TABLE firm_settings (
                    firm_id TEXT PRIMARY KEY,
                    integrations TEXT,
                    notification_preferences TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO firm_settings (firm_id, integrations, notification_preferences)
                VALUES (?, ?, ?)
                """,
                (
                    "firm-db-2",
                    json.dumps(
                        {
                            "premium_reports": {
                                "report_pricing": {
                                    "basic": {"price": 0, "enabled": True},
                                    "standard": {"price": 129, "enabled": True},
                                    "premium": {"price": 349, "enabled": True},
                                }
                            }
                        }
                    ),
                    json.dumps({"digest": {"enabled": True}}),
                ),
            )
            conn.commit()

        monkeypatch.setattr(premium_routes, "_TAX_RETURNS_DB_PATH", db_path)

        response = client.get("/reports/cpa/pricing")

        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "firm_settings"
        assert payload["pricing"]["basic"]["price"] == 0.0
        assert payload["pricing"]["standard"]["price"] == 129.0
        assert payload["pricing"]["premium"]["price"] == 349.0


class TestCPAGenerateForClientEndpoint:
    def test_generate_requires_cpa_team_user(self, app: FastAPI, client: TestClient):
        _set_current_user(app, _make_user(UserType.CONSUMER, user_id="consumer-1"))

        response = client.post(
            "/reports/cpa/generate-for-client",
            params={"client_id": "client-1", "session_id": "session-1"},
        )

        assert response.status_code == 403

    def test_generate_blocks_when_session_access_is_denied(
        self,
        app: FastAPI,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id="firm-1"))
        monkeypatch.setattr(premium_routes, "check_report_access", lambda user, session_id: False)

        response = client.post(
            "/reports/cpa/generate-for-client",
            params={"client_id": "client-1", "session_id": "session-1"},
        )

        assert response.status_code == 403

    def test_generate_blocks_mismatched_session_client(
        self,
        app: FastAPI,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id="firm-1"))
        monkeypatch.setattr(premium_routes, "check_report_access", lambda user, session_id: True)
        monkeypatch.setattr(
            premium_routes,
            "_get_session_ownership",
            lambda session_id: ("client-owner", "firm-1", None),
        )
        monkeypatch.setattr(
            premium_routes,
            "_client_belongs_to_firm",
            lambda client_id, firm_id: True,
        )

        response = client.post(
            "/reports/cpa/generate-for-client",
            params={"client_id": "client-requested", "session_id": "session-1"},
        )

        assert response.status_code == 400
        assert "does not match the owner" in response.json()["detail"]

    def test_generate_blocks_cross_firm_session(
        self,
        app: FastAPI,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id="firm-1"))
        monkeypatch.setattr(premium_routes, "check_report_access", lambda user, session_id: True)
        monkeypatch.setattr(
            premium_routes,
            "_get_session_ownership",
            lambda session_id: ("client-1", "firm-other", None),
        )
        monkeypatch.setattr(
            premium_routes,
            "_client_belongs_to_firm",
            lambda client_id, firm_id: True,
        )

        response = client.post(
            "/reports/cpa/generate-for-client",
            params={"client_id": "client-1", "session_id": "session-1"},
        )

        assert response.status_code == 403
        assert "different firm" in response.json()["detail"]

    def test_generate_blocks_client_not_in_firm(
        self,
        app: FastAPI,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id="firm-1"))
        monkeypatch.setattr(premium_routes, "check_report_access", lambda user, session_id: True)
        monkeypatch.setattr(
            premium_routes,
            "_get_session_ownership",
            lambda session_id: ("client-1", "firm-1", None),
        )
        monkeypatch.setattr(
            premium_routes,
            "_client_belongs_to_firm",
            lambda client_id, firm_id: False,
        )

        response = client.post(
            "/reports/cpa/generate-for-client",
            params={"client_id": "client-1", "session_id": "session-1"},
        )

        assert response.status_code == 403
        assert "does not belong to your firm" in response.json()["detail"]

    def test_generate_succeeds_with_valid_ownership(
        self,
        app: FastAPI,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _set_current_user(app, _make_user(UserType.CPA_TEAM, user_id="cpa-1", firm_id="firm-1"))
        monkeypatch.setattr(premium_routes, "check_report_access", lambda user, session_id: True)
        monkeypatch.setattr(
            premium_routes,
            "_get_session_ownership",
            lambda session_id: ("client-1", "firm-1", "cpa-1"),
        )
        monkeypatch.setattr(
            premium_routes,
            "_client_belongs_to_firm",
            lambda client_id, firm_id: True,
        )
        _install_stub_premium_report_module(monkeypatch)

        response = client.post(
            "/reports/cpa/generate-for-client",
            params={
                "client_id": "client-1",
                "session_id": "session-1",
                "tier": "premium",
                "format": "html",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["report_id"] == "rpt-test-001"
        assert payload["client_id"] == "client-1"
        assert payload["session_id"] == "session-1"
        assert payload["tier"] == "premium"
        assert payload["taxpayer_name"] == "Client Example"
        assert payload["section_count"] == 2
        assert len(payload["action_items"]) == 1
        assert payload["html_content"] is not None
