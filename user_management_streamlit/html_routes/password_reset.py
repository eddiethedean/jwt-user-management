from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, external_url, safe_external_redirect
from app.core.config import settings
from app.core.security import hash_password
from app.db import get_db
from app.models import PasswordResetToken, User
from app.services.email import send_password_reset_email
from user_management_streamlit.web.templates import templates


router = APIRouter(prefix="/password", tags=["password"])
log = logging.getLogger("uvicorn.error")

ADMIN_EMAIL = (os.getenv("SEED_ADMIN_EMAIL") or "admin@example.com").strip().lower()


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("/forgot-form", response_class=HTMLResponse, include_in_schema=False)
async def forgot_password_form(
    request: Request,
    email: str = Form(...),
    return_to: str = Form(default="login"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Demo UX: generate a reset link and render it on the login page.
    For real deployments, you'd email the link instead.
    """
    bp = base_path(request)
    email_n = (email or "").strip().lower()
    # Non-enumerating response: we always show the same success message.
    reset_url: Optional[str] = None

    user: Optional[User] = None
    if email_n:
        user = (await db.exec(select(User).where(User.email == email_n))).first()

    if user:
        raw = PasswordResetToken.new_raw_token()
        token_hash = PasswordResetToken.hash_token(raw)
        now = datetime.now(timezone.utc)
        rec = PasswordResetToken(
            email=email_n,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(hours=2),
            used_at=None,
        )
        db.add(rec)
        await db.commit()
        reset_url = external_url(
            request,
            f"/password/reset?token={raw}",
            public_base_url=settings.public_base_url,
        )
        try:
            log.info(
                "Password reset email: attempting send to=%s smtp_enabled=%s",
                email_n,
                bool(settings.smtp_host and settings.smtp_from_email),
            )
            send_password_reset_email(to_email=email_n, reset_url=reset_url)
            log.info("Password reset email: sent to=%s", email_n)
            # If we're actually emailing, don't render the link in the UI.
            if settings.smtp_host and settings.smtp_from_email:
                reset_url = None
        except Exception:
            # If email fails, keep demo UX (show the link).
            log.exception("Password reset email: failed to send to=%s", email_n)
            pass

    template_name = "login.html"
    ctx: dict = {
        "request": request,
        "base_path": bp,
        "success": "If the account exists, a reset link has been created.",
        "reset_email": email_n,
        "reset_url": reset_url,
    }
    return templates.TemplateResponse(request, template_name, ctx)


@router.post("/forgot")
async def forgot_password_api(
    request: Request,
    payload: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Real flow: generate a reset token and email it (non-enumerating).
    Returns ok=true regardless of whether the account exists.
    """
    email_n = (str(payload.get("email") or "")).strip().lower()
    user: Optional[User] = None
    if email_n:
        user = (await db.exec(select(User).where(User.email == email_n))).first()
    if user:
        raw = PasswordResetToken.new_raw_token()
        token_hash = PasswordResetToken.hash_token(raw)
        now = datetime.now(timezone.utc)
        rec = PasswordResetToken(
            email=email_n,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(hours=2),
            used_at=None,
        )
        db.add(rec)
        await db.commit()
        reset_url = external_url(
            request,
            f"/password/reset?token={raw}",
            public_base_url=settings.public_base_url,
        )
        try:
            send_password_reset_email(to_email=email_n, reset_url=reset_url)
        except Exception:
            pass
    return {"ok": True}


@router.post("/reset")
async def reset_api(payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    token = str(payload.get("token") or "")
    password = str(payload.get("password") or "")
    if not token or not password:
        raise HTTPException(status_code=422, detail="token and password are required")

    token_hash = PasswordResetToken.hash_token(token)
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
    if user:
        user.hashed_password = hash_password(password)
        db.add(user)
    rec.used_at = now
    db.add(rec)
    await db.commit()
    return {"ok": True}


@router.get("/reset", response_class=HTMLResponse, include_in_schema=False)
async def reset_page(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    bp = base_path(request)
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
        },
    )


@router.post("/reset-form", response_class=HTMLResponse, include_in_schema=False)
async def reset_form(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
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
            },
            status_code=404,
        )
    now = datetime.now(timezone.utc)
    if rec.used_at is not None:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "reset_email": rec.email,
                "error": "Reset link already used",
            },
            status_code=400,
        )
    if _as_utc_aware(rec.expires_at) < now:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "reset_email": rec.email,
                "error": "Reset link expired",
            },
            status_code=400,
        )

    user: Optional[User] = (
        await db.exec(select(User).where(User.email == rec.email))
    ).first()
    if user:
        user.hashed_password = hash_password(password)
        db.add(user)
    rec.used_at = now
    db.add(rec)
    await db.commit()

    return safe_external_redirect(
        request,
        "/login",
        status_code=303,
    )
