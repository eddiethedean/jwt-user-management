from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
import logging
from typing import Any, Optional

import httpx

import app.core.config as app_config

log = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class DirectoryEmailRecord:
    email: str
    display_name: str | None = None
    country: str | None = None
    command: str | None = None


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
    if s.lower().startswith("c="):
        s = s[2:].strip()
    return s or None


def _parse_extended(attrs: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    given_name = _first_str(attrs.get("givenName"))
    sn = _first_str(attrs.get("sn"))
    if given_name and sn:
        display = f"{given_name} {sn}"
    else:
        display = _first_str(attrs.get("displayName")) or _first_str(attrs.get("cn"))
    country = _first_str(attrs.get("extensionAttribute8"))
    command = _first_str(attrs.get("department"))
    return display, country, command


def _parse_generic(attrs: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    display = _first_str(attrs.get("displayName")) or _first_str(attrs.get("cn"))
    country = _norm_country(_first_str(attrs.get("c")) or _first_str(attrs.get("co")))
    return display, country, None


def _merge_profile_fields(
    extended: tuple[str | None, str | None, str | None],
    generic: tuple[str | None, str | None, str | None],
) -> tuple[str | None, str | None, str | None]:
    display = extended[0] or generic[0]
    country = extended[1] or generic[1]
    command = extended[2]
    return display, country, command


def _attributes_to_record(email: str, attrs: dict[str, Any]) -> DirectoryEmailRecord:
    profile = app_config.settings.directory_attribute_profile
    extended = _parse_extended(attrs)
    generic = _parse_generic(attrs)
    if profile == "extended":
        display, country, command = extended
    elif profile == "both":
        display, country, command = _merge_profile_fields(extended, generic)
    else:
        display, country, command = generic

    if not app_config.settings.user_command_field_enabled:
        command = None

    return DirectoryEmailRecord(
        email=email.strip().lower(),
        display_name=display,
        country=country,
        command=command,
    )


def _directory_verify() -> bool | str:
    verify: bool | str = bool(app_config.settings.directory_lookup_verify_ssl)
    if verify and (app_config.settings.directory_lookup_ca_bundle or "").strip():
        verify = app_config.settings.directory_lookup_ca_bundle.strip()
    return verify


def _directory_timeout() -> httpx.Timeout:
    return httpx.Timeout(float(app_config.settings.directory_lookup_timeout_s or 5))


def _handle_directory_response(
    resp: httpx.Response, *, email: str
) -> DirectoryEmailRecord | None:
    if resp.status_code == 404:
        log.info("Directory lookup: not found email=%s status=404", email)
        return None
    if resp.status_code < 200 or resp.status_code >= 300:
        if app_config.settings.directory_lookup_required:
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
        if app_config.settings.directory_lookup_required:
            raise
        return None

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

    rec = _attributes_to_record(mail, attrs)
    query_norm = email.strip().lower()
    if rec.email.strip().lower() != query_norm:
        log.warning(
            "Directory lookup: mail mismatch query=%s returned=%s",
            email,
            rec.email,
        )
        return None
    log.info(
        "Directory lookup: ok query=%s mail=%s country=%s command=%s",
        email,
        rec.email,
        rec.country or "",
        rec.command or "",
    )
    return rec


def lookup_email(email: str) -> DirectoryEmailRecord | None:
    """
    Lookup an email address in the external directory service.

    Returns None on "not found" or when lookup is disabled.
    Raises on transport/parse errors only when ``directory_lookup_required`` is True
    (HTTP client layer); application routes do not use this flag to block invites.
    """
    base = (app_config.settings.directory_lookup_url or "").strip()
    if not base:
        return None

    verify = _directory_verify()
    timeout = _directory_timeout()

    try:
        log.info(
            "Directory lookup: start email=%s required=%s url=%s profile=%s",
            email,
            bool(app_config.settings.directory_lookup_required),
            base,
            app_config.settings.directory_attribute_profile,
        )
        resp = httpx.get(
            base,
            params={"query": email},
            timeout=timeout,
            verify=verify,
        )
    except Exception:
        log.exception("Directory lookup: request failed email=%s url=%s", email, base)
        if app_config.settings.directory_lookup_required:
            raise
        return None

    return _handle_directory_response(resp, email=email)


async def lookup_email_async(email: str) -> DirectoryEmailRecord | None:
    """Async directory lookup for route handlers."""
    return await asyncio.to_thread(lookup_email, email)
