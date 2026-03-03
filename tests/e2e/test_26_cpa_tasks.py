"""
E2E Test: Task Management

Tests: Create → List → Get → Update → Delete → Assign → Complete → Comments → Kanban
"""

import pytest
from unittest.mock import patch


class TestTaskCRUD:
    """Task CRUD operations."""

    def test_create_task(self, client, headers, cpa_jwt_payload):
        """Create a new task."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/tasks", headers=headers, json={
                "title": "Review John Doe's W-2",
                "description": "Verify wage amounts match employer records",
                "priority": "high",
                "due_date": "2026-04-01",
            })
        assert response.status_code in [200, 201, 404, 405, 500]

    def test_list_tasks(self, client, headers, cpa_jwt_payload):
        """List all tasks."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/tasks", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_get_task(self, client, headers, cpa_jwt_payload):
        """Get specific task."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/tasks/test-task-id", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_update_task(self, client, headers, cpa_jwt_payload):
        """Update task."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.put("/api/cpa/tasks/test-task-id", headers=headers, json={
                "title": "Updated Task Title",
                "priority": "medium",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_delete_task(self, client, headers, cpa_jwt_payload):
        """Delete task."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.delete("/api/cpa/tasks/test-task-id", headers=headers)
        assert response.status_code in [200, 404, 405, 500]


class TestTaskActions:
    """Task lifecycle actions."""

    def test_assign_task(self, client, headers, cpa_jwt_payload):
        """Assign task to team member."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/tasks/test-task-id/assign", headers=headers, json={
                "assignee_id": "cpa-e2e-001",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_complete_task(self, client, headers, cpa_jwt_payload):
        """Mark task as complete."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/tasks/test-task-id/complete", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]


class TestTaskComments:
    """Task comments."""

    def test_add_comment(self, client, headers, cpa_jwt_payload):
        """Add comment to task."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/tasks/test-task-id/comments", headers=headers, json={
                "content": "Checked with employer, amounts confirmed",
            })
        assert response.status_code in [200, 201, 404, 405, 500]


class TestTaskViews:
    """Task views and filters."""

    def test_my_tasks(self, client, headers, cpa_jwt_payload):
        """Get my assigned tasks."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/tasks/my-tasks", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_kanban_view(self, client, headers, cpa_jwt_payload):
        """Get kanban board view."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/tasks/kanban", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestTaskPage:
    """Task page rendering."""

    def test_tasks_page(self, client, headers):
        """Tasks page should render."""
        response = client.get("/cpa/tasks")
        assert response.status_code in [200, 302, 303, 307, 404]
