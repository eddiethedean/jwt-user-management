from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.web.html_urls import html_base_path, html_redirect
from app.core.email_validation import validate_email_format
from app.core.rate_limit import check_rate_limit
from app.core.security import bump_token_version, hash_password, validate_new_password
from app.db import get_db
from app.models import PasswordResetToken, User
from app.routes.deps import admin_from_bearer, bearer_scheme
from app.routes.email_links import external_password_reset_url
from app.schemas.password import (
    ForgotPasswordRequest,
    InspectResetRequest,
    ResetPasswordRequest,
)
from app.services.email import send_password_reset_email
from app.services.tokens import create_reset_token_atomic, try_consume_reset_token
from app.web.csrf import issue_csrf_token, set_csrf_cookie, validate_csrf
from app.web.templates import templates


router = APIRouter(prefix="/password", tags=["password"])
log = logging.getLogger("uvicorn.error")


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _issue_reset_token(
    request: Request, *, db: AsyncSession, email_n: str
) -> None:
    user = (await db.exec(select(User).where(User.email == email_n))).first()
    if not user:
        return
    raw = await create_reset_token_atomic(db, email=email_n)
    reset_url = external_password_reset_url(request, token=raw)
    try:
        send_password_reset_email(to_email=email_n, reset_url=reset_url)
    except Exception:
        log.exception("password_reset_email_send_failed")


@router.post("/forgot-form", response_class=HTMLResponse, include_in_schema=False)
async def forgot_password_form(
    request: Request,
    email: str = Form(...),
    return_to: str = Form(default="login"),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
    bp = html_base_path(request)
    raw_email = (email or "").strip()
    try:
        email_n = validate_email_format(email)
    except ValueError:
        rate_key = (
            hashlib.sha256(raw_email.encode("utf-8")).hexdigest() if raw_email else None
        )
        check_rate_limit(request, scope="password_forgot", email=rate_key)
        csrf = issue_csrf_token(request)
        resp = templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "base_path": bp,
                "success": "If the account exists, a reset link has been sent.",
                "csrf_token": csrf,
            },
        )
        set_csrf_cookie(resp, request=request)
        return resp
    check_rate_limit(request, scope="password_forgot", email=email_n)
    await _issue_reset_token(request, db=db, email_n=email_n)

    csrf = issue_csrf_token(request)
    resp = templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "base_path": bp,
            "success": "If the account exists, a reset link has been sent.",
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    return resp


@router.post("/forgot")
async def forgot_password_api(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        email_n = validate_email_format(payload.email)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    check_rate_limit(request, scope="password_forgot", email=email_n)
    await _issue_reset_token(request, db=db, email_n=email_n)
    return {"ok": True}


@router.post("/inspect")
async def inspect_reset_token(
    payload: InspectResetRequest,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await admin_from_bearer(db=db, creds=creds)
    token_hash = PasswordResetToken.hash_token(payload.token)
    rec: Optional[PasswordResetToken] = (
        await db.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Reset link not found")
    return {
        "ok": True,
        "email": rec.email,
        "expires_at": rec.expires_at,
        "used_at": rec.used_at,
    }


@router.post("/reset")
async def reset_api(
    request: Request,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not (payload.token or "").strip() or not (payload.password or "").strip():
        raise HTTPException(status_code=422, detail="token and password are required")
    check_rate_limit(request, scope="password_reset")
    try:
        validate_new_password(payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token_hash = PasswordResetToken.hash_token(payload.token)
    rec: Optional[PasswordResetToken] = (
        await db.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Reset link not found")
    now = datetime.now(timezone.utc)
    if rec.used_at is not None:
        raise HTTPException(status_code=400, detail="Reset link already used")
    if _as_utc_aware(rec.expires_at) < now:
        raise HTTPException(status_code=400, detail="Reset link expired")

    user: Optional[User] = (
        await db.exec(select(User).where(User.email == rec.email))
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Reset link invalid or expired")

    consumed = await try_consume_reset_token(db, token_hash=token_hash, now=now)
    if consumed != 1:
        raise HTTPException(status_code=400, detail="Reset link already used")

    user.hashed_password = hash_password(payload.password)
    bump_token_version(user)
    db.add(user)
    await db.commit()
    return {"ok": True}


@router.get("/reset", response_class=HTMLResponse, include_in_schema=False)
async def reset_page(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    bp = html_base_path(request)
    csrf = issue_csrf_token(request)
    token_hash = PasswordResetToken.hash_token(token)
    rec: Optional[PasswordResetToken] = (
        await db.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
    ).first()
    if not rec:
        resp = templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "error": "Reset link not found",
                "csrf_token": csrf,
            },
            status_code=404,
        )
        set_csrf_cookie(resp, request=request)
        return resp
    resp = templates.TemplateResponse(
        request,
        "reset_password.html",
        {
            "request": request,
            "base_path": bp,
            "token": token,
            "reset_email": rec.email,
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    return resp


@router.post("/reset-form", response_class=HTMLResponse, include_in_schema=False)
async def reset_form(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    validate_csrf(request, form_token=csrf_token)
    bp = html_base_path(request)
    check_rate_limit(request, scope="password_reset")
    try:
        validate_new_password(password)
    except ValueError as e:
        csrf = issue_csrf_token(request)
        resp = templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "reset_email": "",
                "error": str(e),
                "csrf_token": csrf,
            },
            status_code=400,
        )
        set_csrf_cookie(resp, request=request)
        return resp
    try:
        await reset_api(
            request,
            ResetPasswordRequest(token=token, password=password),
            db,
        )
    except HTTPException as e:
        csrf = issue_csrf_token(request)
        resp = templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "reset_email": "",
                "error": str(e.detail),
                "csrf_token": csrf,
            },
            status_code=e.status_code,
        )
        set_csrf_cookie(resp, request=request)
        return resp

    return html_redirect(request, "/login", status_code=303, external=True)
