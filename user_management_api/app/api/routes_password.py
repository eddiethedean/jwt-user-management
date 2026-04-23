import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import update
from sqlmodel import Session, select
from starlette.requests import Request
from typing import Optional

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.password import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.security.origin import require_same_origin
from app.services.emailer import send_password_reset_email


router = APIRouter(prefix="/password", tags=["password"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("/forgot", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    """
    Always returns ok=True to avoid account enumeration.
    If the user exists, a reset email is sent with a single-use token link.
    """
    email = str(payload.email)
    user: Optional[User] = db.exec(select(User).where(User.email == email)).first()
    if not user or not user.is_active:
        return ForgotPasswordResponse(ok=True)

    token: str = secrets.token_urlsafe(32)
    token_hash: str = _hash_token(token)
    now: datetime = datetime.now(timezone.utc)
    expires_at: datetime = now + timedelta(minutes=30)

    prt = PasswordResetToken(email=email, token_hash=token_hash, expires_at=expires_at)
    db.add(prt)
    db.commit()

    base: str = (settings.public_base_url or "http://localhost:8000").rstrip("/")
    reset_url: str = f"{base}/password/reset?token={token}"
    send_password_reset_email(to_email=email, reset_url=reset_url)
    return ForgotPasswordResponse(ok=True)


@router.get("/reset", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "reset_password.html", {"request": request, "token": token}
    )


@router.post("/reset", response_model=ResetPasswordResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    token: str = payload.token
    password: str = payload.password
    token_hash: str = _hash_token(token)
    prt: Optional[PasswordResetToken] = db.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).first()
    if not prt:
        raise HTTPException(status_code=404, detail="Reset token not found")
    now: datetime = datetime.now(timezone.utc)
    if _as_utc(prt.expires_at) < now:
        raise HTTPException(status_code=400, detail="Reset token expired")

    # Single-use enforcement (atomic): mark reset token as used only if unused and unexpired.
    res = db.exec(
        update(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .where(PasswordResetToken.used_at.is_(None))
        .where(PasswordResetToken.expires_at >= now)
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if getattr(res, "rowcount", 0) != 1:
        refreshed: Optional[PasswordResetToken] = db.exec(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        ).first()
        if not refreshed:
            raise HTTPException(status_code=404, detail="Reset token not found")
        if refreshed.used_at is not None:
            raise HTTPException(status_code=400, detail="Reset token already used")
        if _as_utc(refreshed.expires_at) < now:
            raise HTTPException(status_code=400, detail="Reset token expired")
        raise HTTPException(status_code=400, detail="Reset token could not be used")

    user: Optional[User] = db.exec(select(User).where(User.email == prt.email)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(password)
    db.add(user)
    db.commit()
    return ResetPasswordResponse(ok=True)


@router.post("/reset-form", response_class=HTMLResponse)
def reset_password_form(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        require_same_origin(request)
    except ValueError:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    try:
        reset_password(
            payload=ResetPasswordRequest(token=token, password=password), db=db
        )
    except HTTPException as e:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"request": request, "token": token, "error": e.detail},
            status_code=e.status_code,
        )
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {"request": request, "token": token, "success": True},
    )
