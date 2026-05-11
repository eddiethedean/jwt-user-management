from __future__ import annotations

import os
import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import decode_token
from app.db import get_db
from app.models import User


router = APIRouter(tags=["admin"])
log = logging.getLogger("uvicorn.error")

bearer_scheme = HTTPBearer(auto_error=False)

ADMIN_EMAIL = (os.getenv("SEED_ADMIN_EMAIL") or "admin@example.com").strip().lower()


@router.patch("/admin/users/{user_id}")
async def admin_api_update_user(
    user_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    admin = await _require_admin_bearer(db=db, creds=creds)
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id and ("is_active" in payload or "is_admin" in payload):
        raise HTTPException(
            status_code=400, detail="You can’t modify your own role/status here"
        )

    if "full_name" in payload:
        fn = str(payload.get("full_name") or "").strip() or None
        user.full_name = fn
    if "is_active" in payload:
        user.is_active = bool(payload.get("is_active"))
    if "is_admin" in payload:
        user.is_admin = bool(payload.get("is_admin"))

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "ok": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "country": user.country,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat(),
        },
    }


@router.delete("/admin/users/{user_id}")
async def admin_api_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    admin = await _require_admin_bearer(db=db, creds=creds)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="You can’t delete your own account")
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return {"ok": True}


async def _require_user(*, db: AsyncSession, token: str) -> User:
    try:
        payload: dict[str, Any] = decode_token(token)
        user_id = int(payload.get("sub") or 0)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


async def _require_admin_user(*, db: AsyncSession, token: str) -> User:
    user = await _require_user(db=db, token=token)
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _require_admin_bearer(
    *, db: AsyncSession, creds: Optional[HTTPAuthorizationCredentials]
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    user = await _require_user(db=db, token=creds.credentials)
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


## Legacy HTML admin routes removed (Streamlit UI is supported instead).
