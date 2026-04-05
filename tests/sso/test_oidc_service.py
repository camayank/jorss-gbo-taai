"""Tests for OIDCService and group→role mapping."""
import pytest
from sso.oidc_service import OIDCService, OIDCUserInfo, map_groups_to_role


def test_map_groups_to_role_partner():
    mapping = {"groups": {"tax-admins": "partner", "staff": "staff"}}
    assert map_groups_to_role(["tax-admins", "other"], mapping) == "partner"


def test_map_groups_to_role_staff():
    mapping = {"groups": {"tax-admins": "partner", "staff": "staff"}}
    assert map_groups_to_role(["staff"], mapping) == "staff"


def test_map_groups_to_role_default_staff_when_no_match():
    mapping = {"groups": {"admins": "partner"}}
    assert map_groups_to_role(["unknown-group"], mapping) == "staff"


def test_map_groups_to_role_default_staff_when_empty_mapping():
    assert map_groups_to_role(["any-group"], {}) == "staff"


def test_map_groups_to_role_empty_groups():
    mapping = {"groups": {"admins": "partner"}}
    assert map_groups_to_role([], mapping) == "staff"


def test_oidc_user_info_defaults():
    info = OIDCUserInfo(
        sub="abc123",
        email="user@example.com",
        name="Jane Doe",
    )
    assert info.email == "user@example.com"
    assert info.groups == []
    assert info.first_name is None


def test_oidc_user_info_with_groups():
    info = OIDCUserInfo(
        sub="abc123",
        email="admin@example.com",
        name="Jane Doe",
        groups=["tax-admins", "all-staff"],
        first_name="Jane",
        last_name="Doe",
    )
    assert info.groups == ["tax-admins", "all-staff"]
    assert info.first_name == "Jane"


@pytest.mark.asyncio
async def test_get_authorization_url_returns_url_and_state():
    from unittest.mock import patch, AsyncMock, MagicMock

    svc = OIDCService(
        client_id="cid",
        client_secret="cs",
        discovery_url="https://okta.example.com/.well-known/openid-configuration",
        redirect_uri="https://app.example.com/api/core/auth/sso/oidc/callback",
    )

    mock_meta = {
        "authorization_endpoint": "https://okta.example.com/authorize",
        "token_endpoint": "https://okta.example.com/token",
        "userinfo_endpoint": "https://okta.example.com/userinfo",
    }

    with patch.object(svc, '_fetch_metadata', new_callable=AsyncMock, return_value=mock_meta):
        mock_client = MagicMock()
        mock_client.create_authorization_url.return_value = (
            "https://okta.example.com/authorize?response_type=code&state=xyz",
            "xyz",
        )
        mock_client.authorization_endpoint = mock_meta["authorization_endpoint"]

        with patch.object(svc, '_get_client', new_callable=AsyncMock, return_value=mock_client):
            url, state = await svc.get_authorization_url()

    assert "okta.example.com" in url
    assert len(state) > 0
