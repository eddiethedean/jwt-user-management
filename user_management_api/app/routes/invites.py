from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from jose import JWTError
from sqlmodel import Session, select

from fastapi_workbench import external_url, safe_external_redirect
from app.core.config import settings
from app.core.security import decode_token, hash_password
from app.db import get_db
from app.models import InviteToken, User


router = APIRouter(prefix="/invites", tags=["invites"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

bearer_scheme = HTTPBearer(auto_error=False)
ADMIN_EMAIL = (os.getenv("SEED_ADMIN_EMAIL") or "admin@example.com").strip().lower()


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _invite_url(request: Request, token: str) -> str:
    # Prefer an explicitly configured browser-routable host (PUBLIC_BASE_URL) if set.
    return external_url(
        request,
        f"/invites/accept?token={token}",
        public_base_url=settings.public_base_url,
    )


def _as_utc_aware(dt: datetime) -> datetime:
    """
    SQLite commonly returns naive datetimes even when we store timezone-aware values.
    Treat naive DB timestamps as UTC to keep comparisons consistent.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _require_admin(db: Session, creds: Optional[HTTPAuthorizationCredentials]) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload: dict[str, Any] = decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")
    user = db.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("")
def create_invite(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    _require_admin(db, creds)
    email = _norm_email(str(payload.get("email") or ""))
    grant_admin = bool(payload.get("grant_admin") or False)
    if not email:
        raise HTTPException(status_code=422, detail="email is required")

    raw = InviteToken.new_raw_token()
    token_hash = InviteToken.hash_token(raw)
    now = datetime.now(timezone.utc)
    invite = InviteToken(
        email=email,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(days=7),
        used_at=None,
        grant_admin=grant_admin,
    )
    db.add(invite)
    db.commit()

    return {
        "ok": True,
        "invite_url": _invite_url(request, raw),
        "expires_at": invite.expires_at,
    }


@router.get("/accept", response_class=HTMLResponse, include_in_schema=False)
def accept_invite_page(
    request: Request, token: str, db: Session = Depends(get_db)
) -> HTMLResponse:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = db.exec(
        select(InviteToken).where(InviteToken.token_hash == token_hash)
    ).first()
    if not invite:
        return templates.TemplateResponse(
            request,
            "accept_invite.html",
            {
                "request": request,
                "token": token,
                "error": "Invite not found",
                "base_path": bp,
            },
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "accept_invite.html",
        {
            "request": request,
            "token": token,
            "invite_email": invite.email,
            "base_path": bp,
        },
    )


def _accept(*, db: Session, token: str, password: str) -> None:
    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = db.exec(
        select(InviteToken).where(InviteToken.token_hash == token_hash)
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    now = datetime.now(timezone.utc)
    if invite.used_at is not None:
        raise HTTPException(status_code=400, detail="Invite already used")
    if _as_utc_aware(invite.expires_at) < now:
        raise HTTPException(status_code=400, detail="Invite expired")

    user = db.exec(select(User).where(User.email == invite.email)).first()
    if user:
        user.hashed_password = hash_password(password)
        user.is_admin = bool(user.is_admin or invite.grant_admin)
    else:
        user = User(
            email=invite.email,
            hashed_password=hash_password(password),
            is_admin=bool(invite.grant_admin),
        )
        db.add(user)
    invite.used_at = now
    db.add(invite)
    db.commit()


@router.post("/accept-form", response_class=HTMLResponse, include_in_schema=False)
def accept_invite_form(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    try:
        _accept(db=db, token=token, password=password)
    except HTTPException as e:
        token_hash = InviteToken.hash_token(token)
        invite: Optional[InviteToken] = db.exec(
            select(InviteToken).where(InviteToken.token_hash == token_hash)
        ).first()
        return templates.TemplateResponse(
            request,
            "accept_invite.html",
            {
                "request": request,
                "token": token,
                "invite_email": invite.email if invite else "",
                "error": e.detail,
                "base_path": bp,
            },
            status_code=e.status_code,
        )
    # Use a full external URL so Workbench doesn't rewrite it to /proxy/<port>/...
    # and so the browser doesn't resolve relative paths incorrectly.
    return safe_external_redirect(
        request,
        "/login",
        status_code=303,
        public_base_url=settings.public_base_url,
    )


@router.post("/accept")
def accept_invite_api(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    token = str(payload.get("token") or "")
    password = str(payload.get("password") or "")
    if not token or not password:
        raise HTTPException(status_code=422, detail="token and password are required")
    _accept(db=db, token=token, password=password)
    return {"ok": True}
