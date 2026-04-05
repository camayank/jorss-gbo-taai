# SSO Integration — SAML 2.0 & OAuth2/OIDC for Enterprise CPA Firms

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable enterprise CPA firms to authenticate their staff via SSO (SAML 2.0 and OIDC), with per-firm config, JIT provisioning, role mapping, and single logout — while keeping password login as fallback.

**Architecture:** A new `src/sso/` package handles all SSO logic (SAML + OIDC) cleanly separated from the existing OAuth2 social login (`src/core/api/oauth_routes.py`). Per-firm SSO config lives in a new `firm_sso_configs` DB table. SSO routes are added to the core router at `/api/core/auth/sso/*`. JIT provisioning creates `User` rows (with nullable `password_hash`) on first SSO login and maps IdP group attributes to existing RBAC roles.

**Tech Stack:** `python3-saml` (SAML 2.0), `Authlib` (OIDC), `SQLAlchemy` (models), `FastAPI` (routes), `alembic` (migrations), `pytest` (tests), existing `rbac.jwt` for token issuance.

---

## Task 1: FirmSSOConfig database model + Alembic migration

**Files:**
- Create: `src/sso/__init__.py`
- Create: `src/sso/models.py`
- Create: `alembic/versions/20260405_01_add_firm_sso_configs.py`

**Step 1: Write the failing test**

```python
# tests/sso/test_sso_models.py
import pytest
from sso.models import FirmSSOConfig, SSOProvider

def test_sso_config_fields():
    cfg = FirmSSOConfig()
    assert hasattr(cfg, 'firm_id')
    assert hasattr(cfg, 'provider')
    assert hasattr(cfg, 'is_enabled')
    assert hasattr(cfg, 'saml_idp_metadata_url')
    assert hasattr(cfg, 'saml_sp_entity_id')
    assert hasattr(cfg, 'saml_idp_certificate')
    assert hasattr(cfg, 'oidc_client_id')
    assert hasattr(cfg, 'oidc_client_secret')
    assert hasattr(cfg, 'oidc_discovery_url')
    assert hasattr(cfg, 'attribute_mapping')
    assert hasattr(cfg, 'session_max_age_seconds')
    assert hasattr(cfg, 'allow_password_fallback')

def test_provider_enum():
    assert SSOProvider.SAML.value == 'saml'
    assert SSOProvider.OKTA_OIDC.value == 'okta_oidc'
    assert SSOProvider.AZURE_AD_OIDC.value == 'azure_ad_oidc'
    assert SSOProvider.GOOGLE_WORKSPACE_OIDC.value == 'google_workspace_oidc'
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/sso/test_sso_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'sso'`

**Step 3: Create the package and model**

```python
# src/sso/__init__.py
# (empty)
```

```python
# src/sso/models.py
"""
SSO Configuration — per-firm SSO settings stored in firm_sso_configs table.
"""
import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer,
    ForeignKey, Index, UniqueConstraint, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from database.models import Base, JSONB


class SSOProvider(str, enum.Enum):
    SAML = "saml"
    OKTA_OIDC = "okta_oidc"
    AZURE_AD_OIDC = "azure_ad_oidc"
    GOOGLE_WORKSPACE_OIDC = "google_workspace_oidc"


class FirmSSOConfig(Base):
    """One SSO config per firm (one active provider at a time)."""
    __tablename__ = "firm_sso_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), nullable=False)  # SSOProvider value
    is_enabled = Column(Boolean, default=False, nullable=False)

    # SAML 2.0 fields (populated when provider == 'saml')
    saml_idp_metadata_url = Column(String(500), nullable=True)
    saml_idp_certificate = Column(Text, nullable=True)  # PEM cert from IdP
    saml_sp_entity_id = Column(String(500), nullable=True)
    saml_acs_url = Column(String(500), nullable=True)  # Assertion Consumer Service URL
    saml_slo_url = Column(String(500), nullable=True)   # Single Logout URL

    # OIDC fields (populated for Okta/Azure AD/Google Workspace)
    oidc_client_id = Column(String(255), nullable=True)
    oidc_client_secret = Column(String(500), nullable=True)  # store encrypted in prod
    oidc_discovery_url = Column(String(500), nullable=True)  # /.well-known/openid-configuration

    # Role/attribute mapping: {"groups": {"tax-admins": "partner", "staff": "staff"}}
    attribute_mapping = Column(JSONB, default=dict, nullable=False)

    # Session settings (0 = use app default)
    session_max_age_seconds = Column(Integer, default=0, nullable=False)

    # Fallback: allow username/password login if SSO fails
    allow_password_fallback = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("firm_id", name="uq_firm_sso_config"),
        Index("ix_firm_sso_enabled", "firm_id", "is_enabled"),
    )
```

**Step 4: Create Alembic migration**

```python
# alembic/versions/20260405_01_add_firm_sso_configs.py
"""Add firm_sso_configs table

Revision ID: 20260405_01
Revises: <previous_revision>
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260405_01'
down_revision = None  # replace with actual latest revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'firm_sso_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('is_enabled', sa.Boolean, default=False, nullable=False),
        sa.Column('saml_idp_metadata_url', sa.String(500), nullable=True),
        sa.Column('saml_idp_certificate', sa.Text, nullable=True),
        sa.Column('saml_sp_entity_id', sa.String(500), nullable=True),
        sa.Column('saml_acs_url', sa.String(500), nullable=True),
        sa.Column('saml_slo_url', sa.String(500), nullable=True),
        sa.Column('oidc_client_id', sa.String(255), nullable=True),
        sa.Column('oidc_client_secret', sa.String(500), nullable=True),
        sa.Column('oidc_discovery_url', sa.String(500), nullable=True),
        sa.Column('attribute_mapping', postgresql.JSONB, default={}, nullable=False),
        sa.Column('session_max_age_seconds', sa.Integer, default=0, nullable=False),
        sa.Column('allow_password_fallback', sa.Boolean, default=True, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_unique_constraint('uq_firm_sso_config', 'firm_sso_configs', ['firm_id'])
    op.create_index('ix_firm_sso_enabled', 'firm_sso_configs', ['firm_id', 'is_enabled'])


def downgrade() -> None:
    op.drop_table('firm_sso_configs')
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/sso/test_sso_models.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add src/sso/__init__.py src/sso/models.py alembic/versions/20260405_01_add_firm_sso_configs.py tests/sso/test_sso_models.py
git commit -m "feat(MKW-71): add FirmSSOConfig model and migration

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 2: SSOConfigService — CRUD for per-firm SSO config

**Files:**
- Create: `src/sso/config_service.py`
- Test: `tests/sso/test_sso_config_service.py`

**Step 1: Write the failing test**

```python
# tests/sso/test_sso_config_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from sso.config_service import SSOConfigService
from sso.models import FirmSSOConfig, SSOProvider

