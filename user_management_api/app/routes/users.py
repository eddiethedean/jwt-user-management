from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, safe_external_redirect, safe_redirect
from app.core.security import decode_token, hash_password, verify_password
from app.db import get_db
from app.models import User
from app.web.session import get_auth_token, set_auth_cookie
from app.web.templates import templates


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


@router.get("/users", response_class=Response)
async def users(
    request: Request,
    token: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Response:
    """
    One route with two modes:\n+    - HTML mode: uses the HttpOnly cookie (or legacy `?token=...`).\n+    - JSON mode: provide `Authorization: Bearer <token>`.\n+"""
    bp = base_path(request)

    if token:
        # Promote legacy/demo URL token into the cookie and clean up the URL.
        try:
            payload: dict[str, Any] = decode_token(token)
            user_id = int(payload.get("sub") or 0)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = (await db.exec(select(User).where(User.id == user_id))).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        resp = safe_external_redirect(
            request,
            "/users",
            status_code=303,
        )
        set_auth_cookie(resp, request=request, token=token)
        return resp

    cookie_token = get_auth_token(request)
    if cookie_token:
        try:
            payload = decode_token(cookie_token)
            user_id = int(payload.get("sub") or 0)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = (await db.exec(select(User).where(User.id == user_id))).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        users = (await db.exec(select(User).order_by(text("id")))).all()
        return templates.TemplateResponse(
            request,
            "users.html",
            {
                "request": request,
                "users": users,
                "email": user.email,
                "session_email": user.email,
                "is_admin": bool(getattr(user, "is_admin", False)),
                "base_path": bp,
            },
        )

    if not creds:
        # Browser navigation (e.g. clicking "Users" in the navbar) should go to login.
        # Keep JSON 401 for API callers.
        accept = (request.headers.get("accept") or "").lower()
        wants_html = ("text/html" in accept) or ("*/*" in accept) or not accept
        if wants_html:
            return safe_redirect(
                request,
                "/login?msg=Please%20log%20in%20to%20view%20Users.&next=/users",
                status_code=303,
            )
        raise HTTPException(
            status_code=401, detail="Provide Authorization: Bearer <token>"
        )
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
