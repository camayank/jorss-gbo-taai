"""Tests for SSO models."""
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


def test_provider_enum_values():
    assert SSOProvider.SAML.value == 'saml'
    assert SSOProvider.OKTA_OIDC.value == 'okta_oidc'
    assert SSOProvider.AZURE_AD_OIDC.value == 'azure_ad_oidc'
    assert SSOProvider.GOOGLE_WORKSPACE_OIDC.value == 'google_workspace_oidc'


def test_provider_enum_from_value():
    assert SSOProvider('saml') is SSOProvider.SAML
    assert SSOProvider('okta_oidc') is SSOProvider.OKTA_OIDC


def test_firm_sso_config_repr():
    cfg = FirmSSOConfig()
    cfg.provider = 'saml'
    cfg.is_enabled = False
    assert 'FirmSSOConfig' in repr(cfg)