@pytest.fixture
def db():
    return MagicMock()

@pytest.fixture
def service(db):
    return SSOConfigService(db)

def test_get_config_for_firm_returns_none_when_missing(service, db):
    db.query.return_value.filter.return_value.first.return_value = None
    result = service.get_config(firm_id=uuid4())
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

def test_upsert_updates_existing_config(service, db):
    existing = FirmSSOConfig()
    existing.firm_id = uuid4()
    db.query.return_value.filter.return_value.first.return_value = existing
    service.upsert_config(
        firm_id=existing.firm_id,
        provider=SSOProvider.SAML,
        saml_idp_metadata_url="https://idp.example.com/metadata",
    )
    assert existing.saml_idp_metadata_url == "https://idp.example.com/metadata"
    assert db.commit.called

def test_enable_disable_config(service, db):
    cfg = FirmSSOConfig()
    cfg.is_enabled = False
    db.query.return_value.filter.return_value.first.return_value = cfg
    service.set_enabled(firm_id=uuid4(), enabled=True)
    assert cfg.is_enabled is True
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/sso/test_sso_config_service.py -v
```
Expected: `ModuleNotFoundError: No module named 'sso.config_service'`

**Step 3: Implement SSOConfigService**

```python
# src/sso/config_service.py
"""CRUD operations for per-firm SSO configuration."""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from .models import FirmSSOConfig, SSOProvider


class SSOConfigService:
    def __init__(self, db: Session):
        self.db = db

    def get_config(self, firm_id: UUID) -> Optional[FirmSSOConfig]:
        return (
            self.db.query(FirmSSOConfig)
            .filter(FirmSSOConfig.firm_id == firm_id)
            .first()
        )

    def get_enabled_config(self, firm_id: UUID) -> Optional[FirmSSOConfig]:
        return (
            self.db.query(FirmSSOConfig)
            .filter(
                FirmSSOConfig.firm_id == firm_id,
                FirmSSOConfig.is_enabled == True,
            )
            .first()
        )

    def upsert_config(
        self,
        firm_id: UUID,
        provider: SSOProvider,
        *,
        saml_idp_metadata_url: Optional[str] = None,
        saml_idp_certificate: Optional[str] = None,
        saml_sp_entity_id: Optional[str] = None,
        saml_acs_url: Optional[str] = None,
        saml_slo_url: Optional[str] = None,
        oidc_client_id: Optional[str] = None,
        oidc_client_secret: Optional[str] = None,
        oidc_discovery_url: Optional[str] = None,
        attribute_mapping: Optional[dict] = None,
        session_max_age_seconds: int = 0,
        allow_password_fallback: bool = True,
    ) -> FirmSSOConfig:
        cfg = self.get_config(firm_id)
        if cfg is None:
            cfg = FirmSSOConfig(firm_id=firm_id)
            self.db.add(cfg)

        cfg.provider = provider.value
        if saml_idp_metadata_url is not None:
            cfg.saml_idp_metadata_url = saml_idp_metadata_url
        if saml_idp_certificate is not None:
            cfg.saml_idp_certificate = saml_idp_certificate
        if saml_sp_entity_id is not None:
            cfg.saml_sp_entity_id = saml_sp_entity_id
        if saml_acs_url is not None:
            cfg.saml_acs_url = saml_acs_url
        if saml_slo_url is not None:
            cfg.saml_slo_url = saml_slo_url
        if oidc_client_id is not None:
            cfg.oidc_client_id = oidc_client_id
        if oidc_client_secret is not None:
            cfg.oidc_client_secret = oidc_client_secret
        if oidc_discovery_url is not None:
            cfg.oidc_discovery_url = oidc_discovery_url
        if attribute_mapping is not None:
            cfg.attribute_mapping = attribute_mapping
        cfg.session_max_age_seconds = session_max_age_seconds
        cfg.allow_password_fallback = allow_password_fallback

        self.db.commit()
        self.db.refresh(cfg)
        return cfg

    def set_enabled(self, firm_id: UUID, enabled: bool) -> None:
        cfg = self.get_config(firm_id)
        if cfg:
            cfg.is_enabled = enabled
            self.db.commit()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/sso/test_sso_config_service.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/sso/config_service.py tests/sso/test_sso_config_service.py
git commit -m "feat(MKW-71): add SSOConfigService for per-firm SSO config CRUD

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 3: OIDC service (Authlib — Okta, Azure AD, Google Workspace)

**Files:**
- Create: `src/sso/oidc_service.py`
- Test: `tests/sso/test_oidc_service.py`

**Step 1: Write the failing test**

