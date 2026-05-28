from __future__ import annotations

from fastapi import Request, Response


AUTH_COOKIE_NAME = "um_access_token"


def get_auth_token(request: Request) -> str | None:
    return request.cookies.get(AUTH_COOKIE_NAME)


def set_auth_cookie(response: Response, *, request: Request, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        path="/",
        samesite="lax"
    )


def clear_auth_cookie(response: Response, *, request: Request) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=True,
        path="/",
        samesite="lax"
    )
