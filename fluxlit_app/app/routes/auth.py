from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    token_extra_claims,
    verify_password,
)
from app.db import get_db
from app.invite_email_domains import invite_email_domain_allowed
from app.models import InviteToken, User
from app.routes.email_links import external_accept_invite_url
from app.services.email import send_self_registration_email
from app.services.tokens import invalidate_unused_invite_tokens


router = APIRouter(tags=["auth"])
log = logging.getLogger("uvicorn.error")


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    email_n = _norm_email(email)
    if not email_n:
        raise HTTPException(status_code=400, detail="Email is required")

    existing: Optional[User] = (
        await db.exec(select(User).where(User.email == email_n))
    ).first()
    if existing:
        return {"ok": True, "email_sent": False}

    if not invite_email_domain_allowed(email_n):
        raise HTTPException(
            status_code=400,
            detail="Email domain is not allowed for registration",
        )

    if not (settings.smtp_host and settings.smtp_from_email):
        raise HTTPException(
            status_code=503,
            detail="Self-registration email is not configured",
        )

    raw = InviteToken.new_raw_token()
    token_hash = InviteToken.hash_token(raw)
    now = datetime.now(timezone.utc)
    await invalidate_unused_invite_tokens(db, email=email_n, now=now)
    invite = InviteToken(
        email=email_n,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(hours=2),
        used_at=None,
        grant_admin=False,
    )
    db.add(invite)
    await db.commit()

    setup_url = external_accept_invite_url(request, token=raw)
    email_sent = False
    try:
        send_self_registration_email(to_email=email_n, setup_url=setup_url)
        email_sent = True
    except Exception:
        log.exception("self_registration_email_send_failed")

    return {"ok": True, "email_sent": email_sent}


@router.post("/auth/token")
async def token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    username = _norm_email(form.username)
    user: Optional[User] = (
        await db.exec(select(User).where(User.email == username))
    ).first()
    if (
        not user
        or not getattr(user, "is_active", True)
        or not verify_password(form.password, user.hashed_password)
    ):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims=token_extra_claims(user),
    )
    return {"access_token": access_token, "token_type": "bearer"}
