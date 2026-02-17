"""HTTP-level regression tests for scenario router behavior."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.routers import scenarios as scenarios_router


def _build_client(service) -> TestClient:
    app = FastAPI()
    scenarios_router._scenario_service = service
    app.include_router(scenarios_router.router)
    return TestClient(app)


def _make_scenario_stub():
    return SimpleNamespace(
        scenario_id=uuid4(),
        name="Income Bump",
        scenario_type=SimpleNamespace(value="what_if"),
        status=SimpleNamespace(value="draft"),
        modifications=[{"field_path": "income.wages_salaries_tips", "new_value": 120000}],
        created_at=datetime.utcnow(),
    )


def test_create_scenario_endpoint_returns_success_payload():
    scenario = _make_scenario_stub()

    class _Service:
        def create_scenario(self, **kwargs):
            _ = kwargs
            return scenario

    client = _build_client(_Service())
    response = client.post(
        "/api/scenarios",
        json={
            "return_id": str(uuid4()),
            "name": "Income Bump",
            "scenario_type": "what_if",
            "modifications": [
                {"field_path": "income.wages_salaries_tips", "new_value": 120000},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["scenario_id"] == str(scenario.scenario_id)
    assert payload["type"] == "what_if"


def test_compare_scenarios_requires_at_least_two_ids():
    class _Service:
        def compare_scenarios(self, **kwargs):
            _ = kwargs
            raise AssertionError("compare_scenarios should not be called for invalid input")

    client = _build_client(_Service())
    response = client.post(
        "/api/scenarios/compare",
        json={"scenario_ids": [str(uuid4())]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "At least 2 scenarios required for comparison"


def test_compare_scenarios_surfaces_validation_error_detail():
    class _Service:
        def compare_scenarios(self, **kwargs):
            _ = kwargs
            raise ValueError("Invalid or out-of-scope scenario IDs: bad-id")

    client = _build_client(_Service())
    response = client.post(
        "/api/scenarios/compare",
        json={"scenario_ids": [str(uuid4()), str(uuid4())]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or out-of-scope scenario IDs: bad-id"


def test_apply_scenario_requires_session_id_from_body_or_cookie():
    class _Service:
        def apply_scenario(self, **kwargs):
            _ = kwargs
            raise AssertionError("apply_scenario should not be called when session is missing")

    client = _build_client(_Service())
    response = client.post(f"/api/scenarios/{uuid4()}/apply", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Session ID required"


def test_apply_scenario_uses_cookie_session_id_when_body_empty():
    captured = {}

    class _Service:
        def apply_scenario(self, scenario_id: str, session_id: str):
            captured["scenario_id"] = scenario_id
            captured["session_id"] = session_id
            return {"return_id": str(uuid4()), "status": "updated"}

    scenario_id = str(uuid4())
    client = _build_client(_Service())
    response = client.post(
        f"/api/scenarios/{scenario_id}/apply",
        json={},
        cookies={"tax_session_id": "sess-cookie-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["scenario_id"] == scenario_id
    assert captured["session_id"] == "sess-cookie-1"
