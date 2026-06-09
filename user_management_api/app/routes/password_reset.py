from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import col

from app.core.security import hash_password, validate_new_password
from app.db import get_db
from app.models import PasswordResetToken, User
from app.routes.email_links import external_password_reset_url
from app.services.email import send_password_reset_email


router = APIRouter(prefix="/password", tags=["password"])
log = logging.getLogger("uvicorn.error")


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def invalidate_unused_reset_tokens_for_email(
    *, db: AsyncSession, email: str, now: datetime
) -> None:
    email_n = (email or "").strip().lower()
    rows = (
        await db.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.email == email_n,
                col(PasswordResetToken.used_at).is_(None),
            )
        )
    ).all()
    for rec in rows:
        rec.used_at = now
        db.add(rec)


async def _claim_reset_token(
    *, db: AsyncSession, token_hash: str, now: datetime
) -> PasswordResetToken:
    stmt = (
        update(PasswordResetToken)
        .where(
            col(PasswordResetToken.token_hash) == token_hash,
            col(PasswordResetToken.used_at).is_(None),
        )
        .values(used_at=now)
    )
    conn = await db.connection()
    result = await conn.execute(stmt)
    if result.rowcount != 1:
        existing = (
            await db.exec(
                select(PasswordResetToken).where(
                    PasswordResetToken.token_hash == token_hash
                )
            )
        ).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Reset link not found")
        if existing.used_at is not None:
            raise HTTPException(status_code=400, detail="Reset link already used")
        if _as_utc_aware(existing.expires_at) < now:
            raise HTTPException(status_code=400, detail="Reset link expired")
        raise HTTPException(status_code=400, detail="Reset link already used")
    rec = (
        await db.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
    ).first()
    assert rec is not None
    if _as_utc_aware(rec.expires_at) < now:
        raise HTTPException(status_code=400, detail="Reset link expired")
    return rec


@router.post("/forgot")
async def forgot_password_api(
    request: Request,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    email_n = (str(payload.get("email") or "")).strip().lower()
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
        reset_url = external_password_reset_url(request, token=raw)
        try:
            send_password_reset_email(to_email=email_n, reset_url=reset_url)
        except Exception:
            log.exception("password_reset_email_send_failed")
    return {"ok": True}


@router.post("/inspect")
async def inspect_reset_token(
    payload: dict = Body(...), db: AsyncSession = Depends(get_db)
) -> dict:
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
async def reset_api(
    payload: dict = Body(...), db: AsyncSession = Depends(get_db)
) -> dict:
    token = str(payload.get("token") or "")
    password = str(payload.get("password") or "")
    if not token or not password:
        raise HTTPException(status_code=422, detail="token and password are required")
    try:
        validate_new_password(password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token_hash = PasswordResetToken.hash_token(token)
    now = datetime.now(timezone.utc)
    rec = await _claim_reset_token(db=db, token_hash=token_hash, now=now)

    user: Optional[User] = (
        await db.exec(select(User).where(User.email == rec.email))
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(password)
    db.add(user)
    await db.commit()
    return {"ok": True}