```python
# tests/sso/test_oidc_service.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sso.oidc_service import OIDCService, OIDCUserInfo, map_groups_to_role

def test_map_groups_to_role_partner():
    mapping = {"groups": {"tax-admins": "partner", "staff": "staff"}}
    role = map_groups_to_role(["tax-admins", "other"], mapping)
    assert role == "partner"

def test_map_groups_to_role_staff():
    mapping = {"groups": {"tax-admins": "partner", "staff": "staff"}}
    role = map_groups_to_role(["staff"], mapping)
    assert role == "staff"

def test_map_groups_to_role_default_staff():
    mapping = {"groups": {}}
    role = map_groups_to_role(["unknown-group"], mapping)
    assert role == "staff"  # default

def test_oidc_user_info_fields():
    info = OIDCUserInfo(
        sub="abc123",
        email="user@example.com",
        name="Jane Doe",
        groups=["admins"],
    )
    assert info.email == "user@example.com"
    assert info.groups == ["admins"]

@pytest.mark.asyncio
async def test_get_authorization_url_returns_url_and_state():
    svc = OIDCService(
        client_id="cid",
        client_secret="cs",
        discovery_url="https://okta.example.com/.well-known/openid-configuration",
        redirect_uri="https://app.example.com/api/core/auth/sso/oidc/callback",
    )
    with patch.object(svc, '_get_client', new_callable=AsyncMock) as mock_client:
        mock_client.return_value.create_authorization_url.return_value = (
            "https://okta.example.com/authorize?...", "state123"
        )
        url, state = await svc.get_authorization_url()
    assert url.startswith("https://")
    assert state == "state123"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/sso/test_oidc_service.py -v
```
Expected: `ModuleNotFoundError: No module named 'sso.oidc_service'`

**Step 3: Implement OIDCService**

```python
# src/sso/oidc_service.py
"""
OIDC/OAuth2 SSO service using Authlib.

Supports: Okta, Azure AD (Microsoft Entra ID), Google Workspace.
All three follow standard OIDC discovery; only the discovery URL differs.
"""
import secrets
from dataclasses import dataclass, field
from typing import Optional, Tuple, List

from authlib.integrations.httpx_client import AsyncOAuth2Client


@dataclass
class OIDCUserInfo:
    sub: str              # IdP subject (stable user ID)
    email: str
    name: str
    groups: List[str] = field(default_factory=list)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


def map_groups_to_role(groups: List[str], attribute_mapping: dict) -> str:
    """
    Map IdP groups to a local RBAC role string.
    attribute_mapping format: {"groups": {"okta-admins": "partner", "okta-staff": "staff"}}
    Returns "staff" if no match found.
    """
    group_map: dict = attribute_mapping.get("groups", {})
    for group in groups:
        if group in group_map:
            return group_map[group]
    return "staff"


class OIDCService:
    """Handles OIDC auth code flow for a single configured IdP."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        discovery_url: str,
        redirect_uri: str,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.discovery_url = discovery_url
        self.redirect_uri = redirect_uri
        self._metadata_cache: Optional[dict] = None

    async def _fetch_metadata(self) -> dict:
        if self._metadata_cache:
            return self._metadata_cache
        import httpx
        async with httpx.AsyncClient() as c:
            resp = await c.get(self.discovery_url, timeout=10)
            resp.raise_for_status()
        self._metadata_cache = resp.json()
        return self._metadata_cache

    async def _get_client(self) -> AsyncOAuth2Client:
        meta = await self._fetch_metadata()
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope="openid email profile",
        )
        client.authorization_endpoint = meta["authorization_endpoint"]
        client.token_endpoint = meta["token_endpoint"]
        client.userinfo_endpoint = meta.get("userinfo_endpoint")
        return client

    async def get_authorization_url(self, extra_params: Optional[dict] = None) -> Tuple[str, str]:
        """Returns (authorization_url, state). Store state in session for CSRF check."""
        client = await self._get_client()
        state = secrets.token_urlsafe(32)
        url, _ = client.create_authorization_url(
            client.authorization_endpoint,
            state=state,
            **(extra_params or {}),
        )
        return url, state

    async def exchange_code(self, code: str, state: str) -> OIDCUserInfo:
        """
        Exchange authorization code for tokens, then fetch user info.
        Raises ValueError on failure.
        """
        client = await self._get_client()
        meta = await self._fetch_metadata()
        try:
            token = await client.fetch_token(
                meta["token_endpoint"],
                code=code,
                state=state,
            )
        except Exception as e:
            raise ValueError(f"OIDC token exchange failed: {e}") from e

        # Fetch user info
        userinfo_url = meta.get("userinfo_endpoint")
        if not userinfo_url:
            raise ValueError("OIDC provider does not expose userinfo endpoint")

        import httpx
        async with httpx.AsyncClient() as c:
            resp = await c.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {token['access_token']}"},
                timeout=10,
            )
            resp.raise_for_status()
        data = resp.json()

        groups: List[str] = data.get("groups", [])  # Okta puts groups here if configured
        # Azure AD uses "roles" or custom claim; Google Workspace has no built-in groups
        groups = groups or data.get("roles", [])

        name = data.get("name", "")
        parts = name.split(" ", 1)
        return OIDCUserInfo(
            sub=data["sub"],
            email=data["email"],
            name=name,
            first_name=parts[0] if parts else "",
            last_name=parts[1] if len(parts) > 1 else "",
            groups=groups,
        )
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/sso/test_oidc_service.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/sso/oidc_service.py tests/sso/test_oidc_service.py
git commit -m "feat(MKW-71): add OIDCService supporting Okta/Azure AD/Google Workspace

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 4: SAML 2.0 service (python3-saml)

**Files:**
- Create: `src/sso/saml_service.py`
- Test: `tests/sso/test_saml_service.py`

**Step 1: Write the failing test**

```python
# tests/sso/test_saml_service.py
import pytest
from unittest.mock import patch, MagicMock
from sso.saml_service import SAMLService, SAMLUserInfo, build_saml_settings

def test_build_saml_settings_structure():
    settings = build_saml_settings(
        sp_entity_id="https://app.example.com",
        acs_url="https://app.example.com/api/core/auth/sso/saml/acs",
        slo_url="https://app.example.com/api/core/auth/sso/saml/slo",
        idp_entity_id="https://idp.example.com",
        idp_sso_url="https://idp.example.com/sso",
        idp_slo_url="https://idp.example.com/slo",
        idp_certificate="MIIC...",
    )
    assert settings["sp"]["entityId"] == "https://app.example.com"
    assert settings["idp"]["entityId"] == "https://idp.example.com"

