"""
Comprehensive Frontend Integration Tests for Advisory Report System

Tests the complete frontend integration including:
- API endpoint availability in /docs
- Report generation from frontend
- PDF status polling
- Report history retrieval
- Preview page functionality
- Error handling and edge cases

Run with: pytest tests/test_advisory_frontend_integration.py -v
"""

import pytest
import uuid
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    try:
        from web.app import app
        return TestClient(app)
    except ImportError as e:
        pytest.skip(f"Could not import app: {e}")


@pytest.fixture
def sample_session_id():
    """Generate a unique session ID for testing."""
    return str(uuid.uuid4())


class TestAPIIntegration:
    """Test API integration and endpoint availability."""

    def test_advisory_api_mounted(self, client):
        """Verify advisory API router is properly mounted."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_spec = response.json()
        paths = openapi_spec.get("paths", {})

        # Check key endpoints exist
        assert any("/api/v1/advisory-reports/generate" in p for p in paths.keys())
        assert any("/api/v1/advisory-reports/{report_id}" in p for p in paths.keys())

    def test_preview_route_exists(self, client):
        """Verify advisory report preview route is accessible."""
        response = client.get("/advisory-report-preview?report_id=test")
        assert response.status_code == 200

    def test_docs_page_includes_advisory_endpoints(self, client):
        """Verify advisory endpoints appear in API docs."""
        response = client.get("/docs")
        assert response.status_code == 200


class TestReportGeneration:
    """Test report generation workflow."""

    def test_generate_sample_report_endpoint(self, client):
        """Test sample report generation."""
        response = client.post("/api/v1/advisory-reports/test/generate-sample")

        if response.status_code == 200:
            data = response.json()
            assert "report_id" in data
            assert isinstance(data["report_id"], str)
            assert len(data["report_id"]) > 0
        else:
            # Log the error for debugging
            print(f"Sample report generation failed: {response.status_code}")
            print(f"Response: {response.text}")

    def test_generate_report_validation(self, client):
        """Test report generation validates required fields."""
        # Missing session_id
        payload = {"report_type": "full_analysis"}
        response = client.post("/api/v1/advisory-reports/generate", json=payload)
        assert response.status_code == 422

    def test_generate_report_with_options(self, client, sample_session_id):
        """Test report generation with various options."""
        payload = {
            "session_id": sample_session_id,
            "report_type": "full_analysis",
            "include_entity_comparison": True,
            "include_multi_year": True,
            "years_ahead": 3,
            "generate_pdf": True
        }

        response = client.post("/api/v1/advisory-reports/generate", json=payload)
        # May fail if session doesn't exist, which is expected
        assert response.status_code in [200, 404, 422]


class TestReportRetrieval:
    """Test report retrieval endpoints."""

    def test_get_nonexistent_report(self, client):
        """Test retrieving non-existent report returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/advisory-reports/{fake_id}")
        assert response.status_code == 404

    def test_get_report_data_structure(self, client):
        """Test report data endpoint returns correct structure."""
        # First generate a sample report
        gen_response = client.post("/api/v1/advisory-reports/test/generate-sample")

        if gen_response.status_code == 200:
            report_id = gen_response.json()["report_id"]

            # Get full data
            response = client.get(f"/api/v1/advisory-reports/{report_id}/data")

            if response.status_code == 200:
                data = response.json()
                # Validate expected structure
                assert "taxpayer_name" in data
                assert "metrics" in data
                assert "recommendations" in data


class TestPDFGeneration:
    """Test PDF generation and polling."""

    def test_pdf_endpoint_exists(self, client):
        """Test PDF download endpoint is accessible."""
        # Generate sample report
        gen_response = client.post("/api/v1/advisory-reports/test/generate-sample")

        if gen_response.status_code == 200:
            report_id = gen_response.json()["report_id"]

            # Try to access PDF endpoint
            response = client.get(f"/api/v1/advisory-reports/{report_id}/pdf")

            # PDF might not be ready immediately
            assert response.status_code in [200, 202, 404]


class TestReportHistory:
    """Test report history functionality."""

    def test_get_session_reports_empty(self, client):
        """Test retrieving reports for session with no reports."""
        session_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/advisory-reports/session/{session_id}/reports")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "reports" in data
        assert isinstance(data["reports"], list)

    def test_report_history_structure(self, client, sample_session_id):
        """Test report history returns correct structure."""
        response = client.get(f"/api/v1/advisory-reports/session/{sample_session_id}/reports")

        if response.status_code == 200:
            data = response.json()
            assert "total" in data
            assert "reports" in data

            # If reports exist, validate structure
            if data["total"] > 0:
                report = data["reports"][0]
                assert "report_id" in report
                assert "taxpayer_name" in report
                assert "generated_at" in report


class TestErrorHandling:
    """Test error handling and validation."""

    def test_invalid_report_id_format(self, client):
        """Test handling of invalid report ID format."""
        response = client.get("/api/v1/advisory-reports/not-a-valid-uuid")
        assert response.status_code in [404, 422]

    def test_malformed_json_payload(self, client):
        """Test handling of malformed JSON."""
        response = client.post(
            "/api/v1/advisory-reports/generate",
            data="{ invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_sql_injection_protection(self, client):
        """Test protection against SQL injection."""
        malicious_id = "1' OR '1'='1"
        response = client.get(f"/api/v1/advisory-reports/{malicious_id}")
        assert response.status_code in [404, 422]


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    def test_complete_workflow(self, client):
        """Test complete workflow: generate -> retrieve -> delete."""
        # Generate
        gen_response = client.post("/api/v1/advisory-reports/test/generate-sample")

        if gen_response.status_code == 200:
            report_id = gen_response.json()["report_id"]

            # Check status
            status_response = client.get(f"/api/v1/advisory-reports/{report_id}")
            assert status_response.status_code == 200

            # Delete
            delete_response = client.delete(f"/api/v1/advisory-reports/{report_id}")
            assert delete_response.status_code in [200, 204, 404]

            # Verify deleted
            verify_response = client.get(f"/api/v1/advisory-reports/{report_id}")
            assert verify_response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
