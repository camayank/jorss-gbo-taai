"""Tests for SSOConfigService CRUD."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sso.config_service import SSOConfigService
from sso.models import FirmSSOConfig, SSOProvider


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def service(db):
    return SSOConfigService(db)


def test_get_config_returns_none_when_missing(service, db):
    db.query.return_value.filter.return_value.first.return_value = None
    result = service.get_config(firm_id=uuid4())
    assert result is None


def test_get_enabled_config_returns_none_when_disabled(service, db):
    db.query.return_value.filter.return_value.first.return_value = None
    result = service.get_enabled_config(firm_id=uuid4())
    assert result is None


def test_upsert_creates_new_config(service, db):
    db.query.return_value.filter.return_value.first.return_value = None
    firm_id = uuid4()
    cfg = service.upsert_config(
        firm_id=firm_id,
        provider=SSOProvider.OKTA_OIDC,
        oidc_client_id="client123",
        oidc_client_secret="secret",
        oidc_discovery_url="https://okta.example.com/.well-known/openid-configuration",
        attribute_mapping={"groups": {"admins": "partner"}},
        session_max_age_seconds=28800,
        allow_password_fallback=True,
    )
    assert db.add.called
    assert db.commit.called
    assert cfg.oidc_client_id == "client123"
    assert cfg.provider == SSOProvider.OKTA_OIDC.value


def test_upsert_updates_existing_config(service, db):
    existing = FirmSSOConfig()
    existing.firm_id = uuid4()
    existing.provider = 'saml'
    db.query.return_value.filter.return_value.first.return_value = existing

    service.upsert_config(
        firm_id=existing.firm_id,
        provider=SSOProvider.SAML,
        saml_idp_metadata_url="https://idp.example.com/metadata",
    )
    assert existing.saml_idp_metadata_url == "https://idp.example.com/metadata"
    assert db.commit.called


def test_set_enabled_true(service, db):
    cfg = FirmSSOConfig()
    cfg.is_enabled = False
    db.query.return_value.filter.return_value.first.return_value = cfg
    service.set_enabled(firm_id=uuid4(), enabled=True)
    assert cfg.is_enabled is True
    assert db.commit.called


def test_set_enabled_false(service, db):
    cfg = FirmSSOConfig()
    cfg.is_enabled = True
    db.query.return_value.filter.return_value.first.return_value = cfg
    service.set_enabled(firm_id=uuid4(), enabled=False)
    assert cfg.is_enabled is False


def test_set_enabled_noop_when_no_config(service, db):
    db.query.return_value.filter.return_value.first.return_value = None
    # Should not raise
    service.set_enabled(firm_id=uuid4(), enabled=True)
