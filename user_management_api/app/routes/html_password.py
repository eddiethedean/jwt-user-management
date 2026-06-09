from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.core.config as app_config
from app.core.security import validate_new_password
from app.db import get_db
from app.models import PasswordResetToken, User
from app.routes.email_links import external_password_reset_url
from app.routes.password_reset import (
    _claim_reset_token,
    invalidate_unused_reset_tokens_for_email,
)
from app.services.email import send_password_reset_email
from app.web.html_urls import html_base_path, html_redirect
from app.web.templates import templates


router = APIRouter(prefix="/password", tags=["html-password"])
log = logging.getLogger("uvicorn.error")


def _expose_reset_url() -> bool:
    return bool(getattr(app_config._defaults, "EXPOSE_SETUP_URLS_IN_RESPONSE", False))


@router.post("/forgot-form", response_class=HTMLResponse, include_in_schema=False)
async def forgot_password_form(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = html_base_path(request)
    email_n = (email or "").strip().lower()
    reset_url: Optional[str] = None

    user: Optional[User] = None
    if email_n:
        user = (await db.exec(select(User).where(User.email == email_n))).first()

    if user:
        now = datetime.now(timezone.utc)
        await invalidate_unused_reset_tokens_for_email(db=db, email=email_n, now=now)
        raw = PasswordResetToken.new_raw_token()
        token_hash = PasswordResetToken.hash_token(raw)
        rec = PasswordResetToken(
            email=email_n,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(hours=2),
            used_at=None,
        )
        db.add(rec)
        await db.commit()
        built_url = external_password_reset_url(request, token=raw)
        try:
            send_password_reset_email(to_email=email_n, reset_url=built_url)
        except Exception:
            log.exception("password_reset_email_send_failed")
        reset_url = built_url if _expose_reset_url() else None

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "base_path": bp,
            "success": "If the account exists, a reset link has been sent.",
            "reset_email": email_n,
            "reset_url": reset_url,
        },
    )


@router.get("/reset", response_class=HTMLResponse, include_in_schema=False)
async def reset_page(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    bp = html_base_path(request)
    mpl = app_config.settings.min_password_length
    token_hash = PasswordResetToken.hash_token(token)
    rec: Optional[PasswordResetToken] = (
        await db.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
    ).first()
    if not rec:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "error": "Reset link not found",
                "min_password_length": mpl,
            },
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {
            "request": request,
            "base_path": bp,
            "token": token,
            "reset_email": rec.email,
            "min_password_length": mpl,
        },
    )


@router.post("/reset-form", response_class=HTMLResponse, include_in_schema=False)
async def reset_form(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = html_base_path(request)
    mpl = app_config.settings.min_password_length
    ctx_base = {
        "request": request,
        "base_path": bp,
        "token": token,
        "min_password_length": mpl,
    }

    try:
        validate_new_password(password)
        token_hash = PasswordResetToken.hash_token(token)
        now = datetime.now(timezone.utc)
        rec = await _claim_reset_token(db=db, token_hash=token_hash, now=now)
        user: Optional[User] = (
            await db.exec(select(User).where(User.email == rec.email))
        ).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        from app.core.security import hash_password

        user.hashed_password = hash_password(password)
        db.add(user)
        await db.commit()
    except HTTPException as e:
        token_hash = PasswordResetToken.hash_token(token)
        rec = (
            await db.exec(
                select(PasswordResetToken).where(
                    PasswordResetToken.token_hash == token_hash
                )
            )
        ).first()
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                **ctx_base,
                "reset_email": rec.email if rec else "",
                "error": e.detail,
            },
            status_code=e.status_code,
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {**ctx_base, "error": str(e)},
            status_code=400,
        )

    return html_redirect(request, "/login", status_code=303, external=True)