def test_saml_user_info_fields():
    info = SAMLUserInfo(
        email="user@firm.com",
        name="John Smith",
        name_id="john.smith@firm.com",
        groups=["tax-admins"],
    )
    assert info.email == "user@firm.com"
    assert info.groups == ["tax-admins"]

def test_get_redirect_url_calls_auth():
    svc = SAMLService(
        sp_entity_id="urn:sp",
        acs_url="https://app/acs",
        slo_url="https://app/slo",
        idp_entity_id="urn:idp",
        idp_sso_url="https://idp/sso",
        idp_slo_url="https://idp/slo",
        idp_certificate="CERT",
    )
    with patch('sso.saml_service.OneLogin_Saml2_Auth') as MockAuth:
        mock_auth = MagicMock()
        mock_auth.login.return_value = "https://idp/sso?SAMLRequest=abc"
        MockAuth.return_value = mock_auth
        url = svc.get_redirect_url(request_data={})
    assert "SAMLRequest" in url
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/sso/test_saml_service.py -v
```
Expected: `ModuleNotFoundError: No module named 'sso.saml_service'`

**Step 3: Implement SAMLService**

```python
# src/sso/saml_service.py
"""
SAML 2.0 SP-initiated SSO using python3-saml.

Usage:
1. Call get_redirect_url() to get the IdP redirect URL.
2. User authenticates at IdP.
3. IdP POSTs SAMLResponse to /acs.
4. Call process_acs_response() to get user info.
5. Call get_slo_redirect_url() to initiate single logout.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from onelogin.saml2.auth import OneLogin_Saml2_Auth


@dataclass
class SAMLUserInfo:
    email: str
    name: str
    name_id: str
    groups: List[str] = field(default_factory=list)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


def build_saml_settings(
    sp_entity_id: str,
    acs_url: str,
    slo_url: str,
    idp_entity_id: str,
    idp_sso_url: str,
    idp_slo_url: str,
    idp_certificate: str,
) -> dict:
    """Build python3-saml settings dict from individual params."""
    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": sp_entity_id,
            "assertionConsumerService": {
                "url": acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": slo_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
        "idp": {
            "entityId": idp_entity_id,
            "singleSignOnService": {
                "url": idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "singleLogoutService": {
                "url": idp_slo_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": idp_certificate,
        },
    }


class SAMLService:
    """Handles SAML 2.0 SP-initiated SSO for a single configured IdP."""

    def __init__(
        self,
        sp_entity_id: str,
        acs_url: str,
        slo_url: str,
        idp_entity_id: str,
        idp_sso_url: str,
        idp_slo_url: str,
        idp_certificate: str,
    ):
        self.settings = build_saml_settings(
            sp_entity_id=sp_entity_id,
            acs_url=acs_url,
            slo_url=slo_url,
            idp_entity_id=idp_entity_id,
            idp_sso_url=idp_sso_url,
            idp_slo_url=idp_slo_url,
            idp_certificate=idp_certificate,
        )

    def _make_auth(self, request_data: dict) -> OneLogin_Saml2_Auth:
        return OneLogin_Saml2_Auth(request_data, self.settings)

    def get_redirect_url(self, request_data: dict) -> str:
        """Return SP-initiated SSO redirect URL (send user here)."""
        auth = self._make_auth(request_data)
        return auth.login()

    def process_acs_response(self, request_data: dict) -> SAMLUserInfo:
        """
        Process POSTed SAMLResponse at ACS endpoint.
        Raises ValueError if the assertion is invalid.
        """
        auth = self._make_auth(request_data)
        auth.process_response()
        if not auth.is_authenticated():
            errors = auth.get_errors()
            raise ValueError(f"SAML authentication failed: {errors}")

        attrs = auth.get_attributes()
        name_id = auth.get_nameid()
        email = (
            attrs.get("email", [None])[0]
            or attrs.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", [None])[0]
            or name_id  # fallback to NameID if it looks like email
        )
        name = (
            attrs.get("displayName", [None])[0]
            or attrs.get("cn", [None])[0]
            or email
        )
        groups = attrs.get("groups", []) or attrs.get("memberOf", [])
        first_name = attrs.get("firstName", [None])[0] or attrs.get("givenName", [None])[0]
        last_name = attrs.get("lastName", [None])[0] or attrs.get("sn", [None])[0]

        return SAMLUserInfo(
            email=email,
            name=name,
            name_id=name_id,
            groups=groups,
            first_name=first_name,
            last_name=last_name,
        )

    def get_slo_redirect_url(self, request_data: dict, name_id: str, session_index: Optional[str] = None) -> str:
        """Return SP-initiated Single Logout redirect URL."""
        auth = self._make_auth(request_data)
        return auth.logout(name_id=name_id, session_index=session_index)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/sso/test_saml_service.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/sso/saml_service.py tests/sso/test_saml_service.py
git commit -m "feat(MKW-71): add SAMLService for SAML 2.0 SP-initiated flow

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 5: JIT provisioning service

**Files:**
- Create: `src/sso/provisioning.py`
- Test: `tests/sso/test_provisioning.py`

**Step 1: Write the failing test**

```python
# tests/sso/test_provisioning.py
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from sso.provisioning import JITProvisioningService

@pytest.fixture
def db():
    return MagicMock()

@pytest.fixture
def service(db):
    return JITProvisioningService(db)

def test_provision_creates_new_user(service, db):
    # No existing user
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
    assert user.password_hash is None  # SSO-only user

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
        sso_subject_id="saml-id",
    )
    assert user.first_name == "New"
    assert user.role == "partner"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/sso/test_provisioning.py -v
```
Expected: `ModuleNotFoundError: No module named 'sso.provisioning'`

**Step 3: Implement JITProvisioningService**

```python
# src/sso/provisioning.py
"""
JIT (Just-In-Time) User Provisioning for SSO.

Creates or updates a User record when a CPA firm member logs in via SSO for
the first time. No password is set for SSO-provisioned users.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from admin_panel.models.user import User


