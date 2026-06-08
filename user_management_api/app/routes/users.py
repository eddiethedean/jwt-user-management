from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import safe_redirect
from app.core.rate_limit import check_rate_limit
from app.core.security import (
    bump_token_version,
    hash_password,
    validate_new_password,
    verify_password,
)
from app.core.config import settings
from app.core.roles import display_user_roles
from app.db import get_db
from app.models import User
from app.routes.deps import bearer_scheme, get_current_user, user_from_token
from app.web.session import get_auth_token


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
    check_rate_limit(
        request, scope="password_change", email=current_user.email
    )
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
    current_user.hashed_password = hash_password(new)
    bump_token_version(current_user)
    db.add(current_user)
    await db.commit()
    return {"ok": True}


@router.get("/users", response_class=Response)
async def users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Response:
    """Admin-only user directory (JSON bearer). Browser sessions redirect elsewhere."""
    cookie_token = get_auth_token(request)
    if cookie_token:
        user = await user_from_token(db=db, token=cookie_token)
        dest = "/admin" if getattr(user, "is_admin", False) else "/account"
        return safe_redirect(request, dest, status_code=303)

    if not creds:
        accept = (request.headers.get("accept") or "").lower()
        wants_html = ("text/html" in accept) or ("*/*" in accept) or not accept
        if wants_html:
            return safe_redirect(
                request,
                "/login?msg=Please%20log%20in.&next=/admin",
                status_code=303,
            )
        raise HTTPException(
            status_code=401, detail="Provide Authorization: Bearer <token>"
        )
    _ = await user_from_token(db=db, token=creds.credentials, require_admin=True)
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
