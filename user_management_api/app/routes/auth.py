from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import external_url
from app.core.config import settings
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.db import get_db
from app.models import InviteToken, User
from app.services.directory import lookup_email
from app.services.email import send_self_registration_email


router = APIRouter(tags=["auth"])


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
        raise HTTPException(status_code=400, detail="Email already exists")

    # Optional directory-backed validation for self-registration email.
    if settings.directory_lookup_url:
        rec = None
        try:
            rec = lookup_email(email_n)
        except Exception:
            rec = None
        if settings.directory_lookup_required and not rec:
            raise HTTPException(status_code=400, detail="Email not found in directory")

    try:
        raw = InviteToken.new_raw_token()
        token_hash = InviteToken.hash_token(raw)
        now = datetime.now(timezone.utc)
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

        setup_url = external_url(
            request,
            f"/invites/accept?token={raw}",
            public_base_url=settings.public_base_url,
        )
        send_self_registration_email(to_email=email_n, setup_url=setup_url)
    except Exception:
        # Email should not block successful registration.
        pass
    return {"ok": True}


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
        extra_claims={"country": user.country}
        if getattr(user, "country", None)
        else None,
    )
    return {"access_token": access_token, "token_type": "bearer"}
