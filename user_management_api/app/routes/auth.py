from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.jwt_principal import access_token_extra_claims_for_user
from app.core.audit import log_auth_failure, log_auth_success, require_user_id
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.db import get_db
from app.models import User
from app.services.email import send_self_registration_email

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
    from app.routes.html_auth import register_handler

    return await register_handler(request=request, email=email, db=db)


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
        reason = "invalid_credentials"
        if user and not getattr(user, "is_active", True):
            reason = "account_disabled"
        log_auth_failure(method="api_token", email=username, reason=reason)
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims=access_token_extra_claims_for_user(user),
    )
    log_auth_success(
        method="api_token",
        email=user.email,
        user_id=require_user_id(user.id),
        is_admin=bool(user.is_admin),
    )
    return {"access_token": access_token, "token_type": "bearer"}
