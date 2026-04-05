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
