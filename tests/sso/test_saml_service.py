"""Tests for SAMLService."""
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
    assert settings["strict"] is True
    assert settings["sp"]["assertionConsumerService"]["url"].endswith("/acs")
    assert settings["idp"]["x509cert"] == "MIIC..."


def test_saml_user_info_defaults():
    info = SAMLUserInfo(
        email="user@firm.com",
        name="John Smith",
        name_id="john.smith@firm.com",
    )
    assert info.email == "user@firm.com"
    assert info.groups == []
    assert info.first_name is None


def test_saml_user_info_with_groups():
    info = SAMLUserInfo(
        email="user@firm.com",
        name="John Smith",
        name_id="john.smith@firm.com",
        groups=["tax-admins"],
        first_name="John",
        last_name="Smith",
    )
    assert info.groups == ["tax-admins"]
    assert info.first_name == "John"


def test_get_redirect_url_calls_auth_login():
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

    assert mock_auth.login.called
    assert "SAMLRequest" in url


def test_process_acs_response_raises_on_auth_failure():
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
        mock_auth.process_response.return_value = None
        mock_auth.is_authenticated.return_value = False
        mock_auth.get_errors.return_value = ["invalid_signature"]
        MockAuth.return_value = mock_auth

        with pytest.raises(ValueError, match="SAML authentication failed"):
            svc.process_acs_response(request_data={})


def test_process_acs_response_extracts_user_info():
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
        mock_auth.process_response.return_value = None
        mock_auth.is_authenticated.return_value = True
        mock_auth.get_nameid.return_value = "jdoe@firm.com"
        mock_auth.get_attributes.return_value = {
            "email": ["jdoe@firm.com"],
            "displayName": ["John Doe"],
            "groups": ["tax-admins"],
            "firstName": ["John"],
            "lastName": ["Doe"],
        }
        MockAuth.return_value = mock_auth

        info = svc.process_acs_response(request_data={})

    assert info.email == "jdoe@firm.com"
    assert info.name == "John Doe"
    assert info.groups == ["tax-admins"]
    assert info.first_name == "John"
