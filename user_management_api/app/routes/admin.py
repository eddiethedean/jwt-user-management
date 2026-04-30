from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlmodel import Session, select

from fastapi_workbench import external_url, safe_redirect
from app.core.config import settings
from app.core.security import create_access_token, decode_token, verify_password
from app.db import get_db
from app.models import InviteToken, User


router = APIRouter(tags=["admin"])
log = logging.getLogger("uvicorn.error")
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

ADMIN_EMAIL = (os.getenv("SEED_ADMIN_EMAIL") or "admin@example.com").strip().lower()


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _invite_url(request: Request, token: str) -> str:
    return external_url(
        request,
        f"/invites/accept?token={token}",
        public_base_url=settings.public_base_url,
    )


def _require_admin_user(*, db: Session, token: str) -> User:
    try:
        payload: dict[str, Any] = decode_token(token)
        user_id = int(payload.get("sub") or 0)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    if user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page(
    request: Request,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    if not token:
        # Use a relative redirect to avoid Workbench rewriting absolute-path
        # redirects into /proxy/<port>/... (which may not be browser-routable).
        if os.getenv("WORKBENCH_DEBUG"):
            log.warning(
                "Admin redirect: scope.root_path=%r path=%r -> Location=%r",
                request.scope.get("root_path"),
                request.url.path,
                "admin/login",
            )
        return safe_redirect(request, "/admin/login", status_code=303)
    user = _require_admin_user(db=db, token=token)

    users = db.exec(select(User).order_by(text("id"))).all()
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "users": users,
            "email": user.email,
            "token": token,
            "base_path": bp,
            "invite_url": None,
            "invite_error": None,
            "invite_email": "",
        },
    )


@router.get("/admin/login", response_class=HTMLResponse, include_in_schema=False)
def admin_login_page(request: Request) -> HTMLResponse:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {"request": request, "admin_email": ADMIN_EMAIL, "base_path": bp},
    )


@router.post("/admin/login", response_class=HTMLResponse, include_in_schema=False)
def admin_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    email_n = _norm_email(email)
    user: Optional[User] = db.exec(select(User).where(User.email == email_n)).first()
    if (
        not user
        or user.email != ADMIN_EMAIL
        or not verify_password(password, user.hashed_password)
    ):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "request": request,
                "error": "Invalid credentials",
                "admin_email": ADMIN_EMAIL,
                "base_path": bp,
            },
            status_code=400,
        )

    token = create_access_token(subject=str(user.id))
    # Relative redirect so Workbench doesn't rewrite into /proxy/<port>/...
    # We are at /admin/login, so ../admin resolves correctly under any prefix.
    return RedirectResponse(url=f"../admin?token={token}", status_code=303)


@router.post("/admin/invite", response_class=HTMLResponse, include_in_schema=False)
def admin_invite_submit(
    request: Request,
    token: str = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    admin_user = _require_admin_user(db=db, token=token)

    email_n = _norm_email(email)
    if not email_n:
        raise HTTPException(status_code=422, detail="email is required")

    raw = InviteToken.new_raw_token()
    token_hash = InviteToken.hash_token(raw)
    now = datetime.now(timezone.utc)
    invite = InviteToken(
        email=email_n,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(days=7),
        used_at=None,
    )
    db.add(invite)
    db.commit()

    users = db.exec(select(User).order_by(text("id"))).all()
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "users": users,
            "email": admin_user.email,
            "token": token,
            "base_path": bp,
            "invite_url": _invite_url(request, raw),
            "invite_error": None,
            "invite_email": email_n,
        },
    )
