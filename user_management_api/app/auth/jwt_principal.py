"""Stateless JWT session principal (decode only; no per-request User SELECT for auth)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import decode_token
from app.models import User
from app.web.session import get_auth_token


@dataclass(frozen=True)
class JwtPrincipal:
    user_id: int
    is_admin: bool
    email: str | None = None


def principal_from_payload(payload: dict[str, Any]) -> JwtPrincipal:
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")
    is_admin = bool(payload.get("is_admin", False))
    email_raw = payload.get("email")
    email = str(email_raw).strip() if email_raw else None
    return JwtPrincipal(user_id=user_id, is_admin=is_admin, email=email or None)


def principal_from_token(token: str) -> JwtPrincipal:
    try:
        payload: dict[str, Any] = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return principal_from_payload(payload)


def principal_from_bearer(
    creds: Optional[HTTPAuthorizationCredentials],
) -> JwtPrincipal:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return principal_from_token(creds.credentials)


def principal_from_request(request: Request) -> Optional[JwtPrincipal]:
    token = get_auth_token(request)
    if not token:
        return None
    try:
        return principal_from_token(token)
    except HTTPException:
        return None


def require_cookie_principal(request: Request) -> JwtPrincipal:
    token = get_auth_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return principal_from_token(token)


def require_admin_principal(principal: JwtPrincipal) -> JwtPrincipal:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return principal


async def load_user_by_id(*, db: AsyncSession, user_id: int) -> User:
    user: Optional[User] = (
        await db.exec(select(User).where(User.id == user_id))
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def access_token_extra_claims_for_user(user: User) -> dict[str, Any]:
    claims: dict[str, Any] = {
        "is_admin": bool(getattr(user, "is_admin", False)),
        "email": user.email,
    }
    if getattr(user, "country", None):
        claims["country"] = user.country
    return claims
