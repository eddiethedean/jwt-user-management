"""Shared HTML-route auth helpers (cookie and bearer tokens)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from jose import JWTError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import decode_token
from app.models import User


def _validate_token_version(payload: dict[str, Any], user: User) -> None:
    expected = int(getattr(user, "token_version", 0) or 0)
    if "tv" in payload:
        if int(payload.get("tv") or 0) != expected:
            raise HTTPException(status_code=401, detail="Invalid token")
    elif expected != 0:
        raise HTTPException(status_code=401, detail="Invalid token")


async def user_from_token(
    *, db: AsyncSession, token: str, require_admin: bool = False
) -> User:
    try:
        payload: dict[str, Any] = decode_token(token)
        user_id = int(payload.get("sub") or 0)
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user: Optional[User] = (
        await db.exec(select(User).where(User.id == user_id))
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    _validate_token_version(payload, user)
    if not getattr(user, "is_active", True):
        raise HTTPException(status_code=403, detail="User is inactive")
    if require_admin and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
