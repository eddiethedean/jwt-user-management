from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from jose import JWTError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, safe_redirect
from app.core.security import decode_token, hash_password, verify_password
from app.db import get_db
from app.models import User
from app.web.session import get_auth_token
from app.web.templates import templates


router = APIRouter(tags=["account"])


async def _require_cookie_user(*, request: Request, db: AsyncSession) -> User:
    token = get_auth_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload: dict[str, Any] = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        user_id = int(payload.get("sub") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")
    user: Optional[User] = (
        await db.exec(select(User).where(User.id == user_id))
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/account", response_class=HTMLResponse, include_in_schema=False)
async def account_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    try:
        user = await _require_cookie_user(request=request, db=db)
    except HTTPException:
        return safe_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20your%20Account.&next=/account",
            status_code=303,
        )
    return templates.TemplateResponse(
        request,
        "account.html",
        {
            "request": request,
            "base_path": bp,
            "session_email": user.email,
            "user": user,
        },
    )


@router.post("/account", response_class=HTMLResponse, include_in_schema=False)
async def account_update(
    request: Request,
    full_name: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    try:
        user = await _require_cookie_user(request=request, db=db)
    except HTTPException:
        return safe_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20your%20Account.&next=/account",
            status_code=303,
        )

    user.full_name = (full_name or "").strip() or None
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return templates.TemplateResponse(
        request,
        "account.html",
        {
            "request": request,
            "base_path": bp,
            "session_email": user.email,
            "user": user,
            "success": "Saved.",
        },
    )


@router.post("/account/password", response_class=HTMLResponse, include_in_schema=False)
async def account_change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    try:
        user = await _require_cookie_user(request=request, db=db)
    except HTTPException:
        return safe_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20your%20Account.&next=/account",
            status_code=303,
        )

    cur = current_password or ""
    nxt = new_password or ""
    cfm = confirm_password or ""

    if not verify_password(cur, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "account.html",
            {
                "request": request,
                "base_path": bp,
                "session_email": user.email,
                "user": user,
                "error": "Current password is incorrect.",
            },
            status_code=400,
        )

    if len(nxt) < 8:
        return templates.TemplateResponse(
            request,
            "account.html",
            {
                "request": request,
                "base_path": bp,
                "session_email": user.email,
                "user": user,
                "error": "New password must be at least 8 characters.",
            },
            status_code=400,
        )

    if nxt != cfm:
        return templates.TemplateResponse(
            request,
            "account.html",
            {
                "request": request,
                "base_path": bp,
                "session_email": user.email,
                "user": user,
                "error": "New password and confirmation do not match.",
            },
            status_code=400,
        )

    user.hashed_password = hash_password(nxt)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return templates.TemplateResponse(
        request,
        "account.html",
        {
            "request": request,
            "base_path": bp,
            "session_email": user.email,
            "user": user,
            "success": "Password updated.",
        },
    )
