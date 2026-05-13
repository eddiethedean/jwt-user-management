from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import hash_password, validate_new_password
from app.db import get_db
from app.models import PasswordResetToken, User
from app.routes.public_urls import email_browser_page_url
from app.services.email import send_password_reset_email


router = APIRouter(prefix="/password", tags=["password"])


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
        reset_url = email_browser_page_url(
            request, page="Reset password", token=raw
        )
        try:
            send_password_reset_email(to_email=email_n, reset_url=reset_url)
        except Exception:
            pass
    return {"ok": True}


@router.post("/inspect")
async def inspect_reset_token(
    payload: dict, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Helper endpoint for non-HTML clients (e.g. Streamlit) to display the
    email bound to a reset token, matching the HTML reset page behavior.
    """
    token = str(payload.get("token") or "")
    if not token:
        raise HTTPException(status_code=422, detail="token is required")
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
    return {
        "ok": True,
        "email": rec.email,
        "expires_at": rec.expires_at,
        "used_at": rec.used_at,
    }


@router.post("/reset")
async def reset_api(payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    token = str(payload.get("token") or "")
    password = str(payload.get("password") or "")
    if not token or not password:
        raise HTTPException(status_code=422, detail="token and password are required")
    try:
        validate_new_password(password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
