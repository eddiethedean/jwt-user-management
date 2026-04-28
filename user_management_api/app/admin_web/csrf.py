from __future__ import annotations

import secrets
from typing import Optional

from fastapi import HTTPException
from starlette.requests import Request


_SESSION_KEY = "csrf_token"
_HEADER = "x-csrf-token"


def get_csrf_token(request: Request) -> str:
    token: Optional[str] = (request.session or {}).get(_SESSION_KEY)  # type: ignore[attr-defined]
    if token:
        return token
    token = secrets.token_urlsafe(32)
    request.session[_SESSION_KEY] = token  # type: ignore[attr-defined]
    return token


def validate_csrf(request: Request, provided: str) -> None:
    expected: Optional[str] = (request.session or {}).get(_SESSION_KEY)  # type: ignore[attr-defined]
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise HTTPException(status_code=403, detail="CSRF failed")


def require_csrf(request: Request) -> None:
    provided: str = (request.headers.get(_HEADER) or "").strip()
    validate_csrf(request, provided)
