from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional

from fastapi import HTTPException, Request

from app.core.config import settings
from app.web.session import auth_cookie_path, auth_cookie_secure

CSRF_FORM_FIELD = "csrf_token"
CSRF_COOKIE_NAME = "um_csrf_token"


def _sign(token: str) -> str:
    secret = settings.jwt_secret.encode("utf-8")
    sig = hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token}.{sig}"


def _verify(signed: str) -> bool:
    if not signed or "." not in signed:
        return False
    token, sig = signed.rsplit(".", 1)
    expected = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected)


def issue_csrf_token(request: Request) -> str:
    """Create or reuse a CSRF token for this request."""
    existing = request.cookies.get(CSRF_COOKIE_NAME)
    if existing and _verify(existing):
        token = existing.rsplit(".", 1)[0]
    else:
        token = secrets.token_urlsafe(32)
    signed = _sign(token)
    request.state.csrf_token = token
    request.state.csrf_signed = signed
    return token


def set_csrf_cookie(response, *, request: Request) -> None:
    signed = getattr(request.state, "csrf_signed", None)
    if not signed:
        return
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=signed,
        httponly=True,
        secure=auth_cookie_secure(request),
        samesite="lax",
        path=auth_cookie_path(request),
    )


def validate_csrf(
    request: Request,
    form_token: Optional[str] = None,
) -> None:
    """Validate double-submit CSRF token (form field + cookie)."""
    cookie = request.cookies.get(CSRF_COOKIE_NAME) or ""
    field = (form_token or request.headers.get("x-csrf-token") or "").strip()
    if not field or not cookie or not _verify(cookie):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    cookie_token = cookie.rsplit(".", 1)[0]
    if not hmac.compare_digest(field, cookie_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
