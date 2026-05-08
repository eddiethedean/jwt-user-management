from __future__ import annotations

from fastapi import Request, Response

from fastapi_workbench import base_path
from app.core.config import settings


AUTH_COOKIE_NAME = "um_access_token"


def _is_https(request: Request) -> bool:
    xf_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    if xf_proto:
        return xf_proto.lower() == "https"
    return (request.url.scheme or "").lower() == "https"


def cookie_path(request: Request) -> str:
    bp = base_path(request)
    return bp or "/"


def get_auth_token(request: Request) -> str | None:
    return request.cookies.get(AUTH_COOKIE_NAME)


def set_auth_cookie(response: Response, *, request: Request, token: str) -> None:
    secure = _is_https(request) if settings.auth_cookie_secure is None else settings.auth_cookie_secure
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=settings.auth_cookie_samesite,
        path=cookie_path(request),
        domain=settings.auth_cookie_domain or None,
    )


def clear_auth_cookie(response: Response, *, request: Request) -> None:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path=cookie_path(request))
