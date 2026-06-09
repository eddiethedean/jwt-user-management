from __future__ import annotations

from fastapi import Request

from app.auth.jwt_principal import (
    JwtPrincipal,
    require_admin_principal,
    require_cookie_principal,
)


def require_cookie_user_principal(request: Request) -> JwtPrincipal:
    return require_cookie_principal(request)


def require_admin_cookie_principal(request: Request) -> JwtPrincipal:
    return require_admin_principal(require_cookie_principal(request))
