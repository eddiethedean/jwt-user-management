from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.rate_limit import check_rate_limit
from app.core.roles import display_user_roles
from app.core.security import (
    bump_token_version,
    create_access_token,
    hash_password,
    token_extra_claims,
    validate_new_password,
    verify_password,
)
from app.db import get_db
from app.models import User
from app.routes.deps import admin_from_bearer, bearer_scheme, get_current_user


router = APIRouter(tags=["users"])


@router.get("/users/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "country": current_user.country,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "roles": display_user_roles(current_user, settings.user_roles),
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
    request: Request,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    check_rate_limit(request, scope="password_change", email=current_user.email)
    cur = str(payload.get("current_password") or "")
    new = str(payload.get("new_password") or "")
    confirm = str(payload.get("confirm_password") or "")
    if not verify_password(cur, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if new != confirm:
        raise HTTPException(
            status_code=400, detail="New password and confirmation do not match"
        )
    try:
        validate_new_password(new)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if verify_password(new, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from your current password",
        )
    current_user.hashed_password = hash_password(new)
    bump_token_version(current_user)
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    access_token = create_access_token(
        subject=str(current_user.id),
        extra_claims=token_extra_claims(current_user),
    )
    return {"ok": True, "access_token": access_token, "token_type": "bearer"}


@router.get("/users")
async def users(
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> JSONResponse:
    _ = await admin_from_bearer(db=db, creds=creds)
    all_users = (await db.exec(select(User).order_by(text("id")))).all()
    return JSONResponse(
        content=[
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "country": u.country,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "roles": display_user_roles(u, settings.user_roles),
                "created_at": u.created_at.isoformat(),
            }
            for u in all_users
        ]
    )
