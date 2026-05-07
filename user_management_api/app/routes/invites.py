from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, external_url, safe_external_redirect
from app.core.config import settings
from app.core.security import decode_token, hash_password
from app.db import get_db
from app.models import InviteToken, User
from app.services.directory import lookup_email
from app.services.email import send_invite_email
from app.web.templates import templates


router = APIRouter(prefix="/invites", tags=["invites"])

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


async def _require_admin(
    db: AsyncSession, creds: Optional[HTTPAuthorizationCredentials]
) -> User:
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
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("")
async def create_invite(
    request: Request,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await _require_admin(db, creds)
    email = _norm_email(str(payload.get("email") or ""))
    grant_admin = bool(payload.get("grant_admin") or False)
    if not email:
        raise HTTPException(status_code=422, detail="email is required")

    if settings.directory_lookup_url:
        try:
            rec = lookup_email(email)
        except Exception:
            rec = None
        if settings.directory_lookup_required and not rec:
            raise HTTPException(status_code=422, detail="email not found in directory")

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
    await db.commit()

    invite_url = _invite_url(request, raw)
    try:
        send_invite_email(to_email=email, invite_url=invite_url)
    except Exception:
        # Email should not break invite creation.
        pass

    return {
        "ok": True,
        "invite_url": invite_url,
        "expires_at": invite.expires_at,
    }


@router.post("/lookup")
async def lookup_invite_email(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await _require_admin(db, creds)
    email = _norm_email(str(payload.get("email") or ""))
    if not email:
        raise HTTPException(status_code=422, detail="email is required")
    if not settings.directory_lookup_url:
        return {"ok": True}
    try:
        rec = lookup_email(email)
    except Exception:
        raise HTTPException(status_code=400, detail="Directory lookup failed")
    if settings.directory_lookup_required and not rec:
        raise HTTPException(status_code=422, detail="email not found in directory")
    return {
        "ok": True,
        "email": rec.email if rec else "",
        "country": rec.country if rec else "",
        "display_name": rec.display_name if rec else "",
    }


@router.get("/accept", response_class=HTMLResponse, include_in_schema=False)
async def accept_invite_page(
    request: Request, token: str, db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    bp = base_path(request)
    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
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


async def _accept(
    *, db: AsyncSession, token: str, password: str, full_name: str | None = None
) -> None:
    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    now = datetime.now(timezone.utc)
    if invite.used_at is not None:
        raise HTTPException(status_code=400, detail="Invite already used")
    if _as_utc_aware(invite.expires_at) < now:
        raise HTTPException(status_code=400, detail="Invite expired")

    user = (await db.exec(select(User).where(User.email == invite.email))).first()
    if user:
        user.hashed_password = hash_password(password)
        user.is_admin = bool(user.is_admin or invite.grant_admin)
        if full_name is not None:
            fn = full_name.strip()
            if fn:
                user.full_name = fn
        if settings.directory_lookup_url:
            try:
                rec = lookup_email(invite.email)
            except Exception:
                rec = None
            if rec and rec.country and not user.country:
                user.country = rec.country
    else:
        fn = (full_name or "").strip() or None
        country = None
        if settings.directory_lookup_url:
            try:
                rec = lookup_email(invite.email)
            except Exception:
                rec = None
            if rec and rec.country:
                country = rec.country
        user = User(
            email=invite.email,
            full_name=fn,
            country=country,
            hashed_password=hash_password(password),
            is_admin=bool(invite.grant_admin),
        )
        db.add(user)
    invite.used_at = now
    db.add(invite)
    await db.commit()


@router.post("/accept-form", response_class=HTMLResponse, include_in_schema=False)
async def accept_invite_form(
    request: Request,
    token: str = Form(...),
    full_name: Optional[str] = Form(default=None),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    try:
        await _accept(db=db, token=token, password=password, full_name=full_name)
    except HTTPException as e:
        token_hash = InviteToken.hash_token(token)
        invite: Optional[InviteToken] = (
            await db.exec(
                select(InviteToken).where(InviteToken.token_hash == token_hash)
            )
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
    )


@router.post("/accept")
async def accept_invite_api(
    payload: dict = Body(...), db: AsyncSession = Depends(get_db)
) -> dict:
    token = str(payload.get("token") or "")
    password = str(payload.get("password") or "")
    full_name = payload.get("full_name")
    full_name_s = None if full_name is None else str(full_name)
    if not token or not password:
        raise HTTPException(status_code=422, detail="token and password are required")
    await _accept(db=db, token=token, password=password, full_name=full_name_s)
    return {"ok": True}