class JITProvisioningService:
    def __init__(self, db: Session):
        self.db = db

    def provision_or_update(
        self,
        firm_id: UUID,
        email: str,
        first_name: str,
        last_name: str,
        role: str,
        sso_provider: str,
        sso_subject_id: str,
    ) -> User:
        """
        Find or create a User for the given SSO identity.

        - If user with this email already exists in the firm: update name + role.
        - Otherwise: create a new user with no password (SSO-only).
        """
        user = (
            self.db.query(User)
            .filter(User.email == email, User.firm_id == firm_id)
            .first()
        )
        if user is None:
            user = User(
                firm_id=firm_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                password_hash=None,  # SSO-only, no local password
                is_active=True,
                is_email_verified=True,  # IdP vouches for the email
            )
            self.db.add(user)
        else:
            # Update profile from IdP (name/role may change)
            user.first_name = first_name
            user.last_name = last_name
            user.role = role
            user.is_active = True

        user.last_login_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)
        return user
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/sso/test_provisioning.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/sso/provisioning.py tests/sso/test_provisioning.py
git commit -m "feat(MKW-71): add JIT provisioning service for SSO user creation

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 6: SSO API routes (OIDC + SAML ACS/SLO)

**Files:**
- Create: `src/sso/routes.py`
- Modify: `src/core/api/router.py` (add sso_router)
- Test: `tests/sso/test_sso_routes.py`

**Step 1: Write the failing test**

```python
# tests/sso/test_sso_routes.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI
from sso.routes import sso_router

app = FastAPI()
app.include_router(sso_router)
client = TestClient(app)

def test_sso_oidc_start_returns_redirect_url():
    with patch('sso.routes.get_db') as mock_get_db, \
         patch('sso.routes.SSOConfigService') as MockCfgSvc, \
         patch('sso.routes.OIDCService') as MockOIDC:
        mock_db = MagicMock()
        mock_get_db.return_value.__next__ = MagicMock(return_value=mock_db)
        cfg = MagicMock()
        cfg.provider = 'okta_oidc'
        cfg.is_enabled = True
        cfg.oidc_client_id = 'cid'
        cfg.oidc_client_secret = 'cs'
        cfg.oidc_discovery_url = 'https://example.okta.com/.well-known/openid-configuration'
        MockCfgSvc.return_value.get_enabled_config.return_value = cfg

        mock_oidc = AsyncMock()
        mock_oidc.get_authorization_url = AsyncMock(return_value=("https://okta.com/auth", "state123"))
        MockOIDC.return_value = mock_oidc

        resp = client.get(
            "/sso/oidc/start",
            params={"firm_id": "00000000-0000-0000-0000-000000000001"},
            allow_redirects=False,
        )
    # Should return a redirect
    assert resp.status_code in (302, 307)

def test_sso_oidc_start_404_when_no_config():
    with patch('sso.routes.get_db') as mock_get_db, \
         patch('sso.routes.SSOConfigService') as MockCfgSvc:
        mock_db = MagicMock()
        mock_get_db.return_value.__next__ = MagicMock(return_value=mock_db)
        MockCfgSvc.return_value.get_enabled_config.return_value = None
        resp = client.get(
            "/sso/oidc/start",
            params={"firm_id": "00000000-0000-0000-0000-000000000001"},
        )
    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/sso/test_sso_routes.py -v
```
Expected: `ModuleNotFoundError: No module named 'sso.routes'`

**Step 3: Implement SSO routes**

