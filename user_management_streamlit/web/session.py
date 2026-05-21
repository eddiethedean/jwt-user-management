from __future__ import annotations

import sys
from typing import Literal, cast

from fastapi import Request, Response

from fastapi_workbench import base_path
from app.core.config import settings
from user_management_streamlit.web.debug_panel import add_cookie_debug


AUTH_COOKIE_NAME = "um_access_token"
AUTH_COOKIE_LEGACY_NAME = "um_access_token-legacy"


def _try_add_partitioned_set_cookie_header(
    response: Response, *, request: Request, cookie_name: str
) -> None:
    """
    Starlette refuses to emit Partitioned cookies on Python < 3.14.
    For embedded Connect contexts, we still want to attempt CHIPS by manually
    appending the `Partitioned` attribute to the Set-Cookie header.
    """
    raw = getattr(response, "raw_headers", None)
    if not isinstance(raw, list):
        add_cookie_debug(request, "cookie:set could not access raw_headers")
        return

    name_prefix = (cookie_name + "=").encode("utf-8")
    updated = 0
    new_raw: list[tuple[bytes, bytes]] = []
    for k, v in raw:
        if k.lower() == b"set-cookie" and v.startswith(name_prefix):
            vv_l = v.lower()
            # Some clients are picky about `SameSite=None` casing.
            v = v.replace(b"SameSite=none", b"SameSite=None")
            if b"partitioned" not in vv_l:
                v = v + b"; Partitioned"
                updated += 1
        new_raw.append((k, v))

    if updated:
        response.raw_headers = new_raw
        add_cookie_debug(
            request,
            "cookie:set manually appended Partitioned to Set-Cookie",
            count=updated,
        )
    else:
        add_cookie_debug(
            request,
            "cookie:set could not find auth Set-Cookie header to patch",
            cookie=cookie_name,
        )


def _is_https(request: Request) -> bool:
    xf_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    if xf_proto:
        add_cookie_debug(
            request,
            "cookie:https",
            source="x-forwarded-proto",
            value=xf_proto,
            https=(xf_proto.lower() == "https"),
        )
        return xf_proto.lower() == "https"
    scheme = (request.url.scheme or "").lower()
    add_cookie_debug(
        request,
        "cookie:https",
        source="request.url.scheme",
        value=scheme,
        https=(scheme == "https"),
    )
    return scheme == "https"


def cookie_path(request: Request) -> str:
    bp = base_path(request)
    p = bp or "/"
    add_cookie_debug(
        request,
        "cookie:path",
        base_path=bp,
        root_path=(request.scope.get("root_path") or ""),
        connect_app_base_url=request.headers.get("rstudio-connect-app-base-url"),
        path=p,
    )
    return p


def get_auth_token(request: Request) -> str | None:
    tok = request.cookies.get(AUTH_COOKIE_NAME)
    legacy = request.cookies.get(AUTH_COOKIE_LEGACY_NAME)
    if not tok and legacy and bool(getattr(settings, "auth_cookie_legacy", True)):
        tok = legacy
    # Never log token contents; only presence and length.
    add_cookie_debug(
        request,
        "cookie:get",
        name=AUTH_COOKIE_NAME,
        present=bool(tok),
        length=(len(tok) if tok else 0),
        legacy_present=bool(legacy),
        request_path=request.url.path,
    )
    return tok


def set_auth_cookie(response: Response, *, request: Request, token: str) -> None:
    secure = (
        _is_https(request)
        if settings.auth_cookie_secure is None
        else settings.auth_cookie_secure
    )
    samesite = cast(
        Literal["lax", "strict", "none"],
        (settings.auth_cookie_samesite or "lax").lower(),
    )
    domain = settings.auth_cookie_domain or None
    path = cookie_path(request)
    wants_partitioned = bool(getattr(settings, "auth_cookie_partitioned", False))
    partitioned_supported = sys.version_info >= (3, 14)
    wants_legacy = bool(getattr(settings, "auth_cookie_legacy", True))

    # Modern browsers require Secure when SameSite=None. Enforce to avoid silent drops.
    if samesite == "none" and not secure:
        add_cookie_debug(
            request, "cookie:set forcing secure=True because samesite=None"
        )
        secure = True

    # Partitioned cookies require SameSite=None; Secure. Enforce to avoid silent drops.
    if wants_partitioned and samesite != "none":
        add_cookie_debug(
            request,
            "cookie:set forcing samesite='none' because partitioned requested",
            prev_samesite=samesite,
        )
        samesite = "none"
    if wants_partitioned and not secure:
        add_cookie_debug(
            request, "cookie:set forcing secure=True because partitioned requested"
        )
        secure = True

    if wants_partitioned and not partitioned_supported:
        add_cookie_debug(
            request,
            "cookie:set partitioned requested but unsupported on this runtime",
            python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )

    add_cookie_debug(
        request,
        "cookie:set",
        name=AUTH_COOKIE_NAME,
        secure=secure,
        samesite=samesite,
        partitioned=(wants_partitioned and partitioned_supported),
        legacy=wants_legacy,
        domain=domain,
        path=path,
        url=str(request.url),
        xf_proto=request.headers.get("x-forwarded-proto"),
    )
    if wants_partitioned and partitioned_supported:
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=secure,
            samesite=samesite,
            path=path,
            domain=domain,
            partitioned=True,
        )
        return

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path=path,
        domain=domain,
    )
    if wants_partitioned and not partitioned_supported:
        _try_add_partitioned_set_cookie_header(
            response, request=request, cookie_name=AUTH_COOKIE_NAME
        )

    # Connect pattern: if SameSite=None, emit a second cookie without SameSite for
    # compatibility with older/quirky clients.
    if wants_legacy and samesite == "none":
        response.set_cookie(
            key=AUTH_COOKIE_LEGACY_NAME,
            value=token,
            httponly=True,
            secure=secure,
            # Intentionally omit samesite=
            path=path,
            domain=domain,
        )
        add_cookie_debug(
            request,
            "cookie:set legacy",
            name=AUTH_COOKIE_LEGACY_NAME,
            secure=secure,
            path=path,
            domain=domain,
        )


def clear_auth_cookie(response: Response, *, request: Request) -> None:
    path = cookie_path(request)
    add_cookie_debug(
        request,
        "cookie:clear",
        name=AUTH_COOKIE_NAME,
        path=path,
        url=str(request.url),
    )
    response.delete_cookie(key=AUTH_COOKIE_NAME, path=path)
    if bool(getattr(settings, "auth_cookie_legacy", True)):
        response.delete_cookie(key=AUTH_COOKIE_LEGACY_NAME, path=path)
        add_cookie_debug(
            request, "cookie:clear legacy", name=AUTH_COOKIE_LEGACY_NAME, path=path
        )
