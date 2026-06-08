from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.email_validation import validate_email_format
from app.core.rate_limit import check_rate_limit
from app.core.security import bump_token_version, hash_password, validate_new_password
from app.db import get_db
from app.models import PasswordResetToken, User
from app.routes.email_links import external_password_reset_url
from app.schemas.password import (
    ForgotPasswordRequest,
    InspectResetRequest,
    ResetPasswordRequest,
)
from app.services.email import send_password_reset_email
from app.services.tokens import create_reset_token_atomic, try_consume_reset_token


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
    request: Request,
    payload: InspectResetRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Public helper for Streamlit reset-password UI (token required in body).
    Rate-limited; does not require admin auth.
    """
    check_rate_limit(request, scope="password_inspect")
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
