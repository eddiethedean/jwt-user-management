from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from fastapi_workbench import external_url, safe_external_redirect
from app.core.config import settings
from app.core.security import hash_password
from app.db import get_db
from app.models import PasswordResetToken, User


router = APIRouter(prefix="/password", tags=["password"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("/forgot-form", response_class=HTMLResponse, include_in_schema=False)
def forgot_password_form(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    """
    Demo UX: generate a reset link and render it on the login page.
    For real deployments, you'd email the link instead.
    """
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    email_n = (email or "").strip().lower()
    # Non-enumerating response: we always show the same success message.
    reset_url: Optional[str] = None

    user: Optional[User] = None
    if email_n:
        user = db.exec(select(User).where(User.email == email_n)).first()

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
        db.commit()
        reset_url = external_url(
            request,
            f"/password/reset?token={raw}",
            public_base_url=settings.public_base_url,
        )

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "base_path": bp,
            "success": "If the account exists, a reset link has been created.",
            "reset_email": email_n,
            "reset_url": reset_url,
        },
    )


@router.get("/reset", response_class=HTMLResponse, include_in_schema=False)
def reset_page(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    token_hash = PasswordResetToken.hash_token(token)
    rec: Optional[PasswordResetToken] = db.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).first()
    if not rec:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "error": "Reset link not found",
            },
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {
            "request": request,
            "base_path": bp,
            "token": token,
            "reset_email": rec.email,
        },
    )


@router.post("/reset-form", response_class=HTMLResponse, include_in_schema=False)
def reset_form(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    token_hash = PasswordResetToken.hash_token(token)
    rec: Optional[PasswordResetToken] = db.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).first()
    if not rec:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "error": "Reset link not found",
            },
            status_code=404,
        )
    now = datetime.now(timezone.utc)
    if rec.used_at is not None:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "reset_email": rec.email,
                "error": "Reset link already used",
            },
            status_code=400,
        )
    if _as_utc_aware(rec.expires_at) < now:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {
                "request": request,
                "base_path": bp,
                "token": token,
                "reset_email": rec.email,
                "error": "Reset link expired",
            },
            status_code=400,
        )

    user: Optional[User] = db.exec(select(User).where(User.email == rec.email)).first()
    if user:
        user.hashed_password = hash_password(password)
        db.add(user)
    rec.used_at = now
    db.add(rec)
    db.commit()

    return safe_external_redirect(
        request,
        "/login",
        status_code=303,
        public_base_url=settings.public_base_url,
    )
