from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.email_validation import validate_email_format
from app.core.rate_limit import check_rate_limit
from app.core.security import (
    create_access_token,
    token_extra_claims,
    verify_password,
)
from app.db import get_db
from app.invite_email_domains import invite_email_domain_allowed
from app.models import User
from app.routes.email_links import external_accept_invite_url
from app.services.directory import lookup_email_async
from app.services.email import send_self_registration_email
from app.services.tokens import create_invite_token_atomic


router = APIRouter(tags=["auth"])
log = logging.getLogger("uvicorn.error")


def _self_registration_enabled() -> bool:
    from app.core.config import settings as live_settings

    return live_settings.self_registration_enabled


async def _register_user(
    *,
    request: Request,
    email_n: str,
    db: AsyncSession,
) -> tuple[bool, bool, Optional[str]]:
    """
    Create a self-registration invite and send email.
    Returns (ok, email_sent, error_message).
    """
    if not email_n:
        return False, False, "Email is required"

    existing: Optional[User] = (
        await db.exec(select(User).where(User.email == email_n))
    ).first()
    if existing:
        return True, False, None

    if not invite_email_domain_allowed(email_n):
        return False, False, "Email domain is not allowed for registration"

    if settings.directory_lookup_url:
        rec = None
        try:
            rec = await lookup_email_async(email_n)
        except Exception:
            rec = None
        if settings.directory_lookup_required and not rec:
            return False, False, "Email not found in directory"

    if not (settings.smtp_host and settings.smtp_from_email):
        return False, False, "Self-registration email is not configured"

    raw = await create_invite_token_atomic(
        db, email=email_n, grant_admin=False, expires_hours=2
    )

    setup_url = external_accept_invite_url(request, token=raw)
    email_sent = False
    try:
        send_self_registration_email(to_email=email_n, setup_url=setup_url)
        email_sent = True
    except Exception:
        log.exception("self_registration_email_send_failed")

    if not email_sent:
        return (
            False,
            False,
            "Could not send registration email. Please try again later.",
        )
    return True, True, None


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not _self_registration_enabled():
        raise HTTPException(status_code=403, detail="Self-registration is disabled")
    try:
        email_n = validate_email_format(email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    check_rate_limit(request, scope="register", email=email_n)

    ok, _email_sent, err = await _register_user(request=request, email_n=email_n, db=db)

    if err:
        status = (
            503
            if "not configured" in err.lower() or "could not send" in err.lower()
            else 400
        )
        raise HTTPException(status_code=status, detail=err)

    return {"ok": ok}


@router.post("/auth/token")
async def token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        username = validate_email_format(form.username)
    except ValueError:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    check_rate_limit(request, scope="auth_token", email=username)
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
