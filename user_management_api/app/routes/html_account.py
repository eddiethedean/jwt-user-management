from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.jwt_principal import load_user_by_id, require_cookie_principal
from app.core.security import hash_password, validate_new_password, verify_password
from app.db import get_db
from app.web.csrf import set_csrf_cookie, verify_csrf
from app.web.html_urls import html_ctx, html_redirect
from app.web.templates import templates


router = APIRouter(tags=["html-account"])


def _login_redirect(request: Request) -> Response:
    return html_redirect(
        request,
        "/login?msg=Please%20log%20in%20to%20view%20your%20Account.&next=/account",
        status_code=303,
    )


@router.get("/account", response_class=HTMLResponse, include_in_schema=False)
async def account_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        principal = require_cookie_principal(request)
        user = await load_user_by_id(db=db, user_id=principal.user_id)
    except HTTPException:
        return _login_redirect(request)
    resp = templates.TemplateResponse(
        request,
        "account.html",
        html_ctx(
            request,
            session_email=principal.email or user.email,
            user=user,
        ),
    )
    set_csrf_cookie(resp, request)
    return resp


@router.post("/account", response_class=HTMLResponse, include_in_schema=False)
async def account_update(
    request: Request,
    full_name: Optional[str] = Form(default=None),
    csrf_token: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    verify_csrf(request, csrf_token)
    try:
        principal = require_cookie_principal(request)
        user = await load_user_by_id(db=db, user_id=principal.user_id)
    except HTTPException:
        return _login_redirect(request)

    user.full_name = (full_name or "").strip() or None
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return templates.TemplateResponse(
        request,
        "account.html",
        html_ctx(
            request,
            session_email=principal.email or user.email,
            user=user,
            success="Saved.",
        ),
    )


@router.post("/account/password", response_class=HTMLResponse, include_in_schema=False)
async def account_change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    verify_csrf(request, csrf_token)
    try:
        principal = require_cookie_principal(request)
        user = await load_user_by_id(db=db, user_id=principal.user_id)
    except HTTPException:
        return _login_redirect(request)

    ctx_base = html_ctx(
        request,
        session_email=principal.email or user.email,
        user=user,
    )

    if not verify_password(current_password or "", user.hashed_password):
        return templates.TemplateResponse(
            request,
            "account.html",
            {**ctx_base, "error": "Current password is incorrect."},
            status_code=400,
        )

    try:
        validate_new_password(new_password or "")
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "account.html",
            {**ctx_base, "error": str(e)},
            status_code=400,
        )

    if (new_password or "") != (confirm_password or ""):
        return templates.TemplateResponse(
            request,
            "account.html",
            {**ctx_base, "error": "New password and confirmation do not match."},
            status_code=400,
        )

    user.hashed_password = hash_password(new_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return templates.TemplateResponse(
        request,
        "account.html",
        {**ctx_base, "success": "Password updated."},
    )
