from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, safe_external_redirect
from app.core.config import settings
from app.core.email_validation import validate_email_format
from app.core.rate_limit import check_rate_limit
from app.core.security import validate_new_password
from app.db import get_db
from app.invite_email_domains import invite_email_domain_allowed
from app.models import InviteToken, User
from app.routes.deps import admin_from_bearer, bearer_scheme
from app.routes.email_links import external_accept_invite_url
from app.schemas.invites import (
    CreateInviteRequest,
    InspectInviteRequest,
    InviteAcceptRequest,
    InviteLookupRequest,
)
from app.services.directory import lookup_email_async
from app.services.email import send_invite_email
from app.services.tokens import create_invite_token_atomic, try_consume_invite_token
from app.web.csrf import issue_csrf_token, set_csrf_cookie, validate_csrf
from app.web.templates import templates


router = APIRouter(prefix="/invites", tags=["invites"])
log = logging.getLogger("uvicorn.error")


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _ensure_no_existing_user(db: AsyncSession, email: str) -> None:
    existing = (await db.exec(select(User).where(User.email == email))).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already has an account")


@router.post("")
async def create_invite(
    request: Request,
    payload: CreateInviteRequest,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await admin_from_bearer(db=db, creds=creds)
    try:
        email = validate_email_format(payload.email)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not invite_email_domain_allowed(email):
        raise HTTPException(
            status_code=422,
            detail="email domain is not allowed for invites",
        )

    await _ensure_no_existing_user(db, email)

    if settings.directory_lookup_url and settings.directory_lookup_required:
        try:
            rec = await lookup_email_async(email)
        except Exception:
            raise HTTPException(status_code=422, detail="directory lookup failed")
        if not rec:
            raise HTTPException(status_code=422, detail="email not found in directory")

    raw = await create_invite_token_atomic(
        db, email=email, grant_admin=payload.grant_admin
    )

    invite_url = external_accept_invite_url(request, token=raw)
    try:
        send_invite_email(to_email=email, invite_url=invite_url)
    except Exception:
        log.exception("invite_email_send_failed")

    invite_row = (
        await db.exec(
            select(InviteToken).where(
                InviteToken.token_hash == InviteToken.hash_token(raw)
            )
        )
    ).first()
    expires_at = invite_row.expires_at if invite_row else datetime.now(timezone.utc)

    return {
        "ok": True,
        "invite_url": invite_url,
        "expires_at": expires_at,
    }


@router.post("/lookup")
async def lookup_invite_email(
    payload: InviteLookupRequest,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await admin_from_bearer(db=db, creds=creds)
    try:
        email = validate_email_format(payload.email)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not settings.directory_lookup_url:
        return {"ok": True, "email": "", "country": "", "display_name": ""}
    rec = None
    try:
        rec = await lookup_email_async(email)
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
    payload: InspectInviteRequest,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    await admin_from_bearer(db=db, creds=creds)
    token_hash = InviteToken.hash_token(payload.token)
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
    csrf = issue_csrf_token(request)
    token_hash = InviteToken.hash_token(token)
    invite: Optional[InviteToken] = (
        await db.exec(select(InviteToken).where(InviteToken.token_hash == token_hash))
    ).first()
    if not invite:
        resp = templates.TemplateResponse(
            request,
            "accept_invite.html",
            {
                "request": request,
                "token": token,
                "error": "Invite not found",
                "base_path": bp,
                "csrf_token": csrf,
            },
            status_code=404,
        )
        set_csrf_cookie(resp, request=request)
        return resp
    resp = templates.TemplateResponse(
        request,
        "accept_invite.html",
        {
            "request": request,
            "token": token,
            "invite_email": invite.email,
            "base_path": bp,
            "csrf_token": csrf,
        },
    )
    set_csrf_cookie(resp, request=request)
    return resp


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

    existing = (await db.exec(select(User).where(User.email == invite.email))).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )

    consumed = await try_consume_invite_token(db, token_hash=token_hash, now=now)
    if consumed != 1:
        raise HTTPException(status_code=400, detail="Invite already used")

    dup = (await db.exec(select(User).where(User.email == invite.email))).first()
    if dup:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )

    fn = (full_name or "").strip() or None
    country = None
    if settings.directory_lookup_url:
        try:
            rec = await lookup_email_async(invite.email)
        except Exception:
            rec = None
        if rec and rec.country:
            country = rec.country
    grant_admin = bool(invite.grant_admin)
    user = User(
        email=invite.email,
        full_name=fn,
        country=country,
        hashed_password=hash_password(password),
        is_admin=grant_admin,
        roles="Admin" if grant_admin else "User",
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )


@router.post("/accept-form", response_class=HTMLResponse, include_in_schema=False)
async def accept_invite_form(
    request: Request,
    token: str = Form(...),
    full_name: Optional[str] = Form(default=None),
    password: str = Form(...),
    csrf_token: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    bp = base_path(request)
    validate_csrf(request, form_token=csrf_token)
    check_rate_limit(request, scope="invites_accept")
    try:
        validate_new_password(password)
        await _accept(db=db, token=token, password=password, full_name=full_name)
    except HTTPException as e:
        csrf = issue_csrf_token(request)
        token_hash = InviteToken.hash_token(token)
        invite: Optional[InviteToken] = (
            await db.exec(
                select(InviteToken).where(InviteToken.token_hash == token_hash)
            )
        ).first()
        resp = templates.TemplateResponse(
            request,
            "accept_invite.html",
            {
                "request": request,
                "token": token,
                "invite_email": invite.email if invite else "",
                "error": e.detail,
                "base_path": bp,
                "csrf_token": csrf,
            },
            status_code=e.status_code,
        )
        set_csrf_cookie(resp, request=request)
        return resp
    return safe_external_redirect(request, "/login", status_code=303)


@router.post("/accept")
async def accept_invite_api(
    request: Request,
    payload: InviteAcceptRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    check_rate_limit(request, scope="invites_accept")
    try:
        validate_new_password(payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _accept(
        db=db,
        token=payload.token,
        password=payload.password,
        full_name=payload.full_name,
    )
    return {"ok": True}
