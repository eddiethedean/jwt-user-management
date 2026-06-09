"""CSRF protection for cookie-authenticated HTML forms."""

from __future__ import annotations

import secrets
from typing import Literal, cast

from fastapi import HTTPException, Request, Response

import app.core.config as app_config
from app.web.session import auth_cookie_path, auth_cookie_secure

CSRF_COOKIE = "um_csrf_token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER = "x-csrf-token"


def _new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def ensure_csrf_token(request: Request) -> str:
    token = getattr(request.state, "csrf_token", None)
    if not token:
        token = request.cookies.get(CSRF_COOKIE) or _new_csrf_token()
        request.state.csrf_token = token
    return token


def set_csrf_cookie(resp: Response, request: Request) -> None:
    token = ensure_csrf_token(request)
    secure = auth_cookie_secure(request)
    samesite = cast(
        Literal["lax", "strict", "none"],
        (app_config.settings.auth_cookie_samesite or "lax").lower(),
    )
    if samesite == "none" and not secure:
        secure = True
    resp.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        httponly=False,
        secure=secure,
        samesite=samesite,
        path=auth_cookie_path(request),
        domain=app_config.settings.auth_cookie_domain or None,
    )


def verify_csrf(request: Request, submitted: str | None = None) -> None:
    expected = request.cookies.get(CSRF_COOKIE) or getattr(
        request.state, "csrf_token", None
    )
    if not expected:
        raise HTTPException(status_code=403, detail="CSRF token missing")
    val = (submitted or "").strip()
    if not val:
        val = (request.headers.get(CSRF_HEADER) or "").strip()
    if not val or not secrets.compare_digest(expected, val):
        raise HTTPException(status_code=403, detail="CSRF token invalid")
