from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import decode_token, hash_password, verify_password
from app.db import get_db
from app.models import User


router = APIRouter(tags=["users"])

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload: dict[str, Any] = decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
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
    return user


@router.get("/users/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "country": current_user.country,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "created_at": current_user.created_at.isoformat(),
    }


@router.patch("/users/me")
async def update_me(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    full_name = payload.get("full_name")
    full_name_s = None if full_name is None else str(full_name).strip()
    current_user.full_name = full_name_s or None
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return {"ok": True, "full_name": current_user.full_name}


@router.post("/users/me/password")
async def change_my_password(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    cur = str(payload.get("current_password") or "")
    new = str(payload.get("new_password") or "")
    confirm = str(payload.get("confirm_password") or "")
    if not verify_password(cur, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(new) < 8:
        raise HTTPException(
            status_code=400, detail="New password must be at least 8 characters"
        )
    if new != confirm:
        raise HTTPException(
            status_code=400, detail="New password and confirmation do not match"
        )
    current_user.hashed_password = hash_password(new)
    db.add(current_user)
    await db.commit()
    return {"ok": True}


@router.get("/users")
async def users(
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> JSONResponse:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    _ = await get_current_user(db=db, creds=creds)
    users = (await db.exec(select(User).order_by(text("id")))).all()
    return JSONResponse(
        content=[
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "country": u.country,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]
    )
