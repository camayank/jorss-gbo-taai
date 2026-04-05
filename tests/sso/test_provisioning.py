"""Tests for JIT provisioning service."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sso.provisioning import JITProvisioningService


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def service(db):
    return JITProvisioningService(db)


def test_provision_creates_new_user(service, db):
    db.query.return_value.filter.return_value.first.return_value = None
    firm_id = uuid4()

    user = service.provision_or_update(
        firm_id=firm_id,
        email="newuser@firm.com",
        first_name="New",
        last_name="User",
        role="staff",
        sso_provider="okta_oidc",
        sso_subject_id="abc123",
    )

    assert db.add.called
    assert db.commit.called
    assert user.email == "newuser@firm.com"
    assert user.role == "staff"
    assert user.password_hash is None
    assert user.is_email_verified is True


def test_provision_updates_existing_user(service, db):
    from admin_panel.models.user import User
    existing = User()
    existing.user_id = uuid4()
    existing.email = "existing@firm.com"
    existing.role = "staff"
    existing.first_name = "Old"
    existing.last_name = "Name"

    db.query.return_value.filter.return_value.first.return_value = existing

    user = service.provision_or_update(
        firm_id=uuid4(),
        email="existing@firm.com",
        first_name="New",
        last_name="Name",
        role="partner",
        sso_provider="saml",
        sso_subject_id="saml-sub",
    )

    assert user.first_name == "New"
    assert user.role == "partner"
    assert db.commit.called


def test_provision_uses_email_prefix_when_no_first_name(service, db):
    db.query.return_value.filter.return_value.first.return_value = None
    user = service.provision_or_update(
        firm_id=uuid4(),
        email="jsmith@firm.com",
        first_name="",
        last_name="",
        role="staff",
        sso_provider="saml",
        sso_subject_id="x",
    )
    assert user.first_name == "jsmith"


def test_provision_sets_last_login_at(service, db):
    db.query.return_value.filter.return_value.first.return_value = None
    from admin_panel.models.user import User
    import datetime

    user = service.provision_or_update(
        firm_id=uuid4(),
        email="user@firm.com",
        first_name="A",
        last_name="B",
        role="staff",
        sso_provider="okta_oidc",
        sso_subject_id="sub",
    )
    assert user.last_login_at is not None
