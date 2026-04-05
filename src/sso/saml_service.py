"""
SAML 2.0 SP-initiated SSO using python3-saml.

Flow:
1. Call get_redirect_url() to get the IdP login redirect URL.
2. User authenticates at IdP.
3. IdP POSTs SAMLResponse to the ACS endpoint.
4. Call process_acs_response() to validate assertion and extract user attributes.
5. Call get_slo_redirect_url() to perform SP-initiated single logout.
"""
from dataclasses import dataclass, field
from typing import Optional, List

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
    """Build python3-saml settings dict from individual parameters."""
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
        """Return SP-initiated SSO redirect URL — redirect user here to begin login."""
        auth = self._make_auth(request_data)
        return auth.login()

    def process_acs_response(self, request_data: dict) -> SAMLUserInfo:
        """
        Validate the SAMLResponse POSTed to the ACS endpoint.

        Raises ValueError if the assertion is invalid or not authenticated.
        """
        auth = self._make_auth(request_data)
        auth.process_response()
        if not auth.is_authenticated():
            errors = auth.get_errors()
            raise ValueError(f"SAML authentication failed: {errors}")

        attrs = auth.get_attributes()
        name_id = auth.get_nameid()

        # Extract email from attributes or fall back to NameID
        email = (
            _first(attrs.get("email"))
            or _first(attrs.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"))
            or name_id
        )
        name = (
            _first(attrs.get("displayName"))
            or _first(attrs.get("cn"))
            or email
        )
        groups = attrs.get("groups", []) or attrs.get("memberOf", [])
        first_name = _first(attrs.get("firstName")) or _first(attrs.get("givenName"))
        last_name = _first(attrs.get("lastName")) or _first(attrs.get("sn"))

        return SAMLUserInfo(
            email=email,
            name=name,
            name_id=name_id,
            groups=list(groups),
            first_name=first_name,
            last_name=last_name,
        )

    def get_slo_redirect_url(
        self,
        request_data: dict,
        name_id: str,
        session_index: Optional[str] = None,
    ) -> str:
        """Return SP-initiated Single Logout redirect URL."""
        auth = self._make_auth(request_data)
        return auth.logout(name_id=name_id, session_index=session_index)


def _first(values) -> Optional[str]:
    """Return first element of list or None."""
    if values:
        return values[0] if isinstance(values, (list, tuple)) else values
    return None
