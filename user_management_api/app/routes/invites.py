from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, safe_external_redirect
from app.core.config import settings
from app.core.security import validate_new_password
from app.db import get_db
from app.invite_email_domains import invite_email_domain_allowed
from app.models import InviteToken, User
from app.routes.deps import admin_from_bearer, bearer_scheme
from app.routes.email_links import external_accept_invite_url
from app.services.directory import lookup_email
from app.services.email import send_invite_email
from app.services.tokens import invalidate_unused_invite_tokens
from app.web.templates import templates


router = APIRouter(prefix="/invites", tags=["invites"])
log = logging.getLogger("uvicorn.error")


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("")
async def create_invite(
    request: Request,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await admin_from_bearer(db=db, creds=creds)
    email = _norm_email(str(payload.get("email") or ""))
    grant_admin = bool(payload.get("grant_admin") or False)
    if not email:
        raise HTTPException(status_code=422, detail="email is required")

    if not invite_email_domain_allowed(email):
        raise HTTPException(
            status_code=422,
            detail="email domain is not allowed for invites",
        )

    if settings.directory_lookup_url and settings.directory_lookup_required:
        try:
            rec = lookup_email(email)
        except Exception:
            raise HTTPException(status_code=422, detail="directory lookup failed")
        if not rec:
            raise HTTPException(
                status_code=422, detail="email not found in directory"
            )

    raw = InviteToken.new_raw_token()
    token_hash = InviteToken.hash_token(raw)
    now = datetime.now(timezone.utc)
    await invalidate_unused_invite_tokens(db, email=email, now=now)
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

    invite_url = external_accept_invite_url(request, token=raw)
    try:
        send_invite_email(to_email=email, invite_url=invite_url)
    except Exception:
        log.exception("invite_email_send_failed")

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
    await admin_from_bearer(db=db, creds=creds)
    email = _norm_email(str(payload.get("email") or ""))
    if not email:
        raise HTTPException(status_code=422, detail="email is required")
    if not settings.directory_lookup_url:
        return {"ok": True, "email": "", "country": "", "display_name": ""}
    rec = None
    try:
        rec = lookup_email(email)
    except Exception:
        log.warning("invite_directory_preview_lookup_failed", exc_info=True)
    return {
        "ok": True,
        "email": rec.email if rec else "",
        "country": rec.country if rec else "",
        "display_name": rec.display_name if rec else "",
    }


@router.post("/inspect")
async def inspect_invite_token(
    payload: dict = Body(...), db: AsyncSession = Depends(get_db)
) -> dict:
    token = str(payload.get("token") or "")
    if not token:
        raise HTTPException(status_code=422, detail="token is required")

    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    return {
        "ok": True,
        "email": invite.email,
        "expires_at": invite.expires_at,
        "used_at": invite.used_at,
        "grant_admin": bool(invite.grant_admin),
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
    from app.core.security import hash_password

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
    if not invite_email_domain_allowed(invite.email):
        raise HTTPException(status_code=400, detail="Email domain is not allowed")

    existing = (
        await db.exec(select(User).where(User.email == invite.email))
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )

    from app.services.tokens import try_consume_invite_token

    consumed = await try_consume_invite_token(db, token_hash=token_hash, now=now)
    if consumed != 1:
        raise HTTPException(status_code=400, detail="Invite already used")

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
        validate_new_password(password)
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
    return safe_external_redirect(request, "/login", status_code=303)


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
    try:
        validate_new_password(password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _accept(db=db, token=token, password=password, full_name=full_name_s)
    return {"ok": True}
