from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

log = logging.getLogger("uvicorn.error")


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


def _norm_country(v: str | None) -> str | None:
    if not v:
        return None
    s = v.strip()
    if not s:
        return None
    # Be tolerant of directory values like "C=US".
    if s.lower().startswith("c="):
        s = s[2:].strip()
    return s or None


def lookup_email(email: str) -> DirectoryEmailRecord | None:
    """
    Lookup an email address in the external directory service.

    Returns None on "not found" or when lookup is disabled.
    Raises on transport/parse errors only when ``directory_lookup_required`` is True
    (HTTP client layer); application routes do not use this flag to block invites.
    """
    base = (settings.directory_lookup_url or "").strip()
    if not base:
        return None

    verify: bool | str = bool(settings.directory_lookup_verify_ssl)
    if verify and (settings.directory_lookup_ca_bundle or "").strip():
        verify = settings.directory_lookup_ca_bundle.strip()

    try:
        log.info(
            "Directory lookup: start email=%s required=%s url=%s",
            email,
            bool(settings.directory_lookup_required),
            base,
        )
        resp = httpx.get(
            base,
            params={"query": email},
            timeout=httpx.Timeout(float(settings.directory_lookup_timeout_s or 5)),
            verify=verify,
        )
    except Exception:
        log.exception("Directory lookup: request failed email=%s url=%s", email, base)
        if settings.directory_lookup_required:
            raise
        return None

    if resp.status_code == 404:
        log.info("Directory lookup: not found email=%s status=404", email)
        return None
    if resp.status_code < 200 or resp.status_code >= 300:
        if settings.directory_lookup_required:
            log.error(
                "Directory lookup: non-2xx email=%s status=%s required=true",
                email,
                resp.status_code,
            )
            raise RuntimeError(f"Directory lookup failed: {resp.status_code}")
        log.warning(
            "Directory lookup: non-2xx email=%s status=%s required=false",
            email,
            resp.status_code,
        )
        return None

    try:
        data = resp.json()
    except Exception:
        log.exception(
            "Directory lookup: invalid json email=%s status=%s",
            email,
            resp.status_code,
        )
        if settings.directory_lookup_required:
            raise
        return None

    # Some deployments return a JSON string that itself contains JSON. Be tolerant.
    if isinstance(data, str):
        try:
            data2 = json.loads(data)
        except Exception:
            log.warning(
                "Directory lookup: unexpected json string email=%s len=%s",
                email,
                len(data),
            )
            return None
        data = data2

    if not isinstance(data, dict):
        log.warning(
            "Directory lookup: unexpected json type email=%s type=%s",
            email,
            type(data).__name__,
        )
        return None
    attrs = data.get("attributes")
    if not isinstance(attrs, dict):
        log.warning("Directory lookup: missing attributes email=%s", email)
        return None

    mail = _first_str(attrs.get("mail")) or _first_str(attrs.get("userPrincipalName"))
    if not mail:
        log.warning("Directory lookup: missing mail field email=%s", email)
        return None

    display = _first_str(attrs.get("displayName")) or _first_str(attrs.get("cn"))
    country = _norm_country(_first_str(attrs.get("c")) or _first_str(attrs.get("co")))
    rec = DirectoryEmailRecord(
        email=mail.strip().lower(),
        display_name=display,
        country=country,
    )
    log.info(
        "Directory lookup: ok query=%s mail=%s country=%s",
        email,
        rec.email,
        rec.country or "",
    )
    return rec
