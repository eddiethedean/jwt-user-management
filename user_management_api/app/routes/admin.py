from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_db
from app.models import User
from app.routes.deps import admin_from_bearer, bearer_scheme


router = APIRouter(tags=["admin"])


@router.patch("/admin/users/{user_id}")
async def admin_api_update_user(
    user_id: int,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    admin = await admin_from_bearer(db=db, creds=creds)
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        if "is_active" in payload and bool(payload.get("is_active")) != bool(
            user.is_active
        ):
            raise HTTPException(
                status_code=400,
                detail="You can’t modify your own role/status here",
            )
        if "is_admin" in payload and bool(payload.get("is_admin")) != bool(
            user.is_admin
        ):
            raise HTTPException(
                status_code=400,
                detail="You can’t modify your own role/status here",
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
    admin = await admin_from_bearer(db=db, creds=creds)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="You can’t delete your own account")
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return {"ok": True}


## Legacy HTML admin routes removed (Streamlit UI is supported instead).