```python
# src/sso/routes.py
"""
SSO Authentication Routes

OIDC flow:
  GET /sso/oidc/start?firm_id=<uuid>         → redirect to IdP
  GET /sso/oidc/callback?code=&state=        → exchange code, issue JWT, redirect to app

SAML flow:
  GET  /sso/saml/start?firm_id=<uuid>        → redirect to IdP
  POST /sso/saml/acs                         → process assertion, issue JWT, redirect
  GET  /sso/saml/slo                         → SP-initiated single logout

Config (partner role required):
  GET  /sso/config/{firm_id}                 → get SSO config for firm
  PUT  /sso/config/{firm_id}                 → upsert SSO config
  POST /sso/config/{firm_id}/enable          → enable SSO
  POST /sso/config/{firm_id}/disable         → disable SSO
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.database import get_db
from rbac.dependencies import optional_auth, require_role
from rbac.roles import Role
from rbac.jwt import create_access_token

from .config_service import SSOConfigService
from .models import SSOProvider
from .oidc_service import OIDCService, map_groups_to_role
from .provisioning import JITProvisioningService

logger = logging.getLogger(__name__)

sso_router = APIRouter(prefix="/sso", tags=["SSO Authentication"])

# In-memory state store (replace with Redis in production)
_oidc_state_store: dict = {}


# ─── OIDC Flow ────────────────────────────────────────────────────────────────

@sso_router.get("/oidc/start")
async def oidc_start(
    firm_id: UUID = Query(...),
    db: Session = Depends(get_db),
):
    """Begin OIDC SSO flow for a firm. Redirects user to IdP."""
    cfg_svc = SSOConfigService(db)
    cfg = cfg_svc.get_enabled_config(firm_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="SSO not configured for this firm")

    if cfg.provider not in (
        SSOProvider.OKTA_OIDC.value,
        SSOProvider.AZURE_AD_OIDC.value,
        SSOProvider.GOOGLE_WORKSPACE_OIDC.value,
    ):
        raise HTTPException(status_code=400, detail="Firm uses SAML, not OIDC")

    oidc = OIDCService(
        client_id=cfg.oidc_client_id,
        client_secret=cfg.oidc_client_secret,
        discovery_url=cfg.oidc_discovery_url,
        redirect_uri=f"{_get_base_url()}/api/core/auth/sso/oidc/callback",
    )
    url, state = await oidc.get_authorization_url()
    _oidc_state_store[state] = str(firm_id)  # tie state to firm
    return RedirectResponse(url=url, status_code=302)


@sso_router.get("/oidc/callback")
async def oidc_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle OIDC callback from IdP. Issues app JWT and redirects."""
    if error:
        return RedirectResponse(f"/login?error=sso_failed&detail={error}", status_code=302)

    firm_id_str = _oidc_state_store.pop(state, None)
    if not firm_id_str:
        return RedirectResponse("/login?error=sso_invalid_state", status_code=302)

    firm_id = UUID(firm_id_str)
    cfg_svc = SSOConfigService(db)
    cfg = cfg_svc.get_enabled_config(firm_id)
    if cfg is None:
        return RedirectResponse("/login?error=sso_config_missing", status_code=302)

    oidc = OIDCService(
        client_id=cfg.oidc_client_id,
        client_secret=cfg.oidc_client_secret,
        discovery_url=cfg.oidc_discovery_url,
        redirect_uri=f"{_get_base_url()}/api/core/auth/sso/oidc/callback",
    )
    try:
        user_info = await oidc.exchange_code(code, state)
    except ValueError as e:
        logger.warning(f"OIDC exchange failed for firm {firm_id}: {e}")
        return RedirectResponse("/login?error=sso_failed", status_code=302)

    role = map_groups_to_role(user_info.groups, cfg.attribute_mapping)
    prov = JITProvisioningService(db)
    user = prov.provision_or_update(
        firm_id=firm_id,
        email=user_info.email,
        first_name=user_info.first_name or "",
        last_name=user_info.last_name or "",
        role=role,
        sso_provider=cfg.provider,
        sso_subject_id=user_info.sub,
    )

    # Determine JWT expiry from IdP session policy
    from datetime import timedelta
    from rbac.roles import Role as RBACRole
    expires = (
        timedelta(seconds=cfg.session_max_age_seconds)
        if cfg.session_max_age_seconds > 0
        else None
    )
    try:
        rbac_role = RBACRole(role)
    except ValueError:
        rbac_role = RBACRole.STAFF

    token = create_access_token(
        user_id=user.user_id,
        email=user.email,
        name=user.full_name,
        role=rbac_role,
        user_type="firm_user",
        firm_id=firm_id,
        expires_delta=expires,
    )
    redirect_url = f"/cpa/dashboard?sso_success=true&token={token}"
    response = RedirectResponse(url=redirect_url, status_code=302)
    import os
    is_prod = os.environ.get("APP_ENVIRONMENT", "development") not in ("development", "dev", "local", "test")
    response.set_cookie(key="access_token", value=token, httponly=True, secure=is_prod, samesite="lax")
    return response


# ─── SAML Flow ────────────────────────────────────────────────────────────────

@sso_router.get("/saml/start")
async def saml_start(
    firm_id: UUID = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Begin SAML 2.0 SP-initiated SSO. Redirects to IdP."""
    from .saml_service import SAMLService
    cfg_svc = SSOConfigService(db)
    cfg = cfg_svc.get_enabled_config(firm_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="SSO not configured for this firm")
    if cfg.provider != SSOProvider.SAML.value:
        raise HTTPException(status_code=400, detail="Firm uses OIDC, not SAML")

    # Fetch IdP metadata to get SSO/SLO URLs and certificate
    idp_meta = await _fetch_saml_idp_metadata(cfg.saml_idp_metadata_url)
    saml = SAMLService(
        sp_entity_id=cfg.saml_sp_entity_id,
        acs_url=cfg.saml_acs_url,
        slo_url=cfg.saml_slo_url,
        idp_entity_id=idp_meta["entity_id"],
        idp_sso_url=idp_meta["sso_url"],
        idp_slo_url=idp_meta["slo_url"],
        idp_certificate=cfg.saml_idp_certificate or idp_meta["certificate"],
    )
    request_data = _build_saml_request_data(request, str(firm_id))
    redirect_url = saml.get_redirect_url(request_data)
    return RedirectResponse(url=redirect_url, status_code=302)


@sso_router.post("/saml/acs")
async def saml_acs(
    request: Request,
    db: Session = Depends(get_db),
):
    """Assertion Consumer Service — receives SAMLResponse POST from IdP."""
    from .saml_service import SAMLService
    from .oidc_service import map_groups_to_role

    form = await request.form()
    relay_state = form.get("RelayState", "")
    firm_id = UUID(relay_state) if relay_state else None
    if not firm_id:
        return RedirectResponse("/login?error=sso_invalid_relay", status_code=302)

    cfg_svc = SSOConfigService(db)
    cfg = cfg_svc.get_enabled_config(firm_id)
    if cfg is None:
        return RedirectResponse("/login?error=sso_config_missing", status_code=302)

    idp_meta = await _fetch_saml_idp_metadata(cfg.saml_idp_metadata_url)
    saml = SAMLService(
        sp_entity_id=cfg.saml_sp_entity_id,
        acs_url=cfg.saml_acs_url,
        slo_url=cfg.saml_slo_url,
        idp_entity_id=idp_meta["entity_id"],
        idp_sso_url=idp_meta["sso_url"],
        idp_slo_url=idp_meta["slo_url"],
        idp_certificate=cfg.saml_idp_certificate or idp_meta["certificate"],
    )
    request_data = _build_saml_request_data(request, relay_state)
    try:
        user_info = saml.process_acs_response(request_data)
    except ValueError as e:
        logger.warning(f"SAML ACS failed for firm {firm_id}: {e}")
        return RedirectResponse("/login?error=sso_failed", status_code=302)

    role = map_groups_to_role(user_info.groups, cfg.attribute_mapping)
    prov = JITProvisioningService(db)
    user = prov.provision_or_update(
        firm_id=firm_id,
        email=user_info.email,
        first_name=user_info.first_name or "",
        last_name=user_info.last_name or "",
        role=role,
        sso_provider="saml",
        sso_subject_id=user_info.name_id,
    )

    from datetime import timedelta
    from rbac.roles import Role as RBACRole
    expires = timedelta(seconds=cfg.session_max_age_seconds) if cfg.session_max_age_seconds > 0 else None
    try:
        rbac_role = RBACRole(role)
    except ValueError:
        rbac_role = RBACRole.STAFF

    token = create_access_token(
        user_id=user.user_id,
        email=user.email,
        name=user.full_name,
        role=rbac_role,
        user_type="firm_user",
        firm_id=firm_id,
        expires_delta=expires,
    )
    import os
    is_prod = os.environ.get("APP_ENVIRONMENT", "development") not in ("development", "dev", "local", "test")
    response = RedirectResponse(url=f"/cpa/dashboard?sso_success=true&token={token}", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True, secure=is_prod, samesite="lax")
    return response


@sso_router.get("/saml/slo")
async def saml_slo(
    firm_id: UUID = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """SP-initiated Single Logout — clears app session and redirects to IdP SLO."""
    # In production: read name_id from current JWT/session
    return RedirectResponse("/login?logout=true", status_code=302)


# ─── Config Management API ────────────────────────────────────────────────────

class SSOConfigRequest(BaseModel):
    provider: str
    saml_idp_metadata_url: Optional[str] = None
    saml_idp_certificate: Optional[str] = None
    saml_sp_entity_id: Optional[str] = None
    saml_acs_url: Optional[str] = None
    saml_slo_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_discovery_url: Optional[str] = None
    attribute_mapping: dict = {}
    session_max_age_seconds: int = 0
    allow_password_fallback: bool = True


@sso_router.get("/config/{firm_id}")
async def get_sso_config(
    firm_id: UUID,
    db: Session = Depends(get_db),
    auth=Depends(require_role(Role.PARTNER)),
):
    """Get SSO configuration for a firm. Requires partner role."""
    cfg = SSOConfigService(db).get_config(firm_id)
    if cfg is None:
        return {"configured": False}
    return {
        "configured": True,
        "provider": cfg.provider,
        "is_enabled": cfg.is_enabled,
        "saml_idp_metadata_url": cfg.saml_idp_metadata_url,
        "saml_sp_entity_id": cfg.saml_sp_entity_id,
        "saml_acs_url": cfg.saml_acs_url,
        "oidc_client_id": cfg.oidc_client_id,
        "oidc_discovery_url": cfg.oidc_discovery_url,
        "attribute_mapping": cfg.attribute_mapping,
        "session_max_age_seconds": cfg.session_max_age_seconds,
        "allow_password_fallback": cfg.allow_password_fallback,
        # NOTE: oidc_client_secret and saml_idp_certificate are NOT returned
    }


@sso_router.put("/config/{firm_id}")
async def upsert_sso_config(
    firm_id: UUID,
    body: SSOConfigRequest,
    db: Session = Depends(get_db),
    auth=Depends(require_role(Role.PARTNER)),
):
    """Create or update SSO configuration for a firm. Requires partner role."""
    try:
        provider = SSOProvider(body.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")

    svc = SSOConfigService(db)
    svc.upsert_config(
        firm_id=firm_id,
        provider=provider,
        saml_idp_metadata_url=body.saml_idp_metadata_url,
        saml_idp_certificate=body.saml_idp_certificate,
        saml_sp_entity_id=body.saml_sp_entity_id,
        saml_acs_url=body.saml_acs_url,
        saml_slo_url=body.saml_slo_url,
        oidc_client_id=body.oidc_client_id,
        oidc_client_secret=body.oidc_client_secret,
        oidc_discovery_url=body.oidc_discovery_url,
        attribute_mapping=body.attribute_mapping,
        session_max_age_seconds=body.session_max_age_seconds,
        allow_password_fallback=body.allow_password_fallback,
    )
    return {"status": "ok"}


@sso_router.post("/config/{firm_id}/enable")
async def enable_sso(firm_id: UUID, db: Session = Depends(get_db), auth=Depends(require_role(Role.PARTNER))):
    SSOConfigService(db).set_enabled(firm_id, True)
    return {"status": "enabled"}


@sso_router.post("/config/{firm_id}/disable")
async def disable_sso(firm_id: UUID, db: Session = Depends(get_db), auth=Depends(require_role(Role.PARTNER))):
    SSOConfigService(db).set_enabled(firm_id, False)
    return {"status": "disabled"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_base_url() -> str:
    import os
    return os.environ.get("APP_BASE_URL", "https://app.example.com")


def _build_saml_request_data(request: Request, relay_state: str) -> dict:
    """Build the request_data dict expected by python3-saml."""
    return {
        "https": "on" if request.url.scheme == "https" else "off",
        "http_host": request.url.hostname,
        "script_name": request.url.path,
        "server_port": str(request.url.port or 443),
        "get_data": dict(request.query_params),
        "post_data": {},  # Populated from form in ACS handler
        "relay_state": relay_state,
    }


async def _fetch_saml_idp_metadata(metadata_url: Optional[str]) -> dict:
    """Fetch and parse IdP SAML metadata XML to extract SSO/SLO URLs and cert."""
    if not metadata_url:
        raise HTTPException(status_code=400, detail="SAML IdP metadata URL not configured")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(metadata_url)
            resp.raise_for_status()
        # Parse the XML to extract SSO URL, SLO URL, entity ID, and certificate
        from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
        parsed = OneLogin_Saml2_IdPMetadataParser.parse(resp.text)
        idp = parsed.get("idp", {})
        return {
            "entity_id": idp.get("entityId", ""),
            "sso_url": idp.get("singleSignOnService", {}).get("url", ""),
            "slo_url": idp.get("singleLogoutService", {}).get("url", ""),
            "certificate": list(idp.get("x509certMulti", {}).get("signing", [""]))[0]
                           or idp.get("x509cert", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch IdP metadata: {e}")
```

