from __future__ import annotations

from typing import Literal, cast

from fastapi import Request, Response

from fastapi_workbench import base_path
from app.core.config import settings
from app.web.debug_panel import add_cookie_debug


AUTH_COOKIE_NAME = "um_access_token"


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
    # Never log token contents; only presence and length.
    add_cookie_debug(
        request,
        "cookie:get",
        name=AUTH_COOKIE_NAME,
        present=bool(tok),
        length=(len(tok) if tok else 0),
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

    # Modern browsers require Secure when SameSite=None. Enforce to avoid silent drops.
    if samesite == "none" and not secure:
        add_cookie_debug(
            request, "cookie:set forcing secure=True because samesite=None"
        )
        secure = True

    add_cookie_debug(
        request,
        "cookie:set",
        name=AUTH_COOKIE_NAME,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path=path,
        url=str(request.url),
        xf_proto=request.headers.get("x-forwarded-proto"),
    )
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=samesite,
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
