from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests

from app.core.config import settings


@dataclass(frozen=True)
class DirectoryEmailRecord:
    email: str
    display_name: str | None = None
    country: str | None = None


def _first_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v:
        x = v[0]
        return x if isinstance(x, str) else str(x)
    return str(v)


def lookup_email(email: str) -> DirectoryEmailRecord | None:
    """
    Lookup an email address in the external directory service.

    Returns None on "not found" or when lookup is disabled.
    Raises on unexpected/transport errors only when directory_lookup_required is True.
    """
    base = (settings.directory_lookup_url or "").strip()
    if not base:
        return None

    try:
        resp = requests.get(
            base,
            params={"query": email},
            timeout=int(settings.directory_lookup_timeout_s or 5),
        )
    except Exception:
        if settings.directory_lookup_required:
            raise
        return None

    if resp.status_code == 404:
        return None
    if not resp.ok:
        if settings.directory_lookup_required:
            raise RuntimeError(f"Directory lookup failed: {resp.status_code}")
        return None

    try:
        data = resp.json()
    except Exception:
        if settings.directory_lookup_required:
            raise
        return None

    if not isinstance(data, dict):
        return None
    attrs = data.get("attributes")
    if not isinstance(attrs, dict):
        return None

    mail = _first_str(attrs.get("mail")) or _first_str(attrs.get("userPrincipalName"))
    if not mail:
        return None

    display = _first_str(attrs.get("displayName")) or _first_str(attrs.get("cn"))
    country = _first_str(attrs.get("c")) or _first_str(attrs.get("co"))
    if country:
        country = country.strip()
    return DirectoryEmailRecord(
        email=mail.strip().lower(),
        display_name=display,
        country=country or None,
    )