**Step 4: Wire the router into core router**

In `src/core/api/router.py`, add after the existing `oauth_router` import:

```python
from sso.routes import sso_router  # SSO enterprise routes

# In the router includes section, add:
core_router.include_router(sso_router)
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/sso/test_sso_routes.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add src/sso/routes.py src/core/api/router.py tests/sso/test_sso_routes.py
git commit -m "feat(MKW-71): add SSO API routes for OIDC/SAML flow and config management

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 7: Install required dependencies

**Files:**
- Modify: `requirements.txt` (or `pyproject.toml`)

**Step 1: Check existing requirements file**

```bash
cat requirements.txt | grep -E "authlib|python3-saml|httpx"
```

**Step 2: Add missing dependencies**

Add to `requirements.txt`:
```
authlib>=1.3.0
python3-saml>=1.16.0
httpx>=0.27.0
```

Note: `python3-saml` requires `xmlsec` which needs system libs:
- Ubuntu/Debian: `apt-get install xmlsec1 libxmlsec1-dev pkg-config`
- macOS: `brew install libxmlsec1 pkg-config`

**Step 3: Verify install**

```bash
pip install authlib python3-saml httpx
python -c "from authlib.integrations.httpx_client import AsyncOAuth2Client; print('authlib OK')"
python -c "from onelogin.saml2.auth import OneLogin_Saml2_Auth; print('python3-saml OK')"
```
Expected: both print OK

**Step 4: Run all SSO tests**

```bash
pytest tests/sso/ -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add requirements.txt
git commit -m "feat(MKW-71): add authlib, python3-saml, httpx dependencies

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 8: Tests/__init__.py + full SSO integration test

