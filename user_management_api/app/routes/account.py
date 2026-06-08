from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, safe_redirect
from app.core.rate_limit import check_rate_limit
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
from app.routes.deps import user_from_token
from app.web.csrf import issue_csrf_token, set_csrf_cookie, validate_csrf
from app.web.session import get_auth_token, set_auth_cookie
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
    csrf = issue_csrf_token(request)
    info = (request.query_params.get("msg") or "").strip() or None
    resp = templates.TemplateResponse(
        request,
        "account.html",
        {
            "request": request,
            "base_path": bp,
            "session_email": user.email,
            "is_admin": bool(getattr(user, "is_admin", False)),
            "user": user,
            "info": info,
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    return resp


@router.post("/account", response_class=HTMLResponse, include_in_schema=False)
async def account_update(
    request: Request,
    full_name: Optional[str] = Form(default=None),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
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

    csrf = issue_csrf_token(request)
    resp = templates.TemplateResponse(
        request,
        "account.html",
        {
            "request": request,
            "base_path": bp,
            "session_email": user.email,
            "is_admin": bool(getattr(user, "is_admin", False)),
            "user": user,
            "success": "Saved.",
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    return resp


@router.post("/account/password", response_class=HTMLResponse, include_in_schema=False)
async def account_change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
    bp = base_path(request)
    try:
        user = await _require_cookie_user(request=request, db=db)
    except HTTPException:
        return safe_redirect(
            request,
            "/login?msg=Please%20log%20in%20to%20view%20your%20Account.&next=/account",
            status_code=303,
        )

    csrf = issue_csrf_token(request)
    ctx = {
        "request": request,
        "base_path": bp,
        "session_email": user.email,
        "is_admin": bool(getattr(user, "is_admin", False)),
        "user": user,
        "csrf_token": csrf,
    }

    check_rate_limit(request, scope="password_change", email=user.email)

    if not verify_password(current_password, user.hashed_password):
        resp = templates.TemplateResponse(
            request,
            "account.html",
            {**ctx, "error": "Current password is incorrect."},
            status_code=400,
        )
        set_csrf_cookie(resp, request=request)
        return resp

    try:
        validate_new_password(new_password)
    except ValueError as e:
        resp = templates.TemplateResponse(
            request,
            "account.html",
            {**ctx, "error": str(e)},
            status_code=400,
        )
        set_csrf_cookie(resp, request=request)
        return resp

    if new_password != confirm_password:
        resp = templates.TemplateResponse(
            request,
            "account.html",
            {**ctx, "error": "New password and confirmation do not match."},
            status_code=400,
        )
        set_csrf_cookie(resp, request=request)
        return resp

    user.hashed_password = hash_password(new_password)
    bump_token_version(user)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims=token_extra_claims(user),
    )
    resp = templates.TemplateResponse(
        request,
        "account.html",
        {
            "request": request,
            "base_path": bp,
            "session_email": user.email,
            "is_admin": bool(getattr(user, "is_admin", False)),
            "user": user,
            "success": "Password updated.",
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    set_auth_cookie(resp, request=request, token=access_token)
    return resp
