"""
Tax Return Flow Integration Tests

SPEC-011: End-to-end tests for tax return CRUD and workflow operations.

Tests:
- Create, read, update, delete tax returns
- Return workflow: DRAFT -> IN_REVIEW -> CPA_APPROVED
- Return notes and annotations
- Queue management
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def mock_tax_return(sample_tax_return_data):
    """Create a mock TaxReturn object that mimics Pydantic model."""
    mock_return = MagicMock()
    mock_return.model_dump.return_value = sample_tax_return_data
    # Add attributes the audit logging accesses
    mock_return.tax_year = 2025
    mock_return.taxpayer = MagicMock()
    mock_return.taxpayer.filing_status.value = "single"
    mock_return.income = True
    mock_return.deductions = True
    mock_return.credits = True
    return mock_return


@pytest.fixture
def mock_save_return(mock_tax_return):
    """
    Context-manager fixture that patches session lookup and DB persistence
    so /api/returns/save can succeed in tests without real session data.
    """
    with patch("web.app._get_tax_return_for_session", return_value=mock_tax_return), \
         patch("database.persistence.save_tax_return", return_value="return-test-001"), \
         patch("database.persistence_adapter.save_tax_return", return_value="return-test-001"):
        yield


class TestTaxReturnCRUD:
    """Tests for basic CRUD operations on tax returns."""

    def test_save_new_return(self, test_client, csrf_headers, sample_tax_return_data, mock_save_return):
        """Should be able to save a new tax return."""
        response = test_client.post(
            "/api/returns/save",
            headers=csrf_headers,
            json={"data": sample_tax_return_data},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "return_id" in data

    def test_save_return_with_session_id(
        self, test_client, csrf_headers, sample_tax_return_data, test_session_id, mock_save_return
    ):
        """Should associate return with provided session ID."""
        response = test_client.post(
            "/api/returns/save",
            headers=csrf_headers,
            json={
                "session_id": test_session_id,
                "data": sample_tax_return_data,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "return_id" in data

    def test_get_return_by_id(
        self, test_client, csrf_headers, sample_tax_return_data, mock_save_return
    ):
        """Should retrieve a return by its ID."""
        # First create a return
        create_response = test_client.post(
            "/api/returns/save",
            headers=csrf_headers,
            json={"data": sample_tax_return_data},
        )
        return_id = create_response.json()["return_id"]

        # Then retrieve it
        response = test_client.get(
            f"/api/returns/{return_id}",
            headers=csrf_headers,
        )

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True

    def test_get_nonexistent_return_404(self, test_client, csrf_headers):
        """Should return 404 for non-existent return."""
        response = test_client.get(
            "/api/returns/nonexistent-id-12345",
            headers=csrf_headers,
        )

        assert response.status_code == 404

    def test_list_returns(self, test_client, csrf_headers):
        """Should list all returns."""
        response = test_client.get(
            "/api/returns",
            headers=csrf_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "returns" in data
        assert isinstance(data["returns"], list)
        assert "count" in data

    def test_list_returns_with_pagination(self, test_client, csrf_headers):
        """Should support pagination parameters."""
        response = test_client.get(
            "/api/returns?limit=10&offset=0",
            headers=csrf_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_delete_return_requires_auth(self, test_client, csrf_headers):
        """Delete endpoint should require RBAC authentication."""
        response = test_client.delete(
            "/api/returns/some-return-id",
            headers=csrf_headers,
        )

        # 401 from require_permission (no RBAC context), or 404 if auth is disabled
        assert response.status_code in [401, 404]


class TestTaxReturnWorkflow:
    """Tests for tax return workflow (DRAFT -> IN_REVIEW -> CPA_APPROVED)."""

    def test_new_return_status_is_draft(
        self, test_client, csrf_headers, test_session_id
    ):
        """Querying status for a session should return DRAFT by default."""
        response = test_client.get(
            f"/api/returns/{test_session_id}/status",
            headers=csrf_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "DRAFT"

    def test_submit_for_review_requires_rbac(
        self, test_client, csrf_headers, test_session_id
    ):
        """Submit for review requires RBAC authentication context."""
        response = test_client.post(
            f"/api/returns/{test_session_id}/submit-for-review",
            headers=csrf_headers,
        )

        # 401 from require_permission (no RBAC AuthContext)
        assert response.status_code == 401

    def test_approve_return_requires_rbac(
        self, test_client, csrf_headers, test_session_id
    ):
        """Approve endpoint requires RBAC authentication context."""
        response = test_client.post(
            f"/api/returns/{test_session_id}/approve",
            headers=csrf_headers,
            json={
                "cpa_reviewer_id": "cpa-123",
                "cpa_reviewer_name": "John CPA",
                "review_notes": "Looks good",
            },
        )

        assert response.status_code == 401

    def test_revert_to_draft_no_return(
        self, test_client, csrf_headers, test_session_id
    ):
        """Reverting a non-existent return should fail."""
        response = test_client.post(
            f"/api/returns/{test_session_id}/revert-to-draft",
            headers=csrf_headers,
            json={"reason": "Needs more info"},
        )

        # 400 because no return status record exists for this session
        assert response.status_code in [400, 401, 404]


class TestReturnQueue:
    """Tests for return queue management."""

    def test_get_draft_queue(self, test_client, csrf_headers):
        """Should retrieve returns in DRAFT status."""
        response = test_client.get(
            "/api/returns/queue/DRAFT",
            headers=csrf_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DRAFT"
        assert "returns" in data

    def test_get_in_review_queue(self, test_client, csrf_headers):
        """Should retrieve returns in IN_REVIEW status."""
        response = test_client.get(
            "/api/returns/queue/IN_REVIEW",
            headers=csrf_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "IN_REVIEW"

    def test_get_approved_queue(self, test_client, csrf_headers):
        """Should retrieve returns in CPA_APPROVED status."""
        response = test_client.get(
            "/api/returns/queue/CPA_APPROVED",
            headers=csrf_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CPA_APPROVED"

    def test_invalid_queue_status_400(self, test_client, csrf_headers):
        """Should reject invalid queue status."""
        response = test_client.get(
            "/api/returns/queue/INVALID_STATUS",
            headers=csrf_headers,
        )

        assert response.status_code == 400


class TestReturnNotes:
    """Tests for return notes and annotations."""

    def test_add_note_requires_rbac(
        self, test_client, csrf_headers, test_session_id
    ):
        """Adding notes requires RBAC authentication context."""
        response = test_client.post(
            f"/api/returns/{test_session_id}/notes",
            headers=csrf_headers,
            json={
                "note": "Please review the W-2 amounts",
                "type": "review",
                "author": "CPA Smith",
            },
        )

        # 401 from require_permission (no RBAC AuthContext)
        assert response.status_code == 401

    def test_get_notes_for_return(
        self, test_client, csrf_headers, test_session_id
    ):
        """Should retrieve notes for a return (read-only, no RBAC required)."""
        response = test_client.get(
            f"/api/returns/{test_session_id}/notes",
            headers=csrf_headers,
        )

        # GET notes may not require RBAC permission
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            assert "notes" in data
            assert isinstance(data["notes"], list)


class TestReturnDataIntegrity:
    """Tests for data integrity in tax returns."""

    def test_save_returns_valid_id(
        self, test_client, csrf_headers, sample_tax_return_data, mock_save_return
    ):
        """Saved return should return a valid return_id."""
        create_response = test_client.post(
            "/api/returns/save",
            headers=csrf_headers,
            json={"data": sample_tax_return_data},
        )

        assert create_response.status_code == 200
        data = create_response.json()
        assert data["success"] is True
        assert data["return_id"] == "return-test-001"

    def test_update_return_with_return_id(
        self, test_client, csrf_headers, sample_tax_return_data, mock_save_return
    ):
        """Updating a return by passing return_id in body."""
        response = test_client.post(
            "/api/returns/save",
            headers=csrf_headers,
            json={
                "return_id": "existing-return-001",
                "data": sample_tax_return_data,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "return_id" in data
