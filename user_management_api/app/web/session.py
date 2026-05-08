from __future__ import annotations

import logging

from fastapi import Request, Response

from fastapi_workbench import base_path
from app.core.config import settings


AUTH_COOKIE_NAME = "um_access_token"
log = logging.getLogger("uvicorn.error")


def _dbg() -> bool:
    return bool(getattr(settings, "cookie_debug", False))


def _is_https(request: Request) -> bool:
    xf_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    if xf_proto:
        if _dbg():
            log.info(
                "cookie:https inferred from x-forwarded-proto=%r -> %s",
                xf_proto,
                xf_proto.lower() == "https",
            )
        return xf_proto.lower() == "https"
    scheme = (request.url.scheme or "").lower()
    if _dbg():
        log.info(
            "cookie:https inferred from request.url.scheme=%r -> %s",
            scheme,
            scheme == "https",
        )
    return scheme == "https"


def cookie_path(request: Request) -> str:
    bp = base_path(request)
    p = bp or "/"
    if _dbg():
        log.info(
            "cookie:path base_path=%r root_path=%r connect_app_base_url=%r -> path=%r",
            bp,
            (request.scope.get("root_path") or ""),
            request.headers.get("rstudio-connect-app-base-url"),
            p,
        )
    return p


def get_auth_token(request: Request) -> str | None:
    tok = request.cookies.get(AUTH_COOKIE_NAME)
    # Never log token contents; only presence and length.
    if _dbg():
        log.info(
            "cookie:get name=%s present=%s len=%s path=%r",
            AUTH_COOKIE_NAME,
            bool(tok),
            (len(tok) if tok else 0),
            request.url.path,
        )
    return tok


def set_auth_cookie(response: Response, *, request: Request, token: str) -> None:
    secure = (
        _is_https(request)
        if settings.auth_cookie_secure is None
        else settings.auth_cookie_secure
    )
    samesite = (settings.auth_cookie_samesite or "lax").lower()
    domain = settings.auth_cookie_domain or None
    path = cookie_path(request)

    # Modern browsers require Secure when SameSite=None. Enforce to avoid silent drops.
    if samesite == "none" and not secure:
        if _dbg():
            log.info("cookie:set forcing secure=True because samesite=None")
        secure = True

    if _dbg():
        log.info(
            "cookie:set name=%s secure=%s samesite=%s domain=%r path=%r url=%s xf_proto=%r",
            AUTH_COOKIE_NAME,
            secure,
            samesite,
            domain,
            path,
            str(request.url),
            request.headers.get("x-forwarded-proto"),
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
    if _dbg():
        log.info(
            "cookie:clear name=%s path=%r url=%s",
            AUTH_COOKIE_NAME,
            path,
            str(request.url),
        )
    response.delete_cookie(key=AUTH_COOKIE_NAME, path=path)
