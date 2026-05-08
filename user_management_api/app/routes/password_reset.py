from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import external_url
from app.core.config import settings
from app.core.security import hash_password
from app.db import get_db
from app.models import PasswordResetToken, User
from app.services.email import send_password_reset_email


router = APIRouter(prefix="/password", tags=["password"])
log = logging.getLogger("uvicorn.error")

ADMIN_EMAIL = (os.getenv("SEED_ADMIN_EMAIL") or "admin@example.com").strip().lower()


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
