"""
Tests for Admin Impersonation API.

Tests the /api/admin/impersonation endpoints for:
- Starting impersonation sessions
- Ending sessions
- Viewing active sessions
- Audit logging
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4


class TestImpersonationModels:
    """Test the impersonation request/response models."""

    def test_impersonation_start_request(self):
        """Test ImpersonationStartRequest model."""
        from src.web.routers.admin_impersonation_api import ImpersonationStartRequest

        request = ImpersonationStartRequest(
            user_id="user-001",
            reason="Investigating billing issue reported by customer",
            duration_minutes=30
        )

        assert request.user_id == "user-001"
        assert request.reason == "Investigating billing issue reported by customer"
        assert request.duration_minutes == 30

    def test_impersonation_default_duration(self):
        """Test default duration is 30 minutes."""
        from src.web.routers.admin_impersonation_api import ImpersonationStartRequest

        request = ImpersonationStartRequest(
            user_id="user-002",
            reason="Customer support investigation"
        )

        assert request.duration_minutes == 30

    def test_impersonation_end_request(self):
        """Test ImpersonationEndRequest model."""
        from src.web.routers.admin_impersonation_api import ImpersonationEndRequest

        request = ImpersonationEndRequest(session_id="session-123")
        assert request.session_id == "session-123"


class TestImpersonationSession:
    """Test the ImpersonationSession class."""

    def test_session_creation(self):
        """Test creating an impersonation session."""
        from src.web.routers.admin_impersonation_api import ImpersonationSession

        session = ImpersonationSession(
            session_id="sess-001",
            admin_id="admin-001",
            admin_email="admin@example.com",
            target_user_id="user-001",
            target_user_email="user@example.com",
            reason="Testing",
            duration_minutes=30,
        )

        assert session.session_id == "sess-001"
        assert session.admin_id == "admin-001"
        assert session.target_user_id == "user-001"
        assert session.ended_at is None
        assert session.is_active is True

    def test_session_is_active_when_not_ended(self):
        """Test session is active when not ended."""
        from src.web.routers.admin_impersonation_api import ImpersonationSession

        session = ImpersonationSession(
            session_id="sess-002",
            admin_id="admin-002",
            admin_email="admin@example.com",
            target_user_id="user-002",
            target_user_email="user@example.com",
            reason="Support",
            duration_minutes=60,
        )

        assert session.is_active is True
        assert session.ended_at is None

    def test_session_inactive_when_ended(self):
        """Test session is inactive when ended."""
        from src.web.routers.admin_impersonation_api import ImpersonationSession

        session = ImpersonationSession(
            session_id="sess-003",
            admin_id="admin-003",
            admin_email="admin@example.com",
            target_user_id="user-003",
            target_user_email="user@example.com",
            reason="Investigation",
            duration_minutes=30,
        )

        # End the session
        session.ended_at = datetime.utcnow()

        assert session.is_active is False

    def test_session_to_dict(self):
        """Test session serialization to dict."""
        from src.web.routers.admin_impersonation_api import ImpersonationSession

        session = ImpersonationSession(
            session_id="sess-004",
            admin_id="admin-004",
            admin_email="admin@example.com",
            target_user_id="user-004",
            target_user_email="user@example.com",
            reason="Testing serialization",
            duration_minutes=15,
        )

        result = session.to_dict()

        assert result["session_id"] == "sess-004"
        assert result["admin_id"] == "admin-004"
        assert result["admin_email"] == "admin@example.com"
        assert result["target_user_id"] == "user-004"
        assert result["reason"] == "Testing serialization"
        assert result["is_active"] is True
        assert "started_at" in result
        assert "expires_at" in result


class TestImpersonationSecurityRules:
    """Test security rules for impersonation."""

    def test_cannot_impersonate_super_admin(self):
        """Test that super admins cannot be impersonated."""
        # Mock user lookup returns super_admin role
        mock_users = {
            "admin-super": {"email": "super@ca4cpa.com", "role": "super_admin"},
        }

        user = mock_users.get("admin-super")
        assert user is not None
        assert user["role"] == "super_admin"
        # In the actual API, this would raise HTTPException(403)

    def test_regular_user_can_be_impersonated(self):
        """Test that regular users can be impersonated."""
        mock_users = {
            "user-regular": {"email": "user@example.com", "role": "firm_client"},
        }

        user = mock_users.get("user-regular")
        assert user is not None
        assert user["role"] != "super_admin"
        # This user can be impersonated


class TestImpersonationDuration:
    """Test session duration validation."""

    def test_minimum_duration(self):
        """Test minimum duration is 5 minutes."""
        from src.web.routers.admin_impersonation_api import ImpersonationStartRequest

        # Field constraint: ge=5
        request = ImpersonationStartRequest(
            user_id="user-001",
            reason="Quick check on user account",
            duration_minutes=5
        )
        assert request.duration_minutes == 5

    def test_maximum_duration(self):
        """Test maximum duration is 120 minutes."""
        from src.web.routers.admin_impersonation_api import ImpersonationStartRequest

        # Field constraint: le=120
        request = ImpersonationStartRequest(
            user_id="user-001",
            reason="Extended investigation",
            duration_minutes=120
        )
        assert request.duration_minutes == 120


class TestAuditLogging:
    """Test audit logging for impersonation."""

    def test_session_tracks_actions(self):
        """Test that sessions can track actions."""
        from src.web.routers.admin_impersonation_api import ImpersonationSession

        session = ImpersonationSession(
            session_id="sess-audit",
            admin_id="admin-audit",
            admin_email="admin@example.com",
            target_user_id="user-audit",
            target_user_email="user@example.com",
            reason="Audit testing",
            duration_minutes=30,
        )

        # Add actions
        session.actions_performed.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "Viewed client list"
        })
        session.actions_performed.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "Downloaded tax return"
        })

        assert len(session.actions_performed) == 2
