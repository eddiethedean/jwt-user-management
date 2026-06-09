from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.core.config as app_config
from app.auth.jwt_principal import access_token_extra_claims_for_user
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.db import get_db
from app.models import User
from app.services.email import send_self_registration_email
from app.services.self_registration import register_email_for_setup

# Re-export for tests that patch ``app.routes.auth.send_self_registration_email``.
__all__ = ["send_self_registration_email"]


router = APIRouter(tags=["auth"])


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if app_config.settings.html_ui_enabled:
        from app.routes.html_auth import register_handler

        return await register_handler(request=request, email=email, db=db)

    result = await register_email_for_setup(request=request, email=email, db=db)
    if not result.ok:
        raise HTTPException(
            status_code=400, detail=result.error or "Registration failed"
        )
    if (
        app_config.settings.smtp_host
        and app_config.settings.smtp_from_email
        and not result.email_sent
    ):
        raise HTTPException(status_code=503, detail="Could not send registration email")
    body: dict = {"ok": True, "email_sent": result.email_sent}
    if result.setup_url:
        body["setup_url"] = result.setup_url
    return body


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
        extra_claims=access_token_extra_claims_for_user(user),
    )
    return {"access_token": access_token, "token_type": "bearer"}
