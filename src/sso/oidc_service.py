"""
OIDC/OAuth2 SSO service using Authlib.

Supports: Okta, Azure AD (Microsoft Entra ID), Google Workspace.
All three follow standard OIDC discovery; only the discovery URL differs.

Typical discovery URLs:
  Okta:             https://<your-domain>.okta.com/.well-known/openid-configuration
  Azure AD:         https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
  Google Workspace: https://accounts.google.com/.well-known/openid-configuration
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
    Returns "staff" if no match found (safest default).
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
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(self.discovery_url)
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
        """
        Returns (authorization_url, state).
        Caller must persist state in session/cache for CSRF validation at callback.
        """
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
        Exchange authorization code for tokens, then fetch userinfo.
        Raises ValueError on authentication failure.
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

        userinfo_url = meta.get("userinfo_endpoint")
        if not userinfo_url:
            raise ValueError("OIDC provider does not expose a userinfo endpoint")

        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            resp.raise_for_status()
        data = resp.json()

        # Groups: Okta includes if configured; Azure AD uses "roles"; GW has none
        groups: List[str] = data.get("groups", []) or data.get("roles", [])

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
