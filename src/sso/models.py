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
    oidc_client_secret = Column(String(500), nullable=True)
    oidc_discovery_url = Column(String(500), nullable=True)

    # Role/attribute mapping: {"groups": {"tax-admins": "partner", "staff": "staff"}}
    attribute_mapping = Column(JSONB, default=dict, nullable=False)

    # Session settings (0 = use app default of 8 hours)
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

    def __repr__(self):
        return f"<FirmSSOConfig(firm_id={self.firm_id}, provider={self.provider}, enabled={self.is_enabled})>"
