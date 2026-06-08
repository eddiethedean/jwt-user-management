from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, safe_redirect
from app.core.security import hash_password, validate_new_password, verify_password
from app.db import get_db
from app.models import User
from app.routes.deps import user_from_token
from app.web.session import get_auth_token
from app.web.templates import templates


router = APIRouter(tags=["account"])


async def _require_cookie_user(*, request: Request, db: AsyncSession) -> User:
    token = get_auth_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return await user_from_token(db=db, token=token)


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

    if not verify_password(current_password, user.hashed_password):
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

    try:
        validate_new_password(new_password)
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "account.html",
            {
                "request": request,
                "base_path": bp,
                "session_email": user.email,
                "user": user,
                "error": str(e),
            },
            status_code=400,
        )

    if new_password != confirm_password:
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

    from app.core.security import bump_token_version

    user.hashed_password = hash_password(new_password)
    bump_token_version(user)
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
