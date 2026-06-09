from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import decode_token
from app.db import get_db
from app.models import User


bearer_scheme = HTTPBearer(auto_error=False)


def _validate_token_version(payload: dict[str, Any], user: User) -> None:
    expected = int(getattr(user, "token_version", 0) or 0)
    if "tv" in payload:
        if int(payload.get("tv") or 0) != expected:
            raise HTTPException(status_code=401, detail="Invalid token")
    elif expected != 0:
        raise HTTPException(status_code=401, detail="Invalid token")


async def _user_from_payload(*, db: AsyncSession, payload: dict[str, Any]) -> User:
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")
    user: Optional[User] = (
        await db.exec(select(User).where(User.id == user_id))
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    _validate_token_version(payload, user)
    return user


async def user_from_bearer(
    *, db: AsyncSession, creds: Optional[HTTPAuthorizationCredentials]
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload: dict[str, Any] = decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return await _user_from_payload(db=db, payload=payload)


async def admin_from_bearer(
    *, db: AsyncSession, creds: Optional[HTTPAuthorizationCredentials]
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload: dict[str, Any] = decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not bool(payload.get("is_admin", False)):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await _user_from_payload(db=db, payload=payload)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    return await user_from_bearer(db=db, creds=creds)


async def user_from_token(
    *, db: AsyncSession, token: str, require_admin: bool = False
) -> User:
    try:
        payload: dict[str, Any] = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if require_admin and not bool(payload.get("is_admin", False)):
        raise HTTPException(status_code=403, detail="Admin access required")
    return await _user_from_payload(db=db, payload=payload)
