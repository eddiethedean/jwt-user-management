from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.jwt_principal import (
    principal_from_bearer,
    require_admin_principal,
    require_cookie_principal,
)
from app.core.audit import (
    log_admin_access_denied,
    log_password_change,
    log_profile_update,
    require_user_id,
)
from app.core.security import hash_password, validate_new_password, verify_password
from app.db import get_db
from app.models import User
from app.routes.deps import bearer_scheme, get_current_user
from app.user_profile import user_to_api_dict

from app.web.html_urls import html_ctx, html_redirect
from app.web.session import get_auth_token
from app.web.templates import templates


router = APIRouter(tags=["users"])


@router.get("/users/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return user_to_api_dict(current_user)


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
    log_profile_update(
        email=current_user.email,
        user_id=require_user_id(current_user.id),
        method="api_profile",
    )
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
    if new != confirm:
        raise HTTPException(
            status_code=400, detail="New password and confirmation do not match"
        )
    try:
        validate_new_password(new)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    current_user.hashed_password = hash_password(new)
    db.add(current_user)
    await db.commit()
    log_password_change(
        email=current_user.email,
        user_id=require_user_id(current_user.id),
        method="api_password",
    )
    return {"ok": True}


@router.get("/users")
async def users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Response:
    return await _users_html_or_json(request=request, db=db, creds=creds)


async def _users_html_or_json(
    *,
    request: Request,
    db: AsyncSession,
    creds: Optional[HTTPAuthorizationCredentials],
) -> Response:
    cookie_token = get_auth_token(request)
    if cookie_token:
        principal = require_cookie_principal(request)
        if not principal.is_admin:
            log_admin_access_denied(
                email=principal.email,
                user_id=principal.user_id,
                path=request.url.path,
            )
            return templates.TemplateResponse(
                request,
                "users.html",
                html_ctx(
                    request,
                    users=[],
                    email=principal.email or "",
                    session_email=principal.email or "",
                    is_admin=False,
                    admin_error="Admin access required to list users.",
                ),
                status_code=403,
            )
        all_users = (await db.exec(select(User).order_by(text("id")))).all()
        return templates.TemplateResponse(
            request,
            "users.html",
            html_ctx(
                request,
                users=all_users,
                email=principal.email or "",
                session_email=principal.email or "",
                is_admin=True,
            ),
        )

    if not creds:
        accept = (request.headers.get("accept") or "").lower()
        wants_html = ("text/html" in accept) or ("*/*" in accept) or not accept
        if wants_html:
            return html_redirect(
                request,
                "/login?msg=Please%20log%20in%20to%20view%20Users.&next=/users",
                status_code=303,
            )
        raise HTTPException(
            status_code=401, detail="Provide Authorization: Bearer <token>"
        )
    require_admin_principal(principal_from_bearer(creds))
    all_users = (await db.exec(select(User).order_by(text("id")))).all()
    return JSONResponse(content=[user_to_api_dict(u) for u in all_users])
