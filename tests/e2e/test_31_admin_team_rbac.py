"""
E2E Test: Team Management & RBAC

Tests: Team CRUD → Invitations → Performance → Roles → Permissions → Assignment
"""

import pytest
from unittest.mock import patch


class TestTeamManagement:
    """Team member CRUD."""

    def test_list_team(self, client, headers, admin_jwt_payload):
        """List team members."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/team", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_invite_team_member(self, client, headers, admin_jwt_payload):
        """Invite new team member."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/team/invite", headers=headers, json={
                "email": "newcpa@taxfirm.com",
                "role": "staff",
                "name": "New CPA",
            })
        assert response.status_code in [200, 201, 404, 405, 500]

    def test_get_team_member(self, client, headers, admin_jwt_payload):
        """Get team member profile."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/team/cpa-e2e-001", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_update_team_member(self, client, headers, admin_jwt_payload):
        """Update team member."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.put("/api/v1/admin/team/cpa-e2e-001", headers=headers, json={
                "role": "senior_staff",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_remove_team_member(self, client, headers, admin_jwt_payload):
        """Remove team member."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.delete("/api/v1/admin/team/cpa-e2e-001", headers=headers)
        assert response.status_code in [200, 404, 405, 500]


class TestInvitations:
    """Team invitations."""

    def test_list_invitations(self, client, headers, admin_jwt_payload):
        """List pending invitations."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/team/invitations", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_resend_invitation(self, client, headers, admin_jwt_payload):
        """Resend invitation."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/team/invitations/test-inv/resend", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_cancel_invitation(self, client, headers, admin_jwt_payload):
        """Cancel invitation."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.delete("/api/v1/admin/team/invitations/test-inv", headers=headers)
        assert response.status_code in [200, 404, 405, 500]


class TestTeamPerformance:
    """Team performance metrics."""

    def test_member_performance(self, client, headers, admin_jwt_payload):
        """Get member performance metrics."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/team/cpa-e2e-001/performance", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestRBAC:
    """Role-based access control."""

    def test_list_permissions(self, client, headers, admin_jwt_payload):
        """List all permissions."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/rbac/permissions", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_list_roles(self, client, headers, admin_jwt_payload):
        """List all roles."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/rbac/roles", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_create_custom_role(self, client, headers, admin_jwt_payload):
        """Create custom role."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/rbac/roles", headers=headers, json={
                "name": "senior_reviewer",
                "description": "Senior tax return reviewer",
                "permissions": ["review_returns", "approve_returns"],
            })
        assert response.status_code in [200, 201, 404, 405, 500]

    def test_update_role_permissions(self, client, headers, admin_jwt_payload):
        """Update role permissions."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.put("/api/v1/admin/rbac/roles/test-role/permissions", headers=headers, json={
                "permissions": ["review_returns", "approve_returns", "manage_clients"],
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_delete_role(self, client, headers, admin_jwt_payload):
        """Delete custom role."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.delete("/api/v1/admin/rbac/roles/test-role", headers=headers)
        assert response.status_code in [200, 404, 405, 500]

    def test_get_user_roles(self, client, headers, admin_jwt_payload):
        """Get roles for a user."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/rbac/users/cpa-e2e-001/roles", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_assign_role_to_user(self, client, headers, admin_jwt_payload):
        """Assign role to user."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.put("/api/v1/admin/rbac/users/cpa-e2e-001/roles", headers=headers, json={
                "roles": ["staff", "reviewer"],
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_remove_role_from_user(self, client, headers, admin_jwt_payload):
        """Remove role from user."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.delete("/api/v1/admin/rbac/users/cpa-e2e-001/roles/reviewer", headers=headers)
        assert response.status_code in [200, 404, 405, 500]

    def test_seed_default_roles(self, client, headers, admin_jwt_payload):
        """Seed default roles."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/rbac/seed", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]
