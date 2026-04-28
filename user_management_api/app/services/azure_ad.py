from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx
import msal

from app.core.config import settings


@dataclass(frozen=True)
class AzureADUser:
    id: str
    mail: Optional[str]
    user_principal_name: Optional[str]
    display_name: Optional[str]


def _enabled() -> bool:
    return bool(
        settings.azure_tenant_id
        and settings.azure_client_id
        and settings.azure_client_secret
    )


def _get_graph_token() -> str:
    authority = f"https://login.microsoftonline.com/{settings.azure_tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=authority,
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(
            f"Failed to acquire Graph token: {result.get('error_description') or result}"
        )
    return result["access_token"]


async def validate_email_in_tenant(email: str) -> Optional[AzureADUser]:
    """
    Returns an AzureADUser if the email exists in the tenant. If Azure AD is not configured, returns None.
    """
    if settings.offline_mode or not _enabled():
        return None

    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Try direct lookup by UPN/email. Graph supports /users/{id|userPrincipalName}
    url = f"https://graph.microsoft.com/v1.0/users/{email}?$select=id,displayName,mail,userPrincipalName"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return AzureADUser(
            id=data["id"],
            mail=data.get("mail"),
            user_principal_name=data.get("userPrincipalName"),
            display_name=data.get("displayName"),
        )
