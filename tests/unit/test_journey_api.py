"""Tests for journey API endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from web.routers.journey_api import router


class TestJourneyProgressEndpoint:

    def test_returns_progress(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("web.routers.journey_api._get_orchestrator") as mock_orch:
            mock_instance = MagicMock()
            mock_instance.get_progress.return_value = {
                "current_stage": "profiling",
                "stages": [],
                "completion_pct": 12,
            }
            mock_orch.return_value = mock_instance
            resp = client.get(
                "/api/journey/progress",
                headers={"X-User-ID": "u1", "X-Tenant-ID": "t1"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["current_stage"] == "profiling"


class TestJourneyNextStepEndpoint:

    def test_returns_next_step(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("web.routers.journey_api._get_orchestrator") as mock_orch:
            mock_instance = MagicMock()
            mock_instance.get_next_step.return_value = {
                "action": "upload_documents",
                "message": "Upload your W-2",
                "cta_label": "Upload",
                "cta_url": "/documents",
            }
            mock_orch.return_value = mock_instance
            resp = client.get(
                "/api/journey/next-step",
                headers={"X-User-ID": "u1", "X-Tenant-ID": "t1"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "upload_documents"

    def test_returns_complete_when_no_next_step(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("web.routers.journey_api._get_orchestrator") as mock_orch:
            mock_instance = MagicMock()
            mock_instance.get_next_step.return_value = None
            mock_orch.return_value = mock_instance
            resp = client.get(
                "/api/journey/next-step",
                headers={"X-User-ID": "u1", "X-Tenant-ID": "t1"},
            )
            assert resp.status_code == 200
            assert resp.json()["action"] is None
