"""API-level smoke test for end-taxpayer lead magnet funnel."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cpa_panel.api.router import cpa_router


def _build_cpa_app() -> FastAPI:
    app = FastAPI()
    app.include_router(cpa_router, prefix="/api")
    return app


def test_taxpayer_funnel_happy_path_smoke():
    client = TestClient(_build_cpa_app())

    # 1) Start funnel session
    start_resp = client.post(
        "/api/cpa/lead-magnet/start",
        json={
            "assessment_mode": "quick",
            "cpa_slug": "default",
            "referral_source": "integration_smoke",
        },
    )
    assert start_resp.status_code == 200
    start_payload = start_resp.json()
    session_id = start_payload["session_id"]
    assert session_id

    # 2) Submit profile for score/personalization
    profile_resp = client.post(
        f"/api/cpa/lead-magnet/{session_id}/profile",
        json={
            "filing_status": "single",
            "state_code": "CA",
            "dependents_count": 1,
            "has_children_under_17": True,
            "income_range": "200k_500k",
            "income_sources": ["self_employed", "investments"],
            "is_homeowner": True,
            "retirement_savings": "none",
            "healthcare_type": "hdhp_hsa",
            "life_events": ["new_job", "business_start"],
            "has_student_loans": False,
            "has_business": True,
            "privacy_consent": True,
        },
    )
    assert profile_resp.status_code == 200
    profile_payload = profile_resp.json()
    assert profile_payload["score_preview"] > 0
    assert profile_payload["score_band"]
    assert profile_payload["missed_savings_range"]
    assert profile_payload["personalization_line"]
    assert profile_payload["next_screen"] == "teaser"

    # 3) Tier-1 report has chart/share/score payloads
    report_resp = client.get(f"/api/cpa/lead-magnet/{session_id}/report")
    assert report_resp.status_code == 200
    report_payload = report_resp.json()
    assert report_payload["tax_health_score"]["overall"] > 0
    assert "comparison_chart" in report_payload
    assert "share_payload" in report_payload
    assert "image_url" in report_payload["share_payload"]
    assert "personalization" in report_payload
    assert "strategy_waterfall" in report_payload
    assert isinstance(report_payload["strategy_waterfall"].get("bars"), list)

    # 4) Contact capture conversion
    contact_resp = client.post(
        f"/api/cpa/lead-magnet/{session_id}/contact",
        json={
            "first_name": "Integration",
            "email": "integration-smoke@example.com",
            "phone": "5555551212",
            "website": "",
            "form_started_at_ms": 1,
        },
    )
    # form_started_at_ms=1 is sufficiently in the past in test runtime
    assert contact_resp.status_code == 200
    contact_payload = contact_resp.json()
    assert contact_payload["lead_id"]
    assert contact_payload["report_ready"] is True

    # 5) Report stays available post conversion with lead id attached
    report_after_resp = client.get(f"/api/cpa/lead-magnet/{session_id}/report")
    assert report_after_resp.status_code == 200
    report_after_payload = report_after_resp.json()
    assert report_after_payload["lead_id"]


def test_start_session_returns_variant_and_accepts_attribution():
    client = TestClient(_build_cpa_app())

    response = client.post(
        "/api/cpa/lead-magnet/start",
        json={
            "assessment_mode": "quick",
            "variant_id": "D",
            "utm_source": "linkedin",
            "utm_medium": "social",
            "utm_campaign": "spring-cpa-promo",
            "device_type": "mobile",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["variant_id"] == "D"


def test_contact_required_phone_variant_blocks_missing_phone():
    client = TestClient(_build_cpa_app())
    start_resp = client.post(
        "/api/cpa/lead-magnet/start",
        json={
            "assessment_mode": "quick",
            "variant_id": "A",
        },
    )
    session_id = start_resp.json()["session_id"]

    profile_resp = client.post(
        f"/api/cpa/lead-magnet/{session_id}/profile",
        json={
            "filing_status": "single",
            "state_code": "TX",
            "income_range": "100k_150k",
            "income_sources": ["w2"],
            "privacy_consent": True,
        },
    )
    assert profile_resp.status_code == 200

    contact_resp = client.post(
        f"/api/cpa/lead-magnet/{session_id}/contact",
        json={
            "first_name": "NoPhone",
            "email": "nophone@example.com",
            "phone": None,
            "website": "",
            "form_started_at_ms": 1,
            "phone_capture_variant": "required",
        },
    )
    assert contact_resp.status_code == 400
    assert "Phone number is required" in contact_resp.json()["detail"]


def test_kpi_endpoint_requires_internal_auth():
    client = TestClient(_build_cpa_app())
    response = client.get("/api/cpa/lead-magnet/analytics/kpis")
    assert response.status_code in {401, 403}
