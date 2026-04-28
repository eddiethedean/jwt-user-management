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


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _public_url(path: str) -> str:
    base: str = (settings.public_base_url or "http://localhost:8000").rstrip("/")
    bp: str = (settings.base_path or "").rstrip("/")
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    return f"{base}{bp}{p}"


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
    email = _norm_email(str(payload.email))
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

    reset_url: str = _public_url(f"/password/reset?token={token}")
    send_password_reset_email(to_email=email, reset_url=reset_url)
    return ForgotPasswordResponse(ok=True)


@router.get("/reset", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str) -> HTMLResponse:
    base_path = str(request.scope.get("root_path") or "").rstrip("/")
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {"request": request, "token": token, "base_path": base_path},
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
        # Use SQLAlchemy `Column` access for typed SQL expressions.
        .where(getattr(PasswordResetToken, "__table__").c.token_hash == token_hash)
        .where(getattr(PasswordResetToken, "__table__").c.used_at.is_(None))
        .where(getattr(PasswordResetToken, "__table__").c.expires_at >= now)
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if getattr(res, "rowcount", 0) != 1:
        refreshed: Optional[PasswordResetToken] = db.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
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
    base_path = str(request.scope.get("root_path") or "").rstrip("/")
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
            {
                "request": request,
                "token": token,
                "error": e.detail,
                "base_path": base_path,
            },
            status_code=e.status_code,
        )
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {"request": request, "token": token, "success": True, "base_path": base_path},
    )
