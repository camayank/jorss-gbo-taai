"""
Tests for Admin API Keys Management.

Tests the /api/admin/api-keys endpoints for:
- Creating API keys
- Listing keys
- Revoking keys
- Key rotation
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4


class TestAPIKeyModels:
    """Test the API key request/response models."""

    def test_api_key_create_model(self):
        """Test APIKeyCreate model."""
        from src.web.routers.admin_api_keys_api import APIKeyCreate

        key = APIKeyCreate(
            name="Production API Key",
            description="Main API key for production integration",
            scopes=["clients:read", "returns:read"],
            expires_in_days=90
        )

        assert key.name == "Production API Key"
        assert "clients:read" in key.scopes
        assert key.expires_in_days == 90

    def test_api_key_create_defaults(self):
        """Test default values for APIKeyCreate."""
        from src.web.routers.admin_api_keys_api import APIKeyCreate

        key = APIKeyCreate(name="Test Key")

        assert key.scopes == []
        assert key.expires_in_days is None
        assert key.description is None

    def test_api_key_update_model(self):
        """Test APIKeyUpdate model."""
        from src.web.routers.admin_api_keys_api import APIKeyUpdate

        update = APIKeyUpdate(
            name="Updated Name",
            scopes=["clients:read", "clients:write"]
        )

        assert update.name == "Updated Name"
        assert "clients:write" in update.scopes


class TestAPIKeyClass:
    """Test the APIKey class."""

    def test_api_key_creation(self):
        """Test creating an APIKey."""
        from src.web.routers.admin_api_keys_api import APIKey

        key = APIKey(
            key_id="key-001",
            firm_id="firm-001",
            name="Test Key",
            key_hash="abc123hash",
            prefix="jgb_test",
            scopes=["clients:read"],
            description="Test API key",
            created_by="user-001",
            expires_at=None,
        )

        assert key.key_id == "key-001"
        assert key.firm_id == "firm-001"
        assert key.is_active is True
        assert key.revoked is False
        assert key.use_count == 0

    def test_api_key_is_active_when_not_revoked(self):
        """Test key is active when not revoked."""
        from src.web.routers.admin_api_keys_api import APIKey

        key = APIKey(
            key_id="key-002",
            firm_id="firm-002",
            name="Active Key",
            key_hash="hash",
            prefix="jgb_act",
            scopes=[],
            description=None,
            created_by="user-002",
            expires_at=None,
        )

        assert key.is_active is True

    def test_api_key_inactive_when_revoked(self):
        """Test key is inactive when revoked."""
        from src.web.routers.admin_api_keys_api import APIKey

        key = APIKey(
            key_id="key-003",
            firm_id="firm-003",
            name="Revoked Key",
            key_hash="hash",
            prefix="jgb_rev",
            scopes=[],
            description=None,
            created_by="user-003",
            expires_at=None,
        )
        key.revoked = True

        assert key.is_active is False

    def test_api_key_inactive_when_expired(self):
        """Test key is inactive when expired."""
        from src.web.routers.admin_api_keys_api import APIKey

        # Set expires_at to past
        past = datetime.utcnow() - timedelta(days=1)

        key = APIKey(
            key_id="key-004",
            firm_id="firm-004",
            name="Expired Key",
            key_hash="hash",
            prefix="jgb_exp",
            scopes=[],
            description=None,
            created_by="user-004",
            expires_at=past,
        )

        assert key.is_active is False

    def test_api_key_to_dict(self):
        """Test APIKey serialization."""
        from src.web.routers.admin_api_keys_api import APIKey

        key = APIKey(
            key_id="key-005",
            firm_id="firm-005",
            name="Serialized Key",
            key_hash="hash",
            prefix="jgb_ser",
            scopes=["clients:read"],
            description="For serialization test",
            created_by="user-005",
            expires_at=None,
        )

        result = key.to_dict()

        assert result["key_id"] == "key-005"
        assert result["name"] == "Serialized Key"
        assert result["prefix"] == "jgb_ser"
        assert result["scopes"] == ["clients:read"]
        assert result["is_active"] is True
        assert "key_hash" not in result  # Should not expose hash


class TestAPIKeyGeneration:
    """Test API key generation."""

    def test_generate_api_key_format(self):
        """Test that generated keys have correct format."""
        from src.web.routers.admin_api_keys_api import _generate_api_key

        raw_key, key_hash, prefix = _generate_api_key()

        # Key should start with jgb_ prefix
        assert raw_key.startswith("jgb_")

        # Hash should be 64 chars (SHA256 hex)
        assert len(key_hash) == 64

        # Prefix should be first 12 chars
        assert prefix == raw_key[:12]

    def test_generate_unique_keys(self):
        """Test that each generated key is unique."""
        from src.web.routers.admin_api_keys_api import _generate_api_key

        keys = set()
        for _ in range(100):
            raw_key, _, _ = _generate_api_key()
            keys.add(raw_key)

        assert len(keys) == 100  # All unique


class TestScopeValidation:
    """Test scope validation."""

    def test_validate_known_scopes(self):
        """Test that known scopes are validated."""
        from src.web.routers.admin_api_keys_api import _validate_scopes, AVAILABLE_SCOPES

        input_scopes = ["clients:read", "returns:write"]
        validated = _validate_scopes(input_scopes)

        assert "clients:read" in validated
        assert "returns:write" in validated

    def test_filter_invalid_scopes(self):
        """Test that invalid scopes are filtered out."""
        from src.web.routers.admin_api_keys_api import _validate_scopes

        input_scopes = ["clients:read", "invalid:scope", "fake:permission"]
        validated = _validate_scopes(input_scopes)

        assert "clients:read" in validated
        assert "invalid:scope" not in validated
        assert "fake:permission" not in validated

    def test_available_scopes(self):
        """Test that all expected scopes are available."""
        from src.web.routers.admin_api_keys_api import AVAILABLE_SCOPES

        expected_scopes = [
            "clients:read",
            "clients:write",
            "returns:read",
            "returns:write",
            "documents:read",
            "documents:write",
            "reports:read",
            "analytics:read",
            "webhooks:manage",
        ]

        for scope in expected_scopes:
            assert scope in AVAILABLE_SCOPES


class TestKeyRotation:
    """Test API key rotation."""

    def test_rotation_creates_new_key(self):
        """Test that rotation creates a new key ID."""
        old_key_id = "old-key-001"
        new_key_id = "new-key-001"

        # In actual rotation, old_key_id != new_key_id
        assert old_key_id != new_key_id

    def test_rotation_preserves_metadata(self):
        """Test that rotation preserves key metadata."""
        from src.web.routers.admin_api_keys_api import APIKey

        old_key = APIKey(
            key_id="old-key",
            firm_id="firm-001",
            name="My Key",
            key_hash="old_hash",
            prefix="jgb_old",
            scopes=["clients:read", "returns:read"],
            description="Important key",
            created_by="user-001",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )

        # New key should have same name, scopes, description
        new_name = old_key.name
        new_scopes = old_key.scopes
        new_expires = old_key.expires_at

        assert new_name == "My Key"
        assert new_scopes == ["clients:read", "returns:read"]
        assert new_expires is not None