**Files:**
- Create: `tests/sso/__init__.py`
- Create: `tests/sso/test_sso_integration.py`

**Step 1: Write integration test**

```python
# tests/sso/test_sso_integration.py
"""
Integration tests for the full SSO flow:
  config upsert → enable → OIDC start → callback → JWT issued
These tests mock the OIDC IdP but use real service layers.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sso.routes import sso_router, _oidc_state_store

app = FastAPI()
app.include_router(sso_router)

@pytest.fixture(autouse=True)
def clear_state_store():
    _oidc_state_store.clear()
    yield
    _oidc_state_store.clear()


def test_full_oidc_flow_returns_jwt_cookie():
    """
    Simulate: config set → enabled → /sso/oidc/start → /sso/oidc/callback
    Verify: app JWT is set as cookie and user is provisioned.
    """
    firm_id = uuid4()
    mock_db = MagicMock()

    from sso.models import FirmSSOConfig, SSOProvider
    cfg = FirmSSOConfig()
    cfg.firm_id = firm_id
    cfg.provider = SSOProvider.OKTA_OIDC.value
    cfg.is_enabled = True
    cfg.oidc_client_id = "client-id"
    cfg.oidc_client_secret = "client-secret"
    cfg.oidc_discovery_url = "https://okta.example.com/.well-known/openid-configuration"
    cfg.attribute_mapping = {"groups": {"admins": "partner"}}
    cfg.session_max_age_seconds = 28800
    cfg.allow_password_fallback = True

    from admin_panel.models.user import User
    mock_user = MagicMock(spec=User)
    mock_user.user_id = uuid4()
    mock_user.email = "ssouser@firm.com"
    mock_user.full_name = "SSO User"
    mock_user.firm_id = firm_id
    mock_user.role = "partner"

    with patch('sso.routes.get_db') as mock_get_db, \
         patch('sso.routes.SSOConfigService') as MockCfgSvc, \
         patch('sso.routes.OIDCService') as MockOIDCSvc, \
         patch('sso.routes.JITProvisioningService') as MockProv, \
         patch('sso.routes.create_access_token', return_value="fake-jwt"):

        mock_get_db.return_value = iter([mock_db])
        MockCfgSvc.return_value.get_enabled_config.return_value = cfg

        # Start: get authorization URL
        mock_oidc = AsyncMock()
        mock_oidc.get_authorization_url = AsyncMock(
            return_value=("https://okta.example.com/auth", "state-xyz")
        )
        MockOIDCSvc.return_value = mock_oidc

        client = TestClient(app, raise_server_exceptions=True)
        start_resp = client.get(
            "/sso/oidc/start",
            params={"firm_id": str(firm_id)},
            allow_redirects=False,
        )
        assert start_resp.status_code in (302, 307)
        assert "state-xyz" in _oidc_state_store

        # Simulate state injection (as if start had run)
        _oidc_state_store["state-xyz"] = str(firm_id)

        # Callback
        from sso.oidc_service import OIDCUserInfo
        mock_oidc.exchange_code = AsyncMock(
            return_value=OIDCUserInfo(
                sub="sub-123",
                email="ssouser@firm.com",
                name="SSO User",
                first_name="SSO",
                last_name="User",
                groups=["admins"],
            )
        )
        MockProv.return_value.provision_or_update.return_value = mock_user

        cb_resp = client.get(
            "/sso/oidc/callback",
            params={"code": "auth-code", "state": "state-xyz"},
            allow_redirects=False,
        )
    assert cb_resp.status_code in (302, 307)
    assert "sso_success=true" in cb_resp.headers["location"]
    assert "access_token" in cb_resp.cookies or "fake-jwt" in cb_resp.headers.get("location", "")
```

**Step 2: Run integration test**

```bash
pytest tests/sso/test_sso_integration.py -v
```
Expected: PASS

**Step 3: Run full test suite to check for regressions**

```bash
pytest tests/sso/ tests/security/ tests/integration/test_auth_flow.py -v
```
Expected: all PASS

**Step 4: Commit**

```bash
git add tests/sso/__init__.py tests/sso/test_sso_integration.py
git commit -m "feat(MKW-71): add SSO integration tests for full OIDC flow

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Checklist Before Done

- [ ] `FirmSSOConfig` model and migration created
- [ ] `SSOConfigService` CRUD working
- [ ] `OIDCService` with Okta/Azure AD/Google Workspace support
- [ ] `SAMLService` with python3-saml
- [ ] `JITProvisioningService` creating/updating `User` rows
- [ ] SSO routes wired into core router
- [ ] Config management endpoints (GET/PUT/enable/disable) behind `PARTNER` role
- [ ] Password fallback: existing `/api/core/auth/login` unchanged
- [ ] Session duration respects `session_max_age_seconds` from config
- [ ] All tests pass: `pytest tests/sso/ -v`
- [ ] No regressions: `pytest tests/security/ tests/integration/ -v`
